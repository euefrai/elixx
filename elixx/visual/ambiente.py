"""Environment Bridge da ELiXX (Fase 19) — ambiente estruturado + runtime.

Camada de adaptação/entrada para estruturas externas (páginas, apps,
janelas, painéis, botões...), SEM visão computacional, SEM screenshots,
SEM LLM e SEM executar código do ambiente:

    Fonte externa → Environment Adapter → Environment
        → Environment → World Bridge → World (F13)
        → Navigation (F15, sem pathfinding novo)
        → AIContextBuilder → AIProvider.gerar_intencao (F18)

    Interaction (declarativa) → InteractionExecutor (mock seguro)

Segurança: strings externas são só dados. Nenhuma avaliação ou
execução dinâmica, nenhuma importação programática, nenhum processo
externo. Geometria reutiliza Vector2 (F10) e Bounds2D (F13); nunca
duplica matemática. Capabilities reutiliza F14 (sem duplicar registry).
Navegação reutiliza F15 (sem novo pathfinding).

Determinismo: mesma entrada → mesma representação, mesmas regiões,
superfícies, boundaries, World, contexto e ordem (listas ordenadas por
id; sem random, sem relógio para decisões, sem threads, sem estado
global implícito).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from ..erros import ErroELiXX
from .mundo import Bounds2D
from .transform import Vector2

__all__ = [
    "TIPOS_ENVIRONMENT",
    "TIPOS_NODE",
    "TIPOS_NODE_CONHECIDOS",
    "TIPOS_SUPERFICIE",
    "LADOS_BOUNDARY",
    "TIPOS_INTERACAO",
    "MAX_NOS",
    "MAX_PROFUNDIDADE",
    "Environment",
    "EnvironmentNode",
    "EnvironmentRegion",
    "EnvironmentSurface",
    "EnvironmentBoundary",
    "InteractionDescriptor",
    "AIContextBuilder",
    "InteractionExecutor",
    "ambiente_de_dict",
    "inferir_interacoes",
    "gerar_boundaries",
    "gerar_surface",
    "vincular_ambiente",
    "construir_grafo_de_ambiente",
    "debug_ambiente",
]

TIPOS_ENVIRONMENT = ("web", "aplicativo", "desktop", "elixx", "generico")
"""Tipos fechados de ambiente (nada executável)."""

TIPOS_NODE = ("janela", "regiao", "painel", "caixa", "botao", "entrada",
              "selecao", "lista", "item", "imagem", "texto", "menu",
              "barra", "tabela", "desconhecido")
"""Tipos estruturais conhecidos (novos só como dados, nunca código)."""

TIPOS_NODE_CONHECIDOS = TIPOS_NODE

TIPOS_SUPERFICIE = ("horizontal", "vertical", "area", "desconhecida")
"""Tipos de superfície (NÃO implica caminhável; ver capacidades)."""

LADOS_BOUNDARY = ("topo", "base", "esquerda", "direita", "interna",
                  "externa")
"""Lados de borda/limite."""

TIPOS_INTERACAO = ("clicar", "focar", "escrever", "selecionar", "limpar",
                   "abrir", "navegar", "fechar", "minimizar", "maximizar")
"""Interações declarativas conhecidas (extensível só como dado)."""

NOS_CONTENTORES = ("janela", "regiao", "painel", "menu", "barra",
                   "tabela", "lista")
"""Tipos que viram área no World (preservam hierarquia/contenção)."""

MAX_NOS = 20000
"""Teto anti-gigante (5000 nós passam; acima disso: erro claro)."""

MAX_PROFUNDIDADE = 32
"""Teto anti-recursão perigosa (pai/filho e região)."""

_PROF_DADOS = 6
"""Aninhamento máximo de atributos/metadados (dados limitados)."""


# ----- utilidades de dados (só dados; sem código) -----

def _finito_num(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'"{o_que}" precisa de número '
                        f"(recebido {type(valor).__name__}).")
    if not math.isfinite(numero):
        raise ErroELiXX(f'"{o_que}" precisa de número finito '
                        "(recebido NaN ou infinito).")
    return numero


def _e_dado(valor, profundidade: int = 0) -> bool:
    """Apenas JSON puro e finito (sem tupla, sem objeto, sem código)."""
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
    """IDs/nomes são strings opacas (maliciosos seguem inertes)."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'"{o_que}" precisa de texto não vazio.')
    return valor.strip()


def _ordenado(valores) -> list:
    return sorted(valores)


# ----- EnvironmentNode -----

class EnvironmentNode:
    """Elemento estrutural (janela, botão, painel...). Só dados."""

    def __init__(self, node_id: str, nome: str = "", tipo: str = "desconhecido",
                 x: float = 0.0, y: float = 0.0,
                 largura: float = 0.0, altura: float = 0.0,
                 visivel: bool = True, habilitado: bool = True,
                 interativo: bool = False, texto: str | None = None,
                 role: str | None = None, atributos: dict | None = None,
                 parent=None) -> None:
        self.id = _id_valido(node_id)
        self.nome = str(nome) if nome is not None else ""
        # Tipos novos: aceitos como dados; desconhecidos seguem inertes.
        bruto = str(tipo).strip() if tipo is not None else "desconhecido"
        self.tipo = bruto or "desconhecido"
        self.tipo_conhecido = self.tipo in TIPOS_NODE
        self.x = _finito_num(x, f"x do nó {self.id}")
        self.y = _finito_num(y, f"y do nó {self.id}")
        self.largura = _finito_num(largura, f"largura do nó {self.id}")
        self.altura = _finito_num(altura, f"altura do nó {self.id}")
        if self.largura < 0 or self.altura < 0:
            raise ErroELiXX(f'Nó "{self.id}": tamanho negativo '
                            f"({self.largura:g}x{self.altura:g}). Use ≥ 0.")
        self.visivel = bool(visivel)
        self.habilitado = bool(habilitado)
        self.interativo = bool(interativo)
        self.texto = (str(texto) if texto is not None else None)
        self.role = (str(role) if role is not None else None)
        attrs = dict(atributos or {})
        if not _e_dado(attrs):
            raise ErroELiXX(f'Nó "{self.id}": atributos inválidos '
                            "(só JSON finito).")
        self.atributos = attrs
        self.parent: EnvironmentNode | None = None
        self.children: list[EnvironmentNode] = []
        if parent is not None:
            parent.adicionar_filho(self)

    # ----- geometria (deriva de x/y/largura/altura; sem duplicar mate.) -----

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.largura

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.altura

    def center(self) -> Vector2:
        return Vector2(self.x + self.largura / 2.0,
                       self.y + self.altura / 2.0)

    def bounds(self) -> Bounds2D:
        return Bounds2D(self.x, self.y, self.largura, self.altura)

    def tem_geometria(self) -> bool:
        return self.largura > 0 and self.altura > 0

    # ----- árvore -----

    def adicionar_filho(self, filho: EnvironmentNode) -> EnvironmentNode:
        if filho is self:
            raise ErroELiXX(f'Nó "{self.id}": ciclo (filho de si mesmo).')
        ancestral = self
        while ancestral is not None:
            if ancestral is filho:
                raise ErroELiXX(f'Ciclo na árvore: "{filho.id}" é ancestral '
                                f'de "{self.id}".')
            ancestral = ancestral.parent
        if filho.parent is not None:
            filho.parent.children = [c for c in filho.parent.children
                                     if c is not filho]
        filho.parent = self
        if filho not in self.children:
            self.children.append(filho)
        if self._profundidade() > MAX_PROFUNDIDADE:
            raise ErroELiXX(f'Nó "{filho.id}": profundidade além de '
                            f"{MAX_PROFUNDIDADE} (recursão perigosa).")
        return filho

    def _profundidade(self) -> int:
        nivel, atual = 0, self
        while atual.parent is not None:
            nivel += 1
            atual = atual.parent
            if nivel > MAX_PROFUNDIDADE + 4:
                break
        return nivel

    def descendentes(self) -> list[EnvironmentNode]:
        saida: list[EnvironmentNode] = []
        for filho in self.children:
            saida.append(filho)
            saida.extend(filho.descendentes())
        return saida

    # ----- serialização (determinística, JSON-safe) -----

    def to_dict(self) -> dict:
        dados = {"id": self.id, "nome": self.nome, "tipo": self.tipo,
                 "x": self.x, "y": self.y, "largura": self.largura,
                 "altura": self.altura, "visivel": self.visivel,
                 "habilitado": self.habilitado,
                 "interativo": self.interativo,
                 "texto": self.texto, "role": self.role,
                 "atributos": dict(self.atributos),
                 "parent": self.parent.id if self.parent else None,
                 "children": [c.id for c in self.children]}
        if not _e_dado(dados):
            raise ErroELiXX(f'Nó "{self.id}" com valores não serializáveis.')
        return dados

    @staticmethod
    def from_dict(dados: dict) -> EnvironmentNode:
        if not isinstance(dados, dict):
            raise ErroELiXX("Nó precisa de dicionário.")
        return EnvironmentNode(
            dados.get("id", ""), nome=dados.get("nome", ""),
            tipo=dados.get("tipo", "desconhecido"),
            x=dados.get("x", 0.0), y=dados.get("y", 0.0),
            largura=dados.get("largura", 0.0),
            altura=dados.get("altura", 0.0),
            visivel=dados.get("visivel", True),
            habilitado=dados.get("habilitado", True),
            interativo=dados.get("interativo", False),
            texto=dados.get("texto"), role=dados.get("role"),
            atributos=dados.get("atributos") or {})

    def __repr__(self) -> str:
        return f"EnvironmentNode({self.tipo} {self.id})"


# ----- Region -----

class EnvironmentRegion:
    """Região semântica (cabeçalho, menu, conteúdo, rodapé...)."""

    def __init__(self, reg_id: str, nome: str = "",
                 nos: list | None = None, superficies: list | None = None,
                 limites: list | None = None,
                 sub_regioes: list | None = None,
                 pai: str | None = None) -> None:
        self.id = _id_valido(reg_id)
        self.nome = str(nome or "")
        self.nos = list(dict.fromkeys(str(n) for n in (nos or [])))
        self.superficies = list(dict.fromkeys(
            str(s) for s in (superficies or [])))
        self.limites = list(dict.fromkeys(str(l) for l in (limites or [])))
        self.sub_regioes = list(dict.fromkeys(
            str(s) for s in (sub_regioes or [])))
        self.pai = (str(pai) if pai is not None else None)

    def to_dict(self) -> dict:
        return {"id": self.id, "nome": self.nome,
                "nos": _ordenado(self.nos),
                "superficies": _ordenado(self.superficies),
                "limites": _ordenado(self.limites),
                "sub_regioes": _ordenado(self.sub_regioes),
                "pai": self.pai}

    @staticmethod
    def from_dict(dados: dict) -> EnvironmentRegion:
        if not isinstance(dados, dict):
            raise ErroELiXX("Região precisa de dicionário.")
        return EnvironmentRegion(
            dados.get("id", ""), nome=dados.get("nome", ""),
            nos=dados.get("nos") or [],
            superficies=dados.get("superficies") or [],
            limites=dados.get("limites") or [],
            sub_regioes=dados.get("sub_regioes") or [],
            pai=dados.get("pai"))

    def __repr__(self) -> str:
        return f"EnvironmentRegion({self.id})"


# ----- Surface -----

class EnvironmentSurface:
    """Superfície potencial de presença/deslocamento (NÃO auto-caminhável).

    A capacidade (caminhar, escalar...) vem dos dados ou das regras do
    chamador — nunca inventada aqui.
    """

    def __init__(self, sup_id: str, owner: str,
                 x: float = 0.0, y: float = 0.0,
                 largura: float = 0.0, altura: float = 0.0,
                 orientacao: str = "desconhecida",
                 tipo: str = "desconhecida",
                 capacidades: list | None = None,
                 bloqueada: bool = False) -> None:
        self.id = _id_valido(sup_id)
        self.owner = _id_valido(owner, "owner da superfície")
        self.x = _finito_num(x, f"x da superfície {self.id}")
        self.y = _finito_num(y, f"y da superfície {self.id}")
        self.largura = _finito_num(largura, f"largura da superfície {self.id}")
        self.altura = _finito_num(altura, f"altura da superfície {self.id}")
        if self.largura < 0 or self.altura < 0:
            raise ErroELiXX(f'Superfície "{self.id}": tamanho negativo.')
        self.orientacao = (str(orientacao).strip() or "desconhecida")
        self.tipo = (str(tipo).strip() or "desconhecida")
        if self.orientacao not in TIPOS_SUPERFICIE:
            self.orientacao = "desconhecida"
        if self.tipo not in TIPOS_SUPERFICIE:
            self.tipo = "desconhecida"
        self.capacidades = tuple(str(c).strip() for c in (capacidades or [])
                                 if str(c).strip())
        self.bloqueada = bool(bloqueada)

    def bounds(self) -> Bounds2D:
        return Bounds2D(self.x, self.y, self.largura, self.altura)

    def navegavel(self) -> bool:
        """Candidata a navegável (regra explícita, sem física)."""
        return (not self.bloqueada and self.largura > 0
                and self.altura >= 0)

    def to_dict(self) -> dict:
        return {"id": self.id, "owner": self.owner, "x": self.x,
                "y": self.y, "largura": self.largura,
                "altura": self.altura, "orientacao": self.orientacao,
                "tipo": self.tipo,
                "capacidades": _ordenado(self.capacidades),
                "bloqueada": self.bloqueada}

    @staticmethod
    def from_dict(dados: dict) -> EnvironmentSurface:
        if not isinstance(dados, dict):
            raise ErroELiXX("Superfície precisa de dicionário.")
        return EnvironmentSurface(
            dados.get("id", ""), dados.get("owner", ""),
            x=dados.get("x", 0.0), y=dados.get("y", 0.0),
            largura=dados.get("largura", 0.0),
            altura=dados.get("altura", 0.0),
            orientacao=dados.get("orientacao", "desconhecida"),
            tipo=dados.get("tipo", "desconhecida"),
            capacidades=dados.get("capacidades") or [],
            bloqueada=dados.get("bloqueada", False))

    def __repr__(self) -> str:
        return f"EnvironmentSurface({self.tipo} {self.id})"


# ----- Boundary -----

class EnvironmentBoundary:
    """Borda/limite derivado de geometria (reusa Bounds2D)."""

    def __init__(self, b_id: str, owner: str, lado: str,
                 x: float = 0.0, y: float = 0.0,
                 largura: float = 0.0, altura: float = 0.0) -> None:
        self.id = _id_valido(b_id)
        self.owner = _id_valido(owner, "owner do limite")
        lado_txt = str(lado).strip()
        if lado_txt not in LADOS_BOUNDARY:
            raise ErroELiXX(f'Lado inválido: "{lado}". '
                            f'Válidos: {", ".join(LADOS_BOUNDARY)}.')
        self.lado = lado_txt
        self.x = _finito_num(x, f"x do limite {self.id}")
        self.y = _finito_num(y, f"y do limite {self.id}")
        self.largura = _finito_num(largura, f"largura do limite {self.id}")
        self.altura = _finito_num(altura, f"altura do limite {self.id}")
        if self.largura < 0 or self.altura < 0:
            raise ErroELiXX(f'Limite "{self.id}": tamanho negativo.')

    def bounds(self) -> Bounds2D:
        return Bounds2D(self.x, self.y, self.largura, self.altura)

    def ponto(self) -> Vector2:
        """Ponto representativo (meio da borda; documentado)."""
        if self.lado == "esquerda":
            return Vector2(self.x, self.y + self.altura / 2.0)
        if self.lado == "direita":
            return Vector2(self.x + self.largura,
                           self.y + self.altura / 2.0)
        if self.lado == "topo":
            return Vector2(self.x + self.largura / 2.0, self.y)
        if self.lado == "base":
            return Vector2(self.x + self.largura / 2.0,
                           self.y + self.altura)
        return Vector2(self.x + self.largura / 2.0,
                       self.y + self.altura / 2.0)

    @staticmethod
    def derivar_de_node(no: EnvironmentNode,
                        lado: str) -> EnvironmentBoundary:
        """Borda derivada do bounds do nó (sem nova matemática)."""
        if lado not in LADOS_BOUNDARY:
            raise ErroELiXX(f'Lado inválido: "{lado}".')
        b = no.bounds()
        if lado == "topo":
            return EnvironmentBoundary(f"{no.id}_borda_topo", no.id, lado,
                                       b.x, b.y, b.largura, 0.0)
        if lado == "base":
            return EnvironmentBoundary(f"{no.id}_borda_base", no.id, lado,
                                       b.x, b.base, b.largura, 0.0)
        if lado == "esquerda":
            return EnvironmentBoundary(f"{no.id}_borda_esquerda", no.id,
                                       lado, b.x, b.y, 0.0, b.altura)
        if lado == "direita":
            return EnvironmentBoundary(f"{no.id}_borda_direita", no.id,
                                       lado, b.direita, b.y, 0.0, b.altura)
        if lado == "interna":
            return EnvironmentBoundary(f"{no.id}_borda_interna", no.id,
                                       lado, b.x, b.y, b.largura, b.altura)
        return EnvironmentBoundary(f"{no.id}_limite_externo", no.id, lado,
                                   b.x, b.y, b.largura, b.altura)

    def to_dict(self) -> dict:
        return {"id": self.id, "owner": self.owner, "lado": self.lado,
                "x": self.x, "y": self.y, "largura": self.largura,
                "altura": self.altura}

    @staticmethod
    def from_dict(dados: dict) -> EnvironmentBoundary:
        if not isinstance(dados, dict):
            raise ErroELiXX("Limite precisa de dicionário.")
        return EnvironmentBoundary(
            dados.get("id", ""), dados.get("owner", ""),
            dados.get("lado", "externa"),
            x=dados.get("x", 0.0), y=dados.get("y", 0.0),
            largura=dados.get("largura", 0.0),
            altura=dados.get("altura", 0.0))

    def __repr__(self) -> str:
        return f"EnvironmentBoundary({self.lado} {self.id})"


# ----- InteractionDescriptor -----

@dataclass
class InteractionDescriptor:
    """Interação declarativa (descrição; nunca executa código)."""

    nome: str
    tipo: str = "clicar"
    alvo: str = ""
    requisitos: tuple = field(default_factory=tuple)
    parametros_permitidos: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.nome = _id_valido(self.nome, "nome da interação")
        self.tipo = str(self.tipo).strip() or "clicar"
        self.alvo = str(self.alvo or "").strip()
        self.requisitos = tuple(str(r).strip() for r in self.requisitos
                                if str(r).strip())
        params = dict(self.parametros_permitidos or {})
        if not _e_dado(params):
            raise ErroELiXX(f'Interação "{self.nome}": parâmetros '
                            "permitidos inválidos (só JSON finito).")
        self.parametros_permitidos = params

    def validar_parametros(self, params: dict | None) -> dict:
        """{"valido", "codigo", "motivo"} — só chaves permitidas."""
        params = params or {}
        if not isinstance(params, dict):
            return {"valido": False, "codigo": "parametros_invalidos",
                    "motivo": "Parâmetros precisam de dicionário."}
        for chave in params:
            if chave not in self.parametros_permitidos:
                return {"valido": False, "codigo": "parametro_desconhecido",
                        "motivo": f'Parâmetro "{chave}" não permitido em '
                                  f'"{self.nome}".'}
        if not _e_dado(params):
            return {"valido": False, "codigo": "parametros_invalidos",
                    "motivo": "Parâmetros com valores não serializáveis."}
        return {"valido": True, "codigo": "ok",
                "motivo": "Parâmetros válidos."}

    def to_dict(self) -> dict:
        return {"nome": self.nome, "tipo": self.tipo, "alvo": self.alvo,
                "requisitos": _ordenado(self.requisitos),
                "parametros_permitidos": dict(self.parametros_permitidos)}

    @staticmethod
    def from_dict(dados: dict) -> InteractionDescriptor:
        if not isinstance(dados, dict):
            raise ErroELiXX("Interação precisa de dicionário.")
        return InteractionDescriptor(
            dados.get("nome", ""), tipo=dados.get("tipo", "clicar"),
            alvo=dados.get("alvo", ""),
            requisitos=tuple(dados.get("requisitos") or ()),
            parametros_permitidos=dict(
                dados.get("parametros_permitidos") or {}))

    def __repr__(self) -> str:
        return f"InteractionDescriptor({self.tipo} {self.nome})"


# ----- Environment -----

class Environment:
    """Abstração única de ambiente externo (web/app/desktop/elixx)."""

    def __init__(self, env_id: str, nome: str = "",
                 tipo: str = "generico", largura: float = 800.0,
                 altura: float = 600.0,
                 metadados: dict | None = None) -> None:
        self.id = _id_valido(env_id)
        self.nome = str(nome or "")
        tipo_txt = str(tipo).strip() or "generico"
        if tipo_txt not in TIPOS_ENVIRONMENT:
            raise ErroELiXX(f'Tipo de ambiente inválido: "{tipo}". '
                            f'Válidos: {", ".join(TIPOS_ENVIRONMENT)}.')
        self.tipo = tipo_txt
        self.largura = _finito_num(largura, "largura do ambiente")
        self.altura = _finito_num(altura, "altura do ambiente")
        if self.largura < 0 or self.altura < 0:
            raise ErroELiXX("Ambiente com tamanho negativo.")
        meta = dict(metadados or {})
        if not _e_dado(meta):
            raise ErroELiXX("Metadados do ambiente inválidos "
                            "(só JSON finito).")
        self.metadados = meta
        self._nos: dict[str, EnvironmentNode] = {}
        self._ordem: list[str] = []
        self._regioes: dict[str, EnvironmentRegion] = {}
        self._superficies: dict[str, EnvironmentSurface] = {}
        self._limites: dict[str, EnvironmentBoundary] = {}
        self._interacoes: dict[str, InteractionDescriptor] = {}

    def __len__(self) -> int:
        return len(self._nos)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nos

    # ----- nós -----

    def adicionar_no(self, no: EnvironmentNode,
                     parent_id: str | None = None) -> EnvironmentNode:
        if not isinstance(no, EnvironmentNode):
            raise ErroELiXX("adicionar_no espera EnvironmentNode.")
        if no.id in self._nos:
            raise ErroELiXX(f'Nó "{no.id}" duplicado no ambiente '
                            f'"{self.id}".')
        if len(self._nos) >= MAX_NOS:
            raise ErroELiXX(f'Ambiente "{self.id}" além de {MAX_NOS} nós '
                            "(estrutura gigante recusada).")
        if parent_id is not None:
            pai = self.obter_no(parent_id)
            pai.adicionar_filho(no)
        elif no.parent is not None and no.parent.id in self._nos:
            dono = self._nos[no.parent.id]
            if no not in dono.children:
                dono.adicionar_filho(no)
        self._nos[no.id] = no
        self._ordem.append(no.id)
        return no

    def obter_no(self, node_id: str) -> EnvironmentNode:
        try:
            return self._nos[str(node_id)]
        except KeyError:
            raise ErroELiXX(f'Nó "{node_id}" não existe no ambiente '
                            f'"{self.id}".')

    por_id = obter_no

    def obter_por_nome(self, nome: str) -> list[EnvironmentNode]:
        return [self._nos[nid] for nid in self._ordem
                if self._nos[nid].nome == nome]

    def filhos_de(self, node_id: str) -> list[EnvironmentNode]:
        return list(self.obter_no(node_id).children)

    # ----- regiões / superfícies / limites / interações -----

    def adicionar_regiao(self, regiao: EnvironmentRegion
                         ) -> EnvironmentRegion:
        if not isinstance(regiao, EnvironmentRegion):
            raise ErroELiXX("adicionar_regiao espera EnvironmentRegion.")
        if regiao.id in self._regioes:
            raise ErroELiXX(f'Região "{regiao.id}" duplicada.')
        self._regioes[regiao.id] = regiao
        return regiao

    def regiao_por_id(self, reg_id: str) -> EnvironmentRegion:
        try:
            return self._regioes[str(reg_id)]
        except KeyError:
            raise ErroELiXX(f'Região "{reg_id}" não existe.')

    def regiao_por_nome(self, nome: str) -> list[EnvironmentRegion]:
        return [r for rid, r in sorted(self._regioes.items())
                if r.nome == nome]

    def nos_da_regiao(self, reg_id: str) -> list[EnvironmentNode]:
        regiao = self.regiao_por_id(reg_id)
        return [self.obter_no(nid) for nid in _ordenado(regiao.nos)
                if nid in self._nos]

    def adicionar_superficie(self, sup: EnvironmentSurface
                             ) -> EnvironmentSurface:
        if not isinstance(sup, EnvironmentSurface):
            raise ErroELiXX("adicionar_superficie espera "
                            "EnvironmentSurface.")
        if sup.id in self._superficies:
            raise ErroELiXX(f'Superfície "{sup.id}" duplicada.')
        self._superficies[sup.id] = sup
        return sup

    def adicionar_limite(self, limite: EnvironmentBoundary
                         ) -> EnvironmentBoundary:
        if not isinstance(limite, EnvironmentBoundary):
            raise ErroELiXX("adicionar_limite espera EnvironmentBoundary.")
        if limite.id in self._limites:
            raise ErroELiXX(f'Limite "{limite.id}" duplicado.')
        self._limites[limite.id] = limite
        return limite

    def adicionar_interacao(self, inter: InteractionDescriptor
                            ) -> InteractionDescriptor:
        if not isinstance(inter, InteractionDescriptor):
            raise ErroELiXX("adicionar_interacao espera "
                            "InteractionDescriptor.")
        if inter.nome in self._interacoes:
            raise ErroELiXX(f'Interação "{inter.nome}" duplicada.')
        self._interacoes[inter.nome] = inter
        return inter

    # ----- validação estrutural (determinística; sem efeitos) -----

    def validar(self) -> dict:
        """Verifica refs, ciclos, tipos e limites. Retorna estruturado."""
        for nid in self._ordem:
            no = self._nos[nid]
            if no.parent is not None and no.parent.id not in self._nos:
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Nó "{nid}": pai '
                                  f'"{no.parent.id}" ausente.'}
        visitados: set[str] = set()

        def _visita(no: EnvironmentNode, pilha: tuple) -> dict | None:
            if no.id in pilha:
                return {"valido": False, "codigo": "ciclo",
                        "motivo": f'Ciclo envolvendo "{no.id}".'}
            if no.id in visitados:
                return None
            visitados.add(no.id)
            for filho in no.children:
                if filho.id not in self._nos:
                    return {"valido": False,
                            "codigo": "referencia_invalida",
                            "motivo": f'Nó "{no.id}": filho '
                                      f'"{filho.id}" ausente.'}
                erro = _visita(filho, pilha + (no.id,))
                if erro is not None:
                    return erro
            return None

        for nid in self._ordem:
            erro = _visita(self._nos[nid], ())
            if erro is not None:
                return erro
        for rid in sorted(self._regioes):
            reg = self._regioes[rid]
            for nid in reg.nos:
                if nid not in self._nos:
                    return {"valido": False,
                            "codigo": "referencia_invalida",
                            "motivo": f'Região "{rid}": nó "{nid}" '
                                      "ausente."}
            for sub in reg.sub_regioes:
                if sub not in self._regioes:
                    return {"valido": False,
                            "codigo": "referencia_invalida",
                            "motivo": f'Região "{rid}": sub-região '
                                      f'"{sub}" ausente.'}
            if reg.pai is not None and reg.pai not in self._regioes:
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Região "{rid}": pai "{reg.pai}" '
                                  "ausente."}
        for sid in sorted(self._superficies):
            sup = self._superficies[sid]
            if sup.owner not in self._nos:
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Superfície "{sid}": dono '
                                  f'"{sup.owner}" ausente.'}
        for lid in sorted(self._limites):
            lim = self._limites[lid]
            if lim.owner not in self._nos:
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Limite "{lid}": dono "{lim.owner}" '
                                  "ausente."}
        for nome in sorted(self._interacoes):
            inter = self._interacoes[nome]
            if inter.alvo and inter.alvo not in self._nos:
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Interação "{nome}": alvo '
                                  f'"{inter.alvo}" ausente.'}
        return {"valido": True, "codigo": "ok",
                "motivo": "Ambiente válido."}

    # ----- serialização -----

    def to_dict(self) -> dict:
        dados = {
            "id": self.id, "nome": self.nome, "tipo": self.tipo,
            "largura": self.largura, "altura": self.altura,
            "metadados": dict(self.metadados),
            "nos": [self._nos[nid].to_dict() for nid in self._ordem],
            "regioes": [self._regioes[rid].to_dict()
                        for rid in sorted(self._regioes)],
            "superficies": [self._superficies[sid].to_dict()
                            for sid in sorted(self._superficies)],
            "limites": [self._limites[lid].to_dict()
                        for lid in sorted(self._limites)],
            "interacoes": [self._interacoes[n].to_dict()
                           for n in sorted(self._interacoes)],
        }
        if not _e_dado(dados):
            raise ErroELiXX("Ambiente com valores não serializáveis.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> Environment:
        if not isinstance(dados, dict):
            raise ErroELiXX("Ambiente precisa de dicionário.")
        env = Environment(
            dados.get("id", ""), nome=dados.get("nome", ""),
            tipo=dados.get("tipo", "generico"),
            largura=dados.get("largura", 800.0),
            altura=dados.get("altura", 600.0),
            metadados=dict(dados.get("metadados") or {}))
        nos_txt = dados.get("nos") or []
        if len(nos_txt) > MAX_NOS:
            raise ErroELiXX(f"Ambiente com {len(nos_txt)} nós (teto "
                            f"{MAX_NOS}).")
        pendentes: dict[str, str | None] = {}
        for item in nos_txt:
            no = EnvironmentNode.from_dict(item)
            pai = item.get("parent")
            pendentes[no.id] = (str(pai) if pai is not None else None)
            env.adicionar_no(no)
        for nid, pai in pendentes.items():
            if pai is not None:
                if pai not in env._nos:
                    raise ErroELiXX(f'Nó "{nid}": pai "{pai}" ausente.')
                env._nos[pai].adicionar_filho(env._nos[nid])
        for item in (dados.get("regioes") or []):
            env.adicionar_regiao(EnvironmentRegion.from_dict(item))
        for item in (dados.get("superficies") or []):
            env.adicionar_superficie(EnvironmentSurface.from_dict(item))
        for item in (dados.get("limites") or []):
            env.adicionar_limite(EnvironmentBoundary.from_dict(item))
        for item in (dados.get("interacoes") or []):
            env.adicionar_interacao(InteractionDescriptor.from_dict(item))
        resultado = env.validar()
        if not resultado["valido"]:
            raise ErroELiXX(f"Ambiente inválido: {resultado['motivo']}")
        return env

    @staticmethod
    def from_json(texto: str) -> Environment:
        if not isinstance(texto, str):
            raise ErroELiXX("Ambiente JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Ambiente JSON inválido: {exc}.")
        return Environment.from_dict(dados)

    def __repr__(self) -> str:
        return f"Environment({self.tipo} {self.id}: {len(self)} nós)"


# ----- adaptador genérico (estrutura externa → Environment) -----

def ambiente_de_dict(dados: dict) -> Environment:
    """Adapter único: dict externo (web/app/desktop) → Environment.

    Esperado: {"id", "tipo"? ("web"|"aplicativo"|"desktop"|"elixx"|
    "generico"), "nome"?, "largura"?, "altura"?, "nos": [...],
    "regioes"?, "superficies"?, "limites"?, "interacoes"?,
    "metadados"?}. Nós: {"id", "tipo", "nome"?, "x"?, "y"?,
    "largura"?, "altura"?, ...}. Tudo validado; nada executado.
    """
    if not isinstance(dados, dict):
        raise ErroELiXX("Adaptador espera dicionário.")
    copia = dict(dados)
    if "tipo" not in copia:
        copia["tipo"] = "generico"
    return Environment.from_dict(copia)


# ----- estrutura → semântica (regras determinísticas e documentadas) -----
#
# 1. tipo "botao" (visível+habilitado) → interativo + clicar/focar.
# 2. tipo "entrada" → focar/escrever/selecionar/limpar.
# 3. tipo "selecao"/"lista" → selecionar/abrir/navegar.
# 4. tipo "janela" → fechar/minimizar/maximizar.
# 5. nó com geometria (largura>0 e altura>0) → 4 boundaries + externa.
# 6. tipo em (painel, caixa, barra) ou atributo superficie=True →
#    EnvironmentSurface horizontal (área por padrão se vertical? não:
#    sempre horizontal salvo atributo orientacao explícito).
# Nenhuma inferência "inteligente": só estas regras, sempre iguais.

def inferir_interacoes(no: EnvironmentNode) -> list[InteractionDescriptor]:
    """Interações declarativas do nó (regras 1–4; sem IA)."""
    if no.tipo == "botao" and no.visivel and no.habilitado:
        return [InteractionDescriptor(f"{no.id}_clicar", tipo="clicar",
                                      alvo=no.id),
                InteractionDescriptor(f"{no.id}_focar", tipo="focar",
                                      alvo=no.id)]
    if no.tipo == "entrada" and no.habilitado:
        return [InteractionDescriptor(f"{no.id}_{acao}", tipo=acao,
                                      alvo=no.id,
                                      requisitos=("focar",)
                                      if acao != "focar" else (),
                                      parametros_permitidos=(
                                          {"texto": "texto"}
                                          if acao == "escrever" else {}))
                for acao in ("focar", "escrever", "selecionar", "limpar")]
    if no.tipo in ("selecao", "lista") and no.habilitado:
        return [InteractionDescriptor(f"{no.id}_{acao}", tipo=acao,
                                      alvo=no.id)
                for acao in ("selecionar", "abrir", "navegar")]
    if no.tipo == "janela":
        return [InteractionDescriptor(f"{no.id}_{acao}", tipo=acao,
                                      alvo=no.id)
                for acao in ("fechar", "minimizar", "maximizar")]
    return []


def gerar_boundaries(no: EnvironmentNode) -> list[EnvironmentBoundary]:
    """Topo/base/esquerda/direita + externa (regra 5; sem geometria→∅)."""
    if not no.tem_geometria():
        return []
    saidas = []
    for lado in ("topo", "base", "esquerda", "direita", "externa"):
        saidas.append(EnvironmentBoundary.derivar_de_node(no, lado))
    return saidas


def gerar_surface(no: EnvironmentNode) -> EnvironmentSurface | None:
    """Superfície do nó (regra 6; None se não aplicável)."""
    marca = (no.atributos or {}).get("superficie", False)
    orientacao = str((no.atributos or {}).get("orientacao",
                                              "horizontal"))
    if orientacao not in TIPOS_SUPERFICIE:
        orientacao = "horizontal"
    if no.tipo in ("painel", "caixa", "barra") or marca is True:
        if not no.tem_geometria():
            return None
        caps = tuple((no.atributos or {}).get("capacidades", []) or ())
        bloqueada = bool((no.atributos or {}).get("bloqueada", False))
        return EnvironmentSurface(
            f"sup_{no.id}", owner=no.id, x=no.x, y=no.y,
            largura=no.largura, altura=no.altura,
            orientacao=orientacao, tipo=orientacao,
            capacidades=[str(c) for c in caps], bloqueada=bloqueada)
    return None


# ----- ponte Environment → World (F13; sem copiar sistemas) -----

def _tipo_world_para(no: EnvironmentNode,
                     superficies: dict[str, EnvironmentSurface]) -> str:
    """Nó → tipo do World (preserva geometria e navegabilidade)."""
    for sup in superficies.values():
        if sup.owner == no.id and not sup.bloqueada:
            if sup.orientacao == "horizontal":
                return "plataforma"
            if sup.orientacao == "vertical":
                return "parede"
            return "area"
    if no.tipo in NOS_CONTENTORES:
        return "area"
    return "objeto"


def vincular_ambiente(environment: Environment, mundo=None,
                      nome_mundo: str | None = None):
    """Environment → World (fonte estrutural → representação operacional).

    Preserva ids (nós; regiões/superfícies ganham id próprio quando não
    colidem), geometria, hierarquia relevante (pai em props), roles e
    capacidades (em props/tags — sem duplicar o registry F14).
    """
    from .mundo import World, WorldEntity

    if not isinstance(environment, Environment):
        raise ErroELiXX("vincular_ambiente espera Environment.")
    resultado = environment.validar()
    if not resultado["valido"]:
        raise ErroELiXX(f"Ambiente inválido: {resultado['motivo']}")
    nome = nome_mundo or environment.id
    if mundo is None:
        mundo = World(nome, cena=None,
                      bounds=Bounds2D(0.0, 0.0, environment.largura,
                                     environment.altura))
    for nid in environment._ordem:
        no = environment._nos[nid]
        tipo_w = _tipo_world_para(no, environment._superficies)
        props = {"env_id": no.id, "env_tipo": no.tipo}
        if no.role:
            props["role"] = no.role
        if no.parent is not None:
            props["pai"] = no.parent.id
        if no.texto:
            props["texto"] = no.texto
        caps: list[str] = []
        for sup in environment._superficies.values():
            if sup.owner == no.id:
                caps.extend(sup.capacidades)
        if caps:
            props["capacidades"] = sorted(set(caps))
        tags = tuple(sorted(set(caps)))
        entidade = WorldEntity(nid, tipo_w, mundo,
                               base=no.bounds(), categoria=no.tipo,
                               tags=tags, props=props)
        entidade.tamanho_explicito = True
        try:
            mundo.adicionar(entidade)
        except ErroELiXX:
            # Colisão honesta (id já usado por região anterior): prefixa.
            entidade.nome = f"no_{nid}"
            entidade.props["env_id"] = nid
            mundo.adicionar(entidade)
    for rid in sorted(environment._regioes):
        if rid in mundo:
            continue
        reg = environment._regioes[rid]
        membros = [environment._nos[n].bounds()
                   for n in reg.nos if n in environment._nos]
        limites = membros[0] if membros else Bounds2D(0.0, 0.0, 0.0, 0.0)
        for outro in membros[1:]:
            limites = limites.uniao(outro)
        props = {"env_regiao": rid, "membros": sorted(reg.nos)}
        if reg.pai:
            props["pai"] = reg.pai
        entidade = WorldEntity(rid, "area", mundo, base=limites,
                               categoria="regiao", tags=(),
                               props=props)
        entidade.tamanho_explicito = True
        mundo.adicionar(entidade)
    return mundo


def construir_grafo_de_ambiente(mundo, ligacoes: list | None = None,
                                nome: str | None = None):
    """World (de Environment) → NavigationGraph (F15, sem inventar rotas).

    Cria nós ent:* para todas as entidades, superfícies/bordas para
    plataforma (como o NavigationBuilder) e SÓ os edges declarados em
    `ligacoes` ([{origem, destino, modo?, custo?, requer?, bloqueado?}]).
    Sem ligações: grafo com nós e zero edges (filosofia conservadora).
    """
    from .navegacao import (NavigationEdge, NavigationGraph,
                            NavigationNode, NavigationSurface,
                            _node_id_de_ref)

    grafo = NavigationGraph(nome or getattr(mundo, "nome", "ambiente"),
                            mundo)
    for nome_ent in list(mundo._ordem):
        entidade = mundo._entidades[nome_ent]
        grafo.adicionar_no(NavigationNode(
            f"ent:{nome_ent}", "entidade", mundo, entidade=nome_ent,
            tags=tuple(entidade.tags)))
        if entidade.tipo in ("chao", "plataforma"):
            navegavel = entidade.tipo == "plataforma"
            grafo.adicionar_superficie(NavigationSurface(
                f"sup:{nome_ent}", nome_ent, entidade.tipo, mundo,
                navegavel=navegavel))
            if entidade.tipo == "plataforma":
                for lado in ("esquerda", "direita"):
                    node_id = f"{nome_ent}_borda_{lado}"
                    grafo.adicionar_no(NavigationNode(
                        node_id, "borda", mundo, entidade=nome_ent,
                        lado=lado))
                    for origem, destino in ((f"ent:{nome_ent}", node_id),
                                            (node_id, f"ent:{nome_ent}")):
                        grafo.adicionar_edge(NavigationEdge(
                            origem, destino, modo="andar"))
    for lig in (ligacoes or []):
        if not isinstance(lig, dict):
            raise ErroELiXX("Ligação precisa de dicionário.")
        origem = _node_id_de_ref(str(lig.get("origem", "")))
        destino = _node_id_de_ref(str(lig.get("destino", "")))
        modo = str(lig.get("modo", "andar") or "andar")
        custo = lig.get("custo")
        custo_f = None
        if custo is not None:
            custo_f = _finito_num(custo, "custo da ligação")
            if custo_f < 0:
                raise ErroELiXX("Custo da ligação precisa de ≥ 0.")
        requer = lig.get("requer")
        requer_txt = (str(requer).strip() if requer is not None else None)
        grafo.adicionar_edge(NavigationEdge(
            origem, destino, modo=modo, custo=custo_f,
            requer=requer_txt,
            bloqueado=bool(lig.get("bloqueado", False))))
    return grafo


# ----- AIContextBuilder (Environment+World+agente → contexto F18) -----

class AIContextBuilder:
    """Contexto estruturado para AIProvider.gerar_intencao (F18).

    Determinístico, serializável, JSON-safe: sem objetos Python, sem
    código, sem funções, sem referências executáveis.
    """

    def construir(self, environment: Environment, mundo,
                  agente, grafo=None, destino=None,
                  raio: float = 400.0) -> dict:
        if not isinstance(environment, Environment):
            raise ErroELiXX("AIContextBuilder espera Environment.")
        raio = _finito_num(raio, "raio do contexto")
        if raio < 0:
            raise ErroELiXX("Raio do contexto precisa de ≥ 0.")
        nome_agente, pos, caps = self._agente_info(environment, mundo,
                                                   agente)
        regioes = [r.to_dict() for _, r in sorted(
            environment._regioes.items())]
        elementos = []
        for nid in environment._ordem:
            no = environment._nos[nid]
            centro = no.center()
            elementos.append({
                "id": no.id, "nome": no.nome, "tipo": no.tipo,
                "x": no.x, "y": no.y, "largura": no.largura,
                "altura": no.altura, "centro": {"x": centro.x,
                                                "y": centro.y},
                "visivel": no.visivel, "habilitado": no.habilitado,
                "interativo": no.interativo,
                "texto": no.texto, "role": no.role,
                "parent": no.parent.id if no.parent else None,
                "children": sorted(c.id for c in no.children)})
        superficies = [s.to_dict() for _, s in sorted(
            environment._superficies.items())]
        interacoes = [i.to_dict() for _, i in sorted(
            environment._interacoes.items())]
        destinos = self._destinos(mundo)
        relacoes = self._relacoes(environment)
        rotas: list[dict] = []
        if grafo is not None and destino is not None:
            rotas = self._rotas(grafo, mundo, agente, nome_agente, destino)
        contexto = {
            "ambiente": {"id": environment.id, "nome": environment.nome,
                         "tipo": environment.tipo,
                         "largura": environment.largura,
                         "altura": environment.altura},
            "agente": nome_agente, "posicao": pos,
            "capacidades": caps, "regioes": regioes,
            "elementos": elementos, "superficies": superficies,
            "interacoes": interacoes, "destinos_possiveis": destinos,
            "relacoes": relacoes, "rotas_disponiveis": rotas,
        }
        if not _e_dado(contexto):
            raise ErroELiXX("Contexto com valores não serializáveis.")
        json.dumps(contexto, ensure_ascii=False, sort_keys=True)
        return contexto

    @staticmethod
    def _agente_info(environment: Environment, mundo, agente):
        """(nome, posicao, capacidades) — Character ou dict simples."""
        nome = getattr(agente, "nome", None)
        if nome is None and isinstance(agente, dict):
            nome = agente.get("nome", "agente")
        nome = str(nome or "agente")
        caps: list[str] = []
        pos = {"x": 0.0, "y": 0.0}
        tem = getattr(agente, "capacidades_compostas", None)
        if callable(tem):
            try:
                caps = sorted(tem().nomes())
            except ErroELiXX:
                caps = []
        elif isinstance(agente, dict):
            caps = sorted(str(c) for c in agente.get("capacidades", []))
        if mundo is not None and nome in getattr(mundo, "_entidades", {}):
            try:
                centro = mundo.por_id(nome).centro()
                pos = {"x": float(centro.x), "y": float(centro.y)}
            except ErroELiXX:
                pass
        elif isinstance(agente, dict):
            try:
                pos = {"x": float(agente.get("x", 0.0)),
                       "y": float(agente.get("y", 0.0))}
            except (TypeError, ValueError):
                pos = {"x": 0.0, "y": 0.0}
        else:
            no = getattr(getattr(agente, "no_raiz", None), "x", None)
            if no is not None:
                try:
                    pos = {"x": float(getattr(agente.no_raiz, "x", 0.0)),
                           "y": float(getattr(agente.no_raiz, "y", 0.0))}
                except (TypeError, ValueError):
                    pass
        _ = environment
        return nome, pos, caps

    @staticmethod
    def _destinos(mundo) -> list[dict]:
        if mundo is None:
            return []
        saida = []
        for nome_ent in list(getattr(mundo, "_ordem", [])):
            entidade = mundo._entidades[nome_ent]
            centro = entidade.centro()
            saida.append({"nome": nome_ent, "tipo": entidade.tipo,
                          "x": float(centro.x), "y": float(centro.y)})
        return sorted(saida, key=lambda d: d["nome"])

    @staticmethod
    def _relacoes(environment: Environment) -> list[dict]:
        rels = []
        for nid in environment._ordem:
            no = environment._nos[nid]
            if no.parent is not None:
                rels.append({"tipo": "filho_de", "de": no.id,
                             "para": no.parent.id})
            for filho in sorted(no.children, key=lambda c: c.id):
                rels.append({"tipo": "contem", "de": no.id,
                             "para": filho.id})
        for rid in sorted(environment._regioes):
            reg = environment._regioes[rid]
            for nid in sorted(reg.nos):
                rels.append({"tipo": "em_regiao", "de": nid,
                             "para": rid})
            for sub in sorted(reg.sub_regioes):
                rels.append({"tipo": "sub_regiao_de", "de": sub,
                             "para": rid})
        return sorted(rels, key=lambda r: (r["tipo"], r["de"], r["para"]))

    @staticmethod
    def _rotas(grafo, mundo, agente, nome_agente, destino) -> list[dict]:
        from .navegacao import rotas_alternativas

        holder = agente if not isinstance(agente, dict) else None
        try:
            rotas = rotas_alternativas(grafo, nome_agente, destino, k=3,
                                       holder=holder, mundo=mundo)
        except ErroELiXX:
            return []
        saida = []
        for rota in rotas:
            if not rota.get("encontrado"):
                continue
            saida.append({"nos": list(rota.get("nos", [])),
                          "modos": list(rota.get("modos", [])),
                          "custo_total": float(rota.get("custo_total", 0.0)),
                          "requisitos": list(rota.get("requisitos", []))})
        return saida


# ----- InteractionExecutor (runtime mockado e seguro) -----

class InteractionExecutor:
    """Valida e simula/executa interações declarativas (sem código)."""

    def __init__(self, environment: Environment) -> None:
        if not isinstance(environment, Environment):
            raise ErroELiXX("InteractionExecutor espera Environment.")
        self.environment = environment
        self.log: list[dict] = []

    def validar(self, interacao_nome: str, alvo_id: str,
                parametros: dict | None = None, agente=None) -> dict:
        env = self.environment
        nome = str(interacao_nome or "").strip()
        alvo = str(alvo_id or "").strip()
        if nome not in env._interacoes:
            return {"valido": False, "codigo": "interacao_inexistente",
                    "motivo": f'Interação "{nome}" não registrada.'}
        if alvo not in env._nos:
            return {"valido": False, "codigo": "alvo_inexistente",
                    "motivo": f'Alvo "{alvo}" não existe.'}
        descritor = env._interacoes[nome]
        if descritor.alvo and descritor.alvo != alvo:
            return {"valido": False, "codigo": "alvo_incompativel",
                    "motivo": f'Interação "{nome}" é do alvo '
                              f'"{descritor.alvo}" (não "{alvo}").'}
        no = env._nos[alvo]
        if not no.habilitado:
            return {"valido": False, "codigo": "alvo_deshabilitado",
                    "motivo": f'Alvo "{alvo}" desabilitado.'}
        checagem = descritor.validar_parametros(parametros)
        if not checagem["valido"]:
            return {"valido": False, "codigo": checagem["codigo"],
                    "motivo": checagem["motivo"]}
        for requisito in descritor.requisitos:
            if not self._tem_capacidade(agente, requisito):
                return {"valido": False, "codigo": "capacidade_ausente",
                        "motivo": f'Capacidade "{requisito}" ausente.',
                        "requisitos": list(descritor.requisitos)}
        return {"valido": True, "codigo": "ok",
                "motivo": f'Interação "{nome}" válida para "{alvo}".'}

    @staticmethod
    def _tem_capacidade(agente, capacidade: str) -> bool:
        if agente is None:
            return False
        tem = getattr(agente, "tem_capacidade", None)
        if callable(tem):
            try:
                return bool(tem(capacidade))
            except ErroELiXX:
                return False
        if isinstance(agente, dict):
            return str(capacidade) in [str(c) for c in
                                       agente.get("capacidades", [])]
        if isinstance(agente, (list, tuple, set)):
            return str(capacidade) in [str(c) for c in agente]
        return False

    def simular(self, interacao_nome: str, alvo_id: str,
                parametros: dict | None = None, agente=None) -> dict:
        """Dry-run: valida sem efeitos (log marcado como simulação)."""
        checagem = self.validar(interacao_nome, alvo_id, parametros,
                                agente)
        if not checagem["valido"]:
            return {"sucesso": False, **checagem, "simulado": True}
        return {"sucesso": True, "codigo": "ok",
                "motivo": f"Simulação de {interacao_nome} em {alvo_id}.",
                "simulado": True,
                "interacao": str(interacao_nome), "alvo": str(alvo_id),
                "parametros": dict(parametros or {})}

    def executar(self, interacao_nome: str, alvo_id: str,
                 parametros: dict | None = None, agente=None) -> dict:
        """Execução mockada: só descritores registrados (sem navegador)."""
        checagem = self.validar(interacao_nome, alvo_id, parametros,
                                agente)
        if not checagem["valido"]:
            return {"sucesso": False, **checagem, "executado": False}
        registro = {"interacao": str(interacao_nome),
                    "alvo": str(alvo_id),
                    "parametros": dict(parametros or {}),
                    "agente": (getattr(agente, "nome", agente)
                               if not isinstance(agente, dict)
                               else agente.get("nome"))}
        self.log.append(registro)
        return {"sucesso": True, "codigo": "ok",
                "motivo": f"{interacao_nome} em {alvo_id} (mock).",
                "executado": True, **registro}


# ----- debug textual (puro; sem UI) -----

def debug_ambiente(environment: Environment) -> str:
    """NÓS/REGIÕES/SUPERFÍCIES/LIMITES/INTERAÇÕES (diagnóstico puro)."""
    linhas = [f"Environment {environment.id} ({environment.tipo}): "
               f"{len(environment)} nós, "
               f"{len(environment._regioes)} regiões, "
               f"{len(environment._superficies)} superfícies, "
               f"{len(environment._limites)} limites, "
               f"{len(environment._interacoes)} interações"]
    linhas.append("NOS:")
    for nid in environment._ordem:
        no = environment._nos[nid]
        linhas.append(
            f"  [{no.tipo}] {nid} @ ({no.x:g},{no.y:g},"
            f"{no.largura:g}x{no.altura:g}) "
            f"interativo={no.interativo}")
    linhas.append("REGIOES:")
    for rid in sorted(environment._regioes):
        reg = environment._regioes[rid]
        linhas.append(f"  {rid} ({reg.nome}): "
                       f"{', '.join(sorted(reg.nos)) or '—'}")
    linhas.append("SUPERFICIES:")
    for sid in sorted(environment._superficies):
        sup = environment._superficies[sid]
        linhas.append(f"  [{sup.tipo}] {sid} dono={sup.owner} "
                       f"caps={','.join(sup.capacidades) or '—'} "
                       f"bloqueada={sup.bloqueada}")
    linhas.append("INTERACOES:")
    for nome in sorted(environment._interacoes):
        inter = environment._interacoes[nome]
        linhas.append(f"  {inter.tipo} {nome} -> {inter.alvo or '—'}")
    return "\n".join(linhas)
