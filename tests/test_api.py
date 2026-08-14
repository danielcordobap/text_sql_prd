"""Pruebas del backend FastAPI.

Se mockea `conversar` (no se toca BD ni LLM). Foco: contrato de la API, mapeo de códigos a HTTP,
la regla antifuga (no reenviar el error crudo de pyodbc) y el flag `truncado`.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api.main import app
from src.brain.orquestador import Respuesta

client = TestClient(app)


def _resp(**kwargs: Any) -> Respuesta:
    """Construye una Respuesta ok por defecto; los kwargs sobreescriben campos."""
    base: dict[str, Any] = {
        "ok": True,
        "sql": "SELECT 1",
        "columnas": ["a"],
        "filas": [{"a": 1}],
        "n_filas": 1,
    }
    base.update(kwargs)
    return Respuesta(**base)


def test_health_ok() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_consultar_sin_thread_id_genera_uno() -> None:
    with patch("src.api.main.conversar", return_value=_resp()) as m:
        r = client.post("/v1/consultar", json={"pregunta": "algo"})
    assert r.status_code == 200
    body = r.json()
    assert body["thread_id"] # se generó un uuid
    assert body["ok"] is True
    assert m.call_args.args[1] == body["thread_id"] # el tid generado se pasó a conversar


def test_consultar_reenvia_thread_id() -> None:
    with patch("src.api.main.conversar", return_value=_resp()):
        r = client.post("/v1/consultar", json={"pregunta": "algo", "thread_id": "t-fijo"})
    assert r.status_code == 200
    assert r.json()["thread_id"] == "t-fijo"


def test_error_dominio_es_200_ok_false() -> None:
    dom = _resp(
        ok=False,
        sql=None,
        columnas=[],
        filas=[],
        n_filas=0,
        codigo_error="SIN_SQL",
        mensaje="no se pudo generar SQL",
    )
    with patch("src.api.main.conversar", return_value=dom):
        r = client.post("/v1/consultar", json={"pregunta": "ambigua"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["codigo_error"] == "SIN_SQL"


def test_infra_ejecucion_bd_es_503() -> None:
    bd = _resp(ok=False, codigo_error="EJECUCION_BD", mensaje="detalle crudo interno")
    with patch("src.api.main.conversar", return_value=bd):
        r = client.post("/v1/consultar", json={"pregunta": "algo"})
    assert r.status_code == 503


def test_infra_error_interno_es_500() -> None:
    ei = _resp(ok=False, codigo_error="ERROR_INTERNO", mensaje="boom")
    with patch("src.api.main.conversar", return_value=ei):
        r = client.post("/v1/consultar", json={"pregunta": "algo"})
    assert r.status_code == 500


def test_antifuga_no_expone_error_crudo_de_pyodbc() -> None:
    """🔴 El error crudo de pyodbc (driver + nombres de tabla) NO debe llegar al cliente."""
    fuga = _resp(
        ok=False,
        sql=None,
        columnas=[],
        filas=[],
        n_filas=0,
        codigo_error="EJECUCION_SQL",
        mensaje="[Microsoft][ODBC Driver 18] Invalid column name 'xyz' en la tabla ventas",
    )
    with patch("src.api.main.conversar", return_value=fuga):
        r = client.post("/v1/consultar", json={"pregunta": "algo"})
    assert r.status_code == 200 # EJECUCION_SQL: query mala (dominio), no infra
    assert "[Microsoft][ODBC" not in r.text
    assert "ventas" not in r.text
    assert r.json()["codigo_error"] == "EJECUCION_SQL" # el código sí, la traza no


def test_truncado_true_cuando_n_filas_alcanza_el_tope() -> None:
    with (
        patch("src.api.main.get_settings", return_value=SimpleNamespace(sql_max_rows=100)),
        patch("src.api.main.conversar", return_value=_resp(n_filas=100)),
    ):
        r = client.post("/v1/consultar", json={"pregunta": "todo"})
    assert r.status_code == 200
    assert r.json()["truncado"] is True


def test_truncado_false_cuando_hay_menos_filas() -> None:
    with (
        patch("src.api.main.get_settings", return_value=SimpleNamespace(sql_max_rows=100)),
        patch("src.api.main.conversar", return_value=_resp(n_filas=99)),
    ):
        r = client.post("/v1/consultar", json={"pregunta": "pocas"})
    assert r.status_code == 200
    assert r.json()["truncado"] is False


def test_body_invalido_sin_pregunta_es_422() -> None:
    r = client.post("/v1/consultar", json={"thread_id": "t"})
    assert r.status_code == 422
