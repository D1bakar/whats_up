from app.ai.context import ConversationContextBuilder
from app.ai.factory import create_ai_provider
from app.ai.orchestrator import AIOrchestrator
from app.ai.provider import AIProvider
from app.bot.engine import BotEngine
from app.bot.handlers.ai import AITextHandler
from app.bot.handlers.commands import DefaultTextHandler
from app.bot.router import BotRouter
from app.core.config import Settings
from app.services.message_repository import MessageRepository
from sqlalchemy.ext.asyncio import AsyncSession


def create_bot_engine(
    settings: Settings,
    session: AsyncSession,
    *,
    ai_provider: AIProvider | None = None,
) -> BotEngine:
    if not settings.ai_enabled:
        return BotEngine()

    provider = ai_provider or create_ai_provider(settings)
    message_repository = MessageRepository(session)
    context_builder = ConversationContextBuilder(message_repository, settings)
    orchestrator = AIOrchestrator(settings, provider, context_builder)
    default_handler = AITextHandler(orchestrator)
    router = BotRouter(default_handler=default_handler)
    return BotEngine(router=router)


def create_bot_engine_without_ai() -> BotEngine:
    return BotEngine(router=BotRouter(default_handler=DefaultTextHandler()))
