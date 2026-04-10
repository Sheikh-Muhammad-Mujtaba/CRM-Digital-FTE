from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select

from api.deps import require_admin_auth
from api.schemas import (
    ConversationBulkDeletePayload,
    TicketHandoffPayload,
    TicketReplyPayload,
    TicketStatusUpdatePayload,
)
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
async def admin_tickets(status: str | None = None, limit: int = 100):
    if limit < 1 or limit > 300:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 300")
    if status not in (None, "open", "in_progress", "resolved", "escalated", "closed"):
        raise HTTPException(status_code=400, detail="invalid ticket status filter")
    return await fetch_assigned_tickets(status=status, limit=limit)


@router.patch("/admin/tickets/{ticket_id}/status", dependencies=[Depends(require_admin_auth)])
async def admin_ticket_status_update(ticket_id: str, payload: TicketStatusUpdatePayload):
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ticket_id") from exc

    target_status = payload.status.strip().lower()
    if target_status == "resolved":
        target_status = "closed"

    allowed_statuses = {"open", "in_progress", "escalated", "closed"}
    if target_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="invalid target status")

    async with AsyncSessionLocal() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.id == ticket_uuid))
        ).scalar_one_or_none()
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket.status = target_status
        if target_status == "closed":
            ticket.resolved_at = ticket.resolved_at or datetime.utcnow()
        elif target_status in {"open", "in_progress", "escalated"}:
            ticket.resolved_at = None

        if ticket.conversation_id is not None:
            conversation = (
                await session.execute(select(Conversation).where(Conversation.id == ticket.conversation_id))
            ).scalar_one_or_none()
            if conversation is not None:
                if target_status == "escalated":
                    conversation.status = "escalated"
                elif target_status == "closed":
                    conversation.status = "closed"
                else:
                    conversation.status = "open"

        await session.commit()

    return {
        "status": "success",
        "message": "Ticket status updated",
        "ticket_id": str(ticket_uuid),
        "ticket_status": target_status,
    }


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

        ticket.status = "closed" if payload.mark_resolved else "in_progress"
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


@router.post("/admin/tickets/{ticket_id}/handoff-to-agent", dependencies=[Depends(require_admin_auth)])
async def admin_ticket_handoff_to_agent(ticket_id: str, payload: TicketHandoffPayload):
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ticket_id") from exc

    instruction = payload.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")

    async with AsyncSessionLocal() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.id == ticket_uuid))
        ).scalar_one_or_none()
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if ticket.conversation_id is None:
            raise HTTPException(status_code=400, detail="Ticket has no linked conversation")

        conversation = (
            await session.execute(select(Conversation).where(Conversation.id == ticket.conversation_id))
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.status = "open"
        if ticket.status != "closed":
            ticket.status = "open"

        first_message = (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        channel = first_message.channel if first_message is not None else "web"

        session.add(
            Message(
                conversation_id=conversation.id,
                sender_type="system",
                content=f"HUMAN_TO_AGENT: {instruction}",
                channel=channel,
            )
        )
        await session.commit()

    return {
        "status": "success",
        "message": "Ticket handed back to agent with instruction",
        "ticket_id": str(ticket_uuid),
    }


@router.delete("/admin/history/conversations/{conversation_id}", dependencies=[Depends(require_admin_auth)])
async def admin_delete_conversation_history(conversation_id: str):
    try:
        conversation_uuid = uuid.UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation_id") from exc

    async with AsyncSessionLocal() as session:
        conversation = (
            await session.execute(select(Conversation).where(Conversation.id == conversation_uuid))
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        deleted_messages = await session.execute(
            delete(Message).where(Message.conversation_id == conversation_uuid)
        ) 
        deleted_tickets = await session.execute(
            delete(Ticket).where(Ticket.conversation_id == conversation_uuid)
        )
        deleted_conversations = await session.execute(
            delete(Conversation).where(Conversation.id == conversation_uuid)
        )
        await session.commit()

    return {
        "status": "success",
        "message": "Conversation and linked data deleted",
        "conversation_id": str(conversation_uuid),
        "deleted_messages": int(deleted_messages.rowcount or 0),
        "deleted_tickets": int(deleted_tickets.rowcount or 0),
        "deleted_conversations": int(deleted_conversations.rowcount or 0),
    }


@router.get("/admin/history/conversations", dependencies=[Depends(require_admin_auth)])
async def admin_conversation_logs(
    limit: int = 100,
    channel: str | None = None,
    status: str | None = None,
    query: str | None = None,
):
    if limit < 10 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 10 and 500")

    normalized_channel = (channel or "").strip().lower() or None
    if normalized_channel not in (None, "web", "whatsapp", "email"):
        raise HTTPException(status_code=400, detail="invalid channel filter")

    normalized_status = (status or "").strip().lower() or None
    if normalized_status not in (None, "open", "escalated", "closed"):
        raise HTTPException(status_code=400, detail="invalid status filter")

    normalized_query = (query or "").strip().lower() or None

    async with AsyncSessionLocal() as session:
        stmt = select(Conversation).order_by(Conversation.started_at.desc()).limit(limit)
        if normalized_status:
            stmt = stmt.where(Conversation.status == normalized_status)

        conversations = (await session.execute(stmt)).scalars().all()
        items: list[dict] = []

        for conv in conversations:
            customer = (
                await session.execute(select(Customer).where(Customer.id == conv.customer_id))
            ).scalar_one_or_none()

            latest_message = (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            first_message = (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(Message.created_at.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            message_count = (
                await session.execute(
                    select(Message).where(Message.conversation_id == conv.id)
                )
            ).scalars().all()

            inferred_channel = None
            if latest_message is not None:
                inferred_channel = latest_message.channel
            elif first_message is not None:
                inferred_channel = first_message.channel

            if normalized_channel and inferred_channel != normalized_channel:
                continue

            customer_name = customer.name if customer else None
            customer_email = customer.email if customer else None
            latest_content = latest_message.content if latest_message else None

            if normalized_query:
                haystacks = [
                    str(conv.id).lower(),
                    (customer_name or "").lower(),
                    (customer_email or "").lower(),
                    (latest_content or "").lower(),
                ]
                if not any(normalized_query in value for value in haystacks):
                    continue

            items.append(
                {
                    "conversation_id": str(conv.id),
                    "status": conv.status,
                    "started_at": conv.started_at.isoformat() if conv.started_at else None,
                    "closed_at": conv.closed_at.isoformat() if conv.closed_at else None,
                    "channel": inferred_channel,
                    "message_count": len(message_count),
                    "customer": {
                        "id": str(customer.id) if customer else None,
                        "name": customer_name,
                        "email": customer_email,
                        "phone_number": customer.phone_number if customer else None,
                    },
                    "latest_message": {
                        "content": latest_content,
                        "created_at": latest_message.created_at.isoformat() if latest_message and latest_message.created_at else None,
                        "sender_type": latest_message.sender_type if latest_message else None,
                    },
                }
            )

    return {"count": len(items), "items": items}


@router.post("/admin/history/conversations/bulk-delete", dependencies=[Depends(require_admin_auth)])
async def admin_bulk_delete_conversation_history(payload: ConversationBulkDeletePayload):
    if not payload.conversation_ids:
        raise HTTPException(status_code=400, detail="conversation_ids cannot be empty")

    conversation_uuids: list[uuid.UUID] = []
    for cid in payload.conversation_ids:
        try:
            conversation_uuids.append(uuid.UUID(cid))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid conversation_id: {cid}") from exc

    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(
                select(Conversation.id).where(Conversation.id.in_(conversation_uuids))
            )
        ).all()
        existing_ids = {row[0] for row in existing}

        deleted_messages = await session.execute(
            delete(Message).where(Message.conversation_id.in_(list(existing_ids)))
        )
        deleted_tickets = await session.execute(
            delete(Ticket).where(Ticket.conversation_id.in_(list(existing_ids)))
        )
        deleted_conversations = await session.execute(
            delete(Conversation).where(Conversation.id.in_(list(existing_ids)))
        )
        await session.commit()

    return {
        "status": "success",
        "message": "Conversations and linked data deleted",
        "deleted_conversations": int(deleted_conversations.rowcount or 0),
        "deleted_tickets": int(deleted_tickets.rowcount or 0),
        "deleted_messages": int(deleted_messages.rowcount or 0),
    }
