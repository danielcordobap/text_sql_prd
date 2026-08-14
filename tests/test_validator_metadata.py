"""tablas derivadas + bloqueo de metadatos incondicional. .

Prueba el validador CONTRA EL CÓDIGO APLICADO (determinista, sin LLM ni BD): recupera el falso
positivo #9 y cierra los bypasses de metadatos por colisión de alias (subconsulta y CTE) que las
lentes cazaron. Producción SIEMPRE pasa esquema, así que todos los casos usan `esquema`.
"""

from src.sql.validator import (
    OPERACION_PROHIBIDA,
    TABLA_O_COLUMNA_DESCONOCIDA,
    validar_sql,
)

# Esquema mínimo real (descripciones.py). Sin sys/INFORMATION_SCHEMA ni "secretos".
ESQUEMA = {
    "ventas": {
        "venta_id", "ticket_id", "fecha", "cliente_id", "tienda_id",
        "producto_id", "cantidad", "precio_unitario", "descuento", "total_linea",
    },
    "productos": {
        "producto_id", "nombre_producto", "categoria_id", "proveedor_id",
        "precio_unitario", "unidad_medida",
    },
    "tiendas": {"tienda_id", "nombre_tienda", "ciudad"},
}


# --- #9 recuperado: tabla derivada con alias en el FROM ---


def test_tabla_derivada_recupera_9() -> None:
    sql = (
        "SELECT t.total FROM "
        "(SELECT ticket_id, SUM(cantidad) AS total FROM ventas GROUP BY ticket_id) AS t"
    )
    r = validar_sql(sql, esquema=ESQUEMA)
    assert r.ok is True, f"debería pasar; dio {r.codigo_error}: {r.mensaje}"


def test_columna_interna_falsa_en_subconsulta_rechazada() -> None:
    # Las columnas REALES dentro de la subconsulta se siguen validando.
    sql = "SELECT t.x FROM (SELECT columna_falsa AS x FROM ventas) AS t"
    r = validar_sql(sql, esquema=ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == TABLA_O_COLUMNA_DESCONOCIDA


# --- bypasses de metadatos por colisión de alias: CERRADOS ---


def test_bypass_sys_por_colision_alias_subconsulta_rechazado() -> None:
    # El alias 'tables' de la subconsulta NO debe eximir a sys.tables.
    sql = "SELECT * FROM sys.tables JOIN (SELECT 1 AS q FROM ventas) AS tables ON 1=1"
    r = validar_sql(sql, esquema=ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == OPERACION_PROHIBIDA


def test_bypass_information_schema_por_colision_rechazado() -> None:
    sql = (
        "SELECT columns.x FROM INFORMATION_SCHEMA.columns "
        "JOIN (SELECT 1 AS x FROM ventas) AS columns ON 1=1"
    )
    r = validar_sql(sql, esquema=ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == OPERACION_PROHIBIDA


def test_bypass_metadatos_por_colision_cte_rechazado() -> None:
    # Latente pre-existente: el mismo truco con CTE también queda cerrado (metadata incondicional).
    sql = "WITH tables AS (SELECT 1 AS q FROM ventas) SELECT * FROM sys.tables JOIN tables ON 1=1"
    r = validar_sql(sql, esquema=ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == OPERACION_PROHIBIDA


def test_metadatos_directos_con_esquema_rechazados() -> None:
    # EDIT 3: el bloqueo de metadatos ahora corre SIEMPRE (antes solo con esquema=None).
    r = validar_sql("SELECT name FROM sys.tables", esquema=ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == OPERACION_PROHIBIDA


def test_tabla_inexistente_por_colision_alias_rechazada() -> None:
    # Tabla fuera de esquema ('secretos') no debe colarse por colisión con un alias.
    sql = "SELECT * FROM secretos JOIN (SELECT 1 AS q FROM ventas) AS secretos ON 1=1"
    r = validar_sql(sql, esquema=ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == TABLA_O_COLUMNA_DESCONOCIDA


# --- sin regresión ---


def test_consulta_normal_sin_subconsulta_ok() -> None:
    r = validar_sql("SELECT COUNT(*) AS n FROM productos", esquema=ESQUEMA)
    assert r.ok is True


def test_drop_sigue_rechazado() -> None:
    r = validar_sql("DROP TABLE productos", esquema=ESQUEMA)
    assert r.ok is False
