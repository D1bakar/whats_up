from typing import Any

from app.core.logging import get_logger
from app.whatsapp.parser import parse_webhook_payload
from app.whatsapp.schemas import (
    OutboundMessageRequest,
    OutboundMessageResult,
    OutboundMessageType,
    WhatsAppInboundEvent,
)

logger = get_logger(__name__)


class MockWhatsAppProvider:
    """Local mock provider for development and automated tests."""

    def __init__(self) -> None:
        self.outbound_messages: list[OutboundMessageRequest] = []
        self._message_counter = 0

    @property
    def name(self) -> str:
        return "mock"

    def parse_incoming_event(self, payload: dict[str, Any]) -> list[WhatsAppInboundEvent]:
        return parse_webhook_payload(payload)

    async def send_text_message(
        self,
        to: str,
        text: str,
        *,
        idempotency_key: str | None = None,
    ) -> OutboundMessageResult:
        request = OutboundMessageRequest(
            to=to,
            text=text,
            message_type=OutboundMessageType.TEXT,
            idempotency_key=idempotency_key,
        )
        return await self.send_message(request)

    async def send_message(self, request: OutboundMessageRequest) -> OutboundMessageResult:
        self._message_counter += 1
        self.outbound_messages.append(request)

        message_id = f"wamid.mock.{self._message_counter}"
        logger.info(
            "outbound_message_succeeded",
            provider=self.name,
            message_id=message_id,
            to=request.to,
            idempotency_key=request.idempotency_key,
        )
        return OutboundMessageResult(
            message_id=message_id,
            provider=self.name,
            metadata={"mock": True},
        )

    def clear(self) -> None:
        self.outbound_messages.clear()
        self._message_counter = 0
