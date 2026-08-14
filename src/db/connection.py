"""Módulo de conexión con context manager a Azure SQL Server."""

import time
from collections.abc import Iterator
from contextlib import contextmanager

import pyodbc

from src.config.settings import Settings, get_settings


class ConexionBDError(Exception):
    """Excepción lanzada cuando falla la conexión a la base de datos."""


def construir_cadena_conexion(settings: Settings | None = None) -> str:
    """Construye la cadena de conexión de pyodbc sin exponer credenciales en logs."""
    s = settings or get_settings()

    server = s.db_server.strip()
    if not server.startswith("tcp:"):
        server = f"tcp:{server}"
    if ",1433" not in server:
        server = f"{server},1433"

    conn_str = (
        f"DRIVER={{{s.db_driver}}};"
        f"SERVER={server};"
        f"DATABASE={s.db_name};"
        f"UID={s.db_user};"
        f"PWD={s.db_password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        f"Connection Timeout={s.db_read_timeout_seconds};"
    )
    return conn_str


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[pyodbc.Connection]:
    """Context manager para abrir conexión pyodbc con reintentos (40613) y cierre garantizado."""
    s = settings or get_settings()
    cadena = construir_cadena_conexion(s)

    cn: pyodbc.Connection | None = None
    max_intentos = 5

    for intento in range(1, max_intentos + 1):
        try:
            cn = pyodbc.connect(cadena, timeout=s.db_read_timeout_seconds)
            break
        except pyodbc.Error as e:
            msg_error = str(e)
            if "40613" in msg_error and intento < max_intentos:
                time.sleep(intento * 1)
                continue
            raise ConexionBDError("No se pudo conectar a la base de datos de Azure SQL.") from e

    if cn is None:
        raise ConexionBDError("No se pudo obtener una conexión válida a la base de datos.")

    try:
        yield cn
    finally:
        try:
            cn.close()
        except pyodbc.Error:  # noqa: S110
            pass
