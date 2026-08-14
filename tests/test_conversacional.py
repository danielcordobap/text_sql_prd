"""contrato de respuesta conversacional (tipo = datos | mensaje).

Cubre el hueco: los 124 tests previos no ejercen el flujo `tipo="mensaje"` del asesor visual
a través de la API, la CLI y el grafo. Verifica que el mensaje se hace visible y que la
sanitización de datos/errores NO cambia (no-regresión).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from src.api.main import app
from src.brain.orquestador import Respuesta
from src.cli import formatear_respuesta
from src.graph.agente import conversar
from src.llm.client import RespuestaLLM

client = TestClient(app)


def _mensaje_resp(texto: str = "Use the Download CSV / Download Excel buttons.") -> Respuesta:
    """Respuesta conversacional pura del asesor visual: ok, sin filas, tipo mensaje."""
    return Respuesta(
        ok=True, sql=None, columnas=[], filas=[], n_filas=0, tipo="mensaje", mensaje=texto
    )


# --- API: el mensaje del asesor sobrevive cuando tipo="mensaje" ---


def test_api_preserva_mensaje_conversacional() -> None:
    with patch("src.api.main.conversar", return_value=_mensaje_resp()):
        r = client.post("/v1/consultar", json={"pregunta": "download in excel"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["tipo"] == "mensaje"
    assert body["mensaje"] == "Use the Download CSV / Download Excel buttons."


# --- API no-regresión: una respuesta de datos sigue con mensaje=None y tipo=datos ---


def test_api_datos_sigue_sin_mensaje() -> None:
    datos = Respuesta(ok=True, sql="SELECT 1", columnas=["a"], filas=[{"a": 1}], n_filas=1)
    with patch("src.api.main.conversar", return_value=datos):
        r = client.post("/v1/consultar", json={"pregunta": "cuantos"})
    assert r.status_code == 200
    body = r.json()
    assert body["tipo"] == "datos"
    assert body["mensaje"] is None


# --- API no-regresión: error de infra sigue sin exponer el mensaje crudo ---


def test_api_error_infra_no_expone_mensaje() -> None:
    bd = Respuesta(ok=False, codigo_error="EJECUCION_BD", mensaje="detalle crudo interno")
    with patch("src.api.main.conversar", return_value=bd):
        r = client.post("/v1/consultar", json={"pregunta": "algo"})
    assert r.status_code == 503
    assert "detalle crudo interno" not in r.text


# --- CLI: imprime el mensaje conversacional; los datos no cambian ---


def test_cli_imprime_mensaje_conversacional() -> None:
    r = _mensaje_resp("Puedes descargar en Excel o CSV con los botones.")
    assert formatear_respuesta(r) == "Puedes descargar en Excel o CSV con los botones."


def test_cli_datos_no_regresion() -> None:
    r = Respuesta(ok=True, sql="SELECT 1", columnas=["a"], filas=[{"a": 1}], n_filas=1)
    txt = formatear_respuesta(r)
    assert "SELECT 1" in txt
    assert "Sin resultados." not in txt


# --- Grafo: la ruta viz produce una Respuesta con tipo="mensaje" ---


def test_conversar_viz_produce_tipo_mensaje() -> None:
    # Router LLM clasifica VISUALIZACION; el asesor produce el mensaje.
    settings = SimpleNamespace(
        router_model_id="router-lite",
        model_id="main-model",
        max_correcciones_sql=2,
        conversation_window=6,
    )
    router_llm = MagicMock(return_value=RespuestaLLM(ok=True, contenido="VISUALIZACION"))
    asesor = MagicMock()
    asesor.completar.return_value = RespuestaLLM(ok=True, contenido="Use the Download buttons.")
    with (
        patch("src.graph.agente.get_settings", return_value=settings),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.completar", router_llm),
        patch("src.graph.agente.ClienteLLM", return_value=asesor),
    ):
        r = conversar("download this in excel", "t-ho017a-viz")
    assert r.ok is True
    assert r.tipo == "mensaje"
    assert r.mensaje == "Use the Download buttons."
