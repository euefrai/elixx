"""Navigation + Traversal da ELiXX (Fase 15).

Sabe POR ONDE é possível passar. Não decide, não executa, sem física,
sem IA. Camada derivada do World (sem duplicar entidades/posições):

    World ──→ NavigationGraph ──→ Path/TraversalPlan (descrições)

Posições sempre ao vivo (Motion reflete na hora). Pathfinding:
Dijkstra determinístico (custo explícito ou distância geométrica).
Sem threads, sem dependências, stdlib.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from ..erros import ErroELiXX
from .transform import Vector2

__all__ = [
    "LADOS_BORDA", "TIPOS_SUPERFICIE",
    "NavigationNode", "NavigationEdge", "NavigationSurface",
    "NavigationGraph", "Path", "TraversalPlan", "NavigationBuilder",
    "vincular_navegacao",
    "acessivel", "rota", "rotas_alternativas", "plano_travessia",
    "debug_navegacao",
]

LADOS_BORDA = ("esquerda", "direita", "topo", "base")
"""Lados com borda derivada; id `<ent>_borda_<lado>`."""

TIPOS_SUPERFICIE = ("chao", "plataforma", "parede")
"""Entidades que viram superfície (parede: não navegável, informativa)."""


def id_borda(entidade: str, lado: str) -> str:
    """Id determinístico de borda (igual ao da semântica)."""
    if lado not in LADOS_BORDA:
        raise ErroELiXX(
            f'Lado de borda inválido: "{lado}". '
            f'Válidos: {", ".join(LADOS_BORDA)}.')
    return f"{entidade}_borda_{lado}"


def entidade_de_borda(no_id: str) -> str | None:
    """Entidade dona da borda (ou None se não for borda)."""
    for lado in LADOS_BORDA:
        sufixo = f"_borda_{lado}"
        if no_id.endswith(sufixo):
            return no_id[: -len(sufixo)]
    return None


# ----- Node -----

class NavigationNode:
    """Nó com identidade estável; posição derivada do World (ao vivo)."""

    def __init__(self, node_id: str, kind: str, mundo,
                 entidade: str | None = None, lado: str | None = None,
                 tags=(), metadados=None) -> None:
        if kind not in ("entidade", "borda", "superficie"):
            raise ErroELiXX(
                f'Tipo de nó inválido: "{kind}". '
                'Válidos: entidade, borda, superficie.')
        self.id = node_id
        self.kind = kind
        self.mundo = mundo
        self.entidade = entidade  # nome da entidade (ou None)
        self.lado = lado  # lado da borda (ou None)
        self.tags = tuple(tags)
        self.metadados = dict(metadados or {})

    def posicao(self) -> Vector2:
        """Posição atual (entidade ao vivo; borda do bounds ao vivo)."""
        if self.kind == "borda":
            return self.mundo._posicao_borda(self.entidade, self.lado)
        if self.entidade is not None:
            return self.mundo.por_id(self.entidade).posicao_global()
        return Vector2(0.0, 0.0)

    def __repr__(self) -> str:
        return f"NavigationNode({self.kind} {self.id})"


# ----- Edge -----

class NavigationEdge:
    """Conexão navegável: modo descritor + requisitos + custo."""

    def __init__(self, origem: str, destino: str, modo: str = "andar",
                 custo: float | None = None, requer: str | None = None,
                 bloqueado: bool = False, tags=(), metadados=None,
                 linha: int = 0) -> None:
        if not modo or not str(modo).strip():
            raise ErroELiXX("Edge precisa de modo não vazio.",
                            exemplo="modo: andar")
        if custo is not None and (not math.isfinite(float(custo))
                                  or float(custo) < 0):
            raise ErroELiXX(f"Custo inválido no edge: {custo!r}. Use ≥ 0.")
        self.origem = origem
        self.destino = destino
        self.modo = str(modo)
        self.custo = None if custo is None else float(custo)
        self.requer = requer
        self.bloqueado = bool(bloqueado)
        self.tags = tuple(tags)
        self.metadados = dict(metadados or {})
        self.linha = linha

    @property
    def id(self) -> str:
        return f"{self.origem}>{self.destino}:{self.modo}"

    def distancia(self, grafo) -> float:
        """Distância geométrica atual entre pontas (Vector2)."""
        a = grafo.nos[self.origem].posicao()
        b = grafo.nos[self.destino].posicao()
        return a.distancia(b)

    def custo_efetivo(self, grafo) -> float:
        """Explícito ou distância (sem arbitrar melhor modo)."""
        if self.custo is not None:
            return self.custo
        return self.distancia(grafo)

    def bloqueio_geometrico(self, grafo, obstaculos=None) -> str | None:
        """Nome do obstáculo/parede cruzado (ou None).

        Geometria simples e determinística (sem física): o segmento
        cruza bounds de obstáculo/parede, ignorando as entidades das
        pontas. Calculado ao vivo (entidades móveis valem na hora).
        `obstaculos` = lista pré-computada [(nome, bounds)] (uma por
        consulta; evita revarrer o mundo por edge).
        """
        mundo = grafo.mundo
        a = grafo.nos[self.origem].posicao()
        b = grafo.nos[self.destino].posicao()
        pontas = {self.origem, self.destino,
                  entidade_de_borda(self.origem) or "",
                  entidade_de_borda(self.destino) or ""}
        if obstaculos is None:
            obstaculos = _obstaculos(grafo)
        for nome, limites in obstaculos:
            if nome in pontas:
                continue
            if _segmento_cruza(limites, a, b):
                return nome
        return None


def _obstaculos(grafo) -> list:
    """[(nome, bounds ao vivo)] de obstáculo/parede (uma varredura)."""
    mundo = grafo.mundo
    saida = []
    for nome in mundo._ordem:
        entidade = mundo._entidades[nome]
        if entidade.tipo in ("obstaculo", "parede"):
            saida.append((nome, entidade.bounds_global()))
    return saida

    def __repr__(self) -> str:
        return f"NavigationEdge({self.id})"


def _segmento_cruza(bounds, p: Vector2, q: Vector2) -> bool:
    """Segmento pq atravessa o interior do retângulo (Liang-Barsky).

    Tocar a borda não conta (ver Bounds2D.toca); só intervalo interno
    com folga numérica. Y cresce para baixo (mesma matemática).
    """
    dx, dy = q.x - p.x, q.y - p.y
    t0, t1 = 0.0, 1.0
    for p_i, q_i in ((-dx, p.x - bounds.x),
                     (dx, bounds.direita - p.x),
                     (-dy, p.y - bounds.y),
                     (dy, bounds.base - p.y)):
        if p_i == 0.0:
            if q_i < 0.0:
                return False  # paralelo e fora da faixa
            continue
        t = q_i / p_i
        if p_i < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    # Interior com folga (exclui toque de borda e ponto isolado).
    return t1 - t0 > 1e-9 and t1 > 1e-9 and t0 < 1.0 - 1e-9


# ----- Surface -----

class NavigationSurface:
    """Superfície compacta (início/fim/comprimento; sem pixel-nodes)."""

    def __init__(self, sup_id: str, entidade: str, tipo: str,
                 mundo, navegavel: bool = True) -> None:
        self.id = sup_id
        self.entidade = entidade
        self.tipo = tipo
        self.mundo = mundo
        self.navegavel = bool(navegavel)

    def bounds(self):
        return self.mundo.por_id(self.entidade).bounds_global()

    def inicio(self) -> Vector2:
        limites = self.bounds()
        if limites.largura >= limites.altura:
            return Vector2(limites.x, limites.y)
        return Vector2(limites.x, limites.y)

    def fim(self) -> Vector2:
        limites = self.bounds()
        if limites.largura >= limites.altura:
            return Vector2(limites.direita, limites.y)
        return Vector2(limites.x, limites.base)

    def comprimento(self) -> float:
        limites = self.bounds()
        return max(limites.largura, limites.altura)

    def __repr__(self) -> str:
        return f"NavigationSurface({self.tipo} {self.id})"


# ----- Graph -----

class NavigationGraph:
    """Grafo derivado do World (não duplica entidades/posições)."""

    def __init__(self, nome: str, mundo) -> None:
        self.nome = nome
        self.mundo = mundo
        self.nos: dict[str, NavigationNode] = {}
        self.edges: list[NavigationEdge] = []
        self.superficies: dict[str, NavigationSurface] = {}
        self._seq = 0

    def adicionar_no(self, no: NavigationNode) -> NavigationNode:
        """Registra nó (id global único no grafo)."""
        if no.id in self.nos:
            raise ErroELiXX(
                f'Nó "{no.id}" repetido no grafo "{self.nome}".')
        self.nos[no.id] = no
        return no

    def adicionar_edge(self, edge: NavigationEdge) -> NavigationEdge:
        """Registra edge (origem/destino precisam existir)."""
        for ponta in (edge.origem, edge.destino):
            if ponta not in self.nos:
                raise ErroELiXX(
                    f'Edge "{edge.id}": nó "{ponta}" inexistente no grafo '
                    f'"{self.nome}".')
        self.edges.append(edge)
        return edge

    def adicionar_superficie(self, superficie: NavigationSurface
                             ) -> NavigationSurface:
        self.superficies[superficie.id] = superficie
        return superficie

    def saidas(self, no_id: str) -> list[NavigationEdge]:
        """Edges que partem do nó (ordem de registro; determinístico)."""
        return [e for e in self.edges if e.origem == no_id]

    def __len__(self) -> int:
        return len(self.nos)

    def __contains__(self, no_id: str) -> bool:
        return no_id in self.nos


# ----- Path / TraversalPlan -----

@dataclass
class Path:
    """Descrição de percurso (não move personagem)."""

    nos: list = field(default_factory=list)  # ids
    edges: list = field(default_factory=list)  # NavigationEdge
    distancia_total: float = 0.0
    custo_total: float = 0.0
    modos: list = field(default_factory=list)
    requisitos: list = field(default_factory=list)  # capabilities
    acessivel: bool = True

    def etapas(self) -> list[dict]:
        """[{de, para, modo, requisitos}] por edge (para o plano)."""
        saida = []
        for edge in self.edges:
            saida.append({"de": edge.origem, "para": edge.destino,
                          "modo": edge.modo,
                          "requisitos": [edge.requer] if edge.requer
                          else []})
        return saida


@dataclass
class TraversalPlan:
    """Plano descritivo: origem→destino via path (sem executar)."""

    origem: str = ""
    destino: str = ""
    path: Path = field(default_factory=Path)
    etapas: list = field(default_factory=list)
    modos: list = field(default_factory=list)
    capacidades_necessarias: list = field(default_factory=list)


# ----- acessibilidade (F14 reutilizada; sem duplicar registry) -----

def acessivel(holder, edge: NavigationEdge, mundo=None) -> dict:
    """Edge acessível? {permitido, motivo, requisitos} (estruturado)."""
    if edge.bloqueado:
        return {"permitido": False, "edge": edge.id,
                "motivo": f'Edge "{edge.id}" bloqueado.',
                "requisitos": []}
    if edge.requer is None:
        return {"permitido": True, "edge": edge.id,
                "motivo": f'Edge "{edge.id}" livre.',
                "requisitos": []}
    if holder is None:
        return {"permitido": True, "edge": edge.id,
                "motivo": f'Edge "{edge.id}" requer "{edge.requer}" '
                          "(sem dono para filtrar).",
                "requisitos": [{"tipo": "capacidade", "alvo": edge.requer,
                                "ok": None,
                                "detalhe": f'requer "{edge.requer}"'}]}
    from .capacidades import tem_capacidade

    ok = tem_capacidade(holder, edge.requer)
    if ok:
        return {"permitido": True, "edge": edge.id,
                "motivo": f'{holder.nome} tem "{edge.requer}".',
                "requisitos": [{"tipo": "capacidade", "alvo": edge.requer,
                                "ok": True,
                                "detalhe": f'tem "{edge.requer}"'}]}
    return {"permitido": False, "edge": edge.id,
            "motivo": f'Capacidade "{edge.requer}" ausente em '
                      f"{holder.nome}.",
            "requisitos": [{"tipo": "capacidade", "alvo": edge.requer,
                            "ok": False,
                            "detalhe": f'capacidade "{edge.requer}" '
                                       "ausente"}]}


# ----- pathfinding (Dijkstra determinístico; sem threads/deps) -----

def _dijkstra(grafo: NavigationGraph, origem: str, destino: str,
              bloqueados: frozenset | None = None,
              filtro=None) -> tuple[list | None, dict]:
    """Menor custo; desempate por inserção (determinístico)."""
    bloqueados = bloqueados or frozenset()
    if origem not in grafo.nos or destino not in grafo.nos:
        return None, {}
    anterior: dict[str, tuple] = {}  # no -> (pai, edge)
    melhor: dict[str, float] = {origem: 0.0}
    pilha: list = [(0.0, 0, origem)]
    seq = 1
    visitados: set[str] = set()
    while pilha:
        custo, _ordem, atual = heapq.heappop(pilha)
        if atual in visitados:
            continue
        visitados.add(atual)
        if atual == destino:
            break
        for edge in grafo.saidas(atual):
            if edge.id in bloqueados:
                continue
            if filtro is not None and not filtro(edge):
                continue
            proximo = edge.destino
            novo = custo + edge.custo_efetivo(grafo)
            if novo < melhor.get(proximo, math.inf):
                melhor[proximo] = novo
                anterior[proximo] = (atual, edge)
                heapq.heappush(pilha, (novo, seq, proximo))
                seq += 1
    if origem == destino:
        return [origem], {}
    if destino not in anterior:
        return None, {}
    nos, edges = [destino], []
    atual = destino
    while atual != origem:
        pai, edge = anterior[atual]
        nos.append(pai)
        edges.append(edge)
        atual = pai
    nos.reverse()
    edges.reverse()
    return nos, anterior


def _montar_path(grafo: NavigationGraph, nos: list,
                 holder=None) -> Path:
    edges = []
    for a, b in zip(nos, nos[1:]):
        candidatos = [e for e in grafo.saidas(a) if e.destino == b]
        if not candidatos:
            raise ErroELiXX(f"Sem edge {a!r} -> {b!r} no caminho.")
        edges.append(candidatos[0])
    distancia = sum(e.distancia(grafo) for e in edges)
    custo = sum(e.custo_efetivo(grafo) for e in edges)
    modos: list[str] = []
    for e in edges:
        if e.modo not in modos:
            modos.append(e.modo)
    requisitos: list[str] = []
    for e in edges:
        if e.requer is not None and e.requer not in requisitos:
            requisitos.append(e.requer)
    return Path(nos=list(nos), edges=edges, distancia_total=distancia,
                custo_total=custo, modos=modos, requisitos=requisitos)


def _resolver_ponta(grafo: NavigationGraph, ponta) -> str:
    """Entidade/nó → id de nó; Vector2 → nó mais próximo (documentado)."""
    from .transform import Vector2 as _V2

    if isinstance(ponta, _V2):
        melhor, melhor_d = None, math.inf
        for node_id in sorted(grafo.nos):
            distancia = grafo.nos[node_id].posicao().distancia(ponta)
            if distancia < melhor_d:
                melhor, melhor_d = node_id, distancia
        if melhor is None:
            raise ErroELiXX("Grafo vazio: sem nós para resolver posição.")
        return melhor
    texto = str(ponta)
    if texto in grafo.nos:
        return texto
    candidato = f"ent:{texto}"
    if candidato in grafo.nos:
        return candidato
    raise ErroELiXX(
        f'Origem/destino "{texto}" não é nó nem entidade do grafo '
        f'"{grafo.nome}".')


def rota(grafo: NavigationGraph, origem, destino, holder=None,
         mundo=None) -> dict:
    """Melhor caminho (Dijkstra). Estruturado; sem exceção no normal.

    Com holder: filtra edges inacessíveis. Se só existir caminho
    inacessível: encontrado=False + capacidades faltantes.
    """
    mundo = mundo if mundo is not None else grafo.mundo
    no_origem = _resolver_ponta(grafo, origem)
    no_destino = _resolver_ponta(grafo, destino)
    obstaculos = _obstaculos(grafo)  # uma varredura por consulta

    def _livre(edge):
        if edge.bloqueado or edge.bloqueio_geometrico(grafo,
                                                      obstaculos) is not None:
            return False
        if holder is None:
            return True
        return acessivel(holder, edge, mundo)["permitido"]

    nos, _anterior = _dijkstra(grafo, no_origem, no_destino, filtro=_livre)
    if nos is not None:
        caminho = _montar_path(grafo, nos, holder)
        return {"encontrado": True, "motivo": "Caminho encontrado.",
                "nos": caminho.nos,
                "edges": [e.id for e in caminho.edges],
                "distancia_total": caminho.distancia_total,
                "custo_total": caminho.custo_total, "modos": caminho.modos,
                "requisitos": caminho.requisitos, "path": caminho}
    # Sem caminho filtrado: existe algum ignorando acessibilidade?
    nos_livres, _anterior = _dijkstra(
        grafo, no_origem, no_destino,
        filtro=lambda e: (not e.bloqueado
                          and e.bloqueio_geometrico(grafo,
                                                    obstaculos) is None))
    if nos_livres is None:
        return {"encontrado": False,
                "motivo": "Destino inacessível (sem conexão).",
                "nos": [], "edges": [], "distancia_total": 0.0,
                "custo_total": 0.0, "modos": [], "requisitos": [],
                "capacidades": [], "path": None}
    caminho = _montar_path(grafo, nos_livres, holder)
    faltantes = [c for c in caminho.requisitos
                 if holder is None or not _tem(holder, c)]
    return {"encontrado": False,
            "motivo": "Capacidade necessária ausente.",
            "nos": caminho.nos, "edges": [e.id for e in caminho.edges],
            "distancia_total": caminho.distancia_total,
            "custo_total": caminho.custo_total, "modos": caminho.modos,
            "requisitos": caminho.requisitos, "capacidades": faltantes,
            "path": caminho}


def _tem(holder, capacidade: str) -> bool:
    from .capacidades import tem_capacidade

    return tem_capacidade(holder, capacidade)


def rotas_alternativas(grafo: NavigationGraph, origem, destino, k: int = 2,
                       holder=None, mundo=None) -> list[dict]:
    """Até k rotas (melhor + variantes bloqueando 1 edge; determinístico)."""
    if k < 1:
        raise ErroELiXX(f"k inválido em rotas: {k!r}. Use ≥ 1.")
    primeira = rota(grafo, origem, destino, holder, mundo)
    if not primeira["encontrado"]:
        return [primeira]
    saida = [primeira]
    vistos = {tuple(primeira["nos"])}
    for edge_id in primeira["edges"]:
        if len(saida) >= k:
            break
        no_origem = _resolver_ponta(grafo, origem)
        no_destino = _resolver_ponta(grafo, destino)
        mundo_ref = mundo if mundo is not None else grafo.mundo
        obstaculos = _obstaculos(grafo)

        def _livre(edge, _bloq=edge_id, _obst=obstaculos):
            if edge.id == _bloq or edge.bloqueado:
                return False
            if edge.bloqueio_geometrico(grafo, _obst) is not None:
                return False
            if holder is None:
                return True
            return acessivel(holder, edge, mundo_ref)["permitido"]

        nos, _anterior = _dijkstra(grafo, no_origem, no_destino,
                                   filtro=_livre)
        if nos is None or tuple(nos) in vistos:
            continue
        vistos.add(tuple(nos))
        caminho = _montar_path(grafo, nos, holder)
        saida.append({"encontrado": True, "motivo": "Rota alternativa.",
                      "nos": caminho.nos,
                      "edges": [e.id for e in caminho.edges],
                      "distancia_total": caminho.distancia_total,
                      "custo_total": caminho.custo_total,
                      "modos": caminho.modos,
                      "requisitos": caminho.requisitos, "path": caminho})
    return saida


def plano_travessia(grafo: NavigationGraph, origem, destino, holder=None,
                    mundo=None) -> TraversalPlan:
    """Rota → plano descritivo (etapas + capabilities; sem executar)."""
    resultado = rota(grafo, origem, destino, holder, mundo)
    if not resultado["encontrado"] or resultado["path"] is None:
        return TraversalPlan(origem=str(origem), destino=str(destino))
    caminho = resultado["path"]
    return TraversalPlan(
        origem=str(origem), destino=str(destino), path=caminho,
        etapas=caminho.etapas(), modos=list(caminho.modos),
        capacidades_necessarias=list(caminho.requisitos))


# ----- Builder (World → grafo; conservador, sem inventar edges) -----

class NavigationBuilder:
    """Deriva nós/superfícies/bordas do World + edges explícitos."""

    def __init__(self, mundo) -> None:
        self.mundo = mundo

    def construir(self, navegacoes_ast, nome: str | None = None
                  ) -> NavigationGraph:
        """Grafo com nós de TODAS as entidades + edges declarados."""
        mundo = self.mundo
        grafo = NavigationGraph(nome or mundo.nome, mundo)
        for nome in mundo._ordem:
            entidade = mundo._entidades[nome]
            grafo.adicionar_no(NavigationNode(
                f"ent:{nome}", "entidade", mundo, entidade=nome,
                tags=tuple(entidade.tags)))
            if entidade.tipo in TIPOS_SUPERFICIE:
                navegavel = entidade.tipo in ("chao", "plataforma")
                grafo.adicionar_superficie(NavigationSurface(
                    f"sup:{nome}", nome, entidade.tipo, mundo,
                    navegavel=navegavel))
                if entidade.tipo == "plataforma":
                    for lado in ("esquerda", "direita"):
                        node_id = f"{nome}_borda_{lado}"
                        grafo.adicionar_no(NavigationNode(
                            node_id, "borda", mundo, entidade=nome,
                            lado=lado))
                        # Estrutural (não inventado): borda pertence à
                        # superfície; andar entidade↔borda custa a distância.
                        for origem, destino in ((f"ent:{nome}", node_id),
                                                (node_id, f"ent:{nome}")):
                            grafo.adicionar_edge(NavigationEdge(
                                origem, destino, modo="andar"))
        for nav_ast in navegacoes_ast:
            for caminho in nav_ast.caminhos:
                self._adicionar_caminho(grafo, caminho)
        return grafo

    def _adicionar_caminho(self, grafo: NavigationGraph, caminho) -> None:
        props = {p.nome: p for p in caminho.propriedades}
        modo = _descritor(props.get("modo")) or "andar"
        custo = _custo_num(props.get("custo"))
        requer = _descritor(props.get("requer"))
        bloqueado = _booleano(props.get("bloqueado"))
        for ponta in (caminho.origem, caminho.destino):
            node_id = _node_id_de_ref(ponta)
            if node_id not in grafo.nos:
                raise ErroELiXX(
                    f'Caminho "{caminho.origem}" -> "{caminho.destino}": '
                    f'nó "{node_id}" ausente do grafo (entidade fora '
                    "deste mundo?).")
        grafo.adicionar_edge(NavigationEdge(
            _node_id_de_ref(caminho.origem),
            _node_id_de_ref(caminho.destino), modo=modo, custo=custo,
            requer=requer, bloqueado=bloqueado,
            linha=caminho.linha))


def _node_id_de_ref(ref: str) -> str:
    """Nome de entidade → id de nó (borda passa direto)."""
    if ref.startswith("ent:"):
        return ref
    if entidade_de_borda(ref) is not None:
        return ref
    return f"ent:{ref}"


def _descritor(prop) -> str | None:
    if prop is None or not prop.valores:
        return None
    from ..compilador import ast as _A

    valor = prop.valores[0]
    if isinstance(valor, _A.TextoLit):
        return valor.valor.strip() or None
    if isinstance(valor, _A.Ident):
        return valor.nome.strip() or None
    return None


def _custo_num(prop) -> float | None:
    if prop is None or not prop.valores:
        return None
    from ..compilador import ast as _A

    valor = prop.valores[0]
    if isinstance(valor, _A.NumeroLit):
        numero = float(valor.valor)
        if numero >= 0:
            return numero
    return None


def _booleano(prop) -> bool:
    if prop is None or not prop.valores:
        return False
    from ..compilador import ast as _A

    valor = prop.valores[0]
    return bool(valor.valor) if isinstance(valor, _A.Booleano) else False


def vincular_navegacao(cena, programa, mundos: dict) -> dict[str,
                                                            NavigationGraph]:
    """Navegações da janela → grafos sobre o mundo dono (determinístico).

    Cada `navegacao` ancora no primeiro mundo (ordem de declaração) que
    contém TODAS as pontas; caminhos fora dele são ignorados (outro
    mundo pode ter sua própria navegação). Sem mundo: erro claro.
    """
    grafos: dict[str, NavigationGraph] = {}
    mundos_por_janela: dict[str, list] = {}
    for janela_ast in list(programa.janelas) + list(programa.telas):
        for mundo_ast in janela_ast.mundos:
            if mundo_ast.nome in mundos:
                mundos_por_janela.setdefault(janela_ast.nome, []).append(
                    mundos[mundo_ast.nome])
    for janela_ast in list(programa.janelas) + list(programa.telas):
        candidatos = mundos_por_janela.get(janela_ast.nome, [])
        for nav_ast in janela_ast.navegacoes:
            if nav_ast.nome in grafos:
                raise ErroELiXX(
                    f'Navegação "{nav_ast.nome}" repetida no programa.')
            mundo = _mundo_dono(nav_ast, candidatos)
            if mundo is None:
                raise ErroELiXX(
                    f'Navegação "{nav_ast.nome}" sem mundo com suas '
                    "entidades (declare mundo com as entidades).")
            grafos[nav_ast.nome] = NavigationBuilder(mundo).construir(
                [nav_ast], nome=nav_ast.nome)
    return grafos


def _mundo_dono(nav_ast, candidatos: list):
    """Primeiro mundo contendo todas as pontas (determinístico)."""
    pontas = set()
    for caminho in nav_ast.caminhos:
        pontas.add(_node_id_de_ref(caminho.origem))
        pontas.add(_node_id_de_ref(caminho.destino))
    for mundo in candidatos:
        nomes = set()
        for nome in mundo._ordem:
            nomes.add(f"ent:{nome}")
            for lado in LADOS_BORDA:
                nomes.add(f"{nome}_borda_{lado}")
        if pontas <= nomes:
            return mundo
    return None


# ----- debug (textual, opcional, sem UI) -----

def debug_navegacao(grafo: NavigationGraph) -> str:
    """NODES/EDGES/SURFACES/BORDAS/REQUISITOS (diagnóstico puro)."""
    linhas = [f"Navigation {grafo.nome}: {len(grafo.nos)} nós, "
               f"{len(grafo.edges)} edges, "
               f"{len(grafo.superficies)} superfícies"]
    linhas.append("NODES:")
    for node_id in sorted(grafo.nos):
        no = grafo.nos[node_id]
        pos = no.posicao()
        linhas.append(f"  [{no.kind}] {node_id} @ ({pos.x:g},{pos.y:g})")
    linhas.append("EDGES:")
    for edge in grafo.edges:
        req = f' requer={edge.requer}' if edge.requer else ""
        bloq = " BLOQUEADO" if edge.bloqueado else ""
        linhas.append(f"  {edge.origem} -> {edge.destino} [{edge.modo}]"
                       f" custo={edge.custo_efetivo(grafo):g}{req}{bloq}")
    linhas.append("SURFACES:")
    for sup_id in sorted(grafo.superficies):
        sup = grafo.superficies[sup_id]
        linhas.append(f"  [{sup.tipo}] {sup_id} comp={sup.comprimento():g} "
                       f"navegavel={sup.navegavel}")
    reqs = sorted({e.requer for e in grafo.edges if e.requer})
    linhas.append(f"REQUISITOS: {', '.join(reqs) or '—'}")
    return "\n".join(linhas)
