"""Paquete del cliente LLM compatible con OpenRouter / OpenAI."""

from src.llm.client import (
    LLM_ERROR,
    LLM_RATE_LIMIT,
    LLM_TIMEOUT,
    LLM_VACIO,
    ClienteLLM,
    RespuestaLLM,
    completar,
)

__all__ = [
    "LLM_ERROR",
    "LLM_RATE_LIMIT",
    "LLM_TIMEOUT",
    "LLM_VACIO",
    "ClienteLLM",
    "RespuestaLLM",
    "completar",
]
