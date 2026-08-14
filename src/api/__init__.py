"""Módulo API del sistema text-to-SQL (FastAPI)."""

from src.api.main import ConsultaRequest, ConsultaResponse, app, consultar, health

__all__ = [
    "ConsultaRequest",
    "ConsultaResponse",
    "app",
    "consultar",
    "health",
]
