import uuid
from collections.abc import AsyncGenerator

import redis.asyncio as redis
from app.core.config import Settings
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_redis(request: Request) -> AsyncGenerator[redis.Redis, None]:
    client: redis.Redis = request.app.state.redis
    yield client


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def new_request_id() -> str:
    return str(uuid.uuid4())
