import base64
import logging
from dataclasses import dataclass, field

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    to: str = ""
    date: str = ""
    snippet: str = ""
    body_text: str = ""
    body_html: str = ""
    labels: list[str] = field(default_factory=list)
    has_attachments: bool = False


class GmailClient:
    """Gmail API client with safe, non-destructive defaults."""

    def __init__(self, credentials: Credentials):
        self.service = build("gmail", "v1", credentials=credentials)

    @classmethod
    def from_refresh_token(cls, refresh_token: str) -> "GmailClient":
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return cls(creds)

    @classmethod
    def auth_flow(cls) -> "GmailClient":
        """Run OAuth2 flow for initial setup (interactive)."""
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
        )
        creds = flow.run_local_server(port=0)
        return cls(creds), creds.refresh_token

    # --- Read operations (safe) ---

    def fetch_messages(
        self,
        query: str = "",
        max_results: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[EmailMessage], str | None]:
        """Fetch a batch of emails. Returns (messages, next_page_token)."""
        result = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
                pageToken=page_token,
            )
            .execute()
        )

        messages = []
        for msg_stub in result.get("messages", []):
            msg = self._get_message(msg_stub["id"])
            if msg:
                messages.append(msg)

        return messages, result.get("nextPageToken")

    def _get_message(self, msg_id: str) -> EmailMessage | None:
        try:
            raw = (
                self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            )
        except Exception as e:
            log.warning(f"Failed to fetch message {msg_id}: {e}")
            return None

        headers = {h["name"].lower(): h["value"] for h in raw.get("payload", {}).get("headers", [])}
        body_text, body_html = self._extract_body(raw.get("payload", {}))

        return EmailMessage(
            id=raw["id"],
            thread_id=raw["threadId"],
            subject=headers.get("subject", ""),
            sender=headers.get("from", ""),
            to=headers.get("to", ""),
            date=headers.get("date", ""),
            snippet=raw.get("snippet", ""),
            body_text=body_text,
            body_html=body_html,
            labels=raw.get("labelIds", []),
            has_attachments=self._has_attachments(raw.get("payload", {})),
        )

    def _extract_body(self, payload: dict) -> tuple[str, str]:
        text, html = "", ""
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            text = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="replace"
            )
        elif payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
            html = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="replace"
            )

        for part in payload.get("parts", []):
            t, h = self._extract_body(part)
            if t:
                text = t
            if h:
                html = h
        return text, html

    def _has_attachments(self, payload: dict) -> bool:
        if payload.get("filename"):
            return True
        return any(self._has_attachments(p) for p in payload.get("parts", []))

    # --- Write operations (require approval) ---

    def add_label(self, msg_id: str, label_id: str):
        self.service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [label_id]}
        ).execute()

    def remove_label(self, msg_id: str, label_id: str):
        self.service.users().messages().modify(
            userId="me", id=msg_id, body={"removeLabelIds": [label_id]}
        ).execute()

    def archive(self, msg_id: str):
        """Remove from inbox (non-destructive)."""
        self.remove_label(msg_id, "INBOX")

    def trash(self, msg_id: str):
        """Move to trash (recoverable for 30 days)."""
        self.service.users().messages().trash(userId="me", id=msg_id).execute()

    def mark_read(self, msg_id: str):
        self.remove_label(msg_id, "UNREAD")

    def create_draft(self, to: str, subject: str, body: str, thread_id: str | None = None):
        """Create a draft reply (never sends automatically)."""
        import email.mime.text

        msg = email.mime.text.MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        draft_body = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        return self.service.users().drafts().create(userId="me", body=draft_body).execute()

    def get_or_create_label(self, label_name: str) -> str:
        """Get label ID by name, creating if it doesn't exist."""
        results = self.service.users().labels().list(userId="me").execute()
        for label in results.get("labels", []):
            if label["name"] == label_name:
                return label["id"]

        created = (
            self.service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return created["id"]
