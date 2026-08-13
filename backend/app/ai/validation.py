from app.ai.exceptions import AIProviderEmptyResponseError, AIProviderMalformedResponseError
from app.ai.schemas import AIResponse


def validate_ai_response(response: AIResponse, *, max_output_chars: int) -> AIResponse:
    if not response.text or not response.text.strip():
        raise AIProviderEmptyResponseError("Provider returned empty text")

    if not response.provider.strip() or not response.model.strip():
        raise AIProviderMalformedResponseError("Missing provider or model metadata")

    text = response.text.strip()
    if len(text) > max_output_chars:
        text = text[:max_output_chars]

    return response.model_copy(update={"text": text})
