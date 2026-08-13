from typing import Any

from app.ai.bot_factory import create_bot_engine
from app.ai.provider import AIProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.webhook_event import WebhookProcessingStatus
from app.services.idempotency import WebhookIdempotencyService
from app.services.message_processor import MessageProcessingService
from app.services.outbound import OutboundMessageService
from app.whatsapp.exceptions import MessageParsingError
from app.whatsapp.provider import WhatsAppProvider
from app.whatsapp.schemas import InboundEventKind, WhatsAppInboundEvent
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class InboundEventService:
    """Processes accepted webhook events through the bot engine pipeline."""

    def __init__(
        self,
        provider: WhatsAppProvider,
        outbound_service: OutboundMessageService,
        session: AsyncSession,
        settings: Settings | None = None,
        *,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self._provider = provider
        self._outbound = outbound_service
        self._session = session
        self._settings = settings or get_settings()
        self._ai_provider = ai_provider
        self._idempotency = WebhookIdempotencyService(session)
        self._processor = MessageProcessingService(
            session,
            outbound_service,
            bot_engine=create_bot_engine(
                self._settings,
                session,
                ai_provider=ai_provider,
            ),
        )

    async def handle_webhook_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            events = self._provider.parse_incoming_event(payload)
        except MessageParsingError:
            logger.warning("webhook_parse_failed")
            return {"accepted": 0, "duplicates": 0, "unsupported": 0, "errors": 1}

        accepted = 0
        duplicates = 0
        unsupported = 0

        for event in events:
            result = await self._process_event(event, payload)
            if result == "accepted":
                accepted += 1
            elif result == "duplicate":
                duplicates += 1
            elif result == "unsupported":
                unsupported += 1

        return {
            "accepted": accepted,
            "duplicates": duplicates,
            "unsupported": unsupported,
            "errors": 0,
        }

    async def _process_event(
        self,
        event: WhatsAppInboundEvent,
        raw_payload: dict[str, Any],
    ) -> str:
        status = (
            WebhookProcessingStatus.UNSUPPORTED
            if event.kind == InboundEventKind.UNSUPPORTED
            else WebhookProcessingStatus.PENDING
        )

        db_event, is_new = await self._idempotency.register(
            event.event_id,
            wamid=event.message_id,
            raw_payload=raw_payload,
            status=status,
        )

        if not is_new and not self._idempotency.should_process(db_event):
            return "duplicate"

        if not is_new:
            logger.info(
                "event_retry",
                event_id=event.event_id,
                message_id=event.message_id,
                status=db_event.processing_status.value,
            )

        logger.info(
            "event_parsed",
            event_id=event.event_id,
            message_id=event.message_id,
            kind=event.kind.value,
            message_type=event.message_type,
        )

        try:
            if event.kind == InboundEventKind.UNSUPPORTED:
                logger.info(
                    "unsupported_event",
                    event_id=event.event_id,
                    message_type=event.message_type,
                )
                await self._idempotency.mark_processed(
                    db_event,
                    WebhookProcessingStatus.UNSUPPORTED,
                )
                return "unsupported"

            if event.kind == InboundEventKind.STATUS:
                await self._idempotency.mark_processed(db_event, WebhookProcessingStatus.PROCESSED)
                return "accepted"

            if event.kind == InboundEventKind.MESSAGE:
                outcome = await self._processor.process_inbound_event(event)

                if outcome == "duplicate":
                    await self._idempotency.mark_processed(
                        db_event,
                        WebhookProcessingStatus.PROCESSED,
                    )
                    return "duplicate"

                if outcome in {"unsupported", "ignored"}:
                    await self._idempotency.mark_processed(
                        db_event,
                        WebhookProcessingStatus.UNSUPPORTED,
                    )
                    return "unsupported"

                if outcome == "failed":
                    await self._idempotency.mark_failed(db_event)
                    return "accepted"

                await self._idempotency.mark_processed(db_event, WebhookProcessingStatus.PROCESSED)
                return "accepted"

            await self._idempotency.mark_processed(db_event, WebhookProcessingStatus.PROCESSED)
            return "accepted"

        except Exception:
            await self._idempotency.mark_failed(db_event)
            raise
