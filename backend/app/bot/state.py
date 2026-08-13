from enum import Enum

from app.bot.exceptions import StateTransitionError


class ConversationState(str, Enum):
    MAIN_MENU = "MAIN_MENU"
    DEMO_FLOW = "DEMO_FLOW"
    DEMO_COLLECTING = "DEMO_COLLECTING"
    DEMO_CONFIRMATION = "DEMO_CONFIRMATION"
    COMPLETED = "COMPLETED"


ALLOWED_TRANSITIONS: dict[ConversationState, frozenset[ConversationState]] = {
    ConversationState.MAIN_MENU: frozenset(
        {
            ConversationState.MAIN_MENU,
            ConversationState.DEMO_FLOW,
        },
    ),
    ConversationState.DEMO_FLOW: frozenset(
        {
            ConversationState.DEMO_CONFIRMATION,
            ConversationState.MAIN_MENU,
        },
    ),
    ConversationState.DEMO_COLLECTING: frozenset(
        {
            ConversationState.DEMO_CONFIRMATION,
            ConversationState.MAIN_MENU,
        },
    ),
    ConversationState.DEMO_CONFIRMATION: frozenset(
        {
            ConversationState.COMPLETED,
            ConversationState.DEMO_COLLECTING,
            ConversationState.MAIN_MENU,
        },
    ),
    ConversationState.COMPLETED: frozenset({ConversationState.MAIN_MENU}),
}


class ConversationStateMachine:
    """Validates and applies conversation state transitions."""

    def __init__(self, current_state: ConversationState) -> None:
        self._current = current_state

    @property
    def current(self) -> ConversationState:
        return self._current

    def can_transition_to(self, target: ConversationState) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self._current, frozenset())
        return target in allowed

    def transition_to(self, target: ConversationState) -> ConversationState:
        if not self.can_transition_to(target):
            raise StateTransitionError(
                f"Transition from {self._current.value} to {target.value} is not allowed",
            )
        self._current = target
        return self._current

    @staticmethod
    def parse(state_name: str) -> ConversationState:
        try:
            return ConversationState(state_name)
        except ValueError as exc:
            raise StateTransitionError(f"Unknown conversation state: {state_name}") from exc
