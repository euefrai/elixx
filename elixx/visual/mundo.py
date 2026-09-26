"""World & Scene Intelligence da ELiXX (Fase 13).

O World SABE; não pensa. Camada semântica sobre a cena existente:

    WORLD (significado) ──→ SCENE (visual) ──→ objetos (F01–F12)

Sem segundo Transform (usa F10: combinar/transform_de_no), sem segundo
Motion, sem loop/thread próprios. Posição é sempre consultada ao vivo
(nunca copiada): Motion e Character refletem na hora. Relações são
derivadas sob demanda (sem cache desatualizável; só índices por id e
por tipo, invalidados em adicionar/remover).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..erros import ErroELiXX
from .transform import Vector2, combinar, transform_de_no

__all__ = [
    "TIPOS_ENTIDADE", "Bounds2D", "WorldEntity", "World", "WorldSnapshot",
    "vincular_mundos",
]

TIPOS_ENTIDADE = ("personagem", "objeto", "plataforma", "parede", "chao",
                  "area", "obstaculo", "ponto", "item")
"""Tipos semânticos (F14: item = instância colocada; sem vínculo renderer)."""


# ----- Bounds2D -----

@dataclass(frozen=True)
class Bounds2D:
    """Retângulo alinhado aos eixos: x, y, largura, altura."""

    x: float = 0.0
    y: float = 0.0
    largura: float = 0.0
    altura: float = 0.0

    @property
    def direita(self) -> float:
        return self.x + self.largura

    @property
    def base(self) -> float:
        return self.y + self.altura

    def centro(self) -> Vector2:
        return Vector2(self.x + self.largura / 2.0,
                       self.y + self.altura / 2.0)

    def contem_ponto(self, ponto: Vector2) -> bool:
        return (self.x <= ponto.x <= self.direita
                and self.y <= ponto.y <= self.base)

    def intersecta(self, outro: Bounds2D) -> bool:
        """Sobreposição com área > 0 (borda não conta; ver toca)."""
        return (self.x < outro.direita and outro.x < self.direita
                and self.y < outro.base and outro.y < self.base)

    def sobrepoe(self, outro: Bounds2D) -> bool:
        """Alias honesto de intersecta (área comum positiva)."""
        return self.intersecta(outro)

    def toca(self, outro: Bounds2D) -> bool:
        """Bordas encostam (sem área comum): diferença de sobreposição."""
        if self.intersecta(outro):
            return False
        return (self.x <= outro.direita and outro.x <= self.direita
                and self.y <= outro.base and outro.y <= self.base)

    def contem(self, outro: Bounds2D) -> bool:
        """Outro bounds inteiramente dentro (bordas inclusas)."""
        return (self.x <= outro.x and self.y <= outro.y
                and self.direita >= outro.direita
                and self.base >= outro.base)

    def expandir(self, margem: float) -> Bounds2D:
        """Cresce margem em todas as direções (margem ≥ 0)."""
        margem = float(margem)
        if margem < 0:
            raise ErroELiXX(
                f'Expansão inválida de bounds: {margem!r}. Use ≥ 0.')
        return Bounds2D(self.x - margem, self.y - margem,
                        self.largura + 2 * margem,
                        self.altura + 2 * margem)

    def uniao(self, outro: Bounds2D) -> Bounds2D:
        """Menor bounds contendo ambos."""
        x0, y0 = min(self.x, outro.x), min(self.y, outro.y)
        x1, y1 = max(self.direita, outro.direita), max(self.base,
                                                       outro.base)
        return Bounds2D(x0, y0, x1 - x0, y1 - y0)

    def distancia_para(self, outro: Bounds2D) -> float:
        """Distância entre centros (regra documentada do World)."""
        return self.centro().distancia(outro.centro())


# ----- WorldEntity -----

class WorldEntity:
    """Algo semanticamente existente (visual opcional, nunca duplicado)."""

    def __init__(self, nome: str, tipo: str, mundo,
                 no=None, character=None, item=None,
                 base: Bounds2D | None = None,
                 categoria: str = "", tags=(), props=None) -> None:
        if tipo not in TIPOS_ENTIDADE:
            raise ErroELiXX(
                f'Tipo de entidade inválido: "{tipo}". '
                f'Válidos: {", ".join(TIPOS_ENTIDADE)}.')
        self.nome = nome
        self.tipo = tipo
        self.mundo = mundo
        self.no = no  # NoVisual (referência viva, sem cópia)
        self.character = character  # Character F12 (referência viva)
        self.item = item  # ItemInstance F14 (referência viva)
        self.base = base or Bounds2D()
        self.categoria = categoria
        self.tags = tuple(tags)
        self.props = dict(props or {})
        # Fase 13: `tamanho:` explícito vence o tamanho do visual
        # (mundo = significado); sem ele, usa-se o nó, senão ponto.
        self.tamanho_explicito = False

    # ----- leitura ao vivo (QUERY; nunca COMMAND) -----

    def _no_ancora(self):
        if self.character is not None:
            return self.character.no_raiz
        if self.item is not None:
            # Fase 14: visual da definição (sem duplicar o nó).
            visual = self.mundo._visual_item(self.item)
            if visual is not None:
                return visual
        return self.no

    def posicao_global(self) -> Vector2:
        """Posição atual (acompanha Motion/Character na hora)."""
        no = self._no_ancora()
        if no is None:
            return Vector2(self.base.x, self.base.y)
        global_ = self.mundo._global_de_no(no)
        return Vector2(global_.x, global_.y)

    def rotacao_global(self) -> float:
        """Orientação atual (Transform da F10, sem duplicar)."""
        no = self._no_ancora()
        if no is None:
            return 0.0
        return float(self.mundo._global_de_no(no).rotacao)

    def bounds_global(self) -> Bounds2D:
        """Bounds no espaço do mundo (origem global + tamanho).

        Tamanho: `tamanho:` explícito vence; senão o nó visual; senão
        ponto (0x0). Origem sempre ao vivo.
        """
        no = self._no_ancora()
        if no is None:
            return Bounds2D(self.base.x, self.base.y, self.base.largura,
                            self.base.altura)
        global_ = self.mundo._global_de_no(no)
        if self.tamanho_explicito:
            largura, altura = self.base.largura, self.base.altura
        else:
            largura = getattr(no, "largura", None)
            altura = getattr(no, "altura", None)
            if largura is None:
                largura = self.base.largura
            if altura is None:
                altura = self.base.altura
        return Bounds2D(global_.x, global_.y, float(largura or 0.0),
                        float(altura or 0.0))

    def centro(self) -> Vector2:
        return self.bounds_global().centro()

    def __repr__(self) -> str:
        return f"WorldEntity({self.tipo} {self.nome})"


# ----- World -----

class World:
    """Mundo lógico: entidades, regiões, consultas (sem loop/thread)."""

    def __init__(self, nome: str, cena=None,
                 bounds: Bounds2D | None = None) -> None:
        self.nome = nome
        self.cena = cena
        self.bounds = bounds or Bounds2D(0.0, 0.0, 800.0, 600.0)
        self._entidades: dict[str, WorldEntity] = {}
        self._por_tipo: dict[str, list[str]] = {}
        self._ordem: list[str] = []
        # Fase 14: visuais de definições de item (nome do nó → nó).
        self._visuais_item: dict[str, object] = {}

    def _visual_item(self, instancia):
        """Nó visual da definição do item (ou None)."""
        return self._visuais_item.get(instancia.definicao)

    # ----- comandos estruturais (única mutação; queries não mutam) -----

    def adicionar(self, entidade: WorldEntity) -> WorldEntity:
        """Registra entidade (id global único no mundo)."""
        if entidade.nome in self._entidades:
            raise ErroELiXX(
                f'Entidade "{entidade.nome}" repetida no mundo '
                f'"{self.nome}".')
        entidade.mundo = self
        self._entidades[entidade.nome] = entidade
        self._por_tipo.setdefault(entidade.tipo, []).append(entidade.nome)
        self._ordem.append(entidade.nome)
        return entidade

    def remover(self, nome: str) -> WorldEntity:
        """Remove e devolve a entidade (erro claro se inexistente)."""
        try:
            entidade = self._entidades.pop(nome)
        except KeyError:
            from ..erros import sugerir

            parecidas = sugerir(nome, sorted(self._entidades))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroELiXX(
                f'Entidade "{nome}" não existe no mundo '
                f'"{self.nome}".{dica}')
        self._por_tipo[entidade.tipo].remove(nome)
        self._ordem.remove(nome)
        return entidade

    # ----- geometria interna (F10, sem duplicar) -----

    def _global_de_no(self, no):
        """Transform global subindo pais (reusa combinar da F10)."""
        atual = transform_de_no(no)
        ancestral = getattr(no, "pai", None)
        cadeia = []
        while ancestral is not None:
            cadeia.append(transform_de_no(ancestral))
            ancestral = getattr(ancestral, "pai", None)
        for transform_pai in cadeia:
            atual = combinar(transform_pai, atual)
        return atual

    # ----- consultas por identidade -----

    def __len__(self) -> int:
        return len(self._entidades)

    def __contains__(self, nome: str) -> bool:
        return nome in self._entidades

    def por_id(self, nome: str) -> WorldEntity:
        """Entidade exata ou erro claro (não usa posição/índice)."""
        try:
            return self._entidades[nome]
        except KeyError:
            from ..erros import sugerir

            parecidas = sugerir(nome, sorted(self._entidades))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroELiXX(
                f'Entidade "{nome}" não existe no mundo '
                f'"{self.nome}".{dica}')

    por_nome = por_id

    def por_tipo(self, tipo: str) -> list[WorldEntity]:
        """Todas do tipo (ordem de registro; determinístico)."""
        if tipo not in TIPOS_ENTIDADE:
            raise ErroELiXX(
                f'Tipo inválido: "{tipo}". '
                f'Válidos: {", ".join(TIPOS_ENTIDADE)}.')
        return [self._entidades[nome] for nome in self._por_tipo.get(tipo,
                                                                     [])]

    def por_tag(self, tag: str) -> list[WorldEntity]:
        """Todas com a tag (ordem de registro)."""
        return [self._entidades[nome] for nome in self._ordem
                if tag in self._entidades[nome].tags]

    # ----- consultas espaciais -----

    def na_area(self, bounds: Bounds2D) -> list[WorldEntity]:
        """Entidades cujo bounds está contido (ordem de registro)."""
        return [self._entidades[nome] for nome in self._ordem
                if bounds.contem(self._entidades[nome].bounds_global())]

    def em_regiao(self, nome_area: str) -> list[WorldEntity]:
        """Entidades dentro da área (a área não contém a si mesma)."""
        area = self.por_id(nome_area)
        if area.tipo != "area":
            raise ErroELiXX(
                f'"{nome_area}" não é área (é {area.tipo}).')
        limites = area.bounds_global()
        return [e for e in self.na_area(limites) if e.nome != nome_area]

    def proximos(self, nome: str, raio: float,
                 tipo: str | None = None) -> list[WorldEntity]:
        """Entidades a até `raio` do centro (exclui a própria)."""
        origem = self.por_id(nome)
        raio = float(raio)
        if raio < 0:
            raise ErroELiXX(f"Raio inválido: {raio!r}. Use ≥ 0.")
        centro = origem.centro()
        saida = []
        for outro_nome in self._ordem:
            if outro_nome == nome:
                continue
            outro = self._entidades[outro_nome]
            if tipo is not None and outro.tipo != tipo:
                continue
            if centro.distancia(outro.centro()) <= raio:
                saida.append(outro)
        return saida

    vizinhos = proximos

    def sobrepostos(self, nome: str) -> list[WorldEntity]:
        """Entidades com área comum positiva (exclui a própria)."""
        origem = self.por_id(nome)
        limites = origem.bounds_global()
        return [self._entidades[n] for n in self._ordem
                if n != nome
                and limites.sobrepoe(self._entidades[n].bounds_global())]

    # ----- medidas -----

    def distancia(self, a: str, b: str) -> float:
        """Distância entre centros (Vector2 da F10)."""
        return self.por_id(a).centro().distancia(self.por_id(b).centro())

    def direcao_de(self, a: str, b: str) -> Vector2:
        """Vetor B − A entre centros (informação, não movimento)."""
        return Vector2(self.por_id(b).centro().x - self.por_id(a).centro().x,
                       self.por_id(b).centro().y - self.por_id(a).centro().y)

    # ----- relações derivadas (sob demanda; nunca armazenadas) -----

    def acima_de(self, a: str, b: str) -> bool:
        """A inteiramente acima de B (base de A ≤ topo de B)."""
        la, lb = (self.por_id(a).bounds_global(),
                  self.por_id(b).bounds_global())
        return la.base <= lb.y

    def abaixo_de(self, a: str, b: str) -> bool:
        """A inteiramente abaixo de B."""
        return self.acima_de(b, a)

    def esquerda_de(self, a: str, b: str) -> bool:
        """A inteiramente à esquerda de B."""
        la, lb = (self.por_id(a).bounds_global(),
                  self.por_id(b).bounds_global())
        return la.direita <= lb.x

    def direita_de(self, a: str, b: str) -> bool:
        """A inteiramente à direita de B."""
        return self.esquerda_de(b, a)

    def perto_de(self, a: str, b: str, raio: float = 100.0) -> bool:
        """Centros a até `raio` (padrão 100)."""
        return self.distancia(a, b) <= float(raio)

    def contem(self, a: str, b: str) -> bool:
        """Bounds de A contém bounds de B (área contém personagem)."""
        return self.por_id(a).bounds_global().contem(
            self.por_id(b).bounds_global())

    def dentro_de(self, a: str, b: str) -> bool:
        """A dentro de B (≠ sobreposição visual)."""
        return self.contem(b, a)

    def sobrepoe(self, a: str, b: str) -> bool:
        """Área comum positiva (geometria, não física)."""
        return self.por_id(a).bounds_global().sobrepoe(
            self.por_id(b).bounds_global())

    def toca(self, a: str, b: str) -> bool:
        """Bordas encostam sem área comum (definição documentada)."""
        return self.por_id(a).bounds_global().toca(
            self.por_id(b).bounds_global())

    # ----- viewport (F10; sem câmera) -----

    def visiveis_na_viewport(self) -> list[WorldEntity]:
        """Entidades cujo bounds cruza a viewport (consulta lógica)."""
        viewport = getattr(self.cena, "viewport", None)
        if viewport is None:
            limites = Bounds2D(0.0, 0.0, 800.0, 600.0)
        else:
            limites = Bounds2D(viewport.x, viewport.y, viewport.largura,
                               viewport.altura)
        return [self._entidades[nome] for nome in self._ordem
                if self._entidades[nome].bounds_global().intersecta(limites)
                or limites.contem(
                    self._entidades[nome].bounds_global())]

    # ----- snapshot (leitura; nunca COMMAND) -----

    def snapshot(self) -> WorldSnapshot:
        """Visão congelada e somente leitura (planejamento/debug/teste)."""
        return WorldSnapshot.from_world(self)

    # ----- regiões -----

    def areas(self) -> list[WorldEntity]:
        """Todas as áreas (ordem de registro)."""
        return self.por_tipo("area")

    def subregioes(self, nome_area: str) -> list[WorldEntity]:
        """Áreas filhas diretas (via prop `pai`)."""
        return [e for e in self.areas()
                if e.props.get("pai") == nome_area]

    # ----- bordas (Fase 15: cantos do bounds ao vivo) -----

    def _posicao_borda(self, entidade_nome: str, lado: str) -> Vector2:
        """Ponto da borda: esquerda/direita = cantos superiores;
        topo/base = meio superior/inferior (documentado)."""
        limites = self.por_id(entidade_nome).bounds_global()
        if lado == "esquerda":
            return Vector2(limites.x, limites.y)
        if lado == "direita":
            return Vector2(limites.direita, limites.y)
        if lado == "topo":
            return Vector2(limites.x + limites.largura / 2.0, limites.y)
        if lado == "base":
            return Vector2(limites.x + limites.largura / 2.0, limites.base)
        raise ErroELiXX(
            f'Lado de borda inválido: "{lado}". '
            'Válidos: esquerda, direita, topo, base.')

    # ----- debug (puro; não toca no runtime) -----

    def debug_texto(self) -> str:
        """Diagnóstico opcional: bounds/centros/nomes/regiões/POIs."""
        linhas = [f"World {self.nome}: "
                   f"{self.bounds.largura:g}x{self.bounds.altura:g} "
                   f"({len(self)} entidades)"]
        for nome in self._ordem:
            entidade = self._entidades[nome]
            limites = entidade.bounds_global()
            centro = limites.centro()
            linhas.append(
                f"  [{entidade.tipo}] {nome}: "
                f"bounds=({limites.x:g},{limites.y:g},"
                f"{limites.largura:g}x{limites.altura:g}) "
                f"centro=({centro.x:g},{centro.y:g})")
        for area in self.areas():
            dentro = [e.nome for e in self.em_regiao(area.nome)]
            linhas.append(f"  região {area.nome}: {', '.join(dentro) or '—'}")
        return "\n".join(linhas)


# ----- Snapshot (somente leitura) -----

@dataclass(frozen=True)
class _ItemSnapshot:
    nome: str
    tipo: str
    x: float
    y: float
    largura: float
    altura: float
    rotacao: float
    categoria: str
    tags: tuple = ()


@dataclass(frozen=True)
class WorldSnapshot:
    """Congelado: tuplas + frozenset; mutar levanta erro (frozen)."""

    mundo: str
    bounds: Bounds2D
    itens: tuple = ()

    @staticmethod
    def from_world(world: World) -> WorldSnapshot:
        itens = []
        for nome in world._ordem:
            entidade = world._entidades[nome]
            limites = entidade.bounds_global()
            itens.append(_ItemSnapshot(
                nome=entidade.nome, tipo=entidade.tipo, x=limites.x,
                y=limites.y, largura=limites.largura,
                altura=limites.altura,
                rotacao=entidade.rotacao_global(),
                categoria=entidade.categoria, tags=tuple(entidade.tags)))
        return WorldSnapshot(mundo=world.nome, bounds=world.bounds,
                             itens=tuple(itens))

    def por_id(self, nome: str) -> _ItemSnapshot:
        """Item exato do snapshot (leitura)."""
        for item in self.itens:
            if item.nome == nome:
                return item
        raise ErroELiXX(f'Entidade "{nome}" ausente no snapshot.')

    def como_tuplas(self) -> tuple:
        """(nome, tipo, x, y, largura, altura) por entidade, em ordem."""
        return tuple((i.nome, i.tipo, i.x, i.y, i.largura, i.altura)
                     for i in self.itens)


# ----- vínculo cena + programa → mundos -----

def _texto_prop(prop) -> str | None:
    """Texto ou identificador (refs como visual: nome)."""
    from ..compilador import ast as _A

    if not prop.valores:
        return None
    valor = prop.valores[0]
    if isinstance(valor, _A.TextoLit):
        return valor.valor
    if isinstance(valor, _A.Ident):
        return valor.nome
    return None


def _medida_par(prop, indice: int, referencia: float) -> float | None:
    from ..visual.cena import resolver_medida

    if len(prop.valores) > indice:
        return resolver_medida(prop.valores[indice], referencia)
    return None


def vincular_mundos(cena, programa, personagens=None,
                     itens: dict | None = None) -> dict[str, World]:
    """Monta Worlds a partir da cena + AST (sem duplicar posições).

    Entidades referenciam nós/characters/itens vivos (leitura ao vivo).
    `personagens` = vincular_personagens(cena) (exigido se houver `usar`
    personagem); `itens` = vincular_itens(programa) (exigido se houver
    `usar item`).
    """
    personagens = personagens or {}
    mundos: dict[str, World] = {}
    janelas = {j.nome: j for j in getattr(cena, "janelas", [])}
    for janela_ast in list(programa.janelas) + list(programa.telas):
        for mundo_ast in janela_ast.mundos:
            if mundo_ast.nome in mundos:
                raise ErroELiXX(
                    f'Mundo "{mundo_ast.nome}" repetido no programa.')
            mundos[mundo_ast.nome] = _vincular_um(
                mundo_ast, janelas.get(janela_ast.nome), cena, personagens,
                itens)
    return mundos


def _vincular_um(mundo_ast, no_janela, cena,
                 personagens: dict, itens: dict | None = None) -> World:
    largura, altura = 800.0, 600.0
    for prop in mundo_ast.propriedades:
        if prop.nome == "tamanho" and len(prop.valores) >= 1:
            valores = [_medida_par(prop, 0, 800.0),
                       _medida_par(prop, 1, 600.0) if len(prop.valores) > 1
                       else None]
            if valores[0] is not None:
                largura = valores[0]
            if valores[1] is not None:
                altura = valores[1]
            elif len(prop.valores) == 1 and valores[0] is not None:
                altura = valores[0]
    mundo = World(mundo_ast.nome, cena=cena,
                  bounds=Bounds2D(0.0, 0.0, largura, altura))
    _registrar_visuais_itens(mundo, cena, itens)
    for entidade_ast in mundo_ast.entidades:
        mundo.adicionar(_vincular_entidade(entidade_ast, mundo, cena,
                                           personagens, itens))
    return mundo


def _registrar_visuais_itens(mundo: World, cena, itens: dict | None) -> None:
    """Mapeia definição de item → nó visual (para bounds ao vivo)."""
    if not itens or cena is None:
        return
    for nome, definicao in itens.get("defs", {}).items():
        if definicao.visual:
            no = cena.buscar(definicao.visual)
            if no is not None:
                mundo._visuais_item[nome] = no


def _vincular_entidade(entidade_ast, mundo: World, cena,
                       personagens: dict,
                       itens: dict | None = None) -> WorldEntity:
    from ..visual.cena import resolver_medida

    nome, tipo = entidade_ast.nome, entidade_ast.tipo
    props = {p.nome: p for p in entidade_ast.propriedades}
    x = y = 0.0
    if "posicao" in props or "posição" in props:
        prop = props.get("posicao", props.get("posição"))
        x = resolver_medida(prop.valores[0], 800.0) or 0.0 \
            if len(prop.valores) > 0 else 0.0
        y = resolver_medida(prop.valores[1], 600.0) or 0.0 \
            if len(prop.valores) > 1 else 0.0
    largura = altura = 0.0
    tamanho_explicito = False
    if "tamanho" in props:
        tamanho_explicito = True
        prop = props["tamanho"]
        largura = resolver_medida(prop.valores[0], 800.0) or 0.0 \
            if len(prop.valores) > 0 else 0.0
        altura = (resolver_medida(prop.valores[1], 600.0) or 0.0
                  if len(prop.valores) > 1 else largura)
    categoria = ""
    if "categoria" in props:
        categoria = _texto_prop(props["categoria"]) or ""
    tags: list[str] = []
    if "tag" in props and _texto_prop(props["tag"]):
        tags.append(_texto_prop(props["tag"]))
    if "tags" in props:
        from ..compilador import ast as _A

        tags.extend(v.valor for v in props["tags"].valores
                    if isinstance(v, _A.TextoLit))
    extras = {}
    if "pai" in props and _texto_prop(props["pai"]):
        extras["pai"] = _texto_prop(props["pai"])

    if tipo == "personagem":
        if nome not in personagens:
            raise ErroELiXX(
                f"Personagem '{nome}' sem vínculo (rode "
                "vincular_personagens antes).")
        entidade = WorldEntity(nome, tipo, mundo,
                               character=personagens[nome],
                               base=Bounds2D(x, y, largura, altura),
                               categoria=categoria, tags=tags, props=extras)
        entidade.tamanho_explicito = tamanho_explicito
        return entidade
    if tipo == "item":
        # Fase 14: `usar item Def [como Apelido]`: instância viva.
        if itens is None:
            raise ErroELiXX(
                f'Item "{nome}" sem vínculo (rode vincular_itens antes).')
        from .capacidades import obter_instancia

        ref = entidade_ast.ref or nome
        instancia = obter_instancia(itens, ref, nome)
        definicao = itens["defs"][ref]
        if not categoria:
            categoria = definicao.categoria
        tags = tuple(tags) + tuple(
            t for t in definicao.tags if t not in tags)
        entidade = WorldEntity(nome, tipo, mundo, item=instancia,
                               base=Bounds2D(x, y, largura, altura),
                               categoria=categoria, tags=tags, props=extras)
        entidade.tamanho_explicito = tamanho_explicito
        return entidade
    no = None
    if "visual" in props and _texto_prop(props["visual"]):
        ref = _texto_prop(props["visual"])
        no = cena.buscar(ref) if cena is not None else None
        if no is None:
            raise ErroELiXX(
                f'Visual "{ref}" da entidade "{nome}" não existe na cena.')
    entidade = WorldEntity(nome, tipo, mundo, no=no,
                           base=Bounds2D(x, y, largura, altura),
                           categoria=categoria, tags=tags, props=extras)
    entidade.tamanho_explicito = tamanho_explicito
    return entidade
