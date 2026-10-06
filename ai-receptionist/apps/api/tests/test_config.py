import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_development_safe() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert not settings.is_production
    assert settings.llm_model_primary == "claude-sonnet-5"
    assert settings.llm_model_fast == "claude-haiku-4-5"


def test_cors_origins_parse_as_list() -> None:
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.setenv("MAX_CALL_DURATION_SECONDS", "600")
    settings = Settings(_env_file=None)
    assert settings.is_production
    assert settings.max_call_duration_seconds == 600


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize(
    "secret", ["dev-only-secret", "change-me-generate-with-openssl-rand-hex-32", "short"]
)
def test_deployed_environments_reject_weak_or_default_secret_key(env: str, secret: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None, app_env=env, secret_key=secret)


def test_deployed_environments_accept_a_strong_secret_key() -> None:
    settings = Settings(_env_file=None, app_env="production", secret_key="a" * 64)
    assert settings.is_production


def test_development_and_test_keep_the_convenient_default() -> None:
    assert Settings(_env_file=None, app_env="development").secret_key == "dev-only-secret"
    assert Settings(_env_file=None, app_env="test").secret_key == "dev-only-secret"
