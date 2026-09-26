"""Behavior Synthesis da ELiXX (Fase 17).

Responde: "como o personagem deve se comportar visualmente enquanto
executa um movimento?" NÃO decide objetivos, rotas ou ações (isso é
das próximas fases); NÃO é IA, planner, física ou comportamento
autônomo.

    MotionPlan (F16) + Character (F12)
        ↓ BehaviorSynthesizer.sintetizar
    BehaviorPlan (tracks: movimento, pose, gesto, expressão)
        ↓ BehaviorPlan.executar(motor, cena, character)
    Motion F11 (único motor) + Pose/Gesture F12 (reutilizados)

Sincronização via callbacks F11 (ao_comecar/ao_terminar/ao_cancelar,
que aceitam ganchos Python desde F17) + marcadores para o meio
(motion vazio com atraso, sem scheduler novo). Sem threads.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..erros import ErroELiXX

__all__ = [
    "PRIORIDADES",
    "TRACKS",
    "ESTADOS_CORPORAIS",
    "POSES_POR_MODO",
    "BehaviorEvent",
    "BehaviorTrack",
    "BehaviorStep",
    "BehaviorPlan",
    "BehaviorSynthesizer",
    "debug_comportamento",
]

PRIORIDADES = ("emergencia", "gesto", "comportamento", "padrao")
"""Ordem de vitória por (parte, prop): emergência primeiro."""

TRACKS = ("movimento", "pose", "gesto", "expressao")
"""Trilhas paralelas de um BehaviorPlan."""

ESTADOS_CORPORAIS = ("parado", "andando", "correndo", "pulando",
                     "escalando", "voando", "pairando", "interagindo")
"""Estados como dados estruturados (sem máquina autônoma)."""

POSES_POR_MODO = {
    "andar": "andar",
    "correr": "correr",
    "pular": "pulo",
    "escalar": "escalar",
    "descer": "descer",
    "voar": "voando",
    "pairar": "pairar",
    "teleportar": None,
}
"""Pose sugerida por modo de travessia (só se existir no personagem)."""


@dataclass
class BehaviorEvent:
    """Evento de sincronização: quando + o quê (dado, sem loop)."""

    quando: str = "ao_comecar"  # ao_comecar|ao_meio|ao_terminar|ao_cancelar
    acao: str = ""  # pose|gesto|expressao|restaurar
    alvo: str = ""  # nome da pose/gesto/expressão
    linha: int = 0

    def __post_init__(self) -> None:
        if self.quando not in ("ao_comecar", "ao_meio", "ao_terminar",
                               "ao_cancelar"):
            raise ErroELiXX(
                f'Evento inválido: "{self.quando}". Válidos: ao_comecar, '
                "ao_meio, ao_terminar, ao_cancelar.")


@dataclass
class BehaviorTrack:
    """Uma trilha paralela: [(step_idx, carga)] em ordem determinística."""

    nome: str = ""
    passos: list = field(default_factory=list)  # [(int, str|None)]

    def __post_init__(self) -> None:
        if self.nome not in TRACKS:
            raise ErroELiXX(
                f'Track inválida: "{self.nome}". Válidas: '
                f"{', '.join(TRACKS)}.")


@dataclass
class BehaviorStep:
    """Um passo: motion F16 + camadas corporais + eventos + requisitos."""

    nome: str = ""
    motion_step: object = None  # MotionStep F16 (origem/destino/motion)
    pose: object = None  # str|Pose|None (comportamento)
    pose_fim: object = None  # str|Pose|None (restauração explícita)
    gesture: object = None  # str|Gesture|None (registro_gestos p/ str)
    expression: object = None  # str|Pose|None (camada separada)
    pose_padrao: object = None  # str|Pose|None (base, menor prioridade)
    prioridade: str = "comportamento"  # emergencia|gesto|comportamento|padrao
    restaurar: bool = True
    eventos: list = field(default_factory=list)  # BehaviorEvent
    requisitos: list = field(default_factory=list)
    estado: str | None = None  # dado de ESTADOS_CORPORAIS
    metadados: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.prioridade not in PRIORIDADES:
            raise ErroELiXX(
                f'Prioridade inválida: "{self.prioridade}". Válidas: '
                f"{', '.join(PRIORIDADES)}.")
        if self.estado is not None and self.estado not in ESTADOS_CORPORAIS:
            raise ErroELiXX(
                f'Estado corporal inválido: "{self.estado}". Válidos: '
                f"{', '.join(ESTADOS_CORPORAIS)}.")
        for evento in self.eventos:
            if not isinstance(evento, BehaviorEvent):
                raise ErroELiXX(
                    "Evento de behavior deve ser BehaviorEvent "
                    f"(recebido {evento!r}).")


@dataclass
class BehaviorPlan:
    """Descrição executável (não move nada sozinho)."""

    nome: str = ""
    personagem: str = ""
    steps: list = field(default_factory=list)  # BehaviorStep
    tracks: list = field(default_factory=list)  # BehaviorTrack
    viavel: bool = True
    motivo: str = "Plano de comportamento sintetizado."
    requisitos: list = field(default_factory=list)
    metadados: dict = field(default_factory=dict)

    def motions(self) -> list:
        """Todas as DefinicaoAnimacao (inclui marcadores de meio)."""
        saida = []
        for step in self.steps:
            for motion in step.metadados.get("motions_extras", []):
                saida.append(motion)
            if step.motion_step is not None:
                motion = step.motion_step.motion
                if motion is not None:
                    saida.append(motion)
        return saida

    def executar(self, motor, cena, character) -> dict:
        """Liga ganchos, carrega no motor e inicia (sem threads).

        SÍNTESE separada de EXECUÇÃO: aqui só encadeamento + disparo.
        Respeita `disparo` do MotionStep F16 (sequencia|paralelo).
        """
        nomes: list[str] = []
        anterior: str | None = None
        for indice, step in enumerate(self.steps):
            nomes_step = _executar_step(step, indice, self, motor, cena,
                                        character, anterior)
            nomes.extend(nomes_step)
            principais = [n for n in nomes_step if "_meio" not in n]
            if principais:
                anterior = principais[-1]
        if not nomes:
            return {"iniciados": [], "estado": "vazio",
                    "motivo": "Plano sem motions."}
        return {"iniciados": nomes, "estado": "executando",
                "motivo": f"{len(nomes)} motion(s) no motor."}


def _executar_step(step: BehaviorStep, indice: int, plano: BehaviorPlan,
                   motor, cena, character, anterior: str | None
                   ) -> list[str]:
    """Prepara um step: clona motion, pendura ganchos, carrega, inicia."""
    nomes: list[str] = []
    motion_step = step.motion_step
    definicao = None
    if motion_step is not None and motion_step.motion is not None:
        # Clona para não mutar o MotionPlan (reutilizável).
        definicao = copy.deepcopy(motion_step.motion)
        definicao.nome = f"{plano.nome}_s{indice:02d}_{definicao.nome}"
        if getattr(motion_step, "espera_ms", 0):
            definicao.atraso_ms = float(motion_step.espera_ms)
    contexto = {"motores_gesto": [], "snapshot": None, "meio_marcadores": []}
    executor = getattr(motor, "executor", None)
    if definicao is not None:
        if (getattr(motion_step, "disparo", "sequencia") == "sequencia"
                and anterior is not None and definicao.depois is None):
            # Encadeia no predecessor (F11 `depois`; preserva o já posto).
            definicao.depois = anterior
        definicao.ao_comecar = _encadear(
            definicao.ao_comecar, executor,
            _gancho_inicio(step, character, motor, cena, contexto))
        definicao.ao_terminar = _encadear(
            definicao.ao_terminar, executor,
            _gancho_fim(step, character, motor, contexto))
        definicao.ao_cancelar = _encadear(
            definicao.ao_cancelar, executor,
            _gancho_cancelar(step, character, motor, contexto))
        motor.carregar([definicao], cena)
        nomes.append(definicao.nome)
    else:
        # Sem motion (ex. espera): aplica camadas de uma vez como efeito
        # duradouro do step (sem ganchos para disparar; documentado).
        contexto["snapshot"] = _fotografar(character, step)
        _aplicar_camadas(step, character, motor, cena, contexto)
    for pos, evento in enumerate(step.eventos):
        if evento.quando != "ao_meio":
            continue
        marcador = _marcador_meio(step, indice, pos, plano, character,
                                  motor, contexto,
                                  base_ms=(definicao.duracao_ms
                                           if definicao is not None
                                           else 0.0))
        motor.carregar([marcador], cena)
        nomes.append(marcador.nome)
        contexto["meio_marcadores"].append(marcador.nome)
    # Início: só cabeças de cadeia (com `depois` o F11 encadeia sozinho;
    # marcadores de meio têm atraso próprio e partem junto).
    if definicao is not None and definicao.depois is None:
        motor.iniciar(definicao.nome)
    for marcador_nome in contexto["meio_marcadores"]:
        motor.iniciar(marcador_nome)
    return nomes


def _encadear(anterior, executor, proximo):
    """Compõe callbacks preservando o anterior (AST ou chamável)."""
    if anterior is None:
        return proximo

    def _ambos():
        if callable(anterior):
            anterior()
        elif executor is not None:
            executor.executar_bloco(anterior)
        proximo()

    return _ambos


def _gancho_inicio(step: BehaviorStep, character, motor, cena,
                   contexto: dict):
    """Aplica pose + gesto + expressão no início do motion."""
    def _hook():
        contexto["snapshot"] = _fotografar(character, step)
        _aplicar_camadas(step, character, motor, cena, contexto)
    return _hook


def _gancho_fim(step: BehaviorStep, character, motor, contexto: dict):
    """Restaura snapshot (se pedido) e encerra gestos do step."""
    def _hook():
        _encerrar_gestos(contexto, motor)
        if step.restaurar:
            _restaurar(contexto, character)
        if step.pose_fim is not None:
            character.aplicar_pose(step.pose_fim)
        if step.prioridade == "emergencia" and step.pose is not None:
            # Emergência vence por último (documentado em PRIORIDADES).
            character.aplicar_pose(step.pose)
    return _hook


def _gancho_cancelar(step: BehaviorStep, character, motor,
                     contexto: dict):
    """Cancela tracks temporários sem prender pose/gesto."""
    def _hook():
        _encerrar_gestos(contexto, motor)
        if step.restaurar:
            _restaurar(contexto, character)
    return _hook


def _marcador_meio(step: BehaviorStep, indice: int, pos: int,
                   plano: BehaviorPlan, character, motor, contexto: dict,
                   base_ms: float):
    """Motion vazio com atraso = ponto médio (reuso F11, sem scheduler)."""
    from ..animacao.motor import DefinicaoAnimacao

    atraso = max(0.0, float(base_ms) / 2.0)
    marcador = DefinicaoAnimacao(
        nome=f"{plano.nome}_s{indice:02d}_meio{pos}",
        alvo=character.no_raiz.nome, chaves=[], duracao_ms=1.0,
        atraso_ms=atraso, movimento="linear")
    evento = step.eventos[pos]

    def _hook_meio(ev=evento):
        _disparar_evento_meio(step, ev, character, motor, contexto)

    marcador.ao_comecar = _hook_meio
    return marcador


def _disparar_evento_meio(step: BehaviorStep, evento: BehaviorEvent,
                          character, motor, contexto: dict) -> None:
    """Executa a ação do evento de meio (pose/gesto/expressão)."""
    if evento.acao == "pose" and evento.alvo:
        character.aplicar_pose(evento.alvo)
    elif evento.acao == "expressao" and evento.alvo:
        _aplicar_expressao(step, evento.alvo, character)
    elif evento.acao == "gesto" and evento.alvo:
        registro = step.metadados.get("_registro_gestos", {})
        gesto = registro.get(evento.alvo)
        if gesto is None:
            raise ErroELiXX(
                f'Gesto "{evento.alvo}" não registrado para evento de meio.')
        grupo = character.executar_gesto(gesto, motor)
        contexto["motores_gesto"].append(grupo)
    elif evento.acao == "restaurar":
        _restaurar(contexto, character)


# ----- composição e restauração -----

def _fotografar(character, step: BehaviorStep) -> dict:
    """Snapshot {(parte, prop)} das partes que o step vai tocar."""
    foto: dict = {}
    for pose_like in (step.pose, step.pose_fim, step.pose_padrao,
                      step.expression):
        if pose_like is None:
            continue
        pose = (character.obter_pose(pose_like)
                if isinstance(pose_like, str) else pose_like)
        for parte_nome in pose.partes():
            parte = character.obter_parte(parte_nome)
            for prop in pose.entradas[parte_nome]:
                foto[(parte_nome, prop)] = character._ler_no(parte.no,
                                                             prop)
    return foto


def _restaurar(contexto: dict, character) -> None:
    """Devolve valores fotografados (só estado temporário do step)."""
    foto = contexto.get("snapshot") or {}
    por_parte: dict = {}
    for (parte_nome, prop), valor in foto.items():
        por_parte.setdefault(parte_nome, {})[prop] = valor
    for parte_nome, props in por_parte.items():
        parte = character.obter_parte(parte_nome)
        character._aplicar_props(parte, props)


def _encerrar_gestos(contexto: dict, motor) -> None:
    """Cancela motions de gestos iniciados pelo step (sem prender)."""
    for grupo in contexto.get("motores_gesto", []):
        for nome in getattr(grupo, "membros", []):
            try:
                motor.cancelar(nome)
            except Exception:
                pass
    contexto["motores_gesto"] = []


def _aplicar_camadas(step: BehaviorStep, character, motor, cena,
                     contexto: dict) -> None:
    """padrao → comportamento → gesto → emergencia; expressão separada."""
    if step.pose_padrao is not None:
        character.aplicar_pose(step.pose_padrao)
    if step.pose is not None:
        character.aplicar_pose(step.pose)
    if step.gesture is not None:
        # _resolver_gesto já entregou objeto (str virou Gesture).
        grupo = character.executar_gesto(step.gesture, motor)
        contexto["motores_gesto"].append(grupo)
    if step.expression is not None:
        _aplicar_expressao(step, step.expression, character)


def _aplicar_expressao(step: BehaviorStep, expressao, character) -> None:
    """Expressão só onde o corpo não atuou (nunca sobrescreve pose)."""
    pose = (character.obter_pose(expressao)
            if isinstance(expressao, str) else expressao)
    ocupadas = _partes_ocupadas(step, character)
    filtrada = {p: props for p, props in pose.entradas.items()
                if p not in ocupadas}
    puladas = sorted(set(pose.entradas) - set(filtrada))
    if puladas:
        step.metadados.setdefault("expressao_pulada", []).extend(
            [p for p in puladas
             if p not in step.metadados.get("expressao_pulada", [])])
    if filtrada:
        from .personagem import Pose

        character.aplicar_pose(Pose(nome=f"{pose.nome}/filtrada",
                                    entradas=filtrada,
                                    expressao=True))


def _partes_ocupadas(step: BehaviorStep, character) -> set:
    """Partes já escritas por pose/gesto do step (para a expressão)."""
    ocupadas: set = set()
    for pose_like in (step.pose_padrao, step.pose):
        if pose_like is None:
            continue
        pose = (character.obter_pose(pose_like)
                if isinstance(pose_like, str) else pose_like)
        ocupadas.update(pose.partes())
    gesto = step.gesture
    if gesto is not None:
        # Já resolvido na síntese (objeto Gesture).
        ocupadas.update(_partes_de_gesto(gesto, character))
    return ocupadas


def _partes_de_gesto(gesto, character) -> set:
    """Partes tocadas pelos passos-pose do gesto (estático)."""
    from .personagem import Gesture, Pose

    ocupadas: set = set()
    for passo in getattr(gesto, "passos", []):
        if isinstance(passo, str):
            try:
                ocupadas.update(character.obter_pose(passo).partes())
            except ErroELiXX:
                pass
        elif isinstance(passo, Pose):
            ocupadas.update(passo.partes())
        elif isinstance(passo, Gesture):
            ocupadas.update(_partes_de_gesto(passo, character))
        elif isinstance(passo, dict):
            alvo = passo.get("alvo")
            if isinstance(alvo, str):
                ocupadas.add(alvo)
    return ocupadas


# ----- sintetizador -----

class BehaviorSynthesizer:
    """MotionPlan + Character → BehaviorPlan (sem decidir nada sozinho).

    Mapeia cada MotionStep F16 em BehaviorStep (pose/expressão/gesto
    por modo, explícitos superando padrões). Só descreve; executar()
    do plano dispara no motor existente.
    """

    def __init__(self, poses: dict | None = None,
                 expressoes: dict | None = None,
                 gestos: dict | None = None,
                 registro_gestos: dict | None = None,
                 pose_padrao: object = None,
                 expressao_padrao: object = None,
                 restaurar: bool = True,
                 eventos: dict | None = None,
                 estados: dict | None = None) -> None:
        self.poses = dict(poses or {})
        self.expressoes = dict(expressoes or {})
        self.gestos = dict(gestos or {})
        self.registro_gestos = dict(registro_gestos or {})
        self.pose_padrao = pose_padrao
        self.expressao_padrao = expressao_padrao
        self.restaurar = bool(restaurar)
        self.eventos = dict(eventos or {})  # idx|modo -> [BehaviorEvent]
        self.estados = dict(estados or {})

    def sintetizar(self, motion_plan, character, holder=None,
                   nome: str = "behavior") -> "BehaviorPlan":
        """Compõe tracks por step (valida requisitos e referências)."""
        self._validar_personagem(character)
        holder = holder if holder is not None else character
        steps: list[BehaviorStep] = []
        requisitos: list[str] = []
        faltantes: list[str] = []
        for indice, motion_step in enumerate(
                getattr(motion_plan, "steps", [])):
            for requisito in list(getattr(motion_step, "requisitos", [])):
                if requisito not in requisitos:
                    requisitos.append(requisito)
                if not self._tem_requisito(holder, requisito):
                    faltantes.append(
                        f"{requisito} (passo {indice})")
            step = self._sintetizar_step(motion_step, indice, character,
                                         holder)
            steps.append(step)
        if faltantes:
            vistos: list[str] = []
            for item in faltantes:
                if item not in vistos:
                    vistos.append(item)
            return BehaviorPlan(
                nome=nome, personagem=getattr(character, "nome", "?"),
                steps=[], viavel=False,
                motivo="Capacidade necessária ausente: "
                       + ", ".join(vistos) + ".",
                requisitos=requisitos,
                metadados={"origem": getattr(motion_plan, "origem", ""),
                           "destino": getattr(motion_plan, "destino", "")})
        plano = BehaviorPlan(
            nome=nome,
            personagem=getattr(character, "nome", "?"),
            steps=steps, viavel=True,
            motivo="Plano de comportamento sintetizado.",
            requisitos=requisitos,
            metadados={"origem": getattr(motion_plan, "origem", ""),
                       "destino": getattr(motion_plan, "destino", "")})
        plano.tracks = self._montar_tracks(plano)
        return plano

    # ----- núcleo -----

    def _sintetizar_step(self, motion_step, indice: int, character,
                         holder) -> BehaviorStep:
        modo = getattr(motion_step, "modo", "andar")
        requisitos = list(getattr(motion_step, "requisitos", []))
        pose = self._resolver_pose(self.poses.get(indice,
                                                      self.poses.get(modo)),
                                   POSES_POR_MODO.get(modo), character)
        expressao = self._resolver_pose(
            self.expressoes.get(indice, self.expressoes.get(modo)),
            self.expressao_padrao, character)
        gesto = self._resolver_gesto(
            self.gestos.get(indice, self.gestos.get(modo)), character,
            indice)
        eventos = [self._clonar_evento(e) for e in
                   self.eventos.get(indice, self.eventos.get(modo, []))]
        estado = self.estados.get(modo, self._estado_de_modo(modo))
        step = BehaviorStep(
            nome=f"passo_{indice:02d}_{modo}",
            motion_step=motion_step, pose=pose, gesture=gesto,
            expression=expressao, pose_padrao=self.pose_padrao,
            restaurar=self.restaurar, eventos=eventos,
            requisitos=requisitos, estado=estado,
            metadados={"modo": modo, "motion": getattr(
                getattr(motion_step, "motion", None), "nome", None),
                "_registro_gestos": dict(self.registro_gestos)})
        return step

    # ----- resolução e validação -----

    @staticmethod
    def _validar_personagem(character) -> None:
        no_raiz = getattr(character, "no_raiz", None)
        if no_raiz is None or not getattr(no_raiz, "nome", None):
            raise ErroELiXX(
                "Personagem inválido para behavior (sem nó root nomeado).")
        for metodo in ("obter_pose", "aplicar_pose", "obter_parte"):
            if not callable(getattr(character, metodo, None)):
                raise ErroELiXX(
                    "Personagem inválido para behavior "
                    f'(sem "{metodo}").')

    @staticmethod
    def _tem_requisito(holder, requisito: str) -> bool:
        from .capacidades import tem_capacidade

        return bool(tem_capacidade(holder, requisito))

    def _resolver_pose(self, explicito, padrao, character):
        """Explícita (erro se ausente) ou padrão (None se ausente)."""
        if explicito is not None:
            character.obter_pose(explicito)  # valida; erro claro se faltar
            return explicito
        if padrao is None:
            return None
        try:
            character.obter_pose(padrao)
            return padrao
        except ErroELiXX:
            return None

    def _resolver_gesto(self, gesto, character, indice: int):
        """Objeto Gesture direto ou nome no registro_gestos."""
        if gesto is None:
            return None
        if isinstance(gesto, str):
            try:
                return self.registro_gestos[gesto]
            except KeyError:
                raise ErroELiXX(
                    f'Gesto "{gesto}" do passo {indice} não registrado '
                    f"(passe registro_gestos com o nome).")
        return gesto

    @staticmethod
    def _clonar_evento(evento: BehaviorEvent) -> BehaviorEvent:
        return BehaviorEvent(quando=evento.quando, acao=evento.acao,
                             alvo=evento.alvo, linha=evento.linha)

    @staticmethod
    def _estado_de_modo(modo: str) -> str | None:
        mapa = {"andar": "andando", "correr": "correndo", "pular": "pulando",
                "escalar": "escalando", "voar": "voando",
                "pairar": "pairando", "descer": "interagindo",
                "teleportar": "interagindo"}
        return mapa.get(modo)

    @staticmethod
    def _montar_tracks(plano: "BehaviorPlan") -> list:
        tracks = [BehaviorTrack(nome=nome) for nome in TRACKS]
        por_nome = {t.nome: t for t in tracks}
        for indice, step in enumerate(plano.steps):
            motion = step.motion_step.motion if step.motion_step else None
            por_nome["movimento"].passos.append(
                (indice, getattr(motion, "nome", None)))
            por_nome["pose"].passos.append((indice, _nome_carga(step.pose)))
            por_nome["gesto"].passos.append(
                (indice, _nome_carga(step.gesture)))
            por_nome["expressao"].passos.append(
                (indice, _nome_carga(step.expression)))
        return tracks


def _nome_carga(carga) -> str | None:
    if carga is None:
        return None
    if isinstance(carga, str):
        return carga
    return getattr(carga, "nome", None)


def debug_comportamento(plano: BehaviorPlan) -> str:
    """Diagnóstico puro: estado/motion/pose/gesto/expressão/etapa."""
    linhas = [f"BehaviorPlan {plano.nome or '?'} "
               f"({plano.personagem or '?'}, {len(plano.steps)} passos, "
               f"viavel={plano.viavel})"]
    if not plano.viavel:
        linhas.append(f"  motivo: {plano.motivo}")
        return "\n".join(linhas)
    for indice, step in enumerate(plano.steps):
        motion = step.motion_step.motion if step.motion_step else None
        linhas.append(
            f"  [{indice:02d}] {step.nome} "
            f"estado={step.estado or '--'} "
            f"motion={getattr(motion, 'nome', None) or '--'} "
            f"pose={_nome_carga(step.pose) or '--'} "
            f"gesto={_nome_carga(step.gesture) or '--'} "
            f"expressao={_nome_carga(step.expression) or '--'} "
            f"eventos={len(step.eventos)} "
            f"req={','.join(step.requisitos) or '--'}")
    return "\n".join(linhas)
