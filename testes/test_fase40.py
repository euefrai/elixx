"""Fase 40 — ELiXX Studio Real Scene Rendering + Visual Object Editor.

Cobre: canvas, rendering, objetos, personagens, partes, assets,
placeholders, selecao, tree, geometria, transform, bbox, handles,
zoom, pan, grade, snap, fit, center, layers, debug, inspector,
code sync, visual->code, code->visual, animacao, agent, contexto,
tools, reasoning, layouts, compacto, palette, teclado, responsivo,
seguranca, performance e integracao F07-F39.
"""

import time

import pytest

from elixx.erros import ErroELiXX

FONTE = (
    'janela p {\n'
    ' titulo: "T"\n'
    ' posicao: 100 200\n'
    ' personagem Juh {\n'
    '  parte corpo {\n'
    '  }\n'
    ' }\n'
    ' texto ola {\n'
    '  texto: "Ola"\n'
    ' }\n'
    '}\n'
)


class _StubCanvas:
    """Stub duck-typed do Canvas Tk (sem display)."""

    def __init__(self, w=800, h=600):
        self._w = w
        self._h = h
        self.itens = []

    def delete(self, _tag):
        self.itens = []

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def _reg(self, kind, *args, **kw):
        self.itens.append((kind, args, kw))
        return len(self.itens)

    def create_rectangle(self, *a, **k):
        return self._reg("rect", *a, **k)

    def create_text(self, *a, **k):
        return self._reg("text", *a, **k)

    def create_line(self, *a, **k):
        return self._reg("line", *a, **k)

    def create_image(self, *a, **k):
        return self._reg("image", *a, **k)

    def create_oval(self, *a, **k):
        return self._reg("oval", *a, **k)


def _workspace(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    return app, ws


def _saida():
    from elixx.studio.scene_canvas import cena_de_texto

    return cena_de_texto(FONTE)


def _canvas(modelo=None, workspace=None):
    from elixx.studio.scene_canvas import SceneCanvas

    saida = _saida()
    assert saida["ok"]
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"], modelo,
                  workspace)
    return canvas, saida


# ---------- pipeline oficial (principio central) ----------


def test_cena_de_texto_ok():
    saida = _saida()
    assert saida["ok"] is True
    assert len(saida["cena"].janelas) == 1
    assert "Juh" in saida["personagens"]


def test_cena_de_texto_erro_honesto():
    from elixx.studio.scene_canvas import cena_de_texto

    saida = cena_de_texto("janela { !!!")
    assert saida["ok"] is False
    assert saida["cena"] is None


def test_cena_de_texto_nao_string():
    from elixx.studio.scene_canvas import cena_de_texto

    with pytest.raises(ErroELiXX):
        cena_de_texto(123)


def test_sem_conteudo_inventado():
    canvas, _ = _canvas()
    ids = {o.id for o in canvas.objetos}
    assert "janela:p" in ids
    assert "personagem:Juh" in ids
    assert "parte:Juh.corpo" in ids
    assert "texto:ola" in ids
    assert len(canvas.objetos) == 4


# ---------- canvas / objetos (A, B) ----------


def test_kinds_validos():
    from elixx.studio.scene_canvas import KINDS

    assert set(KINDS) >= {"janela", "personagem", "parte",
                          "imagem", "texto", "componente",
                          "grupo", "objeto"}


def test_janela_medidas_reais():
    canvas, _ = _canvas()
    jan = canvas.por_id["janela:p"]
    assert (jan.x, jan.y) == (100.0, 200.0)
    assert (jan.largura, jan.altura) == (800.0, 600.0)
    assert jan.tamanho_derivado is False


def test_personagem_placeholder_honesto():
    canvas, _ = _canvas()
    juh = canvas.por_id["personagem:Juh"]
    assert juh.placeholder is True
    assert juh.asset["status"] == "sem_asset"
    assert juh.tamanho_derivado is True


def test_texto_conteudo_real():
    canvas, _ = _canvas()
    txt = canvas.por_id["texto:ola"]
    assert txt.texto == "Ola"
    assert txt.placeholder is False


def test_render_object_kind_invalido():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("x", "nave_espacial")


def test_render_object_id_vazio():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("  ", "objeto")


def test_render_object_tamanho_invalido():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("o", "objeto", largura=0, altura=10)


def test_render_object_nan():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("o", "objeto", x=float("nan"))


def test_render_object_ajuste():
    from elixx.studio.scene_canvas import RenderObject

    assert RenderObject("o", "imagem",
                        ajuste="cobrir").ajuste == "cobrir"
    assert RenderObject("o", "imagem",
                        ajuste="x").ajuste == "conter"


def test_render_object_to_dict():
    canvas, _ = _canvas()
    dados = canvas.por_id["janela:p"].to_dict()
    assert dados["id"] == "janela:p"
    assert dados["largura"] == 800.0


def test_canvas_vazio_sem_objetos():
    from elixx.studio.scene_canvas import SceneCanvas

    canvas = SceneCanvas()
    assert canvas.limites_conteudo() is None
    with pytest.raises(ErroELiXX):
        canvas.enquadrar(800, 600)


def test_fundo_dark_design_system():
    from elixx.studio import ELIXX_DS3

    canvas, _ = _canvas()
    fundo = canvas.fundo_canvas()
    assert fundo["estilo"] == "dark"
    assert fundo["cor"] == ELIXX_DS3["bg_base"]
    assert fundo["cor"] != "#ffffff"


def test_fundo_para_objeto():
    canvas, _ = _canvas()
    assert canvas.fundo_para_objeto("personagem:Juh") == "dark"
    with pytest.raises(ErroELiXX):
        canvas.fundo_para_objeto("x")


# ---------- personagens / partes (C, D) ----------


def test_character_vinculado():
    _, saida = _canvas()
    ch = saida["personagens"]["Juh"]
    assert "corpo" in ch.partes


def test_parte_transform_global_real():
    _, saida = _canvas()
    tg = saida["personagens"]["Juh"].obter_transform_global(
        "corpo")
    assert (tg.x, tg.y) == (20.0, 20.0)


def test_parte_tem_parent_personagem():
    canvas, _ = _canvas()
    parte = canvas.por_id["parte:Juh.corpo"]
    assert parte.parent_id == "personagem:Juh"


def test_selecionar_personagem_global(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_canvas import SceneCanvas

    canvas = SceneCanvas(inspetor=ws.app.inspetor,
                         eventos=ws.app.eventos)
    saida = _saida()
    canvas.montar(saida["cena"], saida["personagens"],
                  ws.modelo)
    sel = canvas.selecionar("personagem:Juh")
    assert sel["tipo"] == "personagem"
    assert ws.app.inspetor.selecao.ref_id == "personagem:Juh"


def test_selecionar_parte():
    canvas, _ = _canvas()
    sel = canvas.selecionar("parte:Juh.corpo")
    assert sel["tipo"] == "parte"


def test_selecionar_no_comum():
    canvas, _ = _canvas()
    sel = canvas.selecionar("texto:ola")
    assert sel["tipo"] == "no"


def test_selecionar_ausente():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.selecionar("fantasma:x")


def test_selecao_emite_eventos(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_canvas import SceneCanvas

    canvas = SceneCanvas(inspetor=ws.app.inspetor,
                         eventos=ws.app.eventos)
    saida = _saida()
    canvas.montar(saida["cena"], saida["personagens"])
    canvas.selecionar("personagem:Juh")
    assert "selecionado" in ws.app.eventos.eventos_emitidos()


def test_hit_test_topo():
    canvas, _ = _canvas()
    obj = canvas.objeto_sob_ponto(100, 200)
    assert obj is not None
    assert obj.id == "janela:p"


def test_hit_test_fora():
    canvas, _ = _canvas()
    assert canvas.objeto_sob_ponto(5000, 5000) is None


def test_hit_test_nan():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.objeto_sob_ponto(float("inf"), 0)


# ---------- tree bidirecional (E) ----------


def test_tree_seleciona_canvas(tmp_path):
    from elixx.studio.scene_editor import SceneEditor

    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_canvas import SceneCanvas

    ed = SceneEditor(inspetor=ws.app.inspetor,
                     eventos=ws.app.eventos)
    ed.construir_arvore(ws.modelo)
    canvas = SceneCanvas(inspetor=ws.app.inspetor,
                         eventos=ws.app.eventos)
    saida = _saida()
    canvas.montar(saida["cena"], saida["personagens"],
                  ws.modelo)
    ed.selecionar("personagem:Juh")
    canvas.selecionar("personagem:Juh")
    assert (ed.selecao_atual()["ref_id"] ==
            "personagem:Juh")


def test_canvas_seleciona_tree_entidade(tmp_path):
    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas(ws.modelo)
    canvas.selecionar("personagem:Juh")
    obj = canvas.por_id["personagem:Juh"]
    assert obj.ent_id == "personagem:Juh"


# ---------- coordenadas / bbox (F, G) ----------


def test_bbox_global_combina_pais():
    canvas, _ = _canvas()
    bb = canvas.por_id["parte:Juh.corpo"].bbox_global(
        canvas.por_id)
    assert bb["x"] == 140.0
    assert bb["y"] == 240.0


def test_bbox_janela_propria():
    canvas, _ = _canvas()
    bb = canvas.por_id["janela:p"].bbox_global(canvas.por_id)
    assert (bb["x"], bb["y"]) == (100.0, 200.0)
    assert bb["largura"] == 800.0


def test_transform_f10_reutilizado():
    canvas, _ = _canvas()
    from elixx.visual.transform import transform_de_no

    saida = _saida()
    t = transform_de_no(saida["cena"].janelas[0])
    assert (t.x, t.y) == (100.0, 200.0)


def test_geometria_bounds_reutilizada():
    from elixx.visual.mundo import Bounds2D
    from elixx.visual.transform import Vector2

    bb = Bounds2D(10, 20, 100, 50)
    assert bb.direita == 110
    assert bb.contem_ponto(Vector2(50, 40)) is True


# ---------- handles (H) ----------


def test_handles_mover_disponivel():
    canvas, _ = _canvas()
    handles = canvas.handles_de("personagem:Juh")
    mover = next(h for h in handles if h["gizmo"] == "mover")
    assert mover["disponivel"] is True


def test_handles_escala_girar_preparados():
    canvas, _ = _canvas()
    handles = canvas.handles_de("personagem:Juh")
    for h in handles:
        if h["gizmo"] in ("escalar", "girar"):
            assert h["disponivel"] is False
            assert h["motivo"]


def test_handles_objeto_ausente():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.handles_de("x")


def test_handles_posicao_centro():
    canvas, _ = _canvas()
    handles = canvas.handles_de("janela:p")
    mover = next(h for h in handles if h["gizmo"] == "mover")
    assert mover["x"] == 500.0
    assert mover["y"] == 500.0


# ---------- drag -> proposta (I) ----------


def test_interpretar_gesto_pan():
    canvas, _ = _canvas()
    assert canvas.interpretar_gesto("meio", True) == "pan"
    assert canvas.interpretar_gesto("direito", False) == "pan"


def test_interpretar_gesto_drag():
    canvas, _ = _canvas()
    canvas.viewport.modo = "Mover"
    assert canvas.interpretar_gesto("esquerdo", True) == \
        "drag_objeto"


def test_interpretar_gesto_selecionar():
    canvas, _ = _canvas()
    assert canvas.interpretar_gesto("esquerdo", True) == \
        "selecionar"
    assert canvas.interpretar_gesto("esquerdo", False) == \
        "selecionar"


def test_arrastar_gera_proposta_sem_escrever(tmp_path):
    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas(ws.modelo)
    cs = canvas.arrastar_para("janela:p", 180, 200,
                              ws.app.workspace, ws.modelo)
    assert cs.estado == "proposto"
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert "180 200" not in texto


def test_arrastar_com_snap(tmp_path):
    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas(ws.modelo)
    cs = canvas.arrastar_para("janela:p", 183, 207,
                              ws.app.workspace, ws.modelo,
                              snap=10)
    assert "180 210" in cs.revisar()[0]["previa"]


def test_arrastar_sem_entidade_falha(tmp_path):
    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.arrastar_para("janela:p", 1, 2,
                             ws.app.workspace, ws.modelo)


def test_arrastar_snap_invalido(tmp_path):
    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas(ws.modelo)
    with pytest.raises(ErroELiXX):
        canvas.arrastar_para("janela:p", 1, 2,
                             ws.app.workspace, ws.modelo,
                             snap=7)


# ---------- code -> visual (J) ----------


def test_recarregar_diff_incremental(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_canvas import SceneCanvas

    saida = _saida()
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"])
    rebuilds = canvas.rebuilds
    novo = FONTE.replace("100 200", "180 200")
    diff = canvas.recarregar(novo)
    assert diff["alterados"] == ["janela:p"]
    assert diff["rebuild_parcial"] is True
    assert canvas.rebuilds == rebuilds
    assert canvas.por_id["janela:p"].x == 180.0


def test_recarregar_adicao(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_canvas import SceneCanvas

    saida = _saida()
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"])
    novo = FONTE.replace(' texto ola {',
                         ' botao ok {\n  texto: "Ok"\n }\n'
                         ' texto ola {')
    diff = canvas.recarregar(novo)
    assert diff["adicionados"]


def test_recarregar_erro_nao_quebra():
    from elixx.studio.scene_canvas import SceneCanvas

    saida = _saida()
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"])
    with pytest.raises(ErroELiXX):
        canvas.recarregar("janela { !!!")
    assert "janela:p" in canvas.por_id


def test_live_preview_aplicar_edicao(tmp_path):
    from elixx.studio.scene_canvas import (
        SceneCanvas,
        aplicar_edicao,
    )

    _, ws = _workspace(tmp_path)
    saida = _saida()
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"])
    novo = FONTE.replace("100 200", "180 200")
    saida_out = aplicar_edicao(ws.app.workspace, ws.modelo,
                               canvas, "src/main.elixx", novo)
    assert saida_out["canvas"]["alterados"] == ["janela:p"]
    em_disco = (tmp_path / "p" / "src" / "main.elixx"
                ).read_text(encoding="utf-8")
    assert "180 200" in em_disco


def test_live_preview_arquivo_ausente(tmp_path):
    from elixx.studio.scene_canvas import aplicar_edicao

    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        aplicar_edicao(ws.app.workspace, ws.modelo, canvas,
                       "nada.elixx", FONTE)


# ---------- assets (K, L) ----------


def test_estado_sem_asset():
    from elixx.studio.scene_canvas import estado_asset

    class _No:
        caminho_recurso = ""

    assert estado_asset(_No())["status"] == "sem_asset"


def test_estado_remoto():
    from elixx.studio.scene_canvas import estado_asset

    class _No:
        caminho_recurso = "https://x/y.png"

    assert estado_asset(_No())["status"] == "remoto"


def test_estado_nao_verificado_sem_workspace():
    from elixx.studio.scene_canvas import estado_asset

    class _No:
        caminho_recurso = "assets/logo.png"

    assert estado_asset(_No())["status"] == "nao_verificado"


def test_estado_encontrado(tmp_path):
    from elixx.studio.scene_canvas import estado_asset

    _, ws = _workspace(tmp_path)
    base = tmp_path / "p" / "assets"
    base.mkdir(parents=True, exist_ok=True)
    (base / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" +
                                    b"\x00" * 100)

    class _No:
        caminho_recurso = "assets/logo.png"

    assert estado_asset(_No(),
                        ws.app.workspace)["status"] in (
        "encontrado", "ausente", "invalido")


def test_estado_ausente(tmp_path):
    from elixx.studio.scene_canvas import estado_asset

    _, ws = _workspace(tmp_path)

    class _No:
        caminho_recurso = "assets/falta.png"

    assert estado_asset(_No(),
                        ws.app.workspace)["status"] in (
        "ausente", "invalido")


def test_carregar_imagem_sem_display():
    from elixx.studio.scene_canvas import carregar_imagem

    assert carregar_imagem("/caminho/que/nao/existe.png") is None
    assert carregar_imagem("x.svg") is None


def test_ajuste_conter_cobrir():
    from elixx.studio.scene_canvas import RenderObject

    assert RenderObject("i", "imagem",
                        ajuste="conter").ajuste == "conter"
    assert RenderObject("i", "imagem",
                        ajuste="cobrir").ajuste == "cobrir"
    assert RenderObject("i", "imagem",
                        ajuste="original").ajuste == "original"


def test_asset_manager_reutilizado():
    from elixx.studio.assets import GerenciadorAssets

    assert GerenciadorAssets is not None


# ---------- placeholders (M) ----------


def test_placeholder_kinds():
    from elixx.studio.scene_canvas import PLACEHOLDER_KINDS

    assert set(PLACEHOLDER_KINDS) == {"PERSONAGEM", "IMAGEM",
                                     "COMPONENTE", "GRUPO",
                                     "TEXTO"}


def test_placeholder_personagem_sem_imagem_falsa():
    canvas, _ = _canvas()
    juh = canvas.por_id["personagem:Juh"]
    assert juh.placeholder is True
    assert juh.asset["status"] == "sem_asset"


def test_desenhar_placeholder_stub():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    stub = _StubCanvas()
    conta = desenhar(stub, canvas)
    assert conta["objetos"] == 4
    assert conta["placeholders"] >= 1
    textos = [kw.get("text", "") for k, a, kw in stub.itens
              if k == "text"]
    assert any("PERSONAGEM" in str(t) for t in textos)
    assert any("sem asset" in str(t) for t in textos)


def test_desenhar_texto_real():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    textos = [kw.get("text", "") for k, a, kw in stub.itens
              if k == "text"]
    assert "Ola" in [str(t) for t in textos]


# ---------- grid / rulers (N, O) ----------


def test_ticks_grade_respeita_viewport():
    canvas, _ = _canvas()
    ticks = canvas.ticks_grade(800, 600)
    assert ticks["verticais"]
    assert ticks["horizontais"]
    assert ticks["passo"] == 20


def test_ticks_grade_com_zoom():
    canvas, _ = _canvas()
    base = canvas.ticks_grade(800, 600)
    canvas.viewport.set_zoom(200)
    dobrado = canvas.ticks_grade(800, 600)
    assert len(dobrado["verticais"]) < len(base["verticais"])


def test_ticks_grade_passo_invalido():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.ticks_grade(800, 600, passo=7)


def test_ticks_regua():
    canvas, _ = _canvas()
    regua = canvas.ticks_regua("x", 800)
    assert regua
    assert "tela" in regua[0] and "mundo" in regua[0]


def test_ticks_regua_eixo_invalido():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.ticks_regua("z", 800)


def test_desenhar_grade_stub():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    canvas.viewport.grid = True
    stub = _StubCanvas()
    conta = desenhar(stub, canvas)
    assert conta["grade"] > 0


# ---------- fit / center / zoom (P, Q) ----------


def test_enquadrar_fit_real():
    canvas, _ = _canvas()
    saida = canvas.enquadrar(800, 600)
    assert saida["zoom"] == 200
    assert saida["fator"] == 2.0


def test_centralizar_selecao():
    canvas, _ = _canvas()
    canvas.selecionar("personagem:Juh")
    saida = canvas.centralizar_selecao(800, 600)
    assert saida["id"] == "personagem:Juh"
    assert saida["offset"] != [0.0, 0.0]


def test_centralizar_sem_selecao():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.centralizar_selecao(800, 600)


def test_zoom_para_selecao():
    canvas, _ = _canvas()
    canvas.selecionar("parte:Juh.corpo")
    saida = canvas.zoom_para_selecao()
    assert saida["zoom"] == 200


def test_zoom_para_selecao_grande():
    canvas, _ = _canvas()
    canvas.selecionar("janela:p")
    saida = canvas.zoom_para_selecao()
    assert saida["zoom"] == 50


def test_zoom_para_selecao_sem_selecao():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.zoom_para_selecao()


# ---------- pan (R) ----------


def test_pan_viewport_real():
    canvas, _ = _canvas()
    assert canvas.viewport.mover(30, -10) == [30.0, -10.0]


def test_pan_nao_quebra_hit():
    canvas, _ = _canvas()
    canvas.viewport.mover(10000, 10000)
    assert canvas.objeto_sob_ponto(100, 200) is None
    canvas.viewport.mover(-10000, -10000)
    assert canvas.objeto_sob_ponto(100, 200) is not None


# ---------- selecao visual (T) ----------


def test_desenhar_selecao_outline():
    from elixx.studio import ELIXX_DS3
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    canvas.selecionar("personagem:Juh")
    stub = _StubCanvas()
    conta = desenhar(stub, canvas)
    assert conta["selecao"] == 1
    acentos = [k for k, a, kw in stub.itens
               if kw.get("outline") == ELIXX_DS3["accent"]]
    assert acentos


def test_desenhar_handles():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    canvas.selecionar("janela:p")
    stub = _StubCanvas()
    desenhar(stub, canvas)
    assert len(stub.itens) > 10


def test_desenhar_fundo_dark():
    from elixx.studio import ELIXX_DS3
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    fundo = stub.itens[0]
    assert fundo[0] == "rect"
    assert fundo[2].get("fill") == ELIXX_DS3["bg_base"]


def test_desenhar_sem_branco_puro():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    for kind, _a, kw in stub.itens:
        assert kw.get("fill") != "#ffffff"
        assert kw.get("fill") != "#fff"


def test_desenhar_respeita_invisivel():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    canvas.por_id["texto:ola"].visivel = False
    stub = _StubCanvas()
    conta = desenhar(stub, canvas)
    assert conta["objetos"] == 3


# ---------- multi-selecao (U) ----------


def test_multi_nao_suportado_honesto():
    canvas, _ = _canvas()
    cap = canvas.capacidade_multi()
    assert cap["suportado"] is False
    assert cap["motivo"]
    with pytest.raises(ErroELiXX):
        canvas.selecionar_multiplos(["a", "b"])


def test_single_selection_oficial():
    canvas, _ = _canvas()
    canvas.selecionar("personagem:Juh")
    canvas.selecionar("texto:ola")
    assert canvas.selecionados == ["texto:ola"]


# ---------- layers (V) ----------


def test_ordem_por_camada_nao_alfabetica():
    canvas, _ = _canvas()
    canvas.por_id["texto:ola"].seq = -1
    ordem = [o.id for o in canvas.ordem_render()]
    assert ordem[0] == "texto:ola"
    assert ordem != sorted(ordem)


def test_camada_real_respeitada():
    canvas, _ = _canvas()
    canvas.por_id["texto:ola"].camada = 10.0
    ordem = [o.id for o in canvas.ordem_render()]
    assert ordem[-1] == "texto:ola"


def test_ordem_visual_f10():
    from elixx.visual.transform import ordem_visual

    saida = _saida()
    nomes = [n.nome for n in
             ordem_visual(saida["cena"].janelas[0])]
    assert nomes == ["Juh", "ola"]


# ---------- debug (W) ----------


def test_debug_desligado_padrao():
    canvas, _ = _canvas()
    assert canvas.debug is False


def test_debug_alternar():
    canvas, _ = _canvas()
    assert canvas.alternar_debug() is True
    assert canvas.alternar_debug() is False


def test_info_debug():
    canvas, _ = _canvas()
    info = canvas.info_debug("parte:Juh.corpo")
    assert info["tipo"] == "parte"
    assert info["parent"] == "personagem:Juh"
    assert "posicao" in info and "tamanho" in info


def test_info_debug_ausente():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.info_debug("x")


def test_desenhar_debug_stub():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    canvas.alternar_debug()
    stub = _StubCanvas()
    antes = len(stub.itens)
    desenhar(stub, canvas)
    assert len(stub.itens) > antes


# ---------- inspector ficha (X) ----------


def test_ficha_identidade(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    ficha = ficha_objeto(ws.modelo, "personagem:Juh")
    assert ficha["IDENTIDADE"]["nome"] == "Juh"
    assert ficha["IDENTIDADE"]["tipo"] == "personagem"
    assert ficha["IDENTIDADE"]["arquivo"] == "src/main.elixx"


def test_ficha_transform_real(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    saida = _saida()
    ficha = ficha_objeto(ws.modelo, "janela:p",
                         cena=saida["cena"])
    assert ficha["TRANSFORM"]["x"] == 100.0
    assert ficha["TRANSFORM"]["width"] == 800.0


def test_ficha_relations(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    ficha = ficha_objeto(ws.modelo, "personagem:Juh")
    assert "RELATIONS" in ficha


def test_ficha_character(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    saida = _saida()
    ficha = ficha_objeto(ws.modelo, "personagem:Juh",
                         cena=saida["cena"],
                         personagens=saida["personagens"])
    assert "corpo" in ficha["CHARACTER"]["parts"]


def test_ficha_sem_dados_inventados(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    ficha = ficha_objeto(ws.modelo, "parte:Juh.corpo")
    assert "ASSET" not in ficha
    assert "CHARACTER" not in ficha


def test_ficha_entidade_ausente(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        ficha_objeto(ws.modelo, "x")


# ---------- animacao (Z) ----------


def _anim_defs():
    from elixx.animacao.motor import DefinicaoAnimacao

    return [DefinicaoAnimacao(nome="acenar", alvo="Juh",
                              duracao_ms=500.0)]


def test_animation_carregar():
    from elixx.studio.scene_canvas import AnimationPreview

    anim = AnimationPreview()
    saida = _saida()
    assert anim.carregar(_anim_defs(), saida["cena"]) == 1
    assert anim.timeline.duracao_total() == 500.0


def test_animation_play_pause_stop():
    from elixx.studio.scene_canvas import AnimationPreview

    anim = AnimationPreview()
    anim.carregar(_anim_defs(), _saida()["cena"])
    assert anim.play("acenar") == "tocando"
    assert anim.pause() == "pausado"
    assert anim.stop() == "parado"


def test_animation_tick():
    from elixx.studio.scene_canvas import AnimationPreview

    anim = AnimationPreview()
    anim.carregar(_anim_defs(), _saida()["cena"])
    anim.play("acenar")
    assert anim.tick(16.0)["estado"] == "tocando"


def test_animation_sem_definicao():
    from elixx.studio.scene_canvas import AnimationPreview

    with pytest.raises(ErroELiXX):
        AnimationPreview().carregar([], _saida()["cena"])


def test_animation_pause_sem_play():
    from elixx.studio.scene_canvas import AnimationPreview

    anim = AnimationPreview()
    anim.carregar(_anim_defs(), _saida()["cena"])
    with pytest.raises(ErroELiXX):
        anim.pause()


def test_animation_play_sem_carregar():
    from elixx.studio.scene_canvas import AnimationPreview

    with pytest.raises(ErroELiXX):
        AnimationPreview().play("x")


# ---------- motion (AA) ----------


def test_motion_poses_reais():
    from elixx.studio.scene_canvas import MotionPreview

    _, saida = _canvas()
    motion = MotionPreview(saida["personagens"]["Juh"])
    assert isinstance(motion.poses(), list)


def test_motion_expressoes():
    from elixx.studio.scene_canvas import MotionPreview

    _, saida = _canvas()
    motion = MotionPreview(saida["personagens"]["Juh"])
    assert isinstance(motion.expressoes(), list)


def test_motion_resumo():
    from elixx.studio.scene_canvas import MotionPreview

    _, saida = _canvas()
    resumo = MotionPreview(
        saida["personagens"]["Juh"]).resumo()
    assert "poses" in resumo and "direcao" in resumo


def test_motion_tipo_invalido():
    from elixx.studio.scene_canvas import MotionPreview

    with pytest.raises(ErroELiXX):
        MotionPreview(object())


def test_motion_sintese_reutilizada():
    from elixx.visual.sintese_comportamento import (
        BehaviorSynthesizer,
    )
    from elixx.visual.sintese_movimento import MotionSynthesizer

    assert MotionSynthesizer() is not None
    assert BehaviorSynthesizer() is not None


def test_motion_preview_pose_real():
    from elixx.studio.scene_canvas import MotionPreview
    from elixx.visual.personagem import Character, Pose

    ch = Character("T", None, {}, {"oi": Pose("oi")})
    motion = MotionPreview(ch)
    assert motion.poses() == ["oi"]
    tocadas = motion.previsualizar_pose("oi")
    assert isinstance(tocadas, list)


# ---------- agent / context / tools / reasoning (AB-AD) ----------


def test_contexto_cena(tmp_path):
    from elixx.studio.scene_canvas import contexto_cena

    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas(ws.modelo)
    ctx = contexto_cena(canvas, ws.agent, ws.modelo,
                        "personagem:Juh")
    assert ctx["selecionado"] == "personagem:Juh"
    assert ctx["contexto"]["entidades"] >= 1
    assert any(v["id"] == "personagem:Juh"
               for v in ctx["visiveis"])


def test_contexto_cena_sem_imagem(tmp_path):
    from elixx.studio.scene_canvas import contexto_cena

    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas()
    ctx = contexto_cena(canvas, ws.agent, ws.modelo,
                        "janela:p")
    assert "visao" not in str(ctx).lower()


def test_agent_planeja_juh(tmp_path):
    _, ws = _workspace(tmp_path)
    plano = ws.agent.planejar(ws.modelo, "Juh")
    assert plano["status"] == "plano"


def test_tool_trace_preservado():
    from elixx.studio.agent.ferramentas_semanticas import (
        AgentToolCall,
        ToolTrace,
    )

    trace = ToolTrace()
    trace.registrar(AgentToolCall("t_buscar_entidade",
                                  {"nome": "Juh"}))
    assert trace.explicar()


def test_reasoning_estagios():
    from elixx.studio.agent.workspace import AgentWorkspace

    area = AgentWorkspace("t")
    assert "TOOLS" in area.estagios


# ---------- bottom / layouts / compacto (AE-AH) ----------


def test_proporcoes_scene_somam_um():
    from elixx.studio.scene_canvas import proporcoes_scene

    props = proporcoes_scene()
    assert abs(sum(props.values()) - 1.0) < 0.01
    assert props["canvas"] >= 0.55


def test_aplicar_layout_scene(tmp_path):
    from elixx.studio.scene_canvas import aplicar_layout_scene

    _, ws = _workspace(tmp_path)
    saida = aplicar_layout_scene(ws.layout)
    assert "preview" in saida["visiveis"]
    assert "inspector" in saida["visiveis"]
    assert saida["tamanhos"]["preview"] >= 0.55


def test_layouts_mantidos():
    from elixx.studio.workspace_ui import LAYOUTS

    for nome in ("DEFAULT", "CODE", "SCENE", "AGENT",
                 "REVIEW"):
        assert nome in LAYOUTS


def test_compacto_canvas_ganha_espaco(tmp_path):
    from elixx.studio.scene_canvas import aplicar_compacto

    _, ws = _workspace(tmp_path)
    saida = aplicar_compacto(ws.layout, True)
    assert saida["compacto"] is True
    assert "preview" in saida["visiveis"]
    aplicar_compacto(ws.layout, False)


def test_preview_construir_canvas(tmp_path):
    _, ws = _workspace(tmp_path)
    saida = _saida()
    canvas = ws.preview.construir_canvas(
        saida["cena"], saida["personagens"], ws.modelo)
    assert "personagem:Juh" in canvas.por_id


# ---------- palette (AI) ----------


def test_comandos_f40_dez():
    from elixx.studio.scene_canvas import COMANDOS_F40

    assert len(COMANDOS_F40) == 10
    ids = [c[0] for c in COMANDOS_F40]
    for esperado in ("scene_fit", "scene_center_selection",
                     "scene_toggle_grid", "scene_toggle_debug",
                     "scene_play_animation",
                     "scene_pause_animation",
                     "scene_stop_animation", "scene_zoom_in",
                     "scene_zoom_out", "scene_reset_zoom"):
        assert esperado in ids


def test_buscar_palette_f40():
    from elixx.studio.scene_canvas import buscar_palette_f40

    assert len(buscar_palette_f40("")) == 10
    assert len(buscar_palette_f40("zoom")) == 3
    assert buscar_palette_f40("animation")


def test_executar_fit_center(tmp_path):
    from elixx.studio.scene_canvas import executar_palette_f40
    from elixx.studio.scene_editor import SceneEditor

    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas()
    ed = SceneEditor()
    assert executar_palette_f40(canvas, ed,
                                "scene_fit")["ok"] is True
    canvas.selecionar("personagem:Juh")
    assert executar_palette_f40(
        canvas, ed, "scene_center_selection")["ok"] is True


def test_executar_grid_debug_zoom(tmp_path):
    from elixx.studio.scene_canvas import executar_palette_f40
    from elixx.studio.scene_editor import SceneEditor

    canvas, _ = _canvas()
    ed = SceneEditor()
    assert executar_palette_f40(canvas, ed,
                                "scene_toggle_grid") == {
        "ok": True, "grid": True}
    assert executar_palette_f40(canvas, ed,
                                "scene_toggle_debug") == {
        "ok": True, "debug": True}
    assert executar_palette_f40(canvas, ed,
                                "scene_zoom_in")["ok"] is True
    assert executar_palette_f40(canvas, ed,
                                "scene_zoom_out")["ok"] is True
    assert executar_palette_f40(canvas, ed,
                                "scene_reset_zoom") == {
        "ok": True, "zoom": 100}


def test_executar_anim_sem_anim():
    from elixx.studio.scene_canvas import executar_palette_f40
    from elixx.studio.scene_editor import SceneEditor

    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        executar_palette_f40(canvas, SceneEditor(),
                             "scene_play_animation")


def test_executar_anim_play_stop():
    from elixx.studio.scene_canvas import (
        AnimationPreview,
        executar_palette_f40,
    )
    from elixx.studio.scene_editor import SceneEditor

    canvas, _ = _canvas()
    anim = AnimationPreview()
    anim.carregar(_anim_defs(), _saida()["cena"])
    assert executar_palette_f40(canvas, SceneEditor(),
                                "scene_play_animation",
                                anim=anim)["estado"] == "tocando"
    assert executar_palette_f40(canvas, SceneEditor(),
                                "scene_pause_animation",
                                anim=anim)["estado"] == "pausado"
    assert executar_palette_f40(canvas, SceneEditor(),
                                "scene_stop_animation",
                                anim=anim)["estado"] == "parado"


def test_executar_comando_invalido():
    from elixx.studio.scene_canvas import executar_palette_f40
    from elixx.studio.scene_editor import SceneEditor

    with pytest.raises(ErroELiXX):
        executar_palette_f40(_canvas()[0], SceneEditor(),
                             "x")


def test_palettes_anteriores_intactas():
    from elixx.studio.agent.interacao import CommandPalette
    from elixx.studio.scene_editor import buscar_palette_f39

    assert len(CommandPalette().buscar("")) == 30
    assert len(buscar_palette_f39("")) == 13


# ---------- teclado (AJ) ----------


def test_atalhos_antigos_preservados():
    from elixx.studio.app import ATALHOS

    for tecla in ("Ctrl+K", "Ctrl+1", "Ctrl+Enter", "Esc",
                  "Ctrl+S", "F5", "Ctrl+Shift+F"):
        assert tecla in ATALHOS


def test_atalhos_f40():
    from elixx.studio.scene_canvas import ATALHOS_F40

    assert ATALHOS_F40["Home"] == "scene_fit"
    assert ATALHOS_F40["+"] == "scene_zoom_in"
    assert ATALHOS_F40["0"] == "scene_reset_zoom"
    assert ATALHOS_F40["G"] == "scene_toggle_grid"
    assert ATALHOS_F40["D"] == "scene_toggle_debug"


def test_conflitos_f40_documentados():
    from elixx.studio.scene_canvas import conflitos_f40

    teclas = [c["tecla"] for c in conflitos_f40()]
    assert "F" in teclas
    from elixx.studio.app import ATALHOS

    assert ATALHOS["F"] == "enquadrar"


# ---------- responsivo (AM) ----------


def test_resolucoes_canvas(tmp_path):
    from elixx.studio.scene_editor import RESOLUCOES_QA

    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas()
    for larg, alt in RESOLUCOES_QA:
        ws.layout.definir_geometria(larg, alt)
        ticks = canvas.ticks_grade(larg, alt)
        assert ticks["verticais"] and ticks["horizontais"]
        stub = _StubCanvas(larg, alt)
        from elixx.studio.scene_canvas import desenhar

        conta = desenhar(stub, canvas)
        assert conta["objetos"] == 4


def test_canvas_minimo_800x500():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    stub = _StubCanvas(800, 500)
    assert desenhar(stub, canvas)["objetos"] == 4


# ---------- seguranca (AP) ----------


def test_sem_execucao_dinamica():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/scene_canvas.py").read_text(
        encoding="utf-8")
    for proibido in ("eval(", "exec(", "importlib",
                     "__import__", "pickle", "subprocess",
                     "os.system", "shell=True"):
        assert proibido not in fonte, proibido


def test_traversal_bloqueado(tmp_path):
    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.app.workspace.resolver("../../fora.elixx")


def test_absoluto_bloqueado(tmp_path):
    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.app.workspace.resolver("C:\\Windows\\x.elixx")


def test_nan_infinito_rejeitados():
    from elixx.studio.scene_canvas import RenderObject

    for ruim in (float("nan"), float("inf")):
        with pytest.raises(ErroELiXX):
            RenderObject("o", "objeto", x=ruim)


def test_payload_gigante_rejeitado():
    canvas, _ = _canvas()
    with pytest.raises(ErroELiXX):
        canvas.selecionar("x" * 500)


def test_recurso_remoto_sem_download():
    from elixx.studio.scene_canvas import estado_asset

    class _No:
        caminho_recurso = "https://exemplo.com/a.png"

    veredito = estado_asset(_No())
    assert veredito["status"] == "remoto"


def test_canvas_nunca_executa_codigo(tmp_path):
    _, ws = _workspace(tmp_path)
    canvas, _ = _canvas(ws.modelo)
    cs = canvas.arrastar_para("janela:p", 180, 200,
                              ws.app.workspace, ws.modelo)
    assert cs.estado == "proposto"


# ---------- performance (AQ) ----------


def _modelo_grande(n):
    from elixx.studio.modelo.modelo import (
        EntidadeSemantica,
        ModeloSemantico,
        RelacaoSemantica,
    )

    modelo = ModeloSemantico("grande")
    modelo.adicionar_entidade(
        EntidadeSemantica("janela:raiz", "janela", "raiz",
                          arquivo="src/main.elixx", linha=1))
    for i in range(n):
        eid = f"simbolo:{i:05d}"
        modelo.adicionar_entidade(
            EntidadeSemantica(eid, "simbolo", f"n{i}",
                              arquivo="src/main.elixx",
                              linha=i + 2))
        modelo.adicionar_relacao(
            RelacaoSemantica("janela:raiz", "contem", eid))
    return modelo


def _cena_grande(n):
    from elixx.visual.cena import Cena, NoVisual

    raiz = NoVisual(tipo="janela", nome="raiz", largura=2000.0,
                    altura=2000.0)
    for i in range(n):
        raiz.adicionar(NoVisual(tipo="objeto", nome=f"n{i}",
                                x=float(i % 100) * 10.0,
                                y=float(i // 100) * 10.0,
                                largura=8.0, altura=8.0))
    return Cena(janelas=[raiz])


def test_perf_100_objetos():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    canvas = SceneCanvas()
    canvas.montar(_cena_grande(100))
    assert len(canvas.objetos) == 101
    assert time.perf_counter() - inicio < 5.0


def test_perf_500_objetos():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    canvas = SceneCanvas()
    canvas.montar(_cena_grande(500))
    assert time.perf_counter() - inicio < 8.0


def test_perf_1000_objetos():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    canvas = SceneCanvas()
    canvas.montar(_cena_grande(1000))
    assert time.perf_counter() - inicio < 12.0


def test_perf_5000_objetos():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    canvas = SceneCanvas()
    canvas.montar(_cena_grande(5000))
    assert time.perf_counter() - inicio < 20.0


def test_perf_10000_objetos():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    canvas = SceneCanvas()
    canvas.montar(_cena_grande(10000))
    assert canvas.ordem_render()
    assert time.perf_counter() - inicio < 30.0


def test_perf_1000_arquivos():
    from elixx.studio.modelo.modelo import (
        EntidadeSemantica,
        ModeloSemantico,
    )

    inicio = time.perf_counter()
    modelo = ModeloSemantico("arq")
    for i in range(1000):
        modelo.adicionar_entidade(
            EntidadeSemantica(f"arquivo:{i:04d}", "arquivo",
                              f"m{i:04d}",
                              arquivo=f"src/m{i:04d}.elixx",
                              linha=1))
    assert len(modelo.entidades()) == 1000
    assert time.perf_counter() - inicio < 15.0


def test_perf_500_partes():
    from elixx.studio.inspetor import fluxo_personagem

    inicio = time.perf_counter()
    _, personagem, _ = fluxo_personagem(
        "Juh", {"parts": [{"id": f"p{i}"}
                           for i in range(500)]},
        analyzer="structured")
    assert len(personagem.partes) >= 500
    assert time.perf_counter() - inicio < 15.0


def test_perf_1000_operacoes():
    from elixx.studio.agent.operacoes import SemanticOperation

    inicio = time.perf_counter()
    ops = [SemanticOperation("alterar_propriedade",
                             {"nome": f"n{i}"},
                             {"propriedade": "posicao"})
           for i in range(1000)]
    assert len(ops) == 1000
    assert time.perf_counter() - inicio < 10.0


def test_sem_rebuild_total_1_mudanca():
    from elixx.studio.scene_canvas import SceneCanvas

    saida = _saida()
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"])
    rebuilds = canvas.rebuilds
    diff = canvas.recarregar(FONTE.replace("100 200",
                                           "101 200"))
    assert diff["rebuild_parcial"] is True
    assert canvas.rebuilds == rebuilds


def test_desenhar_sem_duplicacao():
    from elixx.studio.scene_canvas import desenhar

    canvas, _ = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    n1 = len(stub.itens)
    desenhar(stub, canvas)
    assert len(stub.itens) == n1


# ---------- integracao (AO) ----------


def test_f07_asset_categorias():
    from elixx.studio.assets import CATEGORIAS

    assert "imagens" in CATEGORIAS


def test_f10_transform():
    from elixx.visual.transform import Transform, combinar

    t = combinar(Transform(x=100, y=200), Transform(x=20))
    assert (t.x, t.y) == (120.0, 200.0)


def test_f11_animacao():
    from elixx.animacao.motor import MotorAnimacoes

    assert MotorAnimacoes() is not None


def test_f12_character():
    from elixx.visual.personagem import Character

    assert Character("J", None, {}, {}).nome == "J"


def test_f13_world():
    from elixx.visual.mundo import World

    assert World("w") is not None


def test_f16_sintese():
    from elixx.visual.sintese_movimento import MODOS_SINTESE

    assert "andar" in MODOS_SINTESE


def test_f17_comportamento():
    from elixx.visual.sintese_comportamento import TRACKS

    assert "pose" in TRACKS


def test_f21_geometria():
    from elixx.visual.geometria import GeometryMap

    assert GeometryMap("m") is not None


def test_f23_rigging():
    from elixx.visual.rigging import construir_rig

    assert callable(construir_rig)


def test_f24_deformacao():
    from elixx.visual.deformacao import deformation_rig_de_rig

    assert callable(deformation_rig_de_rig)


def test_f25_preview():
    from elixx.studio import HeadlessPreview

    assert HeadlessPreview().executar(FONTE).sucesso is True


def test_f26_changeset():
    from elixx.studio.agent.mudancas import ChangeSet

    assert ChangeSet().estado == "proposto"


def test_f27_entidades(tmp_path):
    _, ws = _workspace(tmp_path)
    assert "personagem:Juh" in [e.id for e in
                                ws.modelo.entidades()]


def test_f28_contexto(tmp_path):
    _, ws = _workspace(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["entidades"] >= 1


def test_f29_workspace(tmp_path):
    _, ws = _workspace(tmp_path)
    assert ws.estado()["projeto"]


def test_f30_intencao():
    from elixx.studio.agent.intencao import AgentIntent

    assert AgentIntent("modificar_personagem",
                       objetivo="x")


def test_f31_operacao():
    from elixx.studio.agent.operacoes import (
        SemanticOperation,
        validar_operacao,
    )

    assert validar_operacao(
        SemanticOperation("alterar_propriedade",
                          {"nome": "p"},
                          {"propriedade": "posicao"}))


def test_f32_localizacao(tmp_path):
    from elixx.studio.codigo.localizacao import (
        localizar_entidade,
    )

    _, ws = _workspace(tmp_path)
    ent = next(e for e in ws.modelo.entidades()
               if e.id == "personagem:Juh")
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert localizar_entidade(ent, texto).inicio_linha == 4


def test_f33_plano(tmp_path):
    _, ws = _workspace(tmp_path)
    assert ws.agent.planejar(ws.modelo,
                             "Juh")["status"] == "plano"


def test_f34_contexto_config():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoConfig,
    )

    assert ContextoConfig()


def test_f35_reasoning():
    from elixx.studio.agent.workspace import AgentWorkspace

    assert "TASK" in AgentWorkspace("t").estagios


def test_f36_tools():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    assert len(SemanticToolRegistry().listar()) == 30


def test_f37_palette():
    from elixx.studio.agent.interacao import CommandPalette

    assert len(CommandPalette().buscar("")) == 30


def test_f38_tokens():
    from elixx.studio import validar_tokens

    assert validar_tokens()["valido"] is True


def test_f39_editor():
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor()
    assert ed.definir_modo("Mover") == "Mover"
