from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models import AdminRole, Channel, ConversationStatus
from app.models.message import (
    MessageDeliveryStatus,
    MessageDirection,
    MessageProcessingStatus,
)
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(ge=1)


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    role: AdminRole
    is_active: bool
    created_at: datetime


class ContactSummary(BaseModel):
    id: UUID
    channel: Channel
    channel_user_id: str
    display_name: str | None


class ContactResponse(BaseModel):
    id: UUID
    phone_number_id: UUID
    channel: Channel
    channel_user_id: str
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class ConversationSessionSummary(BaseModel):
    current_state: str
    state_data: dict[str, object]


class ConversationSummary(BaseModel):
    id: UUID
    phone_number_id: UUID
    status: ConversationStatus
    last_message_at: datetime | None
    window_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    contact: ContactSummary


class ConversationDetail(ConversationSummary):
    session: ConversationSessionSummary | None = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    wamid: str | None
    direction: MessageDirection
    message_type: str
    payload: dict[str, object]
    processing_status: MessageProcessingStatus
    delivery_status: MessageDeliveryStatus | None
    created_at: datetime
