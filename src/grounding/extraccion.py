import re
from typing import Any

import sqlglot
from sqlglot import exp

from src.schema.valores import COLUMNAS_GROUNDABLES

MAPEO_TEXTO_ORDINAL: dict[str, int] = {
    "1": 0,
    "1ro": 0,
    "primer": 0,
    "primero": 0,
    "2": 1,
    "2do": 1,
    "segundo": 1,
    "3": 2,
    "3ro": 2,
    "tercero": 2,
    "4": 3,
    "4to": 3,
    "cuarto": 3,
}

PATRON_ORDINAL = re.compile(
    r"^\s*(?:el\s+)?(1|2|3|4|1ro|2do|3ro|4to|primer|primero|segundo|tercero|cuarto)\s*$",
    re.IGNORECASE,
)


def _resolver_tabla_columna(
    col: exp.Column,
    alias_map: dict[str, str],
    tablas_en_scope: set[str],
) -> tuple[str, str] | None:
    """Resuelve la tupla (tabla, columna) groundable para un nodo exp.Column (R-A, R-C)."""
    if not col.this or not isinstance(col.this.name, str):
        return None
    col_name = col.this.name.lower()
    raw_table = col.table.lower() if col.table else None

    if raw_table:
        real_table = alias_map.get(raw_table, raw_table)
        if real_table in COLUMNAS_GROUNDABLES and col_name in COLUMNAS_GROUNDABLES[real_table]:
            return (real_table, col_name)
        return None

    # Columna sin cualificar -> restringir a tablas_en_scope ∩ COLUMNAS_GROUNDABLES
    tablas_candidatas = [
        t
        for t in (tablas_en_scope & set(COLUMNAS_GROUNDABLES.keys()))
        if col_name in COLUMNAS_GROUNDABLES[t]
    ]
    if len(tablas_candidatas) == 1:
        return (tablas_candidatas[0], col_name)
    if len(tablas_candidatas) == 0 and not tablas_en_scope:
        globales = [t for t, cset in COLUMNAS_GROUNDABLES.items() if col_name in cset]
        if len(globales) == 1:
            return (globales[0], col_name)

    return None


def _extraer_pares_nodo(node: Any) -> list[tuple[exp.Column, exp.Literal]]:
    """Extrae pares (columna, literal) de un nodo AST exp.EQ, exp.In o exp.Like."""
    pares: list[tuple[exp.Column, exp.Literal]] = []
    if isinstance(node, exp.EQ):
        if (
            isinstance(node.left, exp.Column)
            and isinstance(node.right, exp.Literal)
            and node.right.is_string
        ):
            pares.append((node.left, node.right))
        elif (
            isinstance(node.right, exp.Column)
            and isinstance(node.left, exp.Literal)
            and node.left.is_string
        ):
            pares.append((node.right, node.left))
    elif isinstance(node, exp.In) and isinstance(node.this, exp.Column):
        for expr in node.expressions:
            if isinstance(expr, exp.Literal) and expr.is_string:
                pares.append((node.this, expr))
    elif isinstance(node, exp.Like):
        if (
            isinstance(node.this, exp.Column)
            and isinstance(node.expression, exp.Literal)
            and node.expression.is_string
        ):
            pares.append((node.this, node.expression))
    return pares


def extraer_literales_groundables(
    sql_or_ast: Any,
) -> list[tuple[str, str, str, exp.Literal]]:
    """Extrae tuplas (tabla, columna, literal_texto, nodo_literal) del AST SQL (R-A, R-C, R-H)."""
    if isinstance(sql_or_ast, str):
        try:
            expresion = sqlglot.parse_one(sql_or_ast, read="tsql")
        except Exception:  # noqa: BLE001
            return []
    else:
        expresion = sql_or_ast

    alias_map: dict[str, str] = {}
    tablas_en_scope: set[str] = set()
    for t in expresion.find_all(exp.Table):
        if t.name:
            t_name = t.name.lower()
            tablas_en_scope.add(t_name)
            if t.alias:
                alias_map[t.alias.lower()] = t_name

    resultados: list[tuple[str, str, str, exp.Literal]] = []
    for node in expresion.walk():
        pares = _extraer_pares_nodo(node)
        for col, lit in pares:
            res_tc = _resolver_tabla_columna(col, alias_map, tablas_en_scope)
            if res_tc:
                resultados.append((res_tc[0], res_tc[1], str(lit.this), lit))

    return resultados


def reescribir_literal_pendiente(
    sql_original: str,
    columna_pendiente: str,
    literal_original: str,
    eleccion: str,
) -> str:
    """Reescribe SOLO el literal de la columna del pendiente en el AST (R-G2, R-H)."""
    expresion = sqlglot.parse_one(sql_original, read="tsql")
    literales = extraer_literales_groundables(expresion)
    reemplazado = False
    for _t_name, c_name, lit_val, lit_node in literales:
        if c_name == columna_pendiente and lit_val == literal_original:
            lit_node.replace(exp.Literal.string(eleccion))
            reemplazado = True
            break

    if not reemplazado:
        for node in expresion.walk():
            if isinstance(node, exp.Literal) and node.is_string and node.this == literal_original:
                node.replace(exp.Literal.string(eleccion))
                break

    return expresion.sql(dialect="tsql")


def resolver_ordinal(pregunta: str, candidatos: list[str]) -> str | None:
    """Mapea una referencia ordinal anclada ("2", "el segundo", "1ro") a un candidato (N-2)."""
    match = PATRON_ORDINAL.match(pregunta.strip())
    if not match:
        return None
    token = match.group(1).lower()
    idx = MAPEO_TEXTO_ORDINAL.get(token)
    if idx is not None and idx < len(candidatos):
        return candidatos[idx]
    return None


def procesar_decision_grounding(
    res: Any,
    tabla: str,
    columna: str,
    val_original: str,
    lit_node: exp.Literal,
    sql_parcial: str,
    pregunta: str,
    idioma: str,
) -> tuple[dict[str, Any] | None, bool, str | None]:
    """Maneja la decisión de emparejamiento para un literal en nodo_groundear."""
    from src.brain.orquestador import Respuesta
    from src.prompts.orquestacion import MSJ_ACLARACION_PROMPT, MSJ_SIN_COINCIDENCIA_PROMPT

    if (
        res.decision in ("SUBSTITUIR", "EJECUTAR_DIRECTO")
        and res.mejor_match
        and res.mejor_match != val_original
    ):
        lit_node.replace(exp.Literal.string(res.mejor_match))
        if res.decision == "SUBSTITUIR":
            nota = (
                f"interpreted '{val_original}' as '{res.mejor_match}'"
                if idioma == "en"
                else f"interpreté '{val_original}' como '{res.mejor_match}'"
            )
        else:
            nota = None
        return (None, True, nota)

    if res.decision in ("PEDIR_ACLARACION", "SIN_CANDIDATO"):
        lang = idioma if idioma in MSJ_ACLARACION_PROMPT else "es"
        if res.decision == "PEDIR_ACLARACION":
            pendiente = {
                "columna": columna,
                "tabla": tabla,
                "candidatos": [c.valor for c in res.top_k],
                "sql_original": sql_parcial,
                "literal_original": val_original,
                "pregunta_original": pregunta,
            }
            msg = MSJ_ACLARACION_PROMPT[lang].format(columna=columna)
            resp = Respuesta(ok=True, tipo="aclaracion", mensaje=msg, candidatos=res.top_k)
            return (
                {"respuesta": resp.model_dump(mode="json"), "pendiente_aclaracion": pendiente},
                False,
                None,
            )
        else:
            msg = MSJ_SIN_COINCIDENCIA_PROMPT[lang].format(
                val_original=val_original, columna=columna
            )
            resp = Respuesta(ok=False, codigo_error="SIN_COINCIDENCIA", mensaje=msg)
            # SIN_CANDIDATO es error terminal sin pendiente de aclaracion
            return (
                {"respuesta": resp.model_dump(mode="json"), "pendiente_aclaracion": None},
                False,
                None,
            )

    return (None, False, None)


__all__ = [
    "MAPEO_TEXTO_ORDINAL",
    "PATRON_ORDINAL",
    "extraer_literales_groundables",
    "procesar_decision_grounding",
    "reescribir_literal_pendiente",
    "resolver_ordinal",
]
