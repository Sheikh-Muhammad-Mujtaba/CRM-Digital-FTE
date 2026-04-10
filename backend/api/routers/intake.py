import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request

from api.schemas import WebMessagePayload, WebhookResponse
from channels.gmail_handler import (
    build_gmail_event,
    process_gmail_sync_events,
    require_secret,
)
from channels.web_form_handler import build_web_event
from channels.whatsapp_handler import build_whatsapp_event
from settings import get_settings
from workers.kafka import create_producer, publish_event

logger = logging.getLogger(__name__)

router = APIRouter()
_producer = create_producer()


def _publish(event: dict):
    """Publish event to Kafka intake topic."""
    try:
        publish_event(_producer, get_settings().kafka_intake_topic, event)
        logger.info(
            "Published event to Kafka: channel=%s, event_id=%s",
            event.get("channel"),
            event.get("event_id"),
        )
    except Exception as err:
        logger.error("Failed to publish event: %s", err, exc_info=True)
        raise


@router.post("/intake/web", response_model=WebhookResponse)
async def web_intake(payload: WebMessagePayload):
    """Accept web form submission and queue for processing.
    
    Args:
        payload: Customer message from web form
        
    Returns:
        Status confirmation
        
    Raises:
        HTTPException: 500 if Kafka publish fails
    """
    try:
        _publish(build_web_event(payload))
        return WebhookResponse(status="success", message="Message queued for processing")
    except Exception as exc:
        logger.error("Web intake failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue message: {str(exc)}") from exc


@router.post("/intake/twilio", response_model=WebhookResponse)
@router.post("/intake/whatsapp", response_model=WebhookResponse)
async def whatsapp_intake(request: Request):
    """Accept Twilio WhatsApp webhook and queue for processing.
    
    Expected Twilio form fields:
    - From: Customer phone number
    - Body: Message text
    - AccountSid: Twilio account ID
    - MessageSid: Message ID
    
    Returns:
        Status confirmation
        
    Raises:
        HTTPException: 400 if form data invalid, 500 if Kafka publish fails
    """
    try:
        form_data = await request.form()
        form_dict = dict(form_data)
        
        # Validate required Twilio fields
        if not form_dict.get("From"):
            raise ValueError("Missing Twilio 'From' field (customer phone number)")
        if not form_dict.get("Body"):
            logger.warning("WhatsApp message with empty body received")
        
        _publish(build_whatsapp_event(form_dict))
        logger.info("WhatsApp message queued: from=%s", form_dict.get("From"))
        return WebhookResponse(status="success", message="WhatsApp message queued")
    
    except ValueError as exc:
        logger.warning("WhatsApp intake validation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("WhatsApp intake failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue WhatsApp message: {str(exc)}") from exc


@router.post("/intake/gmail", response_model=WebhookResponse)
async def gmail_intake(request: Request):
    """Accept Gmail webhook (direct JSON payload) and queue for processing.
    
    Accepts JSON payload with keys:
    - message: Message body (or nested structure)
    - sender_email: Sender email address
    - customer_email: Alternative sender field
    - customer_name: Sender name (optional)
    
    Returns:
        Status confirmation
        
    Raises:
        HTTPException: 400 if JSON invalid, 500 if Kafka publish fails
    """
    try:
        payload = await request.json()
        try:
            event = build_gmail_event(payload)
        except ValueError:
            logger.info("Ignored non-support Gmail message at intake")
            return WebhookResponse(status="success", message="Ignored non-support message")

        _publish(event)
        logger.info("Gmail message queued: from=%s", payload.get("sender_email", "unknown"))
        return WebhookResponse(status="success", message="Gmail message queued")
    
    except Exception as exc:
        logger.error("Gmail intake failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue Gmail message: {str(exc)}") from exc


@router.post("/webhooks/gmail/pubsub", response_model=WebhookResponse)
async def gmail_pubsub_push(
    request: Request,
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """Accept Google Cloud Pub/Sub push notification for Gmail.
    
    This endpoint is called by Google Cloud Pub/Sub when new Gmail messages arrive.
    It fetches unread messages from the Gmail API and queues them.
    
    Query params:
    - token: Gmail webhook secret for authentication (optional)
    
    Returns:
        Count of messages queued
        
    Raises:
        HTTPException: 403 if token invalid, 503 if Gmail API unavailable, 500 for other errors
    """
    try:
        require_secret(request, token)
        logger.info("Gmail Pub/Sub push received")
        
        try:
            events = await process_gmail_sync_events()
        except RuntimeError as exc:
            logger.error("Gmail API unavailable: %s", exc)
            raise HTTPException(status_code=503, detail=f"Gmail API error: {str(exc)}") from exc
        
        for event in events:
            _publish(event)
        
        logger.info("Gmail Pub/Sub: queued %d message(s)", len(events))
        return WebhookResponse(status="success", message=f"Queued {len(events)} message(s).")
    
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        if "invalid_grant" in detail.lower() or "refresh token" in detail.lower():
            raise HTTPException(
                status_code=401,
                detail=(
                    "Gmail OAuth credentials are invalid/expired. "
                    "Re-authorize Gmail and update GMAIL_REFRESH_TOKEN."
                ),
            ) from exc
        raise HTTPException(status_code=503, detail=f"Pub/Sub processing failed: {detail}") from exc
    except Exception as exc:
        logger.error("Gmail Pub/Sub push failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pub/Sub processing failed: {str(exc)}") from exc


@router.post("/gmail/sync", response_model=WebhookResponse)
async def gmail_sync_poll(
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """Manual trigger to sync unread Gmail messages (polling mode).
    
    Use this endpoint to manually trigger Gmail inbox synchronization.
    Requires GMAIL_WEBHOOK_SECRET if configured.
    
    Query params:
    - token: Gmail webhook secret for authentication (optional)
    
    Returns:
        Count of messages queued
        
    Raises:
        HTTPException: 403 if token invalid, 503 if Gmail API unavailable
    """
    try:
        require_secret(None, token)
        events = await process_gmail_sync_events()
        for event in events:
            _publish(event)
        logger.info("Manual Gmail sync: queued %d message(s)", len(events))
        return WebhookResponse(status="success", message=f"Queued {len(events)} message(s).")
    
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        logger.error("Gmail sync failed: %s", detail)
        if "invalid_grant" in detail.lower() or "refresh token" in detail.lower():
            raise HTTPException(
                status_code=401,
                detail=(
                    "Gmail OAuth credentials are invalid/expired. "
                    "Re-authorize Gmail and update GMAIL_REFRESH_TOKEN."
                ),
            ) from exc
        raise HTTPException(status_code=503, detail=f"Gmail API error: {detail}") from exc
    except Exception as exc:
        logger.error("Gmail sync failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(exc)}") from exc


@router.post("/gmail/watch", response_model=WebhookResponse)
async def gmail_register_watch(
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """Register Gmail inbox for Pub/Sub push notifications.
    
    Requires GMAIL_PUBSUB_TOPIC to be set in environment.
    Once registered, new messages will be pushed to the configured Pub/Sub topic.
    
    Query params:
    - token: Gmail webhook secret for authentication (optional)
    
    Returns:
        Watch registration details including expiration timestamp
        
    Raises:
        HTTPException: 400 if GMAIL_PUBSUB_TOPIC not configured, 500 if registration fails
    """
    try:
        require_secret(None, token)
        topic = get_settings().gmail_pubsub_topic
        if topic is None:
            raise HTTPException(
                status_code=400,
                detail="Set GMAIL_PUBSUB_TOPIC environment variable (format: projects/PROJECT_ID/topics/TOPIC_NAME)",
            )

        from integrations import gmail_api

        logger.info("Registering Gmail watch on topic: %s", topic)
        result = await asyncio.to_thread(
            lambda: gmail_api.start_inbox_watch(gmail_api.get_gmail_service(), topic)
        )
        exp = result.get("expiration")
        logger.info("Gmail watch registered. Expiration: %s", exp)
        return WebhookResponse(status="success", message=f"Watch registered. expiration={exp}")
    
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        if "invalid_grant" in detail.lower() or "refresh token" in detail.lower():
            raise HTTPException(
                status_code=401,
                detail=(
                    "Gmail OAuth credentials are invalid/expired. "
                    "Re-authorize Gmail and update GMAIL_REFRESH_TOKEN."
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=f"Watch registration failed: {detail}") from exc
    except Exception as exc:
        logger.error("Gmail watch registration failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Watch registration failed: {str(exc)}") from exc


@router.post("/gmail/watch/stop", response_model=WebhookResponse)
async def gmail_stop_watch(
    token: str | None = Query(None, description="GMAIL_WEBHOOK_SECRET (optional)"),
):
    """Unregister Gmail inbox from Pub/Sub push notifications.
    
    Stops the active Gmail watch on the inbox.
    
    Query params:
    - token: Gmail webhook secret for authentication (optional)
    
    Returns:
        Confirmation of watch removal
        
    Raises:
        HTTPException: 403 if token invalid, 500 if stop fails
    """
    try:
        require_secret(None, token)
        from integrations import gmail_api

        logger.info("Stopping Gmail watch")
        await asyncio.to_thread(lambda: gmail_api.stop_watch(gmail_api.get_gmail_service()))
        logger.info("Gmail watch stopped")
        return WebhookResponse(status="success", message="Gmail watch stopped")
    
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        if "invalid_grant" in detail.lower() or "refresh token" in detail.lower():
            raise HTTPException(
                status_code=401,
                detail=(
                    "Gmail OAuth credentials are invalid/expired. "
                    "Re-authorize Gmail and update GMAIL_REFRESH_TOKEN."
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=f"Stop watch failed: {detail}") from exc
    except Exception as exc:
        logger.error("Gmail watch stop failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stop watch failed: {str(exc)}") from exc
