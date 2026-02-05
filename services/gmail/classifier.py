import json
import logging
from dataclasses import dataclass

from services.gmail.client import EmailMessage
from services.llm import llm_router

log = logging.getLogger(__name__)

SCREENING_PROMPT = """Analyze this email for sensitive content. Respond with ONLY "SENSITIVE" or "CLEAN".

Sensitive means: contains PII (SSN, account numbers, medical info, passwords, financial details),
or is clearly personal/private in nature (health, legal, intimate).

Email:
From: {sender}
Subject: {subject}
Body preview: {body}

Your response (one word):"""

CLASSIFICATION_PROMPT = """Classify this email into exactly ONE category and provide a brief reason.

Categories:
- JUNK: spam, marketing you never signed up for, scams
- NEWSLETTER: subscribed newsletters, digests, updates from services
- RECEIPT: purchase confirmations, shipping notifications, invoices
- SOCIAL: social media notifications, friend requests
- ACTIONABLE: requires a response or action from the user
- FYI: informational, no action needed but worth knowing
- PERSONAL: from a real person, personal communication
- IMPORTANT: urgent, time-sensitive, or high-priority

Email:
From: {sender}
Subject: {subject}
Date: {date}
Body: {body}

Respond in JSON format:
{{"category": "CATEGORY", "reason": "brief reason", "suggested_actions": ["action1"], "priority": 1-5}}

Suggested actions can include: archive, delete, unsubscribe, label, draft_reply, keep
Priority: 1=ignore, 2=low, 3=normal, 4=high, 5=urgent"""

UNSUBSCRIBE_PROMPT = """Look at this email body and find any unsubscribe link or mechanism.

Email body (HTML):
{body}

If you find an unsubscribe link, respond with JSON:
{{"has_unsubscribe": true, "unsubscribe_url": "the url", "method": "link"}}

If there's a mailto unsubscribe:
{{"has_unsubscribe": true, "unsubscribe_url": "mailto:...", "method": "mailto"}}

If none found:
{{"has_unsubscribe": false}}"""


@dataclass
class ClassificationResult:
    email_id: str
    category: str
    reason: str
    suggested_actions: list[str]
    priority: int
    is_sensitive: bool
    analyzed_locally: bool
    unsubscribe_url: str | None = None


async def classify_email(msg: EmailMessage) -> ClassificationResult:
    """Classify an email using privacy-first two-pass processing."""
    body_preview = (msg.body_text or msg.snippet)[:2000]

    result = await llm_router.screen_then_analyze(
        content="",  # not used directly, prompts format their own content
        screening_prompt=SCREENING_PROMPT.format(
            sender=msg.sender,
            subject=msg.subject,
            body=body_preview,
        ).replace("{content}", ""),
        analysis_prompt=CLASSIFICATION_PROMPT.format(
            sender=msg.sender,
            subject=msg.subject,
            date=msg.date,
            body=body_preview,
        ).replace("{content}", ""),
    )

    # Parse classification JSON
    try:
        classification = json.loads(result["analysis"].content)
    except (json.JSONDecodeError, KeyError):
        # LLM didn't return clean JSON, extract what we can
        content = result["analysis"].content
        classification = {
            "category": "FYI",
            "reason": content[:200],
            "suggested_actions": ["keep"],
            "priority": 3,
        }

    return ClassificationResult(
        email_id=msg.id,
        category=classification.get("category", "FYI"),
        reason=classification.get("reason", ""),
        suggested_actions=classification.get("suggested_actions", ["keep"]),
        priority=classification.get("priority", 3),
        is_sensitive=result["kept_local"],
        analyzed_locally=result["kept_local"],
        unsubscribe_url=None,
    )


async def batch_classify(messages: list[EmailMessage]) -> list[ClassificationResult]:
    """Classify a batch of emails."""
    results = []
    for msg in messages:
        try:
            result = await classify_email(msg)
            results.append(result)
        except Exception as e:
            log.error(f"Failed to classify {msg.id}: {e}")
            results.append(
                ClassificationResult(
                    email_id=msg.id,
                    category="ERROR",
                    reason=str(e),
                    suggested_actions=["keep"],
                    priority=3,
                    is_sensitive=False,
                    analyzed_locally=True,
                )
            )
    return results
