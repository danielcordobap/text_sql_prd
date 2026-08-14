"""Pruebas del ejecutor SQL."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pyodbc
from src.db.connection import ConexionBDError
from src.sql.executor import EJECUCION_BD, EJECUCION_SQL, ejecutar_consulta

_ESQUEMA = {"productos": {"nombre_producto"}}


def _factory_conexion(mock_cn):
    """Devuelve un reemplazo de get_connection: un context manager real que cede mock_cn."""

    @contextmanager
    def _cm():
        yield mock_cn

    return _cm


def _mock_conexion(columnas, filas):
    cn = MagicMock()
    cur = MagicMock()
    cur.description = [(c,) for c in columnas]
    cur.fetchall.return_value = filas
    cn.cursor.return_value = cur
    return cn


def test_sql_invalido_no_abre_conexion():
    with patch("src.sql.executor.get_connection") as mock_gc:
        r = ejecutar_consulta("DROP TABLE ventas")
    assert r.ok is False
    assert r.codigo_error == "OPERACION_PROHIBIDA"
    mock_gc.assert_not_called() # jamás toca la BD si el validador rechaza


def test_select_valido_devuelve_filas():
    cn = _mock_conexion(["nombre_producto"], [("Leche",), ("Pan",)])
    with patch("src.sql.executor.get_connection", _factory_conexion(cn)):
        r = ejecutar_consulta("SELECT nombre_producto FROM productos", esquema=_ESQUEMA)
    assert r.ok is True
    assert r.columnas == ["nombre_producto"]
    assert r.n_filas == 2
    assert r.filas[0] == {"nombre_producto": "Leche"}
    assert r.sql_ejecutado is not None and "TOP" in r.sql_ejecutado.upper()


def test_conexion_bd_error_tipificado():
    with patch("src.sql.executor.get_connection", side_effect=ConexionBDError("sin conexión")):
        r = ejecutar_consulta("SELECT nombre_producto FROM productos", esquema=_ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == EJECUCION_BD


def test_pyodbc_error_en_ejecucion_tipificado():
    cn = MagicMock()
    cur = MagicMock()
    cur.execute.side_effect = pyodbc.Error("fallo al ejecutar")
    cn.cursor.return_value = cur
    with patch("src.sql.executor.get_connection", _factory_conexion(cn)):
        r = ejecutar_consulta("SELECT nombre_producto FROM productos", esquema=_ESQUEMA)
    assert r.ok is False
    assert r.codigo_error == EJECUCION_SQL
