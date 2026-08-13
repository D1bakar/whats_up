import json

import httpx
import pytest
from app.ai.exceptions import (
    AIProviderConnectionError,
    AIProviderMalformedResponseError,
    AIProviderServerError,
    AIProviderTimeoutError,
)
from app.ai.factory import create_ai_provider
from app.ai.ollama.client import OllamaProvider
from app.ai.prompts.assembler import build_prompt_bundle
from app.ai.schemas import AIRequest, ConversationContext
from app.core.config import Settings


def _ollama_settings(**overrides: object) -> Settings:
    base = {
        "AI_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "phi3:mini",
        "OLLAMA_REQUEST_TIMEOUT": 120.0,
    }
    base.update(overrides)
    return Settings(**base)


def _sample_request(model: str = "phi3:mini") -> AIRequest:
    bundle = build_prompt_bundle(
        ConversationContext(
            conversation_id="conv-1",
            current_state="main_menu",
            prompt_version="v1",
        ),
        "What are your hours?",
    )
    return AIRequest(prompt=bundle, model=model, max_output_tokens=100, temperature=0.7)


def _ollama_chat_response(
    *,
    content: str = "We are open 9am to 5pm.",
    model: str = "phi3:mini",
) -> dict[str, object]:
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": 12,
        "eval_count": 8,
    }


@pytest.mark.asyncio
async def test_ollama_provider_successful_response() -> None:
    settings = _ollama_settings()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://127.0.0.1:11434/api/chat")
        body = json.loads(request.content.decode())
        assert body["model"] == "phi3:mini"
        assert body["stream"] is False
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(200, json=_ollama_chat_response())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, transport=client)

    response = await provider.generate_response(_sample_request())

    assert response.text == "We are open 9am to 5pm."
    assert response.provider == "ollama"
    assert response.model == "phi3:mini"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 12
    assert response.usage.completion_tokens == 8
    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_empty_response_raises() -> None:
    settings = _ollama_settings()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ollama_chat_response(content="   "))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, transport=client)
    response = await provider.generate_response(_sample_request())
    assert response.text.strip() == ""
    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_malformed_response() -> None:
    settings = _ollama_settings()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, transport=client)

    with pytest.raises(AIProviderMalformedResponseError):
        await provider.generate_response(_sample_request())
    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_connection_error() -> None:
    settings = _ollama_settings()

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=_request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, transport=client)

    with pytest.raises(AIProviderConnectionError):
        await provider.generate_response(_sample_request())
    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_server_error() -> None:
    settings = _ollama_settings()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, transport=client)

    with pytest.raises(AIProviderServerError):
        await provider.generate_response(_sample_request())
    await provider.aclose()


@pytest.mark.asyncio
async def test_ollama_provider_timeout() -> None:
    settings = _ollama_settings()

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=_request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(settings, transport=client)

    with pytest.raises(AIProviderTimeoutError):
        await provider.generate_response(_sample_request())
    await provider.aclose()


def test_factory_creates_ollama_provider_without_openai_key() -> None:
    settings = _ollama_settings(OPENAI_API_KEY="")
    provider = create_ai_provider(settings)
    assert provider.name == "ollama"
    assert settings.effective_ai_request_timeout == 120.0


def test_effective_timeout_differs_by_provider() -> None:
    ollama = _ollama_settings()
    openai = Settings(AI_PROVIDER="openai", AI_REQUEST_TIMEOUT=45.0)
    assert ollama.effective_ai_request_timeout == 120.0
    assert openai.effective_ai_request_timeout == 45.0


@pytest.mark.asyncio
@pytest.mark.ollama
async def test_ollama_live_integration() -> None:
    """Optional live test — skipped unless RUN_OLLAMA_INTEGRATION=1."""
    import os

    if os.getenv("RUN_OLLAMA_INTEGRATION") != "1":
        pytest.skip("Set RUN_OLLAMA_INTEGRATION=1 to run live Ollama integration test")

    settings = _ollama_settings()
    provider = create_ai_provider(settings)
    response = await provider.generate_response(_sample_request())
    assert response.provider == "ollama"
    assert response.model == "phi3:mini"
    assert response.text.strip()
    if isinstance(provider, OllamaProvider):
        await provider.aclose()
