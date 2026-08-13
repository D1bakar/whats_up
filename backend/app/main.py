from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import new_request_id
from app.api.v1.health import router as health_router
from app.api.v1.router import router as admin_v1_router
from app.core.config import Settings, get_settings
from app.core.exceptions import APIError
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.schemas.errors import ErrorResponse
from app.services.outbound import OutboundMessageService
from app.webhooks.whatsapp.router import router as whatsapp_webhook_router
from app.whatsapp.exceptions import (
    ProviderAuthenticationError,
    ProviderPermanentFailureError,
    ProviderRateLimitError,
    ProviderTemporaryFailureError,
    ProviderTimeoutError,
    WebhookValidationError,
)
from app.whatsapp.factory import create_whatsapp_provider

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings)

    app.state.session_factory = get_session_factory(settings)
    app.state.redis = redis.from_url(str(settings.redis_url), decode_responses=True)
    app.state.whatsapp_provider = create_whatsapp_provider(settings)
    app.state.outbound_service = OutboundMessageService(
        app.state.whatsapp_provider,
        settings,
    )

    logger.info(
        "application_start",
        environment=settings.environment,
        whatsapp_provider=settings.whatsapp_provider,
        meta_configured=settings.meta_whatsapp_configured,
        ai_provider=settings.ai_provider,
        ai_enabled=settings.ai_enabled,
    )
    try:
        yield
    finally:
        await app.state.redis.aclose()
        logger.info("application_stop")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    app = FastAPI(
        title=config.app_name,
        version="0.1.0",
        docs_url="/docs" if config.is_development else None,
        redoc_url="/redoc" if config.is_development else None,
        lifespan=lifespan,
    )
    app.state.settings = config

    app.include_router(health_router)
    app.include_router(admin_v1_router)
    app.include_router(whatsapp_webhook_router)

    register_exception_handlers(app)
    register_middleware(app)

    return app


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "api_error",
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )
        body = ErrorResponse(code=exc.code, message=exc.message, request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="validation_error",
            message="Request validation failed",
            request_id=request_id,
        )
        logger.info("validation_error", errors=exc.errors(), request_id=request_id)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={**body.model_dump(), "details": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="http_error",
            message=str(exc.detail),
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unhandled_exception", request_id=request_id)
        body = ErrorResponse(
            code="internal_error",
            message="An unexpected error occurred",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(),
        )

    @app.exception_handler(WebhookValidationError)
    async def webhook_validation_handler(
        request: Request,
        exc: WebhookValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="webhook_validation_failed",
            message=str(exc),
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=body.model_dump())

    @app.exception_handler(ProviderAuthenticationError)
    async def provider_auth_handler(
        request: Request,
        exc: ProviderAuthenticationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="provider_authentication_error",
            message="Provider authentication failed",
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=body.model_dump())

    @app.exception_handler(ProviderRateLimitError)
    async def provider_rate_limit_handler(
        request: Request,
        exc: ProviderRateLimitError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="provider_rate_limit",
            message="Provider rate limit exceeded",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=body.model_dump()
        )

    @app.exception_handler(ProviderTemporaryFailureError)
    async def provider_temp_failure_handler(
        request: Request,
        exc: ProviderTemporaryFailureError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="provider_temporary_failure",
            message="Provider temporarily unavailable",
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=body.model_dump())

    @app.exception_handler(ProviderPermanentFailureError)
    async def provider_perm_failure_handler(
        request: Request,
        exc: ProviderPermanentFailureError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="provider_permanent_failure",
            message="Provider rejected the request",
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=body.model_dump())

    @app.exception_handler(ProviderTimeoutError)
    async def provider_timeout_handler(
        request: Request,
        exc: ProviderTimeoutError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        body = ErrorResponse(
            code="provider_timeout",
            message="Provider request timed out",
            request_id=request_id,
        )
        return JSONResponse(status_code=status.HTTP_504_GATEWAY_TIMEOUT, content=body.model_dump())


app = create_app()
