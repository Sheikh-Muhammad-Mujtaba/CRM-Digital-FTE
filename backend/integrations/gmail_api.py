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
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
)


class GmailAuthError(RuntimeError):
    """Raised when Gmail OAuth credentials are invalid or expired."""


def _header_value_map(headers: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for header in headers:
        name = header.get("name")
        value = header.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out[name.lower()] = value
    return out


def should_ignore_inbound_email(customer_email: str, subject: str, headers: list[dict]) -> bool:
    email_l = customer_email.lower()
    subject_l = (subject or "").lower()
    header_map = _header_value_map(headers)

    service_domains = (
        "facebookmail.com",
        "facebook.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "tiktok.com",
        "youtube.com",
        "google.com",
    )
    if any(email_l.endswith(f"@{domain}") for domain in service_domains):
        return True

    no_reply_markers = ("no-reply@", "noreply@", "donotreply@", "do-not-reply@")
    if any(marker in email_l for marker in no_reply_markers):
        return True

    promotion_markers = (
        "newsletter",
        "promotion",
        "promotional",
        "sale",
        "discount",
        "offer",
        "unsubscribe",
        "digest",
    )
    if any(marker in subject_l for marker in promotion_markers):
        return True

    if "list-unsubscribe" in header_map:
        return True

    precedence = header_map.get("precedence", "").lower()
    if precedence in {"bulk", "list", "junk"}:
        return True

    auto_submitted = header_map.get("auto-submitted", "").lower()
    if auto_submitted and auto_submitted != "no":
        return True

    return False


def _credentials() -> Credentials:
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh = os.getenv("GMAIL_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh]):
        raise RuntimeError("Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN")
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
    try:
        creds.refresh(Request())
    except RefreshError as err:
        msg = str(err)
        if "invalid_grant" in msg:
            raise GmailAuthError(
                "Gmail OAuth refresh token is invalid/expired (invalid_grant). "
                "Re-authorize and update GMAIL_REFRESH_TOKEN."
            ) from err
        raise GmailAuthError(f"Gmail OAuth refresh failed: {msg}") from err
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: list[dict], name: str) -> str | None:
    name_l = name.lower()
    for header in headers:
        if header.get("name", "").lower() == name_l:
            return header.get("value")
    return None


def _decode_body_data(data: str | None) -> str:
    if not data:
        return ""
    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        return raw.decode("utf-8", errors="replace")
    except (binascii.Error, ValueError) as err:
        logger.warning("Body decode failed: %s", err)
        return ""


def extract_plain_text_from_payload(payload: dict) -> str:
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        text = _decode_body_data(payload.get("body", {}).get("data"))
        if text.strip():
            return text.strip()

    parts = payload.get("parts") or []
    for part in parts:
        nested = extract_plain_text_from_payload(part)
        if nested.strip():
            return nested.strip()

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

    for item in messages:
        mid = item["id"]
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

        if should_ignore_inbound_email(customer_email, subject, headers):
            logger.info("Ignoring non-support email and marking as read: from=%s subject=%s", customer_email, subject)
            mark_message_read(service, mid)
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
    service = get_gmail_service()
    msg = MIMEText(body_plain, "plain", "utf-8")
    msg["To"] = to_addr
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def start_inbox_watch(service, topic_name: str, label_ids: list[str] | None = None) -> dict:
    body: dict = {"topicName": topic_name, "labelIds": label_ids or ["INBOX"]}
    return service.users().watch(userId="me", body=body).execute()


def stop_watch(service) -> None:
    service.users().stop(userId="me").execute()
