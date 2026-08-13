from typing import Literal

from app.api.deps import get_db, get_redis
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = Field(examples=["whatsapp-platform-api"])


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "error"]
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: list[ReadinessCheck]


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(request: Request) -> HealthResponse:
    return HealthResponse(service=request.app.state.settings.app_name)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyResponse}},
)
async def ready(
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
) -> ReadyResponse:
    checks: list[ReadinessCheck] = []

    try:
        await db.execute(text("SELECT 1"))
        checks.append(ReadinessCheck(name="postgresql", status="ok"))
    except Exception as exc:
        checks.append(
            ReadinessCheck(name="postgresql", status="error", detail=str(exc)),
        )

    try:
        pong = await redis_client.ping()
        if pong:
            checks.append(ReadinessCheck(name="redis", status="ok"))
        else:
            checks.append(ReadinessCheck(name="redis", status="error", detail="PING failed"))
    except Exception as exc:
        checks.append(ReadinessCheck(name="redis", status="error", detail=str(exc)))

    overall: Literal["ok", "degraded"] = (
        "ok" if all(check.status == "ok" for check in checks) else "degraded"
    )
    return ReadyResponse(status=overall, checks=checks)
