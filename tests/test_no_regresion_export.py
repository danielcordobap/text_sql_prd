"""No-regresión de montar el export NO altera /v1/consultar ni invoca el grafo."""

from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api.main import app
from src.sql.executor import ResultadoEjecucion

client = TestClient(app)


def test_openapi_consultar_sigue_presente() -> None:
    paths = app.openapi()["paths"]
    assert "/v1/consultar" in paths
    assert "post" in paths["/v1/consultar"]
    assert "/v1/exportar" in paths # el export se montó, aparte


def test_consulta_response_schema_intacto() -> None:
    """El contrato de ConsultaResponse no cambió al montar el export."""
    schema: dict[str, Any] = app.openapi()["components"]["schemas"]["ConsultaResponse"]
    props = set(schema["properties"].keys())
    assert props == {
        "thread_id",
        "ok",
        "sql",
        "columnas",
        "filas",
        "n_filas",
        "truncado",
        "codigo_error",
        "mensaje",
        "tipo",
    }


def test_export_no_invoca_el_grafo() -> None:
    """El export nunca llama a conversar (aislado del cerebro/memoria)."""
    with (
        patch("src.api.export.esquema_columnas", return_value={}),
        patch(
            "src.api.export.ejecutar_consulta",
            return_value=ResultadoEjecucion(ok=True, columnas=["a"], filas=[{"a": 1}], n_filas=1),
        ),
        patch("src.graph.agente.conversar") as mock_conversar,
    ):
        client.post("/v1/exportar", json={"sql": "SELECT a FROM ventas", "formato": "csv"})
    mock_conversar.assert_not_called()
