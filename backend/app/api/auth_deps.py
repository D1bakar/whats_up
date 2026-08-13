from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from app.api.deps import get_db
from app.core.config import Settings
from app.core.security import decode_access_token
from app.models import AdminRole, AdminUser
from app.services.admin_auth import AdminAuthService, AuthenticationError, AuthorizationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

_bearer_scheme = HTTPBearer(auto_error=False)

ROLE_RANK: dict[AdminRole, int] = {
    AdminRole.VIEWER: 0,
    AdminRole.OPERATOR: 1,
    AdminRole.ADMIN: 2,
}


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Missing or invalid authorization header")

    settings: Settings = request.app.state.settings
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise AuthenticationError("Invalid token subject")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise AuthenticationError("Invalid token subject") from exc

    user = await AdminAuthService(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


def require_role(min_role: AdminRole) -> Callable[..., object]:
    async def _dependency(
        current_user: Annotated[AdminUser, Depends(get_current_user)],
    ) -> AdminUser:
        if ROLE_RANK[current_user.role] < ROLE_RANK[min_role]:
            raise AuthorizationError()
        return current_user

    return _dependency


RequireOperator = Annotated[AdminUser, Depends(require_role(AdminRole.OPERATOR))]
RequireViewer = Annotated[AdminUser, Depends(require_role(AdminRole.VIEWER))]
