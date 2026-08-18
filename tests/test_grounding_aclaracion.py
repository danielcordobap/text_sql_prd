"""Adversariales de la ronda de aclaración (N-9: hoy sin cobertura).

N-2: `resolver_ordinal` no debe dispararse con texto libre que contenga un dígito
(hoy hace `substring in texto` → "LOT 19" elige candidatos[0] por el "1").
"""

from src.graph.agente import nodo_aclarar
from src.grounding.extraccion import resolver_ordinal

_PENDIENTE = {
    "columna": "nombre_producto",
    "tabla": "productos",
    "candidatos": ["Agua 600ml", "Aguacate"],
    "sql_original": "SELECT COUNT(*) AS n FROM productos WHERE nombre_producto = 'agua'",
    "literal_original": "agua",
    "pregunta_original": "ventas del producto agua",
}


def _estado(pregunta: str) -> dict:
    return {"pregunta": pregunta, "pendiente_aclaracion": dict(_PENDIENTE)}


def test_ordinal_no_matchea_digito_dentro_de_texto_libre() -> None:
    # "LOT 19" NO es un ordinal; el "1" no debe seleccionar candidatos[0].
    r = resolver_ordinal("LOT 19", ["LOT 190", "LOT 19 Morthys", "LOT 191", "LOT 192"])
    assert r is None, f"texto libre con dígito se mal-enrutó a ordinal: {r!r}"


def test_ordinal_no_matchea_frase_con_numero() -> None:
    # "en 2020" no es "el 2"; no debe elegir el segundo candidato.
    r = resolver_ordinal("ventas en 2020", ["Bebidas", "Lacteos", "Aseo", "Snacks"])
    assert r is None, f"frase con número se mal-enrutó a ordinal: {r!r}"


def test_ordinal_valido_si_resuelve() -> None:
    # Un ordinal real sí debe resolver.
    r = resolver_ordinal("el segundo", ["A", "B", "C"])
    assert r == "B"
    assert resolver_ordinal("2", ["A", "B", "C"]) == "B"


# --- N-9: ronda de aclaración (nodo_aclarar) ---


def test_aclarar_resuelve_por_ordinal_y_reescribe() -> None:
    # "el segundo" → Aguacate; reescribe el literal, restaura la pregunta, limpia el pendiente.
    out = nodo_aclarar(_estado("el segundo")) # type: ignore[arg-type]
    assert out["pendiente_aclaracion"] is None
    assert "Aguacate" in (out["sql"] or "")
    assert out["pregunta"] == "ventas del producto agua"


def test_aclarar_resuelve_por_fuzzy() -> None:
    # El usuario escribe el valor libre → empareja al candidato.
    out = nodo_aclarar(_estado("agua 600")) # type: ignore[arg-type]
    assert out["pendiente_aclaracion"] is None
    assert "Agua 600ml" in (out["sql"] or "")


def test_aclarar_sin_match_descarta_pendiente() -> None:
    # Pregunta nueva no relacionada → limpia el pendiente y sql=None (se enruta al router).
    out = nodo_aclarar(_estado("cuántas tiendas hay")) # type: ignore[arg-type]
    assert out["pendiente_aclaracion"] is None
    assert out["sql"] is None


def test_conversar_resetea_nota_grounding_por_turno(monkeypatch) -> None:
    # H-1: cada turno debe iniciar con nota_grounding=None para que una nota no se filtre al
    # siguiente turno del mismo thread_id (el canal lo persiste MemorySaver). Sin LLM/BD.
    from src.graph import agente

    capturado: dict = {}

    def fake_invoke(entrada, config=None): # noqa: ANN001, ANN202
        capturado.update(dict(entrada))
        return {"respuesta": {"ok": True, "tipo": "datos", "sql": "SELECT 1", "n_filas": 0}}

    monkeypatch.setattr(agente.grafo, "invoke", fake_invoke)
    agente.conversar("cuántas tiendas hay", "t-reset")
    assert "nota_grounding" in capturado, "el entrada de conversar no resetea nota_grounding (H-1)"
    assert capturado["nota_grounding"] is None
