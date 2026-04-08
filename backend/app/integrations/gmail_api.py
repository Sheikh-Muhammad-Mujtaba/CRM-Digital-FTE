"""
Gmail API using OAuth2 refresh token (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN).
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
import re
from email.mime.text import MIMEText
from email.utils import parseaddr

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# readonly+modify: fetch inbox, mark read. send: outbound replies (hackathon: "Send via Gmail API").
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
)


def _credentials() -> Credentials:
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh = os.getenv("GMAIL_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh]):
        raise RuntimeError(
            "Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN"
        )
    return Credentials(
        token=None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(GMAIL_SCOPES),
    )


def get_gmail_service():
    creds = _credentials()
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: list[dict], name: str) -> str | None:
    name_l = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_l:
            return h.get("value")
    return None


def _decode_body_data(data: str | None) -> str:
    if not data:
        return ""
    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        return raw.decode("utf-8", errors="replace")
    except (binascii.Error, ValueError) as e:
        logger.warning("Body decode failed: %s", e)
        return ""


def extract_plain_text_from_payload(payload: dict) -> str:
    """Recursively walk Gmail message payload for text/plain, then text/html."""
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        t = _decode_body_data(payload.get("body", {}).get("data"))
        if t.strip():
            return t.strip()

    parts = payload.get("parts") or []
    for part in parts:
        sub = extract_plain_text_from_payload(part)
        if sub.strip():
            return sub.strip()

    if mime == "text/html":
        html = _decode_body_data(payload.get("body", {}).get("data"))
        if html.strip():
            return re.sub(r"<[^>]+>", " ", html).strip()
    return ""


def parse_customer_email_from_from_header(from_value: str | None) -> str | None:
    if not from_value:
        return None
    _, addr = parseaddr(from_value)
    return addr.strip() if addr else None


def fetch_unread_support_messages(
    service, *, max_results: int = 10, mailbox_email: str | None = None
) -> list[dict]:
    """
    List recent unread INBOX messages and return dicts ready for Kafka intake.
    Skips messages that appear to be from the same mailbox (outbound copies).
    """
    user_id = "me"
    q = "is:unread in:inbox"
    resp = (
        service.users()
        .messages()
        .list(userId=user_id, q=q, maxResults=max_results)
        .execute()
    )
    messages = resp.get("messages") or []
    out: list[dict] = []

    profile = service.users().getProfile(userId=user_id).execute()
    me_addr = (mailbox_email or profile.get("emailAddress") or "").lower()

    for m in messages:
        mid = m["id"]
        full = (
            service.users()
            .messages()
            .get(userId=user_id, id=mid, format="full")
            .execute()
        )
        headers = full.get("payload", {}).get("headers", [])
        from_h = _header(headers, "From")
        subject = _header(headers, "Subject") or ""
        customer_email = parse_customer_email_from_from_header(from_h)
        if not customer_email:
            continue
        if me_addr and customer_email.lower() == me_addr:
            continue

        snippet = full.get("snippet") or ""
        body = extract_plain_text_from_payload(full.get("payload", {}))
        text = body.strip() if body.strip() else snippet
        if not text:
            continue

        out.append(
            {
                "gmail_message_id": mid,
                "customer_email": customer_email,
                "message": f"Subject: {subject}\n\n{text}" if subject else text,
                "customer_name": None,
            }
        )

    return out


def mark_message_read(service, message_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def send_email_message(to_addr: str, subject: str, body_plain: str) -> None:
    """Send a plain-text email from the authenticated Gmail account (users.messages.send)."""
    service = get_gmail_service()
    msg = MIMEText(body_plain, "plain", "utf-8")
    msg["To"] = to_addr
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def start_inbox_watch(service, topic_name: str, label_ids: list[str] | None = None) -> dict:
    """
    Register Gmail push notifications to a Google Cloud Pub/Sub topic.
    topic_name must be full resource name: projects/PROJECT_ID/topics/TOPIC_NAME
    """
    body: dict = {"topicName": topic_name, "labelIds": label_ids or ["INBOX"]}
    return service.users().watch(userId="me", body=body).execute()


def stop_watch(service) -> None:
    service.users().stop(userId="me").execute()
