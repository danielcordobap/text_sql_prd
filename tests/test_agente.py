"""Pruebas del agente LangGraph."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.brain.generador import ResultadoGeneracion
from src.graph.agente import conversar
from src.sql.executor import ResultadoEjecucion


def _settings(max_corr: int = 2, window: int = 6) -> SimpleNamespace:
    # router_model_id="" → el router hace short-circuit a SQL sin llamar al LLM.
    return SimpleNamespace(
        max_correcciones_sql=max_corr,
        conversation_window=window,
        router_model_id="",
        model_id="test-model",
        grounding_habilitado=False,
    )


def _ex_ok() -> ResultadoEjecucion:
    return ResultadoEjecucion(ok=True, columnas=["a"], filas=[{"a": 1}], n_filas=1)


def _ex_fail() -> ResultadoEjecucion:
    return ResultadoEjecucion(
        ok=False, codigo_error="TABLA_O_COLUMNA_DESCONOCIDA", mensaje="no existe"
    )


def test_conversar_happy_path():
    with (
        patch("src.graph.agente.get_settings", return_value=_settings()),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch(
            "src.graph.agente.generar_sql",
            return_value=ResultadoGeneracion(ok=True, sql="SELECT 1"),
        ),
        patch("src.graph.agente.ejecutar_consulta", return_value=_ex_ok()),
    ):
        r = conversar("dame algo", "t-happy")
    assert r.ok is True
    assert r.n_filas == 1


def test_autocorreccion_falla_luego_ok():
    ejec = MagicMock(side_effect=[_ex_fail(), _ex_ok()])
    gen = MagicMock(return_value=ResultadoGeneracion(ok=True, sql="SELECT 1"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings(max_corr=2)),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.generar_sql", gen),
        patch("src.graph.agente.ejecutar_consulta", ejec),
    ):
        r = conversar("consulta", "t-retry")
    assert r.ok is True
    assert ejec.call_count == 2 # reintentó una vez
    assert gen.call_count == 2 # regeneró con el error


def test_autocorreccion_limite_duro_no_cicla():
    ejec = MagicMock(return_value=_ex_fail())
    gen = MagicMock(return_value=ResultadoGeneracion(ok=True, sql="SELECT 1"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings(max_corr=2)),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.generar_sql", gen),
        patch("src.graph.agente.ejecutar_consulta", ejec),
    ):
        r = conversar("consulta", "t-limit")
    assert r.ok is False
    assert ejec.call_count == 2 # acotado; sin ciclo infinito


def test_generacion_falla_no_ejecuta():
    ejec = MagicMock()
    with (
        patch("src.graph.agente.get_settings", return_value=_settings()),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch(
            "src.graph.agente.generar_sql",
            return_value=ResultadoGeneracion(ok=False, codigo_error="SIN_SQL", mensaje="falta"),
        ),
        patch("src.graph.agente.ejecutar_consulta", ejec),
    ):
        r = conversar("pregunta ambigua", "t-nosql")
    assert r.ok is False
    assert r.codigo_error == "SIN_SQL"
    ejec.assert_not_called()


def test_memoria_persiste_por_thread_id():
    gen = MagicMock(return_value=ResultadoGeneracion(ok=True, sql="SELECT 1"))
    with (
        patch("src.graph.agente.get_settings", return_value=_settings()),
        patch("src.graph.agente.esquema_para_prompt", return_value="ESQ"),
        patch("src.graph.agente.esquema_columnas", return_value={}),
        patch("src.graph.agente.generar_sql", gen),
        patch("src.graph.agente.ejecutar_consulta", return_value=_ex_ok()),
    ):
        conversar("primera pregunta", "t-mem")
        conversar("segunda pregunta", "t-mem")
    # 1er turno: sin historial previo
    assert gen.call_args_list[0].kwargs["historial"] == []
    # 2do turno: el historial trae el turno anterior (memoria por thread_id)
    hist2 = gen.call_args_list[1].kwargs["historial"]
    assert len(hist2) == 2
    assert hist2[0] == {"role": "user", "content": "primera pregunta"}
