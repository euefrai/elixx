"""Easings da ELiXX — matemática pura, determinística, sem renderer.

Toda função recebe t em [0, 1] e retorna progressão. Contrato:
f(0) == 0 e f(1) == 1 (mola/elástico/quicar aproximam 1 no fim; o motor
fixa o valor final exato ao concluir — "snap" padrão de motores).
"""
from __future__ import annotations

import math


def linear(t: float) -> float:
    return t


def suave(t: float) -> float:
    """Acelera e desacelera (smoothstep). Padrão da linguagem."""
    return t * t * (3.0 - 2.0 * t)


def acelerar(t: float) -> float:
    return t * t


def desacelerar(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def rapido(t: float) -> float:
    return t * t * t


def lento(t: float) -> float:
    """Progressão gentil (senoidal)."""
    return (1.0 - math.cos(math.pi * t)) / 2.0


def deslizar(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def mola(t: float) -> float:
    """Mola amortecida (ultrapassa o alvo e assenta)."""
    return 1.0 - math.exp(-6.0 * t) * math.cos(12.0 * t)


def elastico(t: float) -> float:
    """Elástico (oscila antes de assentar)."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 2.0 ** (-10.0 * t) * math.sin((t * 10.0 - 0.75) * (2.0 * math.pi / 3.0)) + 1.0


def quicar(t: float) -> float:
    """Quicar (bounce-out padrão)."""
    if t < 1.0 / 2.75:
        return 7.5625 * t * t
    if t < 2.0 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


def expandir(t: float) -> float:
    """Cresce passando do ponto (para escala/tamanho)."""
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


def encolher(t: float) -> float:
    """Encolhe com recuo (para escala/tamanho)."""
    c1 = 1.70158
    c3 = c1 + 1.0
    return c3 * t ** 3 - c1 * t * t


def sacudir(t: float) -> float:
    """Oscila em torno do caminho e assenta no destino."""
    return t + math.sin(t * 4.0 * math.pi) * (1.0 - t) * 0.3


def aparecer(t: float) -> float:
    """Fade-in linear (o motor liga a visibilidade no início)."""
    return t


def desaparecer(t: float) -> float:
    """Fade-out (o motor desliga a visibilidade no fim)."""
    return t


# Fase 11: aliases de entrada/saída (nomes da linguagem; sem duplicar
# matemática — apontam para as curvas existentes).
def entrada(t: float) -> float:
    """Entrada suave (ease-out = desacelerar)."""
    return desacelerar(t)


def saida(t: float) -> float:
    """Saída com arranque (ease-in = acelerar)."""
    return acelerar(t)


def entrada_saida(t: float) -> float:
    """Entrada e saída (ease-in-out = suave)."""
    return suave(t)


EASINGS: dict[str, object] = {
    "linear": linear,
    "suave": suave,
    "acelerar": acelerar,
    "desacelerar": desacelerar,
    "rapido": rapido,
    "lento": lento,
    "deslizar": deslizar,
    "mola": mola,
    "elastico": elastico,
    "quicar": quicar,
    "expandir": expandir,
    "encolher": encolher,
    "sacudir": sacudir,
    "aparecer": aparecer,
    "desaparecer": desaparecer,
    # Fase 11: aliases (f(t) idênticas às originais).
    "entrada": entrada,
    "saida": saida,
    "saída": saida,
    "entrada_saida": entrada_saida,
    "entrada_saída": entrada_saida,
}
"""Toda entrada nova aqui vira movimento válido sem mexer no motor."""
