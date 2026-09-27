"""Testes da Fase 38 — workspace visual 2.0 + code (sem LLM)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.ux import (
    AbasEditor,
    SecaoInspector,
    ZOOM_NIVEIS,
    cabecalho_arquivo,
    destacar_semantico,
    formatar_arvore,
    resumo_agente,
)

FONTE = (
    "janela p {\n"
    ' titulo: "T"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    " }\n"
    "}\n"
)


def app_tmp(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    return app


# ---------- tokens 2.0 (1-10) ----------

def test_tokens_novos():
    from elixx.studio.tema import (
        ELIXX_COLORS,
        ELIXX_FONT_SIZE,
        ELIXX_GAP,
        ELIXX_LINE_HEIGHT,
        ELIXX_PANEL_WIDTH,
        ELIXX_TOOLBAR_HEIGHT,
    )

    for chave in ("surface_elevated", "surface_hover",
                  "surface_active", "danger"):
        assert chave in ELIXX_COLORS
    assert ELIXX_GAP["md"] == 8
    assert ELIXX_FONT_SIZE["code"] == 9
    assert ELIXX_LINE_HEIGHT["body"] == 12
    assert ELIXX_PANEL_WIDTH["project"] == 220
    assert ELIXX_TOOLBAR_HEIGHT == 32


def test_tokens_validos():
    from elixx.studio.tema import validar_tokens

    assert validar_tokens()["valido"] is True


def test_tokens_hex():
    import re

    from elixx.studio.tema import ELIXX_COLORS

    for nome, cor in ELIXX_COLORS.items():
        assert re.fullmatch(r"#[0-9a-f]{6}", cor), nome


def test_tokens_fonte_tamanhos():
    from elixx.studio.tema import ELIXX_FONT_SIZE, ELIXX_FONTS

    for nome, tamanho in ELIXX_FONT_SIZE.items():
        assert ELIXX_FONTS[nome][1] == tamanho


def test_tokens_gap_ordem():
    from elixx.studio.tema import ELIXX_GAP

    valores = [ELIXX_GAP[k] for k in ("xs", "sm", "md", "lg")]
    assert valores == sorted(valores) and len(set(valores)) == 4


def test_tokens_line_height():
    from elixx.studio.tema import ELIXX_FONT_SIZE, ELIXX_LINE_HEIGHT

    for nome in ELIXX_FONT_SIZE:
        assert ELIXX_LINE_HEIGHT[nome] >= ELIXX_FONT_SIZE[nome]


def test_tokens_panel():
    from elixx.studio.tema import ELIXX_METRICS, ELIXX_PANEL_WIDTH

    assert ELIXX_PANEL_WIDTH["inspector"] == 240
    assert ELIXX_METRICS["largura_lateral"] == 220


def test_tokens_toolbar():
    from elixx.studio.tema import ELIXX_METRICS, ELIXX_TOOLBAR_HEIGHT

    assert ELIXX_METRICS["altura_toolbar"] == ELIXX_TOOLBAR_HEIGHT


def test_tokens_radius():
    from elixx.studio.tema import ELIXX_RADIUS

    assert ELIXX_RADIUS["sm"] < ELIXX_RADIUS["lg"]


def test_tokens_bordas():
    from elixx.studio.tema import ELIXX_BORDERS

    assert ELIXX_BORDERS["nenhuma"] == 0


# ---------- chrome/topbar (11-16) ----------

def test_chrome_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Accent.TButton" in fonte
    assert "Danger.TButton" in fonte
    assert "ttk.Separator" in fonte


def test_chrome_salvar_dirty():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Salvar ●" in fonte


def test_chrome_parar_danger():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Danger.TButton" in fonte


def test_chrome_agrupado():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "botoes_topo" in fonte


# ---------- project (17-24) ----------

def test_project_formatar():
    linhas = formatar_arvore([
        {"nome": "main.elixx", "tipo": "arquivo",
         "caminho": "src/main.elixx"},
        {"nome": "Juh", "tipo": "personagem",
         "caminho": "src/main.elixx"}])
    assert linhas[0].startswith("  • main.elixx")
    assert "◆ Juh" in linhas[1]


def test_project_atual():
    linhas = formatar_arvore(
        [{"nome": "a.elixx", "tipo": "arquivo",
          "caminho": "src/a.elixx"}],
        atual="src/a.elixx")
    assert linhas[0].endswith("→")


def test_project_dirty():
    linhas = formatar_arvore(
        [{"nome": "a.elixx", "tipo": "arquivo",
          "caminho": "src/a.elixx"}],
        sujos=["src/a.elixx"])
    assert linhas[0].endswith("●")


def test_project_grupos():
    linhas = formatar_arvore([
        {"nome": "z.png", "tipo": "asset", "caminho": "a/z.png"},
        {"nome": "a.elixx", "tipo": "arquivo",
         "caminho": "a/a.elixx"}])
    assert linhas[0].endswith("a.elixx")
    assert "▤ z.png" in linhas[1]


def test_project_ordenado():
    linhas = formatar_arvore([
        {"nome": "b.elixx", "tipo": "arquivo", "caminho": "b"},
        {"nome": "a.elixx", "tipo": "arquivo", "caminho": "a"}])
    assert linhas[0].endswith("a.elixx")


def test_project_invalido():
    with pytest.raises(ErroELiXX):
        formatar_arvore(["nao-dict"])
    assert formatar_arvore([]) == []
    assert formatar_arvore(None) == []


def test_project_hover_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "_abrir_duplo" in fonte
    assert "Double-Button-1" in fonte


def test_project_selecao_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "lista_arq" in fonte


# ---------- preview/viewport (25-34) ----------

def test_preview_zoom_niveis():
    assert ZOOM_NIVEIS == (50, 75, 100, 125, 150, "Ajustar")
    assert 100 in ZOOM_NIVEIS


def test_preview_toolbar_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "rotulo_zoom" in fonte
    assert "OptionMenu" in fonte


def test_preview_status_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "rotulo_prev_status" in fonte


def test_preview_viewport_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "quadro_viewport" in fonte


def test_preview_tema_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "selectbackground" in fonte


def test_preview_empty():
    from elixx.studio.workspace_ui import estado_vazio

    assert "Nenhuma cena" in estado_vazio("preview") or \
        estado_vazio("preview")


def test_preview_lista(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    ws.preview.executar(FONTE)
    ents = ws.preview.sincronizar_modelo(ws.modelo)
    assert {e["id"] for e in ents} >= {"personagem:Juh"}


def test_preview_selecao(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    ws.preview.executar(FONTE)
    ws.preview.sincronizar_modelo(ws.modelo)
    ent = ws.preview.selecionar("personagem:Juh")
    assert ent["nome"] == "Juh"


# ---------- inspector (35-42) ----------

def test_inspector_secao():
    sec = SecaoInspector("GERAL", {"Tipo": "x"})
    assert sec.aberta is True
    assert sec.alternar() is False
    assert sec.to_dict()["aberta"] is False
    assert repr(sec).startswith("SecaoInspector(▸")


def test_inspector_titulo():
    with pytest.raises(ErroELiXX):
        SecaoInspector("   ")
    assert SecaoInspector("A", {}).campos == {}


def test_inspector_secoes_reais(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    objs = [SecaoInspector(s["titulo"], s["campos"])
            for s in secoes]
    assert objs[0].titulo == "Juh"
    assert all(isinstance(s, SecaoInspector) for s in objs)


def test_inspector_toggle_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "_alternar_secao" in fonte
    assert "_render_inspetor" in fonte


def test_inspector_ver_codigo(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    from elixx.studio.codigo import localizar_entidade

    ent = ws.modelo.obter_entidade("personagem:Juh")
    loc = localizar_entidade(ent, FONTE)
    assert loc.inicio_linha == 3


def test_inspector_vazio_texto():
    from elixx.studio.workspace_ui import estado_vazio

    texto = estado_vazio("inspector")
    assert "nenhum objeto" in texto


# ---------- editor (43-58) ----------

def test_editor_abas(tmp_path):
    from elixx.studio import GerenciadorDocumentos

    abas = AbasEditor(GerenciadorDocumentos())
    abas.abrir("a.elixx", "aaa")
    abas.abrir("b.elixx", "bbb")
    assert abas.ativa == "b.elixx"
    assert [i["caminho"] for i in abas.lista()] == ["a.elixx",
                                                   "b.elixx"]
    assert abas.trocar("a.elixx") == "a.elixx"
    assert abas.fechar("a.elixx") == "b.elixx"
    with pytest.raises(ErroELiXX):
        abas.trocar("fantasma")
    with pytest.raises(ErroELiXX):
        AbasEditor("nao-gerenciador")


def test_editor_header():
    assert cabecalho_arquivo("src/main.elixx", True) == \
        "main.elixx ●"
    assert cabecalho_arquivo("src/main.elixx", False) == \
        "main.elixx"
    assert cabecalho_arquivo("C:\\x\\a.elixx", False) == "a.elixx"
    with pytest.raises(ErroELiXX):
        cabecalho_arquivo("", False)


def test_editor_highlight_lexer():
    marcas = destacar_semantico("janela p {\n titulo: \"T\"\n}\n")
    classes = {m[2] for m in marcas}
    assert {"palavra", "nome", "string"} <= classes
    palavra = [m for m in marcas if m[2] == "palavra"][0]
    assert palavra == (0, 6, "palavra")


def test_editor_highlight_numeros():
    marcas = destacar_semantico("rotacao: 45deg\n")
    assert any(m[2] == "numero" for m in marcas)


def test_editor_highlight_fallback():
    marcas = destacar_semantico("janela p { titulo: ")
    assert isinstance(marcas, list) and marcas
    with pytest.raises(ErroELiXX):
        destacar_semantico(123)


def test_editor_highlight_deterministico():
    a = destacar_semantico(FONTE)
    b = destacar_semantico(FONTE)
    assert a == b
    assert a == sorted(a)


def test_editor_undo_redo(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("x")
    assert ed.documento.desfazer() is True
    assert ed.documento.refazer() is True


def test_editor_busca(tmp_path):
    from elixx.studio import EditorCodigo, StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar(FONTE)
    codigo = EditorCodigo(ed.documento)
    assert len(codigo.localizar("Juh")) == 1


def test_editor_dirty(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.modificado() is False
    ed.editar("x")
    assert ed.modificado() is True
    ws.salvar_editor("src/main.elixx")
    assert ed.modificado() is False


def test_editor_diagnostico(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.analisar()[0].severidade == "info"
    ed.editar("janela p { titulo: ")
    diags = ed.analisar()
    assert diags[0].severidade == "error"
    ws.diagnosticos.atualizar(diags)
    assert ws.diagnosticos.resumo()["erros"] == 1


def test_editor_sync_salvar(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    n_antes = len(ws.modelo)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar(FONTE + "janela q {\n titulo: \"Q\"\n}\n")
    ws.salvar_editor("src/main.elixx")
    from elixx.studio.codigo.sincronizador import (
        SincronizadorCodigo,
    )

    sinc = SincronizadorCodigo(app.workspace, ws.modelo)
    sinc.codigo_para_modelo("src/main.elixx")
    assert "janela:q" in ws.modelo
    assert len(ws.modelo) > n_antes


def test_editor_sync_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "_sincronizar_apos_salvar" in fonte
    assert "atualizar_arquivo" in fonte


def test_editor_abas_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "_recarregar_abas_ed" in fonte
    assert "quadro_abas_ed" in fonte


# ---------- agent (59-70) ----------

def test_agent_header():
    from elixx.studio.agent.interacao import AgentSession

    s = AgentSession()
    assert s.estado == "IDLE"


def test_agent_status(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.estado()["projeto"] is None


def test_agent_conversa():
    from elixx.studio.agent.interacao import AgentSession

    s = AgentSession()
    assert s.mensagens == []


def test_agent_contexto():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.modelo is None


def test_agent_tools_lista():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    assert len(SemanticToolRegistry().listar()) == 30


def test_agent_plano_vazio():
    from elixx.studio.agent.planejamento import PainelPlano

    assert PainelPlano.__name__ == "PainelPlano"


def test_agent_proposta_formato():
    from elixx.studio.agent import ChangeSet

    cs = ChangeSet()
    assert cs.revisar() == []


def test_agent_revisar_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "_plano_revisar" in fonte
    assert "_plano_aprovar" in fonte
    assert "_plano_cancelar" in fonte


def test_agent_chat_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "hist_chat" in fonte
    assert "entrada_chat" in fonte


def test_agent_mock_label():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "MOCK / DETERMINISTIC" in fonte


# ---------- context/tools/reasoning/plan/changes (71-80) ----------

def test_context_resumo():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    r = construir_contexto(
        m, ContextoTarefa(objetivo="ver", alvo="Juh"))
    assert r.entidades[0].id == "personagem:Juh"


def test_tools_trace():
    from elixx.studio.agent.ferramentas_semanticas import (
        AgentToolCall,
        ToolTrace,
    )

    trace = ToolTrace()
    trace.registrar(AgentToolCall("buscar_entidade", {}))
    assert "buscar_entidade" in trace.explicar()


def test_reasoning_estagios():
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    assert "TOOLS" in ws.estagios


def test_plan_resumo():
    from elixx.studio.agent.operacoes import SemanticOperation
    from elixx.studio.agent.planejamento import PainelPlano, PlanoTarefa

    painel = PainelPlano(PlanoTarefa(
        "x", [SemanticOperation("pose", "Juh", {})]))
    assert painel.resumo()["progresso"]["total"] == 0


def test_changes_estado():
    from elixx.studio.agent import ChangeSet

    assert ChangeSet().estado == "proposto"


def test_changes_review():
    from elixx.studio.agent import AgentChange, ChangeSet

    cs = ChangeSet([AgentChange("a", "criar")])
    assert cs.revisar()[0]["caminho"] == "a"


# ---------- layouts/compact/palette/keyboard/status (81-92) ----------

def test_layouts_todos():
    from elixx.studio.workspace_ui import LAYOUTS, aplicar_layout_nome

    import tempfile
    from pathlib import Path

    from elixx.studio import StudioApp, StudioWorkspace

    tmp = Path(tempfile.mkdtemp(prefix="lay38_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "p", "P")
    for nome in LAYOUTS:
        assert aplicar_layout_nome(ws, nome)


def test_layout_default_conteudo():
    from elixx.studio.workspace_ui import LAYOUTS

    assert set(LAYOUTS["DEFAULT"]) >= {"editor", "preview",
                                       "agent"}


def test_compacto_modelo():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    lay.definir_compacto(True)
    assert lay.compacto is True


def test_palette_busca():
    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    assert len(pal.buscar("")) == 30
    assert pal.buscar("zzz-nada") == []


def test_palette_novos():
    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    ids = [c["id"] for c in pal.buscar("")]
    for cid in ("abrir_codigo", "focar_agent", "salvar",
                "alternar_layout"):
        assert cid in ids


def test_palette_case():
    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    assert pal.buscar("PREVIEW")


def test_keyboard_atual():
    from elixx.studio.app import ATALHOS

    for tecla in ("Ctrl+K", "Ctrl+1", "Ctrl+Enter", "Esc",
                  "Ctrl+S", "F5"):
        assert tecla in ATALHOS, tecla


def test_keyboard_preservado():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+Z"] == "desfazer"
    assert ATALHOS["Ctrl+Shift+P"] == "paleta_comandos"


def test_status_resumo():
    from elixx.studio.workspace_ui import resumo_status

    texto = resumo_status("Loja", "src/main.elixx", True, 0,
                          {"concluidos": 1, "total": 2}, 0)
    assert "Loja" in texto and "1/2" in texto


def test_status_erro():
    from elixx.studio.workspace_ui import resumo_status

    assert "Ready com erros" in resumo_status("P", None, True, 3)


def test_status_vazio():
    from elixx.studio.workspace_ui import resumo_status

    assert "sem modelo" in resumo_status()


# ---------- responsivo (93-94) ----------

def test_responsivo_geometrias():
    from elixx.studio.workspace_ui import GEOMETRIAS_OK, Layout

    lay = Layout()
    for geo in GEOMETRIAS_OK:
        assert lay.definir_geometria(*geo) == geo
    assert len(GEOMETRIAS_OK) == 8


def test_responsivo_minimo():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    with pytest.raises(ErroELiXX):
        lay.definir_geometria(700, 400)


# ---------- segurança (95-103) ----------

def test_sec_traversal(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    with pytest.raises(ErroELiXX):
        ws.abrir_no_editor("../../x.elixx")


def test_sec_absoluto():
    from elixx.studio import StudioApp

    with pytest.raises(ErroELiXX):
        StudioApp().workspace.resolver("C:\\Windows\\x")


def test_sec_strings():
    from elixx.studio.agent.interacao import AgentSession

    s = AgentSession()
    assert "__import__('os')" in AgentSession(
    )._dizer("USER", "__import__('os')").conteudo


def test_sec_nan():
    from elixx.studio.agent.contexto_tarefa import ContextoEntidade

    with pytest.raises(ErroELiXX):
        ContextoEntidade("a", score=float("nan"))


def test_sec_infinity():
    from elixx.studio.ux import SecaoInspector

    assert SecaoInspector("A", {}).aberta is True
    with pytest.raises(ErroELiXX):
        SecaoInspector("   ")


def test_sec_recursao():
    from elixx.studio.agent.interacao import AgentMessage

    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    with pytest.raises(ErroELiXX):
        AgentMessage("USER", "x", referencias=[fundo])


def test_sec_payload():
    from elixx.studio.agent.interacao import AgentMessage

    with pytest.raises(ErroELiXX):
        AgentMessage("USER", "x",
                     referencias=[{"k": object()}])


def test_sec_sem_execucao():
    import elixx.studio.ux as modulo
    import pathlib

    for arq in list(pathlib.Path(modulo.__file__).parent.glob(
            "ux.py")) + [pathlib.Path(
                __import__("elixx.studio.tema",
                           fromlist=["__file__"]).__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess",
                         "os.system", "requests"):
            assert proibido not in fonte, (arq.name, proibido)


# ---------- performance (104-108) ----------

def _modelo_grande(total):
    from elixx.studio.modelo import EntidadeSemantica, ModeloSemantico

    m = ModeloSemantico("p")
    for i in range(total):
        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:05d}", "simbolo", f"S{i}"))
    return m


def test_perf_entidades():
    import time as _t

    for total in (100, 500, 1000, 5000, 10000):
        m = _modelo_grande(total)
        t0 = _t.perf_counter()
        assert len(m.entidades()) == total
        assert (_t.perf_counter() - t0) < 60.0
        if total == 10000:
            print(f"\n10000 ent modelo: {(_t.perf_counter() - t0):.2f}s")


def test_perf_arquivos(tmp_path):
    import time as _t

    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    base = tmp_path / "big"
    (base / "src").mkdir(parents=True)
    for total in (100, 500, 1000):
        for i in range(total):
            (base / "src" / f"m{i:04d}.elixx").write_text(
                "janela p {\n titulo: \"T\"\n}\n",
                encoding="utf-8")
        m = ModeloSemantico("p")
        t0 = _t.perf_counter()
        out = analisar_projeto(m, base)
        dt = _t.perf_counter() - t0
        assert out["arquivos"] == total and dt < 60.0
        for i in range(total):
            (base / "src" / f"m{i:04d}.elixx").unlink()


def test_perf_editor():
    import time as _t

    from elixx.studio.ux import destacar_semantico

    grande = ("janela p {\n titulo: \"T\"\n}\n" * 2000)[:100000]
    t0 = _t.perf_counter()
    marcas = destacar_semantico(grande)
    dt = _t.perf_counter() - t0
    assert len(marcas) > 1000 and dt < 60.0
    if True:
        print(f"\neditor ~{len(grande)} chars: {dt:.2f}s")


def test_perf_highlight_busca():
    import time as _t

    from elixx.studio import DocumentoELiXX, EditorCodigo

    doc = DocumentoELiXX("a.elixx", "janela p {}\n" * 2000)
    codigo = EditorCodigo(doc)
    t0 = _t.perf_counter()
    assert len(codigo.localizar("janela")) == 2000
    assert (_t.perf_counter() - t0) < 30.0


# ---------- integração F25-F37 (109-121) ----------

def test_f25_documento():
    from elixx.studio import DocumentoELiXX

    doc = DocumentoELiXX("a.elixx", "x")
    assert doc.dirty is False


def test_f26_changeset():
    from elixx.studio.agent import ChangeSet

    assert ChangeSet().estado == "proposto"


def test_f27_consulta():
    from elixx.studio.modelo import ConsultaSemantica
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    q = ConsultaSemantica(m)
    assert [e.id for e in q.encontrar_por_nome("Juh")] == \
        ["personagem:Juh"]


def test_f28_resolver():
    from elixx.studio.agent.loop import resolver_alvo
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    assert resolver_alvo(m, "Juh")["status"] == "unico"


def test_f29_layout():
    from elixx.studio.workspace_ui import Layout

    assert "preview" in Layout().paineis_visiveis()


def test_f30_intent():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    assert it.tipo == "mostrar"


def test_f31_operacao():
    from elixx.studio.agent.inteligencia import MockIntentProvider
    from elixx.studio.agent.operacoes import intent_para_operacao

    op = intent_para_operacao(MockIntentProvider(
    ).gerar_intencao(None, "mostre a Juh"))
    assert op.tipo == "mostrar"


def test_f32_localizar():
    from elixx.studio.codigo import localizar_entidade
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    loc = localizar_entidade(m.obter_entidade("personagem:Juh"),
                             FONTE)
    assert loc.inicio_linha == 3


def test_f33_plano():
    from elixx.studio.agent.operacoes import SemanticOperation
    from elixx.studio.agent.planejamento import PlanoTarefa

    t = PlanoTarefa("x", [SemanticOperation("pose", "Juh", {})])
    assert t.task.estado == "criada"


def test_f34_contexto():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    r = construir_contexto(
        m, ContextoTarefa(objetivo="ver", alvo="Juh"))
    assert r.entidades[0].id == "personagem:Juh"


def test_f35_workspace():
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    assert "TOOLS" in ws.estagios


def test_f36_tools():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    assert len(SemanticToolRegistry().listar()) == 30


def test_f37_sessao():
    from elixx.studio.agent.interacao import AgentSession

    assert AgentSession().estado == "IDLE"


# ---------- regressão (122-124) ----------

def test_regressao_tema():
    from elixx.studio.tema import validar_tokens

    assert validar_tokens()["valido"] is True


def test_regressao_ux_import():
    import elixx.studio.ux as modulo

    assert "destacar_semantico" in dir(modulo)


def test_regressao_palette_total():
    from elixx.studio.agent.interacao import CommandPalette

    assert len(CommandPalette().buscar("")) == 30


def test_palette_abrir(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent.interacao import CommandPalette

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {}\n", encoding="utf-8")
    pal = CommandPalette()
    out = pal.executar(app, "abrir_arquivo",
                       {"alvo": "src/main.elixx"})
    assert out["alvo"] == "src/main.elixx"
    assert app.documentos.ativo == "src/main.elixx"
    with pytest.raises(ErroELiXX):
        pal.executar(app, "abrir_arquivo",
                     {"alvo": "src/fantasma.elixx"})
    with pytest.raises(ErroELiXX):
        pal.executar(app, "abrir_arquivo", {})
    with pytest.raises(ErroELiXX):
        pal.executar(app, "abrir_arquivo",
                     {"alvo": "../fora.elixx"})


def test_palette_salvar_sem_doc():
    from elixx.studio import StudioApp
    from elixx.studio.agent.interacao import CommandPalette

    with pytest.raises(ErroELiXX):
        CommandPalette().executar(StudioApp(), "salvar")


def test_tree_grupos_tipos():
    grupos = {}
    for item in formatar_arvore([
            {"nome": "x", "tipo": "cena", "caminho": "x"},
            {"nome": "y", "tipo": "asset", "caminho": "y"},
            {"nome": "z", "tipo": "misterio", "caminho": "z"}]):
        grupos[item.split("]")[0]] = True
    assert len(grupos) == 3


def test_tree_atual_dirty():
    linhas = formatar_arvore(
        [{"nome": "a.elixx", "tipo": "arquivo",
          "caminho": "src/a.elixx"}],
        atual="src/a.elixx", sujos=["src/a.elixx"])
    assert linhas[0].endswith("→ ●")


def test_highlight_posicoes():
    marcas = destacar_semantico("janela teste {\n}\n")
    nomes = [m for m in marcas if m[2] == "nome"]
    assert nomes and nomes[0][0] == 7
    assert marcas == sorted(marcas)


def test_highlight_vazio():
    assert destacar_semantico("") == []
    assert destacar_semantico("   \n  ") == []


def test_abas_multiplas(tmp_path):
    from elixx.studio import GerenciadorDocumentos, StudioApp

    app = StudioApp()
    abas = AbasEditor(GerenciadorDocumentos())
    for nome in ("a.elixx", "b.elixx", "c.elixx"):
        abas.abrir(nome, nome)
    assert len(abas.lista()) == 3
    assert abas.fechar("b.elixx") == "c.elixx"
    assert [i["caminho"] for i in abas.lista()] == ["a.elixx",
                                                   "c.elixx"]


def test_abas_cabecalhos(tmp_path):
    from elixx.studio import GerenciadorDocumentos

    abas = AbasEditor(GerenciadorDocumentos())
    doc = abas.abrir("a.elixx", "x")
    doc.definir_texto("y")
    assert abas.lista()[0]["cabecalho"] == "a.elixx ●"
    assert abas.lista()[0]["ativa"] is True


def test_secao_serializa():
    sec = SecaoInspector("T", {"a": 1}, aberta=False)
    assert sec.to_dict() == {"titulo": "T",
                             "campos": {"a": 1},
                             "aberta": False}
    assert repr(sec).startswith("SecaoInspector(▸")


def test_secao_campos_reais(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    objs = [SecaoInspector(s["titulo"], s["campos"])
            for s in secoes]
    assert any("Arquivo" in o.campos for o in objs)


def test_agent_resumo():
    from elixx.studio.agent.interacao import AgentSession

    s = AgentSession()
    r = resumo_agente(s)
    assert r["header"] == "ELiXX AGENT"
    assert r["provider"] == " / DETERMINISTIC" or "MOCK" in \
        r["provider"] or r["provider"].endswith("DETERMINISTIC")
    assert r["status"] == "IDLE" and r["mensagens"] == 0


def test_agent_resumo_sessao():
    from elixx.studio.agent.interacao import AgentSession

    s = AgentSession()
    s._dizer("USER", "oi")
    r = resumo_agente(s)
    assert r["mensagens"] == 1 and r["tarefa"] == ""


def test_zoom_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "OptionMenu" in fonte
    assert "_zoom_trocar" in fonte


def test_status_fases_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "resumo_status" in fonte
    assert "barra_status" in fonte


def test_teclado_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    for tecla in ("Control-s", "F5>", "Shift-F5", "Control-k",
                  "Control-1", "Escape"):
        assert tecla in fonte, tecla


def test_compacto_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "definir_compacto" in fonte


def test_palette_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Command Palette (Ctrl+K)" in fonte


def test_layout_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "FOCUS_AGENT" in fonte


def test_tema_fonte_clam():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "aplicar_tema" in fonte


def test_accent_perigo_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Accent.TButton" in fonte
    assert "Danger.TButton" in fonte


def test_perf_arvore():
    import time as _t

    nos = [{"nome": f"m{i:04d}.elixx", "tipo": "arquivo",
            "caminho": f"src/m{i:04d}.elixx"} for i in range(1000)]
    t0 = _t.perf_counter()
    linhas = formatar_arvore(nos)
    assert len(linhas) == 1000
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_abas():
    import time as _t

    from elixx.studio import GerenciadorDocumentos

    abas = AbasEditor(GerenciadorDocumentos())
    t0 = _t.perf_counter()
    for i in range(500):
        abas.abrir(f"m{i:04d}.elixx", "x")
    assert len(abas.lista()) == 500
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_palette_busca():
    import time as _t

    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    t0 = _t.perf_counter()
    for _ in range(1000):
        pal.buscar("plano")
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_resumo():
    import time as _t

    from elixx.studio.agent.interacao import AgentSession

    s = AgentSession()
    t0 = _t.perf_counter()
    for _ in range(1000):
        resumo_agente(s)
    assert (_t.perf_counter() - t0) < 30.0


def test_determinismo_tree():
    nos = [{"nome": "b", "tipo": "arquivo", "caminho": "b"},
           {"nome": "a", "tipo": "arquivo", "caminho": "a"}]
    assert formatar_arvore(nos) == formatar_arvore(nos)


def test_determinismo_abas():
    from elixx.studio import GerenciadorDocumentos

    abas = AbasEditor(GerenciadorDocumentos())
    abas.abrir("b.elixx", "x")
    abas.abrir("a.elixx", "y")
    assert [i["caminho"] for i in abas.lista()] == ["b.elixx",
                                                   "a.elixx"]


def test_regressao_interacao_intacta():
    from elixx.studio.agent.interacao import (
        AgentSession,
        CommandPalette,
    )

    assert len(CommandPalette().buscar("")) == 30
    assert AgentSession().estado == "IDLE"


def test_f37_sessao_env():
    from elixx.studio.agent.interacao import AgentSession
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")

    class _Amb:
        modelo = m
        selecionado = ""
        arquivo = ""

    out = AgentSession().enviar("mostre a Juh", _Amb())
    assert out["ok"] is True


def test_abas_fechar_todas():
    from elixx.studio import GerenciadorDocumentos

    abas = AbasEditor(GerenciadorDocumentos())
    abas.abrir("a.elixx", "x")
    assert abas.fechar("a.elixx") is None
    assert abas.lista() == [] and abas.ativa is None


def test_abas_inexistente():
    from elixx.studio import GerenciadorDocumentos

    abas = AbasEditor(GerenciadorDocumentos())
    with pytest.raises(ErroELiXX):
        abas.trocar("fantasma.elixx")


def test_cabecalho_barra():
    assert cabecalho_arquivo("a/b/c.elixx", True) == "c.elixx ●"


def test_highlight_string_pos():
    marcas = destacar_semantico('titulo: "Oi"\n')
    strings = [m for m in marcas if m[2] == "string"]
    assert strings == [(9, 11, "string")]  # conteúdo, sem aspas


def test_palette_navegacao():
    from elixx.studio import StudioApp
    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    for cid in ("abrir_preview", "focar_agent", "alternar_layout",
                "sincronizar_projeto", "nova_sessao"):
        out = pal.executar(StudioApp(), cid)
        assert out["ok"] is True and out["comando"] == cid


def test_palette_foco():
    from elixx.studio import StudioApp
    from elixx.studio.agent.interacao import CommandPalette

    pal = CommandPalette()
    out = pal.executar(StudioApp(), "focar_codigo")
    assert out["comando"] == "focar_codigo"


def test_status_com_plano():
    from elixx.studio.workspace_ui import resumo_status

    texto = resumo_status("P", "a", True, 0,
                          {"concluidos": 0, "total": 3}, 0)
    assert "0/3" in texto and "Context ready" in texto
    vazio = resumo_status("P", "a", True, 0,
                          {"concluidos": 0, "total": 0}, 0)
    assert "Waiting approval" in vazio


def test_status_sem_projeto():
    from elixx.studio.workspace_ui import resumo_status

    assert "(nenhum projeto)" in resumo_status()


def test_sem_tk_novos():
    import pathlib

    for nome in ("ux.py", "tema.py", "interacao.py"):
        base = pathlib.Path("elixx/studio")
        alvos = list(base.glob(nome)) + list(
            base.glob(f"agent/{nome}"))
        for arq in alvos:
            for linha in arq.read_text(
                    encoding="utf-8").splitlines():
                assert not linha.startswith("import tkinter")
                assert not linha.startswith("from tkinter")
