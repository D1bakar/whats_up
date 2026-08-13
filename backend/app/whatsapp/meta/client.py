import json
from typing import Any

import httpx
from app.core.config import Settings
from app.core.logging import get_logger
from app.whatsapp.exceptions import (
    ProviderAuthenticationError,
    ProviderPermanentFailureError,
    ProviderRateLimitError,
    ProviderTemporaryFailureError,
    ProviderTimeoutError,
)
from app.whatsapp.parser import parse_webhook_payload
from app.whatsapp.schemas import (
    OutboundMessageRequest,
    OutboundMessageResult,
    OutboundMessageType,
    WhatsAppInboundEvent,
)
from app.whatsapp.transport import HttpResponse, HttpTransport

logger = get_logger(__name__)


def _map_http_error(status_code: int, body: Any, retry_after: float | None) -> Exception:
    if status_code in (401, 403):
        return ProviderAuthenticationError(f"Provider authentication failed ({status_code})")
    if status_code == 429:
        return ProviderRateLimitError(retry_after=retry_after)
    if status_code >= 500:
        return ProviderTemporaryFailureError(f"Provider temporary failure ({status_code})")
    detail = body if isinstance(body, str) else json.dumps(body)
    return ProviderPermanentFailureError(f"Provider permanent failure ({status_code}): {detail}")


class HttpxTransport:
    """Production HTTP transport using httpx."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        try:
            async with httpx.AsyncClient(timeout=timeout or self._timeout) as client:
                response = await client.post(url, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Provider request timed out") from exc
        except httpx.TransportError as exc:
            raise ProviderTemporaryFailureError("Provider connection failed") from exc

        body: dict[str, Any] | list[Any] | str | None
        try:
            body = response.json()
        except ValueError:
            body = response.text

        return HttpResponse(
            status_code=response.status_code,
            body=body,
            headers=dict(response.headers),
        )


class MetaWhatsAppClient:
    """Meta WhatsApp Cloud API client (Graph API)."""

    def __init__(self, settings: Settings, transport: HttpTransport) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def name(self) -> str:
        return "meta"

    def _messages_url(self) -> str:
        base = self._settings.meta_whatsapp_api_base_url.rstrip("/")
        version = self._settings.meta_whatsapp_api_version.strip("/")
        phone_id = self._settings.meta_whatsapp_phone_number_id
        return f"{base}/{version}/{phone_id}/messages"

    def _auth_headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.meta_whatsapp_access_token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

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
        if request.message_type != OutboundMessageType.TEXT or not request.text:
            raise ProviderPermanentFailureError("Only text outbound messages are supported")

        payload = {
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "text",
            "text": {"body": request.text},
        }

        logger.info(
            "outbound_message_requested",
            provider=self.name,
            to=request.to,
            idempotency_key=request.idempotency_key,
        )

        response = await self._transport.post(
            self._messages_url(),
            json=payload,
            headers=self._auth_headers(request.idempotency_key),
        )

        if response.status_code >= 400:
            retry_after_raw = response.headers.get("Retry-After")
            retry_after = float(retry_after_raw) if retry_after_raw else None
            raise _map_http_error(response.status_code, response.body, retry_after)

        body = response.body if isinstance(response.body, dict) else {}
        messages = body.get("messages") or []
        if not messages or "id" not in messages[0]:
            raise ProviderTemporaryFailureError("Provider response missing message id")

        message_id = str(messages[0]["id"])
        logger.info(
            "outbound_message_succeeded",
            provider=self.name,
            message_id=message_id,
            idempotency_key=request.idempotency_key,
        )
        return OutboundMessageResult(
            message_id=message_id,
            provider=self.name,
            metadata={"response": body},
        )
