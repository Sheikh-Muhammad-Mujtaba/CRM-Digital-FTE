from datetime import datetime, timedelta

from sqlalchemy import func, select

from core.database import AsyncSessionLocal
from database.models.conversation import Conversation
from database.models.message import Message
from database.models.ticket import Ticket


async def fetch_daily_summary(days: int) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        ticket_n = (
            await session.execute(select(func.count()).select_from(Ticket).where(Ticket.created_at >= since))
        ).scalar_one()
        msg_n = (
            await session.execute(select(func.count()).select_from(Message).where(Message.created_at >= since))
        ).scalar_one()
        esc_n = (
            await session.execute(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.status == "escalated", Conversation.started_at >= since)
            )
        ).scalar_one()

    return {
        "period_days": days,
        "since_utc": since.isoformat(),
        "tickets_created": int(ticket_n),
        "messages_logged": int(msg_n),
        "escalated_conversations": int(esc_n),
    }
