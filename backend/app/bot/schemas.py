from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class BotResponseType(str, Enum):
    TEXT = "text"


class BotResponse(BaseModel):
    """Channel-independent bot response representation."""

    type: BotResponseType = BotResponseType.TEXT
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class InternalInboundMessage(BaseModel):
    """Normalized inbound message for bot processing."""

    event_id: str
    message_id: str
    sender_id: str
    channel: Literal["whatsapp"] = "whatsapp"
    channel_user_id: str
    message_type: str
    text: str | None = None
    phone_number_id: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
