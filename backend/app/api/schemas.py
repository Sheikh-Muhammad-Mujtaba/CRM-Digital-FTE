from pydantic import BaseModel
from typing import Optional
import uuid

class WebMessagePayload(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    message: str
    channel: str = "web"

class WebhookResponse(BaseModel):
    status: str
    message: str
