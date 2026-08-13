from app.core.logging import get_logger
from app.models import Channel, Contact
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ContactService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create(
        self,
        *,
        phone_number_id: str,
        channel: Channel,
        channel_user_id: str,
        display_name: str | None = None,
    ) -> tuple[Contact, bool]:
        from uuid import UUID

        phone_uuid = UUID(phone_number_id)

        result = await self._session.execute(
            select(Contact).where(
                Contact.phone_number_id == phone_uuid,
                Contact.channel == channel,
                Contact.channel_user_id == channel_user_id,
            ),
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if display_name and existing.display_name != display_name:
                existing.display_name = display_name
            logger.info("user_resolved", contact_id=str(existing.id), is_new=False)
            return existing, False

        contact = Contact(
            phone_number_id=phone_uuid,
            channel=channel,
            channel_user_id=channel_user_id,
            display_name=display_name,
        )
        self._session.add(contact)
        await self._session.flush()
        logger.info("user_resolved", contact_id=str(contact.id), is_new=True)
        return contact, True

    @staticmethod
    def extract_display_name(metadata: dict[str, object]) -> str | None:
        contacts = metadata.get("contacts")
        if not isinstance(contacts, list):
            return None
        for item in contacts:
            if not isinstance(item, dict):
                continue
            profile = item.get("profile")
            if isinstance(profile, dict):
                name = profile.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        return None
