"""One-off local verification of Ollama through the full bot AI pipeline."""

from __future__ import annotations

import asyncio
import sys
import uuid

from app.ai.bot_factory import create_bot_engine
from app.ai.factory import create_ai_provider
from app.bot import responses as bot_text
from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.models import Base
from app.services.message_processor import MessageProcessingService
from app.services.outbound import OutboundMessageService
from app.whatsapp.mock.provider import MockWhatsAppProvider
from app.whatsapp.schemas import InboundEventKind, WhatsAppInboundEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def main() -> int:
    settings = get_settings()
    if settings.ai_provider != "ollama":
        print(f"ERROR: AI_PROVIDER must be ollama (got {settings.ai_provider})")
        return 1

    engine = get_engine(str(settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    whatsapp = MockWhatsAppProvider()
    outbound = OutboundMessageService(whatsapp, settings)

    print(f"AI provider: {settings.ai_provider}")
    print(f"Ollama URL: {settings.ollama_base_url}")
    print(f"Ollama model: {settings.ollama_model}")

    async with factory() as session:
        bot_engine = create_bot_engine(settings, session, ai_provider=create_ai_provider(settings))
        processor = MessageProcessingService(session, outbound, bot_engine=bot_engine)

        # Commands must bypass AI
        for command in ("/start", "/help", "/menu"):
            event = WhatsAppInboundEvent(
                event_id=f"wamid.cmd.{uuid.uuid4().hex}",
                message_id=f"wamid.cmd.{uuid.uuid4().hex}",
                sender_id="15559876543",
                message_type="text",
                text=command,
                phone_number_id="PHONE_NUMBER_ID",
                kind=InboundEventKind.MESSAGE,
            )
            result = await processor.process_inbound_event(event)
            reply = whatsapp.outbound_messages[-1].text
            print(f"COMMAND {command}: status={result}, reply_preview={reply[:60]!r}...")
            if command == "/start" and bot_text.WELCOME not in reply:
                print("ERROR: /start did not return welcome message")
                return 1

        before_ai = len(whatsapp.outbound_messages)

        # Natural language through full pipeline
        nl_event = WhatsAppInboundEvent(
            event_id=f"wamid.nl.{uuid.uuid4().hex}",
            message_id=f"wamid.nl.{uuid.uuid4().hex}",
            sender_id="15559876543",
            message_type="text",
            text="Reply with exactly: PIPELINE OLLAMA OK",
            phone_number_id="PHONE_NUMBER_ID",
            kind=InboundEventKind.MESSAGE,
        )
        nl_result = await processor.process_inbound_event(nl_event)
        nl_reply = whatsapp.outbound_messages[-1].text
        print(f"NATURAL LANGUAGE: status={nl_result}")
        print(f"NATURAL LANGUAGE reply: {nl_reply!r}")

        if nl_result != "processed":
            print("ERROR: natural language message was not processed")
            return 1
        if len(whatsapp.outbound_messages) <= before_ai:
            print("ERROR: no outbound reply for natural language message")
            return 1

    # Failure fallback with unreachable Ollama
    bad_settings = settings.model_copy(
        update={"ollama_base_url": "http://127.0.0.1:59999"},
    )
    async with factory() as session:
        bot_engine = create_bot_engine(
            bad_settings,
            session,
            ai_provider=create_ai_provider(bad_settings),
        )
        processor = MessageProcessingService(session, outbound, bot_engine=bot_engine)
        fail_event = WhatsAppInboundEvent(
            event_id=f"wamid.fail.{uuid.uuid4().hex}",
            message_id=f"wamid.fail.{uuid.uuid4().hex}",
            sender_id="15559876543",
            message_type="text",
            text="This should trigger fallback",
            phone_number_id="PHONE_NUMBER_ID",
            kind=InboundEventKind.MESSAGE,
        )
        fail_result = await processor.process_inbound_event(fail_event)
        fail_reply = whatsapp.outbound_messages[-1].text
        print(f"FAILURE CASE: status={fail_result}, reply={fail_reply!r}")
        if bot_text.AI_UNAVAILABLE not in fail_reply:
            print("ERROR: fallback message not returned when Ollama unreachable")
            return 1

    await engine.dispose()
    print("PIPELINE VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
