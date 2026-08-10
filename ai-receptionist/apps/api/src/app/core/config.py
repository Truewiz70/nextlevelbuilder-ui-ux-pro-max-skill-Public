"""Application configuration.

Every runtime setting is env-driven (12-factor). `.env` is read in local
development; in staging/production values come from the platform secret store.
Settings are validated at startup — a missing required secret fails fast
rather than surfacing mid-call.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = Field(default="dev-only-secret", description="JWT / signing key")
    cors_origins: str = "http://localhost:3000"

    # Data stores
    database_url: str = "postgresql+asyncpg://receptionist:receptionist@localhost:5432/receptionist"
    redis_url: str = "redis://localhost:6379/0"
    credentials_encryption_key: str = ""

    # Voice layer
    voice_provider: Literal["vapi", "retell"] = "vapi"
    vapi_api_key: str = ""
    vapi_webhook_secret: str = ""
    # Publicly reachable base URL of THIS api, e.g. https://api.example.com or
    # an https tunnel in development. Written into the vendor-side agent as its
    # server URL, so the vendor knows where to send call + tool-call webhooks.
    # Without it, provisioning has nowhere to point and the agent can't call
    # any tool.
    public_webhook_base_url: str = ""

    # Telephony / SMS
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_messaging_service_sid: str = ""

    # LLM
    anthropic_api_key: str = ""
    llm_model_primary: str = "claude-sonnet-5"
    llm_model_fast: str = "claude-haiku-4-5"

    # Embeddings
    voyage_api_key: str = ""
    embedding_model: str = "voyage-3.5"
    embedding_dimensions: int = 1024

    # Integrations
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    resend_api_key: str = ""
    email_from: str = "notifications@example.com"

    # Observability
    sentry_dsn: str = ""

    # Guardrails
    max_call_duration_seconds: int = 900
    tenant_daily_spend_cap_usd: float = 50.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
