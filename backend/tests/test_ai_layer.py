import copy
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from app.ai.bot_factory import create_bot_engine, create_bot_engine_without_ai
from app.ai.context import ConversationContextBuilder
from app.ai.exceptions import (
    AIProviderEmptyResponseError,
    AIProviderError,
    AIProviderMalformedResponseError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)
from app.ai.limits import ConversationRateLimiter
from app.ai.mock.provider import MockAIProvider
from app.ai.orchestrator import AIOrchestrator
from app.ai.prompts.assembler import build_prompt_bundle
from app.ai.sanitization import redact_secrets, sanitize_state_data
from app.ai.schemas import (
    AILatencyMetadata,
    AIRequest,
    AIResponse,
    AIToolRequest,
    ConversationContext,
    ConversationTurn,
)
from app.ai.tools.registry import ToolRegistry, ToolSpec
from app.ai.validation import validate_ai_response
from app.bot import responses as bot_text
from app.bot.handlers.base import BotContext
from app.bot.schemas import InternalInboundMessage
from app.bot.state import ConversationState
from app.core.config import Settings
from app.db.session import get_engine
from app.models import Base, Channel
from app.services.contact import ContactService
from app.services.conversation import ConversationService
from app.services.message_processor import MessageProcessingService
from app.services.message_repository import MessageRepository
from app.services.outbound import OutboundMessageService
from app.services.phone_number import PhoneNumberService
from app.whatsapp.mock.provider import MockWhatsAppProvider
from app.whatsapp.schemas import InboundEventKind, WhatsAppInboundEvent
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.conftest import load_fixture


def _ai_settings(**overrides: Any) -> Settings:
    base = {
        "APP_NAME": "WhatsApp Platform Test",
        "ENVIRONMENT": "development",
        "DEBUG": True,
        "LOG_LEVEL": "WARNING",
        "DATABASE_URL": f"sqlite+aiosqlite:///file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared",
        "REDIS_URL": "redis://localhost:6379/0",
        "WHATSAPP_PROVIDER": "mock",
        "WHATSAPP_VERIFY_TOKEN": "test-verify-token",
        "AI_PROVIDER": "mock",
        "AI_MAX_RETRIES": 1,
        "AI_RETRY_BASE_DELAY": 0.01,
        "AI_MAX_USER_MESSAGE_LENGTH": 100,
        "AI_MAX_INPUT_CHARS": 200,
        "AI_MAX_CONTEXT_MESSAGES": 5,
        "AI_MAX_REQUESTS_PER_CONVERSATION": 3,
        "AI_REQUEST_WINDOW_SECONDS": 3600,
    }
    base.update(overrides)
    return Settings(**base)


def _whatsapp_event(**overrides: Any) -> WhatsAppInboundEvent:
    base = {
        "event_id": f"wamid.test.{uuid.uuid4().hex}",
        "message_id": f"wamid.test.{uuid.uuid4().hex}",
        "sender_id": "15559876543",
        "message_type": "text",
        "text": "hello",
        "phone_number_id": "PHONE_NUMBER_ID",
        "kind": InboundEventKind.MESSAGE,
    }
    base.update(overrides)
    return WhatsAppInboundEvent(**base)


def _payload_with_text(text: str, message_id: str | None = None) -> dict[str, Any]:
    payload = copy.deepcopy(load_fixture("text_message.json"))
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    message["text"]["body"] = text
    if message_id:
        message["id"] = message_id
    return payload


@pytest.fixture
def ai_test_settings() -> Settings:
    return _ai_settings()


@pytest.fixture
def mock_ai_provider() -> MockAIProvider:
    return MockAIProvider(response_text="Mock AI reply")


@pytest.fixture
def whatsapp_mock() -> MockWhatsAppProvider:
    return MockWhatsAppProvider()


@pytest.fixture
def outbound_service(
    whatsapp_mock: MockWhatsAppProvider, ai_test_settings: Settings
) -> OutboundMessageService:
    return OutboundMessageService(whatsapp_mock, ai_test_settings)


async def _seed_conversation(session: AsyncSession) -> str:
    phone = await PhoneNumberService(session).resolve("PHONE_NUMBER_ID")
    contact, _ = await ContactService(session).find_or_create(
        phone_number_id=str(phone.id),
        channel=Channel.WHATSAPP,
        channel_user_id="15559876543",
    )
    conversation, _ = await ConversationService(session).find_or_create(
        phone_number_id=phone.id,
        contact=contact,
    )
    await session.commit()
    return str(conversation.id)


@pytest.fixture
async def ai_session_factory(
    ai_test_settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


def test_redact_secrets() -> None:
    text = "api_key=super-secret-token and Bearer abc.def.ghi"
    redacted = redact_secrets(text)
    assert "super-secret-token" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "[REDACTED]" in redacted


def test_sanitize_state_data_excludes_unsafe_keys() -> None:
    data = sanitize_state_data(
        {"demo_name": "Ada", "secret_key": "hidden", "webhook_secret": "x"},
    )
    assert data == {"demo_name": "Ada"}


def test_validate_ai_response_success() -> None:
    response = AIResponse(text="Hello", provider="mock", model="test")
    validated = validate_ai_response(response, max_output_chars=100)
    assert validated.text == "Hello"


def test_validate_ai_response_empty_raises() -> None:
    response = AIResponse(text="   ", provider="mock", model="test")
    with pytest.raises(AIProviderEmptyResponseError):
        validate_ai_response(response, max_output_chars=100)


def test_validate_ai_response_truncates_output() -> None:
    response = AIResponse(text="a" * 20, provider="mock", model="test")
    validated = validate_ai_response(response, max_output_chars=5)
    assert len(validated.text) == 5


def test_prompt_bundle_is_structured() -> None:
    context = ConversationContext(
        conversation_id="conv-1",
        current_state="main_menu",
        state_summary={"demo_name": "Ada"},
        turns=[ConversationTurn(role="user", content="Hi")],
        prompt_version="v1",
    )
    bundle = build_prompt_bundle(context, "What are your hours?")
    assert bundle.system_instructions
    assert bundle.business_rules
    assert "Ada" in bundle.conversation_context
    assert bundle.user_message == "What are your hours?"
    assert bundle.version == "v1"


def test_tool_registry_validation() -> None:
    class EchoInput(BaseModel):
        text: str

    class EchoOutput(BaseModel):
        text: str

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            description="Echo text",
            input_model=EchoInput,
            output_model=EchoOutput,
            timeout_seconds=1.0,
        ),
    )
    assert registry.list_tools() == ["echo"]
    with pytest.raises(AIProviderError):
        registry.validate_tool_request(AIToolRequest(tool_name="missing", arguments={}))


@pytest.mark.asyncio
async def test_mock_provider_successful_response() -> None:
    provider = MockAIProvider(response_text="OK")
    bundle = build_prompt_bundle(
        ConversationContext(
            conversation_id="c1",
            current_state="main_menu",
            prompt_version="v1",
        ),
        "hello",
    )
    request = AIRequest(
        prompt=bundle,
        model=_ai_settings().ai_model,
        max_output_tokens=50,
    )
    response = await provider.generate_response(request)
    assert response.text == "OK"
    assert response.provider == "mock"


@pytest.mark.asyncio
async def test_orchestrator_successful_response(
    ai_test_settings: Settings,
    mock_ai_provider: MockAIProvider,
) -> None:
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(ai_test_settings, mock_ai_provider, builder)

        response = await orchestrator.generate_reply(
            conversation_id=str(uuid.uuid4()),
            user_message="Tell me about your business",
            current_state="main_menu",
            state_data={},
        )
        assert response.text == "Mock AI reply"
        assert response.fallback_used is False
        assert mock_ai_provider.call_count == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_orchestrator_provider_failure_fallback(
    ai_test_settings: Settings,
) -> None:
    failing_provider = MockAIProvider(fail_with=AIProviderServerError("down"))
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(ai_test_settings, failing_provider, builder)

        response = await orchestrator.generate_reply(
            conversation_id=str(uuid.uuid4()),
            user_message="hello",
            current_state="main_menu",
            state_data={},
        )
        assert response.fallback_used is True
        assert bot_text.AI_UNAVAILABLE in response.text
    await engine.dispose()


@pytest.mark.asyncio
async def test_orchestrator_retries_transient_failure(ai_test_settings: Settings) -> None:
    provider = MockAIProvider()
    call_count = 0
    original_generate = provider.generate_response

    async def flaky_generate(request: AIRequest) -> AIResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise AIProviderTimeoutError("timeout")
        return await original_generate(request)

    provider.generate_response = flaky_generate  # type: ignore[method-assign]

    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(ai_test_settings, provider, builder)
        response = await orchestrator.generate_reply(
            conversation_id=str(uuid.uuid4()),
            user_message="hello",
            current_state="main_menu",
            state_data={},
        )
        assert response.fallback_used is False
        assert call_count == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_orchestrator_input_limit_fallback(ai_test_settings: Settings) -> None:
    provider = MockAIProvider()
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(ai_test_settings, provider, builder)
        response = await orchestrator.generate_reply(
            conversation_id=str(uuid.uuid4()),
            user_message="x" * (ai_test_settings.ai_max_user_message_length + 1),
            current_state="main_menu",
            state_data={},
        )
        assert response.fallback_used is True
        assert bot_text.AI_INPUT_TOO_LONG in response.text
        assert provider.call_count == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_orchestrator_abuse_limit_fallback(ai_test_settings: Settings) -> None:
    provider = MockAIProvider()
    limiter = ConversationRateLimiter(
        max_requests=ai_test_settings.ai_max_requests_per_conversation,
        window_seconds=ai_test_settings.ai_request_window_seconds,
    )
    conversation_id = str(uuid.uuid4())

    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(
            ai_test_settings,
            provider,
            builder,
            rate_limiter=limiter,
        )

        for _ in range(ai_test_settings.ai_max_requests_per_conversation):
            response = await orchestrator.generate_reply(
                conversation_id=conversation_id,
                user_message="hello",
                current_state="main_menu",
                state_data={},
            )
            assert response.fallback_used is False

        blocked = await orchestrator.generate_reply(
            conversation_id=conversation_id,
            user_message="hello again",
            current_state="main_menu",
            state_data={},
        )
        assert blocked.fallback_used is True
        assert bot_text.AI_RATE_LIMITED in blocked.text
    await engine.dispose()


@pytest.mark.asyncio
async def test_context_truncation(ai_test_settings: Settings) -> None:
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        repo = MessageRepository(session)
        conversation_id = await _seed_conversation(session)

        for index in range(6):
            await repo.register_inbound(
                conversation_id=conversation_id,
                wamid=f"wamid.{index}.{uuid.uuid4().hex}",
                message_type="text",
                payload={"text": f"message-{index}-" + ("x" * 50)},
            )
        await session.commit()

        builder = ConversationContextBuilder(repo, ai_test_settings)
        context = await builder.build(
            conversation_id=conversation_id,
            current_state="main_menu",
            state_data={},
            user_message="latest",
        )
        total_chars = sum(len(turn.content) for turn in context.turns)
        assert total_chars <= ai_test_settings.ai_max_input_chars
        assert len(context.turns) <= ai_test_settings.ai_max_context_messages
    await engine.dispose()


@pytest.mark.asyncio
async def test_context_excludes_secrets(ai_test_settings: Settings) -> None:
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        repo = MessageRepository(session)
        conversation_id = await _seed_conversation(session)
        await repo.register_inbound(
            conversation_id=conversation_id,
            wamid="wamid.secret",
            message_type="text",
            payload={"text": "token=abc123", "provider_metadata": {"secret": "hidden"}},
        )
        await session.commit()

        builder = ConversationContextBuilder(repo, ai_test_settings)
        context = await builder.build(
            conversation_id=conversation_id,
            current_state="main_menu",
            state_data={"secret_key": "hidden"},
            user_message="hello",
        )
        joined = " ".join(turn.content for turn in context.turns)
        assert "abc123" not in joined
        assert "hidden" not in context.state_summary
    await engine.dispose()


@pytest.mark.asyncio
async def test_deterministic_commands_bypass_ai(
    ai_session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_ai_provider: MockAIProvider,
    ai_test_settings: Settings,
) -> None:
    async with ai_session_factory() as session:
        engine = create_bot_engine(ai_test_settings, session, ai_provider=mock_ai_provider)
        processor = MessageProcessingService(session, outbound_service, bot_engine=engine)
        for command in ("/start", "/help", "/menu"):
            await processor.process_inbound_event(_whatsapp_event(text=command))
    assert mock_ai_provider.call_count == 0


@pytest.mark.asyncio
async def test_normal_text_reaches_ai(
    ai_session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_ai_provider: MockAIProvider,
    ai_test_settings: Settings,
    whatsapp_mock: MockWhatsAppProvider,
) -> None:
    async with ai_session_factory() as session:
        engine = create_bot_engine(ai_test_settings, session, ai_provider=mock_ai_provider)
        processor = MessageProcessingService(session, outbound_service, bot_engine=engine)
        await processor.process_inbound_event(_whatsapp_event(text="What are your hours?"))

    assert mock_ai_provider.call_count == 1
    assert "Mock AI reply" in whatsapp_mock.outbound_messages[-1].text


@pytest.mark.asyncio
async def test_ai_failure_triggers_fallback_in_pipeline(
    ai_session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    ai_test_settings: Settings,
    whatsapp_mock: MockWhatsAppProvider,
) -> None:
    failing_provider = MockAIProvider(fail_with=AIProviderServerError("down"))
    async with ai_session_factory() as session:
        engine = create_bot_engine(ai_test_settings, session, ai_provider=failing_provider)
        processor = MessageProcessingService(session, outbound_service, bot_engine=engine)
        await processor.process_inbound_event(_whatsapp_event(text="Need help"))

    assert bot_text.AI_UNAVAILABLE in whatsapp_mock.outbound_messages[-1].text


@pytest.mark.asyncio
async def test_ai_integration_message_to_bot_response(
    ai_session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    ai_test_settings: Settings,
) -> None:
    provider = MockAIProvider(response_text="Integration AI response")
    async with ai_session_factory() as session:
        bot_engine = create_bot_engine(ai_test_settings, session, ai_provider=provider)
        processor = MessageProcessingService(session, outbound_service, bot_engine=bot_engine)
        result = await processor.process_inbound_event(
            _whatsapp_event(text="Tell me more about your services"),
        )
        assert result == "processed"

    assert provider.call_count == 1
    assert provider.last_request is not None
    assert provider.last_request.prompt.user_message == "Tell me more about your services"


@pytest.mark.asyncio
async def test_disabled_ai_uses_deterministic_fallback(
    ai_session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    whatsapp_mock: MockWhatsAppProvider,
) -> None:
    async with ai_session_factory() as session:
        processor = MessageProcessingService(
            session,
            outbound_service,
            bot_engine=create_bot_engine_without_ai(),
        )
        await processor.process_inbound_event(_whatsapp_event(text="random gibberish"))

    assert "didn't understand" in whatsapp_mock.outbound_messages[-1].text.lower()


@pytest.mark.asyncio
async def test_malformed_provider_response_fallback(ai_test_settings: Settings) -> None:
    provider = MockAIProvider(response_text="")
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(ai_test_settings, provider, builder)
        response = await orchestrator.generate_reply(
            conversation_id=str(uuid.uuid4()),
            user_message="hello",
            current_state="main_menu",
            state_data={},
        )
        assert response.fallback_used is True
    await engine.dispose()


def test_validate_malformed_metadata() -> None:
    response = AIResponse(text="hello", provider="", model="")
    with pytest.raises(AIProviderMalformedResponseError):
        validate_ai_response(response, max_output_chars=100)


@pytest.mark.asyncio
async def test_rate_limit_error_is_retried(ai_test_settings: Settings) -> None:
    provider = MockAIProvider()
    attempts = 0

    async def rate_limited_then_success(request: Any) -> AIResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AIProviderRateLimitError(retry_after=0.01)
        return AIResponse(
            text="recovered",
            provider="mock",
            model="test",
            latency=AILatencyMetadata(latency_ms=1.0),
        )

    provider.generate_response = rate_limited_then_success  # type: ignore[method-assign]

    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        builder = ConversationContextBuilder(MessageRepository(session), ai_test_settings)
        orchestrator = AIOrchestrator(ai_test_settings, provider, builder)
        response = await orchestrator.generate_reply(
            conversation_id=str(uuid.uuid4()),
            user_message="hello",
            current_state="main_menu",
            state_data={},
        )
        assert response.text == "recovered"
        assert attempts == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_bot_router_selects_ai_handler_for_plain_text(
    ai_test_settings: Settings,
    mock_ai_provider: MockAIProvider,
) -> None:
    engine = get_engine(str(ai_test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        bot_engine = create_bot_engine(ai_test_settings, session, ai_provider=mock_ai_provider)
        context = BotContext(
            conversation_id=str(uuid.uuid4()),
            contact_id=str(uuid.uuid4()),
            channel_user_id="15550001111",
            current_state=ConversationState.MAIN_MENU,
            text="plain question",
        )
        responses, _, _ = await bot_engine.process(
            InternalInboundMessage(
                event_id="evt",
                message_id="wamid.1",
                sender_id="15550001111",
                channel_user_id="15550001111",
                message_type="text",
                text="plain question",
                phone_number_id="PHONE_NUMBER_ID",
            ),
            conversation_id=context.conversation_id,
            contact_id=context.contact_id,
            current_state=ConversationState.MAIN_MENU,
            state_data={},
        )
        assert mock_ai_provider.call_count == 1
        assert responses[0].text == "Mock AI reply"
    await engine.dispose()
