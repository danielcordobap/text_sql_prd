"""Módulo de introspección del esquema real de la base de datos y formateo para prompts."""

from functools import lru_cache

from src.db.connection import get_connection
from src.schema.descripciones import (
    DESCRIPCIONES_COLUMNAS,
    DESCRIPCIONES_TABLAS,
    RELACIONES,
)


@lru_cache
def introspeccionar() -> dict[str, list[tuple[str, str]]]:
    """Consulta INFORMATION_SCHEMA.COLUMNS y devuelve {tabla: [(columna, tipo), ...]}."""
    query = """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    esquema: dict[str, list[tuple[str, str]]] = {}

    with get_connection() as cn:
        cursor = cn.cursor()
        cursor.execute(query)
        filas = cursor.fetchall()

        for tabla, columna, tipo in filas:
            tabla_str = str(tabla).strip().lower()
            columna_str = str(columna).strip().lower()
            tipo_str = str(tipo).strip().lower()

            if tabla_str not in esquema:
                esquema[tabla_str] = []
            esquema[tabla_str].append((columna_str, tipo_str))

    return esquema


def esquema_columnas() -> dict[str, set[str]]:
    """Deriva el mapa {tabla: {columna, ...}} consumido por el validador SQL."""
    esquema_real = introspeccionar()
    return {tabla: {col for col, _ in cols} for tabla, cols in esquema_real.items()}


def esquema_para_prompt() -> str:
    """Genera la representación textual determinista del esquema y significados para el prompt."""
    esquema_real = introspeccionar()
    lineas: list[str] = ["Esquema de la base de datos:"]

    for tabla in sorted(esquema_real.keys()):
        desc_tabla = DESCRIPCIONES_TABLAS.get(tabla, "")
        encabezado_tabla = f"\nTabla {tabla}"
        if desc_tabla:
            encabezado_tabla += f" — {desc_tabla}"
        lineas.append(f"{encabezado_tabla}:")

        cols_desc = DESCRIPCIONES_COLUMNAS.get(tabla, {})
        for col_name, col_tipo in esquema_real[tabla]:
            desc_col = cols_desc.get(col_name, "")
            linea_col = f"  - {col_name} ({col_tipo})"
            if desc_col:
                linea_col += f": {desc_col}"
            lineas.append(linea_col)

    if RELACIONES:
        lineas.append("\nRelaciones (llaves foráneas):")
        for rel in RELACIONES:
            lineas.append(f"  - {rel}")

    return "\n".join(lineas)


__all__ = [
    "esquema_columnas",
    "esquema_para_prompt",
    "introspeccionar",
]
