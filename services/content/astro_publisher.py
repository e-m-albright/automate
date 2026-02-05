import logging
from datetime import UTC, datetime
from pathlib import Path

from services.bookmarks.ingester import DigestedBookmark

log = logging.getLogger(__name__)


def publish_digest_to_astro(
    digest: DigestedBookmark,
    astro_content_dir: Path,
    collection: str = "digests",
) -> Path:
    """Write a digested bookmark as an Astro-compatible markdown file.

    Astro uses content collections with frontmatter. This creates a .md file
    in the specified collection directory.
    """
    output_dir = astro_content_dir / collection
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate slug from title
    slug = _slugify(digest.bookmark.title or digest.bookmark.url)
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"{date_str}-{slug}.md"

    frontmatter = {
        "title": digest.bookmark.title or digest.bookmark.url,
        "url": digest.bookmark.url,
        "date": date_str,
        "category": digest.category,
        "tags": digest.suggested_tags,
        "readTime": digest.read_time_minutes,
        "wordCount": digest.word_count,
        "folder": digest.bookmark.folder,
    }

    # Build the markdown content
    fm_lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}:")
            for item in value:
                fm_lines.append(f"  - {item}")
        else:
            fm_lines.append(f"{key}: {_yaml_escape(str(value))}")
    fm_lines.append("---")
    fm_lines.append("")

    body_lines = [
        "## Summary",
        "",
        digest.summary,
        "",
    ]

    if digest.key_takeaways:
        body_lines.append("## Key Takeaways")
        body_lines.append("")
        for takeaway in digest.key_takeaways:
            body_lines.append(f"- {takeaway}")
        body_lines.append("")

    body_lines.append(f"[Read original]({digest.bookmark.url})")

    content = "\n".join(fm_lines + body_lines) + "\n"

    output_path = output_dir / filename
    output_path.write_text(content)
    log.info(f"Published digest to {output_path}")
    return output_path


def publish_email_digest(
    batch_summary: str,
    items: list[dict],
    astro_content_dir: Path,
    collection: str = "email-digests",
) -> Path:
    """Publish an email review batch summary as a blog post."""
    output_dir = astro_content_dir / collection
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    time_str = datetime.now(UTC).strftime("%H%M")
    filename = f"{date_str}-inbox-review-{time_str}.md"

    content_parts = [
        "---",
        f"title: Inbox Review - {date_str}",
        f"date: {date_str}",
        "type: email-digest",
        "---",
        "",
        f"## {batch_summary}",
        "",
    ]

    # Group by category
    by_category: dict[str, list] = {}
    for item in items:
        cat = item.get("category", "other")
        by_category.setdefault(cat, []).append(item)

    for category, cat_items in sorted(by_category.items()):
        content_parts.append(f"### {category}")
        content_parts.append("")
        for item in cat_items:
            content_parts.append(
                f"- **{item.get('subject', 'No subject')}** from {item.get('sender', 'unknown')}"
            )
            if item.get("summary"):
                content_parts.append(f"  > {item['summary']}")
            content_parts.append("")

    output_path = output_dir / filename
    output_path.write_text("\n".join(content_parts) + "\n")
    log.info(f"Published email digest to {output_path}")
    return output_path


def _slugify(text: str) -> str:
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:60].rstrip("-")


def _yaml_escape(value: str) -> str:
    if any(c in value for c in ":#{}[]&*!|>'\"%@`"):
        return f'"{value}"'
    return value
