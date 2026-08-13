import uuid

import pytest
from app.core.config import Settings
from app.core.security import hash_password
from app.db.session import get_engine
from app.main import create_app
from app.models import (
    AdminRole,
    AdminUser,
    Base,
    Channel,
    ConversationStatus,
    Message,
    MessageDirection,
    MessageProcessingStatus,
)
from app.services.contact import ContactService
from app.services.conversation import ConversationService
from app.services.phone_number import PhoneNumberService
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def admin_settings(test_settings: Settings) -> Settings:
    return test_settings.model_copy(
        update={"SECRET_KEY": "test-secret-key-for-jwt-signing-32bytes-min"}
    )


@pytest.fixture
async def admin_session_factory(admin_settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = get_engine(str(admin_settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.fixture
async def admin_client(
    admin_settings: Settings,
    admin_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncClient:
    app = create_app(admin_settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def _seed_operator(session: AsyncSession) -> tuple[AdminUser, str]:
    password = "operator-pass-123"
    user = AdminUser(
        email="operator@example.com",
        password_hash=hash_password(password),
        role=AdminRole.OPERATOR,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user, password


async def _seed_viewer(session: AsyncSession) -> tuple[AdminUser, str]:
    password = "viewer-pass-1234"
    user = AdminUser(
        email="viewer@example.com",
        password_hash=hash_password(password),
        role=AdminRole.VIEWER,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user, password


async def _seed_conversation_with_messages(session: AsyncSession) -> tuple[str, str]:
    phone = await PhoneNumberService(session).resolve("PHONE_NUMBER_ID")
    contact, _ = await ContactService(session).find_or_create(
        phone_number_id=str(phone.id),
        channel=Channel.WHATSAPP,
        channel_user_id="15559876543",
        display_name="Test User",
    )
    conversation, _ = await ConversationService(session).find_or_create(
        phone_number_id=phone.id,
        contact=contact,
    )
    conversation.status = ConversationStatus.ACTIVE
    inbound = Message(
        conversation_id=conversation.id,
        wamid=f"wamid.in.{uuid.uuid4().hex}",
        direction=MessageDirection.INBOUND,
        message_type="text",
        payload={"text": {"body": "hello"}},
        processing_status=MessageProcessingStatus.PROCESSED,
    )
    outbound = Message(
        conversation_id=conversation.id,
        wamid=f"wamid.out.{uuid.uuid4().hex}",
        direction=MessageDirection.OUTBOUND,
        message_type="text",
        payload={"text": {"body": "hi there"}},
        processing_status=MessageProcessingStatus.PROCESSED,
    )
    session.add_all([inbound, outbound])
    await session.commit()
    return str(conversation.id), str(contact.id)


@pytest.mark.asyncio
async def test_login_returns_token(
    admin_client: AsyncClient,
    admin_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with admin_session_factory() as session:
        _, password = await _seed_operator(session)

    response = await admin_client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.com", "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(
    admin_client: AsyncClient,
    admin_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with admin_session_factory() as session:
        await _seed_operator(session)

    response = await admin_client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_me_requires_authentication(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/api/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_access_conversations(
    admin_client: AsyncClient,
    admin_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with admin_session_factory() as session:
        _, password = await _seed_viewer(session)

    login = await admin_client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@example.com", "password": password},
    )
    token = login.json()["access_token"]

    response = await admin_client.get(
        "/api/v1/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


@pytest.mark.asyncio
async def test_operator_can_list_conversations_and_messages(
    admin_client: AsyncClient,
    admin_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with admin_session_factory() as session:
        _, password = await _seed_operator(session)
        conversation_id, contact_id = await _seed_conversation_with_messages(session)

    login = await admin_client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.com", "password": password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    me_response = await admin_client.get("/api/v1/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "operator@example.com"
    assert me_response.json()["role"] == AdminRole.OPERATOR.value

    conversations_response = await admin_client.get("/api/v1/conversations", headers=headers)
    assert conversations_response.status_code == 200
    conversations_body = conversations_response.json()
    assert conversations_body["total"] == 1
    assert conversations_body["items"][0]["id"] == conversation_id
    assert conversations_body["items"][0]["contact"]["display_name"] == "Test User"

    detail_response = await admin_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["contact"]["channel_user_id"] == "15559876543"

    messages_response = await admin_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert messages_response.status_code == 200
    messages_body = messages_response.json()
    assert messages_body["total"] == 2
    assert messages_body["items"][0]["direction"] == MessageDirection.INBOUND.value

    contacts_response = await admin_client.get("/api/v1/contacts", headers=headers)
    assert contacts_response.status_code == 200
    assert contacts_response.json()["items"][0]["id"] == contact_id

    contact_detail = await admin_client.get(f"/api/v1/contacts/{contact_id}", headers=headers)
    assert contact_detail.status_code == 200
    assert contact_detail.json()["channel"] == Channel.WHATSAPP.value


@pytest.mark.asyncio
async def test_conversation_not_found(
    admin_client: AsyncClient,
    admin_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with admin_session_factory() as session:
        _, password = await _seed_operator(session)

    login = await admin_client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.com", "password": password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await admin_client.get(
        f"/api/v1/conversations/{uuid.uuid4()}",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
