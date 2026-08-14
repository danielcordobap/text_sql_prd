"""Módulo orquestador del pipeline text-to-SQL (generar -> validar -> ejecutar)."""

from typing import Any, Literal

from pydantic import BaseModel

from src.brain.generador import generar_sql
from src.db.connection import ConexionBDError
from src.schema.loader import esquema_columnas, esquema_para_prompt
from src.sql.executor import ejecutar_consulta


class Respuesta(BaseModel):
    """Modelo de respuesta estandarizado de la orquestación text-to-SQL."""

    ok: bool
    sql: str | None = None
    columnas: list[str] = []
    filas: list[dict[str, Any]] = []
    n_filas: int = 0
    codigo_error: str | None = None
    mensaje: str | None = None
    tipo: Literal["datos", "mensaje"] = "datos"


def responder(pregunta: str) -> Respuesta:
    """Orquesta el flujo completo NL -> SQL -> Validación -> Ejecución en BD."""
    try:
        esquema_txt = esquema_para_prompt()
        cols = esquema_columnas()
    except ConexionBDError as e:
        return Respuesta(ok=False, codigo_error="EJECUCION_BD", mensaje=str(e))

    gen = generar_sql(pregunta, esquema_txt)
    if not gen.ok:
        return Respuesta(
            ok=False,
            sql=gen.sql,
            codigo_error=gen.codigo_error,
            mensaje=gen.mensaje,
        )

    if gen.sql is None:
        return Respuesta(
            ok=False,
            sql=None,
            codigo_error=gen.codigo_error,
            mensaje=gen.mensaje,
        )

    res = ejecutar_consulta(gen.sql, esquema=cols)
    if not res.ok:
        return Respuesta(
            ok=False,
            sql=gen.sql,
            codigo_error=res.codigo_error,
            mensaje=res.mensaje,
        )

    return Respuesta(
        ok=True,
        sql=gen.sql,
        columnas=res.columnas,
        filas=res.filas,
        n_filas=res.n_filas,
    )


__all__ = [
    "Respuesta",
    "responder",
]
