from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text

from core.database import AsyncSessionLocal
from database.models.conversation import Conversation
from database.models.message import Message
from database.models.ticket import Ticket
from database.queries.sentiment import (
    is_inbound_sender,
    parse_final_sentiment_marker,
    score_sentiment,
    sentiment_label_to_score,
)


def _normalize_hours(hours: int) -> int:
    return max(1, hours)


def _bounded_limit(limit: int, minimum: int = 10, maximum: int = 300) -> int:
    return min(max(limit, minimum), maximum)


async def fetch_dashboard_data(hours: int = 24) -> dict[str, Any]:
    hours = _normalize_hours(hours)
    since = datetime.utcnow() - timedelta(hours=hours)

    async with AsyncSessionLocal() as session:
        total_tickets = (await session.execute(select(func.count()).select_from(Ticket))).scalar_one()
        open_tickets = (
            await session.execute(select(func.count()).select_from(Ticket).where(Ticket.status != "closed"))
        ).scalar_one()
        total_messages = (await session.execute(select(func.count()).select_from(Message))).scalar_one()
        escalated_conversations = (
            await session.execute(
                select(func.count()).select_from(Conversation).where(Conversation.status == "escalated")
            )
        ).scalar_one()
        messages_window = (
            await session.execute(select(func.count()).select_from(Message).where(Message.created_at >= since))
        ).scalar_one()
        tickets_window = (
            await session.execute(select(func.count()).select_from(Ticket).where(Ticket.created_at >= since))
        ).scalar_one()
        escalations_window = (
            await session.execute(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.status == "escalated", Conversation.started_at >= since)
            )
        ).scalar_one()

        recent_tickets = (
            await session.execute(select(Ticket).order_by(Ticket.created_at.desc()).limit(10))
        ).scalars().all()

        channel_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        channel,
                        COUNT(*) FILTER (WHERE sender_type IN ('customer', 'user', 'human')) AS inbound,
                        COUNT(*) FILTER (WHERE sender_type NOT IN ('customer', 'user', 'human')) AS outbound,
                        COUNT(*) AS total
                    FROM messages
                    WHERE created_at >= :since
                    GROUP BY channel
                    ORDER BY total DESC
                    """
                ),
                {"since": since},
            )
        ).mappings().all()

        log_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        created_at AS timestamp,
                        'info' AS level,
                        'message' AS source,
                        CASE
                            WHEN sender_type IN ('customer', 'user', 'human')
                                THEN 'Inbound message received'
                            ELSE 'Outbound message sent'
                        END AS message,
                        channel,
                        sender_type,
                        conversation_id::text AS conversation_id,
                        id::text AS event_id
                    FROM messages
                    UNION ALL
                    SELECT
                        created_at AS timestamp,
                        CASE
                            WHEN status = 'open' THEN 'warn'
                            WHEN status = 'closed' THEN 'info'
                            ELSE 'info'
                        END AS level,
                        'ticket' AS source,
                        CASE
                            WHEN status = 'open' THEN 'Ticket opened'
                            WHEN status = 'closed' THEN 'Ticket closed'
                            ELSE 'Ticket updated'
                        END AS message,
                        NULL::text AS channel,
                        NULL::text AS sender_type,
                        conversation_id::text AS conversation_id,
                        id::text AS event_id
                    FROM tickets
                    ORDER BY timestamp DESC
                    LIMIT 60
                    """
                )
            )
        ).mappings().all()

        sentiment_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        created_at,
                        content,
                        channel,
                        sender_type,
                        conversation_id::text AS conversation_id
                    FROM messages
                    WHERE created_at >= :since
                      AND sender_type IN ('customer', 'user', 'human')
                    ORDER BY created_at DESC
                    LIMIT 500
                    """
                ),
                {"since": since},
            )
        ).mappings().all()

        final_sentiment_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        conversation_id::text AS conversation_id,
                        content,
                        created_at
                    FROM messages
                    WHERE created_at >= :since
                      AND sender_type = 'system'
                      AND content ILIKE 'FINAL_SENTIMENT:%'
                    ORDER BY created_at DESC
                    LIMIT 1000
                    """
                ),
                {"since": since},
            )
        ).mappings().all()

    escalation_rate = 0.0
    if int(total_tickets) > 0:
        escalation_rate = round((int(escalated_conversations) / int(total_tickets)) * 100, 2)

    channels = []
    for row in channel_rows:
        inbound = int(row["inbound"] or 0)
        outbound = int(row["outbound"] or 0)
        total = int(row["total"] or 0)
        status = "healthy"
        if total == 0:
            status = "down"
        elif inbound > 0 and outbound == 0:
            status = "degraded"

        channels.append(
            {
                "channel": str(row["channel"]),
                "inbound": inbound,
                "outbound": outbound,
                "total": total,
                "status": status,
            }
        )

    recent_status_logs = [
        {
            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
            "level": row["level"],
            "source": row["source"],
            "message": row["message"],
            "metadata": {
                "channel": row["channel"],
                "sender_type": row["sender_type"],
                "conversation_id": row["conversation_id"],
                "event_id": row["event_id"],
            },
        }
        for row in log_rows
    ]

    scored_messages = []
    for row in sentiment_rows:
        label, score = score_sentiment(row["content"])
        scored_messages.append(
            {
                "label": label,
                "score": score,
                "content": row["content"],
                "channel": row["channel"],
                "conversation_id": row["conversation_id"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )

    # Prefer explicit FINAL_SENTIMENT markers (one latest marker per conversation) for accuracy.
    final_outcomes_by_conversation: dict[str, dict[str, Any]] = {}
    for row in final_sentiment_rows:
        conversation_id = str(row["conversation_id"])
        if conversation_id in final_outcomes_by_conversation:
            continue
        parsed = parse_final_sentiment_marker(row["content"])
        if parsed is None:
            continue
        final_outcomes_by_conversation[conversation_id] = {
            "label": parsed,
            "score": sentiment_label_to_score(parsed),
            "content": row["content"],
            "channel": "final_outcome",
            "conversation_id": conversation_id,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    sentiment_items = (
        list(final_outcomes_by_conversation.values())
        if final_outcomes_by_conversation
        else scored_messages
    )

    sentiment_total = len(sentiment_items)
    sentiment_positive = sum(1 for item in sentiment_items if item["label"] == "positive")
    sentiment_negative = sum(1 for item in sentiment_items if item["label"] == "negative")
    sentiment_neutral = sentiment_total - sentiment_positive - sentiment_negative
    avg_sentiment_score = (
        round(sum(item["score"] for item in sentiment_items) / sentiment_total, 4)
        if sentiment_total > 0
        else 0.0
    )
    negative_examples = [item for item in sentiment_items if item["label"] == "negative"][:8]

    return {
        "period_hours": int(hours),
        "generated_at": datetime.utcnow().isoformat(),
        "kpis": {
            "tickets_total": int(total_tickets),
            "tickets_open": int(open_tickets),
            "messages_total": int(total_messages),
            "conversations_escalated": int(escalated_conversations),
            "tickets_24h": int(tickets_window),
            "messages_24h": int(messages_window),
            "escalations_24h": int(escalations_window),
            "escalation_rate": escalation_rate,
        },
        "sentiments": {
            "avg_score": avg_sentiment_score,
            "total": sentiment_total,
            "positive": sentiment_positive,
            "neutral": sentiment_neutral,
            "negative": sentiment_negative,
            "source": "final_outcome" if final_outcomes_by_conversation else "heuristic_customer_message",
            "recent_negative_examples": negative_examples,
        },
        "channels": channels,
        "recent_status_logs": recent_status_logs,
        "recent_tickets": [
            {
                "id": str(t.id),
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent_tickets
        ],
    }


async def fetch_dashboard_analytics(hours: int = 24, bucket_hours: int = 1) -> dict[str, Any]:
    hours = _normalize_hours(hours)
    bucket_hours = max(1, bucket_hours)

    since = datetime.utcnow() - timedelta(hours=hours)

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    WITH message_buckets AS (
                        SELECT
                            date_trunc('hour', created_at) AS bucket,
                            COUNT(*) AS message_count
                        FROM messages
                        WHERE created_at >= :since
                        GROUP BY date_trunc('hour', created_at)
                    ),
                    escalation_buckets AS (
                        SELECT
                            date_trunc('hour', started_at) AS bucket,
                            COUNT(*) AS escalation_count
                        FROM conversations
                        WHERE started_at >= :since
                          AND status = 'escalated'
                        GROUP BY date_trunc('hour', started_at)
                    )
                    SELECT
                        COALESCE(m.bucket, e.bucket) AS bucket,
                        COALESCE(m.message_count, 0) AS messages,
                        COALESCE(e.escalation_count, 0) AS escalations
                    FROM message_buckets m
                    FULL OUTER JOIN escalation_buckets e ON m.bucket = e.bucket
                    ORDER BY bucket ASC
                    """
                ),
                {"since": since},
            )
        ).mappings().all()

    points = [
        {
            "bucket": row["bucket"].isoformat() if row["bucket"] else None,
            "messages": int(row["messages"] or 0),
            "escalations": int(row["escalations"] or 0),
        }
        for row in rows
        if row["bucket"] is not None
    ]

    return {
        "period_hours": int(hours),
        "bucket_hours": int(bucket_hours),
        "generated_at": datetime.utcnow().isoformat(),
        "series": points,
    }


async def fetch_dashboard_activity(
    *,
    hours: int = 24,
    limit: int = 80,
    channel: str | None = None,
    sender_type: str | None = None,
    sentiment: str | None = None,
) -> dict[str, Any]:
    hours = _normalize_hours(hours)
    limit = _bounded_limit(limit)
    sentiment_filter = (sentiment or "").strip().lower()

    since = datetime.utcnow() - timedelta(hours=hours)

    where_clauses = ["m.created_at >= :since"]
    params: dict[str, Any] = {"since": since, "limit": limit}

    if channel:
        where_clauses.append("m.channel = :channel")
        params["channel"] = channel
    if sender_type:
        where_clauses.append("m.sender_type = :sender_type")
        params["sender_type"] = sender_type

    where_sql = " AND ".join(where_clauses)

    query = text(
        f"""
        SELECT
            m.id::text AS id,
            m.created_at,
            m.content,
            m.channel,
            m.sender_type,
            m.conversation_id::text AS conversation_id,
            c.status AS conversation_status,
            cu.id::text AS customer_id,
            cu.name AS customer_name,
            cu.email AS customer_email
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN customers cu ON cu.id = c.customer_id
        WHERE {where_sql}
        ORDER BY m.created_at DESC
        LIMIT :limit
        """
    )

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(query, params)).mappings().all()

    items = []
    for row in rows:
        inbound = is_inbound_sender(row["sender_type"])
        sentiment_label, sentiment_score = score_sentiment(row["content"])

        if sentiment_filter in {"positive", "neutral", "negative"} and sentiment_label != sentiment_filter:
            continue

        if inbound:
            event_kind = "customer_message"
            direction = "inbound"
        elif row["sender_type"] == "agent":
            event_kind = "agent_reply"
            direction = "outbound"
        elif row["sender_type"] == "system":
            event_kind = "system_log"
            direction = "system"
        else:
            event_kind = "internal_event"
            direction = "system"

        items.append(
            {
                "id": row["id"],
                "timestamp": row["created_at"].isoformat() if row["created_at"] else None,
                "event_kind": event_kind,
                "direction": direction,
                "channel": row["channel"],
                "sender_type": row["sender_type"],
                "content": row["content"],
                "sentiment": {
                    "label": sentiment_label,
                    "score": sentiment_score,
                },
                "conversation": {
                    "id": row["conversation_id"],
                    "status": row["conversation_status"],
                },
                "customer": {
                    "id": row["customer_id"],
                    "name": row["customer_name"],
                    "email": row["customer_email"],
                },
            }
        )

    return {
        "period_hours": int(hours),
        "limit": int(limit),
        "count": len(items),
        "generated_at": datetime.utcnow().isoformat(),
        "items": items,
    }
