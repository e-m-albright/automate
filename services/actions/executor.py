import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import ActionType, ContentItem, ProposedAction
from services.gmail.client import GmailClient

log = logging.getLogger(__name__)


async def execute_approved_actions(
    session: AsyncSession,
    batch_id: int,
    gmail_client: GmailClient,
) -> dict:
    """Execute all approved actions in a batch. Returns execution summary."""
    result = await session.execute(
        select(ProposedAction).where(
            ProposedAction.batch_id == batch_id,
            ProposedAction.approved,
            not ProposedAction.executed,
        )
    )
    actions = list(result.scalars().all())

    summary = {"total": len(actions), "succeeded": 0, "failed": 0, "errors": []}

    for action in actions:
        item = await session.get(ContentItem, action.content_item_id)
        if not item:
            action.error = "Content item not found"
            action.executed = True
            action.executed_at = datetime.now(UTC)
            summary["failed"] += 1
            continue

        try:
            await _execute_single(action, item, gmail_client)
            action.executed = True
            action.executed_at = datetime.now(UTC)
            summary["succeeded"] += 1
            log.info(f"Executed {action.action_type.value} on {item.external_id}")
        except Exception as e:
            action.error = str(e)
            action.executed = True
            action.executed_at = datetime.now(UTC)
            summary["failed"] += 1
            summary["errors"].append({"action_id": action.id, "error": str(e)})
            log.error(f"Failed {action.action_type.value} on {item.external_id}: {e}")

    await session.commit()
    return summary


async def _execute_single(
    action: ProposedAction,
    item: ContentItem,
    gmail: GmailClient,
):
    """Execute a single approved action."""
    msg_id = item.external_id
    params = action.action_params or {}

    match action.action_type:
        case ActionType.ARCHIVE:
            gmail.archive(msg_id)

        case ActionType.DELETE:
            gmail.trash(msg_id)  # trash, not permanent delete

        case ActionType.MARK_READ:
            gmail.mark_read(msg_id)

        case ActionType.LABEL:
            label_name = params.get("label", "automate/general")
            label_id = gmail.get_or_create_label(label_name)
            gmail.add_label(msg_id, label_id)

        case ActionType.UNSUBSCRIBE:
            url = params.get("unsubscribe_url")
            if url and url.startswith("http"):
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                    log.info(f"Unsubscribe hit {url}: status={resp.status_code}")
            # Also archive the email
            gmail.archive(msg_id)

        case ActionType.DRAFT_REPLY:
            reply_body = params.get("reply_body", "")
            if reply_body and item.sender:
                gmail.create_draft(
                    to=item.sender,
                    subject=f"Re: {item.title}",
                    body=reply_body,
                    thread_id=item.metadata_json.get("thread_id") if item.metadata_json else None,
                )

        case _:
            raise ValueError(f"Unknown action type: {action.action_type}")
