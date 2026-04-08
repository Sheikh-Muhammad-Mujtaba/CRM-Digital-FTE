"""
Gmail + Google Pub/Sub push webhook with minimal env vars.

Required:
- GMAIL_CLIENT_ID
- GMAIL_CLIENT_SECRET
- GMAIL_REFRESH_TOKEN
- GMAIL_PUBSUB_TOPIC  (full name: projects/PROJECT_ID/topics/TOPIC_NAME) for users.watch

Optional (recommended):
- GMAIL_WEBHOOK_SECRET: protects BOTH the webhook + the watch/sync endpoints
- GMAIL_MARK_READ=true|false: mark processed messages read (default true)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.schemas import WebhookResponse
from app.integrations import gmail_api
from app.streaming.producer import publish_intake

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gmail"])


def _require_secret(request: Request | None, token: str | None) -> None:
    """
    Single optional secret for admin + webhook.
    If GMAIL_WEBHOOK_SECRET is not set, endpoints are open (OK only for private networks).
    """
    secret = os.getenv("GMAIL_WEBHOOK_SECRET")
    if not secret:
        return
    if token == secret:
        return
    if request is not None and request.headers.get("X-Webhook-Token") == secret:
        return
    raise HTTPException(status_code=403, detail="Invalid or missing token")


def _process_inbound_gmail() -> int:
    service = gmail_api.get_gmail_service()
    items = gmail_api.fetch_unread_support_messages(service)
    mark_read = os.getenv("GMAIL_MARK_READ", "true").lower() in ("1", "true", "yes")
    count = 0
    for item in items:
        event_data = {
            "event_id": str(uuid.uuid4()),
            "channel": "email",
            "message": item["message"],
            "customer_email": item["customer_email"],
            "customer_name": item.get("customer_name"),
            "timestamp": time.time(),
            "gmail_message_id": item["gmail_message_id"],
        }
        publish_intake(event_data)
        if mark_read:
            try:
                gmail_api.mark_message_read(service, item["gmail_message_id"])
            except Exception as exc:
                logger.warning(
                    "Could not mark message read %s: %s",
                    item["gmail_message_id"],
                    exc,
                )
        count += 1
    return count


@router.post("/webhooks/gmail/pubsub", response_model=WebhookResponse)
async def gmail_pubsub_push(
    request: Request,
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """
    Pub/Sub push endpoint.
    We treat the Pub/Sub event as a signal and then pull unread inbox mail via Gmail API.
    """
    _require_secret(request, token)

    # Log a subset of the Pub/Sub signal (optional)
    try:
        body = await request.json()
    except Exception:
        body = {}
    msg = body.get("message") or {}
    raw_b64 = msg.get("data")
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            inner = json.loads(decoded)
            logger.info("Gmail Pub/Sub signal: %s", inner)
        except Exception:
            pass

    try:
        n = await asyncio.to_thread(_process_inbound_gmail)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Gmail fetch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return WebhookResponse(status="success", message=f"Queued {n} message(s).")


@router.post("/gmail/sync", response_model=WebhookResponse)
async def gmail_sync_poll(
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """Manual poll endpoint (same logic as Pub/Sub handler)."""
    _require_secret(None, token)
    try:
        n = await asyncio.to_thread(_process_inbound_gmail)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Gmail fetch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return WebhookResponse(status="success", message=f"Queued {n} message(s).")


@router.post("/gmail/watch", response_model=WebhookResponse)
async def gmail_register_watch(
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """Register/renew Gmail push notifications to your Pub/Sub topic."""
    _require_secret(None, token)
    topic = os.getenv("GMAIL_PUBSUB_TOPIC")
    if not topic:
        raise HTTPException(
            status_code=400,
            detail="Set GMAIL_PUBSUB_TOPIC to projects/PROJECT_ID/topics/TOPIC_NAME",
        )

    def _watch():
        service = gmail_api.get_gmail_service()
        return gmail_api.start_inbox_watch(service, topic)

    try:
        result = await asyncio.to_thread(_watch)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("users.watch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    exp = result.get("expiration")
    return WebhookResponse(status="success", message=f"Watch registered. expiration={exp}")


@router.post("/gmail/watch/stop", response_model=WebhookResponse)
async def gmail_stop_watch(
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    _require_secret(None, token)

    def _stop():
        service = gmail_api.get_gmail_service()
        gmail_api.stop_watch(service)

    await asyncio.to_thread(_stop)
    return WebhookResponse(status="success", message="Gmail watch stopped.")
