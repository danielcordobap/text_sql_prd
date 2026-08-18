"""Módulo del agente LangGraph con orquestación multi-agente y memoria conversacional."""

import logging
from typing import Any, cast

import sqlglot
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.brain.generador import generar_sql
from src.brain.orquestador import Respuesta
from src.config.settings import get_settings
from src.db.connection import ConexionBDError
from src.graph.estado import EstadoAgente
from src.graph.nodos_auxiliares import (
    _clasificar_intencion,
    nodo_asesor_visual,
    nodo_finalizar,
    nodo_router,
)
from src.graph.rutas import (
    ruta_inicio,
    ruta_router,
    ruta_tras_aclarar,
    ruta_tras_ejecutar,
    ruta_tras_generar,
    ruta_tras_groundear,
)
from src.grounding import (
    emparejar,
    extraer_literales_groundables,
    procesar_decision_grounding,
    reescribir_literal_pendiente,
    resolver_ordinal,
)
from src.lang.detector import detectar_idioma
from src.llm.client import ClienteLLM, RespuestaLLM, completar
from src.schema.loader import esquema_columnas, esquema_para_prompt
from src.schema.valores import valores_distintos
from src.sql.executor import ejecutar_consulta

logger = logging.getLogger(__name__)


def nodo_generar(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Generador SQL: traduce lenguaje natural a consulta T-SQL."""
    historial, error_previo, s = (
        estado.get("historial") or [],
        estado.get("error_sql"),
        get_settings(),
    )

    def _cliente_generacion(mensajes: list[dict[str, str]]) -> RespuestaLLM:
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
        return {"sql": gen.sql, "respuesta": None}

    resp = Respuesta(ok=False, sql=gen.sql, codigo_error=gen.codigo_error, mensaje=gen.mensaje)
    return {"sql": None, "respuesta": resp.model_dump(mode="json")}


def nodo_groundear(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Groundear: analiza y empareja literales del SQL contra el catálogo de la BD."""
    s = get_settings()
    if not s.grounding_habilitado or not estado.get("sql"):
        return {}

    sql_str = cast(str, estado.get("sql"))
    try:
        expresion = sqlglot.parse_one(sql_str, read="tsql")
        literales = extraer_literales_groundables(expresion)
        if not literales:
            return {}

        hubo_cambio_ast, notas_substitucion = False, []
        for tabla, columna, val_original, lit_node in literales:
            umbral_col = s.grounding_umbral_por_columna.get(columna, s.grounding_umbral)
            res = emparejar(
                val_original,
                valores_distintos(tabla, columna),
                umbral=umbral_col,
                piso=s.grounding_piso,
                margen=s.grounding_margen,
                k=s.grounding_k,
            )
            sql_parcial = expresion.sql(dialect="tsql")
            ret_aclaracion, cambio, nota = procesar_decision_grounding(
                res,
                tabla,
                columna,
                val_original,
                lit_node,
                sql_parcial,
                estado["pregunta"],
                estado.get("idioma", "es"),
            )
            if cambio:
                hubo_cambio_ast = True
            if nota:
                notas_substitucion.append(nota)
            if ret_aclaracion:
                ret_aclaracion["sql"] = sql_parcial if hubo_cambio_ast else sql_str
                return ret_aclaracion

        if hubo_cambio_ast:
            res_dict: dict[str, Any] = {"sql": expresion.sql(dialect="tsql")}
            if notas_substitucion:
                prefix = "Note: " if estado.get("idioma", "es") == "en" else "Nota: "
                res_dict["nota_grounding"] = prefix + ", ".join(notas_substitucion)
            return res_dict
    except Exception as e:  # noqa: BLE001
        logger.warning("Excepción en nodo_groundear; passthrough a ejecutar: %s", e)

    return {}


def nodo_aclarar(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Aclarar: procesa la respuesta ante una aclaración previa (R-F, R-G2, N-3)."""
    pendiente = estado.get("pendiente_aclaracion")
    if not pendiente:
        return {}

    pregunta, candidatos = estado["pregunta"], pendiente.get("candidatos") or []
    columna_pendiente = pendiente.get("columna", "")
    literal_original = pendiente.get("literal_original", "")
    sql_original = pendiente.get("sql_original")
    pregunta_original = pendiente.get("pregunta_original", pregunta)

    eleccion = resolver_ordinal(pregunta, candidatos)
    if not eleccion and candidatos:
        s = get_settings()
        res = emparejar(
            pregunta,
            candidatos,
            umbral=s.grounding_aclaracion_umbral,
            piso=s.grounding_aclaracion_piso,
        )
        if res.decision in ("SUBSTITUIR", "EJECUTAR_DIRECTO") and res.mejor_match:
            eleccion = res.mejor_match

    if eleccion and sql_original:
        try:
            sql_reescrito = reescribir_literal_pendiente(
                sql_original, columna_pendiente, literal_original, eleccion
            )
            return {
                "sql": sql_reescrito,
                "pregunta": pregunta_original,
                "pendiente_aclaracion": None,
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("Fallo al reescribir SQL en nodo_aclarar: %s", e)

    return {"pendiente_aclaracion": None, "sql": None}


def nodo_ejecutar(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Ejecutor SQL: valida y ejecuta la consulta sobre Azure SQL Server."""
    sql = estado.get("sql")
    if sql is None:
        return {}

    res = ejecutar_consulta(sql, esquema=esquema_columnas())
    nota_val = estado.get("nota_grounding")
    msg_nota: str | None = nota_val if isinstance(nota_val, str) else None

    if res.ok:
        resp = Respuesta(
            ok=True,
            sql=sql,
            columnas=res.columnas,
            filas=res.filas,
            n_filas=res.n_filas,
            tipo="datos",
            nota=msg_nota,
        )
        return {"respuesta": resp.model_dump(mode="json")}

    intentos = estado.get("intentos", 0) + 1
    resp = Respuesta(ok=False, sql=sql, codigo_error=res.codigo_error, mensaje=res.mensaje)
    return {
        "error_sql": res.mensaje,
        "intentos": intentos,
        "respuesta": resp.model_dump(mode="json"),
    }


builder = StateGraph(EstadoAgente)
for n, fn in [
    ("router", nodo_router),
    ("generar", nodo_generar),
    ("groundear", nodo_groundear),
    ("ejecutar", nodo_ejecutar),
    ("aclarar", nodo_aclarar),
    ("asesor_visual", nodo_asesor_visual),
    ("finalizar", nodo_finalizar),
]:
    builder.add_node(n, cast(Any, fn))

for src_node, route_fn, dest_map in [
    (START, ruta_inicio, {"aclarar": "aclarar", "router": "router"}),
    ("aclarar", ruta_tras_aclarar, {"groundear": "groundear", "router": "router"}),
    ("router", ruta_router, {"generar": "generar", "asesor_visual": "asesor_visual"}),
    ("generar", ruta_tras_generar, {"finalizar": "finalizar", "groundear": "groundear"}),
    ("groundear", ruta_tras_groundear, {"finalizar": "finalizar", "ejecutar": "ejecutar"}),
    ("ejecutar", ruta_tras_ejecutar, {"generar": "generar", "finalizar": "finalizar"}),
]:
    builder.add_conditional_edges(src_node, route_fn, cast(Any, dest_map))

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
        "nota_grounding": None,
    }

    config = {"configurable": {"thread_id": thread_id}}
    final = cast(dict[str, Any], grafo.invoke(cast(Any, entrada), config=cast(Any, config)))
    resp_dict = final.get("respuesta")
    if isinstance(resp_dict, dict):
        return Respuesta.model_validate(resp_dict)

    return Respuesta(
        ok=False,
        codigo_error="ERROR_INTERNO",
        mensaje="El grafo finalizó sin producir una respuesta.",
    )


__all__ = [
    "ClienteLLM",
    "_clasificar_intencion",
    "completar",
    "conversar",
    "ejecutar_consulta",
    "esquema_columnas",
    "esquema_para_prompt",
    "generar_sql",
    "get_settings",
    "grafo",
    "nodo_aclarar",
    "nodo_asesor_visual",
    "nodo_ejecutar",
    "nodo_finalizar",
    "nodo_generar",
    "nodo_groundear",
    "nodo_router",
    "ruta_inicio",
    "ruta_router",
    "ruta_tras_aclarar",
    "ruta_tras_ejecutar",
    "ruta_tras_generar",
    "ruta_tras_groundear",
]
