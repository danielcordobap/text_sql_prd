"""Script para la creación de tablas e importación masiva de datos CSV a Azure SQL Server.

Lee las credenciales desde el archivo `.env` o permite ingresarlas de forma interactiva/parámetros.
Crea el esquema definido en `esquema_sql_server.sql` y luego carga los 7 archivos CSV en orden de dependencia.

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import pyodbc

# Asegurar codificación UTF-8 para stdout en consolas de Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def cargar_env_si_existe(base_dir: Path) -> dict[str, str]:
    """Carga variables desde el archivo .env si existe."""
    env_file = base_dir / ".env"
    env_vars: dict[str, str] = {}
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip("'\"")
    return env_vars


def obtener_conexion(
    server: str,
    database: str,
    user: str,
    password: str,
    driver: str = "ODBC Driver 18 for SQL Server",
) -> pyodbc.Connection:
    """Establece la conexión a Azure SQL Server con pyodbc."""
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    print(f"Conectando a Azure SQL Server ({server})...")
    return pyodbc.connect(conn_str)


def crear_esquema(conn: pyodbc.Connection, esquema_path: Path) -> None:
    """Ejecuta el script SQL del esquema para crear las 7 tablas."""
    if not esquema_path.exists():
        print(f"[ERROR] No se encontró el archivo de esquema en {esquema_path}")
        sys.exit(1)

    print("Ejecutando script de esquema (esquema_sql_server.sql)...")
    sql_script = esquema_path.read_text(encoding="utf-8")

    cursor = conn.cursor()

    # Filtrar comentarios de bloque /* ... */ y comentarios de línea --
    import re

    sql_sin_bloques = re.sub(r"/\*.*?\*/", "", sql_script, flags=re.DOTALL)

    lineas = []
    for line in sql_sin_bloques.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("--") or line_clean.upper() in ("GO", "USE SUPERMERCADO;"):
            continue
        lineas.append(line)

    sql_limpio = "\n".join(lineas)
    bloques_create = [b.strip() for b in sql_limpio.split("CREATE TABLE") if b.strip()]
    for bloque in bloques_create:
        sql_statement = "CREATE TABLE " + bloque
        nombre_tabla = bloque.split("(")[0].strip()
        try:
            cursor.execute(sql_statement)
            conn.commit()
            print(f"  -> Tabla '{nombre_tabla}' creada / verificada.")
        except pyodbc.Error as e:
            if "already an object named" in str(e) or "ya existe" in str(e).lower():
                print(f"  -> Tabla '{nombre_tabla}' ya existía.")
            else:
                print(f"  -> Advertencia al crear '{nombre_tabla}': {e}")


def limpiar_valor(val: str) -> Any:
    """Convierte cadenas vacías a None (NULL en SQL)."""
    if val is None or val.strip() == "":
        return None
    return val.strip()


def cargar_csv(
    conn: pyodbc.Connection,
    tabla: str,
    csv_path: Path,
    mapeo_tipos: list[type] | None = None,
) -> int:
    """Carga datos desde un CSV a una tabla SQL mediante inserciones por lotes."""
    if not csv_path.exists():
        print(f"[ERROR] No se encontró el archivo CSV en {csv_path}")
        return 0

    print(f"Cargando {csv_path.name} -> tabla '{tabla}'...")
    cursor = conn.cursor()
    cursor.fast_executemany = True

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)

        columnas_str = ", ".join(headers)
        placeholders = ", ".join(["?"] * len(headers))
        sql_insert = f"INSERT INTO {tabla} ({columnas_str}) VALUES ({placeholders})"

        filas: list[list[Any]] = []
        for row in reader:
            fila_procesada = []
            for idx, val in enumerate(row):
                v_limpio = limpiar_valor(val)
                if v_limpio is not None and mapeo_tipos and idx < len(mapeo_tipos):
                    try:
                        v_limpio = mapeo_tipos[idx](v_limpio)
                    except ValueError:
                        pass
                fila_procesada.append(v_limpio)
            filas.append(fila_procesada)

        if filas:
            cursor.executemany(sql_insert, filas)
            conn.commit()
            print(f"  [OK] {len(filas)} filas insertadas en '{tabla}'.")
            return len(filas)
        else:
            print(f"  [INFO] El archivo CSV {csv_path.name} está vacío.")
            return 0


def main() -> None:
    """Punto de entrada principal para el script de carga."""
    parser = argparse.ArgumentParser(description="Cargar datos CSV a Azure SQL Server.")
    parser.add_argument("--server", help="Servidor de Azure SQL")
    parser.add_argument("--database", help="Nombre de la base de datos")
    parser.add_argument("--user", help="Usuario administrador de SQL")
    parser.add_argument("--password", help="Contraseña del usuario administrador")
    parser.add_argument(
        "--driver", default="ODBC Driver 18 for SQL Server", help="Driver ODBC de SQL Server"
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    datos_dir = base_dir / "datos"
    esquema_path = base_dir / "esquema_sql_server.sql"
    env_vars = cargar_env_si_existe(base_dir)

    server = args.server or env_vars.get("DB_SERVER") or os.getenv("DB_SERVER")
    database = args.database or env_vars.get("DB_NAME") or os.getenv("DB_NAME")
    user = args.user or env_vars.get("DB_USER") or os.getenv("DB_USER")
    password = args.password or env_vars.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
    driver = (
        args.driver
        or env_vars.get("DB_DRIVER")
        or os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    )

    print("=========================================================")
    print("CARGADOR DE DATOS CSV A AZURE SQL SERVER")
    print("=========================================================")

    if not server or not database or not user or not password:
        print("[ERROR] Faltan datos de conexión en el archivo .env o argumentos.")
        sys.exit(1)

    try:
        conn = obtener_conexion(server, database, user, password, driver)
    except Exception as e:
        print(f"\n[ERROR] al conectar a la base de datos: {e}")
        print("\nSugerencias:")
        print("1. Revisa que tu IP esté agregada en las reglas de firewall de Azure SQL Server.")
        print("2. Revisa que el usuario y la contraseña sean correctos.")
        print(
            "3. Revisa que el driver de SQL Server esté instalado ('ODBC Driver 18 for SQL Server')."
        )
        sys.exit(1)

    try:
        crear_esquema(conn, esquema_path)

        print("\nIniciando carga de archivos CSV en orden de dependencia...")
        total_filas = 0

        archivos_secuencia = [
            ("categorias", datos_dir / "categorias.csv", [int, str, str]),
            ("proveedores", datos_dir / "proveedores.csv", [int, str, str, str, str]),
            ("tiendas", datos_dir / "tiendas.csv", [int, str, str]),
            ("clientes", datos_dir / "clientes.csv", [int, str, str, str, str]),
            ("productos", datos_dir / "productos.csv", [str, str, int, int, float, str]),
            (
                "ventas",
                datos_dir / "ventas.csv",
                [int, int, str, int, int, str, int, float, float, float],
            ),
            (
                "movimientos_inventario",
                datos_dir / "movimientos_inventario.csv",
                [int, str, int, str, lambda x: int(x) if x else None, str, int, float],
            ),
        ]

        for tabla, csv_file, tipos in archivos_secuencia:
            total_filas += cargar_csv(conn, tabla, csv_file, tipos)

        print("\n=========================================================")
        print(f"[EXITO] Proceso completado. Se cargaron {total_filas} filas en total.")
        print("=========================================================")

    except Exception as e:
        print(f"\n[ERROR] Ocurrió un problema durante la ejecución: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
