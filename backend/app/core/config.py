from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="WhatsApp Platform", alias="APP_NAME")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/whatsapp_platform",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")

    # WhatsApp provider selection
    whatsapp_provider: Literal["mock", "meta"] = Field(
        default="mock",
        alias="WHATSAPP_PROVIDER",
    )

    # Meta Cloud API (real credentials — NOT YET CONFIGURED by default)
    meta_whatsapp_access_token: str = Field(default="", alias="META_WHATSAPP_ACCESS_TOKEN")
    meta_whatsapp_phone_number_id: str = Field(default="", alias="META_WHATSAPP_PHONE_NUMBER_ID")
    meta_whatsapp_business_account_id: str = Field(
        default="",
        alias="META_WHATSAPP_BUSINESS_ACCOUNT_ID",
    )
    meta_whatsapp_api_version: str = Field(default="v21.0", alias="META_WHATSAPP_API_VERSION")
    meta_whatsapp_api_base_url: str = Field(
        default="https://graph.facebook.com",
        alias="META_WHATSAPP_API_BASE_URL",
    )
    meta_whatsapp_request_timeout: float = Field(
        default=30.0, alias="META_WHATSAPP_REQUEST_TIMEOUT"
    )

    # Webhook verification and signature
    whatsapp_verify_token: str = Field(default="dev-verify-token", alias="WHATSAPP_VERIFY_TOKEN")
    whatsapp_app_secret: str = Field(default="", alias="WHATSAPP_APP_SECRET")

    # Outbound retry policy
    whatsapp_outbound_max_retries: int = Field(default=3, alias="WHATSAPP_OUTBOUND_MAX_RETRIES")
    whatsapp_outbound_retry_base_delay: float = Field(
        default=1.0,
        alias="WHATSAPP_OUTBOUND_RETRY_BASE_DELAY",
    )

    @property
    def whatsapp_signature_required(self) -> bool:
        return bool(self.whatsapp_app_secret.strip())

    @property
    def meta_whatsapp_configured(self) -> bool:
        return bool(
            self.meta_whatsapp_access_token.strip() and self.meta_whatsapp_phone_number_id.strip()
        )

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_asyncpg_driver(cls, value: str) -> str:
        url = str(value)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


def get_settings() -> Settings:
    return Settings()
