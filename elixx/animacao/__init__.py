"""Animação da ELiXX — motor de interpolação real (Fase 03).

Conceito:

    animação entrada {
        alvo: cartao
        posição: 0px 90px → 0px 40px
        duração: 600ms
        movimento: suave
    }

Novos movimentos entram em `easing.EASINGS` sem mexer no motor.
O motor escreve só na Cena; cada renderer aplica o que consegue.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..erros import ErroExecucao, sugerir
from .easing import EASINGS
from .motion import (
    FISICAS_MOTION,
    MODOS_MOTION,
    Keyframe,
    Motion,
    MotionGroup,
    Spring,
    avaliar_keyframes,
    curva,
    curva_parametrica,
    interpolar_angulo,
    interpolar_transform,
    interpolar_vetor,
    mola_parametrica,
    progresso_tempo,
)
from .motor import (
    ChaveAnimacao,
    DefinicaoAnimacao,
    Execucao,
    MotorAnimacoes,
)

MOVIMENTOS = {
    "suave": "acelera e desacelera (padrão)",
    "linear": "velocidade constante",
    "acelerar": "começa devagar e acelera",
    "desacelerar": "começa rápido e desacelera",
    "rapido": "rápido com arranque forte",
    "lento": "progressão gentil",
    "mola": "mola amortecida (ultrapassa e assenta)",
    "elastico": "elástico (oscila antes de assentar)",
    "quicar": "quica até parar",
    "sacudir": "oscila em torno do caminho",
    "deslizar": "desliza até o destino",
    "expandir": "cresce passando do ponto",
    "encolher": "encolhe com recuo",
    "aparecer": "surge (visível no início)",
    "desaparecer": "some (invisível no fim)",
    # Fase 11: aliases de entrada/saída (curvas existentes).
    "entrada": "entrada suave (igual a desacelerar)",
    "saida": "saída com arranque (igual a acelerar)",
    "saída": "saída com arranque (igual a acelerar)",
    "entrada_saida": "entrada e saída (igual a suave)",
    "entrada_saída": "entrada e saída (igual a suave)",
}

assert set(MOVIMENTOS) == set(EASINGS), "MOVIMENTOS e EASINGS divergiram"


@dataclass
class Animacao:
    """Compatibilidade Fase 01/02 (ação animar simplificada)."""

    alvo: str
    destino: dict = field(default_factory=dict)
    duracao_ms: float = 500.0
    movimento: str = "suave"
    linha: int = 0


def criar_animacao(alvo: str, destino: dict, duracao_ms: float = 500.0,
                   movimento: str = "suave", linha: int = 0) -> Animacao:
    if movimento not in MOVIMENTOS:
        parecidos = sugerir(movimento, sorted(MOVIMENTOS))
        dica = f" Você quis dizer: {', '.join(parecidos)}?" if parecidos else ""
        raise ErroExecucao(
            f"Movimento desconhecido: {movimento!r}.{dica} "
            f"Movimentos válidos: {', '.join(sorted(MOVIMENTOS))}.",
            linha=linha,
        )
    return Animacao(alvo=alvo, destino=dict(destino),
                    duracao_ms=float(duracao_ms),
                    movimento=movimento, linha=linha)

__all__ = ["MOVIMENTOS", "Animacao", "criar_animacao", "ChaveAnimacao",
           "DefinicaoAnimacao", "Execucao", "MotorAnimacoes", "EASINGS",
           "MODOS_MOTION", "FISICAS_MOTION", "Keyframe", "Motion",
           "MotionGroup", "Spring", "avaliar_keyframes", "curva",
           "curva_parametrica", "interpolar_angulo", "interpolar_transform",
           "interpolar_vetor", "mola_parametrica", "progresso_tempo"]
