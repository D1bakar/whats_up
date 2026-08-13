from uuid import UUID

from app.api.auth_deps import RequireOperator
from app.api.deps import get_db
from app.models import Conversation
from app.models.conversation import ConversationStatus
from app.schemas.admin import (
    ContactSummary,
    ConversationDetail,
    ConversationSessionSummary,
    ConversationSummary,
    MessageResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.services.admin_read import AdminReadService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/conversations", tags=["admin-conversations"])


def _to_summary(conversation: Conversation) -> ConversationSummary:
    contact = conversation.contact
    return ConversationSummary(
        id=conversation.id,
        phone_number_id=conversation.phone_number_id,
        status=conversation.status,
        last_message_at=conversation.last_message_at,
        window_expires_at=conversation.window_expires_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        contact=ContactSummary(
            id=contact.id,
            channel=contact.channel,
            channel_user_id=contact.channel_user_id,
            display_name=contact.display_name,
        ),
    )


def _to_detail(conversation: Conversation) -> ConversationDetail:
    summary = _to_summary(conversation)
    session_summary = None
    if conversation.session is not None:
        session_summary = ConversationSessionSummary(
            current_state=conversation.session.current_state,
            state_data=dict(conversation.session.state_data),
        )
    return ConversationDetail(**summary.model_dump(), session=session_summary)


@router.get("", response_model=PaginatedResponse[ConversationSummary], summary="List conversations")
async def list_conversations(
    _: RequireOperator,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: ConversationStatus | None = Query(default=None),
) -> PaginatedResponse[ConversationSummary]:
    service = AdminReadService(db)
    conversations, total = await service.list_conversations(
        limit=limit,
        offset=offset,
        status=status,
    )
    return PaginatedResponse(
        items=[_to_summary(item) for item in conversations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get conversation detail",
)
async def get_conversation(
    conversation_id: UUID,
    _: RequireOperator,
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conversation = await AdminReadService(db).get_conversation(conversation_id)
    return _to_detail(conversation)


@router.get(
    "/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageResponse],
    summary="List conversation messages",
)
async def list_conversation_messages(
    conversation_id: UUID,
    _: RequireOperator,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[MessageResponse]:
    service = AdminReadService(db)
    messages, total = await service.list_messages(
        conversation_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=[
            MessageResponse.model_validate(message, from_attributes=True) for message in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
