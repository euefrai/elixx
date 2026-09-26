"""Motion Core 2.0 — planos, curvas, keyframes, springs e composição.

Relação (sem segundo motor, sem matemática duplicada):

    Motion (plano: o QUE deve acontecer)
      ↓
    curva / spring (COMO ao longo do tempo; f(t), t em [0, 1])
      ↓
    interpolação (Vector2/Transform da F10)
      ↓
    Cena ← Renderer desenha

O `MotorAnimacoes` (motor.py) executa estes planos; este módulo só
contém os blocos de construção puros e determinísticos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..erros import ErroELiXX
from ..visual.transform import Transform, Vector2
from .easing import EASINGS

__all__ = [
    "MODOS_MOTION", "FISICAS_MOTION",
    "curva", "curva_parametrica", "mola_parametrica",
    "progresso_tempo", "interpolar_vetor", "interpolar_angulo",
    "interpolar_transform", "vetor_para", "mover_por_ponto",
    "Keyframe", "avaliar_keyframes", "Spring",
    "Motion", "MotionGroup",
]

MODOS_MOTION = ("normal", "ping_pong")
"""normal: início→fim por rodada; ping_pong: alterna ida/volta por rodada."""

FISICAS_MOTION = ("mola",)
"""Dinâmicas disponíveis em `fisica:` (easing `mola` continua existindo)."""


# ----- progresso (separado da curva) -----

def progresso_tempo(tempo_ms: float, duracao_ms: float) -> float:
    """Progresso t em [0, 1] a partir do tempo decorrido (sem curva)."""
    if duracao_ms <= 0:
        return 1.0
    return max(0.0, min(1.0, float(tempo_ms) / float(duracao_ms)))


# ----- curvas -----

def curva(nome_ou_funcao) -> object:
    """Devolve f(t) a partir do nome da linguagem ou de função pronta."""
    if callable(nome_ou_funcao):
        return nome_ou_funcao
    try:
        return EASINGS[nome_ou_funcao]
    except KeyError:
        from ..erros import sugerir

        parecidas = sugerir(str(nome_ou_funcao), sorted(EASINGS))
        dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                if parecidas else "")
        raise ErroELiXX(
            f"Movimento desconhecido: {nome_ou_funcao!r}.{dica} "
            f"Válidos: {', '.join(sorted(EASINGS))}.")


def mola_parametrica(rigidez: float = 180.0,
                     amortecimento: float = 12.0) -> object:
    """Curva mola fechada f(t) com parâmetros (easing, não dinâmica).

    Diferente do `Spring` (sistema dinâmico com estado): aqui é função
    pura do tempo, determinística e sem integração numérica.
    """
    rigidez = float(rigidez)
    amortecimento = float(amortecimento)
    if not math.isfinite(rigidez) or rigidez <= 0:
        raise ErroELiXX(
            f'Rigidez inválida: {rigidez!r}. Use número positivo.',
            exemplo="rigidez: 180")
    if not math.isfinite(amortecimento) or amortecimento < 0:
        raise ErroELiXX(
            f'Amortecimento inválido: {amortecimento!r}. Use número ≥ 0.',
            exemplo="amortecimento: 12")

    def _f(t: float) -> float:
        return 1.0 - math.exp(-amortecimento * t) * math.cos(
            math.sqrt(rigidez) * t)

    return _f


def curva_parametrica(nome: str, **params) -> object:
    """Fábrica interna de curvas com parâmetros (Fase 11: só mola)."""
    if nome == "mola":
        return mola_parametrica(params.get("rigidez", 180.0),
                                params.get("amortecimento", 12.0))
    raise ErroELiXX(
        f'Curva paramétrica desconhecida: {nome!r}. Válida: "mola".')


# ----- interpolação (usa F10; nada paralelo) -----

def interpolar_vetor(inicio: Vector2, fim: Vector2, e: float) -> Vector2:
    """Lerp entre vetores: (100,100)→(300,200) em t=0.5 = (200,150)."""
    return Vector2(inicio.x + (fim.x - inicio.x) * e,
                   inicio.y + (fim.y - inicio.y) * e)


def interpolar_angulo(de_graus: float, para_graus: float, e: float,
                      voltas: int = 0) -> float:
    """Interpolação angular pelo menor caminho (+ voltas completas).

    350°→10° vai por 360° (delta +20°), não pela volta completa.
    `voltas` soma voltas inteiras no sentido do movimento (futuro:
    "dar uma volta completa" sem gambiarra).
    """
    delta = ((float(para_graus) - float(de_graus) + 180.0) % 360.0) - 180.0
    voltas = int(voltas or 0)
    if voltas:
        sentido = 1.0 if delta >= 0 else -1.0
        # delta == -180 é ambíguo: trata como +180 (horário).
        if delta == -180.0:
            sentido, delta = 1.0, 180.0
        delta += sentido * 360.0 * abs(voltas)
    return float(de_graus) + delta * e


def interpolar_transform(inicio: Transform, fim: Transform,
                         e: float, voltas: int = 0) -> Transform:
    """Transform A → B (posição, rotação menor caminho, escala, opacidade).

    O pivô do resultado é o de destino (permanece coerente).
    """
    return Transform(
        x=inicio.x + (fim.x - inicio.x) * e,
        y=inicio.y + (fim.y - inicio.y) * e,
        rotacao=interpolar_angulo(inicio.rotacao, fim.rotacao, e, voltas),
        escala_x=inicio.escala_x + (fim.escala_x - inicio.escala_x) * e,
        escala_y=inicio.escala_y + (fim.escala_y - inicio.escala_y) * e,
        opacidade=max(0.0, min(1.0, inicio.opacidade
                               + (fim.opacidade - inicio.opacidade) * e)),
        pivo_x=fim.pivo_x, pivo_y=fim.pivo_y,
        pivo_unidade_x=fim.pivo_unidade_x,
        pivo_unidade_y=fim.pivo_unidade_y,
    )


def vetor_para(origem: Vector2, destino: Vector2) -> Vector2:
    """Deslocamento destino − origem (base do futuro mover_para)."""
    return destino - origem


def mover_por_ponto(atual: Vector2, deslocamento: Vector2) -> Vector2:
    """Movimento relativo: atual + deslocamento (ex. (100,100)+(50,20))."""
    return atual + deslocamento


# ----- keyframes -----

@dataclass
class Keyframe:
    """Estado em um ponto do tempo: tempo em [0, 1], valores por prop."""

    tempo: float
    valores: dict = field(default_factory=dict)  # prop -> float|tupla
    linha: int = 0

    def __post_init__(self) -> None:
        self.tempo = float(self.tempo)
        if not 0.0 <= self.tempo <= 1.0:
            raise ErroELiXX(
                f"Keyframe fora do tempo: {self.tempo!r}. Use 0%..100%.",
                linha=self.linha)


def avaliar_keyframes(frames: list[Keyframe], prop: str, t: float,
                      ease=None) -> object:
    """Valor da prop no progresso t (interpolação entre quadros, por prop).

    Quadros esparsos: cada prop usa seus próprios vizinhos (ausência =
    mantém o vizinho conhecido). Segmento local recebe a curva
    (padrão: linear) — a curva é aplicada por segmento, não global.
    """
    if not frames:
        raise ErroELiXX("Motion sem keyframes não pode ser avaliado.")
    ease = ease or (lambda u: u)
    ordenados = sorted(frames, key=lambda k: k.tempo)
    t = max(0.0, min(1.0, float(t)))
    # prop constante? (só existe num quadro)
    conhecidos = [(k.tempo, k.valores[prop]) for k in ordenados
                  if prop in k.valores]
    if not conhecidos:
        raise ErroELiXX(
            f'Propriedade "{prop}" não aparece nos keyframes.')
    if len(conhecidos) == 1 or t <= conhecidos[0][0]:
        return conhecidos[0][1]
    if t >= conhecidos[-1][0]:
        return conhecidos[-1][1]
    for (t0, v0), (t1, v1) in zip(conhecidos, conhecidos[1:]):
        if t0 <= t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            e = ease(u)
            if isinstance(v0, (tuple, list)) and isinstance(
                    v1, (tuple, list)):
                return tuple(a + (b - a) * e for a, b in zip(v0, v1))
            if prop == "rotacao":
                return interpolar_angulo(float(v0), float(v1), e)
            return float(v0) + (float(v1) - float(v0)) * e
    return conhecidos[-1][1]


# ----- spring dinâmico (sistema com estado; ≠ easing mola) -----

class Spring:
    """Mola semi-implícita de Euler (estável com subpassos).

    Parâmetros: rigidez k, amortecimento c, massa m. Integração em
    subpassos de até 1/120s (sem explosão com parâmetros comuns).
    Convergência: |x−alvo| e |v| abaixo da tolerância.
    """

    def __init__(self, rigidez: float = 180.0, amortecimento: float = 12.0,
                 massa: float = 1.0, tolerancia: float = 0.001) -> None:
        for nome, valor, minimo in (("rigidez", rigidez, 0.0),
                                    ("amortecimento", amortecimento, 0.0),
                                    ("massa", massa, 0.0)):
            numero = float(valor)
            if not math.isfinite(numero) or numero <= minimo:
                raise ErroELiXX(
                    f'Spring inválido: "{nome}" = {valor!r}. '
                    "Use número positivo.",
                    exemplo="rigidez: 180")
        self.rigidez = float(rigidez)
        self.amortecimento = float(amortecimento)
        self.massa = float(massa)
        self.tolerancia = float(tolerancia)
        self.posicao = 0.0
        self.velocidade = 0.0

    def fixar(self, posicao: float) -> None:
        """Estado inicial (posição atual, velocidade zero)."""
        self.posicao = float(posicao)
        self.velocidade = 0.0

    def passo(self, dt_ms: float, alvo: float) -> float:
        """Avança a dinâmica e devolve a posição (dt em ms)."""
        restante = max(0.0, float(dt_ms) / 1000.0)
        while restante > 0.0:
            passo = min(restante, 1.0 / 120.0)
            restante -= passo
            forca = (-self.rigidez * (self.posicao - float(alvo))
                     - self.amortecimento * self.velocidade)
            self.velocidade += forca / self.massa * passo
            self.posicao += self.velocidade * passo
        return self.posicao

    def convergiu(self, alvo: float) -> bool:
        """Perto do alvo e quase parado (pronto para o snap final)."""
        return (abs(self.posicao - float(alvo)) <= self.tolerancia
                and abs(self.velocidade) <= self.tolerancia)


# ----- Motion (plano) e MotionGroup (composição, sem segundo motor) -----

@dataclass
class Motion:
    """Plano de movimento: O QUE deve acontecer (dados + matemática).

    O `MotorAnimacoes` executa; aqui fica o plano explícito com
    progresso separado da curva (futura ponte para IA/behavior).
    """

    alvo: str
    propriedades: list = field(default_factory=list)
    inicio: dict = field(default_factory=dict)
    fim: dict = field(default_factory=dict)
    duracao_ms: float = 500.0
    atraso_ms: float = 0.0
    curva_nome: str = "suave"
    modo: str = "normal"
    linha: int = 0

    def progresso(self, tempo_ms: float) -> float:
        """t em [0, 1] (tempo puro; a curva aplica-se depois)."""
        return progresso_tempo(tempo_ms, self.duracao_ms)

    def avaliar(self, tempo_ms: float) -> dict:
        """{prop: valor} no tempo (curva + interpolação F10)."""
        t = self.progresso(tempo_ms)
        ease = curva(self.curva_nome)
        e = ease(t)
        saida = {}
        for prop in self.propriedades:
            if prop not in self.inicio or prop not in self.fim:
                continue
            v0, v1 = self.inicio[prop], self.fim[prop]
            if isinstance(v0, (tuple, list)):
                saida[prop] = tuple(a + (b - a) * e
                                    for a, b in zip(v0, v1))
            elif prop == "rotacao":
                saida[prop] = interpolar_angulo(float(v0), float(v1), e)
            elif prop == "opacidade":
                saida[prop] = max(0.0, min(1.0, float(v0)
                                           + (float(v1) - float(v0)) * e))
            else:
                saida[prop] = float(v0) + (float(v1) - float(v0)) * e
        return saida


class MotionGroup:
    """Organiza Motions (sequência/paralelo) sobre UM motor existente.

    Não interpola nada: só liga `depois` (sequência) e dispara inícios.
    """

    def __init__(self, nome: str, motor, membros: list[str],
                 modo: str = "paralelo") -> None:
        if modo not in ("paralelo", "sequencia"):
            raise ErroELiXX(
                f'Modo de grupo inválido: {modo!r}. '
                'Use "paralelo" ou "sequencia".')
        self.nome = nome
        self.motor = motor
        self.membros = list(membros)
        self.modo = modo

    def preparar(self) -> None:
        """Sequência: encadeia depois; paralelo: nada a fazer."""
        if self.modo != "sequencia":
            return
        for anterior, proximo in zip(self.membros, self.membros[1:]):
            ex = self.motor.execucoes.get(proximo)
            if ex is not None:
                ex.definicao.depois = anterior
                if ex.estado not in ("concluida", "cancelada"):
                    ex.estado = "aguardando"

    def iniciar(self) -> None:
        """Dispara o grupo (primeiro da sequência ou todos em paralelo)."""
        if self.modo == "sequencia" and self.membros:
            self.motor.iniciar(self.membros[0])
        else:
            for nome in self.membros:
                self.motor.iniciar(nome)

    def estado(self) -> str:
        """Agregado determinístico: concluída só se todas concluídas."""
        estados = [self.motor.execucoes[n].estado for n in self.membros
                   if n in self.motor.execucoes]
        if not estados:
            return "aguardando"
        if all(e == "concluida" for e in estados):
            return "concluida"
        if any(e == "rodando" for e in estados):
            return "rodando"
        if any(e == "cancelada" for e in estados):
            return "cancelada"
        return estados[0]
