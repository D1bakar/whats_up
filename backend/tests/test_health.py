import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "WhatsApp Platform Test"
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_ready_endpoint_returns_checks(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    check_names = {check["name"] for check in payload["checks"]}
    assert check_names == {"postgresql", "redis"}
