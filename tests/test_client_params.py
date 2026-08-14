"""parametrización seed/top_p/provider + reintento-en-vacío en el cliente LLM. Settings FALSOS (SimpleNamespace),
cliente OpenAI mockeado — sin.env real ni secretos. Cubren:
  - No-regresión: sin kwargs nuevos, el request NO lleva seed/top_p/extra_body (router/asesor).
  - Nueva funcionalidad: seed/top_p/provider se inyectan con el formato de OpenRouter.
  - Reintento-en-vacío: recupera si un vacío es seguido de una válida; agota y da LLM_VACIO.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from src.llm.client import LLM_VACIO, ClienteLLM


@pytest.fixture(autouse=True)
def _sin_espera(monkeypatch):
    monkeypatch.setattr("src.llm.client.time.sleep", lambda *_: None)


def _settings(max_retries: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        openrouter_base_url="https://example.test/api/v1",
        openrouter_api_key="clave-falsa",
        model_id="modelo-test",
        llm_max_tokens=16,
        llm_temperature=0.0,
        llm_max_retries=max_retries,
        llm_timeout_seconds=60,
    )


def _cliente(max_retries: int = 2) -> ClienteLLM:
    c = ClienteLLM(settings=_settings(max_retries))
    c.client = MagicMock()
    return c


def _respuesta(contenido):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))])


# --- No-regresión: sin kwargs nuevos, el request es idéntico al de antes ---


def test_sin_kwargs_no_inyecta_seed_top_p_provider() -> None:
    c = _cliente()
    c.client.chat.completions.create.return_value = _respuesta("SELECT 1")
    c.completar([{"role": "user", "content": "hi"}])
    kwargs = c.client.chat.completions.create.call_args.kwargs
    assert "seed" not in kwargs
    assert "top_p" not in kwargs
    assert "extra_body" not in kwargs


def test_preparar_extra_params_vacio_cuando_todo_none() -> None:
    c = _cliente()
    assert c._preparar_extra_params(None, None, None) == {}


# --- Nueva funcionalidad: los parámetros de determinismo se inyectan bien ---


def test_seed_top_p_provider_se_inyectan() -> None:
    c = _cliente()
    c.client.chat.completions.create.return_value = _respuesta("SELECT 1")
    c.completar([{"role": "user", "content": "hi"}], seed=42, top_p=0.0, provider="Novita")
    kwargs = c.client.chat.completions.create.call_args.kwargs
    assert kwargs["seed"] == 42
    assert kwargs["top_p"] == 0.0
    assert kwargs["extra_body"] == {
        "provider": {"order": ["Novita"], "allow_fallbacks": False}
    }


def test_provider_solo_no_agrega_seed() -> None:
    c = _cliente()
    c.client.chat.completions.create.return_value = _respuesta("SELECT 1")
    c.completar([{"role": "user", "content": "hi"}], provider="Novita")
    kwargs = c.client.chat.completions.create.call_args.kwargs
    assert "seed" not in kwargs
    assert kwargs["extra_body"]["provider"]["allow_fallbacks"] is False


# --- Reintento-en-vacío ---


def test_reintento_en_vacio_recupera() -> None:
    c = _cliente(max_retries=2)
    c.client.chat.completions.create.side_effect = [_respuesta(""), _respuesta("SELECT 1")]
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is True
    assert r.contenido == "SELECT 1"
    assert c.client.chat.completions.create.call_count == 2 # 1 vacío + 1 bueno


def test_reintento_en_vacio_agota_y_da_vacio() -> None:
    c = _cliente(max_retries=2)
    c.client.chat.completions.create.return_value = _respuesta("")
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_VACIO
    assert c.client.chat.completions.create.call_count == 3 # llm_max_retries + 1


def test_sin_choices_reintenta_y_agota() -> None:
    c = _cliente(max_retries=1)
    c.client.chat.completions.create.return_value = SimpleNamespace(choices=[])
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_VACIO
    assert c.client.chat.completions.create.call_count == 2 # reintenta, no falla al primer intento
