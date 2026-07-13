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
    monkeypatch.setenv("MAX_CALL_DURATION_SECONDS", "600")
    settings = Settings(_env_file=None)
    assert settings.is_production
    assert settings.max_call_duration_seconds == 600
