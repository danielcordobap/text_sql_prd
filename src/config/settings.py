"""Módulo de configuración tipada con Pydantic v2."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global del sistema cargada desde variables de entorno."""

    # --- LLM (vía OpenRouter) ---
    openrouter_api_key: Annotated[str, Field(min_length=1)]
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_id: Annotated[str, Field(min_length=1)]
    router_model_id: str = ""
    sql_gen_model_id: str = ""  # modelo dedicado a generación de SQL; vacío = usa model_id
    sql_gen_seed: int | None = None  # seed fijo para reproducibilidad de la generación
    sql_gen_provider: str = ""  # proveedor OpenRouter a pinnear en generación; vacío = sin pineo
    sql_gen_top_p: float = 0.0  # top_p para la generación determinista (A6: parámetro en config)
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0
    llm_max_retries: int = 2
    llm_timeout_seconds: int = 60

    # --- Base de datos (Azure SQL Server) ---
    db_server: Annotated[str, Field(min_length=1)]
    db_name: Annotated[str, Field(min_length=1)]
    db_user: Annotated[str, Field(min_length=1)]
    db_password: Annotated[str, Field(min_length=1)]
    db_driver: str = "ODBC Driver 18 for SQL Server"
    db_read_timeout_seconds: int = 30
    db_max_rows: int = 1000

    # --- Aplicación ---
    conversation_window: int = 6
    max_correcciones_sql: int = 2
    sql_max_rows: int = 100
    export_max_rows: int = 50000
    cors_origins: str = "http://localhost:5173"

    # --- Grounding (Value Grounding con aclaración) ---
    grounding_habilitado: bool = True
    grounding_umbral: float = 0.82
    grounding_piso: float = 0.50
    grounding_margen: float = 0.05
    grounding_k: int = 4
    grounding_aclaracion_umbral: float = 0.45
    grounding_aclaracion_piso: float = 0.30
    grounding_umbral_por_columna: dict[str, float] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia cacheada de la configuración global."""
    return Settings()  # type: ignore[call-arg]
