from app.ai.orchestrator import AIOrchestrator
from app.bot.handlers.base import BotContext, HandlerResult
from app.bot.schemas import BotResponse


class AITextHandler:
    """Routes natural-language text to the AI orchestrator."""

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def handle(self, context: BotContext) -> HandlerResult:
        ai_response = await self._orchestrator.generate_reply(
            conversation_id=context.conversation_id,
            user_message=context.text or "",
            current_state=context.current_state.value,
            state_data=context.state_data,
            exclude_wamid=context.message_id,
        )
        return HandlerResult(responses=[BotResponse(text=ai_response.text)])
