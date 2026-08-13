import re

# Patterns that must never be sent to AI providers or logged in full context.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{10,}"),
)

_SAFE_STATE_KEYS = frozenset({"demo_name"})


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def sanitize_state_data(state_data: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in state_data.items() if key in _SAFE_STATE_KEYS}


def sanitize_message_text(text: str | None) -> str:
    if not text:
        return ""
    return redact_secrets(text.strip())
