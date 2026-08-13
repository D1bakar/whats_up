from app.api.deps import get_app_settings, get_db
from app.core.config import Settings
from app.core.security import create_access_token
from app.schemas.admin import LoginRequest, TokenResponse
from app.services.admin_auth import AdminAuthService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=TokenResponse, summary="Issue admin access token")
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> TokenResponse:
    user = await AdminAuthService(db).authenticate(body.email, body.password)
    token, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        settings=settings,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)
