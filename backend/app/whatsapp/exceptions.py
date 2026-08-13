"""WhatsApp integration exceptions."""


class WhatsAppError(Exception):
    """Base exception for WhatsApp integration errors."""


class WebhookValidationError(WhatsAppError):
    """Webhook request failed validation (signature, token, structure)."""


class MessageParsingError(WhatsAppError):
    """Failed to parse a WhatsApp webhook payload into internal events."""


class ProviderAuthenticationError(WhatsAppError):
    """Provider rejected credentials (HTTP 401/403)."""


class ProviderRateLimitError(WhatsAppError):
    """Provider rate limit exceeded (HTTP 429)."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderTemporaryFailureError(WhatsAppError):
    """Transient provider failure (timeout, connection, HTTP 5xx)."""


class ProviderPermanentFailureError(WhatsAppError):
    """Non-retryable provider failure (HTTP 4xx except 429)."""


class ProviderTimeoutError(ProviderTemporaryFailureError):
    """Provider request timed out."""
