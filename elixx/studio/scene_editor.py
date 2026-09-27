"""Scene Editor + Adaptive Workspace (Fase 39) — camada de interacao.

Nao e um segundo renderer, parser, modelo ou selecao: e uma camada de
interacao sobre F10/F11/F12/F13/F21/F22/F23/F24/F25 (Transform, Motion,
Character, World, Geometry, Perception, Rigging, Deformation, Preview)
e sobre o Studio F25-F38 (selecao global, EventBus, ViewportState,
SceneTree, Planner, ChangeSet, Code Sync, Agent MOCK).

Tudo aqui e headless e serializavel; o Tk (quando houver) apenas le
este estado. Modos/gizmos so ativam o que possui implementacao real:
o restante fica "preparado" com motivo honesto, sem fingir.
"""

from __future__ import annotations

import math
import unicodedata

from ..erros import ErroELiXX
from .cena import (
    MODOS_CENA,
    SNAPS,
    ZOOM_CENA,
    SceneTree,
    ViewportState,
    snap_valor,
)
from .inspetor import Selecao

__all__ = [
    "MODOS_F39",
    "ZOOM_F39",
    "SNAPS_F39",
    "GIZMOS",
    "ATALHOS_F39",
    "COMANDOS_F39",
    "MODOS_WORKSPACE",
    "PAINEIS_POR_MODO",
    "ABAS_FUNDO",
    "ABA_PARA_PAINEL",
    "RESOLUCOES_QA",
    "BoundingBox",
    "GizmoStatus",
    "gizmo_para_modo",
    "gizmo_status",
    "SceneEditor",
    "SceneToolbar",
    "ITENS_TOOLBAR",
    "WorkspaceModes",
    "BottomWorkspace",
    "StatusBar",
    "montar_status",
    "erro_amigavel",
    "buscar_palette_f39",
    "executar_palette_f39",
    "conflitos_f39",
    "ir_para_codigo",
    "entidade_do_cursor",
]

MODOS_F39 = MODOS_CENA
"""Modos do Scene Editor (reuso de cena.MODOS_CENA)."""

ZOOM_F39 = ZOOM_CENA
"""Niveis de zoom reais: 25..200 + Ajustar (reuso de cena)."""

SNAPS_F39 = SNAPS
"""Snap: 0 = livre; 1/5/10 px (reuso de cena)."""

GIZMOS = ("mover", "escalar", "girar")
"""Gizmos previstos (so 'mover' possui implementacao real)."""

ATALHOS_F39 = {
    "V": "scene_selecionar",
    "G": "scene_mover",
    "S": "scene_escalar",
    "R": "scene_girar",
    "F": "scene_ajustar",
    "Ctrl+Shift+F": "foco_atual",
    "Esc": "sair_do_foco",
}
"""Atalhos contextuais do Scene Editor (validos com a cena focada).

Nao substituem o mapa global de app.ATALHOS: "F" global continua
"enquadrar" e "Esc" global continua "cancelar" (ver conflitos_f39).
"""

COMANDOS_F39 = (
    ("scene_selecionar", "Scene: Selecionar"),
    ("scene_mover", "Scene: Mover"),
    ("scene_escalar", "Scene: Escalar"),
    ("scene_girar", "Scene: Girar"),
    ("scene_ajustar", "Scene: Ajustar"),
    ("scene_grid", "Scene: Grid"),
    ("scene_snap", "Scene: Snap"),
    ("layout_scene", "Layout: Scene"),
    ("layout_code", "Layout: Code"),
    ("layout_agent", "Layout: Agent"),
    ("layout_review", "Layout: Review"),
    ("foco_atual", "Foco atual"),
    ("sair_do_foco", "Sair do foco"),
)
"""Comandos F39 (lista propria; COMANDOS_PALETTE F37 intacto)."""

MODOS_WORKSPACE = ("DEFAULT", "CODE", "SCENE", "AGENT", "REVIEW")
"""Estados adaptativos do workspace (F37 continua existindo)."""

PAINEIS_POR_MODO = {
    "DEFAULT": ("project", "preview", "inspector", "agent"),
    "CODE": ("project", "editor", "agent"),
    "SCENE": ("preview", "inspector"),
    "AGENT": ("agent", "preview"),
    "REVIEW": ("editor", "inspector", "agent"),
}
"""Paineis por modo (subconjunto de workspace_ui.PAINEIS; sem destruir
estado: so visibilidade)."""

ABAS_FUNDO = ("CODE", "AGENT", "REASONING", "PLAN", "CHANGES", "CONSOLE")
"""Abas da area inferior compartilhada (uma ou poucas abertas)."""

ABA_PARA_PAINEL = {
    "CODE": "editor",
    "AGENT": "agent",
    "REASONING": "raciocinio",
    "PLAN": "plano",
    "CHANGES": "plano",
    "CONSOLE": "console",
}
"""Aba F39 -> painel/aba inferior existente (raciocinio/plano F37)."""

RESOLUCOES_QA = (
    (800, 500),
    (1024, 600),
    (1024, 768),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
)
"""Resolucoes do QA visual (todas dentro de 800x500..3840x2160)."""


def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f"Scene: {o_que} numerico.")
    if not math.isfinite(numero):
        raise ErroELiXX(f"Scene: {o_que} finito.")
    return numero


def _texto_curto(valor, limite: int = 200) -> str:
    texto = str(valor)
    if len(texto) > limite:
        raise ErroELiXX("Scene: texto excede limite.")
    for ch in texto:
        if ord(ch) < 32 and ch not in ("\n", "\t"):
            raise ErroELiXX("Scene: texto com controle invalido.")
    return texto


class BoundingBox:
    """Retangulo real do no (None onde nao ha dado; sem invencao)."""

    def __init__(self, x=None, y=None, largura=None, altura=None,
                 rotacao=None) -> None:
        self.x = x
        self.y = y
        self.largura = largura
        self.altura = altura
        self.rotacao = rotacao

    @staticmethod
    def de_no(no) -> BoundingBox:
        """Le x/y/largura/altura/rotacao do no quando existirem."""
        def _ler(*nomes):
            for nome in nomes:
                if hasattr(no, nome):
                    try:
                        return _finito(getattr(no, nome), nome)
                    except ErroELiXX:
                        return None
            return None

        return BoundingBox(
            x=_ler("x"),
            y=_ler("y"),
            largura=_ler("largura", "width"),
            altura=_ler("altura", "height"),
            rotacao=_ler("rotacao", "rotation"),
        )

    @staticmethod
    def de_props(props: dict) -> BoundingBox:
        """Le do dicionario do inspetor (inspecionar_no)."""
        if not isinstance(props, dict):
            raise ErroELiXX("Scene: props precisa de dict.")
        return BoundingBox(
            x=props.get("x"),
            y=props.get("y"),
            largura=props.get("largura", props.get("width")),
            altura=props.get("altura", props.get("height")),
            rotacao=props.get("rotacao"),
        )

    def vazia(self) -> bool:
        return self.x is None and self.y is None

    def area(self):
        if self.largura is None or self.altura is None:
            return None
        return self.largura * self.altura

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y,
                "largura": self.largura, "altura": self.altura,
                "rotacao": self.rotacao}

    def __repr__(self) -> str:
        return (f"BoundingBox(x={self.x} y={self.y} "
                f"{self.largura}x{self.altura})")


class GizmoStatus:
    """Estado honesto de um gizmo (disponivel ou preparado)."""

    def __init__(self, gizmo: str, disponivel: bool,
                 motivo: str = "") -> None:
        if gizmo not in GIZMOS:
            raise ErroELiXX(f"Scene: gizmo em {GIZMOS}.")
        self.gizmo = gizmo
        self.disponivel = bool(disponivel)
        self.motivo = str(motivo)[:200]

    def to_dict(self) -> dict:
        return {"gizmo": self.gizmo,
                "disponivel": self.disponivel,
                "motivo": self.motivo}

    def __repr__(self) -> str:
        return (f"GizmoStatus({self.gizmo} "
                f"{'ok' if self.disponivel else 'preparado'})")


def gizmo_para_modo(modo: str) -> str | None:
    """Modo -> gizmo (Selecionar/Ajustar nao tem gizmo)."""
    mapa = {"Mover": "mover", "Escalar": "escalar", "Girar": "girar"}
    if modo not in MODOS_F39:
        raise ErroELiXX(f"Scene: modo em {MODOS_F39}.")
    return mapa.get(modo)


def gizmo_status(modo: str) -> GizmoStatus:
    """Disponibilidade real por modo (sem fingir transformacao)."""
    gizmo = gizmo_para_modo(modo)
    if gizmo is None:
        raise ErroELiXX(f'Scene: modo "{modo}" sem gizmo.')
    if gizmo == "mover":
        return GizmoStatus("mover", True,
                           "x/y via proposta aprovada")
    if gizmo == "escalar":
        return GizmoStatus("escalar", False,
                           "preparado: sem escrita geometrica real")
    return GizmoStatus("girar", False,
                       "preparado: sem escrita geometrica real")


class SceneEditor:
    """Camada de interacao sobre Preview/Modelo (sem renderer novo).

    Usa a selecao global (Inspetor) e o EventBus existente; nunca
    escreve no projeto (propor_* devolve ChangeSet para aprovacao).
    """

    def __init__(self, inspetor=None, eventos=None) -> None:
        from .inspetor import Inspetor as _Inspetor

        self.viewport = ViewportState()
        self.arvore = SceneTree()
        self.inspetor = inspetor if inspetor is not None else _Inspetor()
        self.eventos = eventos
        self._destaque: str | None = None

    # ----- modos -----

    def definir_modo(self, modo: str) -> str:
        if modo not in MODOS_F39:
            raise ErroELiXX(f"Scene: modo em {MODOS_F39}.")
        self.viewport.modo = modo
        return modo

    # ----- viewport: zoom / pan / fit / center -----

    def definir_zoom(self, nivel) -> float:
        self.viewport.set_zoom(nivel)
        return self.viewport.fator()

    def zoom_mais(self):
        niveis = [z for z in ZOOM_F39 if z != "Ajustar"]
        atual = self.viewport.zoom
        if atual == "Ajustar":
            return self.definir_zoom(100)
        pos = niveis.index(atual)
        return self.definir_zoom(niveis[min(pos + 1, len(niveis) - 1)])

    def zoom_menos(self):
        niveis = [z for z in ZOOM_F39 if z != "Ajustar"]
        atual = self.viewport.zoom
        if atual == "Ajustar":
            return self.definir_zoom(100)
        pos = niveis.index(atual)
        return self.definir_zoom(niveis[max(pos - 1, 0)])

    def ajustar(self) -> str:
        self.viewport.set_zoom("Ajustar")
        self.viewport.offset_x = 0.0
        self.viewport.offset_y = 0.0
        return "Ajustar"

    def pan(self, dx: float, dy: float) -> list:
        return self.viewport.mover(dx, dy)

    def centralizar(self) -> list:
        self.viewport.offset_x = 0.0
        self.viewport.offset_y = 0.0
        return [0.0, 0.0]

    def fit(self, largura: float, altura: float,
            conteudo_w: float = 800.0,
            conteudo_h: float = 600.0) -> float:
        """Zoom real que cabe o conteudo (sem label falso)."""
        largura = _finito(largura, "largura")
        altura = _finito(altura, "altura")
        conteudo_w = _finito(conteudo_w, "conteudo_w")
        conteudo_h = _finito(conteudo_h, "conteudo_h")
        if largura <= 0 or altura <= 0 or conteudo_w <= 0 \
                or conteudo_h <= 0:
            raise ErroELiXX("Scene: dimensoes positivas.")
        alvo = min(largura / conteudo_w, altura / conteudo_h) * 100.0
        niveis = sorted(z for z in ZOOM_F39 if z != "Ajustar")
        escolhido = niveis[0]
        for nivel in niveis:
            if nivel <= alvo:
                escolhido = nivel
        self.viewport.set_zoom(escolhido)
        self.centralizar()
        return self.viewport.fator()

    # ----- grid / snap -----

    def alternar_grid(self) -> bool:
        self.viewport.grid = not self.viewport.grid
        return self.viewport.grid

    def definir_snap(self, passo: int) -> int:
        if passo not in SNAPS_F39:
            raise ErroELiXX(f"Scene: snap em {SNAPS_F39}.")
        self.viewport.snap = passo
        return passo

    def aplicar_snap(self, valor: float) -> float:
        return snap_valor(valor, self.viewport.snap)

    # ----- arvore -----

    def construir_arvore(self, modelo) -> SceneTree:
        return self.arvore.construir(modelo)

    # ----- selecao (global; bidirecional) -----

    def selecionar(self, node_id: str,
                   origem: str = "scene") -> dict:
        """Seleciona no da arvore na selecao global existente."""
        nid = _texto_curto(node_id, 200).strip()
        if not nid:
            raise ErroELiXX("Scene: node_id nao vazio.")
        if nid not in self.arvore.nos:
            raise ErroELiXX(f'Scene: no "{nid}" ausente.')
        no = self.arvore.nos[nid]
        tipo = "personagem" if no.tipo == "personagem" else "no"
        sel = Selecao(tipo, nid, origem)
        self.inspetor.selecionar(sel)
        self._destaque = nid
        if self.eventos is not None:
            self.eventos.emitir("selecionado", sel.to_dict())
            try:
                self.eventos.emitir("node_selected",
                                    {"node_id": nid})
            except ErroELiXX:
                pass
        return sel.to_dict()

    def selecao_atual(self) -> dict:
        return self.inspetor.selecao.to_dict()

    def destaque(self) -> dict | None:
        """Indicacao visual discreta (outline/bbox do no real)."""
        if self._destaque is None:
            return None
        return {"node_id": self._destaque, "estilo": "outline",
                "accent": True}

    def limpar_selecao(self) -> None:
        from .inspetor import Selecao as _Sel

        self.inspetor.selecionar(_Sel.vazia_sel())
        self._destaque = None

    # ----- bounding box / gizmos -----

    def bbox_entidade(self, modelo, ent_id: str) -> BoundingBox:
        """BBox de dados reais (inspecionar_no; sem invencao)."""
        ent = next((e for e in modelo.entidades()
                    if e.id == str(ent_id)), None)
        if ent is None:
            raise ErroELiXX(f'Scene: entidade "{ent_id}" ausente.')
        dados = ent.dados if isinstance(ent.dados, dict) else {}
        props = {"x": dados.get("x"), "y": dados.get("y"),
                 "largura": dados.get("largura"),
                 "altura": dados.get("altura"),
                 "rotacao": dados.get("rotacao")}
        props = {k: v for k, v in props.items() if v is not None}
        return BoundingBox.de_props(props)

    def gizmo_atual(self) -> GizmoStatus | None:
        gizmo = gizmo_para_modo(self.viewport.modo)
        if gizmo is None:
            return None
        return gizmo_status(self.viewport.modo)

    # ----- edicao via proposta (nunca escreve direto) -----

    def propor_mover(self, workspace, modelo, ent_id: str,
                     novo_x: float, novo_y: float):
        """Move -> ChangeSet proposto (snap aplicado; sem escrita).

        Eixo ELiXX real: a propriedade `posicao` ("X Y"). A proposta
        mostra o antes/depois e nunca escreve no arquivo.
        """
        from .ux import propor_transformacao

        x = self.aplicar_snap(_finito(novo_x, "novo_x"))
        y = self.aplicar_snap(_finito(novo_y, "novo_y"))

        def _txt(v: float) -> str:
            return str(int(v)) if float(v).is_integer() else str(v)

        return propor_transformacao(workspace, modelo, ent_id,
                                    {"posicao": f"{_txt(x)} {_txt(y)}"},
                                    snap=0)

    def propor_transformar(self, workspace, modelo, ent_id: str,
                           props: dict):
        """Transformacao controlada -> ChangeSet (sem escrita)."""
        from .ux import propor_transformacao

        if not isinstance(props, dict) or not props:
            raise ErroELiXX("Scene: props nao vazias.")
        if self.viewport.modo not in ("Mover", "Selecionar"):
            gizmo = gizmo_para_modo(self.viewport.modo)
            if gizmo is not None and not gizmo_status(
                    self.viewport.modo).disponivel:
                raise ErroELiXX(
                    f'Scene: modo "{self.viewport.modo}" preparado, '
                    "sem transformacao real.")
        return propor_transformacao(workspace, modelo, ent_id,
                                    dict(props),
                                    snap=self.viewport.snap)

    # ----- toolbar -----

    def toolbar(self) -> list[dict]:
        return [dict(item) for item in ITENS_TOOLBAR]

    # ----- serializacao -----

    def to_dict(self) -> dict:
        return {"viewport": self.viewport.to_dict(),
                "selecao": self.selecao_atual(),
                "destaque": self._destaque,
                "nos": len(self.arvore.nos)}

    @staticmethod
    def from_dict(dados: dict, inspetor=None,
                  eventos=None) -> SceneEditor:
        if not isinstance(dados, dict):
            raise ErroELiXX("Scene: dict para restaurar.")
        editor = SceneEditor(inspetor=inspetor, eventos=eventos)
        editor.viewport = ViewportState.from_dict(
            dados.get("viewport", {}))
        return editor

    def __repr__(self) -> str:
        return (f"SceneEditor({self.viewport.modo} "
                f"{self.viewport.zoom} {len(self.arvore.nos)} nos)")


ITENS_TOOLBAR = (
    {"id": "scene_selecionar", "rotulo": "Selecionar",
     "tooltip": "Selecionar (V)", "grupo": "modo"},
    {"id": "scene_mover", "rotulo": "Mover",
     "tooltip": "Mover (G)", "grupo": "modo"},
    {"id": "scene_escalar", "rotulo": "Escalar",
     "tooltip": "Escalar (S) — preparado", "grupo": "modo"},
    {"id": "scene_girar", "rotulo": "Girar",
     "tooltip": "Girar (R) — preparado", "grupo": "modo"},
    {"id": "scene_ajustar", "rotulo": "Ajustar",
     "tooltip": "Ajustar (F) — preparado", "grupo": "modo"},
    {"id": "zoom_menos", "rotulo": "-",
     "tooltip": "Reduzir zoom", "grupo": "zoom"},
    {"id": "zoom_rotulo", "rotulo": "100%",
     "tooltip": "Nivel atual de zoom", "grupo": "zoom"},
    {"id": "zoom_mais", "rotulo": "+",
     "tooltip": "Ampliar zoom", "grupo": "zoom"},
    {"id": "scene_grid", "rotulo": "Grid",
     "tooltip": "Grade (respeita zoom/pan)", "grupo": "vista"},
    {"id": "scene_snap", "rotulo": "Snap",
     "tooltip": "Snap: livre/1/5/10", "grupo": "vista"},
)
"""Toolbar compacta (modo | zoom | vista; so dados)."""


class SceneToolbar:
    """Modelo da toolbar (sem Tk; a UI apenas le)."""

    def __init__(self, editor: SceneEditor) -> None:
        if not isinstance(editor, SceneEditor):
            raise ErroELiXX("Toolbar espera SceneEditor.")
        self.editor = editor

    def itens(self) -> list[dict]:
        saida = []
        for item in ITENS_TOOLBAR:
            copia = dict(item)
            if copia["id"] == "zoom_rotulo":
                zoom = self.editor.viewport.zoom
                copia["rotulo"] = (f"{zoom}%" if zoom != "Ajustar"
                                   else "Ajustar")
            if copia["id"] == "scene_grid":
                copia["ativo"] = self.editor.viewport.grid
            if copia["id"] == "scene_snap":
                copia["rotulo"] = (f"Snap {self.editor.viewport.snap}"
                                   if self.editor.viewport.snap
                                   else "Snap")
            saida.append(copia)
        return saida

    def acionar(self, item_id: str) -> dict:
        """Despacha acao real (modos e vista; zoom honesto)."""
        acao = str(item_id)
        ed = self.editor
        mapa_modo = {"scene_selecionar": "Selecionar",
                     "scene_mover": "Mover",
                     "scene_escalar": "Escalar",
                     "scene_girar": "Girar",
                     "scene_ajustar": "Ajustar"}
        if acao in mapa_modo:
            return {"ok": True, "modo": ed.definir_modo(
                mapa_modo[acao])}
        if acao == "zoom_mais":
            fator = ed.zoom_mais()
            return {"ok": True, "zoom": ed.viewport.zoom,
                    "fator": fator}
        if acao == "zoom_menos":
            fator = ed.zoom_menos()
            return {"ok": True, "zoom": ed.viewport.zoom,
                    "fator": fator}
        if acao == "scene_grid":
            return {"ok": True, "grid": ed.alternar_grid()}
        if acao == "scene_snap":
            ordem = list(SNAPS_F39)
            prox = ordem[(ordem.index(ed.viewport.snap) + 1)
                         % len(ordem)]
            return {"ok": True, "snap": ed.definir_snap(prox)}
        if acao == "zoom_rotulo":
            return {"ok": True, "zoom": ed.viewport.zoom,
                    "fator": ed.viewport.fator()}
        raise ErroELiXX(f'Scene: item "{acao}" desconhecido.')

    def __repr__(self) -> str:
        return f"SceneToolbar({self.editor.viewport.modo})"


class WorkspaceModes:
    """Adaptive workspace (so visibilidade; sem destruir estado)."""

    def __init__(self) -> None:
        self.modo = "DEFAULT"

    def aplicar(self, layout, modo: str) -> list[str]:
        if modo not in MODOS_WORKSPACE:
            raise ErroELiXX(f"Workspace: modo em {MODOS_WORKSPACE}.")
        from .workspace_ui import PAINEIS

        desejados = PAINEIS_POR_MODO[modo]
        for painel in PAINEIS:
            layout.visivel[painel] = painel in desejados
        self.modo = modo
        return list(layout.paineis_visiveis())

    def descricao(self, modo: str) -> str:
        textos = {
            "DEFAULT": "Project + Scene + Inspector",
            "CODE": "Project + Code",
            "SCENE": "Scene dominante",
            "AGENT": "Agent dominante",
            "REVIEW": "Code + Diff + Changes",
        }
        if modo not in textos:
            raise ErroELiXX(f"Workspace: modo em {MODOS_WORKSPACE}.")
        return textos[modo]

    def __repr__(self) -> str:
        return f"WorkspaceModes({self.modo})"


class BottomWorkspace:
    """Area inferior compartilhada (uma ou poucas abas abertas)."""

    def __init__(self, aberta: str = "CONSOLE") -> None:
        if aberta not in ABAS_FUNDO:
            raise ErroELiXX(f"Fundo: aba em {ABAS_FUNDO}.")
        self.aberta: str | None = aberta
        self.recentes: list[str] = [aberta]

    def abrir(self, aba: str) -> str:
        if aba not in ABAS_FUNDO:
            raise ErroELiXX(f"Fundo: aba em {ABAS_FUNDO}.")
        self.aberta = aba
        if aba in self.recentes:
            self.recentes.remove(aba)
        self.recentes.insert(0, aba)
        self.recentes = self.recentes[: len(ABAS_FUNDO)]
        return aba

    def fechar(self) -> None:
        self.aberta = None

    def alternar(self, aba: str) -> str | None:
        if aba not in ABAS_FUNDO:
            raise ErroELiXX(f"Fundo: aba em {ABAS_FUNDO}.")
        if self.aberta == aba:
            self.fechar()
            return None
        return self.abrir(aba)

    def painel_para(self, aba: str) -> str:
        if aba not in ABA_PARA_PAINEL:
            raise ErroELiXX(f"Fundo: aba em {ABAS_FUNDO}.")
        return ABA_PARA_PAINEL[aba]

    def to_dict(self) -> dict:
        return {"aberta": self.aberta,
                "recentes": list(self.recentes)}

    @staticmethod
    def from_dict(dados: dict) -> BottomWorkspace:
        if not isinstance(dados, dict):
            raise ErroELiXX("Fundo: dict para restaurar.")
        fundo = BottomWorkspace(dados.get("aberta", "CONSOLE")
                                or "CONSOLE")
        for aba in reversed(dados.get("recentes", [])):
            if aba in ABAS_FUNDO and aba != fundo.aberta:
                fundo.recentes.append(aba)
        fundo.recentes = fundo.recentes[: len(ABAS_FUNDO)]
        return fundo

    def __repr__(self) -> str:
        return f"BottomWorkspace({self.aberta})"


class StatusBar:
    """Barra de status pequena (so texto curto e seguro)."""

    def __init__(self, texto: str = "Ready") -> None:
        self.texto = _texto_curto(texto, 120) or "Ready"

    def atualizar(self, texto: str) -> str:
        self.texto = _texto_curto(texto, 120) or "Ready"
        return self.texto

    def to_dict(self) -> dict:
        return {"texto": self.texto}

    def __repr__(self) -> str:
        return f"StatusBar({self.texto})"


def montar_status(projeto: str = "", arquivo: str = "",
                  entidades: int = 0, mudancas: int = 0,
                  agente: str = "ready",
                  salvo: bool = True) -> str:
    """Texto curto: '3 entities | 2 changes | main.elixx' etc."""
    try:
        total_ent = int(entidades)
        total_mud = int(mudancas)
    except (TypeError, ValueError):
        raise ErroELiXX("Status: contagens inteiras.")
    if total_ent < 0 or total_mud < 0:
        raise ErroELiXX("Status: contagens >= 0.")
    agente_txt = _texto_curto(agente or "ready", 30).strip() or "ready"
    partes = []
    if projeto.strip():
        partes.append(_texto_curto(projeto.strip(), 60))
    if total_ent or total_mud:
        partes.append(f"{total_ent} entities")
        partes.append(f"{total_mud} changes")
    if arquivo.strip():
        partes.append(_texto_curto(arquivo.strip(), 60))
    if not salvo:
        partes.append("Unsaved")
    partes.append(f"Agent {agente_txt}")
    return " | ".join(partes) if partes else "Ready"


def erro_amigavel(exc: BaseException) -> str:
    """Erro curto sem traceback (primeira linha, ate 200 chars)."""
    detalhe = str(exc).split("\n")[0][:200].strip()
    return f"Falha: {detalhe}" if detalhe else "Falha inesperada."


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


def buscar_palette_f39(texto: str = "") -> list[dict]:
    """Busca comandos F39 (propria; sem tocar COMANDOS_PALETTE)."""
    termo = _norm(texto)
    saida = []
    for cid, rotulo in COMANDOS_F39:
        if not termo or termo in _norm(f"{cid} {rotulo}"):
            saida.append({"id": cid, "rotulo": rotulo})
    return saida


def executar_palette_f39(editor: SceneEditor, layout,
                         comando_id: str,
                         modos: WorkspaceModes | None = None,
                         fundo: BottomWorkspace | None = None,
                         foco=None) -> dict:
    """Executa comando F39 (cena/layout/foco; sem efeitos colaterais
    fora do estado do Studio)."""
    cid = str(comando_id)
    mapa_modo = {"scene_selecionar": "Selecionar",
                 "scene_mover": "Mover",
                 "scene_escalar": "Escalar",
                 "scene_girar": "Girar",
                 "scene_ajustar": "Ajustar"}
    if cid in mapa_modo:
        return {"ok": True, "modo": editor.definir_modo(
            mapa_modo[cid])}
    if cid == "scene_grid":
        return {"ok": True, "grid": editor.alternar_grid()}
    if cid == "scene_snap":
        ordem = list(SNAPS_F39)
        prox = ordem[(ordem.index(editor.viewport.snap) + 1)
                     % len(ordem)]
        return {"ok": True, "snap": editor.definir_snap(prox)}
    if cid in ("layout_scene", "layout_code", "layout_agent",
               "layout_review"):
        modo = cid.split("_", 1)[1].upper()
        return {"ok": True, "paineis": (modos or WorkspaceModes())
                .aplicar(layout, modo)}
    if cid == "foco_atual":
        if foco is None:
            from .ux import FocusState as _Focus

            foco = _Focus()
        atual = [p for p in ("preview", "inspector")
                 if p in layout.paineis_visiveis()]
        return {"ok": True,
                "paineis": foco.entrar(layout, atual or ["preview"])}
    if cid == "sair_do_foco":
        if foco is None or getattr(foco, "ativo", None) is None:
            raise ErroELiXX("Scene: foco inativo.")
        return {"ok": True, "paineis": foco.sair(layout)}
    raise ErroELiXX(f'Scene: comando "{cid}" desconhecido.')


def conflitos_f39() -> list[dict]:
    """Atalhos F39 que ja existem no mapa global (sem substituir)."""
    from .app import ATALHOS

    saida = []
    for tecla in ATALHOS_F39:
        if tecla in ATALHOS:
            saida.append({"tecla": tecla,
                          "global": ATALHOS[tecla],
                          "contextual": ATALHOS_F39[tecla],
                          "regra": "global prevalece; F39 so com "
                                   "cena focada"})
    return saida


def ir_para_codigo(editor_modelo, modelo, ent_id: str) -> dict:
    """Selecao visual -> regiao do codigo (F27+F32; sem invencao)."""
    from .codigo.localizacao import localizar_entidade

    ent = next((e for e in modelo.entidades()
                if e.id == str(ent_id)), None)
    if ent is None:
        raise ErroELiXX(f'Scene: entidade "{ent_id}" ausente.')
    if not ent.arquivo:
        raise ErroELiXX("Scene: entidade sem arquivo.")
    doc = getattr(editor_modelo, "documento", None)
    texto = getattr(doc, "texto", "") if doc is not None else ""
    try:
        loc = localizar_entidade(ent, texto)
        linha = int(loc.inicio_linha)
    except ErroELiXX:
        if not ent.linha:
            raise ErroELiXX("Scene: sem regiao de codigo.")
        linha = int(ent.linha)
    editor_modelo.ir_para(linha)
    return {"ok": True, "arquivo": ent.arquivo, "linha": linha,
            "entidade": ent.id}


def entidade_do_cursor(modelo, arquivo: str, linha: int):
    """Regiao do codigo -> entidade (F27+F32; None sem invencao)."""
    from .ux import entidade_na_linha

    try:
        numero = int(linha)
    except (TypeError, ValueError):
        raise ErroELiXX("Scene: linha inteira.")
    if numero < 1:
        raise ErroELiXX("Scene: linha >= 1.")
    return entidade_na_linha(modelo, str(arquivo), numero)
