"""
Photos Watcher — STUB for future implementation.

Architecture notes:
- Google Photos API: read-only access to list/download photos
- Apple iCloud: no official API, but can use pyicloud or watch ~/Pictures/Photos Library
- Vision analysis: use Qwen2.5-VL-7B (local) or Gemini (cloud) for image understanding

Planned triggers:
- New photo added to a specific album (e.g., "Automate" or "Books")
- Photo matches a pattern (thumbs up + bookshelf = scan for book titles)

Planned actions:
- OCR / scene analysis via vision LLM
- Extract structured data (book titles, receipts, whiteboard text)
- Route to appropriate pipeline (books -> review lookup, receipt -> archive)

Integration points:
- Same ContentItem model (source=ContentSource.PHOTO)
- Same review queue (proposed actions need approval)
- Same LLM router (local vision model for screening, cloud for deep analysis)

No implementation yet — this file documents the architecture for when we're ready.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class PhotoTriggerType(StrEnum):
    NEW_PHOTO = "new_photo"
    ALBUM_ADDITION = "album_addition"
    MANUAL_SCAN = "manual_scan"


@dataclass
class PhotoAnalysisRequest:
    """A photo to be analyzed."""

    source: str  # "google_photos" or "icloud"
    photo_id: str
    photo_url: str | None = None
    local_path: str | None = None
    trigger: PhotoTriggerType = PhotoTriggerType.NEW_PHOTO
    albums: list[str] = field(default_factory=list)


@dataclass
class PhotoAnalysisResult:
    """Result of analyzing a photo."""

    request: PhotoAnalysisRequest
    description: str = ""
    detected_objects: list[str] = field(default_factory=list)
    extracted_text: list[str] = field(default_factory=list)
    suggested_actions: list[dict] = field(default_factory=list)
    # e.g., [{"type": "book_lookup", "titles": ["Clean Code", "SICP"]}]


# Future: implement these
# async def watch_google_photos(account_id: int, album_name: str): ...
# async def watch_icloud_photos(account_id: int): ...
# async def analyze_photo(request: PhotoAnalysisRequest) -> PhotoAnalysisResult: ...
