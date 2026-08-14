"""Cliente de LLM agnóstico al proveedor utilizando OpenRouter / OpenAI SDK."""

import time
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError
from pydantic import BaseModel

from src.config.settings import Settings, get_settings

# Constantes de códigos de error tipificados
LLM_TIMEOUT = "LLM_TIMEOUT"
LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
LLM_VACIO = "LLM_VACIO"
LLM_ERROR = "LLM_ERROR"


class RespuestaLLM(BaseModel):
    """Modelo de resultado estandarizado para llamadas al LLM."""

    ok: bool
    contenido: str | None = None
    codigo_error: str | None = None
    mensaje: str | None = None


class ClienteLLM:
    """Cliente para la API del LLM configurado vía OpenRouter."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = OpenAI(
            base_url=self.settings.openrouter_base_url,
            api_key=self.settings.openrouter_api_key,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=0,
        )

    def _extraer_texto_respuesta(self, msg_obj: Any) -> str | None:
        texto = msg_obj.content
        if isinstance(texto, str) and texto.strip():
            return str(texto)
        reasoning = getattr(msg_obj, "reasoning", None)
        if (
            not reasoning
            and hasattr(msg_obj, "model_extra")
            and isinstance(msg_obj.model_extra, dict)
        ):
            reasoning = msg_obj.model_extra.get("reasoning")
        if reasoning and isinstance(reasoning, str) and reasoning.strip():
            return str(reasoning).strip()
        return None

    def _extraer_texto_opciones(self, response: Any) -> str | None:
        if response.choices and response.choices[0].message:
            return self._extraer_texto_respuesta(response.choices[0].message)
        return None

    def _esperar_reintento(self, intento: int, intentos_totales: int) -> bool:
        if intento < intentos_totales:
            time.sleep(intento * 0.5)
            return True
        return False

    def _preparar_extra_params(
        self, seed: int | None, top_p: float | None, provider: str | None
    ) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if seed is not None:
            extra["seed"] = seed
        if top_p is not None:
            extra["top_p"] = top_p
        if provider is not None:
            extra["extra_body"] = {"provider": {"order": [provider], "allow_fallbacks": False}}
        return extra

    def completar(
        self,
        mensajes: list[dict[str, str]],
        model: str | None = None,
        *,
        seed: int | None = None,
        top_p: float | None = None,
        provider: str | None = None,
    ) -> RespuestaLLM:
        """Envía los mensajes al LLM con reintentos con límite duro y manejo de fallos.

        `seed`, `top_p` y `provider` (opcionales) endurecen el determinismo por sitio de llamada:
        se incluyen en el request solo si no son None (comportamiento intacto cuando se omiten).
        Una respuesta VACÍA se reintenta dentro del presupuesto de reintentos
        (flakiness de hosting).
        """
        modelo = model or self.settings.model_id
        max_retries = self.settings.llm_max_retries
        intentos_totales = max_retries + 1
        extra = self._preparar_extra_params(seed, top_p, provider)

        for intento in range(1, intentos_totales + 1):
            try:
                response = self.client.chat.completions.create(
                    model=modelo,
                    max_tokens=self.settings.llm_max_tokens,
                    temperature=self.settings.llm_temperature,
                    messages=mensajes,  # type: ignore[arg-type]
                    **extra,
                )

                texto = self._extraer_texto_opciones(response)
                if not texto:
                    if self._esperar_reintento(intento, intentos_totales):
                        continue
                    return RespuestaLLM(
                        ok=False,
                        codigo_error=LLM_VACIO,
                        mensaje="La respuesta del LLM está vacía tras agotar los reintentos.",
                    )

                return RespuestaLLM(ok=True, contenido=texto)

            except APITimeoutError as e:
                if self._esperar_reintento(intento, intentos_totales):
                    continue
                return RespuestaLLM(
                    ok=False,
                    codigo_error=LLM_TIMEOUT,
                    mensaje=f"Tiempo de espera agotado tras {intentos_totales} intentos: {e}",
                )

            except RateLimitError as e:
                if self._esperar_reintento(intento, intentos_totales):
                    continue
                return RespuestaLLM(
                    ok=False,
                    codigo_error=LLM_RATE_LIMIT,
                    mensaje=f"Límite de tasa excedido tras {intentos_totales} intentos: {e}",
                )

            except APIError as e:
                return RespuestaLLM(
                    ok=False,
                    codigo_error=LLM_ERROR,
                    mensaje=f"Error en la API del LLM: {e}",
                )

        return RespuestaLLM(
            ok=False,
            codigo_error=LLM_ERROR,
            mensaje="No se pudo completar la llamada al LLM.",
        )


_cliente_global: ClienteLLM | None = None


def completar(
    mensajes: list[dict[str, str]],
    client: ClienteLLM | None = None,
    model: str | None = None,
    *,
    seed: int | None = None,
    top_p: float | None = None,
    provider: str | None = None,
) -> RespuestaLLM:
    """Función principal de conveniencia para invocar al LLM."""
    global _cliente_global
    if client is not None:
        return client.completar(mensajes, model=model, seed=seed, top_p=top_p, provider=provider)
    if _cliente_global is None:
        _cliente_global = ClienteLLM()
    return _cliente_global.completar(
        mensajes, model=model, seed=seed, top_p=top_p, provider=provider
    )
