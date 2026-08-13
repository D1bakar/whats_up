import asyncio
from typing import Any

from app.core.logging import get_logger
from app.models.webhook_event import WebhookEvent, WebhookProcessingStatus
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

TERMINAL_STATUSES = frozenset(
    {
        WebhookProcessingStatus.PROCESSED,
        WebhookProcessingStatus.UNSUPPORTED,
        WebhookProcessingStatus.DUPLICATE,
    },
)


class WebhookIdempotencyService:
    """Persistent duplicate-event protection using database unique constraints."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def should_process(event: WebhookEvent) -> bool:
        return event.processing_status not in TERMINAL_STATUSES

    async def register(
        self,
        event_id: str,
        *,
        wamid: str | None,
        raw_payload: dict[str, Any],
        status: WebhookProcessingStatus = WebhookProcessingStatus.PENDING,
    ) -> tuple[WebhookEvent, bool]:
        """Register an event. Returns (event, is_new) where is_new means freshly inserted."""

        dialect_name = self._session.bind.dialect.name if self._session.bind else ""

        if dialect_name == "postgresql":
            return await self._register_postgresql(
                event_id,
                wamid=wamid,
                raw_payload=raw_payload,
                status=status,
            )

        return await self._register_with_constraint(
            event_id,
            wamid=wamid,
            raw_payload=raw_payload,
            status=status,
        )

    async def _register_postgresql(
        self,
        event_id: str,
        *,
        wamid: str | None,
        raw_payload: dict[str, Any],
        status: WebhookProcessingStatus,
    ) -> tuple[WebhookEvent, bool]:
        stmt = (
            insert(WebhookEvent)
            .values(
                event_id=event_id,
                wamid=wamid,
                raw_payload=raw_payload,
                processing_status=status,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
            .returning(WebhookEvent)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        inserted = result.scalar_one_or_none()
        if inserted is not None:
            await self._session.refresh(inserted)
            return inserted, True

        existing = await self._get_by_event_id(event_id)
        if existing is None:
            raise RuntimeError(f"Failed to resolve duplicate event_id={event_id}")
        logger.info(
            "duplicate_event_registered",
            event_id=event_id,
            wamid=wamid,
            status=existing.processing_status.value,
        )
        return existing, False

    async def _register_with_constraint(
        self,
        event_id: str,
        *,
        wamid: str | None,
        raw_payload: dict[str, Any],
        status: WebhookProcessingStatus,
    ) -> tuple[WebhookEvent, bool]:
        event = WebhookEvent(
            event_id=event_id,
            wamid=wamid,
            raw_payload=raw_payload,
            processing_status=status,
        )
        self._session.add(event)

        try:
            await self._session.commit()
            return event, True
        except IntegrityError:
            await self._session.rollback()
            for _ in range(5):
                existing = await self._get_by_event_id(event_id)
                if existing is not None:
                    logger.info(
                        "duplicate_event_registered",
                        event_id=event_id,
                        wamid=wamid,
                        status=existing.processing_status.value,
                    )
                    return existing, False
                await asyncio.sleep(0.01)
            raise

    async def mark_processed(
        self,
        event: WebhookEvent,
        status: WebhookProcessingStatus = WebhookProcessingStatus.PROCESSED,
    ) -> None:
        event.processing_status = status
        await self._session.commit()

    async def mark_failed(self, event: WebhookEvent) -> None:
        event.processing_status = WebhookProcessingStatus.FAILED
        await self._session.commit()

    async def _get_by_event_id(self, event_id: str) -> WebhookEvent | None:
        result = await self._session.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id),
        )
        return result.scalar_one_or_none()
