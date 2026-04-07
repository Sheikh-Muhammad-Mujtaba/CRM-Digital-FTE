from fastapi import APIRouter, HTTPException, Request
from app.api.schemas import WebMessagePayload, WebhookResponse
from app.streaming.producer import publish_event
import uuid
import time

router = APIRouter()

@router.post("/intake/web", response_model=WebhookResponse)
async def web_intake(payload: WebMessagePayload):
    try:
        # Standardize message
        event_data = {
            "event_id": str(uuid.uuid4()),
            "channel": "web",
            "message": payload.message,
            "customer_id": payload.customer_id,
            "customer_name": payload.customer_name,
            "customer_email": payload.customer_email,
            "timestamp": time.time()
        }
        
        # Publish to Kafka
        publish_event("crm_intake", event_data)
        
        return WebhookResponse(status="success", message="Message queued for processing")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intake/twilio", response_model=WebhookResponse)
async def twilio_webhook(request: Request):
    form_data = await request.form()
    message_body = form_data.get("Body", "")
    from_number = form_data.get("From", "")

    event_data = {
        "event_id": str(uuid.uuid4()),
        "channel": "whatsapp",
        "message": message_body,
        "customer_phone": from_number,
        "timestamp": time.time()
    }
    publish_event("crm_intake", event_data)
    return WebhookResponse(status="success", message="WhatsApp message queued")

@router.post("/intake/gmail", response_model=WebhookResponse)
async def gmail_webhook(request: Request):
    payload = await request.json()
    message_body = payload.get("message", {"data": ""})
    customer_email = payload.get("sender_email", "unknown@gmail.com")

    event_data = {
        "event_id": str(uuid.uuid4()),
        "channel": "email",
        "message": message_body,
        "customer_email": customer_email,
        "timestamp": time.time()
    }
    publish_event("crm_intake", event_data)
    return WebhookResponse(status="success", message="Gmail message queued")
