from uuid import UUID

from app.core.exceptions import APIError
from app.core.security import verify_password
from app.models import AdminUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuthenticationError(APIError):
    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(
            code="authentication_failed",
            message=message,
            status_code=401,
        )


class AuthorizationError(APIError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            code="forbidden",
            message=message,
            status_code=403,
        )


class AdminAuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authenticate(self, email: str, password: str) -> AdminUser:
        user = await self.get_by_email(email)
        if user is None or not user.is_active:
            raise AuthenticationError()
        if not verify_password(password, user.password_hash):
            raise AuthenticationError()
        return user

    async def get_by_id(self, user_id: UUID) -> AdminUser | None:
        result = await self._session.execute(
            select(AdminUser).where(AdminUser.id == user_id),
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> AdminUser | None:
        result = await self._session.execute(
            select(AdminUser).where(AdminUser.email == email),
        )
        return result.scalar_one_or_none()
