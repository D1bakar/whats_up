from app.api.auth_deps import RequireOperator
from app.schemas.admin import AdminUserResponse
from fastapi import APIRouter

router = APIRouter(tags=["admin-auth"])


@router.get("/me", response_model=AdminUserResponse, summary="Current admin user")
async def me(current_user: RequireOperator) -> AdminUserResponse:
    return AdminUserResponse.model_validate(current_user, from_attributes=True)
