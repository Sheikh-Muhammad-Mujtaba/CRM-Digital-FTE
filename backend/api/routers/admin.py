from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from api.deps import require_admin_auth
from api.schemas import TicketReplyPayload
from core.database import AsyncSessionLocal
from database.models.conversation import Conversation
from database.models.customer import Customer
from database.models.message import Message
from database.models.ticket import Ticket
from database.queries.admin import (
    fetch_assigned_tickets,
    fetch_daily_summary,
    fetch_dashboard_activity,
    fetch_dashboard_analytics,
    fetch_dashboard_data,
)
from outbound.dispatch import dispatch_channel_reply

router = APIRouter()


@router.get("/reports/daily-summary", dependencies=[Depends(require_admin_auth)])
async def daily_summary(days: int = 1):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return await fetch_daily_summary(days)


@router.get("/admin/dashboard", dependencies=[Depends(require_admin_auth)])
async def admin_dashboard(hours: int = 24):
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 168")
    return await fetch_dashboard_data(hours=hours)


@router.get("/admin/dashboard/analytics", dependencies=[Depends(require_admin_auth)])
async def admin_dashboard_analytics(hours: int = 24, bucket_hours: int = 1):
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 168")
    if bucket_hours < 1 or bucket_hours > 24:
        raise HTTPException(status_code=400, detail="bucket_hours must be between 1 and 24")
    return await fetch_dashboard_analytics(hours=hours, bucket_hours=bucket_hours)


@router.get("/admin/dashboard/activity", dependencies=[Depends(require_admin_auth)])
async def admin_dashboard_activity(
    hours: int = 24,
    limit: int = 80,
    channel: str | None = None,
    sender_type: str | None = None,
    sentiment: str | None = None,
):
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 168")
    if limit < 10 or limit > 300:
        raise HTTPException(status_code=400, detail="limit must be between 10 and 300")
    if sentiment not in (None, "positive", "neutral", "negative"):
        raise HTTPException(status_code=400, detail="sentiment must be positive, neutral, or negative")

    return await fetch_dashboard_activity(
        hours=hours,
        limit=limit,
        channel=channel,
        sender_type=sender_type,
        sentiment=sentiment,
    )


@router.get("/admin/tickets", dependencies=[Depends(require_admin_auth)])
async def admin_tickets(status: str | None = "open", limit: int = 100):
    if limit < 1 or limit > 300:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 300")
    if status not in (None, "open", "in_progress", "resolved", "escalated"):
        raise HTTPException(status_code=400, detail="invalid ticket status filter")
    return await fetch_assigned_tickets(status=status, limit=limit)


@router.post("/admin/tickets/{ticket_id}/reply", dependencies=[Depends(require_admin_auth)])
async def admin_ticket_reply(ticket_id: str, payload: TicketReplyPayload):
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ticket_id") from exc

    response_text = payload.response_text.strip()
    if not response_text:
        raise HTTPException(status_code=400, detail="response_text is required")

    async with AsyncSessionLocal() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.id == ticket_uuid))
        ).scalar_one_or_none()
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        conversation = None
        customer = None
        channel = "web"

        if ticket.conversation_id is not None:
            conversation = (
                await session.execute(select(Conversation).where(Conversation.id == ticket.conversation_id))
            ).scalar_one_or_none()
            if conversation is not None:
                customer = (
                    await session.execute(select(Customer).where(Customer.id == conversation.customer_id))
                ).scalar_one_or_none()
                first_message = (
                    await session.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if first_message is not None:
                    channel = first_message.channel

        ticket.status = "resolved" if payload.mark_resolved else "in_progress"
        if payload.mark_resolved:
            ticket.resolved_at = ticket.resolved_at or datetime.utcnow()
            if conversation is not None:
                conversation.status = "closed"

        if conversation is not None:
            session.add(
                Message(
                    conversation_id=conversation.id,
                    sender_type="agent",
                    content=response_text,
                    channel=channel,
                )
            )

        await session.commit()

    outbound_result = await dispatch_channel_reply(
        channel=channel,
        customer_email=customer.email if customer else None,
        customer_phone=customer.phone_number if customer else None,
        response_text=response_text,
    )

    return {
        "status": "success",
        "message": "Reply saved and dispatched",
        "outbound_result": outbound_result,
        "ticket_id": str(ticket_uuid),
    }
