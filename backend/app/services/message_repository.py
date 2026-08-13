import asyncio
from typing import Any

from app.core.logging import get_logger
from app.models import (
    Message,
    MessageDeliveryStatus,
    MessageDirection,
    MessageProcessingStatus,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

TERMINAL_PROCESSING_STATUSES = frozenset(
    {
        MessageProcessingStatus.PROCESSED,
        MessageProcessingStatus.IGNORED,
    },
)


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_inbound(
        self,
        *,
        conversation_id: str,
        wamid: str,
        message_type: str,
        payload: dict[str, Any],
        provider_metadata: dict[str, Any] | None = None,
    ) -> tuple[Message, bool]:
        """Register inbound message. Returns (message, is_new)."""

        from uuid import UUID

        dialect_name = self._session.bind.dialect.name if self._session.bind else ""

        values = {
            "conversation_id": UUID(conversation_id),
            "wamid": wamid,
            "direction": MessageDirection.INBOUND,
            "message_type": message_type,
            "payload": payload,
            "processing_status": MessageProcessingStatus.RECEIVED,
            "provider_metadata": provider_metadata or {},
        }

        if dialect_name == "postgresql":
            result = await self._register_inbound_postgresql(values, wamid)
        else:
            result = await self._register_inbound_with_constraint(values, wamid)

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._get_by_wamid(wamid)
            if existing is None:
                raise
            logger.info(
                "duplicate_message_ignored",
                wamid=wamid,
                processing_status=existing.processing_status.value,
            )
            return existing, False

        return result

    async def _register_inbound_postgresql(
        self,
        values: dict[str, Any],
        wamid: str,
    ) -> tuple[Message, bool]:
        stmt = (
            insert(Message)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["wamid"])
            .returning(Message)
        )
        result = await self._session.execute(stmt)
        inserted = result.scalar_one_or_none()
        if inserted is not None:
            await self._session.refresh(inserted)
            return inserted, True

        existing = await self._get_by_wamid(wamid)
        if existing is None:
            raise RuntimeError(f"Failed to resolve duplicate wamid={wamid}")
        logger.info(
            "duplicate_message_ignored",
            wamid=wamid,
            processing_status=existing.processing_status.value,
        )
        return existing, False

    async def _register_inbound_with_constraint(
        self,
        values: dict[str, Any],
        wamid: str,
    ) -> tuple[Message, bool]:
        for _ in range(5):
            existing = await self._get_by_wamid(wamid)
            if existing is not None:
                logger.info(
                    "duplicate_message_ignored",
                    wamid=wamid,
                    processing_status=existing.processing_status.value,
                )
                return existing, False

            message = Message(**values)
            self._session.add(message)

            try:
                async with self._session.begin_nested():
                    await self._session.flush()
                return message, True
            except IntegrityError:
                await self._session.rollback()
                await asyncio.sleep(0.01)

        existing = await self._get_by_wamid(wamid)
        if existing is not None:
            logger.info(
                "duplicate_message_ignored",
                wamid=wamid,
                processing_status=existing.processing_status.value,
            )
            return existing, False
        raise RuntimeError(f"Failed to resolve duplicate wamid={wamid}")

    @staticmethod
    def should_process(message: Message) -> bool:
        return message.processing_status not in TERMINAL_PROCESSING_STATUSES

    async def mark_processing(self, message: Message) -> None:
        message.processing_status = MessageProcessingStatus.PROCESSING

    async def mark_processed(self, message: Message) -> None:
        message.processing_status = MessageProcessingStatus.PROCESSED

    async def mark_failed(self, message: Message) -> None:
        message.processing_status = MessageProcessingStatus.FAILED

    async def mark_ignored(self, message: Message) -> None:
        message.processing_status = MessageProcessingStatus.IGNORED

    async def create_outbound(
        self,
        *,
        conversation_id: str,
        message_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> Message:
        from uuid import UUID

        message = Message(
            conversation_id=UUID(conversation_id),
            wamid=None,
            direction=MessageDirection.OUTBOUND,
            message_type=message_type,
            payload=payload,
            processing_status=MessageProcessingStatus.PROCESSING,
            delivery_status=MessageDeliveryStatus.PENDING,
            provider_metadata={"idempotency_key": idempotency_key},
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def mark_outbound_sent(
        self,
        message: Message,
        *,
        wamid: str,
        provider_metadata: dict[str, Any] | None = None,
    ) -> None:
        message.wamid = wamid
        message.processing_status = MessageProcessingStatus.PROCESSED
        message.delivery_status = MessageDeliveryStatus.SENT
        if provider_metadata:
            message.provider_metadata = {**message.provider_metadata, **provider_metadata}

    async def mark_outbound_failed(self, message: Message) -> None:
        message.processing_status = MessageProcessingStatus.FAILED
        message.delivery_status = MessageDeliveryStatus.FAILED

    async def get_by_wamid(self, wamid: str) -> Message | None:
        return await self._get_by_wamid(wamid)

    async def _get_by_wamid(self, wamid: str) -> Message | None:
        result = await self._session.execute(select(Message).where(Message.wamid == wamid))
        return result.scalar_one_or_none()
