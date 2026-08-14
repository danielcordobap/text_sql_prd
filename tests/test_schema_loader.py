"""Pruebas del cargador de esquema."""

from unittest.mock import patch

from src.schema import loader

_FAKE_ESQUEMA = {
    "ventas": [("venta_id", "int"), ("fecha", "date")],
    "productos": [("producto_id", "varchar"), ("nombre_producto", "varchar")],
}


def test_esquema_columnas_deriva_el_mapa():
    with patch("src.schema.loader.introspeccionar", return_value=_FAKE_ESQUEMA):
        mapa = loader.esquema_columnas()
    assert mapa == {
        "ventas": {"venta_id", "fecha"},
        "productos": {"producto_id", "nombre_producto"},
    }


def test_esquema_para_prompt_incluye_estructura_significados_y_relaciones():
    with patch("src.schema.loader.introspeccionar", return_value=_FAKE_ESQUEMA):
        txt = loader.esquema_para_prompt()
    # estructura + tipos
    assert "Tabla ventas" in txt
    assert "fecha (date)" in txt
    # significado transcrito de MODELO_DATOS.md
    assert "Fecha de la venta" in txt
    # sección de relaciones (FKs)
    assert "Relaciones" in txt
    assert "ventas.producto_id -> productos.producto_id" in txt
