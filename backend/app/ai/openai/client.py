import json
import time
from typing import Any

import httpx
from app.ai.exceptions import (
    AIProviderAuthenticationError,
    AIProviderClientError,
    AIProviderConnectionError,
    AIProviderMalformedResponseError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)
from app.ai.prompts.assembler import render_messages_for_provider
from app.ai.schemas import (
    AILatencyMetadata,
    AIRequest,
    AIResponse,
    AIResponseType,
    AIUsageMetadata,
    StructuredAIRequest,
)
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider:
    """OpenAI Chat Completions adapter using httpx."""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = transport or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.ai_request_timeout),
        )
        self._owns_client = transport is None

    @property
    def name(self) -> str:
        return "openai"

    async def generate_response(self, request: AIRequest) -> AIResponse:
        return await self._complete(request)

    async def generate_structured_response(self, request: StructuredAIRequest) -> AIResponse:
        structured_request = request.model_copy(update={"response_format": "json"})
        response = await self._complete(structured_request)
        return response.model_copy(update={"response_type": AIResponseType.STRUCTURED})

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _complete(self, request: AIRequest) -> AIResponse:
        if not self._settings.openai_api_key.strip():
            raise AIProviderAuthenticationError("OpenAI API key is not configured")

        started = time.perf_counter()
        messages = render_messages_for_provider(request.prompt)
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError("OpenAI request timed out") from exc
        except httpx.RequestError as exc:
            raise AIProviderConnectionError("OpenAI connection failed") from exc

        latency_ms = (time.perf_counter() - started) * 1000

        if response.status_code in {401, 403}:
            raise AIProviderAuthenticationError("OpenAI authentication failed")
        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            raise AIProviderRateLimitError(retry_after=retry_after)
        if 400 <= response.status_code < 500:
            raise AIProviderClientError(f"OpenAI client error: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise AIProviderServerError(f"OpenAI server error: HTTP {response.status_code}")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise AIProviderMalformedResponseError("OpenAI returned invalid JSON") from exc

        return _parse_openai_response(
            data,
            provider=self.name,
            model=request.model,
            latency_ms=latency_ms,
            prompt_version=request.prompt.version,
        )


def _parse_openai_response(
    data: dict[str, Any],
    *,
    provider: str,
    model: str,
    latency_ms: float,
    prompt_version: str,
) -> AIResponse:
    try:
        choices = data["choices"]
        message = choices[0]["message"]
        text = message["content"]
        if not isinstance(text, str):
            raise AIProviderMalformedResponseError("OpenAI content is not text")
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderMalformedResponseError("OpenAI response missing content") from exc

    usage_raw = data.get("usage") or {}
    usage = AIUsageMetadata(
        prompt_tokens=_coerce_int(usage_raw.get("prompt_tokens")),
        completion_tokens=_coerce_int(usage_raw.get("completion_tokens")),
        total_tokens=_coerce_int(usage_raw.get("total_tokens")),
    )

    return AIResponse(
        text=text,
        provider=provider,
        model=model,
        usage=usage,
        latency=AILatencyMetadata(latency_ms=latency_ms),
        prompt_version=prompt_version,
    )


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
