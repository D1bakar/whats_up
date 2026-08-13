from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class InboundEventKind(str, Enum):
    MESSAGE = "message"
    STATUS = "status"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class WhatsAppInboundEvent(BaseModel):
    """Normalized inbound event from any WhatsApp provider."""

    event_id: str
    message_id: str | None = None
    sender_id: str | None = None
    message_type: str | None = None
    text: str | None = None
    timestamp: datetime | None = None
    phone_number_id: str | None = None
    kind: InboundEventKind = InboundEventKind.UNKNOWN
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutboundMessageType(str, Enum):
    TEXT = "text"


class OutboundMessageRequest(BaseModel):
    """Internal outbound message intent."""

    to: str
    message_type: OutboundMessageType = OutboundMessageType.TEXT
    text: str | None = None
    idempotency_key: str | None = None


class OutboundMessageResult(BaseModel):
    """Result of a successful outbound send."""

    message_id: str
    provider: str
    status: Literal["sent"] = "sent"
    metadata: dict[str, Any] = Field(default_factory=dict)
