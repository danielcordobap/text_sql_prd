# Guía de inicio — ejecutar ANL localmente

> 🇬🇧 In English? Read [GETTING_STARTED.md](GETTING_STARTED.md).

ANL **no es una app estática**: para correrlo necesitas tres cosas externas — una base de datos
**SQL Server**, una clave de **OpenRouter**, y el **driver ODBC**. Esta guía te lleva de punta a punta.

**El orden importa:** base de datos arriba → esquema + datos cargados (paso 6) → backend → frontend.

---

## Requisitos previos (instalar una vez)

- **Python 3.11+** y [`uv`](https://docs.astral.sh/uv/)
- **Node.js 18+**
- **ODBC Driver 18 for SQL Server** (Microsoft)
- **Docker** (solo si usas la opción de base de datos local de abajo)

---

## Pasos

### 1. Obtener el código

```bash
git clone <url-del-repo>
cd text_to_sql_clean
```

### 2. Tener una base de datos SQL Server

**Opción A — Local, con Docker (lo más "en tu PC"):**

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=TuPassw0rd!Fuerte" \
  -p 1433:1433 -d mcr.microsoft.com/mssql/server:2022-latest
```

Luego crea la base (vacía) — con `sqlcmd`, Azure Data Studio o cualquier cliente SQL:

```sql
CREATE DATABASE supermercado;
```

**Opción B — Azure SQL:** crea un servidor + base de datos en el portal de Azure, y **agrega tu IP al
firewall** (SQL Server → Networking → Add your client IP → Save).

### 3. Conseguir la API key de OpenRouter

Regístrate en [openrouter.ai](https://openrouter.ai) y crea una clave (sección Keys).

### 4. Crear el archivo `.env`

En la raíz del proyecto (está en `.gitignore` — nunca lo subas). Mínimo:

```dotenv
# LLM (OpenRouter)
OPENROUTER_API_KEY=sk-or-...
MODEL_ID=xiaomi/mimo-v2.5
ROUTER_MODEL_ID=meta-llama/llama-3.1-8b-instruct
SQL_GEN_MODEL_ID=qwen/qwen3-coder-30b-a3b-instruct
SQL_GEN_SEED=42
SQL_GEN_PROVIDER=Alibaba

# Base de datos (SQL Server)
DB_SERVER=localhost                 # o tu-servidor.database.windows.net
DB_NAME=supermercado
DB_USER=sa                          # un usuario con acceso de lectura
DB_PASSWORD=TuPassw0rd!Fuerte
DB_DRIVER=ODBC Driver 18 for SQL Server

# App
CORS_ORIGINS=http://localhost:5173
```

La lista completa de variables está en [README.es.md](README.es.md#puesta-en-marcha).

### 5. Instalar el backend

```bash
uv sync            # reconstruye el entorno virtual desde uv.lock
```

### 6. Cargar el esquema + los datos de ejemplo

Crea las 7 tablas y carga los CSV sintéticos. Usa un usuario con permiso de **escritura** (ej. `sa`):

```bash
uv run python datos/cargar_datos.py \
  --server localhost --database supermercado --user sa --password "TuPassw0rd!Fuerte"
```

### 7. (Recomendado) Crear un usuario de solo lectura

El modelo de seguridad de ANL espera que la app se conecte con una cuenta de **solo lectura**. En SQL:

```sql
CREATE LOGIN anl_readonly WITH PASSWORD = 'OtraPassw0rd!Fuerte';
CREATE USER anl_readonly FOR LOGIN anl_readonly;
ALTER ROLE db_datareader ADD MEMBER anl_readonly;
DENY INSERT, UPDATE, DELETE, ALTER TO anl_readonly;
```

Luego apunta `DB_USER` / `DB_PASSWORD` en el `.env` a este usuario. _(Para una prueba rápida local
puedes saltarte esto y usar `sa`; el validador igual bloquea todo lo que no sea `SELECT`.)_

### 8. Levantar el backend

```bash
uv run uvicorn src.api.main:app --port 8000
```

### 9. Levantar el frontend (en otra terminal)

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

### 10. Usarlo

Abre `http://localhost:5173` y pregunta en lenguaje natural (inglés o español). Sin el frontend, usa la
CLI:

```bash
uv run python -m src.cli
```

---

## Solución de problemas

- **Las preguntas fallan aunque el backend arrancó** — casi siempre es: (a) la BD no es accesible /
  firewall (Azure), (b) los datos no se cargaron (paso 6), o (c) la API key está mal.
- **`Client with IP address ... is not allowed` (Azure)** — agrega tu IP actual al firewall del SQL
  Server (tu IP pública puede cambiar, así que puede repetirse).
- **`LLM_VACIO`** — el proveedor del LLM devolvió una respuesta vacía; reintentar suele funcionar. Si
  persiste, prueba otro `SQL_GEN_PROVIDER` (ej. `Novita`, `DeepInfra`, `Parasail`).
- **Errores de ODBC / conexión** — confirma que **ODBC Driver 18 for SQL Server** está instalado y que
  `DB_DRIVER` coincide con su nombre exacto.
- **`[Errno 10048] … solo se permite un uso de cada dirección de socket` (puerto en uso)** — el
  arranque funciona pero falla al reservar el puerto `8000` porque **ya lo tiene otra instancia del
  backend corriendo**. Dos opciones:
  - **Liberar el puerto** y reintentar. En Windows (PowerShell): busca el proceso con
    `netstat -ano | findstr :8000`, luego `Stop-Process -Id <PID> -Force` (o **Ctrl+C** en la terminal
    donde corre). En macOS/Linux el error equivalente es `EADDRINUSE`; usa `lsof -i :8000` y luego
    `kill <PID>`.
  - **Usar otro puerto:** `uv run uvicorn src.api.main:app --port 8001`, y apunta el frontend a él
    creando `frontend/.env` con `VITE_API_BASE_URL=http://localhost:8001`.

---

## Correr los tests (opcional)

```bash
uv run pytest
```

La mayoría de los tests son herméticos (LLM/BD mockeados); algunos esperan el `.env` de arriba.
