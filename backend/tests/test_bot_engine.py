import copy
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.bot import responses as bot_text
from app.bot.engine import BotEngine
from app.bot.exceptions import StateTransitionError
from app.bot.handlers.base import BotContext, HandlerResult
from app.bot.router import BotRouter, CommandDefinition, CommandRegistry
from app.bot.schemas import InternalInboundMessage
from app.bot.state import ConversationState, ConversationStateMachine
from app.core.config import Settings
from app.db.session import get_engine
from app.models import (
    Contact,
    Conversation,
    ConversationSession,
    Message,
    MessageDirection,
    MessageProcessingStatus,
)
from app.services.message_processor import MessageProcessingService
from app.services.message_repository import MessageRepository
from app.services.outbound import OutboundMessageService
from app.whatsapp.exceptions import ProviderPermanentFailureError
from app.whatsapp.mock.provider import MockWhatsAppProvider
from app.whatsapp.schemas import InboundEventKind, WhatsAppInboundEvent
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.conftest import load_fixture


def _internal_message(**overrides: Any) -> InternalInboundMessage:
    base = {
        "event_id": "wamid.test.event",
        "message_id": f"wamid.test.{uuid.uuid4().hex}",
        "sender_id": "15559876543",
        "channel_user_id": "15559876543",
        "message_type": "text",
        "text": "hello",
        "phone_number_id": "PHONE_NUMBER_ID",
    }
    base.update(overrides)
    return InternalInboundMessage(**base)


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
async def session_factory(test_settings: Settings):
    engine = get_engine(str(test_settings.database_url))
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.fixture
def mock_provider() -> MockWhatsAppProvider:
    return MockWhatsAppProvider()


@pytest.fixture
def outbound_service(
    mock_provider: MockWhatsAppProvider, test_settings: Settings
) -> OutboundMessageService:
    return OutboundMessageService(mock_provider, test_settings)


@pytest.mark.asyncio
async def test_command_start(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        result = await processor.process_inbound_event(_whatsapp_event(text="/start"))
        assert result == "processed"

    async with session_factory() as session:
        sess = (await session.execute(select(ConversationSession))).scalar_one()
        assert sess.current_state == ConversationState.MAIN_MENU.value


@pytest.mark.asyncio
async def test_command_help_without_slash(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="help"))

    assert bot_text.HELP in mock_provider.outbound_messages[-1].text


@pytest.mark.asyncio
async def test_command_menu(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="/menu"))

    assert bot_text.MENU in mock_provider.outbound_messages[-1].text


@pytest.mark.asyncio
async def test_unknown_command(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="/unknown"))

    assert "Unknown command" in mock_provider.outbound_messages[-1].text


@pytest.mark.asyncio
async def test_default_text_fallback(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="random gibberish"))

    assert "didn't understand" in mock_provider.outbound_messages[-1].text.lower()


@pytest.mark.asyncio
async def test_new_user_creates_contact_and_conversation(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="/start"))

    async with session_factory() as session:
        contacts = (await session.execute(select(Contact))).scalars().all()
        conversations = (await session.execute(select(Conversation))).scalars().all()
        assert len(contacts) == 1
        assert len(conversations) == 1
        assert contacts[0].channel_user_id == "15559876543"


@pytest.mark.asyncio
async def test_existing_user_reuses_conversation(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
) -> None:
    event = _whatsapp_event(text="/start")
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(event)

    second = _whatsapp_event(text="/help", message_id=f"wamid.second.{uuid.uuid4().hex}")
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(second)

    async with session_factory() as session:
        conversations = (await session.execute(select(Conversation))).scalars().all()
        contacts = (await session.execute(select(Contact))).scalars().all()
        assert len(conversations) == 1
        assert len(contacts) == 1


@pytest.mark.asyncio
async def test_state_transition_demo_flow(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="demo"))

    async with session_factory() as session:
        sess = (await session.execute(select(ConversationSession))).scalar_one()
        assert sess.current_state == ConversationState.DEMO_FLOW.value

    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(
            _whatsapp_event(text="Alice", message_id=f"wamid.demo.{uuid.uuid4().hex}"),
        )

    async with session_factory() as session:
        sess = (await session.execute(select(ConversationSession))).scalar_one()
        assert sess.current_state == ConversationState.DEMO_CONFIRMATION.value
        assert sess.state_data.get("demo_name") == "Alice"


@pytest.mark.asyncio
async def test_invalid_state_transition_raises() -> None:
    machine = ConversationStateMachine(ConversationState.MAIN_MENU)
    with pytest.raises(StateTransitionError):
        machine.transition_to(ConversationState.DEMO_CONFIRMATION)


@pytest.mark.asyncio
async def test_duplicate_inbound_message_skips_bot(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    message_id = f"wamid.duplicate.{uuid.uuid4().hex}"
    event = _whatsapp_event(text="/start", message_id=message_id)

    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        first = await processor.process_inbound_event(event)
        assert first == "processed"

    assert len(mock_provider.outbound_messages) == 1

    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        second = await processor.process_inbound_event(event)
        assert second == "duplicate"

    assert len(mock_provider.outbound_messages) == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_message_processing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Duplicate wamid registration is idempotent across separate sessions."""

    async with session_factory() as session:
        from app.models import Channel
        from app.services.contact import ContactService
        from app.services.conversation import ConversationService
        from app.services.phone_number import PhoneNumberService

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
        conversation_id = str(conversation.id)

    wamid = f"wamid.concurrent.{uuid.uuid4().hex}"

    async with session_factory() as session:
        repo = MessageRepository(session)
        _, is_new_first = await repo.register_inbound(
            conversation_id=conversation_id,
            wamid=wamid,
            message_type="text",
            payload={"text": "/start"},
        )

    async with session_factory() as session:
        repo = MessageRepository(session)
        _, is_new_second = await repo.register_inbound(
            conversation_id=conversation_id,
            wamid=wamid,
            message_type="text",
            payload={"text": "/start"},
        )

    assert is_new_first is True
    assert is_new_second is False

    async with session_factory() as session:
        messages = (
            (await session.execute(select(Message).where(Message.wamid == wamid))).scalars().all()
        )
        assert len(messages) == 1


@pytest.mark.asyncio
async def test_handler_failure_returns_safe_fallback(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    class FailingHandler:
        async def handle(self, context: BotContext) -> HandlerResult:
            raise RuntimeError("boom")

    registry = CommandRegistry()
    registry.register(
        CommandDefinition(
            name="start",
            aliases=(),
            description="fail",
            handler_factory=FailingHandler,
        ),
    )
    router = BotRouter(command_registry=registry)
    engine = BotEngine(router=router)

    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service, bot_engine=engine)
        result = await processor.process_inbound_event(_whatsapp_event(text="/start"))
        assert result == "processed"

    assert "didn't understand" in mock_provider.outbound_messages[-1].text.lower()


@pytest.mark.asyncio
async def test_outbound_provider_failure_marks_message_failed(
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    failing_provider = MockWhatsAppProvider()
    failing_provider.send_message = AsyncMock(  # type: ignore[method-assign]
        side_effect=ProviderPermanentFailureError("send failed"),
    )
    outbound = OutboundMessageService(failing_provider, test_settings)

    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound)
        with pytest.raises(ProviderPermanentFailureError):
            await processor.process_inbound_event(_whatsapp_event(text="/help"))

    async with session_factory() as session:
        outbound_msgs = (
            (
                await session.execute(
                    select(Message).where(Message.direction == MessageDirection.OUTBOUND),
                )
            )
            .scalars()
            .all()
        )
        assert len(outbound_msgs) == 1
        assert outbound_msgs[0].processing_status == MessageProcessingStatus.FAILED


@pytest.mark.asyncio
async def test_full_webhook_pipeline_with_bot(
    client: AsyncClient,
    mock_provider: MockWhatsAppProvider,
) -> None:
    payload = _payload_with_text("/start")
    response = await client.post("/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert bot_text.WELCOME in mock_provider.outbound_messages[0].text


@pytest.mark.asyncio
async def test_webhook_duplicate_protection_end_to_end(client: AsyncClient) -> None:
    payload = _payload_with_text("/help")
    first = await client.post("/webhooks/whatsapp", json=payload)
    second = await client.post("/webhooks/whatsapp", json=payload)
    assert first.json()["accepted"] == 1
    assert second.json()["duplicates"] == 1


@pytest.mark.asyncio
async def test_persist_inbound_and_outbound_messages(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        await processor.process_inbound_event(_whatsapp_event(text="/menu"))

    async with session_factory() as session:
        messages = (await session.execute(select(Message))).scalars().all()
        inbound = [m for m in messages if m.direction == MessageDirection.INBOUND]
        outbound = [m for m in messages if m.direction == MessageDirection.OUTBOUND]
        assert len(inbound) == 1
        assert len(outbound) == 1
        assert inbound[0].processing_status == MessageProcessingStatus.PROCESSED
        assert outbound[0].wamid is not None


@pytest.mark.asyncio
async def test_message_repository_idempotency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        from app.models import Channel
        from app.services.contact import ContactService
        from app.services.conversation import ConversationService
        from app.services.phone_number import PhoneNumberService

        phone_svc = PhoneNumberService(session)
        phone = await phone_svc.resolve("PHONE_NUMBER_ID")
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

        repo = MessageRepository(session)
        first, is_new_first = await repo.register_inbound(
            conversation_id=str(conversation.id),
            wamid="wamid.repo.test",
            message_type="text",
            payload={"text": "hi"},
        )
        second, is_new_second = await repo.register_inbound(
            conversation_id=str(conversation.id),
            wamid="wamid.repo.test",
            message_type="text",
            payload={"text": "hi"},
        )

        assert is_new_first is True
        assert is_new_second is False
        assert first.id == second.id


@pytest.mark.asyncio
async def test_bot_engine_processes_internal_message() -> None:
    engine = BotEngine()
    responses, state, _data = await engine.process(
        _internal_message(text="/help"),
        conversation_id=str(uuid.uuid4()),
        contact_id=str(uuid.uuid4()),
        current_state=ConversationState.MAIN_MENU,
        state_data={},
    )
    assert responses[0].text == bot_text.HELP
    assert state == ConversationState.MAIN_MENU


@pytest.mark.asyncio
async def test_unsupported_message_type_via_webhook(client: AsyncClient) -> None:
    payload = load_fixture("image_message.json")
    response = await client.post("/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
    assert response.json()["unsupported"] == 1


@pytest.mark.asyncio
async def test_malformed_event_missing_identity(
    session_factory: async_sessionmaker[AsyncSession],
    outbound_service: OutboundMessageService,
    mock_provider: MockWhatsAppProvider,
) -> None:
    async with session_factory() as session:
        processor = MessageProcessingService(session, outbound_service)
        result = await processor.process_inbound_event(
            WhatsAppInboundEvent(
                event_id="evt-no-sender",
                message_id="wamid.no.sender",
                sender_id=None,
                message_type="text",
                text="hello",
                phone_number_id="PHONE_NUMBER_ID",
                kind=InboundEventKind.MESSAGE,
            ),
        )
        assert result == "ignored"
        assert len(mock_provider.outbound_messages) == 0
