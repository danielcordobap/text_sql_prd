"""Validador de seguridad SQL (allowlist SELECT-only para T-SQL)."""

from typing import Final

import sqlglot
from pydantic import BaseModel
from sqlglot import exp
from sqlglot.errors import SqlglotError

# Códigos de error tipificados
PARSE_ERROR: Final[str] = "PARSE_ERROR"
MULTIPLES_SENTENCIAS: Final[str] = "MULTIPLES_SENTENCIAS"
NO_ES_SELECT: Final[str] = "NO_ES_SELECT"
OPERACION_PROHIBIDA: Final[str] = "OPERACION_PROHIBIDA"
TABLA_O_COLUMNA_DESCONOCIDA: Final[str] = "TABLA_O_COLUMNA_DESCONOCIDA"
NO_ES_CONSULTA_DATOS: Final[str] = "NO_ES_CONSULTA_DATOS"

_WRITE_COMMANDS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Create,
    exp.Command,
    exp.Grant,
    exp.Execute,
    exp.Merge,
)


class ResultadoValidacion(BaseModel):
    """Resultado de la validación de una consulta SQL."""

    ok: bool
    sql_seguro: str | None = None
    codigo_error: str | None = None
    mensaje: str | None = None


def _parsear_sentencia(
    sql: str,
) -> tuple[exp.Expression | None, ResultadoValidacion | None]:
    """Parsea el string SQL y valida que sea una única sentencia."""
    if not sql or not sql.strip():
        return None, ResultadoValidacion(
            ok=False,
            codigo_error=PARSE_ERROR,
            mensaje="El string SQL está vacío.",
        )

    try:
        raw_sentencias = sqlglot.parse(sql, dialect="tsql")
    except SqlglotError as e:
        return None, ResultadoValidacion(
            ok=False,
            codigo_error=PARSE_ERROR,
            mensaje=f"Error de parseo SQL: {e}",
        )

    valid_sentencias = [s for s in raw_sentencias if isinstance(s, exp.Expression)]
    if not valid_sentencias:
        return None, ResultadoValidacion(
            ok=False,
            codigo_error=PARSE_ERROR,
            mensaje="No se encontraron sentencias SQL válidas.",
        )

    if len(valid_sentencias) > 1:
        return None, ResultadoValidacion(
            ok=False,
            codigo_error=MULTIPLES_SENTENCIAS,
            mensaje="Se detectaron múltiples sentencias SQL.",
        )

    return valid_sentencias[0], None


def _validar_tipo_select(expresion: exp.Expression) -> ResultadoValidacion | None:
    """Verifica que la expresión sea un SELECT y no contenga operaciones prohibidas."""
    if not isinstance(expresion, exp.Select):
        if isinstance(expresion, _WRITE_COMMANDS):
            cmd_name = type(expresion).__name__
            return ResultadoValidacion(
                ok=False,
                codigo_error=OPERACION_PROHIBIDA,
                mensaje=f"Operación prohibida de modificación o administración: {cmd_name}.",
            )
        return ResultadoValidacion(
            ok=False,
            codigo_error=NO_ES_SELECT,
            mensaje="La sentencia no es una consulta SELECT.",
        )

    if expresion.find(exp.Into) is not None:
        return ResultadoValidacion(
            ok=False,
            codigo_error=OPERACION_PROHIBIDA,
            mensaje="La cláusula SELECT INTO está prohibida porque crea o modifica tablas.",
        )

    if expresion.find(*_WRITE_COMMANDS) is not None:
        return ResultadoValidacion(
            ok=False,
            codigo_error=OPERACION_PROHIBIDA,
            mensaje="La consulta contiene sub-operaciones prohibidas.",
        )

    if not list(expresion.find_all(exp.Table)):
        return ResultadoValidacion(
            ok=False,
            codigo_error=NO_ES_CONSULTA_DATOS,
            mensaje="La consulta no referencia ninguna tabla del esquema.",
        )

    return None


def _validar_metadatos_sistema(expresion: exp.Expression) -> ResultadoValidacion | None:
    """Verifica que no se acceda a metadatos de sistema (sys / INFORMATION_SCHEMA)."""
    for t in expresion.find_all(exp.Table):
        db_name = (t.db or "").lower()
        table_name = t.name.lower()
        if (
            db_name in ("sys", "information_schema")
            or table_name.startswith("sys.")
            or table_name.startswith("information_schema.")
        ):
            msg = "Acceso a metadatos del sistema (sys / INFORMATION_SCHEMA) no permitido."
            return ResultadoValidacion(
                ok=False,
                codigo_error=OPERACION_PROHIBIDA,
                mensaje=msg,
            )
    return None


def _validar_columnas(
    expresion: exp.Expression,
    schema_norm: dict[str, set[str]],
    table_aliases: dict[str, str],
    ctes: set[str],
    select_aliases: set[str] | None = None,
) -> ResultadoValidacion | None:
    """Valida que las columnas referenciadas existan en el esquema o sean alias válidos."""
    aliases_set = select_aliases or set()
    all_schema_columns = {col for cols in schema_norm.values() for col in cols}
    for col in expresion.find_all(exp.Column):
        if col.this == exp.Star() or col.name == "*":
            continue
        col_name = col.name.lower()
        table_qualifier = col.table.lower() if col.table else None

        if table_qualifier:
            if table_qualifier in ctes:
                continue
            if table_qualifier in table_aliases:
                real_table = table_aliases[table_qualifier]
                if col_name not in schema_norm[real_table]:
                    return ResultadoValidacion(
                        ok=False,
                        codigo_error=TABLA_O_COLUMNA_DESCONOCIDA,
                        mensaje=f"Columna '{col.name}' desconocida en tabla '{real_table}'.",
                    )
            else:
                return ResultadoValidacion(
                    ok=False,
                    codigo_error=TABLA_O_COLUMNA_DESCONOCIDA,
                    mensaje=f"Alias de tabla desconocido '{col.table}' en columna '{col.name}'.",
                )
        elif col_name not in all_schema_columns and col_name not in aliases_set:
            return ResultadoValidacion(
                ok=False,
                codigo_error=TABLA_O_COLUMNA_DESCONOCIDA,
                mensaje=f"Columna '{col.name}' no existe en el esquema.",
            )
    return None


def _validar_esquema(
    expresion: exp.Expression,
    esquema: dict[str, set[str]],
) -> ResultadoValidacion | None:
    """Verifica que las tablas y columnas referenciadas existan en el esquema dado."""
    schema_norm = {t.lower(): {c.lower() for c in cols} for t, cols in esquema.items()}
    ctes = {cte.alias_or_name.lower() for cte in expresion.find_all(exp.CTE)}
    # Tablas derivadas (subconsultas con alias en el FROM): sus columnas calificadas por el
    # alias son alias de proyección, NO columnas de esquema. Se saltan SOLO en la validación
    # de columnas (más abajo), NUNCA en el bucle de existencia de tablas: un alias de
    # subconsulta jamás es exp.Table, así que meterlo aquí dejaría colar una tabla real
    # prohibida (sys.*) o inexistente cuyo nombre coincida con el alias. Las columnas
    # internas de la subconsulta SÍ se validan por find_all(exp.Column).
    derived_aliases = {
        sq.alias_or_name.lower() for sq in expresion.find_all(exp.Subquery) if sq.alias_or_name
    }

    table_aliases: dict[str, str] = {}
    for t in expresion.find_all(exp.Table):
        t_name = t.name.lower()
        if t_name not in ctes:
            if t_name not in schema_norm:
                return ResultadoValidacion(
                    ok=False,
                    codigo_error=TABLA_O_COLUMNA_DESCONOCIDA,
                    mensaje=f"Tabla desconocida: {t.name}",
                )
            alias = t.alias_or_name.lower()
            table_aliases[alias] = t_name
            table_aliases[t_name] = t_name

    select_aliases = {
        a.alias_or_name.lower() for a in expresion.find_all(exp.Alias) if a.alias_or_name
    }

    return _validar_columnas(
        expresion, schema_norm, table_aliases, ctes | derived_aliases, select_aliases
    )


def _aplicar_limite_top(expresion: exp.Select, max_filas: int) -> exp.Select:
    """Aplica o ajusta la cláusula TOP/LIMIT al SELECT."""
    limit_node = expresion.args.get("limit")
    if limit_node is None:
        return expresion.limit(max_filas)

    try:
        current_limit = int(limit_node.expression.this)
        if current_limit > max_filas:
            return expresion.limit(max_filas)
    except (ValueError, TypeError, AttributeError):
        return expresion.limit(max_filas)

    return expresion


def validar_sql(
    sql: str,
    esquema: dict[str, set[str]] | None = None,
    max_filas: int = 100,
) -> ResultadoValidacion:
    """Valida un string SQL y asegura que sea un SELECT seguro sin efectos secundarios."""
    expresion, err_res = _parsear_sentencia(sql)
    if err_res is not None or expresion is None:
        return err_res or ResultadoValidacion(
            ok=False,
            codigo_error=PARSE_ERROR,
            mensaje="Error al procesar la sentencia.",
        )

    err_select = _validar_tipo_select(expresion)
    if err_select is not None:
        return err_select

    err_meta = _validar_metadatos_sistema(expresion)
    if err_meta is not None:
        return err_meta

    if esquema is not None:
        err_esq = _validar_esquema(expresion, esquema)
        if err_esq is not None:
            return err_esq

    select_exp = expresion
    if isinstance(select_exp, exp.Select):
        select_exp = _aplicar_limite_top(select_exp, max_filas)

    sql_seguro = select_exp.sql(dialect="tsql")
    return ResultadoValidacion(ok=True, sql_seguro=sql_seguro)
