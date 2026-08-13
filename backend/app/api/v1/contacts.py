from uuid import UUID

from app.api.auth_deps import RequireOperator
from app.api.deps import get_db
from app.models import Channel
from app.schemas.admin import ContactResponse
from app.schemas.pagination import PaginatedResponse
from app.services.admin_read import AdminReadService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/contacts", tags=["admin-contacts"])


@router.get("", response_model=PaginatedResponse[ContactResponse], summary="List contacts")
async def list_contacts(
    _: RequireOperator,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    channel: Channel | None = Query(default=None),
) -> PaginatedResponse[ContactResponse]:
    service = AdminReadService(db)
    contacts, total = await service.list_contacts(limit=limit, offset=offset, channel=channel)
    return PaginatedResponse(
        items=[ContactResponse.model_validate(contact, from_attributes=True) for contact in contacts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{contact_id}", response_model=ContactResponse, summary="Get contact detail")
async def get_contact(
    contact_id: UUID,
    _: RequireOperator,
    db: AsyncSession = Depends(get_db),
) -> ContactResponse:
    contact = await AdminReadService(db).get_contact(contact_id)
    return ContactResponse.model_validate(contact, from_attributes=True)
