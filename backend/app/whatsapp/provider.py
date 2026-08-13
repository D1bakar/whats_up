from typing import Any, Protocol

from app.whatsapp.schemas import (
    OutboundMessageRequest,
    OutboundMessageResult,
    WhatsAppInboundEvent,
)


class WhatsAppProvider(Protocol):
    """Provider-independent WhatsApp messaging interface."""

    @property
    def name(self) -> str: ...

    async def send_text_message(
        self,
        to: str,
        text: str,
        *,
        idempotency_key: str | None = None,
    ) -> OutboundMessageResult: ...

    async def send_message(self, request: OutboundMessageRequest) -> OutboundMessageResult: ...

    def parse_incoming_event(self, payload: dict[str, Any]) -> list[WhatsAppInboundEvent]: ...
