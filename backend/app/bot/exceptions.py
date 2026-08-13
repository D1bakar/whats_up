class BotEngineError(Exception):
    """Base exception for bot engine failures."""


class InvalidInboundMessageError(BotEngineError):
    """Raised when an internal inbound message is missing required fields."""


class HandlerExecutionError(BotEngineError):
    """Raised when a command or state handler fails unexpectedly."""


class StateTransitionError(BotEngineError):
    """Raised when a state transition is not permitted."""


class InvalidConversationStateError(BotEngineError):
    """Raised when persisted state is unknown or invalid."""
