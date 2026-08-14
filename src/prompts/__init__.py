"""Módulo de prompts del sistema para traducción NL-a-SQL y orquestación."""

from src.prompts.generacion_sql import SYSTEM_PROMPT, construir_mensajes
from src.prompts.orquestacion import ROUTER_PROMPT, VIZ_ADVISOR_PROMPT

__all__ = [
    "SYSTEM_PROMPT",
    "construir_mensajes",
    "ROUTER_PROMPT",
    "VIZ_ADVISOR_PROMPT",
]
