import asyncio
from typing import Any

from app.core.logging import get_logger
from app.models import BusinessAccount, PhoneNumber
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class PhoneNumberService:
    """Resolves Meta phone_number_id strings to persisted PhoneNumber rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self,
        meta_phone_number_id: str,
        *,
        display_number: str | None = None,
    ) -> PhoneNumber:
        for _ in range(5):
            existing = await self._get_by_meta_id(meta_phone_number_id)
            if existing is not None:
                return existing

            try:
                async with self._session.begin_nested():
                    business = BusinessAccount(
                        meta_waba_id=f"auto-{meta_phone_number_id}",
                        name="Auto-provisioned Account",
                    )
                    self._session.add(business)
                    phone_number = PhoneNumber(
                        business_account=business,
                        meta_phone_number_id=meta_phone_number_id,
                        display_number=display_number or meta_phone_number_id,
                        is_active=True,
                    )
                    self._session.add(phone_number)
                    await self._session.flush()
                logger.info(
                    "phone_number_auto_provisioned",
                    meta_phone_number_id=meta_phone_number_id,
                    phone_number_id=str(phone_number.id),
                )
                return phone_number
            except IntegrityError:
                await asyncio.sleep(0.01)

        existing = await self._get_by_meta_id(meta_phone_number_id)
        if existing is not None:
            return existing
        raise RuntimeError(f"Failed to resolve phone_number_id={meta_phone_number_id}")

    async def _get_by_meta_id(self, meta_phone_number_id: str) -> PhoneNumber | None:
        result = await self._session.execute(
            select(PhoneNumber).where(PhoneNumber.meta_phone_number_id == meta_phone_number_id),
        )
        return result.scalar_one_or_none()

    @staticmethod
    def extract_display_number(metadata: dict[str, Any]) -> str | None:
        return None
