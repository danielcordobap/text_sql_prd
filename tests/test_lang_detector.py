"""Pruebas del detector de idioma."""

from src.lang.detector import detectar_idioma


def test_detecta_ingles() -> None:
    assert detectar_idioma("which are the 3 most expensive products?") == "en"


def test_detecta_espanol_por_diacriticos() -> None:
    assert detectar_idioma("¿cuántas ventas hubo en 2025?") == "es"


def test_detecta_espanol_por_palabras_funcion() -> None:
    assert detectar_idioma("dame los productos del inventario") == "es"


def test_vacio_usa_default() -> None:
    assert detectar_idioma("") == "es"
    assert detectar_idioma(" ") == "es"


def test_empate_usa_default_configurable() -> None:
    # cadena sin señales claras de ningún idioma → default
    assert detectar_idioma("SKU0001 2025", default="en") == "en"
    assert detectar_idioma("SKU0001 2025") == "es"
