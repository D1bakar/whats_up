import json
import uuid
from pathlib import Path

import pytest
from app.core.config import Settings
from app.db.session import get_engine
from app.main import create_app
from app.models import Base
from app.services.outbound import OutboundMessageService
from app.whatsapp.mock.provider import MockWhatsAppProvider
from httpx import ASGITransport, AsyncClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "whatsapp"


@pytest.fixture(autouse=True)
def _clear_engine_cache() -> None:
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        APP_NAME="WhatsApp Platform Test",
        ENVIRONMENT="development",
        DEBUG=True,
        LOG_LEVEL="WARNING",
        DATABASE_URL=f"sqlite+aiosqlite:///file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared",
        REDIS_URL="redis://localhost:6379/0",
        WHATSAPP_PROVIDER="mock",
        WHATSAPP_VERIFY_TOKEN="test-verify-token",
        WHATSAPP_APP_SECRET="",
        WHATSAPP_OUTBOUND_MAX_RETRIES=2,
        WHATSAPP_OUTBOUND_RETRY_BASE_DELAY=0.01,
    )


@pytest.fixture
def mock_provider() -> MockWhatsAppProvider:
    return MockWhatsAppProvider()


@pytest.fixture
async def db_engine(test_settings: Settings):
    engine = get_engine(str(test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(test_settings: Settings, mock_provider: MockWhatsAppProvider) -> AsyncClient:
    engine = get_engine(str(test_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(test_settings)

    async with app.router.lifespan_context(app):
        app.state.whatsapp_provider = mock_provider
        app.state.outbound_service = OutboundMessageService(mock_provider, test_settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
