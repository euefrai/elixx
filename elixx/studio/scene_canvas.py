"""Scene Canvas real (Fase 40) — cena visual sobre dados reais.

Codigo -> Parser -> AST -> F27 -> Scene/Character/Geometry -> Canvas.
Nada e inventado: posicao/tamanho/imagem/personagem/asset/animacao
so aparecem com origem real; sem ela, placeholder honesto.

Reutiliza F07/F10/F11/F12/F13/F16/F17/F21/F23/F24/F25 (assets,
Transform, animacao, Character, World, sintese, Geometry, rigging,
deformation, preview/cena) e F25-F39 do Studio. Sem segundo
renderer/parser/modelo/selecao/EventBus/Transform/Geometry/assets.
Tudo headless e serializavel; o Tk (quando houver display) apenas
desenha este estado via desenhar().
"""

from __future__ import annotations

import math
import unicodedata

from ..erros import ErroELiXX
from .cena import ViewportState
from .inspetor import Selecao

__all__ = [
    "KINDS",
    "PLACEHOLDER_KINDS",
    "COMANDOS_F40",
    "ATALHOS_F40",
    "PROPORCOES_SCENE",
    "TAMANHOS_PADRAO",
    "RenderObject",
    "SceneCanvas",
    "AnimationPreview",
    "MotionPreview",
    "cena_de_texto",
    "estado_asset",
    "carregar_imagem",
    "ficha_objeto",
    "aplicar_edicao",
    "contexto_cena",
    "proporcoes_scene",
    "aplicar_layout_scene",
    "aplicar_compacto",
    "buscar_palette_f40",
    "executar_palette_f40",
    "conflitos_f40",
    "desenhar",
    "abrir_janela_cena",
]

KINDS = ("janela", "personagem", "parte", "imagem", "texto",
         "componente", "grupo", "objeto", "forma")
"""Tipos renderizaveis (somente com dados reais)."""

PLACEHOLDER_KINDS = ("PERSONAGEM", "IMAGEM", "COMPONENTE", "GRUPO",
                     "TEXTO")
"""Placeholders elegantes (sem asset visual real)."""

COMANDOS_F40 = (
    ("scene_fit", "Scene: Fit"),
    ("scene_center_selection", "Scene: Center Selection"),
    ("scene_toggle_grid", "Scene: Toggle Grid"),
    ("scene_toggle_debug", "Scene: Toggle Debug"),
    ("scene_play_animation", "Scene: Play Animation"),
    ("scene_pause_animation", "Scene: Pause Animation"),
    ("scene_stop_animation", "Scene: Stop Animation"),
    ("scene_zoom_in", "Scene: Zoom In"),
    ("scene_zoom_out", "Scene: Zoom Out"),
    ("scene_reset_zoom", "Scene: Reset Zoom"),
)
"""Palette F40 (aditiva; F37/F39 intactas)."""

ATALHOS_F40 = {
    "Home": "scene_fit",
    "F": "scene_center_selection",
    "+": "scene_zoom_in",
    "-": "scene_zoom_out",
    "0": "scene_reset_zoom",
    "G": "scene_toggle_grid",
    "D": "scene_toggle_debug",
}
"""Atalhos contextuais (sem substituir o mapa global)."""

PROPORCOES_SCENE = {"project": 0.20, "canvas": 0.57,
                    "inspector": 0.23}
"""SCENE: Project 20% + Canvas 57% + Inspector 23% (fracoes)."""

TAMANHOS_PADRAO = {
    "personagem": (120.0, 160.0),
    "parte": (60.0, 60.0),
    "imagem": (120.0, 120.0),
    "texto": (100.0, 24.0),
    "componente": (120.0, 60.0),
    "grupo": (200.0, 150.0),
    "objeto": (80.0, 80.0),
    "forma": (80.0, 80.0),
    "janela": (800.0, 600.0),
}
"""Tamanho quando o no nao informa (flag tamanho_derivado)."""


def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f"Canvas: {o_que} numerico.")
    if not math.isfinite(numero):
        raise ErroELiXX(f"Canvas: {o_que} finito.")
    return numero


def _texto_curto(valor, limite: int = 200) -> str:
    texto = str(valor)
    if len(texto) > limite:
        raise ErroELiXX("Canvas: texto excede limite.")
    for ch in texto:
        if ord(ch) < 32 and ch not in ("\n", "\t"):
            raise ErroELiXX("Canvas: texto com controle invalido.")
    return texto


def cena_de_texto(texto: str,
                 entrada: str = "main.elixx") -> dict:
    """Pipeline oficial -> {cena, personagens, diagnosticos}.

    Mesmos passos do preview (diagnosticar, parse, expandir,
    validar, Executor, ConstrutorCena, vincular_personagens).
    """
    if not isinstance(texto, str):
        raise ErroELiXX("Canvas: texto precisa de string.")
    from .editor import diagnosticar_texto

    diags = diagnosticar_texto(texto, entrada)
    erros = [d for d in diags if d.severidade == "error"]
    if erros:
        return {"ok": False, "cena": None, "personagens": {},
                "diagnosticos": diags}
    try:
        from ..compilador.componentes import expandir_componentes
        from ..compilador.lexer import tokenizar
        from ..compilador.parser import Parser
        from ..compilador.semantica import validar
        from ..runtime.nucleo import Executor
        from ..visual.cena import ConstrutorCena
        from ..visual.personagem import vincular_personagens

        prog = Parser(tokenizar(texto)).parse()
        expandir_componentes(prog)
        validar(prog)
        cena = ConstrutorCena().de_objetos(
            Executor().executar(prog, []).objetos)
        try:
            personagens = dict(vincular_personagens(cena))
        except ErroELiXX:
            personagens = {}
        return {"ok": True, "cena": cena,
                "personagens": personagens, "diagnosticos": diags}
    except Exception as exc:
        detalhe = str(exc).split("\n")[0][:200]
        return {"ok": False, "cena": None, "personagens": {},
                "diagnosticos": diags, "erro": detalhe}


def estado_asset(no, workspace=None) -> dict:
    """Asset do no via GerenciadorAssets (sem baixar nada).

    Status: sem_asset | remoto | encontrado | ausente | invalido.
    """
    caminho = str(getattr(no, "caminho_recurso", "") or "")
    if not caminho.strip():
        return {"status": "sem_asset", "caminho": "",
                "tipo": ""}
    if caminho.strip().lower().startswith(("http://", "https://",
                                           "data:")):
        return {"status": "remoto", "caminho": caminho[:200],
                "tipo": "remoto"}
    tipo = ""
    try:
        from ..multimidia.recursos import detectar_tipo

        tipo = str(detectar_tipo(caminho))
    except Exception:
        tipo = ""
    if workspace is None:
        return {"status": "nao_verificado",
                "caminho": caminho[:200], "tipo": tipo}
    try:
        from .assets import GerenciadorAssets

        rel = caminho.replace("\\", "/").lstrip("./")
        veredito = GerenciadorAssets(workspace).validar(rel)
        if veredito.get("valido"):
            return {"status": "encontrado",
                    "caminho": caminho[:200], "tipo": tipo}
        codigo = str(veredito.get("codigo", ""))
        if "ausente" in codigo.lower() or "nao" in codigo.lower():
            return {"status": "ausente",
                    "caminho": caminho[:200], "tipo": tipo}
        return {"status": "invalido",
                "caminho": caminho[:200], "tipo": tipo,
                "motivo": str(veredito.get("motivo", ""))[:120]}
    except ErroELiXX as exc:
        return {"status": "invalido",
                "caminho": caminho[:200], "tipo": tipo,
                "motivo": str(exc).split("\n")[0][:120]}


def carregar_imagem(caminho: str):
    """PhotoImage real (PNG/GIF; JPEG via Pillow) ou None.

    Sem display ou arquivo invalido: None (placeholder assume).
    Nunca levanta para o canvas.
    """
    try:
        texto = str(caminho)
        baixo = texto.lower()
        import tkinter as tk

        if baixo.endswith((".png", ".gif", ".ppm", ".pgm")):
            return tk.PhotoImage(file=texto)
        if baixo.endswith((".jpg", ".jpeg")):
            try:
                from PIL import Image, ImageTk

                return ImageTk.PhotoImage(Image.open(texto))
            except Exception:
                return None
        if baixo.endswith(".svg"):
            return None
        return None
    except Exception:
        return None


class RenderObject:
    """Objeto visual com origem real (no/Character + entidade)."""

    def __init__(self, obj_id: str, kind: str, rotulo: str = "",
                 x: float = 0.0, y: float = 0.0,
                 largura: float | None = None,
                 altura: float | None = None,
                 camada: float = 0.0, seq: int = 0,
                 visivel: bool = True,
                 parent_id: str | None = None,
                 ent_id: str | None = None,
                 asset: dict | None = None,
                 placeholder: bool = False,
                 tamanho_derivado: bool = False,
                 texto: str = "", ajuste: str = "conter",
                 fundo_hex: str | None = None,
                 cor_hex: str | None = None,
                 rotacao: float = 0.0) -> None:
        if kind not in KINDS:
            raise ErroELiXX(f"Canvas: kind em {KINDS}.")
        self.id = _texto_curto(obj_id)
        if not self.id.strip():
            raise ErroELiXX("Canvas: id nao vazio.")
        self.kind = kind
        self.rotulo = _texto_curto(rotulo or self.id, 120)
        self.x = _finito(x, "x")
        self.y = _finito(y, "y")
        if largura is None or altura is None:
            padrao = TAMANHOS_PADRAO[kind]
            largura = padrao[0] if largura is None else largura
            altura = padrao[1] if altura is None else altura
            tamanho_derivado = True
        self.largura = _finito(largura, "largura")
        self.altura = _finito(altura, "altura")
        if self.largura <= 0 or self.altura <= 0:
            raise ErroELiXX("Canvas: tamanho positivo.")
        self.camada = _finito(camada, "camada")
        self.seq = int(seq)
        self.visivel = bool(visivel)
        self.parent_id = parent_id
        self.ent_id = ent_id
        self.asset = dict(asset or {"status": "sem_asset"})
        self.placeholder = bool(placeholder)
        self.tamanho_derivado = bool(tamanho_derivado)
        self.texto = _texto_curto(texto, 500)
        self.ajuste = str(ajuste) if str(ajuste) in (
            "conter", "cobrir", "original") else "conter"
        self.fundo_hex = fundo_hex
        self.cor_hex = cor_hex
        self.rotacao = _finito(rotacao, "rotacao")

    @staticmethod
    def de_no(no, kind: str, obj_id: str, parent_id=None,
              ent_id=None, workspace=None) -> RenderObject:
        """NoVisual real -> RenderObject (globals via F10)."""
        from ..visual.transform import transform_de_no

        try:
            t = transform_de_no(no)
            x, y = float(t.x), float(t.y)
            rot = float(t.rotacao)
        except Exception:
            x, y, rot = 0.0, 0.0, 0.0
        larg = getattr(no, "largura", None)
        alt = getattr(no, "altura", None)
        asset = estado_asset(no, workspace)
        precisa_asset = kind in ("personagem", "imagem",
                                 "componente")
        placeholder = (precisa_asset and asset.get("status") in
                       ("sem_asset", "ausente", "nao_verificado",
                        "invalido"))
        return RenderObject(
            obj_id, kind,
            rotulo=str(getattr(no, "nome", "") or obj_id),
            x=x, y=y, largura=larg, altura=alt,
            camada=float(getattr(no, "camada", 0.0) or 0.0),
            seq=int(getattr(no, "_seq", 0) or 0),
            visivel=bool(getattr(no, "visivel", True)),
            parent_id=parent_id, ent_id=ent_id, asset=asset,
            placeholder=placeholder,
            texto=str(getattr(no, "texto", "") or ""),
            ajuste=str(getattr(no, "ajuste", "conter") or "conter"),
            fundo_hex=getattr(no, "fundo_hex", None),
            cor_hex=getattr(no, "cor_hex", None),
            rotacao=rot)

    def bbox_global(self, objetos: dict) -> dict:
        """BBox somando a cadeia de pais (F10 combinar)."""
        from ..visual.transform import combinar
        from ..visual.transform import Transform

        acc = Transform(x=self.x, y=self.y)
        atual = self
        while atual.parent_id and atual.parent_id in objetos:
            pai = objetos[atual.parent_id]
            acc = combinar(Transform(x=pai.x, y=pai.y), acc)
            atual = pai
        return {"x": float(acc.x), "y": float(acc.y),
                "largura": self.largura, "altura": self.altura}

    def assinatura(self) -> tuple:
        return (self.id, self.kind, self.rotulo, self.x, self.y,
                self.largura, self.altura, self.camada,
                self.visivel, self.parent_id,
                self.asset.get("status"), self.placeholder,
                self.texto, self.ajuste)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind,
                "rotulo": self.rotulo, "x": self.x, "y": self.y,
                "largura": self.largura, "altura": self.altura,
                "camada": self.camada, "visivel": self.visivel,
                "parent_id": self.parent_id, "ent_id": self.ent_id,
                "asset": dict(self.asset),
                "placeholder": self.placeholder,
                "tamanho_derivado": self.tamanho_derivado,
                "texto": self.texto, "ajuste": self.ajuste,
                "rotacao": self.rotacao}

    def __repr__(self) -> str:
        return f"RenderObject({self.kind} {self.id})"


class SceneCanvas:
    """Grafo visual da cena (camada sobre Scene/Character)."""

    def __init__(self, inspetor=None, eventos=None) -> None:
        from .inspetor import Inspetor as _Inspetor

        self.viewport = ViewportState()
        self.objetos: list[RenderObject] = []
        self.por_id: dict[str, RenderObject] = {}
        self.inspetor = (inspetor if inspetor is not None
                         else _Inspetor())
        self.eventos = eventos
        self.debug = False
        self.fundo = "dark"
        self.selecionados: list[str] = []
        self.rebuilds = 0

    # ----- construcao -----

    def montar(self, cena, personagens=None,
               modelo=None, workspace=None) -> SceneCanvas:
        """Cena real -> objetos (ordem por camada, F10/F13/F25)."""
        from ..visual.transform import ordem_visual

        self.objetos = []
        self.por_id = {}
        self.selecionados = []
        pers = dict(personagens or {})
        nomes_ent = {}
        if modelo is not None:
            try:
                from .modelo.consulta import ConsultaSemantica

                q = ConsultaSemantica(modelo)
                for ent in modelo.entidades():
                    nomes_ent.setdefault(ent.nome, ent.id)
            except ErroELiXX:
                nomes_ent = {}
        seq = 0
        for janela in list(getattr(cena, "janelas", [])):
            jid = f"janela:{janela.nome}"
            self._adicionar_no(janela, "janela", jid, None,
                               nomes_ent, workspace)
            for filho in ordem_visual(janela):
                seq += 1
                self._adicionar_filho(filho, jid, nomes_ent,
                                      pers, workspace, seq)
        self.rebuilds += 1
        return self

    def _adicionar_no(self, no, kind, obj_id, parent_id,
                      nomes_ent, workspace) -> RenderObject:
        ent = nomes_ent.get(getattr(no, "nome", ""), None)
        if kind == "personagem" and ent is None:
            ent = nomes_ent.get(getattr(no, "nome", ""), None)
        obj = RenderObject.de_no(no, kind, obj_id, parent_id,
                                 ent, workspace)
        self.objetos.append(obj)
        self.por_id[obj.id] = obj
        return obj

    def _adicionar_filho(self, no, parent_id, nomes_ent, pers,
                         workspace, seq) -> None:
        tipo = str(getattr(no, "tipo", "objeto"))
        nome = str(getattr(no, "nome", ""))
        if tipo == "personagem" and nome in pers:
            pid = f"personagem:{nome}"
            ent = nomes_ent.get(nome)
            obj = RenderObject.de_no(no, "personagem", pid,
                                     parent_id, ent, workspace)
            self.objetos.append(obj)
            self.por_id[pid] = obj
            ch = pers[nome]
            try:
                partes = sorted(ch.partes)
            except Exception:
                partes = []
            for parte_nome in partes:
                try:
                    pno = ch.obter_parte(parte_nome).no
                    tg = ch.obter_transform_global(parte_nome)
                    gpid = f"parte:{nome}.{parte_nome}"
                    pobj = RenderObject(
                        gpid, "parte", rotulo=parte_nome,
                        x=float(tg.x), y=float(tg.y),
                        largura=getattr(pno, "largura", None),
                        altura=getattr(pno, "altura", None),
                        camada=float(
                            getattr(pno, "camada", 0.0) or 0.0),
                        parent_id=pid,
                        ent_id=nomes_ent.get(parte_nome),
                        asset=estado_asset(pno, workspace),
                        placeholder=True,
                        texto=str(getattr(pno, "texto",
                                          "") or ""))
                    self.objetos.append(pobj)
                    self.por_id[gpid] = pobj
                except (ErroELiXX, ValueError, TypeError,
                        AttributeError):
                    continue
            return
        kind = tipo if tipo in KINDS else "objeto"
        oid = f"{kind}:{nome}" if nome else f"{kind}:{seq}"
        if oid in self.por_id:
            oid = f"{oid}#{seq}"
        self._adicionar_no(no, kind, oid, parent_id, nomes_ent,
                           workspace)

    # ----- ordem / camadas -----

    def ordem_render(self) -> list[RenderObject]:
        """Ordem real (camada, seq); nunca alfabetica."""
        return sorted([o for o in self.objetos if o.visivel],
                      key=lambda o: (o.camada, o.seq))

    # ----- selecao (global) -----

    def selecionar(self, obj_id: str,
                   origem: str = "canvas") -> dict:
        oid = _texto_curto(obj_id).strip()
        if oid not in self.por_id:
            raise ErroELiXX(f'Canvas: objeto "{oid}" ausente.')
        obj = self.por_id[oid]
        tipo = ("personagem" if obj.kind == "personagem"
                else "parte" if obj.kind == "parte" else "no")
        ref = obj.ent_id or oid
        sel = Selecao(tipo, ref, origem)
        self.inspetor.selecionar(sel)
        self.selecionados = [oid]
        if self.eventos is not None:
            self.eventos.emitir("selecionado", sel.to_dict())
            try:
                self.eventos.emitir("node_selected",
                                    {"node_id": oid})
            except ErroELiXX:
                pass
        return sel.to_dict()

    def objeto_sob_ponto(self, x: float, y: float):
        """Hit-test: objeto visivel do topo sob o ponto."""
        px, py = self.viewport.da_tela(_finito(x, "x"),
                                       _finito(y, "y"))
        for obj in reversed(self.ordem_render()):
            bb = obj.bbox_global(self.por_id)
            if (bb["x"] <= px <= bb["x"] + bb["largura"]
                    and bb["y"] <= py <= bb["y"] + bb["altura"]):
                return obj
        return None

    def capacidade_multi(self) -> dict:
        return {"suportado": False,
                "motivo": "single selection oficial "
                          "(EventBus/Selection F25); sem "
                          "segundo sistema"}

    def selecionar_multiplos(self, ids: list):
        raise ErroELiXX("Canvas: multi-selecao nao suportada "
                        "(single selection oficial).")

    # ----- handles -----

    def handles_de(self, obj_id: str) -> list[dict]:
        from .scene_editor import gizmo_status

        oid = _texto_curto(obj_id).strip()
        if oid not in self.por_id:
            raise ErroELiXX(f'Canvas: objeto "{oid}" ausente.')
        obj = self.por_id[oid]
        bb = obj.bbox_global(self.por_id)
        cx = bb["x"] + bb["largura"] / 2.0
        cy = bb["y"] + bb["altura"] / 2.0
        saida = []
        st = gizmo_status("Mover")
        saida.append({"gizmo": "mover", "x": cx, "y": cy,
                      "disponivel": st.disponivel,
                      "motivo": st.motivo})
        for modo, gx, gy in (("Escalar",
                              bb["x"] + bb["largura"], bb["y"] +
                              bb["altura"]),
                             ("Girar", cx, bb["y"] - 16.0)):
            gst = gizmo_status(modo)
            saida.append({"gizmo": gst.gizmo, "x": gx, "y": gy,
                          "disponivel": gst.disponivel,
                          "motivo": gst.motivo})
        return saida

    # ----- drag -> proposta (nunca escreve) -----

    def interpretar_gesto(self, botao: str, sobre_objeto: bool,
                          modo: str | None = None) -> str:
        """Distingue pan de viewport vs drag vs selecao."""
        b = str(botao).strip().lower()
        m = modo or self.viewport.modo
        if b in ("meio", "direito", "espaco"):
            return "pan"
        if b == "esquerdo" and sobre_objeto and m == "Mover":
            return "drag_objeto"
        return "selecionar"

    def arrastar_para(self, obj_id: str, novo_x: float,
                      novo_y: float, workspace, modelo,
                      snap: int = 0):
        """Drag -> SemanticOperation -> ChangeSet (sem escrita)."""
        from .ux import propor_transformacao

        oid = _texto_curto(obj_id).strip()
        if oid not in self.por_id:
            raise ErroELiXX(f'Canvas: objeto "{oid}" ausente.')
        obj = self.por_id[oid]
        if obj.ent_id is None:
            raise ErroELiXX("Canvas: objeto sem entidade "
                            "(sem codigo correspondente).")
        if snap not in (0, 1, 5, 10):
            raise ErroELiXX("Canvas: snap em 0/1/5/10.")
        from .cena import snap_valor

        x = snap_valor(_finito(novo_x, "novo_x"), snap)
        y = snap_valor(_finito(novo_y, "novo_y"), snap)

        def _txt(v: float) -> str:
            return str(int(v)) if float(v).is_integer() else str(v)

        return propor_transformacao(workspace, modelo,
                                    obj.ent_id,
                                    {"posicao": f"{_txt(x)} "
                                                f"{_txt(y)}"},
                                    snap=0)

    # ----- viewport: fit / center / zoom selecao -----

    def limites_conteudo(self) -> dict | None:
        vis = [o for o in self.objetos if o.visivel
               and o.kind != "janela"]
        if not vis:
            vis = [o for o in self.objetos if o.visivel]
        if not vis:
            return None
        xs, ys, ds, bs = [], [], [], []
        for o in vis:
            bb = o.bbox_global(self.por_id)
            xs.append(bb["x"])
            ys.append(bb["y"])
            ds.append(bb["x"] + bb["largura"])
            bs.append(bb["y"] + bb["altura"])
        return {"x": min(xs), "y": min(ys),
                "largura": max(ds) - min(xs),
                "altura": max(bs) - min(ys)}

    def enquadrar(self, largura: float,
                  altura: float) -> dict:
        """Fit real: zoom que cabe o conteudo + centraliza."""
        from .scene_editor import SceneEditor as _SE

        limites = self.limites_conteudo()
        if limites is None:
            raise ErroELiXX("Canvas: sem objetos para fit.")
        aux = _SE()
        aux.viewport = self.viewport
        fator = aux.fit(largura, altura,
                        max(limites["largura"], 1.0),
                        max(limites["altura"], 1.0))
        cx = limites["x"] + limites["largura"] / 2.0
        cy = limites["y"] + limites["altura"] / 2.0
        self.viewport.offset_x = (float(largura) / 2.0
                                  - cx * fator)
        self.viewport.offset_y = (float(altura) / 2.0
                                  - cy * fator)
        return {"zoom": self.viewport.zoom, "fator": fator,
                "offset": [self.viewport.offset_x,
                           self.viewport.offset_y]}

    def centralizar_selecao(self, largura: float,
                            altura: float) -> dict:
        if not self.selecionados:
            raise ErroELiXX("Canvas: sem selecao.")
        obj = self.por_id[self.selecionados[0]]
        bb = obj.bbox_global(self.por_id)
        fator = self.viewport.fator()
        cx = bb["x"] + bb["largura"] / 2.0
        cy = bb["y"] + bb["altura"] / 2.0
        self.viewport.offset_x = (float(largura) / 2.0
                                  - cx * fator)
        self.viewport.offset_y = (float(altura) / 2.0
                                  - cy * fator)
        return {"id": obj.id,
                "offset": [self.viewport.offset_x,
                           self.viewport.offset_y]}

    def zoom_para_selecao(self) -> dict:
        if not self.selecionados:
            raise ErroELiXX("Canvas: sem selecao.")
        obj = self.por_id[self.selecionados[0]]
        bb = obj.bbox_global(self.por_id)
        maior = max(bb["largura"], bb["altura"])
        alvo = 200 if maior <= 80 else 150 if maior <= 200 \
            else 100 if maior <= 400 else 50
        self.viewport.set_zoom(alvo)
        return {"id": obj.id, "zoom": alvo,
                "fator": self.viewport.fator()}

    # ----- grade / reguas -----

    def ticks_grade(self, largura: float, altura: float,
                    passo: int = 20) -> dict:
        """Linhas de grade visiveis (respeita zoom/pan)."""
        if passo not in (10, 20, 40, 50, 100):
            raise ErroELiXX("Canvas: passo em 10/20/40/50/100.")
        x0, y0 = self.viewport.da_tela(0, 0)
        x1, y1 = self.viewport.da_tela(float(largura),
                                       float(altura))
        import math as _m

        vx = [p for p in range(int(_m.floor(x0 / passo))
                               * passo,
                               int(_m.ceil(x1)) + passo, passo)
              if x0 <= p <= x1]
        vy = [p for p in range(int(_m.floor(y0 / passo))
                               * passo,
                               int(_m.ceil(y1)) + passo, passo)
              if y0 <= p <= y1]
        f = self.viewport.fator()
        return {"verticais": [v * f + self.viewport.offset_x
                              for v in vx],
                "horizontais": [v * f + self.viewport.offset_y
                                for v in vy],
                "passo": passo}

    def ticks_regua(self, eixo: str, tamanho: float,
                    passo: int = 50) -> list[dict]:
        if eixo not in ("x", "y"):
            raise ErroELiXX('Canvas: eixo "x" ou "y".')
        grade = self.ticks_grade(
            tamanho if eixo == "x" else 100.0,
            tamanho if eixo == "y" else 100.0, passo)
        pos = (grade["verticais"] if eixo == "x"
               else grade["horizontais"])
        f = self.viewport.fator()
        return [{"tela": p,
                 "mundo": round((p - (self.viewport.offset_x
                                      if eixo == "x"
                                      else self.viewport.offset_y))
                                / f, 1)} for p in pos]

    # ----- fundo / debug -----

    def fundo_canvas(self) -> dict:
        from .tema import ELIXX_COLORS

        return {"estilo": self.fundo,
                "cor": ELIXX_COLORS["background"],
                "superficie": ELIXX_COLORS["surface"],
                "grade": ELIXX_COLORS["border"]}

    def fundo_para_objeto(self, obj_id: str) -> str:
        oid = _texto_curto(obj_id).strip()
        if oid not in self.por_id:
            raise ErroELiXX(f'Canvas: objeto "{oid}" ausente.')
        return "dark"

    def alternar_debug(self) -> bool:
        self.debug = not self.debug
        return self.debug

    def info_debug(self, obj_id: str) -> dict:
        oid = _texto_curto(obj_id).strip()
        if oid not in self.por_id:
            raise ErroELiXX(f'Canvas: objeto "{oid}" ausente.')
        obj = self.por_id[oid]
        bb = obj.bbox_global(self.por_id)
        return {"id": obj.id, "tipo": obj.kind,
                "posicao": [bb["x"], bb["y"]],
                "tamanho": [bb["largura"], bb["altura"]],
                "parent": obj.parent_id}

    # ----- recarga incremental -----

    def recarregar(self, texto: str,
                   entrada: str = "main.elixx") -> dict:
        """Texto -> cena -> diff; rebuild parcial quando 1 mudou."""
        saida = cena_de_texto(texto, entrada)
        if not saida["ok"] or saida["cena"] is None:
            raise ErroELiXX("Canvas: codigo com erro "
                            "(sem recarga).")
        antes = {o.id: o.assinatura() for o in self.objetos}
        novo = SceneCanvas()
        novo.montar(saida["cena"], saida["personagens"])
        depois = {o.id: o.assinatura() for o in novo.objetos}
        adicionados = sorted(set(depois) - set(antes))
        removidos = sorted(set(antes) - set(depois))
        alterados = sorted(i for i in set(antes) & set(depois)
                           if antes[i] != depois[i])
        parcial = len(adicionados) + len(removidos) + \
            len(alterados) == 1
        if parcial:
            alvo = (adicionados + removidos + alterados)[0]
            if alvo in novo.por_id:
                self.por_id[alvo] = novo.por_id[alvo]
                self.objetos = [novo.por_id.get(o.id, o)
                                for o in self.objetos]
                if alvo in adicionados:
                    self.objetos.append(novo.por_id[alvo])
            else:
                self.objetos = [o for o in self.objetos
                                if o.id != alvo]
                self.por_id.pop(alvo, None)
                self.selecionados = [s for s in self.selecionados
                                     if s != alvo]
        else:
            self.objetos = novo.objetos
            self.por_id = novo.por_id
            self.selecionados = [s for s in self.selecionados
                                 if s in self.por_id]
        self.rebuilds += 0 if parcial else 1
        return {"adicionados": adicionados,
                "removidos": removidos, "alterados": alterados,
                "rebuild_parcial": parcial}

    def to_dict(self) -> dict:
        return {"objetos": [o.to_dict() for o in self.objetos],
                "viewport": self.viewport.to_dict(),
                "debug": self.debug, "fundo": self.fundo,
                "selecionados": list(self.selecionados)}

    def __repr__(self) -> str:
        return (f"SceneCanvas({len(self.objetos)} objetos "
                f"debug={self.debug})")


class AnimationPreview:
    """Play/pause/stop sobre F11 (sem segundo scheduler)."""

    def __init__(self) -> None:
        self.motor = None
        self.timeline = None
        self.estado = "parado"
        self.atual: str | None = None

    def carregar(self, definicoes: list, cena) -> int:
        from ..animacao.motor import MotorAnimacoes
        from .cena import timeline_de_motions

        if not definicoes:
            raise ErroELiXX("Animacao: sem definicoes reais.")
        self.motor = MotorAnimacoes()
        self.motor.carregar(list(definicoes), cena)
        self.timeline = timeline_de_motions(list(definicoes))
        self.estado = "parado"
        self.atual = None
        return len(definicoes)

    def play(self, nome: str) -> str:
        if self.motor is None:
            raise ErroELiXX("Animacao: carregue antes.")
        self.motor.iniciar(str(nome))
        self.estado = "tocando"
        self.atual = str(nome)
        return self.estado

    def pause(self) -> str:
        if self.motor is None or self.atual is None:
            raise ErroELiXX("Animacao: nada tocando.")
        self.motor.pausar(self.atual)
        self.estado = "pausado"
        return self.estado

    def stop(self) -> str:
        if self.motor is None or self.atual is None:
            raise ErroELiXX("Animacao: nada tocando.")
        self.motor.cancelar(self.atual)
        self.estado = "parado"
        self.atual = None
        return self.estado

    def tick(self, dt_ms: float) -> dict:
        if self.motor is None:
            raise ErroELiXX("Animacao: carregue antes.")
        self.motor.atualizar(_finito(dt_ms, "dt_ms"))
        return {"estado": self.estado, "atual": self.atual}

    def __repr__(self) -> str:
        return f"AnimationPreview({self.estado})"


class MotionPreview:
    """Pose/gesto/expressao/movimento reais (somente leitura +).

    Pre-visualizar aplica a pose no Character em memoria (sem
    escrever arquivos); a ida ao codigo usa proposta F39.
    """

    def __init__(self, character) -> None:
        from ..visual.personagem import Character as _Ch

        if not isinstance(character, _Ch):
            raise ErroELiXX("Motion: espera Character.")
        self.character = character

    def poses(self) -> list[str]:
        return sorted(self.character.poses)

    def expressoes(self) -> list[str]:
        return sorted(n for n, p in self.character.poses.items()
                      if getattr(p, "expressao", False))

    def previsualizar_pose(self, nome: str) -> list[str]:
        pose = self.character.obter_pose(str(nome))
        _ = pose
        return self.character.aplicar_pose(str(nome))

    def resumo(self) -> dict:
        return {"poses": self.poses(),
                "expressoes": self.expressoes(),
                "pose_atual": self.character.pose_atual,
                "direcao": self.character.direcao}

    def __repr__(self) -> str:
        return f"MotionPreview({self.character.nome})"


def ficha_objeto(modelo, ent_id: str, cena=None,
                 personagens=None, workspace=None) -> dict:
    """Inspector F40: identidade/transform/relacoes/asset/character.

    Somente dados reais; secoes vazias sao omitidas.
    """
    from .inspetor import Inspetor
    from .modelo.adaptador import resumo_para_inspetor

    eid = _texto_curto(ent_id).strip()
    ent = next((e for e in modelo.entidades()
                if e.id == eid), None)
    if ent is None:
        raise ErroELiXX(f'Canvas: entidade "{eid}" ausente.')
    secoes: dict = {"IDENTIDADE": {
        "nome": ent.nome, "tipo": ent.tipo,
        "arquivo": ent.arquivo, "linha": ent.linha}}
    if cena is not None:
        alvo = None
        pilha = list(getattr(cena, "janelas", []))
        while pilha:
            no = pilha.pop()
            if getattr(no, "nome", "") == ent.nome:
                alvo = no
                break
            pilha.extend(getattr(no, "filhos", []))
        if alvo is not None:
            props = Inspetor().inspecionar_no(alvo)
            transf = {k: props[k] for k in
                      ("x", "y", "rotacao", "escala_x",
                       "escala_y", "opacidade", "camada",
                       "visivel") if k in props}
            larg = getattr(alvo, "largura", None)
            alt = getattr(alvo, "altura", None)
            if larg is not None:
                transf["width"] = larg
            if alt is not None:
                transf["height"] = alt
            if transf:
                secoes["TRANSFORM"] = transf
            asset = estado_asset(alvo, workspace)
            if asset.get("status") != "sem_asset":
                secoes["ASSET"] = asset
    try:
        resumo = resumo_para_inspetor(modelo, eid)
        rel = {}
        if resumo.get("de"):
            rel["saida"] = resumo["de"]
        if resumo.get("para"):
            rel["entrada"] = resumo["para"]
        if rel:
            secoes["RELATIONS"] = rel
    except ErroELiXX:
        pass
    if personagens and ent.nome in personagens:
        ch = personagens[ent.nome]
        try:
            partes = sorted(ch.partes)
        except Exception:
            partes = []
        try:
            poses = sorted(ch.poses)
        except Exception:
            poses = []
        secoes["CHARACTER"] = {
            "parts": partes, "poses": poses,
            "expressions": sorted(
                n for n, p in ch.poses.items()
                if getattr(p, "expressao", False)),
            "direcao": ch.direcao}
    return secoes


def aplicar_edicao(workspace, modelo, canvas: SceneCanvas,
                   relativo: str, texto_entrada: str,
                   entrada: str = "src/main.elixx") -> dict:
    """Live preview: salva edicao -> F27 -> canvas (sem restart)."""
    from .modelo.adaptador import atualizar_arquivo

    if not isinstance(canvas, SceneCanvas):
        raise ErroELiXX("Canvas: espera SceneCanvas.")
    if not workspace.existe(relativo):
        raise ErroELiXX(f'Canvas: "{relativo}" ausente.')
    destino = workspace.resolver(relativo)
    destino.write_text(texto_entrada, encoding="utf-8")
    info = atualizar_arquivo(modelo, relativo, texto_entrada)
    diff = canvas.recarregar(
        workspace.resolver(entrada).read_text(encoding="utf-8"),
        entrada)
    return {"modelo": info, "canvas": diff}


def contexto_cena(canvas: SceneCanvas, painel_agent, modelo,
                  ent_id: str) -> dict:
    """Agent observa a cena (estruturas; sem visao por imagem)."""
    if not isinstance(canvas, SceneCanvas):
        raise ErroELiXX("Canvas: espera SceneCanvas.")
    base = painel_agent.contexto(modelo, ent_id)
    visiveis = [{"id": o.id, "kind": o.kind,
                 "rotulo": o.rotulo} for o in canvas.ordem_render()
                if o.kind != "janela"][:50]
    return {"selecionado": ent_id, "contexto": base,
            "visiveis": visiveis,
            "total_visiveis": len(visiveis)}


def proporcoes_scene() -> dict:
    total = sum(PROPORCOES_SCENE.values())
    if not 0.99 <= total <= 1.01:
        raise ErroELiXX("Scene: proporcoes somam 1.0.")
    for nome, fracao in PROPORCOES_SCENE.items():
        if not 0.05 <= fracao <= 0.9:
            raise ErroELiXX(f"Scene: {nome} fora de 0.05..0.9.")
    return dict(PROPORCOES_SCENE)


def aplicar_layout_scene(layout) -> dict:
    """SCENE: canvas maximo (fracoes; sem px rigido)."""
    props = proporcoes_scene()
    for painel in list(layout.visivel):
        layout.visivel[painel] = painel in ("project",
                                            "preview",
                                            "inspector",
                                            "console")
    tamanhos = {}
    for painel, fracao in (("project", props["project"]),
                           ("preview", props["canvas"]),
                           ("inspector", props["inspector"])):
        try:
            tamanhos[painel] = layout.redimensionar(painel,
                                                    fracao)
        except ErroELiXX:
            continue
    return {"visiveis": list(layout.paineis_visiveis()),
            "tamanhos": tamanhos}


def aplicar_compacto(layout, ativo: bool = True) -> dict:
    """Compacto: paineis menores; canvas ganha espaco."""
    mapas = layout.definir_compacto(bool(ativo))
    if ativo and "preview" not in layout.paineis_visiveis():
        layout.visivel["preview"] = True
    return {"compacto": layout.compacto,
            "visiveis": list(layout.paineis_visiveis()),
            "mapas": mapas}


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


def buscar_palette_f40(texto: str = "") -> list[dict]:
    termo = _norm(texto)
    return [{"id": cid, "rotulo": rotulo}
            for cid, rotulo in COMANDOS_F40
            if not termo or termo in _norm(f"{cid} {rotulo}")]


def executar_palette_f40(canvas: SceneCanvas, editor,
                         comando_id: str,
                         anim: AnimationPreview | None = None
                         ) -> dict:
    """Comandos F40 sobre canvas real (sem efeitos fora do Studio)."""
    if not isinstance(canvas, SceneCanvas):
        raise ErroELiXX("Canvas: espera SceneCanvas.")
    cid = str(comando_id)
    if cid == "scene_fit":
        return {"ok": True, **canvas.enquadrar(800, 600)}
    if cid == "scene_center_selection":
        return {"ok": True,
                **canvas.centralizar_selecao(800, 600)}
    if cid == "scene_toggle_grid":
        return {"ok": True,
                "grid": editor.alternar_grid()}
    if cid == "scene_toggle_debug":
        return {"ok": True, "debug": canvas.alternar_debug()}
    if cid in ("scene_play_animation", "scene_pause_animation",
               "scene_stop_animation"):
        if anim is None:
            raise ErroELiXX("Animacao: nada carregado.")
        if cid == "scene_play_animation":
            nomes = []
            if canvas is not None and anim.timeline is not None:
                for blocos in anim.timeline.trilhas().values():
                    nomes.extend(b["nome"] for b in blocos)
            if not nomes:
                raise ErroELiXX("Animacao: sem definicao real.")
            return {"ok": True, "estado": anim.play(nomes[0])}
        if cid == "scene_pause_animation":
            return {"ok": True, "estado": anim.pause()}
        return {"ok": True, "estado": anim.stop()}
    if cid == "scene_zoom_in":
        return {"ok": True, "fator": editor.zoom_mais()}
    if cid == "scene_zoom_out":
        return {"ok": True, "fator": editor.zoom_menos()}
    if cid == "scene_reset_zoom":
        editor.definir_zoom(100)
        editor.centralizar()
        return {"ok": True, "zoom": 100}
    raise ErroELiXX(f'Canvas: comando "{cid}" desconhecido.')


def conflitos_f40() -> list[dict]:
    """Atalhos F40 ja existentes no mapa global (sem substituir)."""
    from .app import ATALHOS

    saida = []
    for tecla in ATALHOS_F40:
        if tecla in ATALHOS:
            saida.append({"tecla": tecla,
                          "global": ATALHOS[tecla],
                          "contextual": ATALHOS_F40[tecla],
                          "regra": "global prevalece; F40 so com "
                                   "canvas focado"})
    return saida


def desenhar(canvas_tk, canvas: SceneCanvas,
             tema: dict | None = None) -> dict:
    """Desenha a cena no Canvas Tk (ou stub duck-typed).

    Retorna contagem {objetos, placeholders, selecao, grade}.
    Qualquer falha de item vira placeholder honesto.
    """
    from .tema import ELIXX_COLORS

    cores = dict(ELIXX_COLORS)
    if isinstance(tema, dict):
        cores.update(tema)
    conta = {"objetos": 0, "placeholders": 0, "selecao": 0,
             "grade": 0}
    try:
        canvas_tk.delete("all")
    except Exception:
        pass
    largura = int(canvas_tk.winfo_width()
                  if hasattr(canvas_tk, "winfo_width") else 800)
    altura = int(canvas_tk.winfo_height()
                 if hasattr(canvas_tk, "winfo_height") else 600)
    largura = max(largura, 100)
    altura = max(altura, 100)
    try:
        canvas_tk.create_rectangle(0, 0, largura, altura,
                                   fill=cores["background"],
                                   outline="")
    except Exception:
        pass
    if canvas.viewport.grid:
        try:
            grade = canvas.ticks_grade(largura, altura)
            for gx in grade["verticais"]:
                canvas_tk.create_line(gx, 0, gx, altura,
                                      fill=cores["border"])
                conta["grade"] += 1
            for gy in grade["horizontais"]:
                canvas_tk.create_line(0, gy, largura, gy,
                                      fill=cores["border"])
                conta["grade"] += 1
        except Exception:
            pass
    for obj in canvas.ordem_render():
        try:
            conta["objetos"] += 1
            x, y = canvas.viewport.para_tela(obj.x, obj.y)
            f = canvas.viewport.fator()
            w, h = obj.largura * f, obj.altura * f
            if obj.kind == "imagem" and obj.asset.get(
                    "status") == "encontrado":
                foto = carregar_imagem(
                    obj.asset.get("caminho", ""))
                if foto is not None:
                    canvas_tk.create_image(x, y, image=foto,
                                           anchor="nw")
                    continue
            if obj.placeholder:
                rot = {"PERSONAGEM": "PERSONAGEM",
                       "IMAGEM": "IMAGEM",
                       "COMPONENTE": "COMPONENTE",
                       "GRUPO": "GRUPO",
                       "TEXTO": "TEXTO"}.get(
                    "PERSONAGEM" if obj.kind == "personagem"
                    else "IMAGEM" if obj.kind == "imagem"
                    else "COMPONENTE" if obj.kind ==
                    "componente" else "GRUPO" if obj.kind ==
                    "grupo" else "TEXTO")
                canvas_tk.create_rectangle(
                    x, y, x + w, y + h,
                    fill=cores["surface"],
                    outline=cores["border"])
                canvas_tk.create_text(
                    x + w / 2, y + h / 2 - 8, text=rot,
                    fill=cores["text_muted"])
                canvas_tk.create_text(
                    x + w / 2, y + h / 2 + 8,
                    text=f"{obj.rotulo} · sem asset",
                    fill=cores["text"])
                conta["placeholders"] += 1
            elif obj.kind == "texto":
                canvas_tk.create_text(
                    x, y, text=obj.texto or obj.rotulo,
                    anchor="nw",
                    fill=obj.cor_hex or cores["text"])
            else:
                canvas_tk.create_rectangle(
                    x, y, x + w, y + h,
                    fill=obj.fundo_hex or cores["surface"],
                    outline=cores["border"])
                canvas_tk.create_text(
                    x + w / 2, y + h / 2, text=obj.rotulo,
                    fill=cores["text"])
            if obj.id in canvas.selecionados:
                conta["selecao"] += 1
                canvas_tk.create_rectangle(
                    x - 2, y - 2, x + w + 2, y + h + 2,
                    outline=cores["accent"], width=2)
                canvas_tk.create_text(
                    x, y - 10, text=obj.rotulo, anchor="sw",
                    fill=cores["accent"])
                for hnd in canvas.handles_de(obj.id):
                    hx, hy = canvas.viewport.para_tela(
                        hnd["x"], hnd["y"])
                    canvas_tk.create_rectangle(
                        hx - 4, hy - 4, hx + 4, hy + 4,
                        fill=cores["accent"] if hnd[
                            "disponivel"] else cores["surface"],
                        outline=cores["accent"])
            if canvas.debug:
                info = canvas.info_debug(obj.id)
                canvas_tk.create_text(
                    x, y + h + 10,
                    text=f"{info['id']} {info['tipo']} "
                         f"{info['posicao']}",
                    anchor="nw", fill=cores["text_muted"])
        except Exception:
            continue
    return conta


def abrir_janela_cena(ws, texto: str,
                      entrada: str = "src/main.elixx"):
    """Janela Tk com canvas real (display necessario)."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        raise ErroELiXX("Tk indisponivel neste ambiente.")
    saida = cena_de_texto(texto)
    if not saida["ok"]:
        raise ErroELiXX("Cena com erro (sem janela).")
    canvas = SceneCanvas(inspetor=ws.app.inspetor,
                         eventos=ws.app.eventos)
    canvas.montar(saida["cena"], saida["personagens"],
                  getattr(ws, "modelo", None))
    if tk._default_root is None:
        janela = tk.Tk()
    else:
        janela = tk.Toplevel()
    janela.title("ELiXX Scene Canvas")
    janela.geometry("900x620")
    barra = ttk.Frame(janela)
    barra.pack(fill="x")
    tela = tk.Canvas(janela, highlightthickness=0)
    tela.pack(fill="both", expand=True)

    def _redesenhar():
        desenhar(tela, canvas)

    for rot, cmd in (("Fit", lambda: (canvas.enquadrar(
            max(tela.winfo_width(), 100),
            max(tela.winfo_height(), 100)), _redesenhar())),
                     ("Grid", lambda: (canvas.viewport.__setattr__(
                         "grid", not canvas.viewport.grid),
                         _redesenhar())),
                     ("+1", lambda: (canvas.viewport.set_zoom(
                         min(200, (canvas.viewport.zoom
                                   if canvas.viewport.zoom !=
                                   "Ajustar" else 100) + 25)),
                         _redesenhar()))):
        ttk.Button(barra, text=rot, command=cmd).pack(
            side="left", padx=2)

    def _clique(evento):
        obj = canvas.objeto_sob_ponto(evento.x, evento.y)
        if obj is not None:
            canvas.selecionar(obj.id)
        _redesenhar()

    tela.bind("<Button-1>", _clique)
    tela.bind("<Configure>", lambda _e: _redesenhar())
    _redesenhar()
    return janela
