from dataclasses import dataclass


@dataclass(slots=True)
class APIError(Exception):
    """Domain error mapped to a JSON API response."""

    code: str
    message: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.message
