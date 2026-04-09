import asyncio
import logging
import os
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.admin import router as admin_router
from api.routers.health import router as health_router
from api.routers.intake import router as intake_router
from channels.gmail_handler import process_gmail_sync_events
from settings import get_settings
from workers.kafka import create_producer, publish_event

logger = logging.getLogger(__name__)

_gmail_poll_task: asyncio.Task | None = None


async def _gmail_poll_loop() -> None:
    settings = get_settings()
    producer = create_producer()
    interval = settings.gmail_poll_interval_seconds

    logger.info("Gmail poller started (interval=%ss)", interval)
    while True:
        try:
            events = await process_gmail_sync_events()
            for event in events:
                publish_event(producer, settings.kafka_intake_topic, event)
            if events:
                logger.info("Gmail poller queued %d message(s)", len(events))
        except Exception as err:
            message = str(err)
            if "invalid_grant" in message.lower() or "refresh token" in message.lower():
                logger.error(
                    "Gmail poller stopped due to OAuth credential error: %s",
                    message,
                )
                return
            logger.error("Gmail poller iteration failed: %s", err, exc_info=True)

        await asyncio.sleep(interval)


def _gmail_polling_ready() -> bool:
    required = [
        os.getenv("GMAIL_CLIENT_ID"),
        os.getenv("GMAIL_CLIENT_SECRET"),
        os.getenv("GMAIL_REFRESH_TOKEN"),
    ]
    return all(required)

app = FastAPI(
    title="CRM Digital FTE",
    description="Autonomous Customer Success FTE — multi-channel intake, Kafka, Gemini 2.5 Flash",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(intake_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.on_event("startup")
async def startup_event() -> None:
    global _gmail_poll_task
    settings = get_settings()

    if not settings.gmail_poll_enabled:
        logger.info("Gmail poller disabled by GMAIL_POLL_ENABLED=false")
        return

    if not _gmail_polling_ready():
        logger.warning(
            "Gmail poller disabled: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN"
        )
        return

    _gmail_poll_task = asyncio.create_task(_gmail_poll_loop(), name="gmail-poll-loop")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _gmail_poll_task

    if _gmail_poll_task is None:
        return

    _gmail_poll_task.cancel()
    with suppress(asyncio.CancelledError):
        await _gmail_poll_task
    _gmail_poll_task = None
