"""Tests para el validador de seguridad SQL."""

from src.sql.validator import (
    MULTIPLES_SENTENCIAS,
    NO_ES_CONSULTA_DATOS,
    NO_ES_SELECT,
    OPERACION_PROHIBIDA,
    PARSE_ERROR,
    TABLA_O_COLUMNA_DESCONOCIDA,
    validar_sql,
)

ESQUEMA_PRUEBA: dict[str, set[str]] = {
    "ventas": {"id", "monto", "fecha", "cliente_id"},
    "clientes": {"cliente_id", "nombre_cliente"},
}


def test_select_top_valido() -> None:
    """Prueba SELECT válido con TOP explícito."""
    res = validar_sql("SELECT TOP 10 * FROM ventas")
    assert res.ok is True
    assert res.sql_seguro is not None
    assert "TOP 10" in res.sql_seguro.upper()
    assert res.codigo_error is None


def test_select_sin_top_inyecta_limite() -> None:
    """Prueba que un SELECT sin TOP inyecta TOP max_filas."""
    res = validar_sql("SELECT * FROM ventas", max_filas=100)
    assert res.ok is True
    assert res.sql_seguro is not None
    assert "TOP 100" in res.sql_seguro.upper()
    assert res.codigo_error is None


def test_drop_table_prohibido() -> None:
    """Prueba que DROP TABLE es rechazado como OPERACION_PROHIBIDA."""
    res = validar_sql("DROP TABLE ventas")
    assert res.ok is False
    assert res.codigo_error == OPERACION_PROHIBIDA
    assert res.sql_seguro is None


def test_delete_prohibido() -> None:
    """Prueba que DELETE es rechazado como OPERACION_PROHIBIDA."""
    res = validar_sql("DELETE FROM ventas")
    assert res.ok is False
    assert res.codigo_error == OPERACION_PROHIBIDA


def test_multiples_sentencias_rechazado() -> None:
    """Prueba que múltiples sentencias se rechazan con MULTIPLES_SENTENCIAS."""
    res = validar_sql("SELECT * FROM ventas; DROP TABLE ventas")
    assert res.ok is False
    assert res.codigo_error == MULTIPLES_SENTENCIAS


def test_select_into_prohibido() -> None:
    """Prueba que SELECT INTO se rechaza como OPERACION_PROHIBIDA."""
    res = validar_sql("SELECT * INTO copia FROM ventas")
    assert res.ok is False
    assert res.codigo_error == OPERACION_PROHIBIDA


def test_select_top_excesivo_se_reduce() -> None:
    """Prueba que un TOP mayor a max_filas se reduce a max_filas."""
    res = validar_sql("SELECT TOP 999999 * FROM ventas", max_filas=100)
    assert res.ok is True
    assert res.sql_seguro is not None
    assert "TOP 100" in res.sql_seguro.upper()


def test_sys_tables_sin_esquema_prohibido() -> None:
    """Prueba que consultar sys.tables sin esquema se rechaza como OPERACION_PROHIBIDA."""
    res = validar_sql("SELECT * FROM sys.tables")
    assert res.ok is False
    assert res.codigo_error == OPERACION_PROHIBIDA


def test_tabla_inexistente_con_esquema() -> None:
    """Prueba que una tabla no presente en el esquema retorna TABLA_O_COLUMNA_DESCONOCIDA."""
    res = validar_sql("SELECT * FROM tabla_inexistente", esquema=ESQUEMA_PRUEBA)
    assert res.ok is False
    assert res.codigo_error == TABLA_O_COLUMNA_DESCONOCIDA


def test_columna_inexistente_con_esquema() -> None:
    """Prueba que una columna no presente en el esquema retorna TABLA_O_COLUMNA_DESCONOCIDA."""
    res = validar_sql("SELECT columna_fantasma FROM ventas", esquema=ESQUEMA_PRUEBA)
    assert res.ok is False
    assert res.codigo_error == TABLA_O_COLUMNA_DESCONOCIDA


def test_sql_invalido_parse_error() -> None:
    """Prueba que un string que no es SQL retorna PARSE_ERROR."""
    res = validar_sql("esto no es sql")
    assert res.ok is False
    assert res.codigo_error == PARSE_ERROR


def test_sql_vacio_parse_error() -> None:
    """Prueba que un string vacío o espacios retorna PARSE_ERROR."""
    res = validar_sql(" ")
    assert res.ok is False
    assert res.codigo_error == PARSE_ERROR


def test_join_con_alias_y_esquema_valido() -> None:
    """Prueba JOIN complejo con alias y columnas válidas contra esquema."""
    sql = "SELECT c.nombre_cliente FROM clientes c JOIN ventas v ON v.cliente_id=c.cliente_id"
    res = validar_sql(sql, esquema=ESQUEMA_PRUEBA)
    assert res.ok is True
    assert res.sql_seguro is not None


def test_no_es_select_expresion() -> None:
    """Prueba expresión literal no-SELECT retorna NO_ES_SELECT o OPERACION_PROHIBIDA."""
    res = validar_sql("1 + 1")
    assert res.ok is False
    assert res.codigo_error in (NO_ES_SELECT, PARSE_ERROR)


def test_alias_calculado_del_select_es_valido() -> None:
    """HOTFIX: un alias del SELECT (AS mes) usado en ORDER BY no es columna desconocida."""
    sql = (
        "SELECT MONTH(fecha) AS mes, COUNT(*) AS total "
        "FROM ventas GROUP BY MONTH(fecha) ORDER BY mes"
    )
    res = validar_sql(sql, esquema=ESQUEMA_PRUEBA)
    assert res.ok is True
    assert res.codigo_error is None


def test_hotfix_no_debilita_seguridad_drop_con_esquema() -> None:
    """El HOTFIX de alias NO abre la puerta: DROP sigue prohibido con esquema activo."""
    res = validar_sql("DROP TABLE ventas", esquema=ESQUEMA_PRUEBA)
    assert res.ok is False
    assert res.codigo_error == OPERACION_PROHIBIDA


def test_hotfix_no_debilita_seguridad_multi_sentencia_con_esquema() -> None:
    """El HOTFIX de alias NO abre la puerta: multi-statement sigue rechazado con esquema."""
    res = validar_sql("SELECT id FROM ventas; DROP TABLE ventas", esquema=ESQUEMA_PRUEBA)
    assert res.ok is False
    assert res.codigo_error == MULTIPLES_SENTENCIAS


def test_select_null_rechazado() -> None:
    """SELECT NULL (sin tabla) se rechaza — mata el truco del modelo."""
    res = validar_sql("SELECT NULL")
    assert res.ok is False
    assert res.codigo_error == NO_ES_CONSULTA_DATOS


def test_select_escalar_sin_tabla_rechazado() -> None:
    """un SELECT sin tabla (SELECT 1) se rechaza como NO_ES_CONSULTA_DATOS."""
    res = validar_sql("SELECT 1")
    assert res.ok is False
    assert res.codigo_error == NO_ES_CONSULTA_DATOS


def test_subconsulta_escalar_con_tabla_es_valida() -> None:
    """el check de 'ninguna tabla' NO rechaza un escalar con tabla en subconsulta."""
    res = validar_sql("SELECT (SELECT COUNT(*) FROM ventas) AS total", esquema=ESQUEMA_PRUEBA)
    assert res.ok is True
