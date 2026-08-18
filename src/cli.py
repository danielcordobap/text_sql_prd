"""Capa de transporte CLI para interactuar con el pipeline text-to-SQL."""

import uuid

from src.brain.orquestador import Respuesta
from src.graph.agente import conversar


def formatear_respuesta(r: Respuesta) -> str:
    """Renderiza el resultado tipificado de conversar() en texto plano para la terminal."""
    if not r.ok:
        return f"No se pudo responder [{r.codigo_error}]: {r.mensaje}"

    if r.tipo == "aclaracion":
        opciones = "\n".join(f"  {i + 1}. {c.valor}" for i, c in enumerate(r.candidatos))
        return f"{r.mensaje or ''}\n{opciones}"
    if r.tipo == "mensaje":
        return r.mensaje or ""

    lineas = []
    if r.nota:
        lineas.append(r.nota)
    lineas.extend([f"SQL:\n{r.sql}", f"\nResultado ({r.n_filas} filas):"])
    if r.n_filas == 0:
        lineas.append("Sin resultados.")
        return "\n".join(lineas)

    lineas.append(" | ".join(r.columnas))
    for fila in r.filas:
        lineas.append(" | ".join(str(fila.get(c)) for c in r.columnas))

    return "\n".join(lineas)


def main() -> None:
    """Bucle interactivo principal de la interfaz por consola."""
    print("Text-to-SQL — escribe tu pregunta (Enter vacío para salir)")
    thread_id = str(uuid.uuid4())

    while True:
        try:
            pregunta = input("\nPregunta> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not pregunta:
            break

        r = conversar(pregunta, thread_id)
        print(formatear_respuesta(r))


if __name__ == "__main__":
    main()
