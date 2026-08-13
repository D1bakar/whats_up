import asyncio
import random

from app.core.config import Settings
from app.core.logging import get_logger
from app.whatsapp.exceptions import (
    ProviderPermanentFailureError,
    ProviderRateLimitError,
    ProviderTemporaryFailureError,
)
from app.whatsapp.provider import WhatsAppProvider
from app.whatsapp.schemas import OutboundMessageRequest, OutboundMessageResult

logger = get_logger(__name__)


class OutboundMessageService:
    """Application service for outbound WhatsApp messages with bounded retries."""

    def __init__(self, provider: WhatsAppProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    async def send_text_message(
        self,
        to: str,
        text: str,
        *,
        idempotency_key: str | None = None,
    ) -> OutboundMessageResult:
        request = OutboundMessageRequest(to=to, text=text, idempotency_key=idempotency_key)
        return await self.send_message(request)

    async def send_message(self, request: OutboundMessageRequest) -> OutboundMessageResult:
        max_retries = self._settings.whatsapp_outbound_max_retries
        base_delay = self._settings.whatsapp_outbound_retry_base_delay

        logger.info(
            "outbound_message_requested",
            provider=self._provider.name,
            to=request.to,
            idempotency_key=request.idempotency_key,
        )

        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                result = await self._provider.send_message(request)
                logger.info(
                    "outbound_message_succeeded",
                    provider=self._provider.name,
                    message_id=result.message_id,
                    idempotency_key=request.idempotency_key,
                )
                return result
            except ProviderRateLimitError as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                delay = exc.retry_after or self._backoff(base_delay, attempt)
                logger.warning(
                    "outbound_message_rate_limited",
                    provider=self._provider.name,
                    attempt=attempt + 1,
                    retry_in=delay,
                )
                await asyncio.sleep(delay)
            except ProviderTemporaryFailureError as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                delay = self._backoff(base_delay, attempt)
                logger.warning(
                    "outbound_message_retry",
                    provider=self._provider.name,
                    attempt=attempt + 1,
                    retry_in=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
            except ProviderPermanentFailureError as exc:
                logger.error(
                    "outbound_message_failed",
                    provider=self._provider.name,
                    error=str(exc),
                    retryable=False,
                )
                raise
            except Exception as exc:
                logger.error(
                    "outbound_message_failed",
                    provider=self._provider.name,
                    error=str(exc),
                    retryable=False,
                )
                raise

        logger.error(
            "outbound_message_failed",
            provider=self._provider.name,
            error=str(last_error),
            retryable=True,
            attempts=max_retries + 1,
        )
        assert last_error is not None
        raise last_error

    @staticmethod
    def _backoff(base_delay: float, attempt: int) -> float:
        delay = base_delay * (4**attempt)
        jitter = random.uniform(0, base_delay)
        return float(min(delay + jitter, 60.0))
