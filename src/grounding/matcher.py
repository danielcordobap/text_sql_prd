"""Módulo de emparejamiento difuso (matching) y política de grounding de entidades."""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz, process


def normalizar(s: str) -> str:
    """Normaliza texto: NFKD, sin tildes, puntuación a espacios, casefold y colapsa espacios."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    sin_marcas = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    for char in ".,-_/":
        sin_marcas = sin_marcas.replace(char, " ")
    casefolded = sin_marcas.casefold()
    return " ".join(casefolded.split())


def _tokens_num(s: str) -> set[str]:
    """Extrae los tokens numéricos (secuencias de dígitos) del texto."""
    if not s:
        return set()
    return set(re.findall(r"\d+", s))


class Candidato(BaseModel):
    """Representación de un candidato emparejado con su score de similitud."""

    valor: str
    score: float


class ResultadoGrounding(BaseModel):
    """Resultado del proceso de grounding con la decisión tomada según la política."""

    valor_original: str
    exacto: bool
    mejor_match: str | None
    score: float
    top_k: list[Candidato]
    decision: Literal["EJECUTAR_DIRECTO", "SUBSTITUIR", "PEDIR_ACLARACION", "SIN_CANDIDATO"]


def emparejar(
    valor_usuario: str,
    candidatos: list[str],
    *,
    umbral: float = 0.82,
    piso: float = 0.50,
    margen: float = 0.05,
    k: int = 4,
) -> ResultadoGrounding:
    """Empareja un valor ingresado por el usuario contra una lista de candidatos distintos.

    Aplica normalización NFKD, rapidfuzz token_set_ratio y la política de decisión.
    Desempate estable: score desc, luego longitud del candidato asc, luego alfabético.
    """
    if not valor_usuario or not candidatos:
        return ResultadoGrounding(
            valor_original=valor_usuario,
            exacto=False,
            mejor_match=None,
            score=0.0,
            top_k=[],
            decision="SIN_CANDIDATO",
        )

    norm_usuario = normalizar(valor_usuario)
    if len(norm_usuario) < 2:
        return ResultadoGrounding(
            valor_original=valor_usuario,
            exacto=False,
            mejor_match=None,
            score=0.0,
            top_k=[],
            decision="SIN_CANDIDATO",
        )

    # 1. Comprobación rápida de coincidencia exacta normalizada
    exactos = [c for c in candidatos if normalizar(c) == norm_usuario]
    if exactos:
        exactos_ordenados = sorted(exactos, key=lambda c: (len(c), c))
        mejor_exacto = exactos_ordenados[0]
        otros = [c for c in candidatos if c != mejor_exacto]
        extracted_otros = process.extract(
            valor_usuario,
            otros,
            scorer=fuzz.token_set_ratio,
            processor=normalizar,
            limit=k - 1,
            score_cutoff=piso * 100,
        )
        cands_top_k = [Candidato(valor=mejor_exacto, score=1.0)]
        for choice, score_100, _ in extracted_otros:
            cands_top_k.append(Candidato(valor=choice, score=round(score_100 / 100.0, 4)))

        return ResultadoGrounding(
            valor_original=valor_usuario,
            exacto=True,
            mejor_match=mejor_exacto,
            score=1.0,
            top_k=cands_top_k[:k],
            decision="EJECUTAR_DIRECTO",
        )

    # 2. Extracción difusa con rapidfuzz token_set_ratio sobre los candidatos
    results = process.extract(
        valor_usuario,
        candidatos,
        scorer=fuzz.token_set_ratio,
        processor=normalizar,
        limit=len(candidatos),
        score_cutoff=piso * 100,
    )

    if not results:
        return ResultadoGrounding(
            valor_original=valor_usuario,
            exacto=False,
            mejor_match=None,
            score=0.0,
            top_k=[],
            decision="SIN_CANDIDATO",
        )

    # Desempate estable: score desc, len asc, alfabético asc
    candidatos_evaluados: list[Candidato] = []
    for choice, score_100, _ in results:
        score_norm = round(score_100 / 100.0, 4)
        candidatos_evaluados.append(Candidato(valor=choice, score=score_norm))

    candidatos_ordenados = sorted(
        candidatos_evaluados, key=lambda c: (-c.score, len(c.valor), c.valor)
    )

    mejor = candidatos_ordenados[0]
    best_score = mejor.score
    segundo_score = candidatos_ordenados[1].score if len(candidatos_ordenados) > 1 else 0.0

    top_k = candidatos_ordenados[:k]

    # 3. Aplicar política de decisión (umbral + guard numérico)
    tokens_num_usr = _tokens_num(valor_usuario)
    tokens_num_mjr = _tokens_num(mejor.valor)
    numeros_coinciden = tokens_num_usr.issubset(tokens_num_mjr)

    if best_score >= umbral and (best_score - segundo_score) >= margen and numeros_coinciden:
        decision: Literal["EJECUTAR_DIRECTO", "SUBSTITUIR", "PEDIR_ACLARACION", "SIN_CANDIDATO"] = (
            "SUBSTITUIR"
        )
    else:
        decision = "PEDIR_ACLARACION"

    return ResultadoGrounding(
        valor_original=valor_usuario,
        exacto=False,
        mejor_match=mejor.valor,
        score=best_score,
        top_k=top_k,
        decision=decision,
    )


__all__ = [
    "Candidato",
    "ResultadoGrounding",
    "emparejar",
    "normalizar",
]
