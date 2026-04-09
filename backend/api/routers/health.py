from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text

from core.database import AsyncSessionLocal

router = APIRouter()


@router.get("/")
async def root():
    return {"service": "CRM Digital FTE API", "status": "ok"}


@router.get("/health")
async def health():
    return {"status": "healthy"}


@router.get("/ready")
async def ready():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database not reachable") from exc
    return {"status": "ready"}


@router.get("/metrics")
async def metrics():
    body = "# HELP digital_fte_up Service availability\n# TYPE digital_fte_up gauge\ndigital_fte_up 1\n"
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
