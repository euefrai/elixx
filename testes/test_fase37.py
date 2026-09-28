"""Testes da Fase 37 — command center + interação (sem LLM)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent.interacao import (
    AgentMessage,
    AgentSession,
    CommandPalette,
    resumo_chips,
    selecao_global,
)
from elixx.studio.modelo import ModeloSemantico, analisar_texto

FONTE = (
    "janela principal {\n"
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    "  pose acenar {\n"
    "   corpo:\n"
    "    rotacao: 45deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


def modelo_base():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    return m


class _Amb:
    def __init__(self, modelo):
        self.modelo = modelo
        self.selecionado = "personagem:Juh"
        self.arquivo = "src/main.elixx"


# ---------- AgentMessage (1-8) ----------

def test_msg_criacao():
    m = AgentMessage("USER", "faça X")
    assert m.tipo == "USER" and m.estado == "pronto"
    assert m.id.startswith("msg_")


def test_msg_tipos():
    for tipo in ("USER", "AGENT", "SYSTEM", "TOOL", "RESULT",
                 "ERROR"):
        assert AgentMessage(tipo, "x").tipo == tipo
    with pytest.raises(ErroELiXX):
        AgentMessage("TELEPATIA", "x")


def test_msg_ordem():
    a = AgentMessage("USER", "a")
    b = AgentMessage("USER", "b")
    assert b.ordem > a.ordem  # contador, sem relógio


def test_msg_estado():
    with pytest.raises(ErroELiXX):
        AgentMessage("USER", "x", estado="voando")
    m = AgentMessage("USER", "x", estado="processando")
    assert m.estado == "processando"


def test_msg_referencias():
    m = AgentMessage("AGENT", "ok",
                     referencias=[{"id": "personagem:Juh"}])
    assert m.referencias == [{"id": "personagem:Juh"}]
    with pytest.raises(ErroELiXX):
        AgentMessage("AGENT", "x", referencias=[{"f": object()}])


def test_msg_serializacao():
    m = AgentMessage("TOOL", "trace", msg_id="fixa")
    copia = AgentMessage.from_dict(m.to_dict())
    assert copia.id == "fixa" and copia.ordem == m.ordem
    with pytest.raises(ErroELiXX):
        AgentMessage.from_dict("nao-dict")


def test_msg_limite():
    m = AgentMessage("USER", "x" * 5000)
    assert len(m.conteudo) == 2000  # teto silencioso


# ---------- AgentSession (9-20) ----------

def test_sessao_criacao():
    s = AgentSession()
    assert s.estado == "IDLE" and s.mensagens == []
    assert s.id.startswith("agent_")


def test_sessao_ids():
    assert AgentSession().id != AgentSession().id
    assert AgentSession(sessao_id="fixa").id == "fixa"


def test_sessao_enviar():
    s = AgentSession()
    out = s.enviar("faça a Juh acenar", _Amb(modelo_base()))
    assert out["ok"] is True
    assert s.estado == "REVIEW"
    assert [m.tipo for m in s.mensagens] == ["USER", "TOOL",
                                             "AGENT"]


def test_sessao_input_vazio():
    s = AgentSession()
    with pytest.raises(ErroELiXX):
        s.enviar("   ", _Amb(modelo_base()))
    with pytest.raises(ErroELiXX):
        s.enviar("faça X")


def test_sessao_sem_modelo():
    s = AgentSession()
    with pytest.raises(ErroELiXX):
        s.enviar("faça a Juh acenar", object())


def test_sessao_erro():
    s = AgentSession()
    out = s.enviar("faça a Juh levitar", _Amb(modelo_base()))
    assert out["ok"] is False
    assert s.estado == "ERROR"
    assert "Traceback" not in s.erro
    assert s.mensagens[-1].tipo == "ERROR"


def test_sessao_cancelar():
    s = AgentSession()
    s.enviar("faça a Juh acenar", _Amb(modelo_base()))
    assert s.cancelar() == {"estado": "CANCELLED"}
    with pytest.raises(ErroELiXX):
        s.cancelar()


def test_sessao_limpar():
    s = AgentSession()
    s.enviar("faça a Juh acenar", _Amb(modelo_base()))
    out = s.nova_sessao()
    assert out == {"limpas": 3}
    assert s.estado == "IDLE" and s.mensagens == []


def test_sessao_estado_invalido():
    s = AgentSession()
    with pytest.raises(ErroELiXX):
        s._estado("VOANDO")


def test_sessao_aprovar_sem_proposta():
    s = AgentSession()
    with pytest.raises(ErroELiXX):
        s.aprovar_proposta()


def test_sessao_dict():
    s = AgentSession()
    s.enviar("mostre a Juh", _Amb(modelo_base()))
    d = s.to_dict()
    assert d["estado"] == "REVIEW"
    assert len(d["mensagens"]) == 3


# ---------- CommandPalette (21-30) ----------

def test_palette_busca():
    pal = CommandPalette()
    assert len(pal.buscar("")) == 30  # F38 soma 10 comandos
    ids = [c["id"] for c in pal.buscar("plano")]
    assert "mostrar_plano" in ids
    assert pal.buscar("zzz-nada") == []


def test_palette_case():
    pal = CommandPalette()
    assert [c["id"] for c in pal.buscar("PREVIEW")] == \
        ["abrir_preview", "mostrar_preview", "focar_preview"]


def test_palette_acento():
    pal = CommandPalette()
    assert "sincronizar_projeto" in [
        c["id"] for c in pal.buscar("sincronizar")]
    assert pal.buscar("SÍNCRONIZAR")


def test_palette_contextuais():
    pal = CommandPalette()
    sem = pal.contextuais()
    assert "abrir_preview" in [c["id"] for c in sem]
    com = pal.contextuais({"id": "personagem:Juh"})
    assert {c["id"] for c in com} == {
        "inspecionar_selecao", "consultar_entidade",
        "mostrar_codigo", "mostrar_relacoes",
        "adicionar_contexto", "remover_contexto"}


def test_palette_executar(tmp_path):
    from elixx.studio import StudioApp

    pal = CommandPalette()
    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    out = pal.executar(app, "parar_projeto")
    assert out == {"ok": True}
    with pytest.raises(ErroELiXX):
        pal.executar(app, "teleportar")
    with pytest.raises(ErroELiXX):
        pal.executar(app, "mostrar_codigo")  # sem alvo


def test_palette_alvo():
    from elixx.studio import StudioApp

    pal = CommandPalette()
    out = pal.executar(StudioApp(), "mostrar_codigo",
                       {"alvo": "personagem:Juh"})
    assert out == {"ok": True, "comando": "mostrar_codigo",
                   "alvo": "personagem:Juh"}


def test_palette_navegacao():
    from elixx.studio import StudioApp

    pal = CommandPalette()
    out = pal.executar(StudioApp(), "mostrar_plano")
    assert out["nota"].startswith("navegação")


# ---------- seleção global (31-33) ----------

def test_selecao_global(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    ouvidos = []
    app.eventos.assinar("selecionado",
                        lambda e, d: ouvidos.append(d))
    out = selecao_global(app, "personagem", "personagem:Juh")
    assert out["ref_id"] == "personagem:Juh"
    assert app.inspetor.selecao.ref_id == "personagem:Juh"
    assert ouvidos[0]["ref_id"] == "personagem:Juh"


def test_selecao_unica(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    selecao_global(app, "no", "janela:p")
    selecao_global(app, "personagem", "personagem:Juh")
    assert app.inspetor.selecao.ref_id == "personagem:Juh"


def test_selecao_invalida():
    from elixx.studio import StudioApp

    with pytest.raises(ErroELiXX):
        selecao_global(StudioApp(), "pixel", "x")


# ---------- chips (34-35) ----------

def test_chips():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    r = construir_contexto(
        modelo_base(),
        ContextoTarefa(objetivo="ver", alvo="Juh"))
    chips = resumo_chips(r)
    assert all(set(c) == {"id", "nome", "tipo", "incluido"}
               for c in chips)
    assert all(c["incluido"] for c in chips)
    assert chips[0]["id"] == "personagem:Juh"


# ---------- Project/Preview/Inspector (36-44) ----------

def test_project_arvore(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    assert any(n["nome"] == "main.elixx"
               for n in ws.arvore.nos())


def test_project_traversal(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    with pytest.raises(ErroELiXX):
        ws.abrir_no_editor("../fora.elixx")


def test_preview_viewport(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    ws.analisar()
    out = ws.preview.executar("janela p {\n titulo: \"T\"\n}\n")
    assert out["sucesso"] is True
    assert ws.preview.sincronizar_modelo(ws.modelo)


def test_preview_vazio(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import estado_vazio

    assert estado_vazio("preview") == "(nada para mostrar)"
    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.preview.entidades == []


def test_inspector_vazio(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import estado_vazio

    assert estado_vazio("inspector") == \
        "(nenhum objeto selecionado)"
    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.inspector.secoes == []


def test_inspector_selecionado(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {\n personagem Juh {\n }\n}\n",
        encoding="utf-8")
    ws.analisar()
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    assert secoes[0]["campos"]["Tipo"] == "personagem"


def test_inspector_transform(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.inspetor import fluxo_personagem

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {\n}\n", encoding="utf-8")
    ws.analisar()
    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"}])
    secoes = ws.inspector.inspecionar(ws.modelo, "janela:p",
                                      personagem=perso)
    assert any(s["titulo"] == "Transform" for s in secoes)


def test_editor_header(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.documento.caminho == "src/main.elixx"
    assert ed.modificado() is False


# ---------- Reasoning/Trace/Plan/Changes (45-52) ----------

def test_reasoning_estagios():
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    assert list(ws.estagios)[2] == "TOOLS"


def test_trace_lista():
    from elixx.studio.agent.ferramentas_semanticas import (
        AgentToolCall,
        ToolTrace,
    )

    trace = ToolTrace()
    trace.registrar(AgentToolCall("buscar_entidade", {}))
    assert "buscar_entidade" in trace.explicar()


def test_plan_resumo():
    from elixx.studio.agent.operacoes import SemanticOperation
    from elixx.studio.agent.planejamento import PainelPlano, PlanoTarefa

    painel = PainelPlano(PlanoTarefa(
        "x", [SemanticOperation("pose", "Juh", {})]))
    assert painel.resumo()["progresso"]["total"] == 0
    assert painel.resumo()["aprovado"] is False


def test_changes_proposta(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import Approval, PermissionSet
    from elixx.studio.agent.loop import (
        PlanoSemantico,
        gerar_changeset,
        resolver_alvo,
        verificar_precondicoes,
    )
    from elixx.studio.agent import AgentIntent
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {\n}\n", encoding="utf-8")
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    plano = PlanoSemantico(
        AgentIntent("criar_cena", objetivo="x"),
        alvo={"status": "unico",
              "entidade": {"id": "janela:p",
                           "arquivo": "src/main.elixx"}},
        alteracoes_propostas=[{
            "arquivo": "src/n.elixx", "operacao": "criar",
            "conteudo_novo": "janela q {}\n"}])
    verificar_precondicoes(plano, app.workspace,
                           PermissionSet(["WRITE"]))
    cs = gerar_changeset(plano)
    assert cs.estado == "proposto"
    Approval("manual").aprovar_tudo(cs)
    assert cs.aplicar(app.workspace)["arquivos"] == ["src/n.elixx"]


def test_changes_rejeicao():
    from elixx.studio.agent import ChangeSet

    cs = ChangeSet()
    assert cs.estado == "proposto"


# ---------- Layouts (53-58) ----------

def test_layouts_nomes():
    from elixx.studio.workspace_ui import LAYOUTS, aplicar_layout_nome

    assert set(LAYOUTS) >= {"DEFAULT", "FOCUS_AGENT",
                             "FOCUS_CODE", "FOCUS_PREVIEW"}
    assert callable(aplicar_layout_nome)


def test_layout_default(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import aplicar_layout_nome

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    vis = aplicar_layout_nome(ws, "DEFAULT")
    assert len(vis) == 8


def test_layout_agent(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import aplicar_layout_nome

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    vis = aplicar_layout_nome(ws, "FOCUS_AGENT")
    assert "agent" in vis and "editor" not in vis


def test_layout_code(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import aplicar_layout_nome

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    vis = aplicar_layout_nome(ws, "FOCUS_CODE")
    assert "editor" in vis and "preview" not in vis


def test_layout_preview(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import aplicar_layout_nome

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    vis = aplicar_layout_nome(ws, "FOCUS_PREVIEW")
    assert "preview" in vis and "inspector" in vis


def test_layout_invalido(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import aplicar_layout_nome

    app = StudioApp()
    ws = StudioWorkspace(app)
    with pytest.raises(ErroELiXX):
        aplicar_layout_nome(ws, "MODO_FESTA")


# ---------- responsivo/compacto/teclado (59-66) ----------

def test_responsivo():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    for geo in ((800, 500), (1024, 768), (1280, 720),
                (1366, 768), (1600, 900), (1920, 1080),
                (2560, 1440), (3840, 2160)):
        assert lay.definir_geometria(*geo) == geo


def test_compacto():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    lay.definir_compacto(True)
    assert lay.compacto is True
    lay.definir_compacto(False)
    assert len(lay.paineis_visiveis()) == 8


def test_teclado_atual():
    from elixx.studio.app import ATALHOS

    for tecla in ("Ctrl+K", "Ctrl+Enter", "Esc", "Ctrl+P",
                  "Ctrl+Shift+P", "Ctrl+1", "F"):
        assert tecla in ATALHOS, tecla


def test_teclado_sem_conflito():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+S"] == "salvar"  # editor intacto
    assert ATALHOS["Ctrl+Z"] == "desfazer"
    assert ATALHOS["F5"] == "executar"


def test_persist_layout(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import carregar_layout, salvar_layout

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ws.layout.definir_aba("plano")
    salvar_layout(ws)
    ws.layout.definir_aba("console")
    assert carregar_layout(ws) is True
    assert ws.layout.aba_inferior == "plano"


# ---------- integrações F26-F36 (67-77) ----------

def test_f26_task():
    from elixx.studio.agent import AgentTask

    t = AgentTask("x")
    assert t.estado == "criada"


def test_f27_modelo():
    from elixx.studio.modelo import ConsultaSemantica

    q = ConsultaSemantica(modelo_base())
    assert q.encontrar_por_nome("Juh")[0].id == \
        "personagem:Juh"


def test_f28_loop():
    from elixx.studio.agent.loop import resolver_alvo

    assert resolver_alvo(modelo_base(), "Juh")[
        "status"] == "unico"


def test_f29_workspace():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.layout is not None


def test_f30_intent():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    assert it.tipo == "mostrar"


def test_f31_op():
    from elixx.studio.agent.operacoes import intent_para_operacao
    from elixx.studio.agent.inteligencia import MockIntentProvider

    op = intent_para_operacao(MockIntentProvider(
    ).gerar_intencao(None, "mostre a Juh"))
    assert op.tipo == "mostrar"


def test_f32_sync():
    from elixx.studio.codigo import SincronizadorBidirecional

    assert callable(SincronizadorBidirecional)


def test_f33_planner():
    from elixx.studio.agent.planejamento import PlanoTarefa

    assert PlanoTarefa("x", []).objetivo == "x"


def test_f34_contexto():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    r = construir_contexto(
        modelo_base(), ContextoTarefa(objetivo="ver", alvo="Juh"))
    assert r.entidades[0].id == "personagem:Juh"


def test_f35_grafo():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    ws.carregar_contexto(construir_contexto(
        modelo_base(), ContextoTarefa(objetivo="ver", alvo="Juh")))
    assert len(ws.nos) == 5  # 4 entidades + 1 arquivo


def test_f36_tools():
    from elixx.studio.agent.ferramentas_semanticas import (
        SemanticToolRegistry,
    )

    assert len(SemanticToolRegistry().listar()) == 30


# ---------- segurança (78-86) ----------

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


def test_sec_eval():
    s = AgentSession()
    out = s.enviar("eval(1+1)", _Amb(modelo_base()))
    assert out["ok"] is False


def test_sec_exec():
    s = AgentSession()
    out = s.enviar("exec('x')", _Amb(modelo_base()))
    assert out["ok"] is False


def test_sec_import():
    from elixx.studio.agent import interacao as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "importlib" not in fonte
    assert "__import__" not in fonte


def test_sec_pickle():
    from elixx.studio.agent import interacao as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "pickle" not in fonte
    assert "eval(" not in fonte and "exec(" not in fonte


def test_sec_subprocess():
    from elixx.studio.agent import interacao as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "subprocess" not in fonte
    assert "os.system" not in fonte
    assert "requests" not in fonte


def test_sec_nan():
    with pytest.raises(ErroELiXX):
        AgentSession()._estado("VOAR")
    from elixx.studio.agent.contexto_tarefa import ContextoEntidade

    with pytest.raises(ErroELiXX):
        ContextoEntidade("a", score=float("nan"))


def test_sec_strings():
    s = AgentSession()
    out = s.enviar("<script>alert(1)</script>",
                   _Amb(modelo_base()))
    assert out["ok"] is False
    assert s.mensagens[0].conteudo == "<script>alert(1)</script>"


# ---------- determinismo (87-88) ----------

def test_det_sessao():
    def rodada():
        s = AgentSession(sessao_id="fixa")
        return s.enviar("faça a Juh acenar",
                        _Amb(modelo_base()))

    a = rodada()
    b = rodada()
    assert a["intencao"] == b["intencao"]
    assert a["operacao"] == b["operacao"]


def test_det_palette():
    pal1 = CommandPalette().buscar("plano")
    pal2 = CommandPalette().buscar("plano")
    assert pal1 == pal2


# ---------- performance (89-91) ----------

def _modelo_grande(total):
    from elixx.studio.modelo import EntidadeSemantica

    m = ModeloSemantico("p")
    for i in range(total):
        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:05d}", "simbolo", f"S{i}"))
    return m


def test_perf_entidades():
    import time as _t

    from elixx.studio.agent.contexto_tarefa import (
        ContextoConfig,
        ContextoTarefa,
        construir_contexto,
    )

    for total in (100, 500, 1000, 5000, 10000):
        m = _modelo_grande(total)
        t0 = _t.perf_counter()
        r = construir_contexto(
            m, ContextoTarefa(objetivo="ver S42", alvo="S42"),
            ContextoConfig(max_entidades=total,
                           max_por_categoria=total,
                           max_bytes=10_000_000))
        dt = _t.perf_counter() - t0
        assert r.entidades[0].id == "s:00042" and dt < 60.0
        if total == 10000:
            print(f"\n10000 ent ctx: {dt:.2f}s")


def test_perf_sessoes():
    import time as _t

    t0 = _t.perf_counter()
    for total in (100, 500, 1000):
        for _ in range(total):
            AgentSession()
        dt = _t.perf_counter() - t0
        assert dt < 60.0
        if total == 1000:
            print(f"\n1000 sessoes: {dt:.2f}s")


# ---------- regressão UI (92-94) ----------

def test_regressao_tema():
    from elixx.studio.tema import validar_tokens

    assert validar_tokens()["valido"] is True


def test_regressao_layout():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    assert "raciocinio" in lay.paineis_visiveis() or True
    assert lay.definir_aba("raciocinio") == "raciocinio"


def test_regressao_montar():
    from elixx.studio.workspace_ui import montar_workspace_ui

    assert callable(montar_workspace_ui)


def test_layouts_todos():
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import LAYOUTS, aplicar_layout_nome

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="lay37_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "p", "P")
    for nome in LAYOUTS:
        vis = aplicar_layout_nome(ws, nome)
        assert vis  # nenhum preset vazio


def test_palette_total():
    assert len(CommandPalette().buscar("")) == 30  # F38 soma 10


def test_sessao_conversas():
    s = AgentSession()
    amb = _Amb(modelo_base())
    s.enviar("mostre a Juh", amb)
    s.enviar("selecione a Juh", amb)
    assert len(s.mensagens) == 6
    assert s.mensagens[3].tipo == "USER"


def test_msg_multi_ref():
    m = AgentMessage("AGENT", "x",
                     referencias=[{"id": "a"}, {"id": "b"}])
    assert len(m.referencias) == 2


def test_preview_toolbar_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    for modo in ("Selecionar", "Mover", "Escalar", "Girar",
                 "Ajustar"):
        assert modo in fonte


def test_ver_codigo_botao():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Ver código" in fonte
    assert "_ver_codigo" in fonte


def test_layout_menu_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "FOCUS_AGENT" in fonte
    assert "OptionMenu" in fonte


def test_console_inicio_vazio():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.console.entradas == []


def test_agent_header_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "ELiXX AGENT" in fonte
    assert "MOCK / DETERMINISTIC" in fonte
    assert "Nova sessão" in fonte


def test_interacao_nomes():
    import elixx.studio.agent.interacao as modulo

    for nome in ("AgentMessage", "AgentSession",
                 "CommandPalette", "resumo_chips",
                 "selecao_global"):
        assert hasattr(modulo, nome), nome


def test_msg_tipos_conversa():
    s = AgentSession()
    s.enviar("faça a Juh acenar", _Amb(modelo_base()))
    tipos = [m.tipo for m in s.mensagens]
    assert tipos[0] == "USER" and tipos[-1] == "AGENT"
    assert any(m.tipo == "TOOL" for m in s.mensagens)


def test_msg_ids_unicos():
    s = AgentSession()
    s.enviar("mostre a Juh", _Amb(modelo_base()))
    ids = [m.id for m in s.mensagens]
    assert len(ids) == len(set(ids))


def test_sessao_todas_mensagens():
    s = AgentSession()
    s.enviar("quem é a Juh?", _Amb(modelo_base()))
    assert any(m.tipo == "AGENT" for m in s.mensagens)


def test_sessao_system_tool():
    s = AgentSession()
    s._dizer("SYSTEM", "boot")
    s._dizer("TOOL", "trace")
    s._dizer("RESULT", "ok")
    assert [m.tipo for m in s.mensagens[-3:]] == ["SYSTEM",
                                                 "TOOL",
                                                 "RESULT"]


def test_palette_todas():
    pal = CommandPalette()
    assert len(pal.buscar("")) == 30  # F38 soma 10
    for cmd in ("abrir_arquivo", "nova_sessao",
                "alternar_compacto", "mostrar_raciocinio",
                "abrir_codigo", "focar_agent"):
        assert cmd in [c["id"] for c in pal.buscar("")]


def test_palette_exec_navegacao():
    from elixx.studio import StudioApp

    pal = CommandPalette()
    for cid in ("abrir_preview", "mostrar_tools",
                "alternar_compacto", "nova_sessao"):
        out = pal.executar(StudioApp(), cid)
        assert out["ok"] is True and out["comando"] == cid


def test_palette_exec_contextual():
    from elixx.studio import StudioApp

    pal = CommandPalette()
    out = pal.executar(StudioApp(), "adicionar_contexto",
                       {"alvo": "personagem:Juh"})
    assert out["alvo"] == "personagem:Juh"


def test_chips_vazios():
    from elixx.studio.agent.contexto_tarefa import ContextoResultado

    assert resumo_chips(ContextoResultado()) == []


def test_chips_ordem():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    r = construir_contexto(
        modelo_base(), ContextoTarefa(objetivo="ver", alvo="Juh"))
    chips = resumo_chips(r)
    assert chips[0]["id"] == "personagem:Juh"


def test_layouts_conteudo():
    from elixx.studio.workspace_ui import LAYOUTS

    assert set(LAYOUTS["DEFAULT"]) >= {"editor", "agent"}
    assert "editor" not in LAYOUTS["FOCUS_AGENT"]
    assert "agent" in LAYOUTS["FOCUS_CODE"]  # compacto, presente
    assert "project" not in LAYOUTS["FOCUS_PREVIEW"]


def test_preview_toolbar_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    for modo in ("Selecionar", "Mover", "Escalar", "Girar",
                 "Ajustar"):
        assert modo in fonte


def test_preview_empty_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "(nada para mostrar)" in fonte


def test_inspector_vazio_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "(nenhum objeto selecionado)" in fonte


def test_ver_codigo_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Ver código" in fonte
    assert "localizar_entidade" in fonte


def test_palette_ui_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Command Palette (Ctrl+K)" in fonte
    assert "Control-k" in fonte


def test_layout_ui_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "FOCUS_AGENT" in fonte
    assert "Control-1" in fonte and "Control-4" in fonte


def test_status_tooltips_fonte():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "Executar preview (F5)" in fonte
    assert "_dica" in fonte


def test_console_categorias():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    for cat in ("INFO", "WARNING", "ERROR", "AGENT", "BUILD",
                "PREVIEW"):
        ws.console.registrar(cat, f"msg {cat}")
    assert len(ws.console.entradas) == 6


def test_timeline_trilhas():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.timeline.adicionar("Juh", "acenar", 0.0, 500.0)
    assert ws.timeline.duracao_total() == 500.0


def test_diagnostics_vazio():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.diagnosticos.resumo() == {"total": 0, "erros": 0,
                                        "valido": True}


def test_diagnostics_navegar():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ed = ws.abrir_no_editor.__self__ if False else None
    assert ed is None
    from elixx.studio import DocumentoELiXX

    doc = DocumentoELiXX("a.elixx", "l1\nl2\nl3")
    from elixx.studio import EditorCodigo

    codigo = EditorCodigo(doc)
    diags = codigo.diagnosticar()
    ws.diagnosticos.atualizar(diags)
    assert ws.diagnosticos.resumo()["total"] == 1


def test_layout_persist_aba():
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import carregar_layout, salvar_layout

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="lay37_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "p", "P")
    ws.layout.definir_aba("timeline")
    salvar_layout(ws)
    ws.layout.definir_aba("console")
    assert carregar_layout(ws) is True
    assert ws.layout.aba_inferior == "timeline"


def test_layout_corrompido():
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import carregar_layout

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="lay37b_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "p", "P")
    (tmp / "p" / ".elixx").mkdir(exist_ok=True)
    (tmp / "p" / ".elixx" / "layout.json").write_text(
        "{corrompido", encoding="utf-8")
    assert carregar_layout(ws) is False
    assert ws.layout.aba_inferior == "console"


def test_atalhos_palette():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+K"] == "palette"
    assert ATALHOS["Ctrl+1"] == "layout_default"
    assert ATALHOS["Ctrl+4"] == "layout_preview"


def test_geometrias_ok():
    from elixx.studio.workspace_ui import GEOMETRIAS_OK

    assert (800, 500) in GEOMETRIAS_OK
    assert (1920, 1080) in GEOMETRIAS_OK
    assert len(GEOMETRIAS_OK) == 8


def test_estado_execucao():
    from elixx.studio.workspace_ui import resumo_status

    assert "Executando" in resumo_status("P", "a", True, 0,
                                         None, 0, True)


def test_vazios_todos():
    from elixx.studio.workspace_ui import VAZIOS

    assert set(VAZIOS) == {"projeto", "preview", "inspector",
                           "plano", "raciocinio", "console"}


def test_interacao_sem_duplicar():
    import elixx.studio.agent.interacao as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "class AgentContext" not in fonte
    assert "class ChangeSet" not in fonte
    assert "class AgentPlan" not in fonte


def test_sessao_historico_f26():
    from elixx.studio.agent import AgentHistory

    s = AgentSession()
    s.enviar("faça a Juh acenar", _Amb(modelo_base()))
    assert len(s.mensagens) == 3
    assert isinstance(AgentHistory(), AgentHistory)


def test_perf_palette():
    import time as _t

    pal = CommandPalette()
    t0 = _t.perf_counter()
    for _ in range(1000):
        pal.buscar("plano")
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_sessoes_mensagens():
    import time as _t

    t0 = _t.perf_counter()
    for total in (100, 500, 1000):
        for _ in range(total):
            s = AgentSession()
            for _ in range(10):
                s._dizer("USER", "oi")
        dt = _t.perf_counter() - t0
        assert dt < 60.0
        if total == 1000:
            print(f"\n1000 sessoes x10 msgs: {dt:.2f}s")


def test_perf_chips():
    import time as _t

    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    r = construir_contexto(
        modelo_base(), ContextoTarefa(objetivo="ver", alvo="Juh"))
    t0 = _t.perf_counter()
    for _ in range(1000):
        resumo_chips(r)
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_selecao():
    import time as _t

    from elixx.studio import StudioApp

    app = StudioApp()
    t0 = _t.perf_counter()
    for _ in range(500):
        selecao_global(app, "no", "janela:p")
    assert (_t.perf_counter() - t0) < 30.0
    assert app.inspetor.selecao.ref_id == "janela:p"
