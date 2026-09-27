"""Cena e timeline do Studio (F25) — visualização, não edição completa.

ModeloCena resume a cena compilada (janelas, personagens). Timeline é
visualização de motions existentes (trilhas por alvo) + API para edição
futura. `timeline_de_motions` converte DefinicaoAnimacao F11.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["ModeloCena", "Timeline", "timeline_de_motions",
           "MODOS_CENA", "ZOOM_CENA", "SNAPS",
           "ViewportState", "NoCena", "SceneTree",
           "snap_valor"]


def _finito(valor, o_que: str) -> float:
    import math

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f"Cena: {o_que} numérico.")
    if not math.isfinite(numero):
        raise ErroELiXX(f"Cena: {o_que} finito.")
    return numero


MODOS_CENA = ("Selecionar", "Mover", "Escalar", "Girar", "Ajustar")
"""Modos do Scene Editor (estado visual; transformação real só onde
houver implementação — sem fingir)."""

ZOOM_CENA = (25, 50, 75, 100, 125, 150, 200, "Ajustar")
"""Níveis de zoom (estado real aplicado ao canvas quando houver)."""

SNAPS = (0, 1, 5, 10)
"""Snap: 0 = livre; demais = passo em px (só com transformação)."""


def snap_valor(valor: float, passo: int) -> float:
    """Arredonda ao múltiplo do passo (passo 0 = intacto)."""
    numero = _finito(valor, "valor")
    if passo not in SNAPS:
        raise ErroELiXX(f"Cena: snap em {SNAPS}.")
    if passo == 0:
        return numero
    import math

    return float(math.floor(numero / passo + 0.5)) * passo


class ViewportState:
    """Zoom/pan/grid/snap/modo (serializável, sem Tk)."""

    def __init__(self, zoom=100, offset_x: float = 0.0,
                 offset_y: float = 0.0, grid: bool = False,
                 snap: int = 0, modo: str = "Selecionar") -> None:
        self.set_zoom(zoom)
        self.offset_x = _finito(offset_x, "offset_x")
        self.offset_y = _finito(offset_y, "offset_y")
        self.grid = bool(grid)
        if snap not in SNAPS:
            raise ErroELiXX(f"Cena: snap em {SNAPS}.")
        self.snap = snap
        if modo not in MODOS_CENA:
            raise ErroELiXX(f"Cena: modo em {MODOS_CENA}.")
        self.modo = modo

    def set_zoom(self, nivel) -> None:
        if nivel not in ZOOM_CENA:
            raise ErroELiXX(f"Cena: zoom em {ZOOM_CENA}.")
        self.zoom = nivel

    def fator(self) -> float:
        """Fator numérico (Ajustar = 1.0 documentado)."""
        if self.zoom == "Ajustar":
            return 1.0
        return float(self.zoom) / 100.0

    def mover(self, dx: float, dy: float) -> list:
        self.offset_x = _finito(self.offset_x + float(dx),
                                "offset_x")
        self.offset_y = _finito(self.offset_y + float(dy),
                                "offset_y")
        return [self.offset_x, self.offset_y]

    def para_tela(self, x: float, y: float) -> list:
        f = self.fator()
        return [_finito(x, "x") * f + self.offset_x,
                _finito(y, "y") * f + self.offset_y]

    def da_tela(self, x: float, y: float) -> list:
        f = self.fator()
        return [(_finito(x, "x") - self.offset_x) / f,
                (_finito(y, "y") - self.offset_y) / f]

    def to_dict(self) -> dict:
        return {"zoom": self.zoom, "offset_x": self.offset_x,
                "offset_y": self.offset_y, "grid": self.grid,
                "snap": self.snap, "modo": self.modo}

    @staticmethod
    def from_dict(dados: dict) -> ViewportState:
        if not isinstance(dados, dict):
            raise ErroELiXX("Cena: viewport precisa de dict.")
        return ViewportState(
            dados.get("zoom", 100),
            offset_x=dados.get("offset_x", 0.0),
            offset_y=dados.get("offset_y", 0.0),
            grid=dados.get("grid", False),
            snap=dados.get("snap", 0),
            modo=dados.get("modo", "Selecionar"))

    def __repr__(self) -> str:
        return (f"ViewportState({self.zoom} grid={self.grid} "
                f"snap={self.snap} {self.modo})")


class NoCena:
    """Nó da Scene Tree (id, tipo, nome, filhos ids, expandido)."""

    def __init__(self, node_id: str, tipo: str, nome: str = "",
                 filhos: list | None = None,
                 expandido: bool = True) -> None:
        if not isinstance(node_id, str) or not node_id.strip():
            raise ErroELiXX("Cena: nó precisa de id.")
        self.id = node_id.strip()
        self.tipo = str(tipo)
        self.nome = str(nome) or self.id
        self.filhos = [str(f) for f in (filhos or [])]
        self.expandido = bool(expandido)

    def to_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo,
                "nome": self.nome, "filhos": list(self.filhos),
                "expandido": self.expandido}

    def __repr__(self) -> str:
        return f"NoCena({self.tipo} {self.id})"


class SceneTree:
    """Hierarquia da cena aberta (F27 possui/contem; sem invenção)."""

    def __init__(self) -> None:
        self.nos: dict[str, NoCena] = {}
        self.raizes: list[str] = []

    def construir(self, modelo) -> SceneTree:
        """Janelas → personagens/componentes → partes (relações)."""
        from .modelo.consulta import ConsultaSemantica

        self.nos = {}
        self.raizes = []
        q = ConsultaSemantica(modelo)
        filhos_de: dict[str, list] = {}
        for rel in modelo.relacoes():
            if rel.tipo in ("contem", "possui"):
                filhos_de.setdefault(rel.origem, []).append(
                    rel.destino)
        for ent in modelo.entidades():
            if ent.tipo in ("janela", "tela"):
                self.raizes.append(ent.id)
        for ent in modelo.entidades():
            kids = sorted(set(filhos_de.get(ent.id, [])))
            kids = [k for k in kids if any(
                e.id == k for e in modelo.entidades())]
            self.nos[ent.id] = NoCena(ent.id, ent.tipo, ent.nome,
                                      kids)
        self.raizes = sorted(set(self.raizes) & set(self.nos))
        _ = q
        return self

    def visiveis(self) -> list[NoCena]:
        """Pré-ordem respeitando recolhidos (determinística)."""
        saida: list[NoCena] = []

        def _visita(nid: str, profundidade: int) -> None:
            no = self.nos.get(nid)
            if no is None:
                return
            saida.append(no)
            if no.expandido:
                for filho in no.filhos:
                    _visita(filho, profundidade + 1)

        for raiz in self.raizes:
            _visita(raiz, 0)
        return saida

    def alternar(self, node_id: str) -> bool:
        try:
            no = self.nos[str(node_id)]
        except KeyError:
            raise ErroELiXX(f'Cena: nó "{node_id}" ausente.')
        no.expandido = not no.expandido
        return no.expandido

    def linhas(self) -> list[str]:
        """Texto `▾/▸ ├ └` para a UI (só dados do modelo)."""
        linhas: list[str] = []

        def _visita(nid: str, prefixo: str, ultimo: bool,
                    raiz: bool) -> None:
            no = self.nos.get(nid)
            if no is None:
                return
            if raiz:
                linhas.append(f"▾ {no.tipo} {no.nome}"
                             if no.filhos and no.expandido
                             else f"• {no.tipo} {no.nome}")
            else:
                galho = "└ " if ultimo else "├ "
                marca = "▾ " if no.filhos and no.expandido \
                    else "▸ " if no.filhos else ""
                linhas.append(f"{prefixo}{galho}{marca}{no.tipo} "
                               f"{no.nome}")
            if no.expandido:
                total = len(no.filhos)
                for i, filho in enumerate(no.filhos):
                    prox = prefixo + ("   " if ultimo else "│  ")
                    _visita(filho, prox, i == total - 1, False)

        for raiz in self.raizes:
            _visita(raiz, "", True, True)
        return linhas

    def __repr__(self) -> str:
        return f"SceneTree({len(self.nos)} nós)"


class ModeloCena:
    """Resumo da cena compilada (para preview/inspetor/timeline)."""

    def __init__(self, janelas: int = 0, nos: int = 0,
                 personagens: list | None = None,
                 fonte: str = "") -> None:
        self.janelas = int(janelas)
        self.nos = int(nos)
        self.personagens = sorted(str(p) for p in
                                  (personagens or []))
        self.fonte = str(fonte)

    @staticmethod
    def da_cena(cena, fonte: str = "") -> ModeloCena:
        total = 0
        pilha = list(getattr(cena, "janelas", []))
        while pilha:
            no = pilha.pop()
            total += 1
            pilha.extend(getattr(no, "filhos", []))
        return ModeloCena(len(getattr(cena, "janelas", [])), total,
                          fonte=fonte)

    def to_dict(self) -> dict:
        return {"janelas": self.janelas, "nos": self.nos,
                "personagens": list(self.personagens),
                "fonte": self.fonte}

    def __repr__(self) -> str:
        return (f"ModeloCena({self.janelas} janelas, {self.nos} "
                f"nos)")


class Timeline:
    """Trilhas por alvo: [{alvo, blocos: [{nome, inicio, duracao}]}].

    Tempos em ms (finitos ≥ 0). Nesta fase: visualização + registro;
    edição de keyframes é futura (API já ordenada e determinística).
    """

    def __init__(self) -> None:
        self._trilhas: dict[str, list] = {}

    def _validar_tempo(self, valor, o_que: str) -> float:
        import math

        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ErroELiXX(f'Timeline: "{o_que}" numérico.')
        if not math.isfinite(numero) or numero < 0:
            raise ErroELiXX(f'Timeline: "{o_que}" finito ≥ 0.')
        return numero

    def adicionar(self, alvo: str, nome: str, inicio_ms: float = 0.0,
                  duracao_ms: float = 500.0) -> dict:
        if not str(alvo).strip() or not str(nome).strip():
            raise ErroELiXX("Timeline: alvo e nome não vazios.")
        bloco = {"nome": str(nome),
                 "inicio": self._validar_tempo(inicio_ms, "inicio"),
                 "duracao": self._validar_tempo(duracao_ms,
                                                "duracao")}
        trilha = self._trilhas.setdefault(str(alvo), [])
        trilha.append(bloco)
        trilha.sort(key=lambda b: (b["inicio"], b["nome"]))
        return bloco

    def trilhas(self) -> dict:
        return {alvo: list(blocos) for alvo, blocos in
                sorted(self._trilhas.items())}

    def duracao_total(self) -> float:
        total = 0.0
        for blocos in self._trilhas.values():
            for b in blocos:
                total = max(total, b["inicio"] + b["duracao"])
        return total

    def to_dict(self) -> dict:
        return {"trilhas": self.trilhas(),
                "duracao_total": self.duracao_total()}

    def __repr__(self) -> str:
        return (f"Timeline({len(self._trilhas)} trilhas, "
                f"{self.duracao_total():g}ms)")


def timeline_de_motions(definicoes: list) -> Timeline:
    """DefinicaoAnimacao F11 → Timeline (início 0, duração da def)."""
    linha = Timeline()
    for definicao in definicoes or []:
        alvo = getattr(definicao, "alvo", "?")
        nome = getattr(definicao, "nome", "?")
        duracao = float(getattr(definicao, "duracao_ms", 500.0))
        linha.adicionar(str(alvo), str(nome), 0.0, duracao)
    return linha
