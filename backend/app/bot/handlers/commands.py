from app.bot import responses
from app.bot.handlers.base import BotContext, HandlerResult
from app.bot.schemas import BotResponse
from app.bot.state import ConversationState


class StartCommandHandler:
    async def handle(self, context: BotContext) -> HandlerResult:
        return HandlerResult(
            responses=[BotResponse(text=responses.WELCOME)],
            next_state=ConversationState.MAIN_MENU,
            state_data={},
        )


class HelpCommandHandler:
    async def handle(self, context: BotContext) -> HandlerResult:
        return HandlerResult(responses=[BotResponse(text=responses.HELP)])


class MenuCommandHandler:
    async def handle(self, context: BotContext) -> HandlerResult:
        return HandlerResult(responses=[BotResponse(text=responses.MENU)])


class DefaultTextHandler:
    async def handle(self, context: BotContext) -> HandlerResult:
        return HandlerResult(responses=[BotResponse(text=responses.DEFAULT_FALLBACK)])


class UnknownCommandHandler:
    async def handle(self, context: BotContext) -> HandlerResult:
        return HandlerResult(responses=[BotResponse(text=responses.UNKNOWN_COMMAND)])


class DemoFlowHandler:
    """Minimal example multi-step flow handler."""

    async def handle(self, context: BotContext) -> HandlerResult:
        text = (context.text or "").strip().lower()

        if context.current_state == ConversationState.DEMO_FLOW:
            if text == "cancel":
                return HandlerResult(
                    responses=[
                        BotResponse(text=responses.DEMO_FLOW_CANCELLED.format(menu=responses.MENU)),
                    ],
                    next_state=ConversationState.MAIN_MENU,
                    state_data={},
                )
            if not text:
                return HandlerResult(responses=[BotResponse(text=responses.DEMO_FLOW_INVALID)])
            return HandlerResult(
                responses=[
                    BotResponse(
                        text=responses.DEMO_FLOW_COLLECTED.format(
                            name=context.text.strip() if context.text else "",
                        ),
                    ),
                ],
                next_state=ConversationState.DEMO_CONFIRMATION,
                state_data={"demo_name": context.text.strip() if context.text else ""},
            )

        if context.current_state == ConversationState.DEMO_CONFIRMATION:
            if text == "cancel":
                return HandlerResult(
                    responses=[
                        BotResponse(text=responses.DEMO_FLOW_CANCELLED.format(menu=responses.MENU)),
                    ],
                    next_state=ConversationState.MAIN_MENU,
                    state_data={},
                )
            if text in {"yes", "y"}:
                return HandlerResult(
                    responses=[
                        BotResponse(
                            text=responses.DEMO_FLOW_CONFIRMED.format(menu=responses.MENU),
                        ),
                    ],
                    next_state=ConversationState.MAIN_MENU,
                    state_data={},
                )
            if text in {"no", "n"}:
                return HandlerResult(
                    responses=[BotResponse(text=responses.DEMO_FLOW_START)],
                    next_state=ConversationState.DEMO_FLOW,
                    state_data={},
                )
            return HandlerResult(responses=[BotResponse(text=responses.DEMO_FLOW_CONFIRM_INVALID)])

        return HandlerResult(responses=[BotResponse(text=responses.DEFAULT_FALLBACK)])
