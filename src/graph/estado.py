"""Módulo de definición del estado del grafo LangGraph para el agente text-to-SQL."""

from typing import Any, TypedDict


class EstadoAgente(TypedDict):
    """Estado del grafo LangGraph para el agente text-to-SQL."""

    pregunta: str
    idioma: str
    historial: list[dict[str, str]]
    sql: str | None
    error_sql: str | None
    intentos: int
    intencion: str | None
    respuesta: dict[str, Any] | None


__all__ = [
    "EstadoAgente",
]
