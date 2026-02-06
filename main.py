"""Automate sidecar — lightweight API for things n8n can't do natively.

n8n handles: Gmail, scheduling, approval workflows, LLM nodes, action execution.
This sidecar handles: URL content fetching (BeautifulSoup + markdownify),
Chrome bookmark file parsing (host filesystem access from Docker).

n8n workflows call these endpoints via HTTP Request nodes.
"""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import settings
from services.bookmarks.ingester import (
    fetch_and_distill,
    fetch_url_content,
    find_chrome_bookmarks_path,
    parse_chrome_bookmarks,
)
from services.llm import llm_router

logging.basicConfig(level=getattr(logging, settings.log_level))
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    health = await llm_router.health()
    log.info(f"LLM providers: {health}")
    yield


app = FastAPI(
    title="Automate Sidecar",
    description="URL content fetching & Chrome bookmark parsing for n8n workflows",
    version="0.3.0",
    lifespan=lifespan,
)


# =============================================================================
# Health
# =============================================================================


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_providers": await llm_router.health(),
    }


# =============================================================================
# Content — fetch any URL and return clean markdown (the sidecar's core job)
# =============================================================================


class ContentFetchRequest(BaseModel):
    """Fetch a URL and return clean markdown content.

    This is the sidecar's primary purpose: BeautifulSoup + markdownify
    strips boilerplate and produces LLM-ready text that n8n's native
    Ollama/Claude nodes can then classify and summarize.
    """

    url: str
    max_chars: int = 8000


@app.post("/content/fetch")
async def content_fetch(req: ContentFetchRequest):
    """Fetch a URL, strip HTML boilerplate, return clean markdown.

    n8n workflow 05 calls this for bookmark URLs. Email content
    doesn't need this — it's already text.

    Returns:
        content_markdown: Clean markdown text (truncated to max_chars)
        title: Page <title> if found
        word_count: Approximate word count
        error: Error message if fetch failed (content_markdown will have a fallback)
    """
    log.info(f"Fetching content: {req.url}")
    result = await fetch_url_content(req.url, max_chars=req.max_chars)
    return {
        "content_markdown": result.content_markdown,
        "title": result.title,
        "word_count": result.word_count,
        "url": result.url,
        "error": result.error,
    }


# =============================================================================
# LLM — privacy-first routing (DEPRECATED: workflows now use n8n native nodes)
# =============================================================================


class AnalyzeRequest(BaseModel):
    """Send content through the privacy-first LLM pipeline.

    Pass 1: Local model screens for sensitive content.
    Pass 2: If clean, optionally routes to a cloud model for better analysis.
    """

    content: str
    system_prompt: str = ""
    analysis_prompt: str = ""
    provider: str | None = None  # force a specific provider, or None for auto-routing


class AnalyzeResponse(BaseModel):
    result: str
    provider_used: str
    model_used: str
    kept_local: bool


@app.post("/llm/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """Privacy-first content analysis.

    n8n workflows send email bodies, bookmark content, etc. here.
    The sidecar screens locally first, then routes to cloud if clean.
    """
    screening_prompt = (
        "Analyze this content for sensitive information. "
        "Sensitive means: PII (SSN, account numbers, medical info, passwords, "
        "financial details), or clearly personal/private in nature "
        "(health, legal, intimate). "
        "Respond with ONLY the word SENSITIVE or CLEAN.\n\n"
        "Content:\n{content}"
    )

    analysis_prompt = req.analysis_prompt or (
        "{content}\n\nAnalyze the above content. Provide a structured JSON response."
    )

    result = await llm_router.screen_then_analyze(
        content=req.content,
        screening_prompt=screening_prompt,
        analysis_prompt=analysis_prompt,
        analysis_provider=req.provider,
    )

    return AnalyzeResponse(
        result=result["analysis"].content,
        provider_used=result["analysis"].provider,
        model_used=result["analysis"].model,
        kept_local=result["kept_local"],
    )


class CompletionRequest(BaseModel):
    """Direct LLM completion — bypass privacy screening."""

    prompt: str
    system: str = ""
    provider: str = "ollama"
    temperature: float = 0.3
    max_tokens: int = 4096


@app.post("/llm/complete")
async def complete(req: CompletionRequest):
    """Direct completion on a specific provider. For when you know what you want."""
    try:
        resp = await llm_router.complete(
            prompt=req.prompt,
            system=req.system,
            provider=req.provider,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        return {"result": resp.content, "provider": resp.provider, "model": resp.model}
    except Exception as e:
        raise HTTPException(500, f"LLM completion failed: {e}") from e


@app.get("/llm/test")
async def test_llm(provider: str = "ollama"):
    """Quick health check for a specific LLM provider."""
    try:
        resp = await llm_router.complete(
            prompt="Say 'hello' and nothing else.",
            provider=provider,
            max_tokens=10,
        )
        return {"provider": provider, "response": resp.content, "model": resp.model}
    except Exception as e:
        raise HTTPException(500, f"LLM test failed: {e}") from e


# =============================================================================
# Bookmarks — Chrome bookmarks file parsing (n8n can't read local files)
# =============================================================================


@app.get("/bookmarks/detect")
async def detect_bookmarks():
    """Check if Chrome bookmarks file exists and return stats."""
    path = find_chrome_bookmarks_path()
    if path:
        bookmarks = parse_chrome_bookmarks(path)
        folders = sorted({b.folder for b in bookmarks if b.folder})
        return {
            "found": True,
            "path": str(path),
            "bookmark_count": len(bookmarks),
            "folders": folders,
            "sample": [{"title": b.title, "url": b.url, "folder": b.folder} for b in bookmarks[:5]],
        }
    return {"found": False, "path": None, "bookmark_count": 0}


@app.get("/bookmarks/list")
async def list_bookmarks(
    folder: str = "",
    since_days: int = 0,
    limit: int = 50,
):
    """Return bookmarks as JSON for n8n to iterate over.

    n8n's SplitInBatches node can then process each one.
    """
    path = find_chrome_bookmarks_path()
    if not path:
        raise HTTPException(400, "Chrome bookmarks file not found")

    bookmarks = parse_chrome_bookmarks(path)

    if folder:
        bookmarks = [b for b in bookmarks if folder.lower() in b.folder.lower()]

    if since_days:
        cutoff = datetime.now(UTC) - timedelta(days=since_days)
        bookmarks = [b for b in bookmarks if b.date_added and b.date_added >= cutoff]

    bookmarks = bookmarks[:limit]

    return {
        "count": len(bookmarks),
        "bookmarks": [
            {
                "title": b.title,
                "url": b.url,
                "folder": b.folder,
                "date_added": b.date_added.isoformat() if b.date_added else None,
            }
            for b in bookmarks
        ],
    }


class DigestRequest(BaseModel):
    url: str
    title: str = ""


@app.post("/bookmarks/digest")
async def digest_bookmark(req: DigestRequest):
    """Fetch a single URL and distill it with an LLM.

    n8n sends one bookmark at a time (from SplitInBatches).
    """
    from services.bookmarks.ingester import Bookmark

    bookmark = Bookmark(url=req.url, title=req.title)
    digest = await fetch_and_distill(bookmark)

    return {
        "title": digest.bookmark.title,
        "url": digest.bookmark.url,
        "summary": digest.summary,
        "key_takeaways": digest.key_takeaways,
        "category": digest.category,
        "suggested_tags": digest.suggested_tags,
        "read_time_minutes": digest.read_time_minutes,
        "word_count": digest.word_count,
    }


class IngestRequest(BaseModel):
    """Incoming bookmark from the Chrome extension or iOS Shortcut.

    The extension POSTs here when a bookmark is created.
    This endpoint fetches + distills in one shot.
    """

    url: str
    title: str = ""
    folder: str = ""


@app.post("/bookmarks/ingest")
async def ingest_bookmark(req: IngestRequest):
    """One-shot bookmark ingestion: receive → fetch → distill → return digest.

    Called by:
    - Chrome extension (chrome.bookmarks.onCreated → POST here)
    - iOS Shortcut (Share Sheet → POST here)
    - n8n webhook relay (if you prefer n8n as the entry point)

    Returns the full digest JSON that n8n or any consumer can act on.
    """
    from services.bookmarks.ingester import Bookmark

    log.info(f"Ingesting bookmark: {req.title or req.url}")

    bookmark = Bookmark(url=req.url, title=req.title, folder=req.folder)
    digest = await fetch_and_distill(bookmark)

    return {
        "status": "ingested",
        "title": digest.bookmark.title or req.title,
        "url": digest.bookmark.url,
        "folder": req.folder,
        "summary": digest.summary,
        "key_takeaways": digest.key_takeaways,
        "category": digest.category,
        "suggested_tags": digest.suggested_tags,
        "read_time_minutes": digest.read_time_minutes,
        "word_count": digest.word_count,
    }
