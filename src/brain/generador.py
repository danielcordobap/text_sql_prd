"""Módulo de generación de SQL a partir de lenguaje natural."""

import re
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel

from src.db.connection import ConexionBDError
from src.llm.client import RespuestaLLM, completar
from src.prompts.generacion_sql import construir_mensajes
from src.schema.loader import esquema_para_prompt

SIN_SQL = "SIN_SQL"
SENTINELA_NO_SQL = "NO_SQL:"
_RE_NO_SQL = re.compile(r"\s*NO_SQL\s*:(.*)", re.IGNORECASE | re.DOTALL)


def detectar_no_sql(texto: str) -> str | None:
    """Detecta el centinela NO_SQL al inicio de la respuesta y devuelve la explicación."""
    if not texto:
        return None
    match = _RE_NO_SQL.match(texto)
    if not match:
        return None
    mensaje = match.group(1).strip()
    return mensaje or "No es posible responder esta pregunta con el esquema disponible."


class ResultadoGeneracion(BaseModel):
    """Modelo de resultado estandarizado para la generación de SQL."""

    ok: bool
    sql: str | None = None
    codigo_error: str | None = None
    mensaje: str | None = None


def extraer_sql(texto: str) -> str | None:
    """Extrae la consulta SQL de la respuesta del modelo de forma robusta."""
    if not texto:
        return None

    # 1. Primer bloque ```sql ... ```
    match_sql = re.search(r"```sql\b(.*?)\s*```", texto, re.DOTALL | re.IGNORECASE)
    if match_sql:
        cand = match_sql.group(1).strip()
        if re.search(r"\bSELECT\b", cand, re.IGNORECASE):
            return cand

    # 2. Bloque genérico ``` ... ```
    match_generic = re.search(r"```\s*(.*?)\s*```", texto, re.DOTALL)
    if match_generic:
        contenido = match_generic.group(1).strip()
        if contenido.lower().startswith("sql"):
            contenido = contenido[3:].strip()
        if contenido and re.search(r"\bSELECT\b", contenido, re.IGNORECASE):
            return contenido

    # 3. Si no hay bloque markdown, buscar una sentencia SELECT en el texto
    match_select = re.search(
        r"\b(SELECT\b[\s\S]+?)(?:;|\. Se obtuvieron|\n\n|\s*$)",
        texto,
        re.IGNORECASE,
    )
    if match_select:
        candidate = match_select.group(1).strip()
        if candidate.endswith("."):
            candidate = candidate[:-1].strip()
        return candidate if candidate else None

    return None


def _limpiar_marcas_markdown(texto: str) -> str:
    """Limpia bloques markdown espurios o comentarios si el LLM no emitió un SELECT."""
    limpio = texto.strip()
    if limpio.startswith("```") and limpio.endswith("```"):
        lineas = limpio.splitlines()
        if len(lineas) >= 2:
            limpio = "\n".join(lineas[1:-1]).strip()
    lineas_limpias = []
    for line in limpio.splitlines():
        if line.strip().startswith("--"):
            lineas_limpias.append(line.strip()[2:].strip())
        else:
            lineas_limpias.append(line)
    return "\n".join(lineas_limpias).strip()


def generar_sql(
    pregunta: str,
    esquema_texto: str | None = None,
    idioma: str = "es",
    historial: list[dict[str, str]] | None = None,
    error_previo: str | None = None,
    cliente: Callable[[list[dict[str, str]]], RespuestaLLM] | None = None,
) -> ResultadoGeneracion:
    """Genera una consulta SQL a partir de una pregunta en lenguaje natural."""
    try:
        esquema = esquema_texto if esquema_texto is not None else esquema_para_prompt()
    except ConexionBDError as e:
        return ResultadoGeneracion(
            ok=False,
            codigo_error="EJECUCION_BD",
            mensaje=str(e),
        )

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mensajes = construir_mensajes(
        esquema,
        fecha,
        pregunta,
        idioma=idioma,
        historial=historial,
        error_previo=error_previo,
    )

    fn_completar = cliente if cliente is not None else completar
    resp = fn_completar(mensajes)

    if not resp.ok:
        return ResultadoGeneracion(
            ok=False,
            codigo_error=resp.codigo_error,
            mensaje=resp.mensaje,
        )

    if resp.contenido is None:
        return ResultadoGeneracion(
            ok=False,
            codigo_error=resp.codigo_error or SIN_SQL,
            mensaje=resp.mensaje or "El contenido de la respuesta está vacío.",
        )

    mensaje_no_sql = detectar_no_sql(resp.contenido)
    if mensaje_no_sql is not None:
        return ResultadoGeneracion(
            ok=False,
            codigo_error=SIN_SQL,
            mensaje=_limpiar_marcas_markdown(mensaje_no_sql),
        )

    sql = extraer_sql(resp.contenido)
    if sql is None:
        return ResultadoGeneracion(
            ok=False,
            codigo_error=SIN_SQL,
            mensaje=_limpiar_marcas_markdown(resp.contenido),
        )

    return ResultadoGeneracion(ok=True, sql=sql)


__all__ = [
    "SENTINELA_NO_SQL",
    "SIN_SQL",
    "ResultadoGeneracion",
    "detectar_no_sql",
    "extraer_sql",
    "generar_sql",
]
