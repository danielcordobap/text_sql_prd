"""Módulo de rutas condicionales para la orquestación del grafo LangGraph."""

from typing import Any

from src.config.settings import get_settings


def ruta_inicio(estado: dict[str, Any]) -> str:
    """Ruta condicional inicial desde START."""
    return "aclarar" if estado.get("pendiente_aclaracion") is not None else "router"


def ruta_tras_aclarar(estado: dict[str, Any]) -> str:
    """Ruta condicional tras el nodo aclarar (R-E)."""
    return "groundear" if estado.get("sql") is not None else "router"


def ruta_router(estado: dict[str, Any]) -> str:
    """Ruta condicional tras el nodo router."""
    return "asesor_visual" if estado.get("intencion") == "VISUALIZACION" else "generar"


def ruta_tras_generar(estado: dict[str, Any]) -> str:
    """Determina la ruta tras intentar generar el SQL."""
    return "finalizar" if estado.get("sql") is None else "groundear"


def ruta_tras_groundear(estado: dict[str, Any]) -> str:
    """Determina la ruta tras el nodo groundear."""
    return "finalizar" if estado.get("respuesta") is not None else "ejecutar"


def ruta_tras_ejecutar(estado: dict[str, Any]) -> str:
    """Determina la ruta tras intentar ejecutar la consulta SQL."""
    resp = estado.get("respuesta")
    if resp is not None and resp.get("ok"):
        return "finalizar"
    max_correcciones = get_settings().max_correcciones_sql
    if estado.get("intentos", 0) < max_correcciones:
        return "generar"
    return "finalizar"
