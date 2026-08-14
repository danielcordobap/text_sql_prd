"""Módulo ejecutor de consultas SQL con validación estricta previo a la ejecución."""

from typing import Any

import pyodbc
from pydantic import BaseModel

from src.config.settings import get_settings
from src.db.connection import ConexionBDError, get_connection
from src.sql.validator import (
    MULTIPLES_SENTENCIAS,
    NO_ES_SELECT,
    OPERACION_PROHIBIDA,
    PARSE_ERROR,
    TABLA_O_COLUMNA_DESCONOCIDA,
    validar_sql,
)

# Nuevas constantes de error para ejecución en BD
EJECUCION_BD = "EJECUCION_BD"
EJECUCION_SQL = "EJECUCION_SQL"


class ResultadoEjecucion(BaseModel):
    """Modelo de resultado estandarizado para la ejecución de consultas SQL."""

    ok: bool
    columnas: list[str] = []
    filas: list[dict[str, Any]] = []
    n_filas: int = 0
    sql_ejecutado: str | None = None
    codigo_error: str | None = None
    mensaje: str | None = None


def ejecutar_consulta(
    sql: str,
    esquema: dict[str, set[str]] | None = None,
    max_filas: int | None = None,
) -> ResultadoEjecucion:
    """Ejecuta una consulta SQL previa validación estricta sobre la conexión de solo lectura."""
    limite = max_filas if max_filas is not None else get_settings().sql_max_rows

    # 1. Validar SIEMPRE antes de ejecutar
    res_val = validar_sql(sql, esquema, limite)
    if not res_val.ok or not res_val.sql_seguro:
        return ResultadoEjecucion(
            ok=False,
            codigo_error=res_val.codigo_error,
            mensaje=res_val.mensaje,
        )

    # 2. Ejecutar la consulta validada y segura sobre la conexión de solo lectura
    try:
        with get_connection() as cn:
            cn.timeout = get_settings().db_read_timeout_seconds
            cursor = cn.cursor()
            cursor.execute(res_val.sql_seguro)

            if cursor.description is None:
                return ResultadoEjecucion(
                    ok=True,
                    columnas=[],
                    filas=[],
                    n_filas=0,
                    sql_ejecutado=res_val.sql_seguro,
                )

            columnas = [d[0] for d in cursor.description]
            filas_raw = cursor.fetchall()
            filas = [dict(zip(columnas, fila, strict=False)) for fila in filas_raw]

            return ResultadoEjecucion(
                ok=True,
                columnas=columnas,
                filas=filas,
                n_filas=len(filas),
                sql_ejecutado=res_val.sql_seguro,
            )

    except ConexionBDError as e:
        return ResultadoEjecucion(
            ok=False,
            codigo_error=EJECUCION_BD,
            mensaje=str(e),
        )
    except pyodbc.Error as e:
        return ResultadoEjecucion(
            ok=False,
            codigo_error=EJECUCION_SQL,
            mensaje=f"Error al ejecutar la consulta SQL en la base de datos: {e}",
        )


__all__ = [
    "EJECUCION_BD",
    "EJECUCION_SQL",
    "MULTIPLES_SENTENCIAS",
    "NO_ES_SELECT",
    "OPERACION_PROHIBIDA",
    "PARSE_ERROR",
    "TABLA_O_COLUMNA_DESCONOCIDA",
    "ResultadoEjecucion",
    "ejecutar_consulta",
]
