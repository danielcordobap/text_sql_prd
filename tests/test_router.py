"""Validación del router de intención (). .

 convirtió `nodo_router` de un matcher de keywords a una clasificación por LLM
(`ROUTER_PROMPT` + `ROUTER_MODEL_ID`). Cubren: el mapeo de `_clasificar_intencion`, la
degradación total a SQL (router inactivo, excepción, respuesta no-ok/irreconocible), la
eliminación del falso positivo por substring (H-02) y el aislamiento del cerebro SQL en viz.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.brain.generador import ResultadoGeneracion
from src.graph.agente import _clasificar_intencion, conversar, nodo_router, ruta_router
from src.llm.client import RespuestaLLM
from src.sql.executor import ResultadoEjecucion


def _settings_router(router_model_id: str = "router-lite") -> SimpleNamespace:
    return SimpleNamespace(
        router_model_id=router_model_id,
        model_id="main-model",
        max_correcciones_sql=2,
        conversation_window=6,
    )


# --- _clasificar_intencion: mapeo con prioridad y sesgo a SQL ---


def test_clasificar_intencion_mapea_las_tres_categorias() -> None:
    assert _clasificar_intencion("VISUALIZACION") == "VISUALIZACION"
    assert _clasificar_intencion("EXPLICACION") == "EXPLICACION"
    assert _clasificar_intencion("SQL") == "SQL"


def test_clasificar_intencion_tolera_verboso_y_sesga_a_sql() -> None:
    assert _clasificar_intencion("The category is VISUALIZACION.") == "VISUALIZACION"
    assert _clasificar_intencion("respuesta irreconocible") == "SQL" # sesgo a SQL


# --- nodo_router: clasificación por LLM + degradación total a SQL ---


def test_router_inactivo_sin_modelo_va_a_sql_sin_llamar_llm() -> None:
    llm = MagicMock()
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router(router_model_id="")),
        patch("src.graph.agente.completar", llm),
    ):
        assert nodo_router({"pregunta": "download in excel"})["intencion"] == "SQL" # type: ignore[typeddict-item]
    llm.assert_not_called() # short-circuit: nunca llama al LLM


def test_router_falso_positivo_download_eliminado() -> None:
    # H-02 cerrado: "downloaded" ya NO fuerza VISUALIZACION; manda la decisión del LLM (SQL).
    llm = MagicMock(return_value=RespuestaLLM(ok=True, contenido="SQL"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.completar", llm),
    ):
        r = nodo_router({"pregunta": "how many clients downloaded the app last month"}) # type: ignore[typeddict-item]
    assert r["intencion"] == "SQL"


def test_router_clasifica_visualizacion_por_llm() -> None:
    llm = MagicMock(return_value=RespuestaLLM(ok=True, contenido="VISUALIZACION"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.completar", llm),
    ):
        assert nodo_router({"pregunta": "graficar ventas"})["intencion"] == "VISUALIZACION" # type: ignore[typeddict-item]


def test_router_degrada_a_sql_si_llm_no_ok() -> None:
    llm = MagicMock(return_value=RespuestaLLM(ok=False, codigo_error="LLM_ERROR"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.completar", llm),
    ):
        assert nodo_router({"pregunta": "algo"})["intencion"] == "SQL" # type: ignore[typeddict-item]


def test_router_degrada_a_sql_si_completar_lanza() -> None:
    # Guardia try/except: el router nunca tumba conversar aunque completar lance.
    llm = MagicMock(side_effect=RuntimeError("boom"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.completar", llm),
    ):
        assert nodo_router({"pregunta": "algo"})["intencion"] == "SQL" # type: ignore[typeddict-item]


def test_ruta_router_mapea_intencion() -> None:
    assert ruta_router({"intencion": "VISUALIZACION"}) == "asesor_visual" # type: ignore[typeddict-item]
    assert ruta_router({"intencion": "SQL"}) == "generar" # type: ignore[typeddict-item]
    assert ruta_router({"intencion": "EXPLICACION"}) == "generar" # type: ignore[typeddict-item]
    assert ruta_router({"intencion": None}) == "generar" # type: ignore[typeddict-item]


# --- integración por conversar: aislamiento del cerebro SQL en la ruta viz ---


def test_viz_no_invoca_cerebro_sql() -> None:
    gen = MagicMock()
    ejec = MagicMock()
    router_llm = MagicMock(return_value=RespuestaLLM(ok=True, contenido="VISUALIZACION"))
    asesor = MagicMock()
    asesor.completar.return_value = RespuestaLLM(
        ok=True, contenido="Use the Download CSV / Download Excel buttons."
    )
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.completar", router_llm),
        patch("src.graph.agente.generar_sql", gen),
        patch("src.graph.agente.ejecutar_consulta", ejec),
        patch("src.graph.agente.ClienteLLM", return_value=asesor),
    ):
        r = conversar("download this in excel", "t-viz-iso-b")
    assert r.ok is True
    assert r.tipo == "mensaje"
    gen.assert_not_called() # el generador T-SQL nunca corre
    ejec.assert_not_called() # no se ejecuta SQL contra la BD


def test_sql_path_no_invoca_asesor_visual() -> None:
    gen = MagicMock(return_value=ResultadoGeneracion(ok=True, sql="SELECT 1"))
    ejec = MagicMock(
        return_value=ResultadoEjecucion(ok=True, columnas=["a"], filas=[{"a": 1}], n_filas=1)
    )
    router_llm = MagicMock(return_value=RespuestaLLM(ok=True, contenido="SQL"))
    asesor = MagicMock()
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.completar", router_llm),
        patch("src.graph.agente.generar_sql", gen),
        patch("src.graph.agente.ejecutar_consulta", ejec),
        patch("src.graph.agente.ClienteLLM", return_value=asesor),
    ):
        r = conversar("top 5 productos", "t-sql-path-b")
    assert r.ok is True
    assert r.n_filas == 1
    asesor.completar.assert_not_called() # el asesor visual no se cuela en la ruta SQL


def test_viz_fallback_cuando_llm_no_ok() -> None:
    router_llm = MagicMock(return_value=RespuestaLLM(ok=True, contenido="VISUALIZACION"))
    asesor = MagicMock()
    asesor.completar.return_value = RespuestaLLM(ok=False, codigo_error="LLM_ERROR")
    with (
        patch("src.graph.agente.get_settings", return_value=_settings_router()),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.completar", router_llm),
        patch("src.graph.agente.ClienteLLM", return_value=asesor),
    ):
        r = conversar("descargar en excel por favor", "t-viz-fb-b")
    assert r.ok is True
    assert "descargar" in (r.mensaje or "").lower() # fallback en español, sin crash
