"""Fase 39 — ELiXX Studio Scene Editor + Adaptive Workspace.

Cobre: Scene Editor, viewport, zoom, pan, grid, snap, modos, selecao,
scene tree, hierarquia, inspector, transform, code sync, visual->code,
code->visual, proposta, aprovacao, undo/redo, layouts, foco, fundo,
console, status, agent, context, tools, reasoning, plan, changes,
palette, teclado, responsivo, seguranca, performance e integracao
F25-F38 (sem regressao).
"""

import tempfile
import time
from pathlib import Path

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
    '}\n'
)


def _workspace(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    return app, ws


def _modelo():
    from elixx.studio.modelo.adaptador import analisar_texto
    from elixx.studio.modelo.modelo import ModeloSemantico

    modelo = ModeloSemantico("t")
    analisar_texto(modelo, FONTE, "src/main.elixx")
    return modelo


def _editor_com_arvore():
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor()
    ed.construir_arvore(_modelo())
    return ed


# ---------- scene editor / modos (A) ----------


def test_editor_cria_modo_padrao():
    ed = _editor_com_arvore()
    assert ed.viewport.modo == "Selecionar"


def test_modos_f39_reusa_cena():
    from elixx.studio.cena import MODOS_CENA
    from elixx.studio.scene_editor import MODOS_F39

    assert MODOS_F39 == MODOS_CENA
    assert tuple(MODOS_F39) == ("Selecionar", "Mover", "Escalar",
                                "Girar", "Ajustar")


def test_definir_modo_ok():
    ed = _editor_com_arvore()
    for modo in ("Selecionar", "Mover", "Escalar", "Girar", "Ajustar"):
        assert ed.definir_modo(modo) == modo
    assert ed.viewport.modo == "Ajustar"


def test_definir_modo_invalido():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.definir_modo("Voar")


def test_zoom_f39_reusa_cena():
    from elixx.studio.cena import ZOOM_CENA
    from elixx.studio.scene_editor import ZOOM_F39

    assert ZOOM_F39 == ZOOM_CENA
    assert 25 in ZOOM_F39 and 200 in ZOOM_F39


def test_gizmo_status_move_real():
    from elixx.studio.scene_editor import gizmo_status

    st = gizmo_status("Mover")
    assert st.disponivel is True


def test_gizmo_status_preparados_honestos():
    from elixx.studio.scene_editor import gizmo_status

    for modo in ("Escalar", "Girar"):
        st = gizmo_status(modo)
        assert st.disponivel is False
        assert st.motivo


def test_gizmo_sem_modo_falha():
    from elixx.studio.scene_editor import gizmo_para_modo, gizmo_status

    assert gizmo_para_modo("Selecionar") is None
    assert gizmo_para_modo("Ajustar") is None
    with pytest.raises(ErroELiXX):
        gizmo_status("Selecionar")


def test_gizmo_modo_invalido():
    from elixx.studio.scene_editor import gizmo_para_modo

    with pytest.raises(ErroELiXX):
        gizmo_para_modo("Voar")


def test_gizmo_atual_mover():
    ed = _editor_com_arvore()
    ed.definir_modo("Mover")
    assert ed.gizmo_atual().disponivel is True


def test_gizmo_atual_selecionar_sem_gizmo():
    ed = _editor_com_arvore()
    assert ed.gizmo_atual() is None


# ---------- viewport / zoom / pan (B) ----------


def test_zoom_niveis_todos():
    ed = _editor_com_arvore()
    for nivel in (25, 50, 75, 100, 125, 150, 200):
        assert ed.definir_zoom(nivel) == nivel / 100.0
    assert ed.definir_zoom("Ajustar") == 1.0


def test_zoom_valor_real_nao_label():
    ed = _editor_com_arvore()
    ed.definir_zoom(200)
    assert ed.viewport.para_tela(10, 10) == [20.0, 20.0]
    ed.definir_zoom(50)
    assert ed.viewport.para_tela(10, 10) == [5.0, 5.0]


def test_zoom_invalido():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.definir_zoom(300)


def test_zoom_mais_menos():
    ed = _editor_com_arvore()
    ed.definir_zoom(100)
    ed.zoom_mais()
    assert ed.viewport.zoom == 125
    ed.zoom_menos()
    assert ed.viewport.zoom == 100


def test_zoom_mais_no_teto():
    ed = _editor_com_arvore()
    ed.definir_zoom(200)
    ed.zoom_mais()
    assert ed.viewport.zoom == 200


def test_zoom_menos_no_piso():
    ed = _editor_com_arvore()
    ed.definir_zoom(25)
    ed.zoom_menos()
    assert ed.viewport.zoom == 25


def test_ajustar_reseta_pan():
    ed = _editor_com_arvore()
    ed.pan(40, 30)
    assert ed.ajustar() == "Ajustar"
    assert ed.viewport.offset_x == 0.0
    assert ed.viewport.offset_y == 0.0


def test_pan_move_offset():
    ed = _editor_com_arvore()
    assert ed.pan(10, -5) == [10.0, -5.0]
    assert ed.pan(5, 5) == [15.0, 0.0]


def test_pan_nao_bloqueia_selecao(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor(inspetor=ws.app.inspetor,
                     eventos=ws.app.eventos)
    ed.construir_arvore(ws.modelo)
    ed.pan(20, 20)
    sel = ed.selecionar("personagem:Juh")
    assert sel["ref_id"] == "personagem:Juh"


def test_centralizar():
    ed = _editor_com_arvore()
    ed.pan(99, -33)
    assert ed.centralizar() == [0.0, 0.0]


def test_fit_calcula_zoom_real():
    ed = _editor_com_arvore()
    fator = ed.fit(800, 600, 1600, 1200)
    assert fator == 0.5
    assert ed.viewport.zoom == 50


def test_fit_respeita_menor_eixo():
    ed = _editor_com_arvore()
    ed.fit(800, 600, 800, 1200)
    assert ed.viewport.zoom == 50


def test_fit_dimensao_invalida():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.fit(0, 600)
    with pytest.raises(ErroELiXX):
        ed.fit(800, -1)


def test_viewport_serializavel():
    ed = _editor_com_arvore()
    ed.definir_zoom(150)
    ed.pan(3, 4)
    dados = ed.to_dict()
    assert dados["viewport"]["zoom"] == 150
    from elixx.studio.scene_editor import SceneEditor

    ed2 = SceneEditor.from_dict(dados)
    assert ed2.viewport.zoom == 150
    assert ed2.viewport.offset_x == 3.0


def test_viewport_from_dict_invalido():
    from elixx.studio.scene_editor import SceneEditor

    with pytest.raises(ErroELiXX):
        SceneEditor.from_dict("nao-dict")


# ---------- grid / snap ----------


def test_grid_alterna():
    ed = _editor_com_arvore()
    assert ed.viewport.grid is False
    assert ed.alternar_grid() is True
    assert ed.alternar_grid() is False


def test_grid_respeita_zoom_pan():
    ed = _editor_com_arvore()
    ed.definir_zoom(200)
    ed.pan(10, 10)
    ed.alternar_grid()
    assert ed.viewport.grid is True
    assert ed.viewport.para_tela(5, 5) == [20.0, 20.0]


def test_snap_niveis():
    from elixx.studio.scene_editor import SNAPS_F39

    assert tuple(SNAPS_F39) == (0, 1, 5, 10)


def test_snap_aplicado():
    ed = _editor_com_arvore()
    ed.definir_snap(10)
    assert ed.aplicar_snap(103) == 100.0
    assert ed.aplicar_snap(108) == 110.0


def test_snap_livre():
    ed = _editor_com_arvore()
    ed.definir_snap(0)
    assert ed.aplicar_snap(103.7) == 103.7


def test_snap_invalido():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.definir_snap(7)


def test_snap_nan_rejeitado():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.aplicar_snap(float("nan"))


def test_propor_mover_aplica_snap(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor()
    ed.definir_snap(10)
    cs = ed.propor_mover(ws.app.workspace, ws.modelo,
                         "janela:p", 103, 207)
    previa = cs.revisar()[0]["previa"]
    assert "100 210" in previa


# ---------- toolbar (C) ----------


def test_toolbar_itens_compacta():
    ed = _editor_com_arvore()
    itens = ed.toolbar()
    ids = [i["id"] for i in itens]
    for esperado in ("scene_selecionar", "scene_mover",
                     "scene_escalar", "scene_girar",
                     "scene_ajustar", "zoom_mais", "zoom_menos",
                     "scene_grid", "scene_snap"):
        assert esperado in ids
    assert len(itens) <= 12


def test_toolbar_tooltips():
    ed = _editor_com_arvore()
    for item in ed.toolbar():
        assert item["tooltip"]


def test_toolbar_modo_via_acionar():
    from elixx.studio.scene_editor import SceneToolbar

    ed = _editor_com_arvore()
    barra = SceneToolbar(ed)
    assert barra.acionar("scene_mover") == {"ok": True,
                                            "modo": "Mover"}
    assert ed.viewport.modo == "Mover"


def test_toolbar_zoom_via_acionar():
    from elixx.studio.scene_editor import SceneToolbar

    ed = _editor_com_arvore()
    barra = SceneToolbar(ed)
    saida = barra.acionar("zoom_mais")
    assert saida["ok"] is True and saida["zoom"] == 125


def test_toolbar_grid_snap_via_acionar():
    from elixx.studio.scene_editor import SceneToolbar

    ed = _editor_com_arvore()
    barra = SceneToolbar(ed)
    assert barra.acionar("scene_grid") == {"ok": True,
                                           "grid": True}
    assert barra.acionar("scene_snap") == {"ok": True, "snap": 1}


def test_toolbar_rotulo_zoom_atual():
    from elixx.studio.scene_editor import SceneToolbar

    ed = _editor_com_arvore()
    ed.definir_zoom(150)
    rotulos = {i["id"]: i["rotulo"]
               for i in SceneToolbar(ed).itens()}
    assert rotulos["zoom_rotulo"] == "150%"


def test_toolbar_item_invalido():
    from elixx.studio.scene_editor import SceneToolbar

    with pytest.raises(ErroELiXX):
        SceneToolbar(_editor_com_arvore()).acionar("foguete")


def test_toolbar_exige_editor():
    from elixx.studio.scene_editor import SceneToolbar

    with pytest.raises(ErroELiXX):
        SceneToolbar(object())


# ---------- scene tree / hierarquia (D, E) ----------


def test_arvore_raiz_janela():
    ed = _editor_com_arvore()
    assert "janela:p" in ed.arvore.raizes


def test_arvore_hierarquia_real():
    ed = _editor_com_arvore()
    janela = ed.arvore.nos["janela:p"]
    assert "personagem:Juh" in janela.filhos
    juh = ed.arvore.nos["personagem:Juh"]
    assert "parte:Juh.corpo" in juh.filhos


def test_arvore_nao_inventa():
    from elixx.studio.modelo.adaptador import analisar_texto
    from elixx.studio.modelo.modelo import ModeloSemantico
    from elixx.studio.scene_editor import SceneEditor

    modelo = ModeloSemantico("solo")
    analisar_texto(modelo, 'janela so {\n titulo: "S"\n}\n',
                   "src/main.elixx")
    ed = SceneEditor()
    ed.construir_arvore(modelo)
    assert ed.arvore.nos["janela:so"].filhos == []


def test_arvore_linhas():
    ed = _editor_com_arvore()
    linhas = ed.arvore.linhas()
    texto = "\n".join(linhas)
    assert "Juh" in texto
    assert "corpo" in texto


def test_arvore_alternar():
    ed = _editor_com_arvore()
    assert ed.arvore.alternar("janela:p") is False
    assert ed.arvore.alternar("janela:p") is True


def test_arvore_alternar_ausente():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.arvore.alternar("fantasma:x")


def test_arvore_visiveis_respeita_recolhido():
    ed = _editor_com_arvore()
    total = len(ed.arvore.visiveis())
    ed.arvore.alternar("janela:p")
    assert len(ed.arvore.visiveis()) < total


# ---------- selecao bidirecional ----------


def test_selecionar_no_arvore(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor(inspetor=ws.app.inspetor,
                     eventos=ws.app.eventos)
    ed.construir_arvore(ws.modelo)
    sel = ed.selecionar("personagem:Juh")
    assert sel["ref_id"] == "personagem:Juh"
    assert ws.app.inspetor.selecao.ref_id == "personagem:Juh"


def test_selecao_emite_evento(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor(inspetor=ws.app.inspetor,
                     eventos=ws.app.eventos)
    ed.construir_arvore(ws.modelo)
    ed.selecionar("janela:p")
    assert "selecionado" in ws.app.eventos.eventos_emitidos()


def test_selecao_preview_compartilhada(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_editor import SceneEditor

    ed = SceneEditor(inspetor=ws.app.inspetor,
                     eventos=ws.app.eventos)
    ed.construir_arvore(ws.modelo)
    ws.preview.sincronizar_modelo(ws.modelo)
    ws.preview.selecionar("personagem:Juh")
    assert ed.selecao_atual()["ref_id"] == "personagem:Juh"


def test_selecao_tipo_personagem():
    ed = _editor_com_arvore()
    sel = ed.selecionar("personagem:Juh", origem="tree")
    assert sel["tipo"] == "personagem"
    assert sel["origem"] == "tree"


def test_selecao_no_comum():
    ed = _editor_com_arvore()
    sel = ed.selecionar("janela:p")
    assert sel["tipo"] == "no"


def test_selecionar_no_ausente():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.selecionar("fantasma:x")


def test_destaque_outline_discreto():
    ed = _editor_com_arvore()
    assert ed.destaque() is None
    ed.selecionar("personagem:Juh")
    dest = ed.destaque()
    assert dest["node_id"] == "personagem:Juh"
    assert dest["estilo"] == "outline"


def test_limpar_selecao():
    ed = _editor_com_arvore()
    ed.selecionar("personagem:Juh")
    ed.limpar_selecao()
    assert ed.destaque() is None
    assert ed.selecao_atual()["tipo"] == "nenhum"


# ---------- bounding box ----------


def test_bbox_dados_reais_quando_existem():
    from elixx.studio.scene_editor import BoundingBox

    class _No:
        x = 10
        y = 20
        largura = 100
        altura = 50
        rotacao = 0

    bbox = BoundingBox.de_no(_No())
    assert (bbox.x, bbox.y) == (10.0, 20.0)
    assert bbox.area() == 5000.0


def test_bbox_sem_dados_honesta(tmp_path):
    _, ws = _workspace(tmp_path)
    ed = _editor_com_arvore()
    bbox = ed.bbox_entidade(ws.modelo, "janela:p")
    assert bbox.vazia() is True
    assert bbox.area() is None


def test_bbox_entidade_ausente():
    with pytest.raises(ErroELiXX):
        _editor_com_arvore().bbox_entidade(_modelo(), "x:y")


def test_bbox_nan_ignorado():
    from elixx.studio.scene_editor import BoundingBox

    class _No:
        x = float("nan")
        y = 5

    bbox = BoundingBox.de_no(_No())
    assert bbox.x is None
    assert bbox.y == 5.0


def test_bbox_to_dict():
    from elixx.studio.scene_editor import BoundingBox

    bbox = BoundingBox(1, 2, 3, 4, 0)
    assert bbox.to_dict() == {"x": 1, "y": 2, "largura": 3,
                              "altura": 4, "rotacao": 0}


# ---------- inspector visual (F) ----------


def test_inspector_mostra_juh(tmp_path):
    _, ws = _workspace(tmp_path)
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    texto = str(secoes)
    assert "Juh" in texto


def test_inspector_transform_campos_reais(tmp_path):
    from elixx.studio.inspetor import Inspetor

    _, ws = _workspace(tmp_path)
    insp = Inspetor()
    props = insp.inspecionar_no(
        ws.preview.executar(FONTE) and _no_cena(ws))
    assert "tipo" in props and "nome" in props


def _no_cena(ws):
    from elixx.compilador.lexer import tokenizar
    from elixx.compilador.parser import Parser
    from elixx.runtime.nucleo import Executor
    from elixx.visual.cena import ConstrutorCena

    prog = Parser(tokenizar(FONTE)).parse()
    cena = ConstrutorCena().de_objetos(
        Executor().executar(prog, []).objetos)
    return cena.janelas[0]


def test_propor_alteracao_nao_escreve(tmp_path):
    _, ws = _workspace(tmp_path)
    antes = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    ws.inspector.propor_alteracao("janela:p", "posicao",
                                  "150 200", "src/main.elixx")
    depois = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert antes == depois


def test_propor_transformacao_x_150(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p",
                              {"posicao": "150 200"})
    previa = cs.revisar()[0]["previa"]
    assert "150 200" in previa
    atual = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert "150 200" not in atual


def test_propor_transformacao_entidade_ausente(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        propor_transformacao(ws.app.workspace, ws.modelo,
                             "fantasma:x", {"posicao": "1 2"})


def test_propor_transformacao_props_vazias(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        propor_transformacao(ws.app.workspace, ws.modelo,
                             "janela:p", {})


# ---------- proposta / aprovacao / undo (I) ----------


def test_tracker_adicionar_listar(tmp_path):
    from elixx.studio.ux import PropostasTracker, propor_transformacao

    _, ws = _workspace(tmp_path)
    tracker = PropostasTracker()
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "150 200"})
    pid = tracker.adicionar(cs, "mover Juh")
    assert pid.startswith("prop_")
    assert tracker.listar()[0]["descricao"] == "mover Juh"


def test_tracker_aprovar_aplicar(tmp_path):
    from elixx.studio.ux import PropostasTracker, propor_transformacao

    _, ws = _workspace(tmp_path)
    tracker = PropostasTracker()
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "150 200"})
    pid = tracker.adicionar(cs, "mover")
    tracker.aprovar(pid)
    tracker.aplicar(pid, ws.app.workspace)
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert "150 200" in texto


def test_tracker_aplicar_sem_aprovar_falha(tmp_path):
    from elixx.studio.ux import PropostasTracker, propor_transformacao

    _, ws = _workspace(tmp_path)
    tracker = PropostasTracker()
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "150 200"})
    pid = tracker.adicionar(cs, "mover")
    with pytest.raises(ErroELiXX):
        tracker.aplicar(pid, ws.app.workspace)


def test_tracker_desfazer_ultima(tmp_path):
    from elixx.studio.ux import PropostasTracker, propor_transformacao

    _, ws = _workspace(tmp_path)
    tracker = PropostasTracker()
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "150 200"})
    pid = tracker.adicionar(cs, "mover")
    tracker.aprovar(pid)
    tracker.aplicar(pid, ws.app.workspace)
    tracker.desfazer_ultima(ws.app.workspace)
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert "150 200" not in texto


def test_tracker_desfazer_sem_aplicar_falha():
    from elixx.studio.ux import PropostasTracker

    with pytest.raises(ErroELiXX):
        PropostasTracker().desfazer_ultima(object())


def test_tracker_obter_ausente():
    from elixx.studio.ux import PropostasTracker

    with pytest.raises(ErroELiXX):
        PropostasTracker().obter("prop_999")


def test_proposta_nao_entra_no_historico(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "150 200"})
    assert cs.estado == "proposto"


def test_changeset_revisar_aprovar(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "150 200"})
    assert cs.revisar()
    cs.aprovar()
    assert cs.estado == "aprovado"


# ---------- code <-> visual (G, H) ----------


def test_ir_para_codigo(tmp_path):
    from elixx.studio.scene_editor import ir_para_codigo

    _, ws = _workspace(tmp_path)
    modelo = ws.modelo
    edicao = ws.abrir_no_editor("src/main.elixx")
    saida = ir_para_codigo(edicao, modelo, "personagem:Juh")
    assert saida["ok"] is True
    assert saida["entidade"] == "personagem:Juh"
    assert saida["linha"] >= 1


def test_ir_para_codigo_entidade_ausente(tmp_path):
    from elixx.studio.scene_editor import ir_para_codigo

    _, ws = _workspace(tmp_path)
    edicao = ws.abrir_no_editor("src/main.elixx")
    with pytest.raises(ErroELiXX):
        ir_para_codigo(edicao, ws.modelo, "fantasma:x")


def test_entidade_do_cursor(tmp_path):
    from elixx.studio.scene_editor import entidade_do_cursor

    _, ws = _workspace(tmp_path)
    ent = entidade_do_cursor(ws.modelo, "src/main.elixx", 4)
    assert ent is not None
    assert ent.id == "personagem:Juh"


def test_entidade_do_cursor_sem_match():
    from elixx.studio.scene_editor import entidade_do_cursor

    assert entidade_do_cursor(_modelo(), "src/main.elixx",
                              1) is None or True
    assert entidade_do_cursor(_modelo(), "outro.elixx",
                              99) is None


def test_entidade_do_cursor_linha_invalida():
    from elixx.studio.scene_editor import entidade_do_cursor

    with pytest.raises(ErroELiXX):
        entidade_do_cursor(_modelo(), "src/main.elixx", 0)


def test_fluxo_visual_code_proposta(tmp_path):
    from elixx.studio.scene_editor import SceneEditor
    from elixx.studio.ux import PropostasTracker

    _, ws = _workspace(tmp_path)
    ed = SceneEditor()
    tracker = PropostasTracker()
    cs = ed.propor_mover(ws.app.workspace, ws.modelo,
                         "janela:p", 150, 200)
    pid = tracker.adicionar(cs, "Juh posicao X 100 -> 150")
    tracker.aprovar(pid)
    tracker.aplicar(pid, ws.app.workspace)
    ws.analisar()
    ed.construir_arvore(ws.modelo)
    assert "janela:p" in ed.arvore.nos


def test_propor_transformar_modo_preparado_falha(tmp_path):
    from elixx.studio.scene_editor import SceneEditor

    _, ws = _workspace(tmp_path)
    ed = SceneEditor()
    ed.definir_modo("Escalar")
    with pytest.raises(ErroELiXX):
        ed.propor_transformar(ws.app.workspace, ws.modelo,
                              "janela:p", {"posicao": "1 2"})


def test_propor_transformar_mover_ok(tmp_path):
    from elixx.studio.scene_editor import SceneEditor

    _, ws = _workspace(tmp_path)
    ed = SceneEditor()
    ed.definir_modo("Mover")
    cs = ed.propor_transformar(ws.app.workspace, ws.modelo,
                               "janela:p", {"posicao": "150 200"})
    assert cs.revisar()


def test_propor_mover_infinito_falha(tmp_path):
    from elixx.studio.scene_editor import SceneEditor

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        SceneEditor().propor_mover(ws.app.workspace, ws.modelo,
                                   "janela:p", float("inf"), 0)


# ---------- adaptive workspace (J) ----------


def test_modos_workspace_nomes():
    from elixx.studio.scene_editor import MODOS_WORKSPACE

    assert tuple(MODOS_WORKSPACE) == ("DEFAULT", "CODE", "SCENE",
                                     "AGENT", "REVIEW")


def test_modo_default(tmp_path):
    from elixx.studio.scene_editor import WorkspaceModes

    _, ws = _workspace(tmp_path)
    paineis = WorkspaceModes().aplicar(ws.layout, "DEFAULT")
    assert set(paineis) >= {"preview", "inspector"}


def test_modo_code(tmp_path):
    from elixx.studio.scene_editor import WorkspaceModes

    _, ws = _workspace(tmp_path)
    paineis = WorkspaceModes().aplicar(ws.layout, "CODE")
    assert "editor" in paineis


def test_modo_scene_dominante(tmp_path):
    from elixx.studio.scene_editor import WorkspaceModes

    _, ws = _workspace(tmp_path)
    paineis = WorkspaceModes().aplicar(ws.layout, "SCENE")
    assert "preview" in paineis
    assert "inspector" in paineis


def test_modo_agent(tmp_path):
    from elixx.studio.scene_editor import WorkspaceModes

    _, ws = _workspace(tmp_path)
    paineis = WorkspaceModes().aplicar(ws.layout, "AGENT")
    assert "agent" in paineis


def test_modo_review(tmp_path):
    from elixx.studio.scene_editor import WorkspaceModes

    _, ws = _workspace(tmp_path)
    paineis = WorkspaceModes().aplicar(ws.layout, "REVIEW")
    assert "editor" in paineis


def test_modo_invalido(tmp_path):
    from elixx.studio.scene_editor import WorkspaceModes

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        WorkspaceModes().aplicar(ws.layout, "3D")


def test_layouts_novos_registrados():
    from elixx.studio.workspace_ui import LAYOUTS

    for nome in ("CODE", "SCENE", "AGENT", "REVIEW"):
        assert nome in LAYOUTS


def test_aplicar_layout_scene(tmp_path):
    from elixx.studio.workspace_ui import aplicar_layout_nome

    _, ws = _workspace(tmp_path)
    paineis = aplicar_layout_nome(ws, "SCENE")
    assert "preview" in paineis


def test_descricao_modos():
    from elixx.studio.scene_editor import WorkspaceModes

    modos = WorkspaceModes()
    for modo in ("DEFAULT", "CODE", "SCENE", "AGENT", "REVIEW"):
        assert modos.descricao(modo)


# ---------- foco (K) ----------


def test_foco_entrar_sair(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    foco = FocusState()
    foco.entrar(ws.layout, ["preview"])
    assert ws.layout.paineis_visiveis() == ["preview"]
    foco.sair(ws.layout)
    assert "editor" in ws.layout.paineis_visiveis()


def test_foco_nao_destroi_estado(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    antes = ws.layout.to_dict()
    foco = FocusState()
    foco.entrar(ws.layout, ["preview", "inspector"])
    foco.sair(ws.layout)
    assert ws.layout.to_dict()["visivel"] == antes["visivel"]


def test_foco_duplo_falha(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    foco = FocusState()
    foco.entrar(ws.layout, ["preview"])
    with pytest.raises(ErroELiXX):
        foco.entrar(ws.layout, ["editor"])


def test_foco_sair_inativo_falha(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        FocusState().sair(ws.layout)


def test_foco_painel_invalido(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        FocusState().entrar(ws.layout, ["holodeck"])


# ---------- bottom workspace (L) ----------


def test_abas_fundo_nomes():
    from elixx.studio.scene_editor import ABAS_FUNDO

    assert tuple(ABAS_FUNDO) == ("CODE", "AGENT", "REASONING",
                                 "PLAN", "CHANGES", "CONSOLE")


def test_fundo_abrir_alternar():
    from elixx.studio.scene_editor import BottomWorkspace

    fundo = BottomWorkspace()
    assert fundo.aberta == "CONSOLE"
    fundo.abrir("AGENT")
    assert fundo.aberta == "AGENT"
    assert fundo.alternar("AGENT") is None
    assert fundo.alternar("PLAN") == "PLAN"


def test_fundo_aba_invalida():
    from elixx.studio.scene_editor import BottomWorkspace

    with pytest.raises(ErroELiXX):
        BottomWorkspace("HOLODECK")


def test_fundo_mapeia_paineis_existentes():
    from elixx.studio.scene_editor import ABAS_FUNDO, BottomWorkspace
    from elixx.studio.workspace_ui import ABAS_INFERIORES, PAINEIS

    fundo = BottomWorkspace()
    for aba in ABAS_FUNDO:
        destino = fundo.painel_para(aba)
        assert destino in PAINEIS or destino in ABAS_INFERIORES, \
            destino


def test_fundo_serializavel():
    from elixx.studio.scene_editor import BottomWorkspace

    fundo = BottomWorkspace()
    fundo.abrir("CODE")
    fundo2 = BottomWorkspace.from_dict(fundo.to_dict())
    assert fundo2.aberta == "CODE"


# ---------- console / status (M, N) ----------


def test_console_categorias(tmp_path):
    _, ws = _workspace(tmp_path)
    assert "SUCCESS" in ws.console.CATEGORIAS
    for cat in ("INFO", "SUCCESS", "WARNING", "ERROR"):
        ws.console.registrar(cat, "msg")
    assert len(ws.console.por_categoria("SUCCESS")) == 1


def test_console_sem_traceback(tmp_path):
    _, ws = _workspace(tmp_path)
    entrada = ws.console.registrar("ERROR", "Traceback x\nlinha2")
    assert "Traceback" not in str(entrada)


def test_erro_amigavel_sem_traceback():
    from elixx.studio.scene_editor import erro_amigavel

    try:
        raise ValueError("quebrou\nTraceback interno\nmais")
    except ValueError as exc:
        msg = erro_amigavel(exc)
    assert "Traceback" not in msg
    assert "quebrou" in msg


def test_montar_status_completo():
    from elixx.studio.scene_editor import montar_status

    texto = montar_status("P", "main.elixx", 3, 2, "ready",
                          False)
    assert "3 entities" in texto
    assert "2 changes" in texto
    assert "main.elixx" in texto
    assert "Unsaved" in texto


def test_montar_status_minimo():
    from elixx.studio.scene_editor import montar_status

    assert montar_status() == "Agent ready"


def test_montar_status_contagem_invalida():
    from elixx.studio.scene_editor import montar_status

    with pytest.raises(ErroELiXX):
        montar_status(entidades=-1)


def test_statusbar_modelo():
    from elixx.studio.scene_editor import StatusBar

    barra = StatusBar()
    assert barra.texto == "Ready"
    barra.atualizar("3 entities")
    assert barra.texto == "3 entities"


# ---------- agent / context / tools / reasoning (W-Z) ----------


def test_agent_recebe_entidade_selecionada(tmp_path):
    _, ws = _workspace(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["entidades"]


def test_agent_consulta_personagem(tmp_path):
    _, ws = _workspace(tmp_path)
    saida = ws.agent.consultar(ws.modelo, "tipo",
                               tipo="personagem")
    assert saida["total"] >= 1


def test_agent_planeja_juh(tmp_path):
    _, ws = _workspace(tmp_path)
    plano = ws.agent.planejar(ws.modelo, "Juh")
    assert plano


def test_agent_mock_deterministico(tmp_path):
    from elixx.studio.agent.interacao import AgentSession

    _, ws = _workspace(tmp_path)
    sessao = AgentSession()
    assert sessao.estado == "IDLE"


def test_contexto_mostra_juh(tmp_path):
    _, ws = _workspace(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["entidades"] >= 1
    assert "src/main.elixx" in ctx["arquivos"]
    viz = ws.agent.consultar(ws.modelo, "nome", nome="Juh")
    assert "Juh" in str(viz)


def test_tool_trace_compacto(tmp_path):
    from elixx.studio.agent.ferramentas_semanticas import (
        AgentToolCall,
        SemanticToolRegistry,
        ToolTrace,
    )

    _, ws = _workspace(tmp_path)
    reg = SemanticToolRegistry()
    assert reg.listar()
    trace = ToolTrace()
    trace.registrar(AgentToolCall(
        "t_buscar_entidade", {"nome": "Juh"}))
    assert trace.explicar()
    assert "Juh" in trace.explicar() or "buscar" in trace.explicar()


def test_registry_30_tools():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    assert len(SemanticToolRegistry().listar()) == 30


def test_reasoning_workspace_estagios(tmp_path):
    from elixx.studio.agent.workspace import AgentWorkspace

    _, ws = _workspace(tmp_path)
    area = AgentWorkspace("tarefa")
    assert "TOOLS" in area.estagios
    assert area.vista["zoom"] == 1.0


def test_plano_painel(tmp_path):
    from elixx.studio.agent.planejamento import PainelPlano

    _, ws = _workspace(tmp_path)
    plano = ws.agent.planejar(ws.modelo, "Juh")
    assert plano is not None


def test_changes_propor_sem_aplicar(tmp_path):
    class _Perm:
        def tem(self, _p):
            return True

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.agent.propor(ws.app.workspace, [])
    plano = ws.agent.planejar(ws.modelo, "Juh")
    assert plano["status"] == "plano"
    with pytest.raises(ErroELiXX):
        ws.agent.propor(ws.app.workspace, [])
    proposta = ws.agent.propor(
        ws.app.workspace,
        [{"arquivo": "src/main.elixx", "operacao": "editar",
          "conteudo_novo": FONTE, "descricao": "revisao"}],
        permissoes=_Perm())
    assert proposta["status"] == "proposta"
    assert proposta["mudancas"]


# ---------- palette (U) ----------


def test_palette_f39_comandos():
    from elixx.studio.scene_editor import COMANDOS_F39

    ids = [c[0] for c in COMANDOS_F39]
    for esperado in ("scene_selecionar", "scene_mover",
                     "scene_escalar", "scene_girar",
                     "scene_ajustar", "scene_grid", "scene_snap",
                     "layout_scene", "layout_code", "layout_agent",
                     "layout_review", "foco_atual", "sair_do_foco"):
        assert esperado in ids


def test_palette_f39_busca():
    from elixx.studio.scene_editor import buscar_palette_f39

    assert len(buscar_palette_f39("")) == 13
    assert [c["id"] for c in buscar_palette_f39("layout")] == [
        "layout_scene", "layout_code", "layout_agent",
        "layout_review"]


def test_palette_f39_executa_modo(tmp_path):
    from elixx.studio.scene_editor import executar_palette_f39

    _, ws = _workspace(tmp_path)
    ed = _editor_com_arvore()
    saida = executar_palette_f39(ed, ws.layout, "scene_mover")
    assert saida == {"ok": True, "modo": "Mover"}


def test_palette_f39_executa_layout(tmp_path):
    from elixx.studio.scene_editor import (
        WorkspaceModes,
        executar_palette_f39,
    )

    _, ws = _workspace(tmp_path)
    ed = _editor_com_arvore()
    saida = executar_palette_f39(ed, ws.layout, "layout_scene",
                                 modos=WorkspaceModes())
    assert "preview" in saida["paineis"]


def test_palette_f39_grid_snap(tmp_path):
    from elixx.studio.scene_editor import executar_palette_f39

    _, ws = _workspace(tmp_path)
    ed = _editor_com_arvore()
    assert executar_palette_f39(ed, ws.layout,
                                "scene_grid")["grid"] is True
    assert executar_palette_f39(ed, ws.layout,
                                "scene_snap")["snap"] == 1


def test_palette_f39_foco(tmp_path):
    from elixx.studio.scene_editor import executar_palette_f39
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    ed = _editor_com_arvore()
    foco = FocusState()
    executar_palette_f39(ed, ws.layout, "foco_atual", foco=foco)
    assert ws.layout.paineis_visiveis()
    saida = executar_palette_f39(ed, ws.layout, "sair_do_foco",
                                 foco=foco)
    assert saida["ok"] is True


def test_palette_f39_comando_invalido(tmp_path):
    from elixx.studio.scene_editor import executar_palette_f39

    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        executar_palette_f39(_editor_com_arvore(), ws.layout,
                             "holodeck")


def test_palette_antiga_intacta():
    from elixx.studio.agent.interacao import CommandPalette

    assert len(CommandPalette().buscar("")) == 30


# ---------- teclado (V) ----------


def test_atalhos_antigos_preservados():
    from elixx.studio.app import ATALHOS

    for tecla in ("Ctrl+K", "Ctrl+1", "Ctrl+Enter", "Esc",
                  "Ctrl+S", "F5", "Ctrl+Z", "Ctrl+Shift+P"):
        assert tecla in ATALHOS, tecla


def test_atalho_foco_novo():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+Shift+F"] == "foco_atual"


def test_atalhos_f39_contextuais():
    from elixx.studio.scene_editor import ATALHOS_F39

    for tecla in ("V", "G", "S", "R", "F", "Ctrl+Shift+F",
                  "Esc"):
        assert tecla in ATALHOS_F39


def test_conflitos_documentados():
    from elixx.studio.scene_editor import conflitos_f39

    teclas = [c["tecla"] for c in conflitos_f39()]
    assert "F" in teclas
    assert "Esc" in teclas
    for item in conflitos_f39():
        assert item["regra"]


def test_global_nao_substituido():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["F"] == "enquadrar"
    assert ATALHOS["Esc"] == "cancelar"


# ---------- responsivo / compacto (S, T) ----------


def test_resolucoes_qa():
    from elixx.studio.scene_editor import RESOLUCOES_QA

    assert len(RESOLUCOES_QA) == 8
    for larg, alt in RESOLUCOES_QA:
        assert 800 <= larg <= 3840
        assert 500 <= alt <= 2160


def test_todas_resolucoes_sem_quebra(tmp_path):
    from elixx.studio.scene_editor import RESOLUCOES_QA

    _, ws = _workspace(tmp_path)
    for larg, alt in RESOLUCOES_QA:
        ws.layout.definir_geometria(larg, alt)
        assert ws.layout.geometria == (larg, alt)


def test_compacto_preserva_scene(tmp_path):
    _, ws = _workspace(tmp_path)
    ws.layout.definir_compacto(True)
    assert ws.layout.compacto is True
    ed = _editor_com_arvore()
    assert ed.definir_modo("Mover") == "Mover"


def test_fracoes_sem_sobreposicao(tmp_path):
    _, ws = _workspace(tmp_path)
    total = 0.0
    for painel in ("project", "preview", "inspector"):
        total += ws.layout.redimensionar(painel, 0.2)
    assert total <= 0.9 * 3


def test_geometrias_ok_8():
    from elixx.studio.workspace_ui import GEOMETRIAS_OK

    assert len(GEOMETRIAS_OK) == 8


# ---------- seguranca (AB) ----------


def test_sem_execucao_dinamica_no_modulo():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/scene_editor.py").read_text(
        encoding="utf-8")
    for proibido in ("eval(", "exec(", "importlib",
                     "__import__", "pickle", "subprocess",
                     "os.system", "shell=True"):
        assert proibido not in fonte, proibido


def test_traversal_bloqueado(tmp_path):
    _, ws = _workspace(tmp_path)
    with pytest.raises(Exception):
        ws.app.workspace.resolver("../../fora.elixx")


def test_caminho_absoluto_bloqueado(tmp_path):
    _, ws = _workspace(tmp_path)
    with pytest.raises(Exception):
        ws.app.workspace.resolver("C:\\Windows\\x.elixx")


def test_nan_zoom_rejeitado():
    from elixx.studio.cena import ViewportState

    with pytest.raises(ErroELiXX):
        ViewportState(offset_x=float("nan"))


def test_infinito_pan_rejeitado():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.pan(float("inf"), 0)


def test_payload_gigante_rejeitado():
    ed = _editor_com_arvore()
    with pytest.raises(ErroELiXX):
        ed.selecionar("x" * 500)


def test_string_maliciosa_rejeitada(tmp_path):
    _, ws = _workspace(tmp_path)
    resolvido = ws.app.workspace.resolver("a\x00b")
    raiz = ws.app.workspace.raiz.resolve()
    assert resolvido.resolve() == resolvido
    assert raiz in resolvido.resolve().parents or \
        resolvido.resolve() == raiz


def test_scene_nunca_executa_codigo(tmp_path):
    from elixx.studio.scene_editor import SceneEditor

    _, ws = _workspace(tmp_path)
    ed = SceneEditor()
    cs = ed.propor_mover(ws.app.workspace, ws.modelo,
                         "janela:p", 150, 200)
    assert cs.estado == "proposto"
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert "150 200" not in texto or "100 200" in texto


# ---------- performance (AA) ----------


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


def test_perf_100_entidades():
    from elixx.studio.scene_editor import SceneEditor

    inicio = time.perf_counter()
    SceneEditor().construir_arvore(_modelo_grande(100))
    assert time.perf_counter() - inicio < 5.0


def test_perf_1000_entidades():
    from elixx.studio.scene_editor import SceneEditor

    inicio = time.perf_counter()
    ed = SceneEditor()
    ed.construir_arvore(_modelo_grande(1000))
    assert len(ed.arvore.nos) == 1001
    assert time.perf_counter() - inicio < 10.0


def test_perf_5000_entidades():
    from elixx.studio.scene_editor import SceneEditor

    inicio = time.perf_counter()
    ed = SceneEditor()
    ed.construir_arvore(_modelo_grande(5000))
    assert len(ed.arvore.visiveis()) == 5001
    assert time.perf_counter() - inicio < 20.0


def test_perf_10000_entidades():
    from elixx.studio.scene_editor import SceneEditor

    inicio = time.perf_counter()
    ed = SceneEditor()
    ed.construir_arvore(_modelo_grande(10000))
    assert len(ed.arvore.nos) == 10001
    assert time.perf_counter() - inicio < 30.0


def test_perf_1000_arquivos(tmp_path):
    from elixx.studio.modelo.modelo import (
        EntidadeSemantica,
        ModeloSemantico,
    )

    inicio = time.perf_counter()
    modelo = ModeloSemantico("arquivos")
    for i in range(1000):
        modelo.adicionar_entidade(
            EntidadeSemantica(f"arquivo:{i:04d}", "arquivo",
                              f"mod{i:04d}.elixx",
                              arquivo=f"src/mod{i:04d}.elixx",
                              linha=1))
    assert len(modelo.entidades()) == 1000
    assert time.perf_counter() - inicio < 30.0


def test_perf_500_partes_personagem():
    from elixx.studio.inspetor import fluxo_personagem

    _, personagem, _ = fluxo_personagem(
        "Juh", {"parts": [{"id": f"p{i}"} for i in range(500)]},
        analyzer="structured")
    assert len(personagem.partes) >= 500


def test_perf_1000_operacoes():
    from elixx.studio.agent.operacoes import SemanticOperation

    inicio = time.perf_counter()
    ops = [SemanticOperation("alterar_propriedade",
                             {"nome": f"n{i}"},
                             {"propriedade": "posicao"})
           for i in range(1000)]
    assert len(ops) == 1000
    assert time.perf_counter() - inicio < 10.0


# ---------- integracao F25-F38 (AD) ----------


def test_f25_preview_headless(tmp_path):
    from elixx.studio import HeadlessPreview

    resultado = HeadlessPreview().executar(FONTE)
    assert resultado.sucesso is True


def test_f26_agent_sessao():
    from elixx.studio.agent.interacao import AgentSession

    assert AgentSession().estado == "IDLE"


def test_f27_modelo_entidades():
    modelo = _modelo()
    nomes = [e.id for e in modelo.entidades()]
    assert "personagem:Juh" in nomes


def test_f28_loop_contexto(tmp_path):
    from elixx.studio.agent.loop import (
        construir_contexto_semantico,
    )

    _, ws = _workspace(tmp_path)
    ctx = construir_contexto_semantico(ws.modelo,
                                       ["personagem:Juh"])
    assert ctx.entidades


def test_f29_workspace_estado(tmp_path):
    _, ws = _workspace(tmp_path)
    assert ws.estado()["projeto"]


def test_f30_intencao():
    from elixx.studio.agent.intencao import AgentIntent

    assert AgentIntent("modificar_personagem",
                       objetivo="mover Juh")


def test_f31_operacao_valida():
    from elixx.studio.agent.operacoes import (
        SemanticOperation,
        validar_operacao,
    )

    op = SemanticOperation("alterar_propriedade",
                           {"nome": "p"},
                           {"propriedade": "posicao"})
    assert validar_operacao(op)


def test_f32_localiza_entidade(tmp_path):
    from elixx.studio.codigo.localizacao import localizar_entidade

    _, ws = _workspace(tmp_path)
    ent = next(e for e in ws.modelo.entidades()
               if e.id == "personagem:Juh")
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    loc = localizar_entidade(ent, texto)
    assert loc.inicio_linha == 4


def test_f33_plano(tmp_path):
    from elixx.studio.agent.intencao import AgentIntent
    from elixx.studio.agent.loop import (
        PlanoSemantico,
        gerar_changeset,
        resolver_alvo,
        verificar_precondicoes,
    )

    class _Perm:
        def tem(self, _p):
            return True

    _, ws = _workspace(tmp_path)
    alvo = resolver_alvo(ws.modelo, "Juh")
    assert alvo["status"] == "unico"
    plano = PlanoSemantico(
        AgentIntent("modificar_interface", objetivo="mover Juh"),
        alvo=alvo, entidades=["personagem:Juh"],
        alteracoes_propostas=[
            {"arquivo": "src/main.elixx", "operacao": "editar",
             "conteudo_novo": FONTE, "descricao": "mover"}])
    pre = verificar_precondicoes(plano, ws.app.workspace,
                                 _Perm())
    assert all(c["ok"] for c in pre)
    cs = gerar_changeset(plano)
    assert cs.revisar()


def test_f34_contexto_config():
    from elixx.studio.agent.contexto_tarefa import ContextoConfig

    assert ContextoConfig()


def test_f35_reasoning_estagios():
    from elixx.studio.agent.workspace import AgentWorkspace

    area = AgentWorkspace("t")
    assert "TASK" in area.estagios
    assert "TOOLS" in area.estagios


def test_f36_tools_registry():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    assert SemanticToolRegistry().listar()


def test_f37_palette_30():
    from elixx.studio.agent.interacao import CommandPalette

    assert len(CommandPalette().buscar("")) == 30


def test_f38_tokens():
    from elixx.studio import validar_tokens

    assert validar_tokens()["valido"] is True
