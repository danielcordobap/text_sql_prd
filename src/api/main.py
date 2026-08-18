"""Módulo principal del backend FastAPI para la API web text-to-SQL."""

import logging
import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.export import router as export_router
from src.brain.orquestador import Respuesta
from src.config.settings import get_settings
from src.graph.agente import conversar
from src.grounding.matcher import Candidato

logger = logging.getLogger(__name__)


class ConsultaRequest(BaseModel):
    """Modelo de solicitud para el endpoint /v1/consultar."""

    pregunta: str
    thread_id: str | None = None


class ConsultaResponse(BaseModel):
    """Modelo de respuesta para el endpoint /v1/consultar."""

    thread_id: str
    ok: bool
    sql: str | None = None
    columnas: list[str] = []
    filas: list[dict[str, Any]] = []
    n_filas: int = 0
    truncado: bool = False
    codigo_error: str | None = None
    mensaje: str | None = None
    tipo: Literal["datos", "mensaje", "aclaracion"] = "datos"
    candidatos: list[Candidato] = []
    nota: str | None = None


def _msg_seguro(r: Respuesta) -> str | None:
    """Mapea un mensaje de error seguro orientado al usuario según el código de error."""
    if r.ok:
        return r.mensaje if r.tipo in ("mensaje", "aclaracion") else None

    # Mapeo de errores de infraestructura a mensajes genéricos seguros
    if r.codigo_error in ("EJECUCION_BD", "EJECUCION_SQL", "ERROR_INTERNO"):
        return "Error al procesar la consulta en la base de datos."

    # Para errores de dominio (ej. SIN_SQL, TABLA_O_COLUMNA_DESCONOCIDA, NO_ES_SELECT, etc.)
    return r.mensaje


app = FastAPI(title="Text-to-SQL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition", "X-Export-Truncated"],
)

app.include_router(export_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Endpoint de verificación de estado de la API."""
    return {"status": "ok"}


@app.post("/v1/consultar")
def consultar(req: ConsultaRequest) -> ConsultaResponse:
    """Endpoint principal para realizar consultas en lenguaje natural."""
    tid = req.thread_id or str(uuid.uuid4())
    r = conversar(req.pregunta, tid)

    if not r.ok:
        # Loguear siempre la causa raíz cruda con logger.error
        logger.error(
            "Fallo en consulta text-to-SQL [thread_id=%s, codigo=%s]: %s",
            tid,
            r.codigo_error,
            r.mensaje,
        )

        # Mapeo de errores de infraestructura a excepciones HTTP
        if r.codigo_error == "EJECUCION_BD":
            raise HTTPException(
                status_code=503,
                detail="Servicio de base de datos no disponible temporalmente.",
            )
        if r.codigo_error == "ERROR_INTERNO":
            raise HTTPException(
                status_code=500,
                detail="Error interno del servidor.",
            )

    msg = _msg_seguro(r)

    return ConsultaResponse(
        thread_id=tid,
        ok=r.ok,
        sql=r.sql,
        columnas=r.columnas,
        filas=r.filas,
        n_filas=r.n_filas,
        truncado=(r.n_filas >= get_settings().sql_max_rows),
        codigo_error=r.codigo_error,
        mensaje=msg,
        tipo=r.tipo,
        candidatos=r.candidatos,
        nota=r.nota,
    )


__all__ = [
    "ConsultaRequest",
    "ConsultaResponse",
    "app",
    "consultar",
    "health",
]
