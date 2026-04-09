import logging
import time
import uuid

logger = logging.getLogger(__name__)


def build_whatsapp_event(form_data: dict) -> dict:
    """Build a Kafka event from Twilio WhatsApp webhook payload.
    
    Expected form_data keys (sent by Twilio):
    - From: Twilio phone number (e.g., 'whatsapp:+1234567890')
    - Body: Message text content
    - AccountSid: Twilio account ID
    - MessageSid: Unique message identifier
    - Name: Customer name (optional)
    
    Args:
        form_data: Form data from Twilio webhook
        
    Returns:
        Event dict ready for Kafka publishing
        
    Raises:
        ValueError: If required fields are missing
    """
    message_body = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "").strip()
    message_sid = form_data.get("MessageSid", "").strip()
    account_sid = form_data.get("AccountSid", "").strip()
    
    # Validate required fields
    if not from_number:
        logger.error("WhatsApp webhook missing 'From' field")
        raise ValueError("WhatsApp webhook: missing 'From' (sender phone number)")
    
    if not message_body:
        logger.warning("WhatsApp message from %s has empty body", from_number)
    
    if not message_sid:
        logger.warning("WhatsApp message from %s missing MessageSid", from_number)
    
    event = {
        "event_id": str(uuid.uuid4()),
        "channel": "whatsapp",
        "message": message_body or "(empty message)",
        "customer_phone": from_number,
        "customer_name": form_data.get("Name", "WhatsApp User").strip() or "WhatsApp User",
        "timestamp": time.time(),
        "provider_message_id": message_sid or None,
        "provider_account_id": account_sid or None,
    }
    
    logger.info(
        "Built WhatsApp event: from=%s, message_id=%s, body_len=%d",
        from_number,
        message_sid,
        len(message_body),
    )
    
    return event
