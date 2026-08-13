from typing import Literal

from app.ai.prompts import v1
from app.ai.sanitization import sanitize_message_text, sanitize_state_data
from app.ai.schemas import ConversationContext, ConversationTurn
from app.core.config import Settings
from app.models import Message, MessageDirection
from app.services.message_repository import MessageRepository


class ConversationContextBuilder:
    """Builds bounded, sanitized conversation context for AI requests."""

    def __init__(self, message_repository: MessageRepository, settings: Settings) -> None:
        self._messages = message_repository
        self._settings = settings

    async def build(
        self,
        *,
        conversation_id: str,
        current_state: str,
        state_data: dict[str, object],
        user_message: str,
        exclude_wamid: str | None = None,
    ) -> ConversationContext:
        turns = await self._load_recent_turns(
            conversation_id=conversation_id,
            exclude_wamid=exclude_wamid,
        )
        turns = self._truncate_turns(turns)

        return ConversationContext(
            conversation_id=conversation_id,
            current_state=current_state,
            state_summary=sanitize_state_data(state_data),
            turns=turns,
            prompt_version=v1.PROMPT_VERSION,
        )

    async def _load_recent_turns(
        self,
        *,
        conversation_id: str,
        exclude_wamid: str | None,
    ) -> list[ConversationTurn]:
        limit = self._settings.ai_max_context_messages
        messages = await self._messages.get_recent_messages(
            conversation_id,
            limit=limit + 1,
        )

        turns: list[ConversationTurn] = []
        for message in messages:
            if exclude_wamid and message.wamid == exclude_wamid:
                continue
            text = self._extract_text(message)
            if not text:
                continue
            role: Literal["user", "assistant"] = (
                "user" if message.direction == MessageDirection.INBOUND else "assistant"
            )
            turns.append(ConversationTurn(role=role, content=text))

        if len(turns) > limit:
            turns = turns[-limit:]
        return turns

    def _truncate_turns(self, turns: list[ConversationTurn]) -> list[ConversationTurn]:
        max_chars = self._settings.ai_max_input_chars
        total = 0
        truncated: list[ConversationTurn] = []
        for turn in reversed(turns):
            turn_chars = len(turn.content)
            if total + turn_chars > max_chars:
                break
            truncated.append(turn)
            total += turn_chars
        truncated.reverse()
        return truncated

    @staticmethod
    def _extract_text(message: Message) -> str:
        payload = message.payload if isinstance(message.payload, dict) else {}
        raw_text = payload.get("text")
        if not isinstance(raw_text, str):
            return ""
        return sanitize_message_text(raw_text)
