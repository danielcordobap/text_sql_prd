"""Adversariales del matcher de grounding — el guard de token numérico (H1 de la auditoría).

Codifican el contrato CORREGIDO de F1.3: un número de la pregunta nunca debe auto-sustituirse
por un número distinto. Fallan contra la implementación con `WRatio` (bloqueada); pasan con
`token_set_ratio` + guard de token numérico.
"""

from src.grounding.matcher import emparejar, normalizar


def test_substituir_positivo_typo_confiado() -> None:
    # P0: la banda CENTRAL. Un typo confiado → SUBSTITUIR al valor real (no exacto, ganador claro).
    # Typo con holgura sobre el umbral (no pegado a 0.82) para no ser frágil a recalibración.
    r = emparejar("Bebiddas", ["Bebidas", "Lacteos", "Aseo"])
    assert r.decision == "SUBSTITUIR"
    assert r.mejor_match == "Bebidas"
    assert r.exacto is False
    assert r.score >= 0.85 # documenta el acoplamiento al umbral; revisar si se sube >0.85


def test_normalizar_tildes_puntuacion_casefold() -> None:
    assert normalizar("Bogotá D.C.") == "bogota d c"
    assert normalizar(" ÁGUILA-2 ") == "aguila 2"


def test_guard_longitud_minima() -> None:
    # Aísla el guard len<2: "a" == "a" es coincidencia EXACTA; solo el guard explica SIN_CANDIDATO
    # (sin el guard sería EJECUTAR_DIRECTO). Un candidato bajo el piso no serviría para aislarlo.
    r = emparejar("a", ["a", "Bebidas"])
    assert r.decision == "SIN_CANDIDATO"


def test_ambiguedad_por_margen_pide_aclaracion() -> None:
    # Dos candidatos casi empatados (superconjuntos) → no auto-sustituye, pide aclaración.
    r = emparejar("Bebida Cola", ["Bebida Cola Zero", "Bebida Cola Light", "Aseo"])
    assert r.decision == "PEDIR_ACLARACION"


def test_no_sustituye_a_numero_distinto() -> None:
    # "LOT 19" NO debe auto-sustituirse por "LOT 190" (19 != 190 son identidades distintas).
    r = emparejar("LOT 19", ["LOT 190"])
    assert r.decision != "SUBSTITUIR", (
        f"auto-sustituyó a un número distinto: {r.mejor_match} ({r.decision})"
    )


def test_ranking_no_prefiere_numero_distinto() -> None:
    # Con el candidato correcto presente, jamás debe elegir el vecino numérico equivocado.
    r = emparejar("LOT 19", ["LOT 19 Morthys", "LOT 190"])
    assert r.mejor_match != "LOT 190", "eligió el LOT numérico equivocado como mejor_match"
    if r.decision == "SUBSTITUIR":
        assert r.mejor_match == "LOT 19 Morthys"


def test_exacto_ejecuta_directo() -> None:
    r = emparejar("Bebidas", ["Bebidas", "Lacteos", "Aseo"])
    assert r.exacto is True
    assert r.decision == "EJECUTAR_DIRECTO"


def test_sin_candidatos_da_sin_candidato() -> None:
    r = emparejar("cualquier cosa", [])
    assert r.decision == "SIN_CANDIDATO"
