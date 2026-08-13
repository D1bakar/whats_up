import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.contact import Channel, Contact
from app.models.conversation import Conversation, ConversationStatus
from app.models.conversation_session import ConversationSession
from app.models.message import (
    Message,
    MessageDeliveryStatus,
    MessageDirection,
    MessageProcessingStatus,
)
from app.models.webhook_event import WebhookEvent, WebhookProcessingStatus


class AdminRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, name="admin_role", native_enum=False),
        nullable=False,
        default=AdminRole.VIEWER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BusinessAccount(Base):
    __tablename__ = "business_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meta_waba_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(
        back_populates="business_account",
        cascade="all, delete-orphan",
    )


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meta_phone_number_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    display_number: Mapped[str] = mapped_column(String(32), nullable=False)
    verify_token_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    business_account: Mapped[BusinessAccount] = relationship(back_populates="phone_numbers")


__all__ = [
    "AdminRole",
    "AdminUser",
    "Base",
    "BusinessAccount",
    "Channel",
    "Contact",
    "Conversation",
    "ConversationSession",
    "ConversationStatus",
    "Message",
    "MessageDeliveryStatus",
    "MessageDirection",
    "MessageProcessingStatus",
    "PhoneNumber",
    "WebhookEvent",
    "WebhookProcessingStatus",
]
