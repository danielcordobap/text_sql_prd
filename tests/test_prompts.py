"""Pruebas del prompt / construir_mensajes (cerebro). ."""

from src.prompts.generacion_sql import SYSTEM_PROMPT, construir_mensajes

_TABLAS_REALES = [
    "categorias",
    "proveedores",
    "productos",
    "tiendas",
    "clientes",
    "ventas",
    "movimientos_inventario",
]


def test_system_prompt_formatea_sin_error() -> None:
    """El SYSTEM_PROMPT renderiza con esquema/fecha/idioma sin romper.format()."""
    msgs = construir_mensajes("ESQ", "2026-08-10", "hola", idioma="es")
    assert msgs[0]["role"] == "system"
    assert "ESQ" in msgs[0]["content"]


def test_msg_idioma_en_va_tras_la_pregunta() -> None:
    """el _MSG_IDIOMA (inglés) se inyecta como system tras la pregunta."""
    msgs = construir_mensajes("ESQ", "2026-08-10", "how many sales?", idioma="en")
    assert msgs[-1]["role"] == "system"
    assert "ENGLISH" in msgs[-1]["content"]
    assert msgs[-2]["role"] == "user"


def test_msg_idioma_es() -> None:
    msgs = construir_mensajes("ESQ", "2026-08-10", "cuántas ventas?", idioma="es")
    assert "ESPAÑOL" in msgs[-1]["content"]


def test_correccion_es_el_ultimo_mensaje() -> None:
    msgs = construir_mensajes("ESQ", "2026-08-10", "q", idioma="es", error_previo="col x")
    assert "corregida" in msgs[-1]["content"]


def test_fewshot_solo_menciona_tablas_reales() -> None:
    """Anti-alucinación (§7): el few-shot de esquema nombra solo tablas del catálogo real."""
    for t in _TABLAS_REALES:
        assert t in SYSTEM_PROMPT
    for inventada in ["empleados", "nomina", "salarios", "usuarios"]:
        assert inventada not in SYSTEM_PROMPT.lower()
