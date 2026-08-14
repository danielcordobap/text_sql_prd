"""Pruebas del cliente LLM.

Usa settings FALSOS (SimpleNamespace) — sin acoplar al.env real ni exponer secretos.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIError, APITimeoutError, RateLimitError
from src.llm.client import (
    LLM_ERROR,
    LLM_RATE_LIMIT,
    LLM_TIMEOUT,
    LLM_VACIO,
    ClienteLLM,
)

_REQ = httpx.Request("POST", "https://example.test/api/v1/chat/completions")


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


def test_cliente_construido_con_timeout_y_sin_reintento_sdk() -> None:
    """el cliente OpenAI se construye con timeout de config y max_retries=0."""
    c = ClienteLLM(settings=_settings())
    assert c.client.max_retries == 0
    assert c.client.timeout == 60


def _cliente(max_retries: int = 2) -> ClienteLLM:
    c = ClienteLLM(settings=_settings(max_retries))
    c.client = MagicMock()
    return c


def _respuesta(contenido):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))])


def test_exito_devuelve_contenido():
    c = _cliente()
    c.client.chat.completions.create.return_value = _respuesta("hola mundo")
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is True
    assert r.contenido == "hola mundo"
    assert c.client.chat.completions.create.call_count == 1


def test_timeout_agota_reintentos():
    c = _cliente(max_retries=2)
    c.client.chat.completions.create.side_effect = APITimeoutError(request=_REQ)
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_TIMEOUT
    assert c.client.chat.completions.create.call_count == 3 # max_retries + 1


def test_rate_limit_agota_reintentos():
    c = _cliente(max_retries=1)
    resp = httpx.Response(429, request=_REQ)
    c.client.chat.completions.create.side_effect = RateLimitError("rate", response=resp, body=None)
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_RATE_LIMIT
    assert c.client.chat.completions.create.call_count == 2


def test_contenido_en_blanco_es_vacio():
    c = _cliente()
    c.client.chat.completions.create.return_value = _respuesta(" ")
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_VACIO


def test_sin_choices_es_vacio():
    c = _cliente()
    c.client.chat.completions.create.return_value = SimpleNamespace(choices=[])
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_VACIO


def test_api_error_tipificado():
    c = _cliente()
    c.client.chat.completions.create.side_effect = APIError("boom", request=_REQ, body=None)
    r = c.completar([{"role": "user", "content": "hi"}])
    assert r.ok is False
    assert r.codigo_error == LLM_ERROR


def test_error_no_api_propaga():
    # Tras el cleanup (E2), un error inesperado (no-API) es un bug y DEBE propagarse, no ocultarse.
    c = _cliente()
    c.client.chat.completions.create.side_effect = ValueError("bug inesperado")
    with pytest.raises(ValueError):
        c.completar([{"role": "user", "content": "hi"}])
