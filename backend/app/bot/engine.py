from app.bot.exceptions import HandlerExecutionError, InvalidConversationStateError
from app.bot.handlers.base import BotContext, HandlerResult
from app.bot.router import BotRouter
from app.bot.schemas import BotResponse, InternalInboundMessage
from app.bot.state import ConversationState, ConversationStateMachine
from app.core.logging import get_logger

logger = get_logger(__name__)


class BotEngine:
    """Deterministic bot engine — routes messages and manages state transitions."""

    def __init__(self, router: BotRouter | None = None) -> None:
        self._router = router or BotRouter()

    async def process(
        self,
        message: InternalInboundMessage,
        *,
        conversation_id: str,
        contact_id: str,
        current_state: ConversationState,
        state_data: dict[str, object],
    ) -> tuple[list[BotResponse], ConversationState, dict[str, object]]:
        context = BotContext(
            conversation_id=conversation_id,
            contact_id=contact_id,
            channel_user_id=message.channel_user_id,
            current_state=current_state,
            state_data=state_data,
            text=message.text,
        )

        try:
            result = await self._router.route(context)
        except Exception as exc:
            logger.exception(
                "handler_failed",
                conversation_id=conversation_id,
                message_id=message.message_id,
            )
            raise HandlerExecutionError("Handler execution failed") from exc

        next_state, next_data = self._apply_state_transition(
            current_state=current_state,
            state_data=state_data,
            result=result,
            conversation_id=conversation_id,
        )

        logger.info(
            "response_generated",
            conversation_id=conversation_id,
            message_id=message.message_id,
            response_count=len(result.responses),
        )
        return result.responses, next_state, next_data

    @staticmethod
    def _apply_state_transition(
        *,
        current_state: ConversationState,
        state_data: dict[str, object],
        result: HandlerResult,
        conversation_id: str,
    ) -> tuple[ConversationState, dict[str, object]]:
        machine = ConversationStateMachine(current_state)
        next_state = result.next_state or current_state
        next_data = result.state_data if result.state_data is not None else state_data

        if next_state != current_state:
            try:
                machine.transition_to(next_state)
            except Exception as exc:
                raise InvalidConversationStateError(str(exc)) from exc
            logger.info(
                "state_transition",
                conversation_id=conversation_id,
                from_state=current_state.value,
                to_state=next_state.value,
            )

        return next_state, next_data
