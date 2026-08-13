import json

from app.api.deps import get_app_settings, get_db
from app.core.config import Settings
from app.core.exceptions import APIError
from app.core.logging import get_logger
from app.services.inbound import InboundEventService
from app.services.outbound import OutboundMessageService
from app.webhooks.whatsapp.signature import verify_signature
from app.whatsapp.provider import WhatsAppProvider
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_whatsapp_provider(request: Request) -> WhatsAppProvider:
    provider: WhatsAppProvider = request.app.state.whatsapp_provider
    return provider


def get_outbound_service(request: Request) -> OutboundMessageService:
    service: OutboundMessageService = request.app.state.outbound_service
    return service


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    settings: Settings = Depends(get_app_settings),
) -> PlainTextResponse:
    if hub_mode != "subscribe":
        raise APIError("webhook_validation_failed", "Invalid hub.mode", status_code=403)

    if not hub_verify_token or hub_verify_token != settings.whatsapp_verify_token:
        logger.warning("webhook_verification_failed", reason="invalid_verify_token")
        raise APIError("webhook_validation_failed", "Invalid verify token", status_code=403)

    logger.info("webhook_verification_succeeded")
    return PlainTextResponse(content=hub_challenge or "", status_code=200)


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    provider: WhatsAppProvider = Depends(get_whatsapp_provider),
    outbound_service: OutboundMessageService = Depends(get_outbound_service),
) -> dict[str, int | str]:
    raw_body = await request.body()

    if settings.whatsapp_signature_required:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(settings.whatsapp_app_secret, raw_body, signature):
            logger.warning("webhook_verification_failed", reason="invalid_signature")
            raise APIError("webhook_validation_failed", "Invalid signature", status_code=403)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        logger.warning("webhook_invalid_json", error=str(exc))
        raise APIError(
            "webhook_validation_failed", "Invalid JSON payload", status_code=400
        ) from exc

    if not isinstance(payload, dict):
        raise APIError(
            "webhook_validation_failed", "Payload must be a JSON object", status_code=400
        )

    logger.info("webhook_received", object_type=payload.get("object"))

    inbound_service = InboundEventService(provider, outbound_service, db)

    try:
        result = await inbound_service.handle_webhook_payload(payload)
    except Exception as exc:
        logger.exception("webhook_processing_failed")
        raise APIError(
            "webhook_processing_failed",
            "Unable to persist webhook event",
            status_code=503,
        ) from exc

    return {"status": "ok", **result}
