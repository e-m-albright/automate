import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import (
    ActionType,
    ContentItem,
    ContentSource,
    ProposedAction,
    ReviewBatch,
    ReviewStatus,
)
from services.gmail.classifier import ClassificationResult

log = logging.getLogger(__name__)

# Map classifier suggestions to action types
ACTION_MAP = {
    "archive": ActionType.ARCHIVE,
    "delete": ActionType.DELETE,
    "unsubscribe": ActionType.UNSUBSCRIBE,
    "label": ActionType.LABEL,
    "draft_reply": ActionType.DRAFT_REPLY,
    "mark_read": ActionType.MARK_READ,
    "keep": None,  # no action needed
}


async def create_email_review_batch(
    session: AsyncSession,
    account_id: int,
    classifications: list[ClassificationResult],
    emails: dict,  # msg_id -> EmailMessage
) -> ReviewBatch:
    """Create a review batch from classified emails.

    Nothing is executed — everything is proposed and awaits approval.
    """
    batch = ReviewBatch(
        account_id=account_id,
        status=ReviewStatus.PENDING,
        item_count=len(classifications),
    )
    session.add(batch)
    await session.flush()  # get batch.id

    summaries_by_category = {}

    for cls_result in classifications:
        msg = emails.get(cls_result.email_id)
        if not msg:
            continue

        # Store the content item
        item = ContentItem(
            account_id=account_id,
            source=ContentSource.EMAIL,
            external_id=cls_result.email_id,
            title=msg.subject,
            snippet=msg.snippet,
            sender=msg.sender,
            category=cls_result.category,
            summary=cls_result.reason,
            sensitivity_flag=cls_result.is_sensitive,
            ai_provider_used="local" if cls_result.analyzed_locally else "cloud",
            processed_at=datetime.now(UTC),
        )
        session.add(item)
        await session.flush()

        # Create proposed actions
        for action_name in cls_result.suggested_actions:
            action_type = ACTION_MAP.get(action_name)
            if action_type is None:
                continue

            params = {}
            if action_type == ActionType.LABEL:
                params["label"] = f"automate/{cls_result.category.lower()}"
            if action_type == ActionType.UNSUBSCRIBE and cls_result.unsubscribe_url:
                params["unsubscribe_url"] = cls_result.unsubscribe_url

            action = ProposedAction(
                batch_id=batch.id,
                content_item_id=item.id,
                action_type=action_type,
                action_params=params,
                reason=cls_result.reason,
            )
            session.add(action)

        # Track for summary
        cat = cls_result.category
        summaries_by_category.setdefault(cat, 0)
        summaries_by_category[cat] += 1

    # Build human-readable batch summary
    parts = [f"{count} {cat.lower()}" for cat, count in sorted(summaries_by_category.items())]
    batch.batch_summary = f"Email batch: {', '.join(parts)}"

    await session.commit()
    log.info(f"Created review batch {batch.id}: {batch.batch_summary}")
    return batch


async def get_pending_batches(session: AsyncSession, account_id: int) -> list[ReviewBatch]:
    result = await session.execute(
        select(ReviewBatch)
        .where(ReviewBatch.account_id == account_id, ReviewBatch.status == ReviewStatus.PENDING)
        .order_by(ReviewBatch.created_at.desc())
    )
    return list(result.scalars().all())


async def get_batch_details(session: AsyncSession, batch_id: int) -> dict:
    """Get full batch details for the review UI."""
    batch = await session.get(ReviewBatch, batch_id)
    if not batch:
        return None

    actions_result = await session.execute(
        select(ProposedAction).where(ProposedAction.batch_id == batch_id)
    )
    actions = list(actions_result.scalars().all())

    # Join with content items
    item_ids = [a.content_item_id for a in actions]
    items_result = await session.execute(select(ContentItem).where(ContentItem.id.in_(item_ids)))
    items_map = {i.id: i for i in items_result.scalars().all()}

    return {
        "batch": batch,
        "actions": [
            {
                "action": a,
                "item": items_map.get(a.content_item_id),
            }
            for a in actions
        ],
    }


async def approve_batch(
    session: AsyncSession,
    batch_id: int,
    approved_action_ids: list[int] | None = None,
    reject_all: bool = False,
) -> ReviewBatch:
    """Approve (or reject) a review batch.

    If approved_action_ids is None and reject_all is False, approve everything.
    If approved_action_ids is a list, only approve those specific actions.
    """
    batch = await session.get(ReviewBatch, batch_id)
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    actions_result = await session.execute(
        select(ProposedAction).where(ProposedAction.batch_id == batch_id)
    )
    actions = list(actions_result.scalars().all())

    if reject_all:
        for a in actions:
            a.approved = False
        batch.status = ReviewStatus.REJECTED
    elif approved_action_ids is None:
        for a in actions:
            a.approved = True
        batch.status = ReviewStatus.APPROVED
    else:
        approved_set = set(approved_action_ids)
        has_approved = False
        has_rejected = False
        for a in actions:
            a.approved = a.id in approved_set
            if a.approved:
                has_approved = True
            else:
                has_rejected = True
        batch.status = (
            ReviewStatus.PARTIAL
            if (has_approved and has_rejected)
            else (ReviewStatus.APPROVED if has_approved else ReviewStatus.REJECTED)
        )

    batch.reviewed_at = datetime.now(UTC)
    await session.commit()
    return batch
