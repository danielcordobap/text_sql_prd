"""Módulo de detección determinista de idioma (español / inglés)."""

import re
from typing import Literal

_ES_DIACRITICOS = re.compile(r"[áéíóúñü¿¡]", re.IGNORECASE)
_ES_PALABRAS = {
    "qué",
    "que",
    "cuál",
    "cuáles",
    "cuántos",
    "cuántas",
    "cómo",
    "dónde",
    "cuándo",
    "los",
    "las",
    "del",
    "por",
    "para",
    "más",
    "y",
    "en",
}
_EN_PALABRAS = {
    "how",
    "many",
    "what",
    "which",
    "show",
    "list",
    "the",
    "of",
    "in",
    "by",
    "for",
    "and",
    "most",
    "top",
    "are",
    "is",
    "who",
    "when",
    "where",
}


def detectar_idioma(
    pregunta: str,
    historial: list[dict[str, str]] | None = None,
    default: Literal["es", "en"] = "es",
) -> Literal["es", "en"]:
    """Detecta deterministamente si el idioma de la pregunta es español ('es') o inglés ('en')."""
    if not pregunta or not pregunta.strip():
        return default
    tokens = re.findall(r"[a-záéíóúñü]+", pregunta.lower())
    es = len(_ES_DIACRITICOS.findall(pregunta)) * 2 + sum(1 for t in tokens if t in _ES_PALABRAS)
    en = sum(1 for t in tokens if t in _EN_PALABRAS)
    if es > en:
        return "es"
    if en > es:
        return "en"
    return default
