"""Visual Geometry Core da ELiXX (Fase 21) — onde algo está.

Camada independente e puramente factual de geometria 2D:

    Environment (F19, o que existe)
        ↓ (só geometria explícita; nunca inventada)
    GeometryMap (onde existe)
        ↓ (fonte espacial; sem duplicar entidades)
    World (F13, fonte semântica)

A geometria NÃO decide: não escolhe ação, caminho, botão ou destino.
Ela apenas fornece fatos estruturados (posição, tamanho, centro,
relações, direção, contenção, visibilidade geométrica básica).

Reuso (sem duplicar matemática ou sistemas):

- `Vector2` da F10 (`transform.py`);
- `Bounds2D` da F13 (`mundo.py`);
- `Environment`/`EnvironmentNode` da F19 (só leitura);
- `World`/`WorldEntity` da F13 (integração opcional, sem duplicar);
- Navigation (F15) e Motion (F11/F16) NÃO são recriados aqui.

Segurança: entrada externa é DADO. Só números finitos, strings de
IDs, booleanos e estruturas JSON rasas. Nenhuma avaliação dinâmica,
nenhuma importação programática, nenhum processo externo, nenhuma
rede. Determinismo total: mesma entrada → mesmos fatos, mesma ordem
(listas ordenadas ou por inserção documentada; sem aleatoriedade,
sem relógio, sem threads).

F21 NÃO implementa: folhas de estilo, percepção por imagem,
detectores visuais, leitura de pixels, navegador, modelos de
linguagem, simulação de corpos, busca de rotas, planejador de tarefas
ou execução de ações.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from ..erros import ErroELiXX
from .mundo import Bounds2D
from .transform import Vector2

__all__ = [
    "Vector2",
    "Bounds2D",
    "Point2D",
    "Size2D",
    "DIRECOES",
    "MAX_NOS_GEOMETRIA",
    "MAX_PROFUNDIDADE_GEO",
    "MAX_VALOR_GEO",
    "GeometryNode",
    "GeometryRegion",
    "GeometryMap",
    "GeometrySnapshot",
    "geometry_map_de_dict",
    "parsear_mapa_explicito",
    "environment_para_geometria",
    "geometria_para_world",
    "vincular_geometria_world",
    "direcao_entre",
    "debug_geometria",
]

DIRECOES = ("norte", "sul", "leste", "oeste", "nordeste", "noroeste",
            "sudeste", "sudoeste", "centro")
"""Direções determinísticas a partir de centros (documentado abaixo)."""

MAX_NOS_GEOMETRIA = 100000
"""Teto anti-gigante (F22: mapas planos de percepção com 50k passam;
hierarquia funda segue limitada por MAX_PROFUNDIDADE_GEO)."""

MAX_PROFUNDIDADE_GEO = 32
"""Teto anti-ciclo/recursão na hierarquia (alinha com F19)."""

MAX_VALOR_GEO = 1.0e9
"""Módulo máximo de qualquer coordenada/tamanho (anti-gigante)."""

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
    if abs(numero) > MAX_VALOR_GEO:
        raise ErroELiXX(f'"{o_que}" além de ±{MAX_VALOR_GEO:g} '
                        "(valor gigantesco recusado).")
    return numero


def _e_dado(valor, profundidade: int = 0) -> bool:
    """Apenas JSON puro e finito (sem tupla, sem objeto, sem código)."""
    if profundidade > _PROF_DADOS:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, float) and not math.isfinite(valor):
            return False
        if isinstance(valor, float) and abs(valor) > MAX_VALOR_GEO:
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


# ----- Point2D / Size2D (primitivas novas; Vector2/Bounds2D reutilizados) -----

class Point2D(Vector2):
    """Ponto 2D (x, y). Subclasse de Vector2: sem matemática duplicada."""

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}

    @staticmethod
    def from_dict(dados: dict) -> Point2D:
        if not isinstance(dados, dict):
            raise ErroELiXX("Ponto precisa de dicionário.")
        return Point2D(_finito(dados.get("x", 0.0), "x do ponto"),
                       _finito(dados.get("y", 0.0), "y do ponto"))

    def __repr__(self) -> str:
        return f"Point2D({self.x:g}, {self.y:g})"


@dataclass(frozen=True)
class Size2D:
    """Tamanho 2D (largura, altura ≥ 0)."""

    largura: float = 0.0
    altura: float = 0.0

    def __post_init__(self) -> None:
        larg = _finito(self.largura, "largura do tamanho")
        alt = _finito(self.altura, "altura do tamanho")
        if larg < 0 or alt < 0:
            raise ErroELiXX("Tamanho com dimensão negativa "
                            f"({larg:g}x{alt:g}). Use ≥ 0.")
        object.__setattr__(self, "largura", larg)
        object.__setattr__(self, "altura", alt)

    @property
    def area(self) -> float:
        return self.largura * self.altura

    def to_dict(self) -> dict:
        return {"largura": self.largura, "altura": self.altura}

    @staticmethod
    def from_dict(dados: dict) -> Size2D:
        if not isinstance(dados, dict):
            raise ErroELiXX("Tamanho precisa de dicionário.")
        return Size2D(dados.get("largura", 0.0), dados.get("altura", 0.0))

    def __repr__(self) -> str:
        return f"Size2D({self.largura:g}x{self.altura:g})"


# ----- acessores Bounds2D no vocabulário da F21 (delegam; sem duplicar) -----

def bounds_esquerda(b: Bounds2D) -> float:
    """Esquerda (= x)."""
    return b.x


def bounds_topo(b: Bounds2D) -> float:
    """Topo (= y; Y cresce para baixo, convenção F10)."""
    return b.y


def bounds_baixo(b: Bounds2D) -> float:
    """Baixo (= base da F13)."""
    return b.base


def bounds_tamanho(b: Bounds2D) -> Size2D:
    """Tamanho do bounds."""
    return Size2D(b.largura, b.altura)


def bounds_transladado(b: Bounds2D, dx: float = 0.0,
                       dy: float = 0.0) -> Bounds2D:
    """Cópia deslocada por (dx, dy)."""
    dx_f = _finito(dx, "deslocamento x")
    dy_f = _finito(dy, "deslocamento y")
    return Bounds2D(_finito(b.x + dx_f, "x transladado"),
                    _finito(b.y + dy_f, "y transladado"),
                    b.largura, b.altura)


def bounds_expandido(b: Bounds2D, valor: float) -> Bounds2D:
    """Alias de expandir (margem ≥ 0 em todas as direções)."""
    return b.expandir(valor)


# ----- direção (regra explícita e documentada) -----
#
# Usa os centros: dx = leste(+) / oeste(-), dy = sul(+) / norte(-)
# (Y cresce para baixo, convenção F10). Se |dx| e |dy| < 0.5: centro.
# Caso contrário, o eixo dominante dá o ponto cardeal; se o eixo
# secundário tem pelo menos metade do dominante, vira diagonal.
# Sem heurísticas, sem limiares mágicos por tipo de objeto.

def direcao_entre(origem: Vector2, destino: Vector2) -> str:
    """Direção de origem → destino (8 vias + centro)."""
    dx = float(destino.x) - float(origem.x)
    dy = float(destino.y) - float(origem.y)
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return "centro"
    horiz = "leste" if dx > 0 else "oeste"
    vert = "sul" if dy > 0 else "norte"
    if abs(dx) < 0.5:
        return vert
    if abs(dy) < 0.5:
        return horiz
    if abs(dy) >= abs(dx) / 2.0 and abs(dx) >= abs(dy) / 2.0:
        # Diagonal: eixo vertical primeiro (nordeste, sudoeste...).
        nomes = {("norte", "leste"): "nordeste",
                 ("norte", "oeste"): "noroeste",
                 ("sul", "leste"): "sudeste",
                 ("sul", "oeste"): "sudoeste"}
        return nomes[(vert, horiz)]
    if abs(dx) >= abs(dy):
        return horiz
    return vert


# ----- GeometryNode -----

class GeometryNode:
    """Geometria de uma entidade: bounds LOCAL + estado. Só dados.

    `bounds` é local ao pai (pai ausente = já global). O bounds global
    é derivado pelo GeometryMap (soma de origens até a raiz).
    Fonte de verdade sobre movimento ELiXX continua sendo Transform/
    Scene: este nó é representação espacial derivada (documentado).
    """

    def __init__(self, node_id: str, bounds: Bounds2D | None = None,
                 parent_id: str | None = None,
                 visible: bool = True, enabled: bool = True,
                 z_index: int = 0,
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(node_id)
        if bounds is None:
            bounds = Bounds2D(0.0, 0.0, 0.0, 0.0)
        if not isinstance(bounds, Bounds2D):
            raise ErroELiXX(f'Nó "{self.id}": bounds precisa de Bounds2D.')
        for campo in ("x", "y", "largura", "altura"):
            _finito(getattr(bounds, campo), f"{campo} do nó {self.id}")
        if bounds.largura < 0 or bounds.altura < 0:
            raise ErroELiXX(f'Nó "{self.id}": tamanho negativo.')
        self.bounds = bounds
        self.parent_id = (str(parent_id).strip()
                          if parent_id is not None else None)
        if self.parent_id == "":
            self.parent_id = None
        if self.parent_id == self.id:
            raise ErroELiXX(f'Nó "{self.id}": pai de si mesmo (ciclo).')
        self.visible = bool(visible)
        self.enabled = bool(enabled)
        try:
            self.z_index = int(z_index)
        except (TypeError, ValueError):
            raise ErroELiXX(f'Nó "{self.id}": z_index precisa de inteiro.')
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Nó "{self.id}": metadata inválida '
                            "(só JSON finito e raso).")
        self.metadata = meta

    # ----- consultas locais (delegam a Bounds2D; sem duplicar) -----

    @property
    def esquerda(self) -> float:
        return self.bounds.x

    @property
    def direita(self) -> float:
        return self.bounds.direita

    @property
    def topo(self) -> float:
        return self.bounds.y

    @property
    def baixo(self) -> float:
        return self.bounds.base

    @property
    def tamanho(self) -> Size2D:
        return Size2D(self.bounds.largura, self.bounds.altura)

    def centro_local(self) -> Point2D:
        c = self.bounds.centro()
        return Point2D(c.x, c.y)

    def contem_ponto(self, ponto: Vector2) -> bool:
        return self.bounds.contem_ponto(ponto)

    def intersecta(self, outro: Bounds2D) -> bool:
        return self.bounds.intersecta(outro)

    def sobrepoe(self, outro: Bounds2D) -> bool:
        return self.bounds.sobrepoe(outro)

    def toca(self, outro: Bounds2D) -> bool:
        return self.bounds.toca(outro)

    def distancia_para(self, outro: Bounds2D) -> float:
        """Distância entre centros (mesma regra documentada do World)."""
        return self.bounds.distancia_para(outro)

    def expandido(self, valor: float) -> Bounds2D:
        return self.bounds.expandir(valor)

    def transladado(self, dx: float = 0.0, dy: float = 0.0) -> Bounds2D:
        return bounds_transladado(self.bounds, dx, dy)

    # ----- serialização -----

    def to_dict(self) -> dict:
        dados = {"id": self.id,
                 "bounds": {"x": self.bounds.x, "y": self.bounds.y,
                            "largura": self.bounds.largura,
                            "altura": self.bounds.altura},
                 "parent_id": self.parent_id,
                 "visible": self.visible, "enabled": self.enabled,
                 "z_index": self.z_index,
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX(f'Nó "{self.id}" não serializável.')
        return dados

    @staticmethod
    def from_dict(dados: dict) -> GeometryNode:
        if not isinstance(dados, dict):
            raise ErroELiXX("GeometryNode precisa de dicionário.")
        b = dados.get("bounds") or {}
        if not isinstance(b, dict):
            raise ErroELiXX("Bounds do nó precisa de dicionário.")
        return GeometryNode(
            dados.get("id", ""),
            Bounds2D(b.get("x", 0.0), b.get("y", 0.0),
                     b.get("largura", 0.0), b.get("altura", 0.0)),
            parent_id=dados.get("parent_id"),
            visible=dados.get("visible", True),
            enabled=dados.get("enabled", True),
            z_index=dados.get("z_index", 0),
            metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"GeometryNode({self.id} {self.bounds})"


# ----- GeometryRegion -----

class GeometryRegion:
    """Região espacial (área nomeada para consultas). Só dados."""

    def __init__(self, reg_id: str, bounds: Bounds2D | None = None,
                 parent_id: str | None = None, tipo: str = "area",
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(reg_id, "id da região")
        if bounds is None:
            bounds = Bounds2D(0.0, 0.0, 0.0, 0.0)
        if not isinstance(bounds, Bounds2D):
            raise ErroELiXX(f'Região "{self.id}": bounds precisa de '
                            "Bounds2D.")
        for campo in ("x", "y", "largura", "altura"):
            _finito(getattr(bounds, campo), f"{campo} da região {self.id}")
        self.bounds = bounds
        self.parent_id = (str(parent_id).strip()
                          if parent_id is not None else None)
        if self.parent_id == "":
            self.parent_id = None
        self.tipo = str(tipo).strip() or "area"
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Região "{self.id}": metadata inválida.')
        self.metadata = meta

    def centro(self) -> Point2D:
        c = self.bounds.centro()
        return Point2D(c.x, c.y)

    def contem_ponto(self, ponto: Vector2) -> bool:
        return self.bounds.contem_ponto(ponto)

    def to_dict(self) -> dict:
        return {"id": self.id,
                "bounds": {"x": self.bounds.x, "y": self.bounds.y,
                           "largura": self.bounds.largura,
                           "altura": self.bounds.altura},
                "parent_id": self.parent_id, "tipo": self.tipo,
                "metadata": dict(self.metadata)}

    @staticmethod
    def from_dict(dados: dict) -> GeometryRegion:
        if not isinstance(dados, dict):
            raise ErroELiXX("GeometryRegion precisa de dicionário.")
        b = dados.get("bounds") or {}
        if not isinstance(b, dict):
            raise ErroELiXX("Bounds da região precisa de dicionário.")
        return GeometryRegion(
            dados.get("id", ""),
            Bounds2D(b.get("x", 0.0), b.get("y", 0.0),
                     b.get("largura", 0.0), b.get("altura", 0.0)),
            parent_id=dados.get("parent_id"),
            tipo=dados.get("tipo", "area"),
            metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"GeometryRegion({self.tipo} {self.id})"


# ----- GeometryMap -----

class GeometryMap:
    """Armazém determinístico de GeometryNode/GeometryRegion.

    Ordem de inserção preservada; listagens públicas saem ordenadas
    por (z_index, ordem de inserção) ou por id — sempre documentado
    e sempre igual para a mesma sequência de operações.
    """

    def __init__(self, nome: str = "mapa") -> None:
        self.nome = str(nome or "mapa")
        self._nos: dict[str, GeometryNode] = {}
        self._ordem: list[str] = []
        self._regioes: dict[str, GeometryRegion] = {}

    def __len__(self) -> int:
        return len(self._nos)

    def __contains__(self, node_id: str) -> bool:
        return str(node_id) in self._nos

    # ----- CRUD -----

    def adicionar(self, no: GeometryNode) -> GeometryNode:
        if not isinstance(no, GeometryNode):
            raise ErroELiXX("adicionar espera GeometryNode.")
        if no.id in self._nos:
            raise ErroELiXX(f'Nó "{no.id}" duplicado no mapa '
                            f'"{self.nome}".')
        if len(self._nos) >= MAX_NOS_GEOMETRIA:
            raise ErroELiXX(f'Mapa "{self.nome}" além de '
                            f"{MAX_NOS_GEOMETRIA} nós.")
        if no.parent_id is not None and no.parent_id not in self._nos:
            raise ErroELiXX(f'Nó "{no.id}": pai "{no.parent_id}" '
                            "ausente no mapa.")
        self._nos[no.id] = no
        self._ordem.append(no.id)
        erro = self._ciclo(no.id)
        if erro is not None:
            del self._nos[no.id]
            self._ordem.remove(no.id)
            raise ErroELiXX(erro)
        return no

    def atualizar(self, node_id: str, bounds: Bounds2D | None = None,
                  parent_id: str | None = None, _remover_pai: bool = False,
                  visible: bool | None = None,
                  enabled: bool | None = None,
                  z_index: int | None = None,
                  metadata: dict | None = None) -> GeometryNode:
        no = self.obter(node_id)
        if bounds is not None:
            if not isinstance(bounds, Bounds2D):
                raise ErroELiXX("bounds precisa de Bounds2D.")
            for campo in ("x", "y", "largura", "altura"):
                _finito(getattr(bounds, campo), f"{campo} do nó {no.id}")
            no.bounds = bounds
        if _remover_pai:
            no.parent_id = None
        elif parent_id is not None:
            pai = str(parent_id).strip() or None
            if pai == no.id:
                raise ErroELiXX(f'Nó "{no.id}": pai de si mesmo.')
            if pai is not None and pai not in self._nos:
                raise ErroELiXX(f'Nó "{no.id}": pai "{pai}" ausente.')
            antigo = no.parent_id
            no.parent_id = pai
            erro = self._ciclo(no.id)
            if erro is not None:
                no.parent_id = antigo
                raise ErroELiXX(erro)
        if visible is not None:
            no.visible = bool(visible)
        if enabled is not None:
            no.enabled = bool(enabled)
        if z_index is not None:
            try:
                no.z_index = int(z_index)
            except (TypeError, ValueError):
                raise ErroELiXX(f'Nó "{no.id}": z_index inteiro.')
        if metadata is not None:
            meta = dict(metadata)
            if not _e_dado(meta):
                raise ErroELiXX(f'Nó "{no.id}": metadata inválida.')
            no.metadata = meta
        return no

    def remover(self, node_id: str) -> GeometryNode:
        no = self.obter(node_id)
        filhos = self.filhos(node_id)
        if filhos:
            raise ErroELiXX(
                f'Nó "{node_id}" tem {len(filhos)} filho(s) '
                "([{}]); remova-os antes.".format(
                    ", ".join(sorted(f.id for f in filhos))))
        del self._nos[no.id]
        self._ordem.remove(no.id)
        return no

    def obter(self, node_id: str) -> GeometryNode:
        try:
            return self._nos[str(node_id)]
        except KeyError:
            raise ErroELiXX(f'Nó "{node_id}" não existe no mapa '
                            f'"{self.nome}".')

    por_id = obter

    def listar(self) -> list[GeometryNode]:
        """Todos os nós em ordem de inserção (determinística)."""
        return [self._nos[nid] for nid in self._ordem]

    def listar_por_id(self) -> list[GeometryNode]:
        return [self._nos[nid] for nid in _ordenado(self._nos)]

    def ordenar_z(self) -> list[GeometryNode]:
        """Ordem visual: (z_index, inserção). Sem compositor."""
        pos = {nid: i for i, nid in enumerate(self._ordem)}
        return sorted(self._nos.values(),
                      key=lambda n: (n.z_index, pos[n.id]))

    # ----- hierarquia -----

    def filhos(self, node_id: str) -> list[GeometryNode]:
        self.obter(node_id)
        return [self._nos[nid] for nid in self._ordem
                if self._nos[nid].parent_id == str(node_id)]

    def ancestrais(self, node_id: str) -> list[GeometryNode]:
        atual = self.obter(node_id)
        saida: list[GeometryNode] = []
        vistos = {atual.id}
        while atual.parent_id is not None:
            pai = self.obter(atual.parent_id)
            if pai.id in vistos:
                raise ErroELiXX(f'Ciclo envolvendo "{pai.id}".')
            vistos.add(pai.id)
            saida.append(pai)
            atual = pai
        return saida

    def descendentes(self, node_id: str) -> list[GeometryNode]:
        self.obter(node_id)
        saida: list[GeometryNode] = []
        for filho in self.filhos(node_id):
            saida.append(filho)
            saida.extend(self.descendentes(filho.id))
        return saida

    def _ciclo(self, inicio: str) -> str | None:
        vistos = set()
        atual: str | None = inicio
        while atual is not None:
            if atual in vistos:
                return (f'Ciclo na hierarquia envolvendo "{atual}" '
                        "(A→B→C→A recusado).")
            vistos.add(atual)
            no = self._nos.get(atual)
            if no is None:
                return None
            atual = no.parent_id
            if len(vistos) > MAX_PROFUNDIDADE_GEO + 4:
                return (f'Hierarquia além de {MAX_PROFUNDIDADE_GEO} '
                        "níveis (recursão perigosa).")
        return None

    # ----- coordenadas local ↔ global -----
    #
    # bounds é LOCAL ao pai (origem do pai + offset do filho).
    # global = soma das origens até a raiz. Sem rotação/escala aqui:
    # Transform (F10) continua dono de movimento/ângulo; a geometria
    # soma translações (documentado como limitação honesta).

    def bounds_global(self, node_id: str) -> Bounds2D:
        no = self.obter(node_id)
        x, y = no.bounds.x, no.bounds.y
        for ancestral in self.ancestrais(node_id):
            x += ancestral.bounds.x
            y += ancestral.bounds.y
        return Bounds2D(_finito(x, f"x global de {node_id}"),
                        _finito(y, f"y global de {node_id}"),
                        no.bounds.largura, no.bounds.altura)

    def centro_global(self, node_id: str) -> Point2D:
        c = self.bounds_global(node_id).centro()
        return Point2D(c.x, c.y)

    def local_para_global(self, node_id: str,
                          ponto: Vector2) -> Point2D:
        g = self.bounds_global(node_id)
        return Point2D(_finito(g.x + float(ponto.x), "x global"),
                       _finito(g.y + float(ponto.y), "y global"))

    def global_para_local(self, node_id: str,
                          ponto: Vector2) -> Point2D:
        g = self.bounds_global(node_id)
        return Point2D(_finito(float(ponto.x) - g.x, "x local"),
                       _finito(float(ponto.y) - g.y, "y local"))

    # ----- relações (fatos; sem intenção) -----

    def relacao(self, id_a: str, id_b: str) -> dict:
        """Fatos geométricos entre A e B (globais)."""
        if str(id_a) == str(id_b):
            raise ErroELiXX("Relação precisa de dois nós distintos.")
        ga = self.bounds_global(id_a)
        gb = self.bounds_global(id_b)
        ca, cb = ga.centro(), gb.centro()
        dist = ca.distancia(cb)
        return {
            "de": str(id_a), "para": str(id_b),
            "acima": gb.y > ga.base or (cb.y < ca.y and not ga.sobrepoe(gb)),
            "abaixo": ga.y > gb.base or (cb.y > ca.y and not ga.sobrepoe(gb)),
            "esquerda": gb.x >= ga.direita or
                        (cb.x < ca.x and not ga.sobrepoe(gb)),
            "direita": ga.x >= gb.direita or
                       (cb.x > ca.x and not ga.sobrepoe(gb)),
            "dentro": gb.contem(ga),
            "contem": ga.contem(gb),
            "sobrepoe": ga.sobrepoe(gb),
            "toca": ga.toca(gb),
            "distancia": dist,
            "direcao": direcao_entre(ca, cb),
        }

    def acima_de(self, node_id: str) -> list[str]:
        return _ordenado(n.id for n in self.listar()
                         if n.id != node_id and self.relacao(
                             node_id, n.id)["acima"])

    def abaixo_de(self, node_id: str) -> list[str]:
        return _ordenado(n.id for n in self.listar()
                         if n.id != node_id and self.relacao(
                             node_id, n.id)["abaixo"])

    def a_esquerda_de(self, node_id: str) -> list[str]:
        return _ordenado(n.id for n in self.listar()
                         if n.id != node_id and self.relacao(
                             node_id, n.id)["esquerda"])

    def a_direita_de(self, node_id: str) -> list[str]:
        return _ordenado(n.id for n in self.listar()
                         if n.id != node_id and self.relacao(
                             node_id, n.id)["direita"])

    # ----- regiões -----

    def adicionar_regiao(self, regiao: GeometryRegion) -> GeometryRegion:
        if not isinstance(regiao, GeometryRegion):
            raise ErroELiXX("adicionar_regiao espera GeometryRegion.")
        if regiao.id in self._regioes:
            raise ErroELiXX(f'Região "{regiao.id}" duplicada.')
        self._regioes[regiao.id] = regiao
        return regiao

    def regiao(self, reg_id: str) -> GeometryRegion:
        try:
            return self._regioes[str(reg_id)]
        except KeyError:
            raise ErroELiXX(f'Região "{reg_id}" não existe.')

    def listar_regioes(self) -> list[GeometryRegion]:
        return [self._regioes[rid] for rid in _ordenado(self._regioes)]

    def entidades_na_regiao(self, reg_id: str) -> list[GeometryNode]:
        reg = self.regiao(reg_id)
        return [n for n in self.listar_por_id()
                if reg.bounds.contem(self.bounds_global(n.id))]

    def regioes_sobrepostas(self, reg_id: str) -> list[GeometryRegion]:
        reg = self.regiao(reg_id)
        return [r for r in self.listar_regioes()
                if r.id != reg.id and reg.bounds.sobrepoe(r.bounds)]

    def regioes_com_ponto(self, ponto: Vector2) -> list[GeometryRegion]:
        return [r for r in self.listar_regioes()
                if r.bounds.contem_ponto(ponto)]

    # ----- consultas espaciais (determinísticas; sem ranking) -----

    def buscar_por_ponto(self, ponto: Vector2) -> list[GeometryNode]:
        return [n for n in self.listar_por_id()
                if self.bounds_global(n.id).contem_ponto(ponto)]

    def buscar_por_area(self, area: Bounds2D) -> list[GeometryNode]:
        if not isinstance(area, Bounds2D):
            raise ErroELiXX("buscar_por_area espera Bounds2D.")
        return [n for n in self.listar_por_id()
                if area.sobrepoe(self.bounds_global(n.id))
                or area.contem(self.bounds_global(n.id))]

    def buscar_por_regiao(self, reg_id: str) -> list[GeometryNode]:
        return self.entidades_na_regiao(reg_id)

    def buscar_proximos(self, ponto: Vector2,
                        limite: int = 5) -> list[dict]:
        """N nós mais próximos do ponto (centro global; empate por id)."""
        try:
            k = int(limite)
        except (TypeError, ValueError):
            raise ErroELiXX("limite precisa de inteiro.")
        if k < 0:
            raise ErroELiXX("limite precisa de ≥ 0.")
        pares = sorted(
            ((self.centro_global(n.id).distancia(ponto), n.id)
             for n in self.listar()),
            key=lambda p: (p[0], p[1]))
        return [{"id": nid, "distancia": d} for d, nid in pares[:k]]

    def buscar_direcao(self, origem: str,
                       direcao: str) -> list[GeometryNode]:
        if direcao not in DIRECOES:
            raise ErroELiXX(f'Direção inválida: "{direcao}". '
                            f'Válidas: {", ".join(DIRECOES)}.')
        centro_o = self.centro_global(origem)
        saida = []
        for n in self.listar():
            if n.id == origem:
                continue
            if direcao_entre(centro_o, self.centro_global(n.id)) == direcao:
                saida.append(n)
        return sorted(saida, key=lambda n: n.id)

    def buscar_intersecoes(self, area: Bounds2D) -> list[GeometryNode]:
        if not isinstance(area, Bounds2D):
            raise ErroELiXX("buscar_intersecoes espera Bounds2D.")
        return [n for n in self.listar_por_id()
                if self.bounds_global(n.id).intersecta(area)]

    # ----- validação / serialização / snapshot -----

    def validar(self) -> dict:
        for nid in self._ordem:
            no = self._nos[nid]
            if no.parent_id is not None and no.parent_id not in self._nos:
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Nó "{nid}": pai "{no.parent_id}" '
                                  "ausente."}
            erro = self._ciclo(nid)
            if erro is not None:
                return {"valido": False, "codigo": "ciclo",
                        "motivo": erro}
        return {"valido": True, "codigo": "ok",
                "motivo": "Mapa válido."}

    def to_dict(self) -> dict:
        dados = {"nome": self.nome,
                 "nos": [self._nos[nid].to_dict() for nid in self._ordem],
                 "regioes": [self._regioes[rid].to_dict()
                             for rid in _ordenado(self._regioes)]}
        if not _e_dado(dados):
            raise ErroELiXX("Mapa com valores não serializáveis.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> GeometryMap:
        mapa = GeometryMap(dados.get("nome", "mapa") if isinstance(
            dados, dict) else "mapa")
        if not isinstance(dados, dict):
            raise ErroELiXX("Mapa precisa de dicionário.")
        nos_txt = dados.get("nos") or []
        if len(nos_txt) > MAX_NOS_GEOMETRIA:
            raise ErroELiXX(f"Mapa com {len(nos_txt)} nós (teto "
                            f"{MAX_NOS_GEOMETRIA}).")
        pendentes: list[tuple[GeometryNode, str | None]] = []
        for item in nos_txt:
            if not isinstance(item, dict):
                raise ErroELiXX("Nó do mapa precisa de dicionário.")
            pai = item.get("parent_id")
            copia = dict(item)
            copia["parent_id"] = None
            no = GeometryNode.from_dict(copia)
            mapa._nos[no.id] = no
            if no.id in mapa._ordem:
                raise ErroELiXX(f'Nó "{no.id}" duplicado no mapa.')
            mapa._ordem.append(no.id)
            pendentes.append((no, (str(pai).strip() or None)
                              if pai is not None else None))
        for no, pai in pendentes:
            if pai is not None:
                if pai not in mapa._nos:
                    raise ErroELiXX(f'Nó "{no.id}": pai "{pai}" ausente.')
                no.parent_id = pai
        for item in (dados.get("regioes") or []):
            mapa.adicionar_regiao(GeometryRegion.from_dict(item))
        resultado = mapa.validar()
        if not resultado["valido"]:
            raise ErroELiXX(f"Mapa inválido: {resultado['motivo']}")
        return mapa

    @staticmethod
    def from_json(texto: str) -> GeometryMap:
        if not isinstance(texto, str):
            raise ErroELiXX("Mapa JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Mapa JSON inválido: {exc}.")
        return GeometryMap.from_dict(dados)

    def snapshot(self) -> GeometrySnapshot:
        """Foto imutável (alterações posteriores não a afetam)."""
        return GeometrySnapshot(self.to_dict())

    def __repr__(self) -> str:
        return (f"GeometryMap({self.nome}: {len(self)} nós, "
                f"{len(self._regioes)} regiões)")


# ----- GeometrySnapshot (imutável) -----

class GeometrySnapshot:
    """Snapshot imutável: inspeção/debug/testes/contexto futuro."""

    def __init__(self, dados: dict) -> None:
        if not isinstance(dados, dict):
            raise ErroELiXX("Snapshot precisa de dicionário.")
        if not _e_dado(dados):
            raise ErroELiXX("Snapshot com valores inválidos.")
        # Congela via JSON (cópia profunda só de dados).
        self._dados = json.loads(json.dumps(dados, sort_keys=True))
        self._globais: dict[str, dict] = {}
        nos = {n["id"]: n for n in self._dados.get("nos", [])}
        for nid in nos:
            x, y = float(nos[nid]["bounds"]["x"]), float(
                nos[nid]["bounds"]["y"])
            atual = nos[nid].get("parent_id")
            vistos = {nid}
            while atual is not None and atual in nos:
                if atual in vistos:
                    break
                vistos.add(atual)
                x += float(nos[atual]["bounds"]["x"])
                y += float(nos[atual]["bounds"]["y"])
                atual = nos[atual].get("parent_id")
            b = nos[nid]["bounds"]
            self._globais[nid] = {"x": x, "y": y,
                                  "largura": float(b["largura"]),
                                  "altura": float(b["altura"])}

    @property
    def nome(self) -> str:
        return str(self._dados.get("nome", "mapa"))

    def ids(self) -> list[str]:
        return sorted(n["id"] for n in self._dados.get("nos", []))

    def por_id(self, node_id: str) -> dict:
        for n in self._dados.get("nos", []):
            if n["id"] == str(node_id):
                return dict(n)
        raise ErroELiXX(f'Nó "{node_id}" ausente no snapshot.')

    def bounds_global(self, node_id: str) -> dict:
        try:
            return dict(self._globais[str(node_id)])
        except KeyError:
            raise ErroELiXX(f'Nó "{node_id}" ausente no snapshot.')

    def regioes(self) -> list[dict]:
        return [dict(r) for r in self._dados.get("regioes", [])]

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self._dados, sort_keys=True))

    def __repr__(self) -> str:
        return f"GeometrySnapshot({self.nome}: {len(self.ids())} nós)"


# ----- parser seguro de mapa explícito -----

def parsear_mapa_explicito(dados: dict,
                           nome: str = "explicito") -> GeometryMap:
    """Dict externo {id: {x, y, largura, altura, ...}} → GeometryMap.

    Aceita só números finitos (≤ ±1e9), strings, booleanos e
    estruturas rasas. Rejeita NaN/Infinity/gigantes/recursão/código.
    Chaves extras desconhecidas por nó geram aviso? Não: são
    recusadas com erro claro (contrato explícito).
    """
    if not isinstance(dados, dict):
        raise ErroELiXX("Mapa explícito precisa de dicionário.")
    mapa = GeometryMap(nome)
    for nid, bruto in dados.items():
        nid_txt = _id_valido(nid, "id do mapa explícito")
        if not isinstance(bruto, dict):
            raise ErroELiXX(f'Entrada "{nid_txt}": precisa de dicionário '
                            "com x/y/largura/altura.")
        permitidas = {"x", "y", "largura", "altura", "parent_id",
                      "visible", "enabled", "z_index", "metadata"}
        for chave in bruto:
            if chave not in permitidas:
                raise ErroELiXX(f'Entrada "{nid_txt}": chave "{chave}" '
                                "desconhecida (contrato: x, y, largura, "
                                "altura, parent_id, visible, enabled, "
                                "z_index, metadata).")
        if not _e_dado(bruto):
            raise ErroELiXX(f'Entrada "{nid_txt}": valores inválidos '
                            "(NaN/Infinity/gigante/recursão recusados).")
        meta = bruto.get("metadata") or {}
        if not isinstance(meta, dict):
            raise ErroELiXX(f'Entrada "{nid_txt}": metadata precisa de '
                            "dicionário.")
        pai = bruto.get("parent_id")
        mapa.adicionar(GeometryNode(
            nid_txt,
            Bounds2D(_finito(bruto.get("x", 0.0), f"x de {nid_txt}"),
                     _finito(bruto.get("y", 0.0), f"y de {nid_txt}"),
                     _finito(bruto.get("largura", 0.0),
                             f"largura de {nid_txt}"),
                     _finito(bruto.get("altura", 0.0),
                             f"altura de {nid_txt}")),
            parent_id=(str(pai).strip() or None)
            if pai is not None else None,
            visible=bruto.get("visible", True),
            enabled=bruto.get("enabled", True),
            z_index=bruto.get("z_index", 0),
            metadata=dict(meta)))
    return mapa


geometry_map_de_dict = parsear_mapa_explicito


# ----- Environment → Geometry (só explícita; nunca inventada) -----

def environment_para_geometria(environment, geometria: dict | None = None,
                               nome: str = "derivado") -> tuple:
    """Environment + mapa explícito → (GeometryMap, ausentes).

    Regras honestas: entra no mapa quem tem geometria REAL
    (`tem_geometria()` — largura>0 e altura>0) OU entrada no mapa
    explícito (que vence). Quem não tem nenhum dos dois vai para
    `ausentes` (lista de ids) — sem posição falsa, sem tamanho
    assumido, sem ordem DOM como coordenada, sem layout fictício.
    A F20 NÃO depende daqui (integração opcional, sem ciclo).
    """
    from .ambiente import Environment

    if not isinstance(environment, Environment):
        raise ErroELiXX("environment_para_geometria espera Environment.")
    explicito = dict(geometria or {})
    mapa = GeometryMap(nome)
    ausentes: list[str] = []
    for nid in list(environment._ordem):
        no = environment._nos[nid]
        if nid in explicito:
            bruto = explicito[nid]
            if not isinstance(bruto, dict):
                raise ErroELiXX(f'Geometria de "{nid}": dicionário.')
            if not _e_dado(bruto):
                raise ErroELiXX(f'Geometria de "{nid}": valores '
                                "inválidos.")
            mapa.adicionar(GeometryNode(
                nid,
                Bounds2D(_finito(bruto.get("x", 0.0), f"x de {nid}"),
                         _finito(bruto.get("y", 0.0), f"y de {nid}"),
                         _finito(bruto.get("largura", 0.0),
                                 f"largura de {nid}"),
                         _finito(bruto.get("altura", 0.0),
                                 f"altura de {nid}")),
                parent_id=(no.parent.id if no.parent is not None
                           else None),
                visible=no.visivel, enabled=no.habilitado,
                metadata={"env_tipo": no.tipo,
                          "fonte": "explicita"}))
        elif no.tem_geometria():
            mapa.adicionar(GeometryNode(
                nid, Bounds2D(no.x, no.y, no.largura, no.altura),
                parent_id=(no.parent.id if no.parent is not None
                           else None),
                visible=no.visivel, enabled=no.habilitado,
                metadata={"env_tipo": no.tipo, "fonte": "environment"}))
        else:
            ausentes.append(nid)
    for rid in sorted(environment._regioes):
        reg = environment._regioes[rid]
        membros = [environment._nos[n].bounds()
                   for n in reg.nos if n in environment._nos
                   and environment._nos[n].tem_geometria()]
        if not membros:
            continue  # região sem geometria real: ausente, sem inventar
        uniao = membros[0]
        for outro in membros[1:]:
            uniao = uniao.uniao(outro)
        mapa.adicionar_regiao(GeometryRegion(
            rid, uniao, tipo="area",
            metadata={"env_regiao": rid, "membros": sorted(reg.nos)}))
    return mapa, _ordenado(ausentes)


# ----- Geometry → World (opcional; sem duplicar entidades) -----

def geometria_para_world(mapa: GeometryMap,
                         nome: str = "geometria") -> object:
    """GeometryMap → World novo (uma entidade por nó visível).

    Entidades: tipo "objeto" (regiões viram "area"), categoria
    "geometria", props {geo_id, parent_id}. Base = bounds global.
    """
    from .mundo import Bounds2D as _B, World, WorldEntity

    if not isinstance(mapa, GeometryMap):
        raise ErroELiXX("geometria_para_world espera GeometryMap.")
    mundo = World(nome, cena=None)
    for no in mapa.listar():
        if not no.visible:
            continue
        g = mapa.bounds_global(no.id)
        entidade = WorldEntity(no.id, "objeto", mundo,
                               base=_B(g.x, g.y, g.largura, g.altura),
                               categoria="geometria", tags=(),
                               props={"geo_id": no.id,
                                      "parent_id": no.parent_id})
        entidade.tamanho_explicito = True
        mundo.adicionar(entidade)
    for reg in mapa.listar_regioes():
        if reg.id in [e for e in getattr(mundo, "_ordem", [])]:
            continue
        entidade = WorldEntity(reg.id, "area", mundo,
                               base=_B(reg.bounds.x, reg.bounds.y,
                                       reg.bounds.largura,
                                       reg.bounds.altura),
                               categoria="regiao_geometrica", tags=(),
                               props={"geo_regiao": reg.id})
        entidade.tamanho_explicito = True
        mundo.adicionar(entidade)
    return mundo


def vincular_geometria_world(mundo, mapa: GeometryMap) -> dict:
    """Atualiza entidades existentes com a base global do mapa.

    World continua fonte semântica; a geometria só preenche o
    espacial. Retorna {"atualizadas": [...], "ausentes": [...]} —
    nunca cria nem remove entidades (sem duplicar).
    """
    from .mundo import Bounds2D as _B

    if not isinstance(mapa, GeometryMap):
        raise ErroELiXX("vincular_geometria_world espera GeometryMap.")
    atualizadas, ausentes = [], []
    ordem = list(getattr(mundo, "_ordem", []))
    entidades = getattr(mundo, "_entidades", {})
    for nome_ent in ordem:
        if nome_ent in mapa:
            g = mapa.bounds_global(nome_ent)
            entidades[nome_ent].base = _B(g.x, g.y, g.largura, g.altura)
            atualizadas.append(nome_ent)
        else:
            ausentes.append(nome_ent)
    return {"atualizadas": _ordenado(atualizadas),
            "ausentes": _ordenado(ausentes)}


# ----- debug -----

def debug_geometria(mapa_ou_snapshot) -> str:
    """Texto legível: ids, posição, tamanho, centro, pai, z, vis."""
    if isinstance(mapa_ou_snapshot, GeometrySnapshot):
        snap = mapa_ou_snapshot
        linhas = [f"GeometrySnapshot {snap.nome}: "
                   f"{len(snap.ids())} nós"]
        for nid in snap.ids():
            g = snap.bounds_global(nid)
            linhas.append(
                f"  {nid}: pos=({g['x']:g},{g['y']:g}) "
                f"tam={g['largura']:g}x{g['altura']:g} "
                f"centro=({g['x'] + g['largura'] / 2:g},"
                f"{g['y'] + g['altura'] / 2:g})")
        return "\n".join(linhas)
    mapa = mapa_ou_snapshot
    linhas = [f"GeometryMap {mapa.nome}: {len(mapa)} nós, "
               f"{len(mapa._regioes)} regiões"]
    linhas.append("NOS (ordem z):")
    for no in mapa.ordenar_z():
        g = mapa.bounds_global(no.id)
        linhas.append(
            f"  {no.id}: pos=({g.x:g},{g.y:g}) "
            f"tam={g.largura:g}x{g.altura:g} "
            f"centro=({g.x + g.largura / 2:g},{g.y + g.altura / 2:g}) "
            f"pai={no.parent_id} z={no.z_index} "
            f"vis={no.visible} hab={no.enabled}")
    if mapa._regioes:
        linhas.append("REGIOES:")
        for reg in mapa.listar_regioes():
            linhas.append(
                f"  {reg.id} ({reg.tipo}): "
                f"pos=({reg.bounds.x:g},{reg.bounds.y:g}) "
                f"tam={reg.bounds.largura:g}x{reg.bounds.altura:g}")
    return "\n".join(linhas)
