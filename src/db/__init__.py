"""Paquete de gestión de conexión a Azure SQL Server."""

from src.db.connection import ConexionBDError, construir_cadena_conexion, get_connection

__all__ = [
    "ConexionBDError",
    "construir_cadena_conexion",
    "get_connection",
]
