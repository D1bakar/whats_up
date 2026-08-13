from collections.abc import Callable
from dataclasses import dataclass

from app.bot.handlers.base import BotContext, BotHandler, HandlerResult
from app.bot.handlers.commands import (
    DefaultTextHandler,
    HelpCommandHandler,
    MenuCommandHandler,
    StartCommandHandler,
    UnknownCommandHandler,
)
from app.bot.handlers.demo import DemoEntryHandler
from app.bot.handlers.demo_start import DemoStartCommandHandler
from app.bot.state import ConversationState
from app.core.logging import get_logger

logger = get_logger(__name__)

CommandHandlerFactory = Callable[[], BotHandler]


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    aliases: tuple[str, ...]
    description: str
    handler_factory: CommandHandlerFactory
    required_states: frozenset[ConversationState] | None = None


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, CommandDefinition] = {}

    def register(self, command: CommandDefinition) -> None:
        keys = (command.name, *command.aliases)
        for key in keys:
            self._commands[key.lower()] = command

    def resolve(self, text: str) -> CommandDefinition | None:
        normalized = _normalize_command(text)
        if not normalized:
            return None
        return self._commands.get(normalized)


def _normalize_command(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    stripped = stripped.removeprefix("/")
    token = stripped.split()[0].lower()
    return token or None


def build_default_command_registry() -> CommandRegistry:
    registry = CommandRegistry()
    registry.register(
        CommandDefinition(
            name="start",
            aliases=(),
            description="Restart the conversation",
            handler_factory=StartCommandHandler,
        ),
    )
    registry.register(
        CommandDefinition(
            name="help",
            aliases=(),
            description="Show help",
            handler_factory=HelpCommandHandler,
        ),
    )
    registry.register(
        CommandDefinition(
            name="menu",
            aliases=(),
            description="Show main menu",
            handler_factory=MenuCommandHandler,
        ),
    )
    registry.register(
        CommandDefinition(
            name="demo",
            aliases=("1",),
            description="Start demo flow",
            handler_factory=DemoStartCommandHandler,
        ),
    )
    return registry


_STATE_HANDLERS: dict[ConversationState, CommandHandlerFactory] = {
    ConversationState.DEMO_FLOW: DemoEntryHandler,
    ConversationState.DEMO_CONFIRMATION: DemoEntryHandler,
}


class BotRouter:
    """Routes inbound text to command handlers, state handlers, or defaults."""

    def __init__(
        self,
        command_registry: CommandRegistry | None = None,
        default_handler: BotHandler | None = None,
        unknown_command_handler: BotHandler | None = None,
    ) -> None:
        self._commands = command_registry or build_default_command_registry()
        self._default_handler = default_handler or DefaultTextHandler()
        self._unknown_command_handler = unknown_command_handler or UnknownCommandHandler()

    async def route(self, context: BotContext) -> HandlerResult:
        text = context.text or ""

        command = self._commands.resolve(text)
        if command is not None:
            if command.required_states and context.current_state not in command.required_states:
                logger.info(
                    "command_state_mismatch",
                    command=command.name,
                    current_state=context.current_state.value,
                )
                return await self._default_handler.handle(context)

            logger.info("command_detected", command=command.name)
            handler = command.handler_factory()
            logger.info("handler_selected", handler=handler.__class__.__name__)
            return await handler.handle(context)

        if _looks_like_unknown_command(text):
            logger.info("unknown_command_detected", text=text.strip())
            return await self._unknown_command_handler.handle(context)

        state_factory = _STATE_HANDLERS.get(context.current_state)
        if state_factory is not None:
            handler = state_factory()
            logger.info("handler_selected", handler=handler.__class__.__name__)
            return await handler.handle(context)

        logger.info("handler_selected", handler=self._default_handler.__class__.__name__)
        return await self._default_handler.handle(context)


def _looks_like_unknown_command(text: str) -> bool:
    normalized = _normalize_command(text)
    if not normalized:
        return False
    return text.strip().startswith("/")
