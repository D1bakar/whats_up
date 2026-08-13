from app.ai.mock.provider import MockAIProvider
from app.ai.ollama.client import OllamaProvider
from app.ai.openai.client import OpenAIProvider
from app.ai.provider import AIProvider
from app.core.config import Settings


def create_ai_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "mock":
        return MockAIProvider()
    if settings.ai_provider == "ollama":
        return OllamaProvider(settings)
    if settings.ai_provider == "openai":
        return OpenAIProvider(settings)
    raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")
