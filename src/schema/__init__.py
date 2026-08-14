"""Paquete de gestión e introspección del esquema de la base de datos."""

from src.schema.descripciones import (
    DESCRIPCIONES_COLUMNAS,
    DESCRIPCIONES_TABLAS,
    RELACIONES,
)
from src.schema.loader import (
    esquema_columnas,
    esquema_para_prompt,
    introspeccionar,
)

__all__ = [
    "DESCRIPCIONES_COLUMNAS",
    "DESCRIPCIONES_TABLAS",
    "RELACIONES",
    "esquema_columnas",
    "esquema_para_prompt",
    "introspeccionar",
]
