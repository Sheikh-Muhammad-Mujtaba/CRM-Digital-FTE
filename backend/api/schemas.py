from typing import Optional

from pydantic import BaseModel


class WebMessagePayload(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    message: str
    channel: str = "web"


class WebhookResponse(BaseModel):
    status: str
    message: str


class TicketReplyPayload(BaseModel):
    response_text: str
    mark_resolved: bool = False


class TicketHandoffPayload(BaseModel):
    instruction: str


class TicketStatusUpdatePayload(BaseModel):
    status: str


class ConversationBulkDeletePayload(BaseModel):
    conversation_ids: list[str]
