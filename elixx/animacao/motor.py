"""Motor de interpolação da ELiXX — Motion Core 2.0 (Fase 11).

Evolução do motor da Fase 03 (mesmas classes, mesmos estados, mesmos
callbacks): o motor escreve SOMENTE na Cena (NoVisual). Cada renderer
aplica o que consegue. Testes usam dt falso — sem Tk, sem tempo real.

Novidades F11 (sem segundo motor): progresso separado da curva,
keyframes, ping_pong, relativo, voltas, spring dinâmico (`fisica:
mola`, distinto do easing `mola`), callbacks começar/cancelar e regra
explícita de conflito (novo substitui antigo na mesma propriedade).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..erros import ErroExecucao
from .easing import EASINGS
from .motion import (FISICAS_MOTION, MODOS_MOTION, Keyframe, Spring,
                     avaliar_keyframes, interpolar_angulo, progresso_tempo)

PROPS_ANIMAVEIS = ("posicao", "tamanho", "escala", "rotacao", "opacidade")


@dataclass
class ChaveAnimacao:
    propriedade: str  # normalizada (sem acento)
    de: object  # None = captura o valor atual ao iniciar
    para: object  # número/tupla ou chamável (alvo dinâmico, Fase 11)
    linha: int = 0


@dataclass
class DefinicaoAnimacao:
    nome: str
    alvo: str
    chaves: list[ChaveAnimacao] = field(default_factory=list)
    duracao_ms: float = 500.0
    atraso_ms: float = 0.0
    movimento: object = "suave"  # nome ou f(t) (Fase 11: paramétrica)
    repetir: object = None  # None = 1x; int = N vezes; "infinito"
    depois: str | None = None
    inicio: str = "automatico"
    ao_terminar: object = None  # Bloco AST, chamável (F17) ou None
    linha: int = 0
    # Fase 11: composição e dinâmica (padrões = comportamento Fase 03).
    modo: str = "normal"  # normal | ping_pong
    relativo: bool = False  # para = deslocamento a partir do atual
    voltas: int = 0  # voltas extras na rotação (chaves, não keyframes)
    fisica: str | None = None  # None | "mola" (dinâmica, ≠ easing)
    rigidez: float = 180.0
    amortecimento: float = 12.0
    massa: float = 1.0
    keyframes: list[Keyframe] = field(default_factory=list)
    ao_comecar: object = None  # Bloco AST, chamável (F17) ou None
    ao_cancelar: object = None  # Bloco AST, chamável (F17) ou None


@dataclass
class Execucao:
    definicao: DefinicaoAnimacao
    no: object  # NoVisual
    estado: str = "aguardando"  # aguardando|atraso|rodando|pausada|...
    tempo_ms: float = 0.0
    rodada: int = 0
    chaves: list[ChaveAnimacao] = field(default_factory=list)
    _retomar_para: str = "rodando"
    # Fase 11: direção da rodada (+1 ida, −1 volta), callbacks 1x e
    # springs por chave (índice → Spring ou lista de Springs).
    direcao: int = 1
    substituida: bool = False
    _comecou: bool = False
    _terminou: bool = False
    _cancelou: bool = False
    springs: dict = field(default_factory=dict)

    @property
    def progresso(self) -> float:
        """t em [0, 1] (tempo puro; a curva aplica-se depois)."""
        if self.estado in ("aguardando", "manual", "atraso"):
            return 0.0
        if self.estado in ("concluida", "cancelada"):
            return 1.0 if self.estado == "concluida" else progresso_tempo(
                self.tempo_ms, self.definicao.duracao_ms)
        return progresso_tempo(self.tempo_ms, self.definicao.duracao_ms)


def _ler_prop(no, prop: str):
    if prop == "posicao":
        return (no.x, no.y)
    if prop == "tamanho":
        if no.largura is None or no.altura is None:
            raise ErroExecucao(
                "Tamanho automático não pode ser animado sem valor 'de'. "
                "Escreva: tamanho: 100px 100px → 200px 200px.",
                linha=no.linha,
            )
        return (no.largura, no.altura)
    if prop == "escala":
        # Fase 10: animação de escala é uniforme (define os dois eixos).
        return getattr(no, "escala_x", no.escala)
    return {"escala": getattr(no, "escala_x", no.escala),
            "rotacao": no.rotacao,
            "opacidade": no.opacidade}[prop]


def _escrever_prop(no, prop: str, valor: object) -> None:
    if prop == "posicao":
        no.x, no.y = float(valor[0]), float(valor[1])
    elif prop == "tamanho":
        no.largura, no.altura = float(valor[0]), float(valor[1])
    elif prop == "escala":
        no.escala = float(valor)  # type: ignore[arg-type]
        no.escala_x = float(valor)  # type: ignore[arg-type]
        no.escala_y = float(valor)  # type: ignore[arg-type]
    elif prop == "rotacao":
        no.rotacao = float(valor)  # type: ignore[arg-type]
    elif prop == "opacidade":
        no.opacidade = max(0.0, min(1.0, float(valor)))  # type: ignore[arg-type]


def _interpola(de: object, para: object, e: float,
                 prop: str = "posicao", voltas: int = 0) -> object:
    if isinstance(de, (tuple, list)) and isinstance(para, (tuple, list)):
        return tuple(d + (p - d) * e for d, p in zip(de, para))
    if prop == "rotacao":
        # Fase 11: menor caminho angular (+ voltas completas opcionais).
        return interpolar_angulo(float(de), float(para), e, voltas)
    return float(de) + (float(para) - float(de)) * e  # type: ignore[arg-type]


def _numero(valor: object) -> float:
    if isinstance(valor, tuple):
        return float(valor[1])
    return float(valor)  # type: ignore[arg-type]


def _zero_como(valor: object) -> object:
    """Zero no formato do valor (escalar ou tupla)."""
    if isinstance(valor, (tuple, list)):
        return tuple(0.0 for _ in valor)
    return 0.0


def _soma(a: object, b: object) -> object:
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return tuple(x + y for x, y in zip(a, b))
    return float(a) + float(b)  # type: ignore[arg-type]


def _sub(a: object, b: object) -> object:
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return tuple(x - y for x, y in zip(a, b))
    return float(a) - float(b)  # type: ignore[arg-type]


def _converte(valor: object, prop: str = "posicao") -> object:
    """Unidade da AST → float do motor (Fase 10: por propriedade).

    Rotação: rad vira graus; deg/graus/número ficam em graus. Opacidade:
    % vira 0..1. Posição/tamanho/escala: pixels/número direto.
    """
    import math

    if isinstance(valor, tuple) and valor and isinstance(valor[0], tuple):
        return tuple(_numero(v) for v in valor)
    if isinstance(valor, tuple):
        unidade, numero = valor[0], float(valor[1])
        if prop == "rotacao" and unidade == "rad":
            return math.degrees(numero)
        if prop == "opacidade" and unidade == "%":
            return numero / 100.0
        return numero
    return _numero(valor)


def converter_valor_anim(valor: object, prop: str = "posicao") -> object:
    """Conversão pública AST→motor (reuso do Character Core, Fase 12)."""
    return _converte(valor, prop)


def definicao_de_ast(no) -> DefinicaoAnimacao:
    """Converte AnimacaoDef (AST) em DefinicaoAnimacao do motor."""
    return DefinicaoAnimacao(
        nome=no.nome, alvo=no.alvo,
        chaves=[ChaveAnimacao(c.propriedade,
                              _converte(c.de, c.propriedade)
                              if c.de is not None else None,
                              _converte(c.para, c.propriedade), c.linha)
                for c in no.chaves],
        duracao_ms=no.duracao_ms, atraso_ms=no.atraso_ms,
        movimento=no.movimento, repetir=no.repetir, depois=no.depois,
        inicio=no.inicio, ao_terminar=no.ao_terminar, linha=no.linha,
        modo=getattr(no, "modo", "normal"),
        relativo=bool(getattr(no, "relativo", False)),
        voltas=int(getattr(no, "voltas", 0) or 0),
        fisica=getattr(no, "fisica", None),
        rigidez=float(getattr(no, "rigidez", 180.0) or 180.0),
        amortecimento=float(getattr(no, "amortecimento", 12.0) or 12.0),
        massa=float(getattr(no, "massa", 1.0) or 1.0),
        keyframes=[Keyframe(
            tempo=k.percent / 100.0,
            valores={c.propriedade: _converte(c.para, c.propriedade)
                     for c in k.chaves},
            linha=k.linha) for k in getattr(no, "keyframes", [])],
        ao_comecar=getattr(no, "ao_comecar", None),
        ao_cancelar=getattr(no, "ao_cancelar", None),
    )


class MotorAnimacoes:
    """Executa definições de animação sobre a Cena."""

    def __init__(self, executor=None) -> None:
        self.executor = executor
        self.execucoes: dict[str, Execucao] = {}
        self._cena = None  # Fase 12: última cena carregada (gestos).

    # ----- carga -----

    def carregar(self, definicoes: list[DefinicaoAnimacao], cena) -> None:
        self._cena = cena
        for d in definicoes:
            no = cena.buscar(d.alvo)
            if no is None:
                raise ErroExecucao(
                    f'Animação "{d.nome}": alvo {d.alvo!r} não existe.',
                    linha=d.linha,
                    sugestao="Verifique o nome do componente na janela.",
                )
            self._validar_definicao(d)
            chaves = [ChaveAnimacao(c.propriedade, c.de, c.para, c.linha)
                      for c in d.chaves]
            # manual ou com depois: parada até iniciar() ou até a
            # antecessora concluir. Só automática sem depois já nasce ativa.
            if d.depois is not None or d.inicio == "manual":
                estado = "aguardando" if d.depois is not None else "manual"
            else:
                estado = "atraso"
            self.execucoes[d.nome] = Execucao(definicao=d, no=no,
                                              estado=estado,
                                              chaves=chaves)

    @staticmethod
    def _validar_definicao(d: DefinicaoAnimacao) -> None:
        """Defesa em profundidade (a semântica já valida a linguagem)."""
        from .motion import curva as _curva

        try:
            _curva(d.movimento)
        except ErroExecucao as exc:
            raise ErroExecucao(
                f'Animação "{d.nome}": {exc.mensagem}',
                linha=d.linha,
            )
        if d.modo not in MODOS_MOTION:
            raise ErroExecucao(
                f'Animação "{d.nome}": modo inválido: {d.modo!r}. '
                f'Válidos: {", ".join(MODOS_MOTION)}.',
                linha=d.linha,
            )
        if d.fisica is not None and d.fisica not in FISICAS_MOTION:
            raise ErroExecucao(
                f'Animação "{d.nome}": fisica inválida: {d.fisica!r}.',
                linha=d.linha,
            )
        for campo in ("rigidez", "amortecimento", "massa"):
            numero = float(getattr(d, campo))
            import math

            if not math.isfinite(numero) or numero <= 0:
                raise ErroExecucao(
                    f'Animação "{d.nome}": "{campo}" precisa de número '
                    "positivo.",
                    linha=d.linha,
                )

    # ----- controle -----

    def _obter(self, nome: str) -> Execucao:
        try:
            return self.execucoes[nome]
        except KeyError:
            raise ErroExecucao(
                f'Animação desconhecida: "{nome}". '
                f"Válidas: {', '.join(sorted(self.execucoes)) or 'nenhuma'}.",
            )

    def iniciar(self, nome: str) -> None:
        ex = self._obter(nome)
        ex.estado = "atraso"
        ex.tempo_ms = 0.0
        ex.rodada = 0
        # Fase 11: novo início = nova direção, callbacks e springs zerados.
        ex.direcao = 1
        ex.substituida = False
        ex._comecou = False
        ex._terminou = False
        ex._cancelou = False
        ex.springs = {}

    def pausar(self, nome: str) -> None:
        ex = self._obter(nome)
        if ex.estado in ("atraso", "rodando"):
            ex.estado = "pausada_" + ex.estado
            ex._retomar_para = ex.estado[len("pausada_"):]

    def continuar(self, nome: str) -> None:
        ex = self._obter(nome)
        if ex.estado.startswith("pausada_"):
            ex.estado = getattr(ex, "_retomar_para", "rodando")

    def cancelar(self, nome: str) -> None:
        ex = self._obter(nome)
        if ex.estado in ("concluida", "cancelada"):
            return
        ex.estado = "cancelada"
        self._disparar(ex, "ao_cancelar", "_cancelou")

    def iniciar_automaticas(self) -> None:
        for nome, ex in self.execucoes.items():
            d = ex.definicao
            if d.inicio == "automatico" and d.depois is None:
                self.iniciar(nome)

    # ----- tempo -----

    def atualizar(self, dt_ms: float) -> None:
        # Foto da lista: ganchos (F17) podem carregar novos motions
        # durante o tick sem invalidar a iteração.
        for ex in list(self.execucoes.values()):
            self._passo(ex, max(0.0, dt_ms))

    def _disparar(self, ex: Execucao, campo: str, flag: str) -> None:
        """Callback do executor uma única vez (ordem de definição)."""
        if getattr(ex, flag):
            return
        setattr(ex, flag, True)
        bloco = getattr(ex.definicao, campo)
        if bloco is None:
            return
        if callable(bloco):
            # Fase 17: gancho Python (ex. aplicar pose no início do
            # motion). Mesmo precedente do `para` chamável (Fase 11).
            bloco()
            return
        if self.executor is not None:
            self.executor.executar_bloco(bloco)

    def _props_ativas(self, ex: Execucao) -> set[str]:
        """Propriedades que esta execução escreve (chaves + keyframes)."""
        props = {c.propriedade for c in ex.chaves}
        for quadro in ex.definicao.keyframes:
            props.update(quadro.valores)
        return props

    def _resolver_conflito(self, ex: Execucao) -> None:
        """Regra explícita (Fase 11): novo substitui antigo.

        Ao INICIAR (não por rodada), Motions ativas no mesmo alvo e
        mesma propriedade são canceladas (com `quando cancelar`).
        Propriedades diferentes coexistem.
        """
        alvos = self._props_ativas(ex)
        if not alvos:
            return
        for outra in self.execucoes.values():
            if outra is ex or outra.no is not ex.no:
                continue
            if outra.estado != "rodando":
                continue
            if alvos & self._props_ativas(outra):
                outra.estado = "cancelada"
                outra.substituida = True
                self._disparar(outra, "ao_cancelar", "_cancelou")

    def _passo(self, ex: Execucao, dt: float) -> None:
        from .motion import curva as _curva

        d = ex.definicao
        if ex.estado == "aguardando":
            dep = self.execucoes.get(d.depois or "")
            if dep is not None and dep.estado == "concluida":
                ex.estado = "atraso"
                ex.tempo_ms = 0.0
            return
        if ex.estado in ("concluida", "cancelada", "manual") or ex.estado.startswith("pausada_"):
            return
        if ex.estado == "atraso":
            ex.tempo_ms += dt
            if ex.tempo_ms < d.atraso_ms:
                return
            ex.tempo_ms = 0.0
            ex.estado = "rodando"
            self._resolver_conflito(ex)
            self._capturar(ex)
            self._fixar_springs(ex)
            self._disparar(ex, "ao_comecar", "_comecou")
            if d.movimento == "aparecer":
                ex.no.visivel = True
        # rodando
        ex.tempo_ms += dt
        t = progresso_tempo(ex.tempo_ms, d.duracao_ms)
        ease = _curva(d.movimento)
        if d.keyframes:
            self._passo_keyframes(ex, t, ease)
        elif d.fisica == "mola":
            self._passo_spring(ex, dt)
        else:
            e = ease(t)
            if d.modo == "ping_pong" and ex.direcao < 0:
                e = 1.0 - e
            for chave in ex.chaves:
                _escrever_prop(ex.no, chave.propriedade,
                               _interpola(chave.de, chave.para, e,
                                          chave.propriedade, d.voltas))
        if t < 1.0:
            return
        # fim de uma rodada: snap exato no alvo da perna (sem drift).
        self._snap_fim_rodada(ex)
        total = d.repetir
        pernas = (float("inf") if total == "infinito"
                  else (int(total) if isinstance(total, int) else 1))
        if ex.rodada + 1 < pernas:
            ex.rodada += 1
            ex.tempo_ms = 0.0
            if d.modo == "ping_pong":
                ex.direcao *= -1
                self._fixar_springs(ex)
            elif d.fisica == "mola":
                self._fixar_springs(ex)
            return
        ex.estado = "concluida"
        if d.movimento == "desaparecer":
            ex.no.visivel = False
        self._disparar(ex, "ao_terminar", "_terminou")

    def _snap_fim_rodada(self, ex: Execucao) -> None:
        """Valor final exato da perna (ida=fim, volta=início; sem drift)."""
        from .motion import avaliar_keyframes as _ak

        d = ex.definicao
        if d.keyframes:
            quadros = sorted(d.keyframes, key=lambda k: k.tempo)
            alvo = 1.0 if ex.direcao > 0 else 0.0
            chaves_por_prop = {c.propriedade: c for c in ex.chaves}
            em_quadros: set[str] = set()
            for quadro in quadros:
                em_quadros.update(quadro.valores)
            for prop in self._props_ativas(ex):
                if prop in em_quadros:
                    _escrever_prop(ex.no, prop, _ak(
                        quadros, prop, alvo, lambda u: u))
                elif prop in chaves_por_prop:
                    # Fase 16: chave simples coexiste com keyframes.
                    chave = chaves_por_prop[prop]
                    destino = (chave.para if ex.direcao > 0 else chave.de)
                    if destino is None:
                        destino = chave.para
                    _escrever_prop(ex.no, prop, destino)
            return
        for chave in ex.chaves:
            destino = (chave.para if ex.direcao > 0 else chave.de)
            if destino is None:
                destino = chave.para
            _escrever_prop(ex.no, chave.propriedade, destino)

    def _passo_keyframes(self, ex: Execucao, t: float, ease) -> None:
        from .motion import avaliar_keyframes as _ak

        quadros = sorted(ex.definicao.keyframes, key=lambda k: k.tempo)
        tt = t if ex.direcao > 0 else 1.0 - t
        chaves_por_prop = {c.propriedade: c for c in ex.chaves}
        em_quadros: set[str] = set()
        for quadro in quadros:
            em_quadros.update(quadro.valores)
        for prop in self._props_ativas(ex):
            if prop in em_quadros:
                _escrever_prop(ex.no, prop, _ak(quadros, prop, tt, ease))
            elif prop in chaves_por_prop:
                # Fase 16: chave simples coexiste com keyframes (ex. girar
                # durante o pulo); interpola normal com a mesma curva.
                c = chaves_por_prop[prop]
                _escrever_prop(ex.no, prop, _interpola(
                    c.de, c.para, ease(t), prop, ex.definicao.voltas))

    def _passo_spring(self, ex: Execucao, dt: float) -> None:
        d = ex.definicao
        for idx, chave in enumerate(ex.chaves):
            alvo = (chave.para if ex.direcao > 0 else chave.de)
            if alvo is None:
                alvo = chave.para
            molas = ex.springs.get(idx)
            if molas is None:
                continue
            if isinstance(alvo, (tuple, list)):
                valores = tuple(m.passo(dt, a) for m, a in zip(molas, alvo))
            else:
                valores = molas.passo(dt, float(alvo))
            _escrever_prop(ex.no, chave.propriedade, valores)

    def _fixar_springs(self, ex: Execucao) -> None:
        """Springs nascem do estado atual (determinístico, sem salto)."""
        d = ex.definicao
        if d.fisica != "mola":
            ex.springs = {}
            return
        ex.springs = {}
        for idx, chave in enumerate(ex.chaves):
            atual = _ler_prop(ex.no, chave.propriedade)
            if isinstance(atual, (tuple, list)):
                molas = []
                for comp in atual:
                    mola = Spring(d.rigidez, d.amortecimento, d.massa)
                    mola.fixar(float(comp))
                    molas.append(mola)
                ex.springs[idx] = molas
            else:
                mola = Spring(d.rigidez, d.amortecimento, d.massa)
                mola.fixar(float(atual))
                ex.springs[idx] = mola

    def _capturar(self, ex: Execucao) -> None:
        for chave in ex.chaves:
            especificado = chave.de  # None ou valor do `de` escrito
            if chave.de is None:
                chave.de = _ler_prop(ex.no, chave.propriedade)
            if callable(chave.para):
                # Fase 11: alvo dinâmico avaliado no início do Motion.
                chave.para = chave.para()
            if ex.definicao.relativo:
                # Fase 11: `para` é deslocamento: destino = atual +
                # (para − de_escrito). Sem `de`, o deslocamento é o
                # próprio valor (ex. escala: 2 soma 2).
                atual = _ler_prop(ex.no, chave.propriedade)
                base = (especificado if especificado is not None
                        else _zero_como(chave.para))
                delta = _sub(chave.para, base)
                chave.de = atual
                chave.para = _soma(atual, delta)
