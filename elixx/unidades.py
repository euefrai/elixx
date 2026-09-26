"""Unidades da ELiXX.

Categorias da Fase 01:

    comprimento: px, %, vw, vh
    tempo:       ms, s
    ângulo:      graus

Fase 10: ângulo aceita `deg` (= graus) e `rad` (radianos, convertidos
para graus no núcleo de transformação). Unidade interna: graus.
"""
from __future__ import annotations

UNIDADES_POR_CATEGORIA: dict[str, set[str]] = {
    "comprimento": {"px", "%", "vw", "vh"},
    "tempo": {"ms", "s"},
    "angulo": {"graus", "deg", "rad"},
}

UNIDADES_VALIDAS: frozenset[str] = frozenset(
    unidade for grupo in UNIDADES_POR_CATEGORIA.values() for unidade in grupo
)


def categoria(unidade: str) -> str | None:
    """Retorna a categoria da unidade ('comprimento', 'tempo', 'angulo')."""
    for nome, grupo in UNIDADES_POR_CATEGORIA.items():
        if unidade in grupo:
            return nome
    return None


def tempo_para_ms(valor: float, unidade: str) -> float:
    """Normaliza uma medida de tempo para milissegundos."""
    if unidade == "ms":
        return float(valor)
    if unidade == "s":
        return float(valor) * 1000.0
    raise ValueError(f"Unidade de tempo desconhecida: {unidade!r}")
