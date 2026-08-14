"""Router de la API web para exportación de consultas SQL a CSV y XLSX."""

import logging
from datetime import UTC, datetime
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config.settings import get_settings
from src.export.serializers import a_csv, a_xlsx
from src.schema.loader import esquema_columnas
from src.sql.executor import ResultadoEjecucion, ejecutar_consulta

logger = logging.getLogger(__name__)
router = APIRouter()

_DOMINIO = {
    "NO_ES_SELECT",
    "TABLA_O_COLUMNA_DESCONOCIDA",
    "OPERACION_PROHIBIDA",
    "MULTIPLES_SENTENCIAS",
    "NO_ES_CONSULTA_DATOS",
    "PARSE_ERROR",
    "EJECUCION_SQL",
}

_MSG_EXPORT = {
    "NO_ES_SELECT": "Solo se pueden exportar consultas SELECT.",
    "OPERACION_PROHIBIDA": "La consulta contiene una operación no permitida.",
    "MULTIPLES_SENTENCIAS": "Solo se permite una sentencia por exportación.",
    "TABLA_O_COLUMNA_DESCONOCIDA": "La consulta referencia tablas o columnas inexistentes.",
    "NO_ES_CONSULTA_DATOS": "La consulta no devuelve datos exportables.",
    "PARSE_ERROR": "La consulta no es válida.",
    "EJECUCION_SQL": "No se pudo ejecutar la consulta.",
    "EJECUCION_BD": "No se pudo generar el archivo con esa consulta.",
    "ERROR_INTERNO": "No se pudo generar el archivo con esa consulta.",
}


class ExportRequest(BaseModel):
    """Modelo de solicitud para exportación de datos SQL."""

    sql: str
    formato: Literal["csv", "xlsx"]


def _mensaje_export_seguro(res: ResultadoEjecucion) -> str:
    """Mensaje genérico por código; evita fuga y enumeración de esquema."""
    return _MSG_EXPORT.get(res.codigo_error or "", "No se pudo generar el archivo.")


@router.post("/v1/exportar")
def exportar(req: ExportRequest) -> StreamingResponse:
    """Ejecuta de forma segura una consulta SQL validada y devuelve el resultado descargable."""
    res = ejecutar_consulta(
        req.sql,
        esquema=esquema_columnas(),
        max_filas=get_settings().export_max_rows,
    )
    if not res.ok:
        logger.error("export fallo [%s]: %s", res.codigo_error, res.mensaje)
        codigo = (
            503
            if res.codigo_error == "EJECUCION_BD"
            else (400 if res.codigo_error in _DOMINIO else 500)
        )
        raise HTTPException(status_code=codigo, detail=_mensaje_export_seguro(res))

    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if req.formato == "csv":
        data = a_csv(res.columnas, res.filas)
        media = "text/csv; charset=utf-8"
        ext = "csv"
    else:
        data = a_xlsx(res.columnas, res.filas)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"

    filename = f"export_{ts}.{ext}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if res.n_filas >= get_settings().export_max_rows:
        headers["X-Export-Truncated"] = "true"
    return StreamingResponse(BytesIO(data), media_type=media, headers=headers)


__all__ = [
    "ExportRequest",
    "exportar",
    "router",
]
