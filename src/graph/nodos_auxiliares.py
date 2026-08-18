"""Módulo de nodos auxiliares del grafo LangGraph (router, asesor visual y finalizador)."""

import logging
from typing import Any

from openai import APIError, APITimeoutError, RateLimitError

from src.brain.orquestador import Respuesta
from src.config.settings import get_settings
from src.graph.estado import EstadoAgente
from src.llm.client import ClienteLLM, completar
from src.prompts.orquestacion import (
    MSJ_VIZ_FALLBACK_PROMPT,
    ROUTER_PROMPT,
    VIZ_ADVISOR_PROMPT,
)

logger = logging.getLogger(__name__)


def _clasificar_intencion(texto: str) -> str:
    """Normaliza la salida del clasificador a una categoría del ROUTER_PROMPT."""
    t = texto.upper()
    if "VISUALIZACION" in t:
        return "VISUALIZACION"
    if "EXPLICACION" in t:
        return "EXPLICACION"
    return "SQL"


def _obtener_settings() -> Any:
    import sys

    agente = sys.modules.get("src.graph.agente")
    if agente and hasattr(agente, "get_settings"):
        return agente.get_settings()
    return get_settings()


def _obtener_completar() -> Any:
    import sys

    agente = sys.modules.get("src.graph.agente")
    if agente and hasattr(agente, "completar"):
        return agente.completar
    return completar


def _obtener_cliente_llm() -> Any:
    import sys

    agente = sys.modules.get("src.graph.agente")
    if agente and hasattr(agente, "ClienteLLM"):
        return agente.ClienteLLM
    return ClienteLLM


def nodo_router(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Router: clasifica la intención con un LLM instruct ligero (ROUTER_PROMPT)."""
    modelo_router = _obtener_settings().router_model_id
    if not modelo_router:
        return {"intencion": "SQL"}
    try:
        res = _obtener_completar()(
            [
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": estado["pregunta"]},
            ],
            model=modelo_router,
        )
        if res.ok and res.contenido:
            return {"intencion": _clasificar_intencion(res.contenido)}
    except Exception as e:  # noqa: BLE001
        logger.warning("Router LLM falló; degradando a SQL: %s", e)
    return {"intencion": "SQL"}


def nodo_asesor_visual(estado: EstadoAgente) -> dict[str, Any]:
    """Nodo Asesor Visual: responde consultas sobre descargas y gráficos."""
    idioma = estado.get("idioma", "es")
    idioma_legible = "English" if idioma == "en" else "Español"

    try:
        client = _obtener_cliente_llm()()
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

    if idioma not in MSJ_VIZ_FALLBACK_PROMPT:
        idioma = "es"
    resp = Respuesta(ok=True, tipo="mensaje", mensaje=MSJ_VIZ_FALLBACK_PROMPT[idioma])
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
            resumen = f"[ok] sql={sql} rows={n_filas}" if sql else f"[ok] {mensaje}"
        else:
            resumen = f"[error:{codigo_error}] {mensaje}"

    nuevo_historial: list[dict[str, str]] = historial + [
        {"role": "user", "content": pregunta},
        {"role": "assistant", "content": resumen},
    ]

    ventana = _obtener_settings().conversation_window
    max_mensajes = ventana * 2
    if len(nuevo_historial) > max_mensajes:
        nuevo_historial = nuevo_historial[-max_mensajes:]

    return {"historial": nuevo_historial}
