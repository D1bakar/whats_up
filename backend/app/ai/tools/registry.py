from app.ai.exceptions import AIProviderError
from app.ai.schemas import AIToolRequest
from pydantic import BaseModel


class ToolSpec(BaseModel):
    """Foundation for future safe, typed tools."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    timeout_seconds: float
    requires_authorization: bool = True


class ToolRegistry:
    """Registry of explicitly defined tools — no dangerous defaults."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def validate_tool_request(self, request: AIToolRequest) -> ToolSpec:
        spec = self.get(request.tool_name)
        if spec is None:
            raise AIProviderError(f"Unknown tool requested: {request.tool_name}")
        return spec

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())
