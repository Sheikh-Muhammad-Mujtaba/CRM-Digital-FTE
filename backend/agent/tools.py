import json
import logging
import os
import uuid
from datetime import datetime
from typing import Literal

from agents import function_tool
from pydantic import BaseModel, Field
from sqlalchemy import select

from database.models.conversation import Conversation
from database.models.knowledge import KnowledgeBase
from database.models.message import Message
from database.models.ticket import Ticket
from outbound.dispatch import dispatch_channel_reply

logger = logging.getLogger(__name__)

_EMBEDDING_CACHE_MAX = 256
_embedding_cache: dict[str, list[float]] = {}


def _cached_embedding_key(query: str) -> str:
    return " ".join(query.lower().split())


def _put_embedding_in_cache(key: str, vector: list[float]) -> None:
    if key in _embedding_cache:
        _embedding_cache.pop(key)
    _embedding_cache[key] = vector
    if len(_embedding_cache) > _EMBEDDING_CACHE_MAX:
        oldest = next(iter(_embedding_cache))
        _embedding_cache.pop(oldest, None)


def _get_embedding_from_cache(key: str) -> list[float] | None:
    vector = _embedding_cache.get(key)
    if vector is None:
        return None
    # Touch key for basic LRU behavior.
    _embedding_cache.pop(key)
    _embedding_cache[key] = vector
    return vector


def build_tracking_number(ticket_id: uuid.UUID, channel: str) -> str:
    prefix_map = {
        "web": "WEB",
        "whatsapp": "WHA",
        "email": "EML",
    }
    prefix = prefix_map.get((channel or "").lower(), "SRV")
    compact = str(ticket_id).replace("-", "").upper()
    return f"{prefix}-{compact[:4]}-{compact[4:8]}"


class SearchQueryArgs(BaseModel):
    query: str = Field(description="The user's direct support inquiry or question")


class CreateTicketArgs(BaseModel):
    title: str = Field(description="A short one-line summary of the issue")
    description: str = Field(description="Detailed description and context")
    priority: str = Field(default="medium", description="Priority: low, medium, or high")


class EscalateArgs(BaseModel):
    reason: str = Field(description="Why human intervention is required")


class ResponseArgs(BaseModel):
    response_text: str = Field(description="Final message to send to the customer")
    solved: bool = Field(
        default=False,
        description="Set true only if the customer issue is resolved in this response.",
    )
    final_sentiment: Literal["positive", "neutral", "negative"] = Field(
        default="neutral",
        description="Final customer outcome sentiment for reporting: positive, neutral, or negative.",
    )


@function_tool
async def search_knowledge_base(ctx, params: SearchQueryArgs) -> str:
    try:
        logger.info("tool=search_knowledge_base customer_id=%s", ctx.context.customer_id)
        from google import genai

        query_key = _cached_embedding_key(params.query)
        query_vector = _get_embedding_from_cache(query_key)

        if query_vector is None:
            genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            emb_res = genai_client.models.embed_content(
                model="text-embedding-004",
                contents=params.query,
            )
            query_vector = emb_res.embeddings[0].values
            _put_embedding_in_cache(query_key, query_vector)
            logger.info("tool=search_knowledge_base embedding_cache=miss")
        else:
            logger.info("tool=search_knowledge_base embedding_cache=hit")

        stmt = (
            select(KnowledgeBase.title, KnowledgeBase.content)
            .order_by(KnowledgeBase.embedding.cosine_distance(query_vector))
            .limit(5)
        )
        result = await ctx.context.session.execute(stmt)
        articles = result.all()
        if not articles:
            logger.info("tool=search_knowledge_base result=empty")
            return "No specific articles found matching the query."
        logger.info("tool=search_knowledge_base result_count=%s", len(articles))
        return "\n\n".join([f"Title: {row.title}\nContent: {row.content}" for row in articles])
    except Exception as exc:
        logger.exception("tool=search_knowledge_base failed")
        return f"Knowledge search failed ({exc!s}). Answer conservatively and offer escalation if unsure."


@function_tool
async def get_customer_history(ctx) -> str:
    try:
        customer_uuid = uuid.UUID(ctx.context.customer_id)

        ticket_stmt = (
            select(Ticket)
            .where(Ticket.customer_id == customer_uuid)
            .order_by(Ticket.created_at.desc())
            .limit(20)
        )
        ticket_result = await ctx.context.session.execute(ticket_stmt)
        tickets = ticket_result.scalars().all()

        conversation_ids_stmt = select(Conversation.id).where(Conversation.customer_id == customer_uuid)
        conversation_ids_result = await ctx.context.session.execute(conversation_ids_stmt)
        conversation_ids = [row[0] for row in conversation_ids_result.all()]

        messages = []
        if conversation_ids:
            message_stmt = (
                select(Message)
                .where(Message.conversation_id.in_(conversation_ids))
                .order_by(Message.created_at.desc())
                .limit(50)
            )
            message_result = await ctx.context.session.execute(message_stmt)
            messages = message_result.scalars().all()

        payload = {
            "tickets": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "conversation_id": str(t.conversation_id) if t.conversation_id else None,
                }
                for t in tickets
            ],
            "conversation_count": len(conversation_ids),
            "recent_messages": [
                {
                    "id": str(m.id),
                    "conversation_id": str(m.conversation_id),
                    "sender_type": m.sender_type,
                    "channel": m.channel,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
        logger.info(
            "tool=get_customer_history customer_id=%s ticket_count=%s conversation_count=%s message_count=%s",
            ctx.context.customer_id,
            len(tickets),
            len(conversation_ids),
            len(messages),
        )
        return json.dumps(payload)
    except Exception as exc:
        logger.exception("tool=get_customer_history failed")
        return f"Customer history lookup failed ({exc!s}). Continue with best effort."


@function_tool
async def create_ticket(ctx, params: CreateTicketArgs) -> str:
    try:
        logger.info("tool=create_ticket customer_id=%s conversation_id=%s", ctx.context.customer_id, ctx.context.conversation_id)
        existing_stmt = select(Ticket).where(
            Ticket.customer_id == uuid.UUID(ctx.context.customer_id),
            Ticket.status.in_(["open", "in_progress", "escalated"]),
        )
        existing_result = await ctx.context.session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            if existing.conversation_id is None:
                existing.conversation_id = uuid.UUID(ctx.context.conversation_id)
                await ctx.context.session.commit()
            tracking = build_tracking_number(existing.id, ctx.context.channel)
            logger.info("tool=create_ticket existing_ticket_id=%s tracking=%s", existing.id, tracking)
            return f"Ticket already exists. Tracking ID: {tracking}"

        new_ticket = Ticket(
            customer_id=uuid.UUID(ctx.context.customer_id),
            conversation_id=uuid.UUID(ctx.context.conversation_id),
            title=params.title,
            description=params.description,
            priority=params.priority,
            status="open",
        )
        ctx.context.session.add(new_ticket)
        await ctx.context.session.commit()
        tracking = build_tracking_number(new_ticket.id, ctx.context.channel)
        logger.info("tool=create_ticket created_ticket_id=%s tracking=%s", new_ticket.id, tracking)
        return f"Ticket created. Tracking ID: {tracking}"
    except Exception as exc:
        logger.exception("tool=create_ticket failed")
        return f"Ticket creation failed ({exc!s})."


@function_tool
async def escalate_to_human(ctx, params: EscalateArgs) -> str:
    try:
        conv_id = uuid.UUID(ctx.context.conversation_id)
        stmt = select(Conversation).where(Conversation.id == conv_id)
        res = await ctx.context.session.execute(stmt)
        conv = res.scalar_one_or_none()
        if conv:
            conv.status = "escalated"

        ticket_stmt = select(Ticket).where(
            Ticket.customer_id == uuid.UUID(ctx.context.customer_id),
            Ticket.conversation_id == conv_id,
        )
        ticket_result = await ctx.context.session.execute(ticket_stmt)
        ticket = ticket_result.scalar_one_or_none()
        if ticket is not None:
            ticket.status = "escalated"

        ctx.context.session.add(
            Message(
                conversation_id=conv_id,
                sender_type="system",
                content=f"ESCALATED: {params.reason}",
                channel=ctx.context.channel,
            )
        )
        await ctx.context.session.commit()
        logger.info("tool=escalate_to_human conversation_id=%s reason=%s", ctx.context.conversation_id, params.reason)
        return f"Escalation recorded: {params.reason}"
    except Exception as exc:
        logger.exception("tool=escalate_to_human failed")
        return f"Escalation failed ({exc!s})."


@function_tool
async def send_response(ctx, params: ResponseArgs) -> str:
    try:
        ticket_stmt = select(Ticket).where(
            Ticket.customer_id == uuid.UUID(ctx.context.customer_id),
            Ticket.conversation_id == uuid.UUID(ctx.context.conversation_id),
        )
        ticket_result = await ctx.context.session.execute(ticket_stmt)
        ticket = ticket_result.scalar_one_or_none()

        response_text = params.response_text.strip()
        if ticket is not None and "Ticket Tracking Number:" not in response_text:
            tracking = build_tracking_number(ticket.id, ctx.context.channel)
            response_text = f"{response_text}\n\nTicket Tracking Number: {tracking}"

        conversation_id = uuid.UUID(ctx.context.conversation_id)

        if params.solved and ticket is not None:
            ticket.status = "closed"
            ticket.resolved_at = ticket.resolved_at or datetime.utcnow()
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = await ctx.context.session.execute(conv_stmt)
            conv = conv_result.scalar_one_or_none()
            if conv is not None:
                conv.status = "closed"

        # Persist a final sentiment marker for downstream reporting/auditing.
        ctx.context.session.add(
            Message(
                conversation_id=conversation_id,
                sender_type="system",
                content=f"FINAL_SENTIMENT: {params.final_sentiment}",
                channel=ctx.context.channel,
            )
        )

        ctx.context.session.add(
            Message(
                conversation_id=conversation_id,
                sender_type="agent",
                content=response_text,
                channel=ctx.context.channel,
            )
        )
        await ctx.context.session.commit()

        outbound = await dispatch_channel_reply(
            channel=ctx.context.channel,
            customer_email=ctx.context.customer_email,
            customer_phone=ctx.context.customer_phone,
            response_text=response_text,
        )
        logger.info(
            "tool=send_response conversation_id=%s solved=%s final_sentiment=%s outbound=%s",
            ctx.context.conversation_id,
            params.solved,
            params.final_sentiment,
            outbound,
        )
        return f"Response saved. Outbound: {outbound}"
    except Exception as exc:
        logger.exception("tool=send_response failed")
        return f"Response send failed ({exc!s})."
