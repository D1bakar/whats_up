from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class HttpResponse:
    status_code: int
    body: dict[str, Any] | list[Any] | str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class HttpTransport(Protocol):
    """Injectable HTTP transport for provider clients."""

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...


@dataclass
class RecordedRequest:
    method: str
    url: str
    json: dict[str, Any] | None
    headers: dict[str, str]


class MockHttpTransport:
    """Records outbound HTTP calls and returns configured responses."""

    def __init__(
        self,
        *,
        response: HttpResponse | None = None,
        responses: list[HttpResponse] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.requests: list[RecordedRequest] = []
        self._response = response or HttpResponse(
            status_code=200,
            body={"messages": [{"id": "wamid.mock123"}]},
        )
        self._responses = responses
        self._raise_error = raise_error
        self._call_index = 0

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        self.requests.append(
            RecordedRequest(method="POST", url=url, json=json, headers=headers or {}),
        )
        if self._raise_error is not None:
            raise self._raise_error

        if self._responses is not None:
            response = self._responses[min(self._call_index, len(self._responses) - 1)]
            self._call_index += 1
            return response

        return self._response
