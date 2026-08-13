from app.bot.handlers.base import BotContext, HandlerResult
from app.bot.handlers.commands import DemoFlowHandler
from app.bot.schemas import BotResponse
from app.bot.state import ConversationState


class DemoEntryHandler:
    """Starts the minimal demo flow from the main menu."""

    def __init__(self) -> None:
        self._demo = DemoFlowHandler()

    async def handle(self, context: BotContext) -> HandlerResult:
        if context.current_state == ConversationState.MAIN_MENU:
            text = (context.text or "").strip().lower()
            if text in {"demo", "1"}:
                from app.bot import responses

                return HandlerResult(
                    responses=[BotResponse(text=responses.DEMO_FLOW_START)],
                    next_state=ConversationState.DEMO_FLOW,
                    state_data={},
                )
        return await self._demo.handle(context)
