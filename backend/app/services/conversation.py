from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.bot.state import ConversationState
from app.core.logging import get_logger
from app.models import Contact, Conversation, ConversationSession, ConversationStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)

WHATSAPP_SESSION_WINDOW = timedelta(hours=24)


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create(
        self,
        *,
        phone_number_id: UUID,
        contact: Contact,
        message_timestamp: datetime | None = None,
    ) -> tuple[Conversation, bool]:
        result = await self._session.execute(
            select(Conversation)
            .options(selectinload(Conversation.session))
            .where(
                Conversation.phone_number_id == phone_number_id,
                Conversation.contact_id == contact.id,
            ),
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self._touch(existing, message_timestamp)
            logger.info("conversation_resolved", conversation_id=str(existing.id), is_new=False)
            return existing, False

        now = message_timestamp or datetime.now(tz=UTC)
        conversation = Conversation(
            phone_number_id=phone_number_id,
            contact_id=contact.id,
            status=ConversationStatus.ACTIVE,
            last_message_at=now,
            window_expires_at=now + WHATSAPP_SESSION_WINDOW,
        )
        self._session.add(conversation)
        await self._session.flush()

        session_row = ConversationSession(
            conversation_id=conversation.id,
            current_state=ConversationState.MAIN_MENU.value,
            state_data={},
        )
        self._session.add(session_row)
        await self._session.flush()
        await self._session.refresh(conversation, attribute_names=["session"])

        logger.info("conversation_resolved", conversation_id=str(conversation.id), is_new=True)
        return conversation, True

    async def get_session_state(
        self,
        conversation: Conversation,
    ) -> tuple[ConversationState, dict[str, object]]:
        if conversation.session is None:
            session_row = ConversationSession(
                conversation_id=conversation.id,
                current_state=ConversationState.MAIN_MENU.value,
                state_data={},
            )
            self._session.add(session_row)
            await self._session.flush()
            conversation.session = session_row

        state = ConversationState(conversation.session.current_state)
        return state, dict(conversation.session.state_data)

    async def persist_session_state(
        self,
        conversation: Conversation,
        *,
        current_state: ConversationState,
        state_data: dict[str, object],
    ) -> None:
        if conversation.session is None:
            session_row = ConversationSession(
                conversation_id=conversation.id,
                current_state=current_state.value,
                state_data=state_data,
            )
            self._session.add(session_row)
            conversation.session = session_row
        else:
            conversation.session.current_state = current_state.value
            conversation.session.state_data = state_data

    async def _touch(
        self,
        conversation: Conversation,
        message_timestamp: datetime | None,
    ) -> None:
        now = message_timestamp or datetime.now(tz=UTC)
        conversation.last_message_at = now
        conversation.window_expires_at = now + WHATSAPP_SESSION_WINDOW
        if conversation.status == ConversationStatus.CLOSED:
            conversation.status = ConversationStatus.ACTIVE
