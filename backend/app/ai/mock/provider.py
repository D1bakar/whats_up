import asyncio
import json
from typing import Any

from app.ai.schemas import (
    AILatencyMetadata,
    AIRequest,
    AIResponse,
    AIResponseType,
    AIUsageMetadata,
    StructuredAIRequest,
)


class MockAIProvider:
    """Deterministic AI provider for development and automated tests."""

    DEFAULT_RESPONSE = "Mock AI: I can help with that."

    def __init__(
        self,
        *,
        response_text: str | None = None,
        structured_response: dict[str, Any] | None = None,
        fail_with: Exception | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.response_text = self.DEFAULT_RESPONSE if response_text is None else response_text
        self.structured_response = structured_response
        self.fail_with = fail_with
        self.delay_seconds = delay_seconds
        self.call_count = 0
        self.last_request: AIRequest | None = None

    @property
    def name(self) -> str:
        return "mock"

    async def generate_response(self, request: AIRequest) -> AIResponse:
        self.call_count += 1
        self.last_request = request
        await self._maybe_fail_or_delay()

        return AIResponse(
            text=self.response_text,
            provider=self.name,
            model=request.model,
            usage=AIUsageMetadata(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            latency=AILatencyMetadata(latency_ms=1.0),
            prompt_version=request.prompt.version,
        )

    async def generate_structured_response(self, request: StructuredAIRequest) -> AIResponse:
        self.call_count += 1
        self.last_request = request
        await self._maybe_fail_or_delay()

        payload = self.structured_response or {"answer": self.response_text}
        return AIResponse(
            text=json.dumps(payload),
            response_type=AIResponseType.STRUCTURED,
            provider=self.name,
            model=request.model,
            usage=AIUsageMetadata(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            latency=AILatencyMetadata(latency_ms=1.0),
            prompt_version=request.prompt.version,
        )

    async def _maybe_fail_or_delay(self) -> None:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.fail_with is not None:
            raise self.fail_with
