"""Motion Synthesis da ELiXX (Fase 16).

Transforma TraversalPlan (F15) em MotionPlan executável pelo Motion
Core (F11) sobre Transform (F10) e Character (F12):

    TraversalPlan → MotionSynthesizer → MotionPlan → Motion F11

SÍNTESE ≠ EXECUÇÃO: sintetizar() só descreve; MotionPlan.executar()
carrega no motor existente (sem threads, sem loop paralelo, sem
física geral, sem IA). Destino final sempre exato (snap do F11).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..animacao.motion import Keyframe
from ..animacao.motor import ChaveAnimacao, DefinicaoAnimacao
from ..erros import ErroELiXX
from .transform import Vector2

__all__ = [
    "MODOS_SINTESE", "VELOCIDADES_PADRAO", "POSES_SUGERIDAS",
    "MotionStep", "MotionPlan", "MotionSynthesizer",
    "debug_sintese_movimento",
]

MODOS_SINTESE = ("andar", "correr", "pular", "escalar", "descer", "voar",
                 "pairar", "teleportar")
"""Modos com síntese própria (descritores; sem comportamento)."""

VELOCIDADES_PADRAO = {
    "andar": 200.0,
    "correr": 400.0,
    "escalar": 120.0,
    "descer": 120.0,
    "voar": 300.0,
    "pairar": 150.0,
}
"""px/s por modo de deslocamento (determinísticos; configuráveis)."""

POSES_SUGERIDAS = {
    "andar": "andar",
    "correr": "correr",
    "pular": "pular",
    "escalar": "escalar",
    "descer": "descer",
    "voar": "voar",
    "pairar": "pairar",
    "teleportar": "teleportar",
}
"""Metadado pose_sugerida por modo (F12 decide se executa)."""


def orientacao_graus(origem: Vector2, destino: Vector2) -> float | None:
    """Ângulo horário do deslocamento (direita=0, baixo=90, esq=180).

    Usa a convenção ELiXX (graus horários, Y para baixo): atan2 direto.
    Deslocamento nulo → None (mantém orientação atual).
    """
    dx = float(destino.x) - float(origem.x)
    dy = float(destino.y) - float(origem.y)
    if dx == 0.0 and dy == 0.0:
        return None
    return math.degrees(math.atan2(dy, dx))


@dataclass
class MotionStep:
    """Uma etapa sintetizada: modo + waypoints + motion F11."""

    modo: str
    origem: str = ""
    destino: str = ""
    waypoint_inicial: Vector2 = field(default_factory=Vector2)
    waypoint_final: Vector2 = field(default_factory=Vector2)
    duracao_ms: float = 500.0
    requisitos: list = field(default_factory=list)
    orientacao: float | None = None  # graus horários (None = mantém)
    motion: object = None  # DefinicaoAnimacao (ou None se espera)
    disparo: str = "sequencia"  # sequencia | paralelo | espera
    espera_ms: float = 0.0
    pose_sugerida: str | None = None
    metadados: dict = field(default_factory=dict)


@dataclass
class MotionPlan:
    """Descrição executável: steps → motor existente (sem mover aqui)."""

    origem: str = ""
    destino: str = ""
    steps: list = field(default_factory=list)  # MotionStep
    modos: list = field(default_factory=list)
    requisitos: list = field(default_factory=list)
    duracao_total_ms: float = 0.0
    viavel: bool = True
    motivo: str = "Plano sintetizado."
    nome_alvo: str = ""

    def definicoes(self) -> list:
        """DefinicaoAnimacao dos steps (ordem determinística)."""
        return [s.motion for s in self.steps if s.motion is not None]

    def carregar(self, motor, cena) -> list[str]:
        """Carrega no motor com encadeamento (sem iniciar)."""
        nomes: list[str] = []
        anterior: str | None = None
        for step in self.steps:
            definicao = step.motion
            if definicao is None:
                continue
            if step.disparo == "sequencia" and anterior is not None:
                definicao.depois = anterior
            if step.espera_ms:
                definicao.atraso_ms = float(step.espera_ms)
            motor.carregar([definicao], cena)
            nomes.append(definicao.nome)
            if step.disparo != "paralelo":
                anterior = definicao.nome
        return nomes

    def executar(self, motor, cena) -> dict:
        """Carrega + inicia (sequência encadeada, paralelos juntos).

        Reutiliza o executor/motor existente; não cria threads.
        """
        nomes = self.carregar(motor, cena)
        if not nomes:
            return {"iniciados": [], "estado": "vazio",
                    "motivo": "Plano sem motions."}
        primeiro = self.steps[0].motion
        if primeiro is not None and primeiro.depois is None:
            motor.iniciar(primeiro.nome)
        else:
            for step in self.steps:
                if step.motion is not None and step.disparo == "paralelo":
                    motor.iniciar(step.motion.nome)
            if not any(s.disparo == "paralelo" and s.motion is not None
                       for s in self.steps) and nomes:
                motor.iniciar(nomes[0])
        return {"iniciados": nomes, "estado": "executando",
                "motivo": f"{len(nomes)} motion(s) no motor."}


class MotionSynthesizer:
    """TraversalPlan → MotionPlan (só descreve; F11 executa).

    Parâmetros determinísticos (sem configuração global):
    velocidades px/s por modo, altura_do_pulo, curva, orientar,
    virar_antes (gira antes) ou virar_durante (gira junto),
    duracao_rotacao_ms, amplitude/pairar, duracao (override total? não:
    por etapa via duracao_ms só em teleport/espera — ver abaixo).
    """

    def __init__(self, velocidades: dict | None = None,
                 altura_pulo: float = 60.0, curva: str = "suave",
                 orientar: bool = True, virar_antes: bool = False,
                 duracao_rotacao_ms: float = 250.0,
                 amplitude_pairar: float = 8.0,
                 acelerar_voo: bool = False,
                 desacelerar_voo: bool = True) -> None:
        velocidades = dict(velocidades or {})
        for modo, valor in velocidades.items():
            numero = float(valor)
            if not math.isfinite(numero) or numero <= 0:
                raise ErroELiXX(
                    f'Velocidade inválida para "{modo}": {valor!r}. '
                    "Use número positivo (px/s).")
        self.velocidades = dict(VELOCIDADES_PADRAO)
        self.velocidades.update({k: float(v)
                                 for k, v in velocidades.items()})
        altura = float(altura_pulo)
        if not math.isfinite(altura) or altura < 0:
            raise ErroELiXX(
                f'Altura de pulo inválida: {altura_pulo!r}. Use ≥ 0.')
        self.altura_pulo = altura
        from ..animacao.motion import curva as _curva

        try:
            _curva(curva)
        except ErroELiXX as exc:
            raise ErroELiXX(
                f'Curva de síntese inválida: {curva!r}. {exc.mensagem}')
        self.curva = curva
        self.orientar = bool(orientar)
        self.virar_antes = bool(virar_antes)
        duracao_rot = float(duracao_rotacao_ms)
        if not math.isfinite(duracao_rot) or duracao_rot < 0:
            raise ErroELiXX(
                f'Duração de rotação inválida: {duracao_rotacao_ms!r}.')
        self.duracao_rotacao_ms = duracao_rot
        amp = float(amplitude_pairar)
        if not math.isfinite(amp) or amp < 0:
            raise ErroELiXX(
                f'Amplitude de pairar inválida: {amplitude_pairar!r}.')
        self.amplitude_pairar = amp
        self.acelerar_voo = bool(acelerar_voo)
        self.desacelerar_voo = bool(desacelerar_voo)

    # ----- entrada principal -----

    def sintetizar(self, traversal_plan, grafo, alvo, holder=None,
                   mundo=None) -> MotionPlan:
        """TraversalPlan → MotionPlan (waypoints do F15 preservados).

        `alvo`: Character (move o root) ou nome de nó da cena.
        Requisitos de cada etapa avaliados contra o holder (plano
        inviável = estruturado, sem exceção).
        """
        nome_alvo = self._nome_alvo(alvo)
        etapas = list(getattr(traversal_plan, "etapas", [])
                      or getattr(getattr(traversal_plan, "path", None),
                                 "etapas", lambda: [])())
        if callable(etapas):
            etapas = etapas()
        plano = MotionPlan(origem=str(getattr(traversal_plan, "origem", "")),
                           destino=str(getattr(traversal_plan, "destino",
                                               "")),
                           nome_alvo=nome_alvo)
        if not etapas:
            plano.viavel = False
            plano.motivo = "Plano de travessia vazio (sem etapas)."
            return plano
        for indice, etapa in enumerate(etapas):
            steps = self._sintetizar_etapa(etapa, grafo, nome_alvo, indice,
                                           holder, mundo)
            if not steps:
                plano.viavel = False
                plano.motivo = (
                    f'Etapa {indice} inviável '
                    f'({etapa.get("de", "?")} -> {etapa.get("para", "?")}).')
                plano.steps = []
                plano.modos = []
                plano.requisitos = []
                plano.duracao_total_ms = 0.0
                return plano
            plano.steps.extend(steps)
        plano.modos = []
        for step in plano.steps:
            if step.modo not in plano.modos:
                plano.modos.append(step.modo)
        plano.requisitos = []
        for step in plano.steps:
            for requisito in step.requisitos:
                if requisito not in plano.requisitos:
                    plano.requisitos.append(requisito)
        plano.duracao_total_ms = sum(s.duracao_ms + s.espera_ms
                                     for s in plano.steps)
        return plano

    # ----- núcleo por etapa -----

    def _sintetizar_etapa(self, etapa: dict, grafo, nome_alvo: str,
                          indice: int, holder, mundo) -> list:
        """Etapa → 1 step (ou [giro, move] com virar_antes; [] = inviável)."""
        modo = str(etapa.get("modo", "andar"))
        if modo not in MODOS_SINTESE:
            raise ErroELiXX(
                f'Modo de síntese não suportado: "{modo}". '
                f'Válidos: {", ".join(MODOS_SINTESE)}.')
        no_de = etapa.get("de", "?")
        no_para = etapa.get("para", "?")
        p0 = self._posicao_no(grafo, no_de, indice, "origem")
        p1 = self._posicao_no(grafo, no_para, indice, "destino")
        requisitos = list(etapa.get("requisitos", []))
        if holder is not None:
            for requisito in requisitos:
                if not self._tem_requisito(holder, requisito):
                    return []
        base = f"passo_{indice:02d}_{modo}"
        orientacao = (orientacao_graus(p0, p1) if self.orientar
                      and modo != "teleportar" else None)
        construtor = getattr(self, f"_modo_{modo}")
        step = construtor(base, nome_alvo, no_de, no_para, p0, p1,
                          requisitos, orientacao)
        step.pose_sugerida = POSES_SUGERIDAS[modo]
        step.metadados["pose_sugerida"] = POSES_SUGERIDAS[modo]
        previos = step.metadados.pop("giro_previo", None)
        if previos is not None:
            previos.pose_sugerida = POSES_SUGERIDAS[modo]
            previos.metadados["pose_sugerida"] = POSES_SUGERIDAS[modo]
            previos.metadados["vira_antes"] = True
            return [previos, step]
        if etapa.get("relativo") and step.motion is not None:
            # Fase 11: deslocamento relativo; waypoints absolutos viram
            # delta (para − p0) com de=None (captura o atual). Só vale
            # para chaves simples (pular/pairar usam keyframes absolutos).
            for chave in step.motion.chaves:
                if (chave.propriedade == "posicao"
                        and isinstance(chave.para, (tuple, list))):
                    chave.para = (float(chave.para[0]) - float(p0.x),
                                  float(chave.para[1]) - float(p0.y))
            step.motion.relativo = True
            step.metadados["relativo"] = True
        return [step]

    # ----- utilidades -----

    @staticmethod
    def _nome_alvo(alvo) -> str:
        """Character → nome do nó root; str → nome do nó."""
        no_raiz = getattr(alvo, "no_raiz", None)
        if no_raiz is not None:
            nome = getattr(no_raiz, "nome", None)
            if not nome:
                raise ErroELiXX(
                    "Personagem sem nó root nomeado (fora do pipeline?).")
            return str(nome)
        if isinstance(alvo, str) and alvo.strip():
            return alvo.strip()
        raise ErroELiXX(
            "Alvo de síntese inválido: use Character ou nome de nó.",
            exemplo="sintetizar(plano, heroi)")

    @staticmethod
    def _posicao_no(grafo, no_id: str, indice: int, papel: str) -> Vector2:
        try:
            no = grafo.nos[no_id]
        except KeyError:
            raise ErroELiXX(
                f"Etapa {indice}: {papel} {no_id!r} fora do grafo.")
        posicao = no.posicao()
        return Vector2(float(posicao.x), float(posicao.y))

    @staticmethod
    def _tem_requisito(holder, requisito: str) -> bool:
        from .capacidades import tem_capacidade

        return bool(tem_capacidade(holder, requisito))

    def _duracao_deslocamento(self, modo: str, p0: Vector2,
                              p1: Vector2) -> float:
        velocidade = self.velocidades.get(modo, 200.0)
        distancia = p0.distancia(p1)
        if distancia <= 0:
            return 0.0
        return distancia / velocidade * 1000.0

    def _nome_motion(self, base: str, sufixo: str = "") -> str:
        return f"{base}{('_' + sufixo) if sufixo else ''}"

    def _chave_pos(self, para: Vector2) -> ChaveAnimacao:
        return ChaveAnimacao("posicao", None,
                             (float(para.x), float(para.y)))

    def _chave_rot(self, angulo: float) -> ChaveAnimacao:
        return ChaveAnimacao("rotacao", None, float(angulo))

    def _deslocamento(self, base: str, nome_alvo: str, no_de: str,
                      no_para: str, p0: Vector2, p1: Vector2,
                      requisitos: list, orientacao, modo: str,
                      movimento: str | None = None) -> MotionStep:
        """Núcleo andar/correr/escalar/descer/voar (sem duplicar)."""
        chaves = [self._chave_pos(p1)]
        if orientacao is not None and not self.virar_antes:
            chaves.append(self._chave_rot(orientacao))
        duracao = self._duracao_deslocamento(modo, p0, p1)
        motion = DefinicaoAnimacao(
            nome=self._nome_motion(base), alvo=nome_alvo, chaves=chaves,
            duracao_ms=duracao, movimento=movimento or self.curva)
        step = MotionStep(modo=modo, origem=no_de, destino=no_para,
                          waypoint_inicial=p0, waypoint_final=p1,
                          duracao_ms=duracao, requisitos=requisitos,
                          orientacao=orientacao, motion=motion)
        if orientacao is not None and self.virar_antes:
            giro = MotionStep(
                modo=modo, origem=no_de, destino=no_de,
                waypoint_inicial=p0, waypoint_final=p0,
                duracao_ms=self.duracao_rotacao_ms, requisitos=[],
                orientacao=orientacao,
                motion=DefinicaoAnimacao(
                    nome=self._nome_motion(base, "girar"), alvo=nome_alvo,
                    chaves=[self._chave_rot(orientacao)],
                    duracao_ms=self.duracao_rotacao_ms,
                    movimento=self.curva))
            giro.pose_sugerida = POSES_SUGERIDAS[modo]
            giro.metadados["pose_sugerida"] = POSES_SUGERIDAS[modo]
            giro.metadados["vira_antes"] = True
            # Sequência virar→mover via depois (F11, sem motor novo).
            motion.depois = giro.motion.nome
            motion.inicio = "manual"
            step.metadados["giro_previo"] = giro
        return step

    # ----- modos -----

    def _modo_andar(self, base, nome_alvo, no_de, no_para, p0, p1,
                    requisitos, orientacao) -> MotionStep:
        return self._deslocamento(base, nome_alvo, no_de, no_para, p0, p1,
                                  requisitos, orientacao, "andar")

    def _modo_correr(self, base, nome_alvo, no_de, no_para, p0, p1,
                     requisitos, orientacao) -> MotionStep:
        return self._deslocamento(base, nome_alvo, no_de, no_para, p0, p1,
                                  requisitos, orientacao, "correr")

    def _modo_escalar(self, base, nome_alvo, no_de, no_para, p0, p1,
                      requisitos, orientacao) -> MotionStep:
        return self._deslocamento(base, nome_alvo, no_de, no_para, p0, p1,
                                  requisitos, orientacao, "escalar")

    def _modo_descer(self, base, nome_alvo, no_de, no_para, p0, p1,
                     requisitos, orientacao) -> MotionStep:
        return self._deslocamento(base, nome_alvo, no_de, no_para, p0, p1,
                                  requisitos, orientacao, "descer")

    def _modo_voar(self, base, nome_alvo, no_de, no_para, p0, p1,
                   requisitos, orientacao) -> MotionStep:
        if self.acelerar_voo and not self.desacelerar_voo:
            movimento = "acelerar"
        elif self.desacelerar_voo and not self.acelerar_voo:
            movimento = "desacelerar"
        else:
            movimento = self.curva
        return self._deslocamento(base, nome_alvo, no_de, no_para, p0, p1,
                                  requisitos, orientacao, "voar",
                                  movimento=movimento)

    def _modo_pular(self, base, nome_alvo, no_de, no_para, p0, p1,
                    requisitos, orientacao) -> MotionStep:
        """Trajetória determinística em keyframes (sem física).

        0% início → 30% subida → 50% ápice → 70% descida → 100% destino
        (snap do F11 garante o ponto final exato).
        """
        altura = self.altura_pulo
        pontos = [
            (0.0, p0),
            (0.3, Vector2(p0.x + (p1.x - p0.x) * 0.3,
                          p0.y + (p1.y - p0.y) * 0.3 - altura * 0.75)),
            (0.5, Vector2((p0.x + p1.x) / 2.0,
                          (p0.y + p1.y) / 2.0 - altura)),
            (0.7, Vector2(p0.x + (p1.x - p0.x) * 0.7,
                          p0.y + (p1.y - p0.y) * 0.7 - altura * 0.75)),
            (1.0, p1),
        ]
        quadros = [Keyframe(tempo=t, valores={
            "posicao": (float(p.x), float(p.y))}) for t, p in pontos]
        chaves = []
        if orientacao is not None and not self.virar_antes:
            chaves.append(self._chave_rot(orientacao))
        distancia = p0.distancia(p1)
        duracao = self._duracao_deslocamento("andar", p0, p1)
        duracao = max(duracao, 200.0) if distancia > 0 else 200.0
        motion = DefinicaoAnimacao(
            nome=self._nome_motion(base), alvo=nome_alvo, chaves=chaves,
            duracao_ms=duracao, movimento=self.curva, keyframes=quadros)
        return MotionStep(modo="pular", origem=no_de, destino=no_para,
                          waypoint_inicial=p0, waypoint_final=p1,
                          duracao_ms=duracao, requisitos=requisitos,
                          orientacao=orientacao, motion=motion,
                          metadados={"altura": altura})

    def _modo_pairar(self, base, nome_alvo, no_de, no_para, p0, p1,
                     requisitos, orientacao) -> MotionStep:
        """Desloca até o destino e oscila 2× (determinístico, fim exato)."""
        amp = self.amplitude_pairar
        quadros = [
            Keyframe(tempo=0.0, valores={
                "posicao": (float(p0.x), float(p0.y))}),
            Keyframe(tempo=0.6, valores={
                "posicao": (float(p1.x), float(p1.y))}),
            Keyframe(tempo=0.7, valores={
                "posicao": (float(p1.x), float(p1.y - amp))}),
            Keyframe(tempo=0.8, valores={
                "posicao": (float(p1.x), float(p1.y + amp))}),
            Keyframe(tempo=0.9, valores={
                "posicao": (float(p1.x), float(p1.y - amp / 2.0))}),
            Keyframe(tempo=1.0, valores={
                "posicao": (float(p1.x), float(p1.y))}),
        ]
        chaves = []
        if orientacao is not None and not self.virar_antes:
            chaves.append(self._chave_rot(orientacao))
        duracao = self._duracao_deslocamento("pairar", p0, p1)
        duracao = max(duracao, 400.0) if p0.distancia(p1) > 0 else 400.0
        motion = DefinicaoAnimacao(
            nome=self._nome_motion(base), alvo=nome_alvo, chaves=chaves,
            duracao_ms=duracao, movimento=self.curva, keyframes=quadros)
        return MotionStep(modo="pairar", origem=no_de, destino=no_para,
                          waypoint_inicial=p0, waypoint_final=p1,
                          duracao_ms=duracao, requisitos=requisitos,
                          orientacao=orientacao, motion=motion,
                          metadados={"amplitude": amp})

    def _modo_teleportar(self, base, nome_alvo, no_de, no_para, p0, p1,
                         requisitos, orientacao) -> MotionStep:
        """Mudança estrutural instantânea (sem interpolar, sem girar)."""
        motion = DefinicaoAnimacao(
            nome=self._nome_motion(base), alvo=nome_alvo,
            chaves=[self._chave_pos(p1)], duracao_ms=0.0,
            movimento="linear")
        return MotionStep(modo="teleportar", origem=no_de, destino=no_para,
                          waypoint_inicial=p0, waypoint_final=p1,
                          duracao_ms=0.0, requisitos=requisitos,
                          orientacao=None, motion=motion)


def debug_sintese_movimento(plano: MotionPlan) -> str:
    """Diagnóstico puro: plano/etapas/modo/duração/orientação (sem mover)."""
    linhas = [f"MotionPlan {plano.origem or '?'} -> "
               f"{plano.destino or '?'}: "
               f"{len(plano.steps)} etapa(s), "
               f"{plano.duracao_total_ms:.0f}ms, "
               f"viavel={plano.viavel}"]
    if not plano.viavel:
        linhas.append(f"  motivo: {plano.motivo}")
        return "\n".join(linhas)
    for indice, step in enumerate(plano.steps):
        p0, p1 = step.waypoint_inicial, step.waypoint_final
        orientacao = ("--" if step.orientacao is None
                      else f"{step.orientacao:.0f}°")
        requisitos = ",".join(step.requisitos) or "--"
        linhas.append(
            f"  [{indice:02d}] {step.modo} {step.origem} -> {step.destino} "
            f"({p0.x:g},{p0.y:g}) -> ({p1.x:g},{p1.y:g}) "
            f"{step.duracao_ms:.0f}ms ori={orientacao} req={requisitos} "
            f"disparo={step.disparo}")
    return "\n".join(linhas)
