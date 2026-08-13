import json
import time
from typing import Any

import httpx
from app.ai.exceptions import (
    AIProviderClientError,
    AIProviderConnectionError,
    AIProviderMalformedResponseError,
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


class OllamaProvider:
    """Ollama /api/chat adapter using httpx."""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._client = transport or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.effective_ai_request_timeout),
        )
        self._owns_client = transport is None

    @property
    def name(self) -> str:
        return "ollama"

    async def generate_response(self, request: AIRequest) -> AIResponse:
        return await self._chat(request)

    async def generate_structured_response(self, request: StructuredAIRequest) -> AIResponse:
        structured_request = request.model_copy(update={"response_format": "json"})
        response = await self._chat(structured_request)
        return response.model_copy(update={"response_type": AIResponseType.STRUCTURED})

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _chat(self, request: AIRequest) -> AIResponse:
        started = time.perf_counter()
        messages = render_messages_for_provider(request.prompt)
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": request.max_output_tokens,
            },
        }
        if request.temperature is not None:
            payload["options"]["temperature"] = request.temperature
        if request.response_format == "json":
            payload["format"] = "json"

        url = f"{self._base_url}/api/chat"

        try:
            response = await self._client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError("Ollama request timed out") from exc
        except httpx.RequestError as exc:
            raise AIProviderConnectionError("Ollama connection failed") from exc

        latency_ms = (time.perf_counter() - started) * 1000

        if 400 <= response.status_code < 500:
            raise AIProviderClientError(f"Ollama client error: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise AIProviderServerError(f"Ollama server error: HTTP {response.status_code}")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise AIProviderMalformedResponseError("Ollama returned invalid JSON") from exc

        return _parse_ollama_response(
            data,
            provider=self.name,
            model=request.model,
            latency_ms=latency_ms,
            prompt_version=request.prompt.version,
        )


def _parse_ollama_response(
    data: dict[str, Any],
    *,
    provider: str,
    model: str,
    latency_ms: float,
    prompt_version: str,
) -> AIResponse:
    try:
        message = data["message"]
        text = message["content"]
        if not isinstance(text, str):
            raise AIProviderMalformedResponseError("Ollama content is not text")
    except (KeyError, TypeError) as exc:
        raise AIProviderMalformedResponseError("Ollama response missing content") from exc

    response_model = data.get("model")
    resolved_model = response_model if isinstance(response_model, str) else model

    usage = AIUsageMetadata(
        prompt_tokens=_coerce_int(data.get("prompt_eval_count")),
        completion_tokens=_coerce_int(data.get("eval_count")),
        total_tokens=_sum_tokens(
            _coerce_int(data.get("prompt_eval_count")),
            _coerce_int(data.get("eval_count")),
        ),
    )

    return AIResponse(
        text=text,
        provider=provider,
        model=resolved_model,
        usage=usage,
        latency=AILatencyMetadata(latency_ms=latency_ms),
        prompt_version=prompt_version,
    )


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _sum_tokens(prompt: int | None, completion: int | None) -> int | None:
    if prompt is None and completion is None:
        return None
    return (prompt or 0) + (completion or 0)
