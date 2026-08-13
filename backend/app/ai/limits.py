import time
from collections import defaultdict


class ConversationRateLimiter:
    """In-memory per-conversation AI request limiter."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def allow(self, conversation_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        recent = [ts for ts in self._timestamps[conversation_id] if ts > cutoff]
        self._timestamps[conversation_id] = recent
        if len(recent) >= self._max_requests:
            return False
        recent.append(now)
        self._timestamps[conversation_id] = recent
        return True

    def reset(self) -> None:
        self._timestamps.clear()
