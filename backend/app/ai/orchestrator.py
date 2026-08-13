import asyncio
import time

from app.ai.context import ConversationContextBuilder
from app.ai.exceptions import (
    AIAbuseLimitExceededError,
    AIInputLimitExceededError,
    AIProviderAuthenticationError,
    AIProviderClientError,
    AIProviderConnectionError,
    AIProviderEmptyResponseError,
    AIProviderError,
    AIProviderMalformedResponseError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)
from app.ai.limits import ConversationRateLimiter
from app.ai.prompts.assembler import build_prompt_bundle
from app.ai.provider import AIProvider
from app.ai.schemas import AILatencyMetadata, AIRequest, AIResponse
from app.ai.validation import validate_ai_response
from app.bot import responses as bot_text
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TRANSIENT_ERRORS = (
    AIProviderTimeoutError,
    AIProviderConnectionError,
    AIProviderRateLimitError,
    AIProviderServerError,
)


class AIOrchestrator:
    """
    Application-level AI orchestration.

    Does not send WhatsApp messages, access raw webhooks, execute code,
    modify arbitrary database records, or expose secrets.
    """

    def __init__(
        self,
        settings: Settings,
        provider: AIProvider,
        context_builder: ConversationContextBuilder,
        *,
        rate_limiter: ConversationRateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._context_builder = context_builder
        self._rate_limiter = rate_limiter or ConversationRateLimiter(
            max_requests=settings.ai_max_requests_per_conversation,
            window_seconds=settings.ai_request_window_seconds,
        )

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def generate_reply(
        self,
        *,
        conversation_id: str,
        user_message: str,
        current_state: str,
        state_data: dict[str, object],
        exclude_wamid: str | None = None,
    ) -> AIResponse:
        started = time.perf_counter()

        logger.info(
            "ai_request_started",
            conversation_id=conversation_id,
            provider=self._provider.name,
            model=self._settings.ai_model,
        )

        try:
            self._validate_user_message(user_message)
            if not self._rate_limiter.allow(conversation_id):
                raise AIAbuseLimitExceededError("Conversation AI request limit exceeded")

            context = await self._context_builder.build(
                conversation_id=conversation_id,
                current_state=current_state,
                state_data=state_data,
                user_message=user_message,
                exclude_wamid=exclude_wamid,
            )

            prompt = build_prompt_bundle(context, user_message)
            request = AIRequest(
                prompt=prompt,
                model=self._settings.ai_model,
                max_output_tokens=self._settings.ai_max_output_tokens,
                temperature=self._settings.ai_temperature,
            )

            response = await self._generate_with_retries(request)
            validated = validate_ai_response(
                response,
                max_output_chars=self._settings.ai_max_output_chars,
            )

            latency_ms = (time.perf_counter() - started) * 1000
            final = validated.model_copy(
                update={
                    "latency": validated.latency or AILatencyMetadata(latency_ms=latency_ms),
                },
            )

            logger.info(
                "ai_request_completed",
                conversation_id=conversation_id,
                provider=final.provider,
                model=final.model,
                latency_ms=final.latency.latency_ms if final.latency else latency_ms,
                prompt_tokens=final.usage.prompt_tokens if final.usage else None,
                completion_tokens=final.usage.completion_tokens if final.usage else None,
                fallback_used=False,
            )
            return final

        except AIInputLimitExceededError as exc:
            logger.warning(
                "ai_request_failed",
                conversation_id=conversation_id,
                failure_type="input_limit",
                error=str(exc),
            )
            return self._fallback_response(
                bot_text.AI_INPUT_TOO_LONG,
                started=started,
                reason="input_limit",
            )
        except AIAbuseLimitExceededError as exc:
            logger.warning(
                "ai_request_failed",
                conversation_id=conversation_id,
                failure_type="abuse_limit",
                error=str(exc),
            )
            return self._fallback_response(
                bot_text.AI_RATE_LIMITED,
                started=started,
                reason="abuse_limit",
            )
        except AIProviderError as exc:
            logger.warning(
                "ai_request_failed",
                conversation_id=conversation_id,
                failure_type=exc.__class__.__name__,
                error=str(exc),
            )
            return self._fallback_response(
                bot_text.AI_UNAVAILABLE,
                started=started,
                reason=exc.__class__.__name__,
            )

    async def _generate_with_retries(self, request: AIRequest) -> AIResponse:
        max_attempts = self._settings.ai_max_retries + 1
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return await self._provider.generate_response(request)
            except _TRANSIENT_ERRORS as exc:
                last_error = exc
                if attempt >= max_attempts - 1:
                    break
                delay = self._settings.ai_retry_base_delay * (2**attempt)
                if isinstance(exc, AIProviderRateLimitError) and exc.retry_after:
                    delay = max(delay, exc.retry_after)
                logger.info(
                    "ai_request_retry",
                    provider=self._provider.name,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    failure_type=exc.__class__.__name__,
                )
                await asyncio.sleep(delay)
            except (
                AIProviderAuthenticationError,
                AIProviderClientError,
                AIProviderMalformedResponseError,
                AIProviderEmptyResponseError,
            ):
                raise
            except AIProviderError as exc:
                last_error = exc
                break

        if last_error is not None:
            raise last_error
        raise AIProviderError("AI generation failed without a specific error")

    def _validate_user_message(self, user_message: str) -> None:
        if len(user_message) > self._settings.ai_max_user_message_length:
            raise AIInputLimitExceededError("User message exceeds maximum length")

    def _fallback_response(
        self,
        text: str,
        *,
        started: float,
        reason: str,
    ) -> AIResponse:
        latency_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "ai_fallback_used",
            provider=self._provider.name,
            model=self._settings.ai_model,
            latency_ms=latency_ms,
            reason=reason,
        )
        return AIResponse(
            text=text,
            provider=self._provider.name,
            model=self._settings.ai_model,
            latency=AILatencyMetadata(latency_ms=latency_ms),
            fallback_used=True,
        )
