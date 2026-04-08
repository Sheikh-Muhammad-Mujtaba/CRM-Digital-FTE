import base64
import binascii
import json
import logging
import time
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.schemas import WebMessagePayload, WebhookResponse
from app.core.database import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.ticket import Ticket
from app.streaming.producer import publish_intake

logger = logging.getLogger(__name__)

router = APIRouter()


def _decode_gmail_pubsub_body(payload: dict) -> tuple[str, str | None]:
    """Extract plain-text body and sender from Gmail push (Pub/Sub) or direct JSON test payloads."""
    inner = payload
    msg = payload.get("message") or {}
    data_b64 = msg.get("data") if isinstance(msg, dict) else None
    if data_b64:
        try:
            raw = base64.b64decode(data_b64)
            inner = json.loads(raw.decode("utf-8"))
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Gmail Pub/Sub payload decode failed: %s", e)

    body = (
        inner.get("snippet")
        or inner.get("body")
        or inner.get("textPlain")
        or ""
    )
    if isinstance(body, dict):
        body = json.dumps(body)
    sender = inner.get("sender_email") or inner.get("from") or payload.get("sender_email")
    return (str(body) if body else "", sender)


@router.post("/intake/web", response_model=WebhookResponse)
async def web_intake(payload: WebMessagePayload):
    try:
        event_data = {
            "event_id": str(uuid.uuid4()),
            "channel": "web",
            "message": payload.message,
            "customer_id": payload.customer_id,
            "customer_name": payload.customer_name,
            "customer_email": payload.customer_email,
            "timestamp": time.time(),
        }
        publish_intake(event_data)
        return WebhookResponse(status="success", message="Message queued for processing")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _twilio_whatsapp_to_kafka(request: Request) -> WebhookResponse:
    form_data = await request.form()
    message_body = form_data.get("Body", "")
    from_number = form_data.get("From", "")

    event_data = {
        "event_id": str(uuid.uuid4()),
        "channel": "whatsapp",
        "message": str(message_body),
        "customer_phone": str(from_number),
        "timestamp": time.time(),
    }
    publish_intake(event_data)
    return WebhookResponse(status="success", message="WhatsApp message queued")


@router.post("/intake/twilio", response_model=WebhookResponse)
async def twilio_webhook(request: Request):
    return await _twilio_whatsapp_to_kafka(request)


@router.post("/intake/whatsapp", response_model=WebhookResponse)
async def whatsapp_intake(request: Request):
    """Twilio WhatsApp webhook (alias per hackathon channel naming)."""
    return await _twilio_whatsapp_to_kafka(request)


@router.post("/intake/gmail", response_model=WebhookResponse)
async def gmail_webhook(request: Request):
    payload = await request.json()
    body, sender = _decode_gmail_pubsub_body(payload)
    customer_email = sender or payload.get("sender_email") or "unknown@example.com"

    event_data = {
        "event_id": str(uuid.uuid4()),
        "channel": "email",
        "message": body or "(empty body)",
        "customer_email": customer_email,
        "timestamp": time.time(),
    }
    publish_intake(event_data)
    return WebhookResponse(status="success", message="Gmail message queued")


@router.get("/reports/daily-summary")
async def daily_summary(days: int = 1):
    """Operational snapshot for Customer Success (tickets, volume, escalations)."""
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        ticket_n = (
            await session.execute(
                select(func.count()).select_from(Ticket).where(Ticket.created_at >= since)
            )
        ).scalar_one()
        msg_n = (
            await session.execute(
                select(func.count()).select_from(Message).where(Message.created_at >= since)
            )
        ).scalar_one()
        esc_n = (
            await session.execute(
                select(func.count())
                .select_from(Conversation)
                .where(
                    Conversation.status == "escalated",
                    Conversation.started_at >= since,
                )
            )
        ).scalar_one()
    return {
        "period_days": days,
        "since_utc": since.isoformat(),
        "tickets_created": int(ticket_n),
        "messages_logged": int(msg_n),
        "escalated_conversations": int(esc_n),
    }
