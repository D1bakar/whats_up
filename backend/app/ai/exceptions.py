"""AI layer exceptions."""


class AIError(Exception):
    """Base exception for AI layer errors."""


class AIInputLimitExceededError(AIError):
    """User input or context exceeds configured limits."""


class AIAbuseLimitExceededError(AIError):
    """Per-conversation AI request limit exceeded."""


class AIProviderError(AIError):
    """Base exception for AI provider failures."""


class AIProviderTimeoutError(AIProviderError):
    """Provider request timed out."""


class AIProviderConnectionError(AIProviderError):
    """Network or connection failure reaching the provider."""


class AIProviderAuthenticationError(AIProviderError):
    """Provider rejected credentials (HTTP 401/403)."""


class AIProviderRateLimitError(AIProviderError):
    """Provider rate limit exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AIProviderClientError(AIProviderError):
    """Non-retryable provider client error (HTTP 4xx except 429)."""


class AIProviderServerError(AIProviderError):
    """Transient provider server error (HTTP 5xx)."""


class AIProviderMalformedResponseError(AIProviderError):
    """Provider returned a response that could not be parsed."""


class AIProviderEmptyResponseError(AIProviderError):
    """Provider returned an empty or whitespace-only response."""
