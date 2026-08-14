"""Tests para el módulo de configuración tipada."""

import pytest
from pydantic import ValidationError
from src.config.settings import Settings, get_settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prueba que los settings se cargan correctamente desde variables de entorno."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODEL_ID", "openai/gpt-4o")
    monkeypatch.setenv("DB_SERVER", "localhost")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("DB_USER", "testuser")
    monkeypatch.setenv("DB_PASSWORD", "secretpass") # noqa: S105

    settings = Settings(_env_file=None)
    assert settings.openrouter_api_key == "sk-test-key"
    assert settings.model_id == "openai/gpt-4o"
    assert settings.db_server == "localhost"
    assert settings.db_name == "testdb"
    assert settings.db_user == "testuser"
    assert settings.db_password == "secretpass" # noqa: S105
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_max_tokens == 4096
    assert settings.llm_temperature == 0.0
    assert settings.llm_max_retries == 2
    assert settings.db_driver == "ODBC Driver 18 for SQL Server"
    assert settings.db_read_timeout_seconds == 30
    assert settings.db_max_rows == 1000
    assert settings.conversation_window == 6
    assert settings.sql_max_rows == 100
    assert settings.export_max_rows == 50000


def test_settings_missing_secret_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prueba que faltar una clave obligatoria lanza ValidationError."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_ID", raising=False)
    monkeypatch.delenv("DB_SERVER", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_caching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prueba que get_settings devuelva una instancia cacheada."""
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-cache-key")
    monkeypatch.setenv("MODEL_ID", "openai/gpt-4o")
    monkeypatch.setenv("DB_SERVER", "localhost")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("DB_USER", "testuser")
    monkeypatch.setenv("DB_PASSWORD", "secretpass") # noqa: S105

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
