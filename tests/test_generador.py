"""Pruebas del generador NL->SQL."""

from src.brain.generador import (
    SIN_SQL,
    ResultadoGeneracion,
    detectar_no_sql,
    extraer_sql,
    generar_sql,
)
from src.llm.client import RespuestaLLM


def _cliente_que_devuelve(texto: str):
    def _fn(_mensajes: list[dict[str, str]]) -> RespuestaLLM:
        return RespuestaLLM(ok=True, contenido=texto)

    return _fn


def test_extraer_sql_bloque_etiquetado():
    assert extraer_sql("respuesta:\n```sql\nSELECT 1\n```\nfin") == "SELECT 1"


def test_extraer_sql_bloque_generico():
    assert extraer_sql("```\nSELECT 2 FROM t\n```") == "SELECT 2 FROM t"


def test_extraer_sql_empieza_por_select():
    assert extraer_sql("SELECT 3 FROM productos") == "SELECT 3 FROM productos"


def test_extraer_sql_sin_sql_devuelve_none():
    assert extraer_sql("No puedo: no existe esa tabla en el esquema.") is None


def test_generar_sql_ok_extrae_del_bloque():
    cliente = _cliente_que_devuelve("```sql\nSELECT TOP 5 nombre_producto FROM productos\n```")
    r = generar_sql("dame productos", esquema_texto="ESQUEMA", cliente=cliente)
    assert r.ok is True
    assert r.sql == "SELECT TOP 5 nombre_producto FROM productos"


def test_generar_sql_propaga_error_del_llm():
    def _falla(_m: list[dict[str, str]]) -> RespuestaLLM:
        return RespuestaLLM(ok=False, codigo_error="LLM_TIMEOUT", mensaje="timeout")

    r = generar_sql("x", esquema_texto="ESQUEMA", cliente=_falla)
    assert r.ok is False
    assert r.codigo_error == "LLM_TIMEOUT"


def test_generar_sql_sin_sql_devuelve_aclaracion():
    cliente = _cliente_que_devuelve("Falta la columna 'color' en el esquema.")
    r = generar_sql("color de las ventas", esquema_texto="ESQUEMA", cliente=cliente)
    assert isinstance(r, ResultadoGeneracion)
    assert r.ok is False
    assert r.codigo_error == SIN_SQL
    assert r.mensaje == "Falta la columna 'color' en el esquema."


def test_extraer_sql_select_embebido_en_prosa():
    """HOTFIX: si el modelo no usa bloque de código, se rescata el SELECT del texto libre."""
    texto = "Claro, aquí tienes: SELECT TOP 3 nombre_producto FROM productos ORDER BY precio DESC"
    assert extraer_sql(texto) == "SELECT TOP 3 nombre_producto FROM productos ORDER BY precio DESC"


def test_generar_sql_rescata_sin_bloque_markdown():
    """HOTFIX end-to-end: generar_sql extrae el SELECT aunque el modelo no lo envuelva en ```sql."""
    cliente = _cliente_que_devuelve("SELECT TOP 3 nombre_producto FROM productos")
    r = generar_sql("productos", esquema_texto="ESQUEMA", cliente=cliente)
    assert r.ok is True
    assert r.sql == "SELECT TOP 3 nombre_producto FROM productos"


def test_detectar_no_sql_con_centinela():
    """el centinela NO_SQL: se detecta y devuelve la explicación limpia."""
    assert detectar_no_sql("NO_SQL: there is no color field") == "there is no color field"


def test_detectar_no_sql_sin_centinela():
    """sin centinela, devuelve None (cae a la extracción normal)."""
    assert detectar_no_sql("```sql\nSELECT 1\n```") is None


def test_generar_sql_centinela_devuelve_sin_sql():
    """si el modelo emite NO_SQL:, generar_sql devuelve SIN_SQL con el mensaje limpio."""
    cliente = _cliente_que_devuelve("NO_SQL: no existe un campo de color en el esquema")
    r = generar_sql("color de las ventas", esquema_texto="ESQUEMA", cliente=cliente)
    assert r.ok is False
    assert r.codigo_error == SIN_SQL
    assert r.mensaje == "no existe un campo de color en el esquema"
