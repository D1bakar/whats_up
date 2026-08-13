from app.ai.prompts import v1
from app.ai.schemas import ConversationContext, PromptBundle


def build_prompt_bundle(
    context: ConversationContext,
    user_message: str,
) -> PromptBundle:
    """Assemble a versioned prompt from structured components."""

    context_lines: list[str] = []
    if context.state_summary:
        state_parts = [f"{key}={value}" for key, value in context.state_summary.items()]
        context_lines.append(f"Conversation state: {context.current_state}")
        context_lines.append(f"State data: {', '.join(state_parts)}")

    for turn in context.turns:
        role_label = "User" if turn.role == "user" else "Assistant"
        context_lines.append(f"{role_label}: {turn.content}")

    conversation_context = "\n".join(context_lines) if context_lines else "(no prior messages)"

    return PromptBundle(
        system_instructions=v1.SYSTEM_INSTRUCTIONS,
        business_rules=v1.BUSINESS_RULES,
        conversation_context=conversation_context,
        user_message=user_message,
        version=v1.PROMPT_VERSION,
    )


def render_messages_for_provider(bundle: PromptBundle) -> list[dict[str, str]]:
    """Render prompt bundle into provider chat message format."""

    system_content = f"{bundle.system_instructions}\n\n{bundle.business_rules}"
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (
                f"Conversation history:\n{bundle.conversation_context}\n\n"
                f"Latest user message:\n{bundle.user_message}"
            ),
        },
    ]
