from typing import Literal

from app.bot import responses as bot_text
from app.bot.adapters import to_internal_message
from app.bot.engine import BotEngine
from app.bot.exceptions import (
    BotEngineError,
    HandlerExecutionError,
    InvalidInboundMessageError,
)
from app.bot.schemas import BotResponse, BotResponseType
from app.core.logging import get_logger
from app.models import Channel
from app.services.contact import ContactService
from app.services.conversation import ConversationService
from app.services.message_repository import MessageRepository
from app.services.outbound import OutboundMessageService
from app.services.phone_number import PhoneNumberService
from app.whatsapp.exceptions import ProviderPermanentFailureError, ProviderTemporaryFailureError
from app.whatsapp.schemas import InboundEventKind, WhatsAppInboundEvent
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class MessageProcessingService:
    """Orchestrates inbound message processing through the bot engine pipeline."""

    def __init__(
        self,
        session: AsyncSession,
        outbound_service: OutboundMessageService,
        bot_engine: BotEngine | None = None,
    ) -> None:
        self._session = session
        self._outbound = outbound_service
        self._bot = bot_engine or BotEngine()
        self._phone_numbers = PhoneNumberService(session)
        self._contacts = ContactService(session)
        self._conversations = ConversationService(session)
        self._messages = MessageRepository(session)

    async def process_inbound_event(
        self, event: WhatsAppInboundEvent
    ) -> Literal[
        "processed",
        "duplicate",
        "unsupported",
        "ignored",
        "failed",
    ]:
        if event.kind == InboundEventKind.UNSUPPORTED:
            logger.info(
                "unsupported_message_type",
                event_id=event.event_id,
                message_type=event.message_type,
            )
            return "unsupported"

        if event.kind != InboundEventKind.MESSAGE:
            return "ignored"

        try:
            internal = to_internal_message(event)
        except InvalidInboundMessageError as exc:
            logger.warning("invalid_inbound_message", event_id=event.event_id, error=str(exc))
            return "ignored"

        logger.info(
            "message_received",
            event_id=event.event_id,
            message_id=internal.message_id,
            channel_user_id=internal.channel_user_id,
        )

        try:
            phone_number = await self._phone_numbers.resolve(internal.phone_number_id)
            display_name = ContactService.extract_display_name(internal.metadata)
            contact, _ = await self._contacts.find_or_create(
                phone_number_id=str(phone_number.id),
                channel=Channel.WHATSAPP,
                channel_user_id=internal.channel_user_id,
                display_name=display_name,
            )
            conversation, _ = await self._conversations.find_or_create(
                phone_number_id=phone_number.id,
                contact=contact,
                message_timestamp=internal.timestamp,
            )

            inbound, is_new = await self._messages.register_inbound(
                conversation_id=str(conversation.id),
                wamid=internal.message_id,
                message_type=internal.message_type,
                payload={"text": internal.text} if internal.text else {},
                provider_metadata={"event_id": internal.event_id},
            )

            if not is_new and not self._messages.should_process(inbound):
                logger.info(
                    "duplicate_ignored",
                    message_id=internal.message_id,
                    processing_status=inbound.processing_status.value,
                )
                return "duplicate"

            await self._messages.mark_processing(inbound)
            await self._session.commit()
            await self._session.refresh(conversation, attribute_names=["session"])

            current_state, state_data = await self._conversations.get_session_state(conversation)

            if not internal.text:
                bot_responses = [BotResponse(text=bot_text.DEFAULT_FALLBACK)]
                next_state = current_state
                next_data = state_data
            else:
                try:
                    bot_responses, next_state, next_data = await self._bot.process(
                        internal,
                        conversation_id=str(conversation.id),
                        contact_id=str(contact.id),
                        current_state=current_state,
                        state_data=state_data,
                    )
                except HandlerExecutionError:
                    bot_responses = [BotResponse(text=bot_text.DEFAULT_FALLBACK)]
                    next_state = current_state
                    next_data = state_data

            await self._conversations.persist_session_state(
                conversation,
                current_state=next_state,
                state_data=next_data,
            )
            await self._session.commit()

            await self._send_responses(
                internal,
                conversation_id=str(conversation.id),
                channel_user_id=internal.channel_user_id,
                responses=bot_responses,
            )

            inbound_refresh = await self._messages.get_by_wamid(internal.message_id)
            if inbound_refresh is not None:
                await self._messages.mark_processed(inbound_refresh)
            await self._session.commit()

            logger.info(
                "processing_completed",
                event_id=event.event_id,
                message_id=internal.message_id,
                conversation_id=str(conversation.id),
            )
            return "processed"

        except (
            ProviderTemporaryFailureError,
            ProviderPermanentFailureError,
        ) as exc:
            await self._session.rollback()
            inbound_msg = await self._messages.get_by_wamid(event.message_id or "")
            if inbound_msg is not None:
                await self._messages.mark_failed(inbound_msg)
                await self._session.commit()
            logger.error(
                "outbound_provider_failed",
                event_id=event.event_id,
                message_id=event.message_id,
                error=str(exc),
            )
            raise
        except BotEngineError as exc:
            await self._session.rollback()
            logger.error(
                "processing_failed",
                event_id=event.event_id,
                message_id=event.message_id,
                error=str(exc),
            )
            return "failed"
        except Exception:
            await self._session.rollback()
            logger.exception(
                "processing_failed",
                event_id=event.event_id,
                message_id=event.message_id,
            )
            raise

    async def _send_responses(
        self,
        internal_message: object,
        *,
        conversation_id: str,
        channel_user_id: str,
        responses: list[BotResponse],
    ) -> None:
        from app.bot.schemas import InternalInboundMessage

        message = internal_message if isinstance(internal_message, InternalInboundMessage) else None
        event_id = message.event_id if message else "unknown"

        for index, response in enumerate(responses):
            if response.type != BotResponseType.TEXT or not response.text:
                continue

            idempotency_key = f"reply:{event_id}:{index}"
            outbound = await self._messages.create_outbound(
                conversation_id=conversation_id,
                message_type="text",
                payload={"text": response.text},
                idempotency_key=idempotency_key,
            )
            await self._session.commit()

            logger.info(
                "outbound_send_requested",
                conversation_id=conversation_id,
                idempotency_key=idempotency_key,
            )

            try:
                result = await self._outbound.send_text_message(
                    to=channel_user_id,
                    text=response.text,
                    idempotency_key=idempotency_key,
                )
            except Exception:
                await self._messages.mark_outbound_failed(outbound)
                await self._session.commit()
                raise

            await self._messages.mark_outbound_sent(
                outbound,
                wamid=result.message_id,
                provider_metadata={"provider": result.provider},
            )
            await self._session.commit()
