from __future__ import annotations

from typing import Any

from sqlalchemy import select

from core.database import AsyncSessionLocal
from database.models.conversation import Conversation
from database.models.customer import Customer
from database.models.message import Message
from database.models.ticket import Ticket


async def fetch_assigned_tickets(status: str | None = "open", limit: int = 100) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Ticket.status == status)

        tickets = (await session.execute(stmt)).scalars().all()
        items: list[dict[str, Any]] = []

        for ticket in tickets:
            conversation = None
            customer = None
            if ticket.conversation_id is not None:
                conversation = (
                    await session.execute(select(Conversation).where(Conversation.id == ticket.conversation_id))
                ).scalar_one_or_none()
                if conversation is not None:
                    customer = (
                        await session.execute(select(Customer).where(Customer.id == conversation.customer_id))
                    ).scalar_one_or_none()

            latest_message = None
            first_message = None
            if conversation is not None:
                latest_message = (
                    await session.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                first_message = (
                    await session.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

            items.append(
                {
                    "id": str(ticket.id),
                    "title": ticket.title,
                    "description": ticket.description,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                    "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                    "conversation": {
                        "id": str(conversation.id) if conversation else None,
                        "status": conversation.status if conversation else None,
                        "channel": first_message.channel if first_message else None,
                    },
                    "customer": {
                        "id": str(customer.id) if customer else None,
                        "name": customer.name if customer else None,
                        "email": customer.email if customer else None,
                        "phone_number": customer.phone_number if customer else None,
                    },
                    "latest_message": {
                        "content": latest_message.content if latest_message else None,
                        "sender_type": latest_message.sender_type if latest_message else None,
                        "created_at": latest_message.created_at.isoformat() if latest_message and latest_message.created_at else None,
                    },
                }
            )

    return {"count": len(items), "items": items}