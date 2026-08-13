from uuid import UUID

from app.core.exceptions import APIError
from app.models import Channel, Contact, Conversation, ConversationStatus, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


class NotFoundError(APIError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            code="not_found",
            message=f"{resource} not found",
            status_code=404,
        )


class AdminReadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_conversations(
        self,
        *,
        limit: int,
        offset: int,
        status: ConversationStatus | None = None,
    ) -> tuple[list[Conversation], int]:
        filters = []
        if status is not None:
            filters.append(Conversation.status == status)

        count_stmt = select(func.count()).select_from(Conversation).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Conversation)
            .options(joinedload(Conversation.contact))
            .where(*filters)
            .order_by(
                Conversation.last_message_at.desc().nullslast(),
                Conversation.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_conversation(self, conversation_id: UUID) -> Conversation:
        stmt = (
            select(Conversation)
            .options(
                joinedload(Conversation.contact),
                joinedload(Conversation.session),
            )
            .where(Conversation.id == conversation_id)
        )
        result = await self._session.execute(stmt)
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundError("Conversation")
        return conversation

    async def list_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Message], int]:
        await self.get_conversation(conversation_id)

        filters = [Message.conversation_id == conversation_id]
        count_stmt = select(func.count()).select_from(Message).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Message)
            .where(*filters)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_contacts(
        self,
        *,
        limit: int,
        offset: int,
        channel: Channel | None = None,
    ) -> tuple[list[Contact], int]:
        filters = []
        if channel is not None:
            filters.append(Contact.channel == channel)

        count_stmt = select(func.count()).select_from(Contact).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Contact)
            .where(*filters)
            .order_by(Contact.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_contact(self, contact_id: UUID) -> Contact:
        result = await self._session.execute(select(Contact).where(Contact.id == contact_id))
        contact = result.scalar_one_or_none()
        if contact is None:
            raise NotFoundError("Contact")
        return contact
