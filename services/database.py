from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config.settings import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# --- Enums ---


class ContentSource(StrEnum):
    EMAIL = "email"
    BOOKMARK = "bookmark"
    RSS = "rss"
    PHOTO = "photo"  # future stub


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIAL = "partial"  # some items approved, some rejected


class ActionType(StrEnum):
    LABEL = "label"
    ARCHIVE = "archive"
    DELETE = "delete"
    UNSUBSCRIBE = "unsubscribe"
    DRAFT_REPLY = "draft_reply"
    MARK_READ = "mark_read"
    BOOKMARK_TAG = "bookmark_tag"
    PUBLISH_SUMMARY = "publish_summary"


# --- Models ---


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # "Evan", "Wife"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class ContentItem(Base):
    """A piece of content from any source (email, bookmark, RSS, photo)."""

    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer)
    source: Mapped[ContentSource] = mapped_column(SAEnum(ContentSource))
    external_id: Mapped[str] = mapped_column(String(500))  # Gmail msg ID, bookmark URL, etc.
    title: Mapped[str] = mapped_column(String(500), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    full_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # AI analysis
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitivity_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReviewBatch(Base):
    """A batch of proposed actions for user review."""

    __tablename__ = "review_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[ReviewStatus] = mapped_column(SAEnum(ReviewStatus), default=ReviewStatus.PENDING)
    batch_summary: Mapped[str] = mapped_column(Text, default="")
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProposedAction(Base):
    """A single proposed action within a review batch."""

    __tablename__ = "proposed_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer)
    content_item_id: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[ActionType] = mapped_column(SAEnum(ActionType))
    action_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = pending
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
