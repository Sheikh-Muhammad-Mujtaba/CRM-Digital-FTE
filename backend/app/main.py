import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import routes
from app.core.database import AsyncSessionLocal

app = FastAPI(
    title="CRM Digital FTE",
    description="Autonomous Customer Success FTE — multi-channel intake, Kafka, Gemini 2.5 Flash",
    version="1.0.0",
)

_cors = os.getenv("CORS_ORIGINS", "http://localhost:3000")
_origins = [o.strip() for o in _cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")


@app.get("/")
async def root():
    return {"service": "CRM Digital FTE API", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Database not reachable"
        ) from exc
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Minimal Prometheus-style scrape target (uptime probe)."""
    body = "# HELP digital_fte_up Service availability\n# TYPE digital_fte_up gauge\ndigital_fte_up 1\n"
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
