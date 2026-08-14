"""Módulo del agente LangGraph con orquestación multi-agente y memoria conversacional."""

import logging
from typing import Any, cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from openai import APIError, APITimeoutError, RateLimitError

from src.brain.generador import generar_sql
from src.brain.orquestador import Respuesta
from src.config.settings import get_settings
from src.db.connection import ConexionBDError
from src.graph.estado import EstadoAgente
from src.lang.detector import detectar_idioma
from src.llm.client import ClienteLLM, RespuestaLLM, completar
from src.prompts.orquestacion import ROUTER_PROMPT, VIZ_ADVISOR_PROMPT
from src.schema.loader import esquema_columnas, esquema_para_prompt
from src.sql.executor import ejecutar_consulta

logger = logging.getLogger(__name__)


def _clasificar_intencion(texto: str) -> str:
    """Normaliza la salida del clasificador a una categoría del ROUTER_PROMPT.

    Prioridad VISUALIZACION > EXPLICACION > SQL para tolerar salidas verbosas;
    ante cualquier ambigüedad se sesga a SQL (la función principal del sistema).
    """
    t = texto.upper()
    if "VISUALIZACION" in t:
        return "VISUALIZACION"
    if "EXPLICACION" in t:
        return "EXPLICACION"
    return "SQL"


def nodo_router(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Router: clasifica la intención con un LLM instruct ligero (ROUTER_PROMPT).

    Degradación total a "SQL" (la función principal) en tres casos, para que un router
    indisponible NUNCA bloquee la generación de datos:
      1. `router_model_id` sin configurar → router inactivo.
      2. La llamada LLM lanza una excepción de cualquier tipo.
      3. La respuesta es no-ok, vacía o de categoría irreconocible.
    NO se usa el modelo razonador por defecto: su fallback a `reasoning` metería prosa
    de razonamiento al clasificador (falso positivo). Requiere un modelo instruct ligero.
    """
    modelo_router = get_settings().router_model_id
    if not modelo_router:
        return {"intencion": "SQL"}
    try:
        res = completar(
            [
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": estado["pregunta"]},
            ],
            model=modelo_router,
        )
    except Exception as e:  # noqa: BLE001 — degradación defensiva: el router nunca bloquea
        logger.warning("Router LLM falló; degradando a SQL: %s", e)
        return {"intencion": "SQL"}
    if res.ok and res.contenido:
        return {"intencion": _clasificar_intencion(res.contenido)}
    return {"intencion": "SQL"}


def nodo_generar(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Generador SQL: traduce lenguaje natural a consulta T-SQL."""
    historial = estado.get("historial") or []
    error_previo = estado.get("error_sql")
    s = get_settings()

    def _cliente_generacion(mensajes: list[dict[str, str]]) -> RespuestaLLM:
        # Determinismo SOLO en la generación de SQL (ADR-007): modelo instruct + seed + pineo.
        return ClienteLLM(s).completar(
            mensajes,
            model=s.sql_gen_model_id or None,
            seed=s.sql_gen_seed,
            top_p=s.sql_gen_top_p if s.sql_gen_seed is not None else None,
            provider=s.sql_gen_provider or None,
        )

    gen = generar_sql(
        estado["pregunta"],
        idioma=estado.get("idioma", "es"),
        historial=historial,
        error_previo=error_previo,
        cliente=_cliente_generacion,
    )
    if gen.ok:
        return {"sql": gen.sql}

    resp = Respuesta(
        ok=False,
        sql=gen.sql,
        codigo_error=gen.codigo_error,
        mensaje=gen.mensaje,
    )
    return {"sql": None, "respuesta": resp.model_dump(mode="json")}


def nodo_ejecutar(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Ejecutor SQL: valida y ejecuta la consulta sobre Azure SQL Server."""
    sql = estado.get("sql")
    if sql is None:
        return {}

    cols = esquema_columnas()
    res = ejecutar_consulta(sql, esquema=cols)

    if res.ok:
        resp = Respuesta(
            ok=True,
            sql=sql,
            columnas=res.columnas,
            filas=res.filas,
            n_filas=res.n_filas,
        )
        return {"respuesta": resp.model_dump(mode="json")}

    intentos = estado.get("intentos", 0) + 1
    resp = Respuesta(
        ok=False,
        sql=sql,
        codigo_error=res.codigo_error,
        mensaje=res.mensaje,
    )
    return {
        "error_sql": res.mensaje,
        "intentos": intentos,
        "respuesta": resp.model_dump(mode="json"),
    }


def nodo_asesor_visual(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Asesor Visual: responde consultas sobre descargas y gráficos."""
    idioma = estado.get("idioma", "es")
    idioma_legible = "English" if idioma == "en" else "Español"

    try:
        client = ClienteLLM()
        res = client.completar(
            [
                {
                    "role": "system",
                    "content": VIZ_ADVISOR_PROMPT.format(idioma=idioma_legible),
                },
                {"role": "user", "content": estado["pregunta"]},
            ]
        )
        if res.ok and res.contenido:
            resp = Respuesta(ok=True, tipo="mensaje", mensaje=res.contenido)
            return {"respuesta": resp.model_dump(mode="json")}
    except (APIError, APITimeoutError, RateLimitError) as e:
        logger.warning("Fallo en asesor visual LLM: %s", e)

    mensaje_fallback = (
        "You can download the query results to Excel or CSV instantly using "
        "the 'Download CSV' and 'Download Excel' buttons right below the table, "
        "or toggle the interactive chart view using 'Show Chart'."
        if idioma == "en"
        else "Puedes descargar los resultados de la consulta a Excel o CSV "
        "al instante usando los botones 'Download CSV' y 'Download Excel' justo "
        "debajo de la tabla, o activar la vista interactiva usando 'Show Chart'."
    )
    resp = Respuesta(ok=True, tipo="mensaje", mensaje=mensaje_fallback)
    return {"respuesta": resp.model_dump(mode="json")}


def nodo_finalizar(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Finalizador: actualiza y acota la memoria conversacional."""
    historial = list(estado.get("historial") or [])
    pregunta = estado.get("pregunta", "")
    respuesta = estado.get("respuesta")

    resumen = ""
    if respuesta is not None:
        ok = respuesta.get("ok", False)
        sql = respuesta.get("sql")
        n_filas = respuesta.get("n_filas", 0)
        codigo_error = respuesta.get("codigo_error")
        mensaje = respuesta.get("mensaje")

        if ok:
            if sql:
                resumen = f"[ok] sql={sql} rows={n_filas}"
            else:
                resumen = f"[ok] {mensaje}"
        else:
            resumen = f"[error:{codigo_error}] {mensaje}"

    nuevo_historial: list[dict[str, str]] = historial + [
        {"role": "user", "content": pregunta},
        {"role": "assistant", "content": resumen},
    ]

    ventana = get_settings().conversation_window
    max_mensajes = ventana * 2
    if len(nuevo_historial) > max_mensajes:
        nuevo_historial = nuevo_historial[-max_mensajes:]

    return {"historial": nuevo_historial}


def ruta_router(estado: EstadoAgente) -> str:
    """Ruta condicional tras el nodo router."""
    intencion = estado.get("intencion")
    if intencion == "VISUALIZACION":
        return "asesor_visual"
    return "generar"


def ruta_tras_generar(estado: EstadoAgente) -> str:
    """Determina la ruta tras intentar generar el SQL."""
    if estado.get("sql") is None:
        return "finalizar"
    return "ejecutar"


def ruta_tras_ejecutar(estado: EstadoAgente) -> str:
    """Determina la ruta tras intentar ejecutar la consulta SQL."""
    resp = estado.get("respuesta")
    if resp is not None and resp.get("ok"):
        return "finalizar"

    max_correcciones = get_settings().max_correcciones_sql
    intentos = estado.get("intentos", 0)
    if intentos < max_correcciones:
        return "generar"

    return "finalizar"


builder = StateGraph(EstadoAgente)
builder.add_node("router", cast(Any, nodo_router))
builder.add_node("generar", cast(Any, nodo_generar))
builder.add_node("ejecutar", cast(Any, nodo_ejecutar))
builder.add_node("asesor_visual", cast(Any, nodo_asesor_visual))
builder.add_node("finalizar", cast(Any, nodo_finalizar))

builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    ruta_router,
    {"generar": "generar", "asesor_visual": "asesor_visual"},
)
builder.add_conditional_edges(
    "generar",
    ruta_tras_generar,
    {"finalizar": "finalizar", "ejecutar": "ejecutar"},
)
builder.add_conditional_edges(
    "ejecutar",
    ruta_tras_ejecutar,
    {"generar": "generar", "finalizar": "finalizar"},
)
builder.add_edge("asesor_visual", "finalizar")
builder.add_edge("finalizar", END)

checkpointer = MemorySaver()
grafo = builder.compile(checkpointer=checkpointer)


def conversar(pregunta: str, thread_id: str) -> Respuesta:
    """Maneja una conversación interactiva con orquestación multi-agente."""
    try:
        _ = esquema_para_prompt()
        _ = esquema_columnas()
    except ConexionBDError as e:
        return Respuesta(ok=False, codigo_error="EJECUCION_BD", mensaje=str(e))

    entrada: dict[str, Any] = {
        "pregunta": pregunta,
        "idioma": detectar_idioma(pregunta),
        "sql": None,
        "error_sql": None,
        "intentos": 0,
        "intencion": None,
        "respuesta": None,
    }

    config = {"configurable": {"thread_id": thread_id}}
    final = cast(
        dict[str, Any],
        grafo.invoke(cast(Any, entrada), config=cast(Any, config)),
    )

    resp_dict = final.get("respuesta")
    if isinstance(resp_dict, dict):
        return Respuesta.model_validate(resp_dict)

    return Respuesta(
        ok=False,
        codigo_error="ERROR_INTERNO",
        mensaje="El grafo finalizó sin producir una respuesta.",
    )


__all__ = [
    "conversar",
    "grafo",
]
