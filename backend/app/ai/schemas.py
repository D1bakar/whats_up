from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class AIResponseType(str, Enum):
    TEXT = "text"
    STRUCTURED = "structured"
    TOOL_REQUEST = "tool_request"


class AIUsageMetadata(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AILatencyMetadata(BaseModel):
    latency_ms: float


class AIToolRequest(BaseModel):
    """Future tool invocation requested by the model."""

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class AIResponse(BaseModel):
    text: str
    response_type: AIResponseType = AIResponseType.TEXT
    provider: str
    model: str
    usage: AIUsageMetadata | None = None
    latency: AILatencyMetadata | None = None
    tool_request: AIToolRequest | None = None
    fallback_used: bool = False
    prompt_version: str | None = None


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConversationContext(BaseModel):
    conversation_id: str
    current_state: str
    state_summary: dict[str, object] = Field(default_factory=dict)
    turns: list[ConversationTurn] = Field(default_factory=list)
    prompt_version: str


class PromptBundle(BaseModel):
    """Versioned, structured prompt components."""

    system_instructions: str
    business_rules: str
    conversation_context: str
    user_message: str
    version: str


class AIRequest(BaseModel):
    prompt: PromptBundle
    model: str
    max_output_tokens: int
    temperature: float | None = None
    response_format: Literal["text", "json"] = "text"


class StructuredAIRequest(AIRequest):
    response_schema: dict[str, object] = Field(default_factory=dict)
