"""Pruebas del orquestador text-to-SQL."""

from unittest.mock import patch

from src.brain.generador import ResultadoGeneracion
from src.brain.orquestador import responder
from src.db.connection import ConexionBDError
from src.sql.executor import ResultadoEjecucion


def test_responder_happy_path():
    gen = ResultadoGeneracion(ok=True, sql="SELECT TOP 3 nombre_producto FROM productos")
    ex = ResultadoEjecucion(
        ok=True, columnas=["nombre_producto"], filas=[{"nombre_producto": "Leche"}], n_filas=1
    )
    with (
        patch("src.brain.orquestador.esquema_para_prompt", return_value="ESQUEMA"),
        patch(
            "src.brain.orquestador.esquema_columnas",
            return_value={"productos": {"nombre_producto"}},
        ),
        patch("src.brain.orquestador.generar_sql", return_value=gen),
        patch("src.brain.orquestador.ejecutar_consulta", return_value=ex),
    ):
        r = responder("dame 3 productos")
    assert r.ok is True
    assert r.sql == gen.sql
    assert r.n_filas == 1
    assert r.filas == [{"nombre_producto": "Leche"}]


def test_responder_falla_generacion():
    gen = ResultadoGeneracion(ok=False, codigo_error="SIN_SQL", mensaje="falta info")
    with (
        patch("src.brain.orquestador.esquema_para_prompt", return_value="ESQUEMA"),
        patch("src.brain.orquestador.esquema_columnas", return_value={}),
        patch("src.brain.orquestador.generar_sql", return_value=gen),
    ):
        r = responder("pregunta ambigua")
    assert r.ok is False
    assert r.codigo_error == "SIN_SQL"


def test_responder_falla_ejecucion_incluye_sql():
    gen = ResultadoGeneracion(ok=True, sql="SELECT foo FROM bar")
    ex = ResultadoEjecucion(
        ok=False, codigo_error="TABLA_O_COLUMNA_DESCONOCIDA", mensaje="no existe"
    )
    with (
        patch("src.brain.orquestador.esquema_para_prompt", return_value="ESQUEMA"),
        patch("src.brain.orquestador.esquema_columnas", return_value={}),
        patch("src.brain.orquestador.generar_sql", return_value=gen),
        patch("src.brain.orquestador.ejecutar_consulta", return_value=ex),
    ):
        r = responder("x")
    assert r.ok is False
    assert r.codigo_error == "TABLA_O_COLUMNA_DESCONOCIDA"
    assert r.sql == "SELECT foo FROM bar"


def test_responder_bd_caida():
    with patch("src.brain.orquestador.esquema_para_prompt", side_effect=ConexionBDError("caída")):
        r = responder("x")
    assert r.ok is False
    assert r.codigo_error == "EJECUCION_BD"
