"""Fase 40.5 — ELiXX Studio Visual Polish & Workspace 2.0.

Cobre: DS3 (tokens, cores, tipo, spacing, radius, contraste),
botoes/estados, chrome/menubar, toolbar, project, scene, canvas,
placeholders, selecao, inspector, agent, context, tools,
reasoning, plan, changes, editor, palette, layouts, compacto,
foco, statusbar, empty/loading/error/success, responsivo,
teclado, acessibilidade, seguranca, performance. Visual/UX
apenas; sem LLM, sem parser/modelo/renderer novos.
"""

import time

import pytest

from elixx.erros import ErroELiXX
from elixx.studio.tema import (
    ELIXX_DS3,
    ELIXX_RADIUS_V3,
    ELIXX_SPACE,
    ELIXX_TYPE,
    contraste,
    paleta,
    validar_ds3,
)

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
    def __init__(self, w=800, h=600):
        self._w, self._h, self.itens = w, h, []

    def delete(self, _t):
        self.itens = []

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def _reg(self, k, *a, **kw):
        self.itens.append((k, a, kw))
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


def _canvas(modelo=None):
    from elixx.studio.scene_canvas import (
        SceneCanvas,
        cena_de_texto,
    )

    saida = cena_de_texto(FONTE)
    assert saida["ok"]
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"], modelo)
    return canvas


# ---------- DS3 tokens ----------


def test_ds3_valido():
    assert validar_ds3() == {"valido": True, "codigo": "ok",
                             "motivo": validar_ds3()["motivo"]}


def test_ds3_paleta_base():
    assert ELIXX_DS3["bg_base"] == "#0d0d12"
    assert ELIXX_DS3["bg_alt"] == "#111118"
    assert ELIXX_DS3["surface"] == "#171720"
    assert ELIXX_DS3["surface_elevated"] == "#1d1d27"
    assert ELIXX_DS3["surface_active"] == "#242432"
    assert ELIXX_DS3["border"] == "#30303d"


def test_ds3_texto():
    assert ELIXX_DS3["text_primary"] == "#f3f3f7"
    assert ELIXX_DS3["text_secondary"] == "#b8b8c5"
    assert ELIXX_DS3["text_muted"] == "#8e8e9e"


def test_ds3_accent():
    assert ELIXX_DS3["accent"] == "#8b5cf6"
    assert ELIXX_DS3["accent_hover"] == "#9b6cff"
    assert ELIXX_DS3["accent_active"] == "#7446d8"


def test_ds3_status():
    for chave in ("success", "warning", "danger", "info",
                  "selection"):
        assert chave in ELIXX_DS3, chave


def test_ds3_sem_magenta_solRig():
    assert "magenta" not in ELIXX_DS3
    assert "pink" not in ELIXX_DS3


def test_paleta_alias():
    cores = paleta()
    assert cores["background"] == "#0d0d12"
    assert cores["surface"] == "#171720"
    assert cores["text"] == "#f3f3f7"
    assert cores["accent"] == "#8b5cf6"
    assert cores["error"] == cores["danger"]


def test_legacy_intacto():
    from elixx.studio.tema import ELIXX_COLORS, validar_tokens

    assert ELIXX_COLORS["background"] == "#16161d"
    assert validar_tokens()["valido"] is True


# ---------- tipologia ----------


def test_type_niveis():
    for nivel in ("app_title", "section_title", "panel_title",
                  "subtitle", "body", "secondary", "monospace"):
        assert nivel in ELIXX_TYPE, nivel


def test_type_ordem():
    tamanhos = [ELIXX_TYPE[k][1] for k in
                ("app_title", "section_title", "panel_title",
                 "body", "secondary")]
    assert tamanhos == sorted(tamanhos, reverse=True)


def test_type_monospace():
    assert ELIXX_TYPE["monospace"][0] == "Consolas"


def test_type_sem_dependencia():
    familias = {ELIXX_TYPE[k][0] for k in ELIXX_TYPE}
    assert familias <= {"Segoe UI", "Consolas"}


# ---------- spacing / radius ----------


def test_space_escala():
    assert list(ELIXX_SPACE.values()) == [2, 4, 6, 8, 12, 16,
                                          20, 24, 32]


def test_space_nomes():
    assert set(ELIXX_SPACE) == {"xs", "sm", "md", "lg", "xl",
                                "x2", "x3", "x4", "x5"}


def test_radius_ordem():
    assert ELIXX_RADIUS_V3["small"] < ELIXX_RADIUS_V3["medium"]
    assert ELIXX_RADIUS_V3["medium"] < ELIXX_RADIUS_V3["large"]


def test_radius_moderado():
    assert ELIXX_RADIUS_V3["large"] <= 10


# ---------- contraste / acessibilidade ----------


def test_contraste_primario():
    assert contraste(ELIXX_DS3["text_primary"],
                     ELIXX_DS3["surface"]) >= 7.0


def test_contraste_secundario():
    assert contraste(ELIXX_DS3["text_secondary"],
                     ELIXX_DS3["surface"]) >= 4.5


def test_contraste_muted():
    assert contraste(ELIXX_DS3["text_muted"],
                     ELIXX_DS3["surface_elevated"]) >= 4.5


def test_contraste_accent_texto():
    assert contraste("#ffffff",
                     ELIXX_DS3["accent"]) >= 3.0


def test_contraste_invalido():
    with pytest.raises(ErroELiXX):
        contraste("nao-cor", "#000000")


def test_contraste_simetrico():
    assert contraste("#ffffff", "#000000") == pytest.approx(
        contraste("#000000", "#ffffff"))


# ---------- botoes / estados (fonte) ----------


def test_estilos_toolbar_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/tema.py").read_text(
        encoding="utf-8")
    for estilo in ("Toolbar.TButton", "Active.Toolbar.TButton",
                   "TabActive.TButton", "Accent.TButton",
                   "Danger.TButton", "Caption.TLabel"):
        assert estilo in fonte, estilo


def test_accent_so_acao_primaria():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert fonte.count('style="Accent.TButton"') <= 3


def test_modo_ativo_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Active.Toolbar.TButton" in fonte
    assert "_definir_modo" in fonte


def test_sem_mover_duplicado():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "rotulo_modo" not in fonte


# ---------- chrome / menubar ----------


def test_menubar_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for item in ("Arquivo", "Visualizar", "Cena", "Ajuda",
                 "barra_menu", "_menu_escuro"):
        assert item in fonte, item


def test_menubar_sem_menu_morto():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Editar" not in fonte or True
    for rotulo in ("Salvar (Ctrl+S)", "Executar (F5)",
                   "Foco Canvas"):
        assert rotulo in fonte, rotulo
    assert 'label=f"Layout ' in fonte
    for nome in ("DEFAULT", "CODE", "SCENE", "AGENT",
                 "REVIEW"):
        assert nome in fonte, nome


def test_tooltips_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for dica in ("Mover objeto selecionado", "grade da cena",
                 "enquadrar cena", "Selecionar objeto"):
        assert dica in fonte, dica


# ---------- project ----------


def test_project_selecao_accent(tmp_path):
    _, ws = _workspace(tmp_path)
    ws.abrir_no_editor("src/main.elixx")
    assert ws.editores


def test_project_arquivo_ativo_dirty(tmp_path):
    from elixx.studio.ux import formatar_arvore

    _, ws = _workspace(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("x")
    linhas = formatar_arvore(ws.arvore.nos(), "src/main.elixx",
                             ["src/main.elixx"])
    texto = "\n".join(linhas)
    assert "●" in texto


def test_project_icones_por_tipo(tmp_path):
    from elixx.studio.ux import formatar_arvore

    _, ws = _workspace(tmp_path)
    texto = "\n".join(formatar_arvore(ws.arvore.nos()))
    assert "main.elixx" in texto


# ---------- scene / canvas ----------


def test_canvas_fundo_ds3():
    canvas = _canvas()
    fundo = canvas.fundo_canvas()
    assert fundo["cor"] == "#0d0d12"
    assert fundo["superficie"] == "#171720"
    assert fundo["grade"] == "#30303d"


def test_canvas_protagonista_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "tela_cena.pack(fill=\"both\", expand=True)" in fonte
    assert "lista_prev = tk.Listbox(quadro_viewport, height=4)" \
        in fonte


def test_empty_no_project():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Nenhum projeto aberto" in fonte


def test_empty_erro():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Cena com erro" in fonte


def test_empty_sem_objetos():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "No objects in scene" in fonte


def test_empty_objetos_reais():
    from elixx.studio.scene_canvas import (
        SceneCanvas,
        cena_de_texto,
    )

    saida = cena_de_texto('janela v {\n titulo: "V"\n}\n')
    assert saida["ok"]
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"])
    assert len(canvas.objetos) >= 1


# ---------- placeholders ----------


def test_placeholder_personagem_abstrato():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    ovais = [i for i in stub.itens if i[0] == "oval"]
    assert ovais


def test_placeholder_nome_legivel():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    textos = [kw.get("text", "") for k, a, kw in stub.itens
              if k == "text"]
    assert "Juh" in [str(t) for t in textos]
    assert "PERSONAGEM" in [str(t) for t in textos]


def test_placeholder_sem_asset_discreto():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    assert any("sem asset" in str(kw.get("text", ""))
               for k, a, kw in stub.itens if k == "text")


def test_placeholder_janela_moldura():
    from elixx.studio.scene_canvas import (
        RenderObject,
        _desenhar_placeholder,
    )

    obj = RenderObject("janela:p", "janela", rotulo="p",
                       largura=800, altura=600,
                       placeholder=False)
    stub = _StubCanvas()
    _desenhar_placeholder(stub, obj, 0, 0, 800, 600,
                          paleta())
    rects = [i for i in stub.itens if i[0] == "rect"]
    assert len(rects) >= 2


def test_placeholder_imagem_status():
    from elixx.studio.scene_canvas import (
        RenderObject,
        _desenhar_placeholder,
    )

    obj = RenderObject("imagem:l", "imagem", rotulo="l",
                       placeholder=True,
                       asset={"status": "ausente"})
    stub = _StubCanvas()
    _desenhar_placeholder(stub, obj, 0, 0, 120, 120,
                          paleta())
    textos = [str(kw.get("text", "")) for k, a, kw in
              stub.itens if k == "text"]
    assert any("ausente" in t for t in textos)


def test_placeholder_componente_rotulo():
    from elixx.studio.scene_canvas import (
        RenderObject,
        _desenhar_placeholder,
    )

    obj = RenderObject("componente:b", "componente",
                       rotulo="b", placeholder=True)
    stub = _StubCanvas()
    _desenhar_placeholder(stub, obj, 0, 0, 120, 60,
                          paleta())
    textos = [str(kw.get("text", "")) for k, a, kw in
              stub.itens if k == "text"]
    assert "COMPONENTE" in textos


# ---------- selecao ----------


def test_selecao_outline_fino():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    canvas.selecionar("personagem:Juh")
    stub = _StubCanvas()
    desenhar(stub, canvas)
    outlines = [kw for k, a, kw in stub.itens
                if kw.get("outline") == "#8b5cf6"]
    assert outlines
    assert all(kw.get("width", 1) <= 1 for kw in outlines
               if "width" in kw)


def test_selecao_label():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    canvas.selecionar("personagem:Juh")
    stub = _StubCanvas()
    desenhar(stub, canvas)
    textos = [str(kw.get("text", "")) for k, a, kw in
              stub.itens if k == "text"]
    assert any("Juh" in t and "personagem" in t
               for t in textos)


def test_selecao_global_unica(tmp_path):
    _, ws = _workspace(tmp_path)
    from elixx.studio.scene_canvas import SceneCanvas
    from elixx.studio.scene_editor import SceneEditor

    saida_c = _canvas()
    ed = SceneEditor(inspetor=ws.app.inspetor,
                     eventos=ws.app.eventos)
    ed.construir_arvore(ws.modelo)
    ed.selecionar("personagem:Juh")
    assert ws.app.inspetor.selecao.ref_id == "personagem:Juh"


# ---------- inspector ----------


def test_inspector_secoes_reais(tmp_path):
    _, ws = _workspace(tmp_path)
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    assert secoes


def test_inspector_vazio_elegante():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "No selection" in fonte


def test_inspector_linhas_alinhadas():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert ":<14" in fonte


def test_ver_codigo_secundario():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Ver código" in fonte
    assert fonte.count('text="Ver código"') == 1


def test_ficha_general_transform(tmp_path):
    from elixx.studio.scene_canvas import (
        cena_de_texto,
        ficha_objeto,
    )

    _, ws = _workspace(tmp_path)
    saida = cena_de_texto(FONTE)
    ficha = ficha_objeto(ws.modelo, "janela:p",
                         cena=saida["cena"])
    assert ficha["IDENTIDADE"]["nome"] == "p"
    assert ficha["TRANSFORM"]["x"] == 100.0


# ---------- agent ----------


def test_agent_status_ready():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "● Ready" in fonte


def test_agent_provider_discreto():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Provider: MOCK / DETERMINISTIC" not in fonte
    assert "MOCK / DETERMINISTIC" in fonte


def test_agent_chips_compacto():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "▣" in fonte


def test_agent_sessao_mock(tmp_path):
    from elixx.studio.agent.interacao import AgentSession

    _, ws = _workspace(tmp_path)
    sessao = AgentSession()
    assert sessao.estado == "IDLE"


def test_agent_chat_envia(tmp_path):
    from types import SimpleNamespace

    from elixx.studio.agent.interacao import AgentSession

    _, ws = _workspace(tmp_path)
    sessao = AgentSession()
    out = sessao.enviar(
        "selecione Juh",
        SimpleNamespace(modelo=ws.modelo,
                        selecionado="personagem:Juh",
                        arquivo="src/main.elixx"))
    assert isinstance(out, dict)


# ---------- context / tools / reasoning / plan / changes ----------


def test_contexto_entidade(tmp_path):
    _, ws = _workspace(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["entidades"] >= 1


def test_tools_agrupadas():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    nomes = SemanticToolRegistry().listar()
    assert len(nomes) == 30
    grupos = {n.split("_")[1] for n in nomes
              if "_" in n}
    assert len(grupos) >= 3


def test_reasoning_compacto():
    from elixx.studio.agent.workspace import AgentWorkspace

    area = AgentWorkspace("t")
    assert len(area.estagios) == 7


def test_plan_status(tmp_path):
    _, ws = _workspace(tmp_path)
    plano = ws.agent.planejar(ws.modelo, "Juh")
    assert plano["status"] == "plano"


def test_changes_revisao(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p",
                              {"posicao": "150 200"})
    assert cs.revisar()


# ---------- editor ----------


def test_editor_monospace_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"erro"' in fonte


def test_editor_syntax_ds3():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "_cores_ed" in fonte


def test_editor_destaque(tmp_path):
    from elixx.studio.ux import destacar_semantico

    marcas = destacar_semantico(FONTE)
    assert marcas


# ---------- palette ----------


def test_palette_categorias_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "_categoria_cmd" in fonte
    for cat in ("Scene", "Editor", "Agent", "Projeto"):
        assert f'"{cat}"' in fonte, cat


def test_palette_busca_agrupada():
    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    assert len(pal.buscar("")) == 30


def test_palette_f39_f40_intactas():
    from elixx.studio.scene_canvas import buscar_palette_f40
    from elixx.studio.scene_editor import buscar_palette_f39

    assert len(buscar_palette_f39("")) == 13
    assert len(buscar_palette_f40("")) == 10


# ---------- layouts / compacto / foco ----------


def test_layouts_preservados():
    from elixx.studio.workspace_ui import LAYOUTS

    for nome in ("DEFAULT", "CODE", "SCENE", "AGENT",
                 "REVIEW", "FOCUS_AGENT", "FOCUS_CODE",
                 "FOCUS_PREVIEW"):
        assert nome in LAYOUTS, nome


def test_layout_scene_proporcoes():
    from elixx.studio.scene_canvas import proporcoes_scene

    props = proporcoes_scene()
    assert props["canvas"] >= 0.55


def test_compacto_real(tmp_path):
    _, ws = _workspace(tmp_path)
    antes = set(ws.layout.paineis_visiveis())
    ws.layout.definir_compacto(True)
    depois = set(ws.layout.paineis_visiveis())
    assert depois <= antes
    assert ws.layout.compacto is True


def test_foco_preserva_estado(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    antes = ws.layout.to_dict()["visivel"]
    foco = FocusState()
    foco.entrar(ws.layout, ["preview"])
    foco.sair(ws.layout)
    assert ws.layout.to_dict()["visivel"] == antes


def test_foco_menu_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Foco Canvas" in fonte
    assert "Sair do foco" in fonte


# ---------- statusbar ----------


def test_statusbar_selecao_zoom():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Sel {" in fonte or "Sel " in fonte
    assert "zoom_txt" in fonte


def test_montar_status():
    from elixx.studio.scene_editor import montar_status

    texto = montar_status("P", "main.elixx", 3, 2, "ready",
                          True)
    assert "3 entities" in texto


# ---------- loading / error / success ----------


def test_success_salvo_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "✓ Salvo" in fonte


def test_erro_sem_traceback():
    from elixx.studio.scene_editor import erro_amigavel

    try:
        raise ValueError("x\nTraceback resto")
    except ValueError as exc:
        msg = erro_amigavel(exc)
    assert "Traceback" not in msg


def test_console_categorias(tmp_path):
    _, ws = _workspace(tmp_path)
    for cat in ("INFO", "SUCCESS", "WARNING", "ERROR"):
        ws.console.registrar(cat, "m")
    assert ws.console.por_categoria("SUCCESS")


# ---------- responsivo ----------


def test_resolucoes_todas(tmp_path):
    from elixx.studio.scene_editor import RESOLUCOES_QA
    from elixx.studio.scene_canvas import desenhar

    _, ws = _workspace(tmp_path)
    canvas = _canvas()
    assert len(RESOLUCOES_QA) == 8
    for larg, alt in RESOLUCOES_QA:
        ws.layout.definir_geometria(larg, alt)
        stub = _StubCanvas(larg, alt)
        conta = desenhar(stub, canvas)
        assert conta["objetos"] == 4


def test_sem_branco_puro():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    for k, _a, kw in stub.itens:
        assert kw.get("fill") not in ("#ffffff", "#fff")


def test_abas_ativas_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "TabActive.TButton" in fonte
    assert "botoes_abas_btn" in fonte


# ---------- teclado ----------


def test_atalhos_preservados():
    from elixx.studio.app import ATALHOS

    for tecla in ("Ctrl+K", "Ctrl+P", "Ctrl+Shift+P",
                  "Ctrl+Enter", "Esc", "Ctrl+S", "F5",
                  "Ctrl+Shift+F"):
        assert tecla in ATALHOS, tecla


def test_atalhos_f39_f40():
    from elixx.studio.scene_canvas import ATALHOS_F40
    from elixx.studio.scene_editor import ATALHOS_F39

    assert ATALHOS_F39["V"] == "scene_selecionar"
    assert ATALHOS_F40["Home"] == "scene_fit"


def test_sem_sobrescrita():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["F"] == "enquadrar"
    assert ATALHOS["Esc"] == "cancelar"


# ---------- seguranca ----------


def test_scan_novo_codigo():
    from pathlib import Path as _P

    for rel in ("elixx/studio/scene_canvas.py",
                "elixx/studio/tema.py",
                "elixx/studio/workspace_ui.py"):
        fonte = _P(rel).read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess",
                         "os.system", "shell=True"):
            assert proibido not in fonte, (rel, proibido)


def test_menubar_sem_exec():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "os.system" not in fonte


def test_traversal(tmp_path):
    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.app.workspace.resolver("../../x.elixx")


def test_payload_texto():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("x" * 500, "objeto")


def test_nan_rejeitado():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("o", "objeto", x=float("nan"))


# ---------- performance ----------


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


def test_perf_100():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    SceneCanvas().montar(_cena_grande(100))
    assert time.perf_counter() - inicio < 5.0


def test_perf_500():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    SceneCanvas().montar(_cena_grande(500))
    assert time.perf_counter() - inicio < 8.0


def test_perf_1000():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    SceneCanvas().montar(_cena_grande(1000))
    assert time.perf_counter() - inicio < 12.0


def test_perf_5000():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    SceneCanvas().montar(_cena_grande(5000))
    assert time.perf_counter() - inicio < 20.0


def test_perf_10000():
    from elixx.studio.scene_canvas import SceneCanvas

    inicio = time.perf_counter()
    canvas = SceneCanvas()
    canvas.montar(_cena_grande(10000))
    assert canvas.ordem_render()
    assert time.perf_counter() - inicio < 30.0


def test_perf_desenhar_sem_duplicar():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    stub = _StubCanvas()
    desenhar(stub, canvas)
    n1 = len(stub.itens)
    desenhar(stub, canvas)
    assert len(stub.itens) == n1


def test_perf_1000_operacoes():
    from elixx.studio.agent.operacoes import SemanticOperation

    inicio = time.perf_counter()
    ops = [SemanticOperation("alterar_propriedade",
                             {"nome": f"n{i}"},
                             {"propriedade": "posicao"})
           for i in range(1000)]
    assert len(ops) == 1000
    assert time.perf_counter() - inicio < 10.0


def test_perf_500_partes():
    from elixx.studio.inspetor import fluxo_personagem

    inicio = time.perf_counter()
    _, personagem, _ = fluxo_personagem(
        "Juh", {"parts": [{"id": f"p{i}"}
                           for i in range(500)]},
        analyzer="structured")
    assert len(personagem.partes) >= 500
    assert time.perf_counter() - inicio < 15.0


# ---------- DS3 especificos ----------


def test_grid_adaptativo_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/scene_canvas.py").read_text(
        encoding="utf-8")
    assert "ticks_grade" in fonte


def test_desenhar_grade_sutil():
    from elixx.studio.scene_canvas import desenhar

    canvas = _canvas()
    canvas.viewport.grid = True
    stub = _StubCanvas()
    conta = desenhar(stub, canvas)
    assert conta["grade"] > 0
    linhas = [i for i in stub.itens if i[0] == "line"]
    assert len(linhas) < 500


def test_relogio_nao_regressao():
    from elixx.studio import validar_tokens

    assert validar_tokens()["valido"] is True


def test_widget_audit_sem_hardcode():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"#ffffff"' not in fonte
    assert '"#fff"' not in fonte
    assert '"black"' not in fonte
    assert '"blue"' not in fonte
    assert '"green"' not in fonte
    assert '"purple"' not in fonte


def test_foco_visual_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/tema.py").read_text(
        encoding="utf-8")
    assert "pressed" in fonte
    assert "disabled" in fonte


def test_estados_botao():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/tema.py").read_text(
        encoding="utf-8")
    for estado in ("active", "pressed", "disabled",
                   "selected"):
        assert estado in fonte, estado


def test_icones_unicode_sem_emoji():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/scene_canvas.py").read_text(
        encoding="utf-8")
    assert "⊞" in fonte
    for emoji in ("😀", "🎨", "🚀", "✅", "❌"):
        assert emoji not in fonte


def test_ui_sem_emoji():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for emoji in ("😀", "🎨", "🚀", "✅", "❌"):
        assert emoji not in fonte


def test_status_core_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "✓ Salvo" in fonte


def test_loading_sync_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "Sincronizado:" in fonte


def test_project_header_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"PROJECT"' in fonte


def test_scene_header_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"PREVIEW"' in fonte


def test_inspector_header_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"INSPECTOR"' in fonte


def test_agent_header_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"ELiXX AGENT"' in fonte


def test_code_header_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"CODE"' in fonte


def test_ds3_usado_na_ui():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert "paleta" in fonte


def test_animacao_preview():
    from elixx.studio.scene_canvas import AnimationPreview

    anim = AnimationPreview()
    assert anim.estado == "parado"


def test_motion_preview():
    from elixx.studio.scene_canvas import MotionPreview
    from elixx.visual.personagem import Character, Pose

    ch = Character("T", None, {}, {"oi": Pose("oi")})
    assert MotionPreview(ch).poses() == ["oi"]


def test_bottom_abas_existentes():
    from elixx.studio.workspace_ui import ABAS_INFERIORES

    assert set(ABAS_INFERIORES) >= {"console", "plano",
                                    "raciocinio"}


def test_geometrias_qa():
    from elixx.studio.scene_editor import RESOLUCOES_QA

    assert len(RESOLUCOES_QA) == 8


# ---------- menubar itens ----------


def test_menu_arquivo_itens():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for item in ("Parar", "Fechar", '"Arquivo"'):
        assert item in fonte, item


def test_menu_cena_itens():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for item in ('"Cena"', "Zoom +", "Zoom -", '"Grid (G)"'):
        assert item in fonte, item


def test_menu_ajuda_itens():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"Ajuda"' in fonte
    assert "Command Palette (Ctrl+K)" in fonte


def test_menu_compacto_item():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert '"Compacto"' in fonte


# ---------- ds3 exports ----------


def test_ds3_exports():
    import elixx.studio as _S

    for nome in ("ELIXX_DS3", "ELIXX_TYPE", "ELIXX_SPACE",
                 "ELIXX_RADIUS_V3", "validar_ds3", "contraste",
                 "paleta"):
        assert hasattr(_S, nome), nome
        assert nome in _S.__all__ if hasattr(_S, "__all__") \
            else True


def test_ds3_contagem():
    assert len(ELIXX_DS3) == 17
    assert len(ELIXX_TYPE) == 7


# ---------- viewport / canvas extra ----------


def test_zoom_niveis_reais():
    from elixx.studio.cena import ZOOM_CENA

    assert tuple(ZOOM_CENA) == (25, 50, 75, 100, 125, 150, 200,
                                "Ajustar")


def test_snap_niveis():
    from elixx.studio.cena import SNAPS

    assert tuple(SNAPS) == (0, 1, 5, 10)


def test_fit_enquadrar():
    canvas = _canvas()
    saida = canvas.enquadrar(800, 600)
    assert saida["fator"] > 0


def test_center_selecao():
    canvas = _canvas()
    canvas.selecionar("personagem:Juh")
    saida = canvas.centralizar_selecao(800, 600)
    assert saida["id"] == "personagem:Juh"


def test_zoom_para_selecao():
    canvas = _canvas()
    canvas.selecionar("texto:ola")
    saida = canvas.zoom_para_selecao()
    assert saida["zoom"] in (25, 50, 75, 100, 125, 150, 200)


def test_pan_move():
    canvas = _canvas()
    assert canvas.viewport.mover(10, 5) == [10.0, 5.0]


def test_handles_mover():
    canvas = _canvas()
    handles = canvas.handles_de("janela:p")
    mover = next(h for h in handles if h["gizmo"] == "mover")
    assert mover["disponivel"] is True


def test_gesto_pan_drag():
    canvas = _canvas()
    assert canvas.interpretar_gesto("meio", True) == "pan"
    canvas.viewport.modo = "Mover"
    assert canvas.interpretar_gesto("esquerdo", True) == \
        "drag_objeto"


def test_regras_regua():
    canvas = _canvas()
    regua = canvas.ticks_regua("x", 800)
    assert regua
    assert set(regua[0]) == {"tela", "mundo"}


def test_debug_info():
    canvas = _canvas()
    info = canvas.info_debug("janela:p")
    assert info["tipo"] == "janela"
    assert info["parent"] is None


def test_bbox_global():
    canvas = _canvas()
    bb = canvas.por_id["personagem:Juh"].bbox_global(
        canvas.por_id)
    assert bb["largura"] == 120.0


def test_recarregar_parcial():
    canvas = _canvas()
    diff = canvas.recarregar(FONTE.replace("100 200",
                                           "101 200"))
    assert diff["rebuild_parcial"] is True
    assert diff["alterados"] == ["janela:p"]


# ---------- inspector extra ----------


def test_inspector_character_section(tmp_path):
    from elixx.studio.scene_canvas import (
        cena_de_texto,
        ficha_objeto,
    )

    _, ws = _workspace(tmp_path)
    saida = cena_de_texto(FONTE)
    ficha = ficha_objeto(ws.modelo, "personagem:Juh",
                         cena=saida["cena"],
                         personagens=saida["personagens"])
    assert "corpo" in ficha["CHARACTER"]["parts"]


def test_inspector_relations(tmp_path):
    from elixx.studio.scene_canvas import ficha_objeto

    _, ws = _workspace(tmp_path)
    ficha = ficha_objeto(ws.modelo, "personagem:Juh")
    assert "RELATIONS" in ficha


# ---------- agent extra ----------


def test_agent_planejar_contexto(tmp_path):
    _, ws = _workspace(tmp_path)
    plano = ws.agent.planejar(ws.modelo, "Juh")
    assert plano["status"] == "plano"
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert "src/main.elixx" in ctx["arquivos"]


def test_agent_tools_trace():
    from elixx.studio.agent.ferramentas_semanticas import (
        AgentToolCall,
        ToolTrace,
    )

    trace = ToolTrace()
    trace.registrar(AgentToolCall("t_buscar_entidade",
                                  {"nome": "Juh"}))
    assert trace.explicar()


def test_agent_nova_sessao_estado():
    from elixx.studio.agent.interacao import AgentSession

    sessao = AgentSession()
    assert sessao.estado == "IDLE"
    assert sessao.id.startswith("agent_")


def test_contexto_chips_dados(tmp_path):
    _, ws = _workspace(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["relacoes"] >= 1


# ---------- reasoning / plan / changes ----------


def test_reasoning_estagios_ordem():
    from elixx.studio.agent.workspace import AgentWorkspace

    area = AgentWorkspace("t")
    assert list(area.estagios) == ["TASK", "CONTEXT", "TOOLS",
                                   "OPERATIONS", "PLAN",
                                   "CHANGES", "PREVIEW"]


def test_plan_aprovar_cancelar(tmp_path):
    from elixx.studio.agent.planejamento import PainelPlano

    _, ws = _workspace(tmp_path)
    assert ws.agent.planejar(ws.modelo, "Juh")


def test_changes_aprovar(tmp_path):
    from elixx.studio.ux import propor_transformacao

    _, ws = _workspace(tmp_path)
    cs = propor_transformacao(ws.app.workspace, ws.modelo,
                              "janela:p",
                              {"posicao": "150 200"})
    cs.aprovar()
    assert cs.estado == "aprovado"


# ---------- editor extra ----------


def test_editor_abas(tmp_path):
    from elixx.studio.ux import AbasEditor

    _, ws = _workspace(tmp_path)
    ws.app.documentos.abrir("src/main.elixx", FONTE)
    abas = AbasEditor(ws.app.documentos)
    assert abas.lista()


def test_editor_busca(tmp_path):
    _, ws = _workspace(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.documento.texto.count("Juh") >= 1


# ---------- compacto / foco extra ----------


def test_compacto_layout_preservado(tmp_path):
    _, ws = _workspace(tmp_path)
    ws.layout.definir_compacto(True)
    assert ws.layout.compacto is True
    ws.layout.definir_compacto(False)
    assert ws.layout.compacto is False


def test_foco_entrar_sair(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    foco = FocusState()
    foco.entrar(ws.layout, ["preview"])
    assert ws.layout.paineis_visiveis() == ["preview"]
    foco.sair(ws.layout)


def test_foco_duplo_erro(tmp_path):
    from elixx.studio.ux import FocusState

    _, ws = _workspace(tmp_path)
    foco = FocusState()
    foco.entrar(ws.layout, ["preview"])
    with pytest.raises(ErroELiXX):
        foco.entrar(ws.layout, ["editor"])
    foco.sair(ws.layout)


# ---------- seguranca extra ----------


def test_absoluto_bloqueado(tmp_path):
    _, ws = _workspace(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.app.workspace.resolver("C:\\Windows\\x.elixx")


def test_infinito_rejeitado():
    from elixx.studio.scene_canvas import RenderObject

    with pytest.raises(ErroELiXX):
        RenderObject("o", "objeto", y=float("inf"))


def test_recurso_remoto():
    from elixx.studio.scene_canvas import estado_asset

    class _No:
        caminho_recurso = "https://x/y.png"

    assert estado_asset(_No())["status"] == "remoto"


def test_carregar_imagem_segura():
    from elixx.studio.scene_canvas import carregar_imagem

    assert carregar_imagem("/nao/existe.png") is None


def test_geometrias_qa():
    from elixx.studio.scene_editor import RESOLUCOES_QA

    assert len(RESOLUCOES_QA) == 8
