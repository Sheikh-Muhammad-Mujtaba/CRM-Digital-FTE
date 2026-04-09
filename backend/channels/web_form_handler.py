import time
import uuid

from api.schemas import WebMessagePayload


def build_web_event(payload: WebMessagePayload) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "channel": "web",
        "message": payload.message,
        "customer_id": payload.customer_id,
        "customer_name": payload.customer_name,
        "customer_email": payload.customer_email,
        "timestamp": time.time(),
    }
