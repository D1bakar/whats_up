from typing import Protocol

from app.ai.schemas import AIRequest, AIResponse, StructuredAIRequest


class AIProvider(Protocol):
    """Provider-independent AI generation interface."""

    @property
    def name(self) -> str: ...

    async def generate_response(self, request: AIRequest) -> AIResponse: ...

    async def generate_structured_response(self, request: StructuredAIRequest) -> AIResponse: ...
