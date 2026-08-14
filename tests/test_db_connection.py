"""Pruebas del gestor de conexión BD.

Usa settings FALSOS (SimpleNamespace) — NUNCA credenciales reales en los tests.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pyodbc
import pytest
from src.db.connection import (
    ConexionBDError,
    construir_cadena_conexion,
    get_connection,
)


@pytest.fixture(autouse=True)
def _sin_espera(monkeypatch):
    monkeypatch.setattr("src.db.connection.time.sleep", lambda *_: None)


def _settings(server: str = "miserver.database.windows.net") -> SimpleNamespace:
    return SimpleNamespace(
        db_server=server,
        db_driver="ODBC Driver 18 for SQL Server",
        db_name="una_db",
        db_user="usuario_falso",
        db_password="password-falso",
        db_read_timeout_seconds=30,
    )


def test_cadena_agrega_tcp_y_puerto():
    cadena = construir_cadena_conexion(_settings())
    assert "SERVER=tcp:miserver.database.windows.net,1433;" in cadena
    assert cadena.count(",1433") == 1
    assert "Encrypt=yes;" in cadena
    assert "TrustServerCertificate=no;" in cadena


def test_cadena_no_duplica_tcp_ni_puerto():
    cadena = construir_cadena_conexion(_settings(server="tcp:miserver.database.windows.net,1433"))
    assert cadena.count("tcp:") == 1
    assert cadena.count(",1433") == 1


@patch("src.db.connection.pyodbc.connect")
def test_reintenta_40613_y_conecta(mock_connect):
    fake = MagicMock()
    mock_connect.side_effect = [pyodbc.Error("('40613', 'auto-paused')"), fake]
    with get_connection(_settings()) as cn:
        assert cn is fake
    assert mock_connect.call_count == 2
    fake.close.assert_called_once()


@patch("src.db.connection.pyodbc.connect")
def test_40613_persistente_lanza_conexionbderror(mock_connect):
    mock_connect.side_effect = pyodbc.Error("('40613', 'still paused')")
    with pytest.raises(ConexionBDError), get_connection(_settings()):
        pass
    assert mock_connect.call_count == 5


@patch("src.db.connection.pyodbc.connect")
def test_error_no_expone_password(mock_connect):
    mock_connect.side_effect = pyodbc.Error("login failed for password-falso")
    with pytest.raises(ConexionBDError) as exc, get_connection(_settings()):
        pass
    assert "password-falso" not in str(exc.value)


@patch("src.db.connection.pyodbc.connect")
def test_cierre_garantizado_ante_excepcion(mock_connect):
    fake = MagicMock()
    mock_connect.return_value = fake
    with pytest.raises(ValueError, match="boom"), get_connection(_settings()):
        raise ValueError("boom en el bloque")
    fake.close.assert_called_once()
