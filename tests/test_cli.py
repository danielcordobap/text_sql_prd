"""Pruebas de la CLI (función de formateo)."""

from src.brain.orquestador import Respuesta
from src.cli import formatear_respuesta


def test_formatear_ok_con_filas():
    r = Respuesta(
        ok=True,
        sql="SELECT a, b FROM t",
        columnas=["a", "b"],
        filas=[{"a": 1, "b": 2}, {"a": 3, "b": 4}],
        n_filas=2,
    )
    txt = formatear_respuesta(r)
    assert "SELECT a, b FROM t" in txt
    assert "a | b" in txt
    assert "1 | 2" in txt
    assert "3 | 4" in txt


def test_formatear_ok_sin_filas():
    r = Respuesta(ok=True, sql="SELECT 1 WHERE 1=0", columnas=[], filas=[], n_filas=0)
    assert "Sin resultados." in formatear_respuesta(r)


def test_formatear_error():
    r = Respuesta(ok=False, codigo_error="SIN_SQL", mensaje="falta info")
    assert formatear_respuesta(r) == "No se pudo responder [SIN_SQL]: falta info"
