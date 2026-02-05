import logging
from contextlib import asynccontextmanager
from datetime import UTC

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from services.actions.executor import execute_approved_actions
from services.bookmarks.ingester import (
    fetch_and_distill,
    find_chrome_bookmarks_path,
    parse_chrome_bookmarks,
)
from services.database import get_session, init_db
from services.gmail.classifier import batch_classify
from services.gmail.client import GmailClient
from services.llm import llm_router
from services.review.queue import (
    approve_batch,
    create_email_review_batch,
    get_batch_details,
    get_pending_batches,
)

logging.basicConfig(level=getattr(logging, settings.log_level))
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    health = await llm_router.health()
    log.info(f"LLM providers: {health}")
    yield


app = FastAPI(
    title="Automate",
    description="Privacy-first email & content automation",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Health ---


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_providers": await llm_router.health(),
    }


# --- Gmail OAuth ---


class OAuthSetupRequest(BaseModel):
    account_name: str
    email: str


@app.post("/accounts/gmail/auth-url")
async def gmail_auth_url():
    """Get the OAuth URL for Gmail setup. User visits this in their browser."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080"],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.labels",
        ],
    )
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return {"auth_url": auth_url}


# --- Email Processing ---


class ProcessEmailsRequest(BaseModel):
    account_id: int
    query: str = "is:inbox"
    max_results: int = 50


@app.post("/emails/process")
async def process_emails(
    req: ProcessEmailsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Fetch, classify, and create a review batch. No actions taken yet."""
    from services.database import Account

    account = await session.get(Account, req.account_id)
    if not account or not account.google_refresh_token:
        raise HTTPException(400, "Account not found or not connected to Gmail")

    gmail = GmailClient.from_refresh_token(account.google_refresh_token)
    messages, next_page = gmail.fetch_messages(query=req.query, max_results=req.max_results)

    if not messages:
        return {"message": "No emails to process", "batch_id": None}

    classifications = await batch_classify(messages)
    emails_map = {m.id: m for m in messages}
    batch = await create_email_review_batch(session, account.id, classifications, emails_map)

    return {
        "batch_id": batch.id,
        "summary": batch.batch_summary,
        "item_count": batch.item_count,
        "next_page_token": next_page,
    }


# --- Review Queue ---


@app.get("/reviews/pending/{account_id}")
async def get_pending_reviews(
    account_id: int,
    session: AsyncSession = Depends(get_session),
):
    batches = await get_pending_batches(session, account_id)
    return [
        {
            "id": b.id,
            "summary": b.batch_summary,
            "item_count": b.item_count,
            "created_at": b.created_at.isoformat(),
        }
        for b in batches
    ]


@app.get("/reviews/{batch_id}")
async def get_review(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
):
    details = await get_batch_details(session, batch_id)
    if not details:
        raise HTTPException(404, "Batch not found")

    return {
        "batch": {
            "id": details["batch"].id,
            "summary": details["batch"].batch_summary,
            "status": details["batch"].status.value,
            "item_count": details["batch"].item_count,
        },
        "actions": [
            {
                "action_id": a["action"].id,
                "action_type": a["action"].action_type.value,
                "reason": a["action"].reason,
                "params": a["action"].action_params,
                "item": {
                    "title": a["item"].title if a["item"] else "",
                    "sender": a["item"].sender if a["item"] else "",
                    "snippet": a["item"].snippet if a["item"] else "",
                    "category": a["item"].category if a["item"] else "",
                    "sensitive": a["item"].sensitivity_flag if a["item"] else False,
                }
                if a["item"]
                else None,
            }
            for a in details["actions"]
        ],
    }


class ApprovalRequest(BaseModel):
    approved_action_ids: list[int] | None = None  # None = approve all
    reject_all: bool = False


@app.post("/reviews/{batch_id}/approve")
async def approve_review(
    batch_id: int,
    req: ApprovalRequest,
    session: AsyncSession = Depends(get_session),
):
    """Approve or reject a review batch, then execute approved actions."""
    batch = await approve_batch(
        session,
        batch_id,
        approved_action_ids=req.approved_action_ids,
        reject_all=req.reject_all,
    )

    if batch.status.value in ("approved", "partial"):
        # Need Gmail client to execute
        from services.database import Account

        account = await session.get(Account, batch.account_id)
        if account and account.google_refresh_token:
            gmail = GmailClient.from_refresh_token(account.google_refresh_token)
            summary = await execute_approved_actions(session, batch_id, gmail)
            return {"batch_status": batch.status.value, "execution": summary}

    return {"batch_status": batch.status.value, "execution": None}


# --- Bookmarks ---


@app.get("/bookmarks/detect")
async def detect_bookmarks():
    """Check if Chrome bookmarks file can be found."""
    path = find_chrome_bookmarks_path()
    if path:
        bookmarks = parse_chrome_bookmarks(path)
        return {
            "found": True,
            "path": str(path),
            "bookmark_count": len(bookmarks),
            "sample": [
                {"title": b.title, "url": b.url, "folder": b.folder} for b in bookmarks[:10]
            ],
        }
    return {"found": False, "path": None, "bookmark_count": 0}


class DigestBookmarksRequest(BaseModel):
    folder: str = ""  # empty = all bookmarks
    limit: int = 10
    since_days: int = 7  # only process bookmarks added in last N days


@app.post("/bookmarks/digest")
async def digest_bookmarks(req: DigestBookmarksRequest):
    """Fetch and distill bookmarks into summaries."""
    path = find_chrome_bookmarks_path()
    if not path:
        raise HTTPException(400, "Chrome bookmarks not found")

    bookmarks = parse_chrome_bookmarks(path)

    # Filter by folder if specified
    if req.folder:
        bookmarks = [b for b in bookmarks if req.folder.lower() in b.folder.lower()]

    # Filter by date if date_added is available
    from datetime import timedelta

    cutoff = None
    if req.since_days:
        from datetime import datetime

        cutoff = datetime.now(UTC) - timedelta(days=req.since_days)

    if cutoff:
        bookmarks = [b for b in bookmarks if b.date_added and b.date_added >= cutoff]

    bookmarks = bookmarks[: req.limit]

    results = []
    for bm in bookmarks:
        digest = await fetch_and_distill(bm)
        results.append(
            {
                "title": digest.bookmark.title,
                "url": digest.bookmark.url,
                "summary": digest.summary,
                "key_takeaways": digest.key_takeaways,
                "category": digest.category,
                "tags": digest.suggested_tags,
                "read_time": digest.read_time_minutes,
            }
        )

    return {"count": len(results), "digests": results}


# --- LLM Health ---


@app.get("/llm/test")
async def test_llm(provider: str = "ollama"):
    """Quick test that an LLM provider is working."""
    try:
        resp = await llm_router.complete(
            prompt="Say 'hello' and nothing else.",
            provider=provider,
            max_tokens=10,
        )
        return {"provider": provider, "response": resp.content, "model": resp.model}
    except Exception as e:
        raise HTTPException(500, f"LLM test failed: {e}") from e
