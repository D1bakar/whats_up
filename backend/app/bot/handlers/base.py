from dataclasses import dataclass, field
from typing import Protocol

from app.bot.schemas import BotResponse
from app.bot.state import ConversationState


@dataclass(frozen=True)
class BotContext:
    """Runtime context passed to handlers during message processing."""

    conversation_id: str
    contact_id: str
    channel_user_id: str
    current_state: ConversationState
    state_data: dict[str, object] = field(default_factory=dict)
    text: str | None = None


@dataclass(frozen=True)
class HandlerResult:
    """Result of executing a bot handler."""

    responses: list[BotResponse]
    next_state: ConversationState | None = None
    state_data: dict[str, object] | None = None


class BotHandler(Protocol):
    async def handle(self, context: BotContext) -> HandlerResult: ...


class CommandHandler(BotHandler, Protocol):
    pass
