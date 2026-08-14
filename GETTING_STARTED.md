# Getting started — run ANL locally

> 🇪🇸 ¿En español? Lee [GETTING_STARTED.es.md](GETTING_STARTED.es.md).

ANL is **not a static app**: to run it you need three external things — a **SQL Server** database, an
**OpenRouter** API key, and the **ODBC driver**. This guide walks you through it end to end.

**Order matters:** database up → schema + data loaded (step 6) → backend → frontend.

---

## Prerequisites (install once)

- **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/)
- **Node.js 18+**
- **ODBC Driver 18 for SQL Server** (Microsoft)
- **Docker** (only if you use the local database option below)

---

## Steps

### 1. Get the code

```bash
git clone <repo-url>
cd text_to_sql_clean
```

### 2. Get a SQL Server database

**Option A — Local, with Docker (most "on your machine"):**

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=YourStrong!Passw0rd" \
  -p 1433:1433 -d mcr.microsoft.com/mssql/server:2022-latest
```

Then create the (empty) database — with `sqlcmd`, Azure Data Studio, or any SQL client:

```sql
CREATE DATABASE supermercado;
```

**Option B — Azure SQL:** create a server + database in the Azure portal, and **add your client IP to
the firewall** (SQL Server → Networking → Add your client IP → Save).

### 3. Get an OpenRouter API key

Sign up at [openrouter.ai](https://openrouter.ai) and create a key (Keys section).

### 4. Create the `.env` file

In the project root (it is git-ignored — never commit it). Minimum:

```dotenv
# LLM (OpenRouter)
OPENROUTER_API_KEY=sk-or-...
MODEL_ID=xiaomi/mimo-v2.5
ROUTER_MODEL_ID=meta-llama/llama-3.1-8b-instruct
SQL_GEN_MODEL_ID=qwen/qwen3-coder-30b-a3b-instruct
SQL_GEN_SEED=42
SQL_GEN_PROVIDER=Alibaba

# Database (SQL Server)
DB_SERVER=localhost                 # or your-server.database.windows.net
DB_NAME=supermercado
DB_USER=sa                          # a user with read access
DB_PASSWORD=YourStrong!Passw0rd
DB_DRIVER=ODBC Driver 18 for SQL Server

# App
CORS_ORIGINS=http://localhost:5173
```

See [README.md](README.md#setup) for the full list of variables.

### 5. Install the backend

```bash
uv sync            # rebuilds the virtualenv from uv.lock
```

### 6. Load the schema + example data

This creates the 7 tables and loads the synthetic CSVs. Use a user with **write** permission (e.g. `sa`):

```bash
uv run python datos/cargar_datos.py \
  --server localhost --database supermercado --user sa --password "YourStrong!Passw0rd"
```

### 7. (Recommended) Create a read-only user

ANL's safety model expects the app to connect with a **read-only** account. In SQL:

```sql
CREATE LOGIN anl_readonly WITH PASSWORD = 'AnotherStrong!Passw0rd';
CREATE USER anl_readonly FOR LOGIN anl_readonly;
ALTER ROLE db_datareader ADD MEMBER anl_readonly;
DENY INSERT, UPDATE, DELETE, ALTER TO anl_readonly;
```

Then point `DB_USER` / `DB_PASSWORD` in `.env` to this user. _(For a quick local trial you can skip
this and keep `sa`; the validator still blocks anything that isn't a `SELECT`.)_

### 8. Start the backend

```bash
uv run uvicorn src.api.main:app --port 8000
```

### 9. Start the frontend (in another terminal)

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

### 10. Use it

Open `http://localhost:5173` and ask a question in natural language (English or Spanish). Without the
frontend, use the CLI:

```bash
uv run python -m src.cli
```

---

## Troubleshooting

- **Questions fail even though the backend started** — usually one of: (a) the database is not
  reachable / firewall (Azure), (b) the data was not loaded (step 6), or (c) a wrong OpenRouter key.
- **`Client with IP address ... is not allowed` (Azure)** — add your current IP to the SQL Server
  firewall (your public IP can change, so this may recur).
- **`LLM_VACIO`** — the LLM provider returned an empty response; retrying usually works. If it
  persists, try a different `SQL_GEN_PROVIDER` (e.g. `Novita`, `DeepInfra`, `Parasail`).
- **ODBC / connection errors** — confirm **ODBC Driver 18 for SQL Server** is installed and that
  `DB_DRIVER` matches its exact name.
- **`[Errno 10048] … only one usage of each socket address` (port already in use)** — the startup
  succeeds but binding fails because port `8000` is already taken, usually by a **previous backend
  instance still running**. Two options:
  - **Free the port** and start again. On Windows (PowerShell): find the process with
    `netstat -ano | findstr :8000`, then `Stop-Process -Id <PID> -Force` (or press **Ctrl+C** in the
    terminal where it runs). On macOS/Linux the equivalent error is `EADDRINUSE`; use
    `lsof -i :8000` then `kill <PID>`.
  - **Use another port:** `uv run uvicorn src.api.main:app --port 8001`, and point the frontend to it
    by creating `frontend/.env` with `VITE_API_BASE_URL=http://localhost:8001`.

---

## Run the tests (optional)

```bash
uv run pytest
```

Most tests are hermetic (mocked LLM/DB); a few expect the `.env` above.
