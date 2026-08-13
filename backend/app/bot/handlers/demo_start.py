from app.bot import responses
from app.bot.handlers.base import BotContext, HandlerResult
from app.bot.schemas import BotResponse
from app.bot.state import ConversationState


class DemoStartCommandHandler:
    async def handle(self, context: BotContext) -> HandlerResult:
        return HandlerResult(
            responses=[BotResponse(text=responses.DEMO_FLOW_START)],
            next_state=ConversationState.DEMO_FLOW,
            state_data={},
        )
