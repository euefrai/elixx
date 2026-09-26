"""2D Character Deformation da ELiXX (Fase 24) — rig vira living puppet.

A F23 responde quais são as partes e como se conectam; a F24 responde
como elas se deformam e se comportam como um único personagem:

    CharacterRig (F23) ──→ CharacterDeformationRig (adaptação)
        ──→ Character (F12, sem segundo puppet)
        ──→ Motion Core (F11, sem segundo motor)
        ──→ Transform (F10, sem segunda matemática) ──→ Renderer

"F24 adiciona comportamento visual ao rig, não inteligência
artificial." Tudo aqui é definição estruturada + Transform: escala,
squash/stretch, rotação, deslocamento, inclinação. Curvatura (bend)
e malha (mesh) existem como representação honesta com fallback para
transformações simples — nunca se finge deformação real inexistente.

"Deformação não significa reconstrução de pixels ausentes."

Sem drift: toda deformação temporária parte da BasePose (referência
estável) e pode voltar a ela. Sem threads por personagem, sem random,
sem IA, sem rede.
"""
from __future__ import annotations

import json
import math

from ..erros import ErroELiXX
from .mundo import Bounds2D
from .transform import Vector2

__all__ = [
    "TIPOS_DEFORMACAO",
    "EXPRESSOES_BASE",
    "BOCAS",
    "OLHARES",
    "MAX_ANCHORS",
    "MAX_VALOR_DEF",
    "Anchor",
    "Influence",
    "Vertex2D",
    "Mesh2D",
    "Deformacao",
    "BasePose",
    "ExpressionStack",
    "CharacterDeformationRig",
    "deformation_rig_de_rig",
    "aplicar_deformacao",
    "deformacao_para_pose",
    "deformacao_para_motions",
    "compor_camadas",
    "comportamento",
    "respirar",
    "piscar",
    "olhar_para",
    "boca_estado",
    "renderer_fallback",
    "debug_deformacao",
]

TIPOS_DEFORMACAO = ("rigid", "scale", "squash", "stretch", "bend",
                    "offset", "rotate", "tilt")
"""Tipos estruturados. bend/mesh avançado: representação + fallback."""

EXPRESSOES_BASE = ("sorriso", "tristeza", "surpresa",
                   "olhos_fechados", "olhos_abertos", "lingua_fora",
                   "bravo", "neutro")
"""Expressões base (combináveis em camadas; sem imagem por combinação)."""

BOCAS = ("neutra", "sorriso", "aberta", "fechada", "surpresa")
"""Estados visuais da boca (estrutura; sem lip sync, sem áudio)."""

OLHARES = ("esquerda", "direita", "cima", "baixo", "centro")
"""Direções do olhar (offsets/rotação simples; sem tracking real)."""

MAX_ANCHORS = 10000
"""Teto anti-gigante de anchors/influências por rig."""

MAX_VALOR_DEF = 1.0e9
"""Módulo máximo de coordenadas, intensidades e pesos derivados."""

_PROF_DADOS = 6
"""Aninhamento máximo de metadados (só JSON raso)."""


# ----- validação de dados (só dados; sem código) -----

def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'"{o_que}" precisa de número '
                        f"(recebido {type(valor).__name__}).")
    if not math.isfinite(numero):
        raise ErroELiXX(f'"{o_que}" precisa de número finito '
                        "(recebido NaN ou infinito).")
    if abs(numero) > MAX_VALOR_DEF:
        raise ErroELiXX(f'"{o_que}" gigante ({numero:g}).')
    return numero


def _e_dado(valor, profundidade: int = 0) -> bool:
    if profundidade > _PROF_DADOS:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, float) and not math.isfinite(valor):
            return False
        return True
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(i, profundidade + 1) for i in valor)
    if isinstance(valor, dict):
        return all(isinstance(c, str)
                   and _e_dado(i, profundidade + 1)
                   for c, i in valor.items())
    return False


def _id_valido(valor, o_que: str = "id") -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'"{o_que}" precisa de texto não vazio.')
    return valor.strip()


def _ordenado(valores) -> list:
    return sorted(valores)


def _peso(valor, dono: str) -> float:
    numero = _finito(valor, f"peso de {dono}")
    if not 0.0 <= numero <= 1.0:
        raise ErroELiXX(f'Peso de "{dono}" precisa de 0..1 '
                        f"(recebido {numero:g}).")
    return numero


# ----- Anchor -----

class Anchor:
    """Ponto de referência nomeado (ombro, olho, boca...). Só dados."""

    def __init__(self, anchor_id: str, posicao=None,
                 parte_id: str | None = None,
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(anchor_id, "id do anchor")
        if posicao is None:
            posicao = Vector2(0.0, 0.0)
        if isinstance(posicao, dict):
            posicao = Vector2(_finito(posicao.get("x", 0.0),
                                      f"x de {self.id}"),
                              _finito(posicao.get("y", 0.0),
                                      f"y de {self.id}"))
        if not isinstance(posicao, Vector2):
            raise ErroELiXX(f'Anchor "{self.id}": posição de Vector2.')
        _finito(posicao.x, f"x de {self.id}")
        _finito(posicao.y, f"y de {self.id}")
        self.posicao = Vector2(posicao.x, posicao.y)
        self.parte_id = (str(parte_id).strip() or None
                         if parte_id is not None else None)
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Anchor "{self.id}": metadata inválida.')
        self.metadata = meta

    def to_dict(self) -> dict:
        return {"id": self.id,
                "posicao": {"x": self.posicao.x, "y": self.posicao.y},
                "parte_id": self.parte_id,
                "metadata": dict(self.metadata)}

    @staticmethod
    def from_dict(dados: dict) -> Anchor:
        if not isinstance(dados, dict):
            raise ErroELiXX("Anchor precisa de dicionário.")
        return Anchor(dados.get("id", ""),
                      posicao=dados.get("posicao") or {},
                      parte_id=dados.get("parte_id"),
                      metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"Anchor({self.id} {self.posicao.tupla()})"


# ----- Influence -----

class Influence:
    """Influência de um joint sobre uma parte (peso 0..1). Só dados.

    Skinning real é futuro; aqui a estrutura permite evolução sem
    quebrar o contrato (pesos validados, soma NÃO imposta — documentado
    como escolha para misturas parciais honestas).
    """

    def __init__(self, parte_id: str, joint: str,
                 peso: float = 1.0) -> None:
        self.parte_id = _id_valido(parte_id, "parte da influência")
        self.joint = _id_valido(joint, "joint da influência")
        self.peso = _peso(peso, f"{self.parte_id}/{self.joint}")

    def to_dict(self) -> dict:
        return {"parte_id": self.parte_id, "joint": self.joint,
                "peso": self.peso}

    @staticmethod
    def from_dict(dados: dict) -> Influence:
        if not isinstance(dados, dict):
            raise ErroELiXX("Influência precisa de dicionário.")
        return Influence(dados.get("parte_id", ""),
                         dados.get("joint", ""),
                         peso=dados.get("peso", 1.0))

    def __repr__(self) -> str:
        return (f"Influence({self.parte_id}←{self.joint} "
                f"{self.peso:g})")


# ----- Mesh2D (abstração futura; sem triangulação/GPU/3D) -----

class Vertex2D:
    """Vértice 2D com peso (abstração; sem deformador nesta fase)."""

    def __init__(self, vert_id: str, posicao=None,
                 peso: float = 1.0) -> None:
        self.id = _id_valido(vert_id, "id do vértice")
        if posicao is None:
            posicao = Vector2(0.0, 0.0)
        if isinstance(posicao, dict):
            posicao = Vector2(_finito(posicao.get("x", 0.0), "x"),
                              _finito(posicao.get("y", 0.0), "y"))
        if not isinstance(posicao, Vector2):
            raise ErroELiXX(f'Vértice "{self.id}": Vector2.')
        _finito(posicao.x, f"x de {self.id}")
        _finito(posicao.y, f"y de {self.id}")
        self.posicao = Vector2(posicao.x, posicao.y)
        self.peso = _peso(peso, self.id)

    def to_dict(self) -> dict:
        return {"id": self.id,
                "posicao": {"x": self.posicao.x, "y": self.posicao.y},
                "peso": self.peso}

    @staticmethod
    def from_dict(dados: dict) -> Vertex2D:
        if not isinstance(dados, dict):
            raise ErroELiXX("Vértice precisa de dicionário.")
        return Vertex2D(dados.get("id", ""),
                        posicao=dados.get("posicao") or {},
                        peso=dados.get("peso", 1.0))

    def __repr__(self) -> str:
        return f"Vertex2D({self.id})"


class Mesh2D:
    """Malha 2D nominal (vértices + parte dona; sem solver)."""

    def __init__(self, mesh_id: str, parte_id: str,
                 vertices: list | None = None) -> None:
        self.id = _id_valido(mesh_id, "id da malha")
        self.parte_id = _id_valido(parte_id, "parte da malha")
        verts = []
        for v in (vertices or []):
            verts.append(v if isinstance(v, Vertex2D)
                         else Vertex2D.from_dict(v))
        vistos = set()
        for v in verts:
            if v.id in vistos:
                raise ErroELiXX(f'Malha "{self.id}": vértice "{v.id}" '
                                "duplicado.")
            vistos.add(v.id)
        self.vertices = verts

    def to_dict(self) -> dict:
        return {"id": self.id, "parte_id": self.parte_id,
                "vertices": [v.to_dict() for v in self.vertices]}

    @staticmethod
    def from_dict(dados: dict) -> Mesh2D:
        if not isinstance(dados, dict):
            raise ErroELiXX("Malha precisa de dicionário.")
        return Mesh2D(dados.get("id", ""), dados.get("parte_id", ""),
                      vertices=dados.get("vertices") or [])

    def __repr__(self) -> str:
        return f"Mesh2D({self.id}: {len(self.vertices)} vértices)"


# ----- Deformacao -----

class Deformacao:
    """Deformação estruturada sobre uma parte (nunca executa código)."""

    def __init__(self, alvo: str, tipo: str = "scale",
                 intensidade: float = 0.0,
                 parametros: dict | None = None,
                 origem: str = "manual") -> None:
        self.alvo = _id_valido(alvo, "alvo da deformação")
        tipo_txt = str(tipo).strip() or "scale"
        if tipo_txt not in TIPOS_DEFORMACAO:
            raise ErroELiXX(f'Tipo "{tipo_txt}" inválido '
                            f'({", ".join(TIPOS_DEFORMACAO)}).')
        self.tipo = tipo_txt
        self.intensidade = _finito(intensidade, "intensidade")
        params = dict(parametros or {})
        if not _e_dado(params):
            raise ErroELiXX(f'Deformação em "{self.alvo}": parâmetros '
                            "inválidos (só JSON finito).")
        self.parametros = params
        self.origem = str(origem).strip() or "manual"

    def to_dict(self) -> dict:
        return {"alvo": self.alvo, "tipo": self.tipo,
                "intensidade": self.intensidade,
                "parametros": dict(self.parametros),
                "origem": self.origem}

    @staticmethod
    def from_dict(dados: dict) -> Deformacao:
        if not isinstance(dados, dict):
            raise ErroELiXX("Deformação precisa de dicionário.")
        return Deformacao(
            dados.get("alvo", ""), tipo=dados.get("tipo", "scale"),
            intensidade=dados.get("intensidade", 0.0),
            parametros=dict(dados.get("parametros") or {}),
            origem=dados.get("origem", "manual"))

    def __repr__(self) -> str:
        return (f"Deformacao({self.tipo} {self.alvo} "
                f"{self.intensidade:g})")


# ----- BasePose (referência estável anti-drift) -----

class BasePose:
    """Estado original do personagem (leitura atual, sem motor próprio).

    Captura {parte → props F12} e restaura via `aplicar_pose` (público
    do F12). Deformações temporárias sempre calculam a partir daqui:
    1.0 → 0.9 → restaurar → 1.0 (nunca 0.81).
    """

    PROPS = ("posicao", "rotacao", "escala", "opacidade")

    def __init__(self, valores: dict | None = None) -> None:
        vals = dict(valores or {})
        for parte, props in vals.items():
            if not isinstance(props, dict) or not _e_dado(props):
                raise ErroELiXX(f'BasePose: props de "{parte}" '
                                "inválidas.")
        self.valores = {str(p): dict(v) for p, v in vals.items()}

    @staticmethod
    def capturar(personagem) -> BasePose:
        """Lê o estado atual das partes (x/y, rotação, escala, opac)."""
        vals = {}
        for nome in sorted(personagem.partes):
            no = personagem.partes[nome].no
            vals[nome] = {
                "posicao": [float(no.x), float(no.y)],
                "rotacao": float(no.rotacao),
                "escala": [float(getattr(no, "escala_x", 1.0)),
                           float(getattr(no, "escala_y", 1.0))],
                "opacidade": float(no.opacidade)}
        return BasePose(vals)

    def restaurar(self, personagem) -> list[str]:
        """Volta ao capturado (retorna partes tocadas)."""
        from .personagem import Pose

        return personagem.aplicar_pose(
            Pose("base_pose",
                 entradas={p: dict(v)
                           for p, v in self.valores.items()}))

    def valor(self, parte: str, prop: str):
        try:
            return self.valores[str(parte)][prop]
        except KeyError:
            raise ErroELiXX(f'BasePose sem "{prop}" de "{parte}".')

    def to_dict(self) -> dict:
        return {"valores": {p: dict(v)
                            for p, v in self.valores.items()}}

    @staticmethod
    def from_dict(dados: dict) -> BasePose:
        if not isinstance(dados, dict):
            raise ErroELiXX("BasePose precisa de dicionário.")
        return BasePose(dict(dados.get("valores") or {}))

    def __repr__(self) -> str:
        return f"BasePose({len(self.valores)} partes)"


# ----- deformação → props F12 (a partir da base; sem drift) -----

def deformacao_para_pose(deformacao: Deformacao, base: BasePose,
                         nome: str = ""):
    """Deformação + BasePose → Pose F12 (props calculadas da base).

    squash k: escala (1+k, 1-k) — mais largo e baixo.
    stretch k: escala (1-k, 1+k) — mais alto e fino.
    scale k: uniforme (1+k). rotate: rotação base+k graus.
    offset: posição base + (dx, dy) de parâmetros.
    tilt: rotação base + k (inclinação honesta via Transform).
    rigid: identidade declarada (sem mudança; documenta intenção).
    bend: representação + fallback rotate (aviso honesto em metadata
    da Pose? não — Pose F12 não carrega avisos; o chamador consulta
    `renderer_fallback`).
    """
    from .personagem import Pose

    if not isinstance(deformacao, Deformacao):
        raise ErroELiXX("deformacao_para_pose espera Deformacao.")
    if not isinstance(base, BasePose):
        raise ErroELiXX("deformacao_para_pose espera BasePose.")
    alvo = deformacao.alvo
    if alvo not in base.valores:
        raise ErroELiXX(f'Deformação: alvo "{alvo}" ausente na base.')
    k = deformacao.intensidade
    atual = base.valores[alvo]
    if deformacao.tipo == "squash":
        props = {"escala": [atual["escala"][0] * (1.0 + k),
                            atual["escala"][1] * (1.0 - k)]}
    elif deformacao.tipo == "stretch":
        props = {"escala": [atual["escala"][0] * (1.0 - k),
                            atual["escala"][1] * (1.0 + k)]}
    elif deformacao.tipo == "scale":
        props = {"escala": [atual["escala"][0] * (1.0 + k),
                            atual["escala"][1] * (1.0 + k)]}
    elif deformacao.tipo in ("rotate", "tilt", "bend"):
        props = {"rotacao": float(atual["rotacao"]) + k}
    elif deformacao.tipo == "offset":
        dx = float(deformacao.parametros.get("dx", 0.0))
        dy = float(deformacao.parametros.get("dy", 0.0))
        props = {"posicao": [atual["posicao"][0] + dx,
                             atual["posicao"][1] + dy]}
    elif deformacao.tipo == "rigid":
        props = {"posicao": list(atual["posicao"]),
                 "rotacao": float(atual["rotacao"]),
                 "escala": list(atual["escala"])}
    else:  # pragma: no cover (tipos fechados acima)
        raise ErroELiXX(f'Tipo "{deformacao.tipo}" sem regra.')
    return Pose(nome or f"{deformacao.tipo}_{alvo}",
                entradas={alvo: props})


def aplicar_deformacao(personagem, deformacao: Deformacao,
                       base: BasePose | None = None) -> list[str]:
    """Aplica agora via F12 (retorna partes tocadas)."""
    if base is None:
        base = BasePose.capturar(personagem)
    pose = deformacao_para_pose(deformacao, base)
    return personagem.aplicar_pose(pose)


def deformacao_para_motions(personagem, deformacao: Deformacao,
                            base: BasePose | None = None,
                            duracao_ms: float = 500.0,
                            movimento: str = "suave") -> list:
    """Deformação → DefinicaoAnimacao F11 (transicionar_pose).

    Ida (base → deformado). Volta = `base.restaurar` ou transição à
    pose base. Sem scheduler próprio.
    """
    if base is None:
        base = BasePose.capturar(personagem)
    pose = deformacao_para_pose(deformacao, base)
    return personagem.transicionar_pose(pose, duracao_ms=float(
        duracao_ms), movimento=movimento)


# ----- composição de camadas (prioridade documentada) -----

def compor_camadas(camadas: list):
    """[Pose...] ordem crescente de prioridade → Pose fundida.

    Política: manual > pose > expressão > automático. Quem chama ordena
    (automáticas primeiro, manual por último); última vence por
    (parte, prop) — mesma regra de `Pose.combinar` (F12).
    """
    from .personagem import Pose

    fundida: dict = {}
    nomes = []
    for camada in camadas:
        if not isinstance(camada, Pose):
            raise ErroELiXX("compor_camadas espera lista de Pose.")
        nomes.append(camada.nome)
        for parte, props in camada.entradas.items():
            fundida.setdefault(str(parte), {}).update(
                {str(k): v for k, v in dict(props).items()})
    return Pose("+".join(nomes) if nomes else "vazia",
                entradas=fundida)


class ExpressionStack:
    """Pilha de expressões: base + olhos + boca + ... (determinística)."""

    def __init__(self, expressoes: list | None = None) -> None:
        self.pilha: list[str] = []
        for e in (expressoes or []):
            self.push(e)

    def push(self, nome: str) -> list[str]:
        nome_txt = _id_valido(nome, "nome da expressão")
        if nome_txt not in self.pilha:
            self.pilha.append(nome_txt)
        return list(self.pilha)

    def pop(self, nome: str | None = None) -> list[str]:
        if not self.pilha:
            raise ErroELiXX("Pilha de expressões vazia.")
        if nome is None:
            self.pilha.pop()
        else:
            try:
                self.pilha.remove(str(nome))
            except ValueError:
                raise ErroELiXX(f'Expressão "{nome}" fora da pilha.')
        return list(self.pilha)

    def resolver(self, disponiveis: dict):
        """Nomes → Pose fundida (ordem da pilha = prioridade)."""
        from .personagem import Pose

        camadas = []
        for nome in self.pilha:
            try:
                pose = disponiveis[nome]
            except KeyError:
                raise ErroELiXX(f'Expressão "{nome}" indisponível '
                                "(declare no rig/personagem).")
            if isinstance(pose, dict):
                pose = Pose(nome, entradas=dict(pose))
            if not isinstance(pose, Pose):
                raise ErroELiXX("Expressões resolvem para Pose.")
            camadas.append(pose)
        return compor_camadas(camadas)

    def to_dict(self) -> dict:
        return {"pilha": list(self.pilha)}

    def __repr__(self) -> str:
        return f"ExpressionStack({self.pilha})"


# ----- comportamentos vivos (definição; F11 executa) -----

def _passos(personagem, nome: str, alvos: list) -> list:
    """Filtra passos para partes existentes (ausente = pulado)."""
    from .personagem import Pose

    saidas = []
    for i, (parte, props) in enumerate(alvos):
        if parte not in personagem.partes:
            continue
        saidas.append(Pose(f"{nome}_{i:02d}",
                           entradas={parte: dict(props)}))
    return saidas


def respirar(personagem, intensidade: float = 0.03) -> list:
    """Tronco/peito expande e volta (determinístico, sem threads)."""
    k = _finito(intensidade, "intensidade do respirar")
    for alvo in ("tronco", "peito", "corpo"):
        if alvo in personagem.partes:
            return _passos(personagem, "respirar", [
                (alvo, {"escala": [1.0, 1.0 + k]}),
                (alvo, {"escala": [1.0, 1.0]}),
            ])
    return []


def piscar(personagem) -> list:
    """Olhos fecham e abrem (coexiste com expressão/olhar/fala)."""
    alvos = [p for p in ("olhos", "olho_esquerdo", "olho_direito")
             if p in personagem.partes]
    if not alvos:
        return []
    passos = []
    for i, alvo in enumerate(alvos):
        passos.append((alvo, {"opacidade": 0.0}))
    for i, alvo in enumerate(alvos):
        passos.append((alvo, {"opacidade": 1.0}))
    return _passos(personagem, "piscar", passos)


def olhar_para(personagem, direcao: str,
               intensidade: float = 6.0) -> list:
    """Olhar simples: offset dos olhos + rotação leve da cabeça."""
    d = str(direcao).strip().lower()
    if d not in OLHARES:
        raise ErroELiXX(f'Olhar "{direcao}" inválido '
                        f'({", ".join(OLHARES)}).')
    k = _finito(intensidade, "intensidade do olhar")
    mapa = {"esquerda": (-k, 0.0), "direita": (k, 0.0),
            "cima": (0.0, -k), "baixo": (0.0, k), "centro": (0.0, 0.0)}
    dx, dy = mapa[d]
    # offsets a partir do estado atual (ida; volta via BasePose)
    passos = []
    for parte in ("olhos", "olho_esquerdo", "olho_direito"):
        if parte in personagem.partes:
            no = personagem.partes[parte].no
            passos.append((parte, {"posicao": [float(no.x) + dx,
                                               float(no.y) + dy]}))
    if "cabeca" in personagem.partes:
        no = personagem.partes["cabeca"].no
        rot = {"esquerda": -4.0, "direita": 4.0, "cima": -3.0,
               "baixo": 3.0, "centro": 0.0}[d]
        passos.append(("cabeca", {"rotacao": float(no.rotacao)
                                  + rot}))
    return _passos(personagem, "olhar", passos)


def boca_estado(personagem, estado: str) -> list:
    """Estado visual da boca (sem lip sync, sem áudio)."""
    e = str(estado).strip().lower()
    if e not in BOCAS:
        raise ErroELiXX(f'Boca "{estado}" inválida '
                        f'({", ".join(BOCAS)}).')
    if "boca" not in personagem.partes:
        return []
    mapa = {"neutra": {"escala": [1.0, 1.0]},
            "sorriso": {"escala": [1.3, 0.8]},
            "aberta": {"escala": [1.0, 1.6]},
            "fechada": {"escala": [1.0, 0.3]},
            "surpresa": {"escala": [0.8, 1.4]}}
    return _passos(personagem, f"boca_{e}", [("boca", mapa[e])])


def comportamento(personagem, nome: str, **kwargs) -> list:
    """Despacho de comportamentos vivos (só definição estruturada)."""
    chave = str(nome).strip().lower()
    if chave == "respirar":
        return respirar(personagem,
                        intensidade=float(kwargs.get("intensidade",
                                                     0.03)))
    if chave == "piscar":
        return piscar(personagem)
    if chave in ("olhar", "olhar_para"):
        return olhar_para(personagem,
                          kwargs.get("direcao", "centro"),
                          intensidade=float(kwargs.get("intensidade",
                                                       6.0)))
    if chave in ("boca", "boca_estado"):
        return boca_estado(personagem, kwargs.get("estado",
                                                  "neutra"))
    raise ErroELiXX(f'Comportamento "{nome}" desconhecido '
                    "(respirar, piscar, olhar, boca).")


# ----- renderer fallback (honesto) -----

def renderer_fallback(deformacao: Deformacao) -> dict:
    """Diz se o renderer padrão representa o tipo só com Transform.

    posicao/rotacao/escala/opacidade: sim. bend/mesh: não — retorna
    estado estruturado + warning (nunca finge renderização).
    """
    if not isinstance(deformacao, Deformacao):
        raise ErroELiXX("renderer_fallback espera Deformacao.")
    if deformacao.tipo in ("rigid", "scale", "squash", "stretch",
                           "rotate", "offset", "tilt"):
        return {"representavel": True, "codigo": "transform",
                "motivo": f'"{deformacao.tipo}" via posição, rotação, '
                          "escala e opacidade.",
                "props": ["posicao", "rotacao", "escala",
                          "opacidade"]}
    return {"representavel": False, "codigo": "fallback_estruturado",
            "motivo": f'"{deformacao.tipo}" sem deformador real; '
                      "estado estruturado preservado, renderer usa "
                      "fallback de Transform.",
            "props": ["posicao", "rotacao", "escala", "opacidade"]}


# ----- CharacterDeformationRig (adaptação; delega ao Character) -----

class CharacterDeformationRig:
    """Rig + personagem + base + anchors (wrapper, sem 2º Character)."""

    def __init__(self, rig, personagem, base: BasePose | None = None,
                 anchors: list | None = None,
                 influences: list | None = None,
                 meshes: list | None = None) -> None:
        from .personagem import Character
        from .rigging import CharacterRig

        if not isinstance(rig, CharacterRig):
            raise ErroELiXX("deformation rig espera CharacterRig.")
        if not isinstance(personagem, Character):
            raise ErroELiXX("deformation rig espera Character (F12).")
        self.rig = rig
        self.personagem = personagem
        self.base = base if base is not None else BasePose.capturar(
            personagem)
        self.anchors: dict[str, Anchor] = {}
        for a in (anchors or []):
            anc = a if isinstance(a, Anchor) else Anchor.from_dict(a)
            if anc.id in self.anchors:
                raise ErroELiXX(f'Anchor "{anc.id}" duplicado.')
            if (anc.parte_id is not None
                    and anc.parte_id not in personagem.partes):
                raise ErroELiXX(f'Anchor "{anc.id}": parte '
                                f'"{anc.parte_id}" ausente.')
            if len(self.anchors) >= MAX_ANCHORS:
                raise ErroELiXX("Anchors além do teto.")
            self.anchors[anc.id] = anc
        self.influences: list[Influence] = []
        for i in (influences or []):
            inf = i if isinstance(i, Influence) else Influence.from_dict(
                i)
            if inf.parte_id not in personagem.partes:
                raise ErroELiXX(f'Influência: parte "{inf.parte_id}" '
                                "ausente.")
            self.influences.append(inf)
        self.meshes: dict[str, Mesh2D] = {}
        for m in (meshes or []):
            mesh = m if isinstance(m, Mesh2D) else Mesh2D.from_dict(m)
            if mesh.parte_id not in personagem.partes:
                raise ErroELiXX(f'Malha "{mesh.id}": parte ausente.')
            self.meshes[mesh.id] = mesh
        self.ativas: list[Deformacao] = []

    def __getattr__(self, nome: str):
        """Delega tudo do Character (sem duplicar API)."""
        if nome in ("rig", "personagem", "base", "anchors",
                    "influences", "meshes", "ativas"):
            raise AttributeError(nome)
        return getattr(object.__getattribute__(self, "personagem"),
                       nome)

    def aplicar(self, deformacao: Deformacao) -> list[str]:
        """Aplica da base (sem drift) e registra como ativa."""
        tocadas = aplicar_deformacao(self.personagem, deformacao,
                                     self.base)
        self.ativas = [d for d in self.ativas
                       if d.alvo != deformacao.alvo
                       or d.tipo != deformacao.tipo] + [deformacao]
        return tocadas

    def restaurar(self) -> list[str]:
        """Volta à base e limpa ativas."""
        tocadas = self.base.restaurar(self.personagem)
        self.ativas = []
        return tocadas

    def animar(self, deformacao: Deformacao,
               duracao_ms: float = 500.0,
               movimento: str = "suave") -> list:
        """Deformação → motions F11 (ida; volta via restaurar)."""
        return deformacao_para_motions(self.personagem, deformacao,
                                       self.base, duracao_ms,
                                       movimento)

    def influencias_de(self, parte_id: str) -> list[Influence]:
        return [i for i in self.influences
                if i.parte_id == str(parte_id)]

    def to_dict(self) -> dict:
        dados = {"rig": self.rig.id, "personagem": self.personagem.nome,
                 "base": self.base.to_dict(),
                 "anchors": [self.anchors[k].to_dict()
                             for k in _ordenado(self.anchors)],
                 "influences": [i.to_dict() for i in self.influences],
                 "meshes": [self.meshes[k].to_dict()
                            for k in _ordenado(self.meshes)],
                 "ativas": [d.to_dict() for d in self.ativas]}
        if not _e_dado(dados):
            raise ErroELiXX("Deformation rig não serializável.")
        return dados

    def __repr__(self) -> str:
        return (f"CharacterDeformationRig({self.personagem.nome}: "
                f"{len(self.anchors)} anchors, {len(self.ativas)} "
                "ativas)")


def deformation_rig_de_rig(rig, personagem,
                           base: BasePose | None = None,
                           anchors: list | None = None,
                           influences: list | None = None,
                           meshes: list | None = None
                           ) -> CharacterDeformationRig:
    """F23 Rig + F12 Character → deformation rig (adaptação)."""
    return CharacterDeformationRig(rig, personagem, base, anchors,
                                   influences, meshes)


# ----- debug -----

def debug_deformacao(alvo) -> str:
    """Texto legível: deformações, anchors, base, ativas."""
    if isinstance(alvo, Deformacao):
        return (f"Deformacao {alvo.tipo} em {alvo.alvo} "
                f"k={alvo.intensidade:g} origem={alvo.origem} "
                f"params={alvo.parametros}")
    if isinstance(alvo, BasePose):
        linhas = [f"BasePose: {len(alvo.valores)} partes"]
        for parte in _ordenado(alvo.valores):
            v = alvo.valores[parte]
            linhas.append(
                f"  {parte}: pos={v['posicao']} rot={v['rotacao']} "
                f"esc={v['escala']} opa={v['opacidade']}")
        return "\n".join(linhas)
    rig = alvo
    linhas = [f"CharacterDeformationRig {rig.personagem.nome}: "
               f"{len(rig.anchors)} anchors, "
               f"{len(rig.influences)} influências, "
               f"{len(rig.meshes)} malhas, {len(rig.ativas)} ativas"]
    for aid in _ordenado(rig.anchors):
        a = rig.anchors[aid]
        linhas.append(f"  anchor {aid}: parte={a.parte_id} "
                       f"pos={a.posicao.tupla()}")
    for d in rig.ativas:
        linhas.append(f"  ativa: {d.tipo} {d.alvo} k={d.intensidade:g}")
    return "\n".join(linhas)
