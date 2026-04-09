from database.queries.admin import fetch_daily_summary


async def collect_last_24h_metrics() -> dict:
    summary = await fetch_daily_summary(1)
    return {
        "tickets_24h": summary["tickets_created"],
        "messages_24h": summary["messages_logged"],
        "escalations_24h": summary["escalated_conversations"],
    }
