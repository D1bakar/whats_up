import json

import pytest
from app.core.config import Settings
from app.services.idempotency import WebhookIdempotencyService
from app.services.outbound import OutboundMessageService
from app.webhooks.whatsapp.signature import compute_signature, verify_signature
from app.whatsapp.exceptions import (
    MessageParsingError,
    ProviderPermanentFailureError,
    ProviderTemporaryFailureError,
    ProviderTimeoutError,
)
from app.whatsapp.meta.client import MetaWhatsAppClient
from app.whatsapp.mock.provider import MockWhatsAppProvider
from app.whatsapp.parser import parse_webhook_payload
from app.whatsapp.schemas import InboundEventKind
from app.whatsapp.transport import HttpResponse, MockHttpTransport
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_webhook_verification_valid(client: AsyncClient) -> None:
    response = await client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "challenge-123",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge-123"


@pytest.mark.asyncio
async def test_webhook_verification_invalid_token(client: AsyncClient) -> None:
    response = await client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge-123",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_text_event(client: AsyncClient, mock_provider: MockWhatsAppProvider) -> None:
    payload = load_fixture("text_message.json")
    response = await client.post("/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["accepted"] == 1
    assert body["duplicates"] == 0
    assert len(mock_provider.outbound_messages) == 1
    assert "didn't understand" in mock_provider.outbound_messages[0].text.lower()


@pytest.mark.asyncio
async def test_webhook_malformed_payload(client: AsyncClient) -> None:
    response = await client.post("/webhooks/whatsapp", content=b"not-json")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_unsupported_event(client: AsyncClient) -> None:
    payload = load_fixture("image_message.json")
    response = await client.post("/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["unsupported"] == 1
    assert body["accepted"] == 0


@pytest.mark.asyncio
async def test_webhook_status_event(
    client: AsyncClient, mock_provider: MockWhatsAppProvider
) -> None:
    payload = load_fixture("status_update.json")
    response = await client.post("/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 1
    assert len(mock_provider.outbound_messages) == 0


@pytest.mark.asyncio
async def test_webhook_duplicate_event(client: AsyncClient) -> None:
    payload = load_fixture("text_message.json")

    first = await client.post("/webhooks/whatsapp", json=payload)
    second = await client.post("/webhooks/whatsapp", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["accepted"] == 1
    assert second.json()["duplicates"] == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_processing(db_engine) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    payload = {"test": True}

    async def register_once() -> bool:
        async with session_factory() as session:
            svc = WebhookIdempotencyService(session)
            _, is_new = await svc.register(
                "wamid.concurrent", wamid="wamid.concurrent", raw_payload=payload
            )
            return is_new

    results: list[bool] = []
    for _ in range(5):
        results.append(await register_once())

    assert sum(results) == 1


@pytest.mark.asyncio
async def test_webhook_retries_after_failed_processing(
    test_settings: Settings,
    mock_provider: MockWhatsAppProvider,
) -> None:
    """Events marked FAILED must be reprocessed on Meta webhook retry."""
    from app.db.session import get_engine
    from app.main import create_app
    from app.models import Base, WebhookEvent, WebhookProcessingStatus
    from app.services.outbound import OutboundMessageService
    from httpx import ASGITransport
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    engine = get_engine(str(test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(test_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        session.add(
            WebhookEvent(
                event_id="wamid.HBgLMTU1NTk4NzY1NDMBFQIAEhgWM0VCMDYyOTVCMzY1OTY2ODI5AA==",
                wamid="wamid.HBgLMTU1NTk4NzY1NDMBFQIAEhgWM0VCMDYyOTVCMzY1OTY2ODI5AA==",
                raw_payload={"preexisting": True},
                processing_status=WebhookProcessingStatus.FAILED,
            ),
        )
        await session.commit()

    async with app.router.lifespan_context(app):
        app.state.whatsapp_provider = mock_provider
        app.state.outbound_service = OutboundMessageService(mock_provider, test_settings)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/whatsapp",
                json=load_fixture("text_message.json"),
            )

    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert len(mock_provider.outbound_messages) == 1

    async with session_factory() as session:
        result = await session.execute(
            select(WebhookEvent).where(
                WebhookEvent.event_id
                == "wamid.HBgLMTU1NTk4NzY1NDMBFQIAEhgWM0VCMDYyOTVCMzY1OTY2ODI5AA==",
            ),
        )
        event = result.scalar_one()
        assert event.processing_status == WebhookProcessingStatus.PROCESSED


@pytest.mark.asyncio
async def test_parser_text_message() -> None:
    payload = load_fixture("text_message.json")
    events = parse_webhook_payload(payload)

    assert len(events) == 1
    event = events[0]
    assert event.kind == InboundEventKind.MESSAGE
    assert event.text == "Hello, bot!"
    assert event.sender_id == "15559876543"
    assert event.phone_number_id == "PHONE_NUMBER_ID"


@pytest.mark.asyncio
async def test_parser_malformed_payload() -> None:
    with pytest.raises(MessageParsingError):
        parse_webhook_payload({"entry": "invalid"})


@pytest.mark.asyncio
async def test_mock_outbound_text_message(mock_provider: MockWhatsAppProvider) -> None:
    result = await mock_provider.send_text_message("15559876543", "Hello")
    assert result.message_id.startswith("wamid.mock.")
    assert len(mock_provider.outbound_messages) == 1


@pytest.mark.asyncio
async def test_outbound_retry_on_500(test_settings: Settings) -> None:
    transport = MockHttpTransport(
        responses=[
            HttpResponse(status_code=500, body={"error": "server error"}),
            HttpResponse(status_code=200, body={"messages": [{"id": "wamid.retry"}]}),
        ],
    )
    client = MetaWhatsAppClient(
        Settings(
            WHATSAPP_PROVIDER="meta",
            META_WHATSAPP_ACCESS_TOKEN="test-token",
            META_WHATSAPP_PHONE_NUMBER_ID="123",
            WHATSAPP_OUTBOUND_MAX_RETRIES=2,
            WHATSAPP_OUTBOUND_RETRY_BASE_DELAY=0.01,
        ),
        transport=transport,
    )
    service = OutboundMessageService(client, test_settings)

    result = await service.send_text_message("15559876543", "Hi")
    assert result.message_id == "wamid.retry"
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_outbound_retry_on_429(test_settings: Settings) -> None:
    transport = MockHttpTransport(
        responses=[
            HttpResponse(
                status_code=429, body={"error": "rate limit"}, headers={"Retry-After": "0.01"}
            ),
            HttpResponse(status_code=200, body={"messages": [{"id": "wamid.ratelimit"}]}),
        ],
    )
    client = MetaWhatsAppClient(
        Settings(
            WHATSAPP_PROVIDER="meta",
            META_WHATSAPP_ACCESS_TOKEN="test-token",
            META_WHATSAPP_PHONE_NUMBER_ID="123",
            WHATSAPP_OUTBOUND_MAX_RETRIES=2,
            WHATSAPP_OUTBOUND_RETRY_BASE_DELAY=0.01,
        ),
        transport=transport,
    )
    service = OutboundMessageService(client, test_settings)

    result = await service.send_text_message("15559876543", "Hi")
    assert result.message_id == "wamid.ratelimit"


@pytest.mark.asyncio
async def test_outbound_permanent_error_no_retry(test_settings: Settings) -> None:
    transport = MockHttpTransport(
        response=HttpResponse(status_code=400, body={"error": "bad request"})
    )
    client = MetaWhatsAppClient(
        Settings(
            WHATSAPP_PROVIDER="meta",
            META_WHATSAPP_ACCESS_TOKEN="test-token",
            META_WHATSAPP_PHONE_NUMBER_ID="123",
        ),
        transport=transport,
    )
    service = OutboundMessageService(client, test_settings)

    with pytest.raises(ProviderPermanentFailureError):
        await service.send_text_message("15559876543", "Hi")
    assert len(transport.requests) == 1


@pytest.mark.asyncio
async def test_outbound_timeout(test_settings: Settings) -> None:
    transport = MockHttpTransport(raise_error=ProviderTimeoutError("timeout"))
    client = MetaWhatsAppClient(
        Settings(
            WHATSAPP_PROVIDER="meta",
            META_WHATSAPP_ACCESS_TOKEN="test-token",
            META_WHATSAPP_PHONE_NUMBER_ID="123",
            WHATSAPP_OUTBOUND_MAX_RETRIES=1,
            WHATSAPP_OUTBOUND_RETRY_BASE_DELAY=0.01,
        ),
        transport=transport,
    )
    service = OutboundMessageService(client, test_settings)

    with pytest.raises(ProviderTemporaryFailureError):
        await service.send_text_message("15559876543", "Hi")


@pytest.mark.asyncio
async def test_outbound_exhausted_retries(test_settings: Settings) -> None:
    transport = MockHttpTransport(
        response=HttpResponse(status_code=503, body={"error": "unavailable"})
    )
    client = MetaWhatsAppClient(
        Settings(
            WHATSAPP_PROVIDER="meta",
            META_WHATSAPP_ACCESS_TOKEN="test-token",
            META_WHATSAPP_PHONE_NUMBER_ID="123",
            WHATSAPP_OUTBOUND_MAX_RETRIES=2,
            WHATSAPP_OUTBOUND_RETRY_BASE_DELAY=0.01,
        ),
        transport=transport,
    )
    retry_settings = Settings(
        WHATSAPP_PROVIDER="meta",
        META_WHATSAPP_ACCESS_TOKEN="test-token",
        META_WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_OUTBOUND_MAX_RETRIES=2,
        WHATSAPP_OUTBOUND_RETRY_BASE_DELAY=0.01,
    )
    service = OutboundMessageService(client, retry_settings)

    with pytest.raises(ProviderTemporaryFailureError):
        await service.send_text_message("15559876543", "Hi")
    assert len(transport.requests) == 3


def test_signature_verification() -> None:
    secret = "test-secret"
    body = b'{"object":"whatsapp_business_account"}'
    signature = compute_signature(secret, body)
    assert verify_signature(secret, body, signature)
    assert not verify_signature(secret, body, "sha256=invalid")


@pytest.mark.asyncio
async def test_webhook_signature_required(mock_provider: MockWhatsAppProvider) -> None:
    from app.db.session import get_engine
    from app.main import create_app
    from app.models import Base
    from httpx import ASGITransport

    settings = Settings(
        APP_NAME="WhatsApp Platform Test",
        ENVIRONMENT="development",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/0",
        WHATSAPP_PROVIDER="mock",
        WHATSAPP_VERIFY_TOKEN="test-verify-token",
        WHATSAPP_APP_SECRET="test-secret",
    )

    engine = get_engine(str(settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings)
    app.state.whatsapp_provider = mock_provider
    app.state.outbound_service = OutboundMessageService(mock_provider, settings)

    payload = load_fixture("text_message.json")
    body = json.dumps(payload).encode()

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        unsigned = await client.post("/webhooks/whatsapp", content=body)
        assert unsigned.status_code == 403

        signed = await client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": compute_signature("test-secret", body),
            },
        )
        assert signed.status_code == 200


def test_config_validation_defaults() -> None:
    settings = Settings()
    assert settings.whatsapp_provider == "mock"
    assert settings.meta_whatsapp_configured is False
    assert settings.whatsapp_signature_required is False


@pytest.mark.asyncio
async def test_meta_client_does_not_log_secrets(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    caplog.set_level(logging.INFO)
    transport = MockHttpTransport()
    client = MetaWhatsAppClient(
        Settings(
            META_WHATSAPP_ACCESS_TOKEN="super-secret-token",
            META_WHATSAPP_PHONE_NUMBER_ID="123",
        ),
        transport=transport,
    )

    await client.send_text_message("15559876543", "Hello")

    log_text = caplog.text
    assert "super-secret-token" not in log_text
    assert "Bearer" not in log_text
