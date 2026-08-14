"""Módulo de validación, seguridad y ejecución de consultas SQL."""

from src.sql.executor import (
    EJECUCION_BD,
    EJECUCION_SQL,
    ResultadoEjecucion,
    ejecutar_consulta,
)
from src.sql.validator import (
    MULTIPLES_SENTENCIAS,
    NO_ES_CONSULTA_DATOS,
    NO_ES_SELECT,
    OPERACION_PROHIBIDA,
    PARSE_ERROR,
    TABLA_O_COLUMNA_DESCONOCIDA,
    ResultadoValidacion,
    validar_sql,
)

__all__ = [
    "EJECUCION_BD",
    "EJECUCION_SQL",
    "MULTIPLES_SENTENCIAS",
    "NO_ES_CONSULTA_DATOS",
    "NO_ES_SELECT",
    "OPERACION_PROHIBIDA",
    "PARSE_ERROR",
    "ResultadoEjecucion",
    "ResultadoValidacion",
    "TABLA_O_COLUMNA_DESCONOCIDA",
    "ejecutar_consulta",
    "validar_sql",
]
