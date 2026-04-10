from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
import uuid

from fastapi import HTTPException, Request

from integrations import gmail_api
from integrations.gmail_api import GmailAuthError
from settings import get_settings

logger = logging.getLogger(__name__)


def _extract_subject_from_text(body: str) -> str:
    first_line = (body or "").splitlines()[0].strip() if body else ""
    if first_line.lower().startswith("subject:"):
        return first_line.split(":", 1)[1].strip()
    return ""


def decode_gmail_pubsub_body(payload: dict) -> tuple[str, str | None]:
    inner = payload
    msg = payload.get("message") or {}
    data_b64 = msg.get("data") if isinstance(msg, dict) else None
    if data_b64:
        try:
            raw = base64.b64decode(data_b64)
            inner = json.loads(raw.decode("utf-8"))
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as err:
            logger.warning("Gmail Pub/Sub payload decode failed: %s", err)

    body = inner.get("snippet") or inner.get("body") or inner.get("textPlain") or ""
    if isinstance(body, dict):
        body = json.dumps(body)
    sender = inner.get("sender_email") or inner.get("from") or payload.get("sender_email")
    return (str(body) if body else "", sender)


def require_secret(request: Request | None, token: str | None) -> None:
    secret = get_settings().gmail_webhook_secret
    if not secret:
        return
    if token == secret:
        return
    if request is not None and request.headers.get("X-Webhook-Token") == secret:
        return
    raise HTTPException(status_code=403, detail="Invalid or missing token")


def build_gmail_event(payload: dict) -> dict:
    """Build a Kafka event from Gmail webhook or direct JSON payload.
    
    Handles both:
    1. Direct Gmail API payloads (with snippet, body, sender_email)
    2. Google Cloud Pub/Sub wrapped payloads (with base64-encoded message)
    
    Args:
        payload: Webhook payload from Gmail integration
        
    Returns:
        Event dict ready for Kafka publishing
    """
    body, sender = decode_gmail_pubsub_body(payload)
    customer_email = sender or payload.get("sender_email") or "unknown@example.com"
    subject = (payload.get("subject") or "").strip() or _extract_subject_from_text(body)

    if customer_email and gmail_api.should_ignore_inbound_email(customer_email, subject, []):
        raise ValueError("Ignored non-support/promotional/service-platform email")
    
    if not body:
        logger.warning("Gmail payload has empty body from %s", customer_email)
    
    event = {
        "event_id": str(uuid.uuid4()),
        "channel": "email",
        "message": body or "(empty body)",
        "customer_email": customer_email,
        "customer_name": payload.get("customer_name", "Email User").strip() or "Email User",
        "timestamp": time.time(),
        "provider_message_id": payload.get("message_id"),
    }
    
    logger.info(
        "Built Gmail event: from=%s, body_len=%d",
        customer_email,
        len(body),
    )
    
    return event


def process_inbound_gmail() -> list[dict]:
    service = gmail_api.get_gmail_service()
    items = gmail_api.fetch_unread_support_messages(service)
    events = []
    for item in items:
        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "channel": "email",
                "message": item["message"],
                "customer_email": item["customer_email"],
                "customer_name": item.get("customer_name"),
                "timestamp": time.time(),
                "gmail_message_id": item["gmail_message_id"],
            }
        )
        try:
            gmail_api.mark_message_read(service, item["gmail_message_id"])
        except Exception as err:
            logger.warning("Could not mark message read %s: %s", item["gmail_message_id"], err)
    return events


async def process_gmail_sync_events() -> list[dict]:
    """Fetch unread Gmail messages and convert to events.
    
    Runs Gmail API calls in thread pool to avoid blocking async event loop.
    
    Returns:
        List of event dicts ready for Kafka
        
    Raises:
        RuntimeError: If Gmail API call fails
    """
    try:
        events = await asyncio.to_thread(process_inbound_gmail)
        logger.info("Gmail sync: processed %d unread message(s)", len(events))
        return events
    except GmailAuthError as err:
        logger.error("Gmail auth failed: %s", err)
        raise RuntimeError(str(err)) from err
    except Exception as err:
        logger.error("Gmail sync failed: %s", err, exc_info=True)
        raise RuntimeError(f"Failed to sync Gmail inbox: {err}") from err
