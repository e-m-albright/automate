import json
import logging
import os
import platform
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

from services.llm import llm_router

log = logging.getLogger(__name__)


@dataclass
class Bookmark:
    url: str
    title: str = ""
    date_added: datetime | None = None
    folder: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class DigestedBookmark:
    bookmark: Bookmark
    summary: str = ""
    key_takeaways: list[str] = field(default_factory=list)
    category: str = ""
    suggested_tags: list[str] = field(default_factory=list)
    full_text: str = ""
    word_count: int = 0
    read_time_minutes: int = 0


def find_chrome_bookmarks_path() -> Path | None:
    """Find Chrome's Bookmarks JSON file on the local filesystem.

    Chrome syncs bookmarks to a local JSON file — no extension needed.
    We just watch this file for changes.
    """
    system = platform.system()
    home = Path.home()

    candidates = []
    if system == "Darwin":
        candidates = [
            home / "Library/Application Support/Google/Chrome/Default/Bookmarks",
            home / "Library/Application Support/Google/Chrome/Profile 1/Bookmarks",
        ]
    elif system == "Linux":
        candidates = [
            home / ".config/google-chrome/Default/Bookmarks",
            home / ".config/chromium/Default/Bookmarks",
        ]
    elif system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            local / "Google/Chrome/User Data/Default/Bookmarks",
        ]

    for p in candidates:
        if p.exists():
            return p
    return None


def parse_chrome_bookmarks(bookmarks_path: Path) -> list[Bookmark]:
    """Parse Chrome's Bookmarks JSON file into a flat list."""
    with open(bookmarks_path) as f:
        data = json.load(f)

    bookmarks = []
    _walk_bookmark_tree(data.get("roots", {}), "", bookmarks)
    return bookmarks


def _walk_bookmark_tree(node: dict, folder: str, out: list[Bookmark]):
    if isinstance(node, dict):
        if node.get("type") == "url":
            date_added = None
            if "date_added" in node:
                try:
                    # Chrome uses Windows epoch (microseconds since 1601-01-01)
                    chrome_ts = int(node["date_added"])
                    unix_ts = (chrome_ts - 11644473600000000) / 1_000_000
                    date_added = datetime.fromtimestamp(unix_ts, tz=UTC)
                except (ValueError, OSError):
                    pass

            out.append(
                Bookmark(
                    url=node.get("url", ""),
                    title=node.get("name", ""),
                    date_added=date_added,
                    folder=folder,
                )
            )
        elif node.get("type") == "folder":
            subfolder = f"{folder}/{node.get('name', '')}" if folder else node.get("name", "")
            for child in node.get("children", []):
                _walk_bookmark_tree(child, subfolder, out)
        else:
            for _key, value in node.items():
                _walk_bookmark_tree(value, folder, out)


@dataclass
class FetchedContent:
    """Raw content fetched from a URL — no LLM processing, just clean markdown."""

    url: str
    title: str = ""
    content_markdown: str = ""
    word_count: int = 0
    error: str = ""


async def fetch_url_content(url: str, max_chars: int = 8000) -> FetchedContent:
    """Fetch a URL and return clean markdown content.

    This is the sidecar's core value-add: BeautifulSoup + markdownify
    strips boilerplate (nav, footer, scripts, ads) and converts to
    clean markdown that an LLM can consume.

    n8n calls this via POST /content/fetch. All LLM work (classification,
    summarization) now happens in n8n's native Ollama/Claude nodes.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                url, headers={"User-Agent": "Mozilla/5.0 (Automate Bot; content digest)"}
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract title from <title> tag if present
            page_title = ""
            if soup.title and soup.title.string:
                page_title = soup.title.string.strip()

            # Remove scripts, styles, nav, footer
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            content = markdownify(str(soup), strip=["img", "a"])
            content = content[:max_chars]
            word_count = len(content.split())

            return FetchedContent(
                url=url,
                title=page_title,
                content_markdown=content,
                word_count=word_count,
            )
    except Exception as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return FetchedContent(
            url=url,
            content_markdown=f"[Could not fetch content: {e}]",
            error=str(e),
        )


async def fetch_and_distill(bookmark: Bookmark) -> DigestedBookmark:
    """Fetch a bookmarked URL and distill its content with an LLM.

    DEPRECATED: New workflows use fetch_url_content() + n8n LLM nodes instead.
    Kept for backward compatibility with older workflow JSONs.
    """
    fetched = await fetch_url_content(bookmark.url)
    full_text = fetched.content_markdown
    word_count = fetched.word_count

    # Distill with LLM
    prompt = f"""Analyze this article/page and provide a structured digest.

Title: {bookmark.title}
URL: {bookmark.url}
Content:
{full_text}

Respond in JSON:
{{
    "summary": "2-3 sentence summary of the key points",
    "key_takeaways": ["takeaway 1", "takeaway 2", "takeaway 3"],
    "category": "one of: tech, business, science, health, politics, culture, tutorial, reference, tool, other",
    "suggested_tags": ["tag1", "tag2", "tag3"],
    "read_time_minutes": estimated_minutes_to_read_original
}}"""

    try:
        response = await llm_router.complete(prompt=prompt, temperature=0.2)
        data = json.loads(response.content)
    except Exception as e:
        log.warning(f"Failed to distill {bookmark.url}: {e}")
        data = {
            "summary": f"Content from {bookmark.title or bookmark.url}",
            "key_takeaways": [],
            "category": "other",
            "suggested_tags": [],
            "read_time_minutes": max(1, word_count // 250),
        }

    return DigestedBookmark(
        bookmark=bookmark,
        summary=data.get("summary", ""),
        key_takeaways=data.get("key_takeaways", []),
        category=data.get("category", "other"),
        suggested_tags=data.get("suggested_tags", []),
        full_text=full_text,
        word_count=word_count,
        read_time_minutes=data.get("read_time_minutes", max(1, word_count // 250)),
    )
