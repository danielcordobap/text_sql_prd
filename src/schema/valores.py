"""Módulo de catálogo y obtención de valores distintos para grounding de entidades."""

import logging
from functools import lru_cache

from src.db.connection import get_connection

logger = logging.getLogger(__name__)

COLUMNAS_GROUNDABLES: dict[str, set[str]] = {
    "productos": {"nombre_producto", "unidad_medida"},
    "clientes": {"ciudad", "segmento", "nombre_cliente"},
    "tiendas": {"ciudad", "nombre_tienda"},
    "proveedores": {"ciudad", "nombre_proveedor"},
    "categorias": {"nombre_categoria"},
    "movimientos_inventario": {"tipo_movimiento"},
}


@lru_cache
def valores_distintos(tabla: str, columna: str) -> list[str]:
    """Obtiene y cachea la lista de valores distintos de una columna groundable.

    Valida (tabla, columna) contra la allowlist COLUMNAS_GROUNDABLES antes de consultar.
    Degradación graciosa: si la BD falla o no se puede conectar, devuelve [].
    """
    tabla_norm = tabla.strip().lower()
    columna_norm = columna.strip().lower()

    cols = COLUMNAS_GROUNDABLES.get(tabla_norm)
    if not cols or columna_norm not in cols:
        raise ValueError(f"La combinación tabla='{tabla}' / columna='{columna}' no es groundable.")

    # Invariante de seguridad: tabla_norm y columna_norm están validadas contra la allowlist
    query = f"SELECT DISTINCT {columna_norm} FROM dbo.{tabla_norm} WHERE {columna_norm} IS NOT NULL"  # noqa: S608

    try:
        with get_connection() as cn:
            cursor = cn.cursor()
            cursor.execute(query)
            filas = cursor.fetchall()
            return [str(f[0]).strip() for f in filas if f[0] is not None and str(f[0]).strip()]
    except Exception as e:  # noqa: BLE001
        # Degradación graciosa: ante fallo en BD, grounding se trata como SIN_CANDIDATO (retorna [])
        logger.warning("Fallo al obtener valores distintos para %s.%s: %s", tabla, columna, e)
        return []


__all__ = [
    "COLUMNAS_GROUNDABLES",
    "valores_distintos",
]
