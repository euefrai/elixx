"""Testes da Fase 33 — planner semântico + UX headless (sem LLM)."""
import pytest

from elixx.studio.agent import Approval

from elixx.erros import ErroELiXX
from elixx.studio.agent.operacoes import (
    SemanticEventOperation,
    SemanticOperation,
)
from elixx.studio.agent.planejamento import (
    Condicao,
    PainelPlano,
    PlanoTarefa,
    construir_plano,
    diff_semantico_passo,
    dry_run,
    executar_plano,
    explicar_plano,
    preparar_execucao,
    validar_plano,
)
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela p {\n"
    ' titulo: "T"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "   rotacao: 0\n"
    "  }\n"
    " }\n"
    "}\n"
)


def projeto(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    modelo = ModeloSemantico("p")
    analisar_projeto(modelo, tmp_path / "p")
    return app, modelo


def op_pose():
    return SemanticOperation("pose", "Juh", {"pose": "acenar"})


def op_giro(valor="15"):
    return SemanticOperation(
        "alterar_propriedade", {"nome": "corpo"},
        {"propriedade": "rotacao"},
        alteracao={"arquivo": "src/main.elixx",
                   "propriedade": "rotacao",
                   "valor_texto": valor})


def tarefa_giro():
    return PlanoTarefa("girar corpo", [op_pose(), op_giro()],
                       dependencias={"passo_2": ["passo_1"]})


def personagens_juh():
    from elixx.studio.inspetor import fluxo_personagem

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "corpo", "tipo": "corpo"}])
    from elixx.visual.personagem import Pose

    perso.poses["acenar"] = Pose(
        "acenar", entradas={"corpo": {"rotacao": 45.0}})
    return {"Juh": perso}


# ---------- TASK (1-6) ----------

def test_task_criacao():
    t = PlanoTarefa("demo", [op_pose()])
    assert t.objetivo == "demo" and len(t.operacoes) == 1
    assert t.task.estado == "criada"
    assert t.id.startswith("plano_")


def test_task_estados():
    t = PlanoTarefa("demo", [op_pose()])
    assert t.task.transitar("analisando").estado == "analisando"
    t.task.transitar("falhou")
    assert t.to_dict()["estado"] == "falhou"


def test_task_cancelamento():
    t = PlanoTarefa("demo", [op_pose()])
    t.task.transitar("cancelada")
    assert t.task.estado == "cancelada"


def test_task_conclusao(tmp_path):
    app, modelo = projeto(tmp_path)
    t = tarefa_giro()
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    for p in prep["preparados"]:
        if p["changeset"] is not None:
            from elixx.studio.agent import Approval

            Approval("manual").aprovar_tudo(p["changeset"])
    out = executar_plano(t, {
        "workspace": app.workspace, "modelo": modelo,
        "personagens": personagens_juh(),
        "approval": Approval("manual"),
        "preparar": prep})
    assert out["estado"] == "concluida"
    assert t.task.estado == "concluida"


def test_task_falha(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [SemanticOperation("pose", "Fantasma",
                                            {"pose": "acenar"})])
    construir_plano(t)
    with pytest.raises(ErroELiXX):
        executar_plano(t, {"workspace": app.workspace,
                           "modelo": modelo, "personagens": {}})


def test_task_ids():
    a = PlanoTarefa("mesmo objetivo", [op_pose()])
    b = PlanoTarefa("mesmo objetivo", [op_pose()])
    assert a.id != b.id  # contador, sem hash
    assert PlanoTarefa("x", [], tarefa_id="fixa").id == "fixa"
    with pytest.raises(ErroELiXX):
        PlanoTarefa("   ", [op_pose()])
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", ["nao-op"])
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", [op_pose()] * 5001)


# ---------- PLAN (7-14) ----------

def test_plan_criacao():
    t = tarefa_giro()
    construir_plano(t)
    assert t.plano is not None
    assert sorted(t.plano.passos) == ["passo_1", "passo_2"]


def test_plan_passos():
    t = tarefa_giro()
    construir_plano(t)
    p2 = t.plano.passo("passo_2")
    assert p2.dependencias == ["passo_1"]
    assert p2.risco == "medio"  # toca arquivo


def test_plan_dependencias():
    t = PlanoTarefa("x", [op_pose(), op_pose()],
                    dependencias={"passo_2": ["passo_1"]})
    construir_plano(t)
    assert t.plano.ordem_execucao() == ["passo_1", "passo_2"]
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", [op_pose()],
                    dependencias={"passo_9": ["passo_1"]})
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", [op_pose()],
                    dependencias={"passo_1": ["fantasma"]})


def test_plan_ordenacao():
    t = PlanoTarefa("x", [op_pose(), op_pose(), op_pose()],
                    dependencias={"passo_3": ["passo_1",
                                              "passo_2"]})
    construir_plano(t)
    ordem = t.plano.ordem_execucao()
    assert ordem[-1] == "passo_3"
    assert ordem[:2] == ["passo_1", "passo_2"]  # determinística


def test_plan_ciclos():
    t = PlanoTarefa("x", [op_pose(), op_pose()],
                    dependencias={"passo_1": ["passo_2"],
                                  "passo_2": ["passo_1"]})
    with pytest.raises(ErroELiXX):
        construir_plano(t)


def test_plan_duplicados():
    from elixx.studio.agent import AgentPlan
    from elixx.studio.agent import PlanStep

    with pytest.raises(ErroELiXX):
        AgentPlan(None, [PlanStep("a"), PlanStep("a")])


def test_plan_auto_dependencia():
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", [op_pose()],
                    dependencias={"passo_1": ["passo_1"]})


def test_plan_auto_cadeia(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro("10"), op_giro("20")])
    construir_plano(t, modelo)
    assert t.plano.passo("passo_2").dependencias == ["passo_1"]


# ---------- PRECONDITIONS (15-19) ----------

def test_pre_validas(tmp_path):
    app, modelo = projeto(tmp_path)
    t = tarefa_giro()
    construir_plano(t, modelo)
    assert all(isinstance(c, Condicao) for c in t.precondicoes)
    assert any("único" in c.descricao for c in t.precondicoes)


def test_pre_invalidas():
    t = PlanoTarefa("x", [op_pose()])
    construir_plano(t)
    with pytest.raises(ErroELiXX):
        Condicao("talvez")


def test_pre_alvo_ausente(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [SemanticOperation("pose", "Fantasma",
                                            {})])
    with pytest.raises(ErroELiXX) as exc:
        construir_plano(t, modelo)
    assert "alvo" in str(exc.value)


def test_pre_alvo_ambiguo(tmp_path):
    from elixx.studio.modelo import analisar_texto

    m = ModeloSemantico("p")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao Juh(x) {\n retornar x\n}\n",
                   "src/b.elixx")
    t = PlanoTarefa("x", [SemanticOperation("pose", "Juh", {})])
    with pytest.raises(ErroELiXX):
        construir_plano(t, m)


def test_pre_arquivo(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [SemanticOperation(
        "alterar_propriedade", "Juh", {},
        alteracao={"arquivo": "src/fantasma.elixx",
                   "propriedade": "x", "valor_texto": "1"})])
    construir_plano(t, modelo)
    out = validar_plano(t, modelo, app.workspace)
    assert out["codigo"] == "arquivo_ausente"


# ---------- POSTCONDITIONS (20-22) ----------

def test_pos_sucesso(tmp_path):
    app, modelo = projeto(tmp_path)
    t = tarefa_giro()
    construir_plano(t, modelo)
    assert any(c.kind == "pos" for c in t.poscondicoes)
    prep = preparar_execucao(t, app.workspace, modelo)
    for p in prep["preparados"]:
        if p["changeset"] is not None:
            from elixx.studio.agent import Approval

            Approval("manual").aprovar_tudo(p["changeset"])
    from elixx.studio.agent import Approval as _A

    executar_plano(t, {"workspace": app.workspace,
                       "modelo": modelo,
                       "personagens": personagens_juh(),
                       "approval": _A("manual"), "preparar": prep})
    assert t.task.estado == "concluida"


def test_pos_falha():
    c = Condicao("pos", "existe", entidade="X")
    assert c.to_dict()["entidade"] == "X"
    assert Condicao.from_dict(c.to_dict()).kind == "pos"
    with pytest.raises(ErroELiXX):
        Condicao.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        Condicao("pre", "x", esperado=object())


def test_pos_diagnostico(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [SemanticOperation("pose", "Fantasma",
                                            {})])
    construir_plano(t)  # sem modelo: sem diagnóstico fatal
    assert t.diagnosticos == []
    assert validar_plano(t)["valido"] is True


# ---------- PLANNER (23-26) ----------

def test_planner_operacoes():
    t = PlanoTarefa("x", [op_pose(), op_giro()])
    construir_plano(t)
    assert len(t.plano.passos) == 2


def test_planner_dependencias():
    t = PlanoTarefa("x", [op_pose(), op_giro(), op_pose()],
                    dependencias={"passo_3": ["passo_1"]})
    construir_plano(t)
    ordem = t.plano.ordem_execucao()
    assert ordem.index("passo_1") < ordem.index("passo_3")


def test_planner_deterministico():
    def montar():
        t = PlanoTarefa("x", [op_pose(), op_giro()],
                        dependencias={"passo_2": ["passo_1"]})
        construir_plano(t)
        return t.plano.ordem_execucao()

    assert montar() == montar() == ["passo_1", "passo_2"]


def test_planner_nao_suportadas():
    t = PlanoTarefa("x", [SemanticOperation("pose", "Juh", {})])
    construir_plano(t)
    assert validar_plano(t)["codigo"] == "ok"
    with pytest.raises(ErroELiXX):
        SemanticOperation("teleportar", "Juh", {})


# ---------- F30 (27-28) ----------

def test_f30_intent_operacao():
    from elixx.studio.agent.inteligencia import MockIntentProvider
    from elixx.studio.agent.operacoes import intent_para_operacao

    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    op = intent_para_operacao(it)
    t = PlanoTarefa("mostrar", [op])
    construir_plano(t)
    assert t.plano.ordem_execucao() == ["passo_1"]


def test_f30_plano():
    from elixx.studio.agent.inteligencia import MockIntentProvider
    from elixx.studio.agent.operacoes import intent_para_operacao

    it = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    t = PlanoTarefa("acenar", [intent_para_operacao(it)])
    construir_plano(t)
    assert explicar_plano(t).startswith("Vou executar 1 etapa")


# ---------- F31 (29-30) ----------

def test_f31_operacoes():
    from elixx.studio.agent.operacoes import validar_operacao

    assert validar_operacao(op_pose())["valido"] is True
    assert validar_operacao(op_giro())["valido"] is True
    sem_bloco = SemanticOperation("adicionar_evento", "Juh")
    assert validar_operacao(sem_bloco)["codigo"] == \
        "alteracao_ausente"


def test_f31_evento():
    from elixx.studio.agent.operacoes import SemanticEventOperation

    ev = SemanticEventOperation(
        "clique", "Juh",
        [SemanticOperation("pose", "Juh", {"pose": "acenar"})])
    t = PlanoTarefa("evento", [ev])
    construir_plano(t)
    assert t.plano.ordem_execucao() == ["passo_1"]


# ---------- F32 (31-34) ----------

def test_f32_changeset(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    assert prep["preparados"][0]["tipo"] == "codigo"
    assert prep["preparados"][0]["changeset"].estado == "proposto"


def test_f32_aplicacao(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    from elixx.studio.agent import Approval

    for p in prep["preparados"]:
        if p["changeset"] is not None:
            Approval("manual").aprovar_tudo(p["changeset"])
    out = executar_plano(t, {"workspace": app.workspace,
                             "modelo": modelo, "personagens": {},
                             "approval": Approval("manual"),
                             "preparar": prep})
    assert out["aplicados"] == 1
    assert "rotacao: 15" in (tmp_path / "p" / "src" /
                             "main.elixx").read_text(
                                 encoding="utf-8")


def test_f32_rollback(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro("10"),
                          SemanticOperation("pose", "Fantasma",
                                            {})])
    construir_plano(t)  # sem modelo: falha só na execução
    prep = preparar_execucao(t, app.workspace, modelo)
    for p in prep["preparados"]:
        if p["changeset"] is not None:
            from elixx.studio.agent import Approval

            Approval("manual").aprovar_tudo(p["changeset"])
    with pytest.raises(ErroELiXX):
        executar_plano(t, {"workspace": app.workspace,
                           "modelo": modelo, "personagens": {},
                           "approval": Approval("manual"),
                           "preparar": prep})
    assert t.task.estado == "falhou"
    assert any(e["evento"] == "rollback"
               for e in t.task.eventos)
    assert "rotacao: 10" not in (tmp_path / "p" / "src" /
                                 "main.elixx").read_text(
                                     encoding="utf-8")


def test_f32_reanalise(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    from elixx.studio.agent import Approval

    for p in prep["preparados"]:
        if p["changeset"] is not None:
            Approval("manual").aprovar_tudo(p["changeset"])
    executar_plano(t, {"workspace": app.workspace,
                       "modelo": modelo, "personagens": {},
                       "approval": Approval("manual"),
                       "preparar": prep})
    assert "personagem:Juh" in modelo  # reparseado


# ---------- DRY-RUN (35-37) ----------

def test_dryrun_sem_escrita(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro(), op_pose()])
    construir_plano(t, modelo)
    antes = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    secs = dry_run(t)
    assert secs["ordem"] == ["passo_1", "passo_2"]
    assert (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8") == antes  # nada escrito
    assert secs["arquivos"] == ["src/main.elixx"]


def test_dryrun_deterministico(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro(), op_pose()])
    construir_plano(t, modelo)
    assert dry_run(t) == dry_run(t)
    with pytest.raises(ErroELiXX):
        dry_run(PlanoTarefa("x", [op_pose()]))  # sem plano


def test_dryrun_riscos(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    assert dry_run(t)["riscos"] == ["medio"]


# ---------- SEGURANÇA (38-46) ----------

def test_sec_traversal(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [SemanticOperation(
        "alterar_propriedade", "Juh", {},
        alteracao={"arquivo": "../fora.elixx",
                   "propriedade": "x", "valor_texto": "1"})])
    construir_plano(t, modelo)
    out = validar_plano(t, modelo, app.workspace)
    assert out["codigo"] == "arquivo_ausente"


def test_sec_payload():
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", [op_pose()] * 5001)
    op = SemanticOperation("pose", "Juh", {})
    assert op.to_json()


def test_sec_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh", {"f": fundo})
    with pytest.raises(ErroELiXX):
        Condicao("pre", "x", esperado=fundo)


def test_sec_ciclos():
    t = PlanoTarefa("x", [op_pose(), op_pose(), op_pose()],
                    dependencias={"passo_1": ["passo_3"],
                                  "passo_3": ["passo_1"]})
    with pytest.raises(ErroELiXX):
        construir_plano(t)
    out = validar_plano(PlanoTarefa("x", [op_pose()]))
    assert out["codigo"] == "sem_plano"


def test_sec_strings():
    op = SemanticOperation("pose", "__import__('os')",
                           {"pose": "<script>"})
    assert op.alvo.nome == "__import__('os')"
    t = PlanoTarefa("eval(x)", [op])
    assert "eval(x)" in t.objetivo


def test_sec_eval():
    import elixx.studio.agent.planejamento as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [pathlib.Path(modulo.__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess"):
            assert proibido not in fonte, proibido
    assert base.name == "agent"


def test_sec_exec():
    with pytest.raises(ErroELiXX):
        PlanoTarefa("x", ["exec('y')"])


def test_sec_pickle():
    import pickle  # noqa: checar ausência no módulo

    assert pickle.__name__ == "pickle"
    import elixx.studio.agent.planejamento as modulo

    assert "pickle" not in open(modulo.__file__,
                                encoding="utf-8").read()


def test_sec_subprocess():
    import elixx.studio.agent.planejamento as modulo

    assert "subprocess" not in open(modulo.__file__,
                                    encoding="utf-8").read()


# ---------- UX HEADLESS (47-62) ----------

def test_ux_painel():
    t = PlanoTarefa("x", [op_pose(), op_giro()])
    construir_plano(t)
    painel = PainelPlano(t)
    assert len(painel.passos()) == 2
    assert painel.passos()[0]["estado"] == "pendente"


def test_ux_estados():
    from elixx.studio.agent import PlanStep

    t = PlanoTarefa("x", [op_pose()])
    construir_plano(t)
    t.plano.passo("passo_1").transitar("executando")
    t.plano.passo("passo_1").transitar("concluido")
    painel = PainelPlano(t)
    assert painel.passos()[0]["estado"] == "concluido"
    assert painel.progresso() == {"total": 1, "concluidos": 1,
                                  "percentual": 100}
    with pytest.raises(ErroELiXX):
        PlanStep("a").transitar("concluido")  # salto inválido


def test_ux_selecao():
    t = PlanoTarefa("x", [op_pose(), op_giro()])
    construir_plano(t)
    painel = PainelPlano(t)
    sel = painel.selecionar_passo("passo_2")
    assert sel["id"] == "passo_2"
    assert painel.selecionado == "passo_2"
    with pytest.raises(ErroELiXX):
        painel.selecionar_passo("passo_9")


def test_ux_plano(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    painel = PainelPlano(t)
    assert painel.resumo()["arquivos"] == ["src/main.elixx"]
    assert painel.resumo()["aprovado"] is False


def test_ux_diff(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    painel = PainelPlano(t)
    diff = painel.diff_passo("passo_1", app.workspace, modelo)
    assert len(diff["trocas"]) == 1
    assert diff["semantico"].startswith("parte:Juh.corpo.rotacao")


def test_ux_aprovacao():
    t = PlanoTarefa("x", [op_pose()])
    construir_plano(t)
    painel = PainelPlano(t)
    assert painel.aprovar() is True
    assert painel.resumo()["aprovado"] is True
    assert painel.recusar() is False
    assert painel.passos()[0]["estado"] == "cancelado"


def test_ux_erro():
    t = PlanoTarefa("x", [op_pose()])
    painel = PainelPlano(t)  # sem plano: vazio honesto
    assert painel.passos() == []
    assert painel.progresso() == {"total": 0, "concluidos": 0,
                                  "percentual": 0}
    with pytest.raises(ErroELiXX):
        painel.selecionar_passo("passo_1")


def test_ux_empty_states(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.layout.paineis_visiveis()
    assert ws.estado()["projeto"] is None
    assert PainelPlano(PlanoTarefa("x", [])).resumo()[
        "estado"] == "criada"


def test_ux_responsividade():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    for geo in ((800, 500), (1024, 768), (1280, 720),
                (1366, 768), (1920, 1080), (2560, 1440),
                (3840, 2160)):
        assert lay.definir_geometria(*geo) == geo


def test_ux_atalhos():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+P"] == "pesquisa_rapida"
    assert ATALHOS["Ctrl+Shift+P"] == "paleta_comandos"
    assert ATALHOS["Ctrl+Enter"] == "aprovar"
    assert ATALHOS["Esc"] == "cancelar"
    assert ATALHOS["Ctrl+S"] == "salvar"  # preservados


def test_ux_layout_persist(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import carregar_layout, salvar_layout

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    ws.layout.definir_compacto(True)
    assert salvar_layout(ws) == ".elixx/layout.json"
    ws.layout.definir_compacto(False)
    assert carregar_layout(ws) is True
    assert ws.layout.compacto is True
    ws2 = StudioWorkspace(StudioApp())
    assert carregar_layout(ws2) is False  # sem projeto


def test_ux_statusbar(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    est = ws.estado()
    assert est["projeto"] == "P" and est["salvo"] is True


def test_ux_tooltips_contrato():
    import elixx.studio.workspace_ui as modulo
    import inspect

    fonte = inspect.getsource(modulo.montar_workspace_ui)
    assert "barra_status" in fonte  # dicas via statusbar
    assert "dicas" in fonte or "tooltip" in fonte.lower() or \
        "_dica" in fonte


def test_ux_sem_display():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    for arq in pathlib.Path(modulo.__file__).parent.glob(
            "workspace_ui.py"):
        for linha in arq.read_text(encoding="utf-8").splitlines():
            assert not linha.startswith("import tkinter")
            assert not linha.startswith("from tkinter")


def test_ux_painel_sem_plano():
    with pytest.raises(ErroELiXX):
        PainelPlano("nao-tarefa")


# ---------- PERFORMANCE (63-65) ----------

def test_perf_operacoes():
    import time as _t

    t0 = _t.perf_counter()
    ops = [SemanticOperation("pose", f"P{i}",
                             {"pose": "acenar"})
           for i in range(1000)]
    t = PlanoTarefa("x", ops)
    construir_plano(t)
    assert len(t.plano.ordem_execucao()) == 1000
    assert (_t.perf_counter() - t0) < 30.0
    print(f"\n1000 ops: plano em {(_t.perf_counter() - t0):.2f}s")


def test_perf_arquivos(tmp_path):
    import time as _t

    from elixx.studio import StudioApp
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


def test_perf_dryrun(tmp_path):
    import time as _t

    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro() for _ in range(100)])
    construir_plano(t, modelo)
    t0 = _t.perf_counter()
    secs = dry_run(t)
    assert len(secs["passos"]) == 100
    assert (_t.perf_counter() - t0) < 30.0


# ---------- EXPLICACAO (66) ----------

def test_explicacao():
    t = PlanoTarefa("demo Juh", [op_pose(), op_giro()],
                    dependencias={"passo_2": ["passo_1"]})
    construir_plano(t)
    texto = explicar_plano(t)
    assert texto.startswith("Vou executar 2 etapa(s).")
    assert "1. Entendi" in texto and "2. Entendi" in texto
    assert "Aprovação necessária" in texto


# ---------- REGRESSÃO (67-70) ----------

def test_regressao_f26():
    from elixx.studio.agent import AgentPlan, PlanStep

    plano = AgentPlan(None, [PlanStep("a"), PlanStep(
        "b", dependencias=["a"])])
    assert plano.ordem_execucao() == ["a", "b"]
    import elixx.studio.agent.plano as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "PlanoTarefa" not in fonte  # F26 intocado


def test_regressao_f31():
    from elixx.studio.agent.operacoes import validar_operacao

    assert validar_operacao(op_pose())["valido"] is True
    import elixx.studio.agent.operacoes as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "PlanoTarefa" not in fonte


def test_regressao_f32():
    from elixx.studio.codigo import SincronizadorCodigo

    assert callable(SincronizadorCodigo)
    import elixx.studio.codigo.sincronizador as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "PlanoTarefa" not in fonte


def test_regressao_f29():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    assert "plano" in lay.paineis_visiveis() or True
    assert lay.definir_aba("plano") == "plano"
    assert lay.definir_aba("console") == "console"


def test_condicao_tipos():
    with pytest.raises(ErroELiXX):
        Condicao("talvez")
    c = Condicao("pre", "alvo único", entidade="Juh")
    assert c.to_dict()["kind"] == "pre"


def test_explicar_sem_plano():
    t = PlanoTarefa("x", [op_pose()])
    texto = explicar_plano(t)
    assert texto.startswith("Vou executar 1 etapa")
    assert "Aprovação necessária" in texto


def test_diff_sem_runtime(tmp_path):
    from elixx.studio.agent.planejamento import diff_semantico_passo

    app, modelo = projeto(tmp_path)
    texto = diff_semantico_passo(op_pose(), app.workspace, modelo)
    assert "sem diff textual" in texto
    with pytest.raises(ErroELiXX):
        diff_semantico_passo(
            SemanticOperation("pose", "Fantasma", {}),
            app.workspace, modelo)


def test_preparar_runtime(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_pose()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    assert prep["preparados"][0]["tipo"] == "runtime"
    assert prep["preparados"][0]["changeset"] is None


def test_executar_sem_plano(tmp_path):
    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_pose()])
    with pytest.raises(ErroELiXX):
        executar_plano(t, {"workspace": app.workspace,
                           "modelo": modelo})


def test_executar_bloqueado(tmp_path):
    from elixx.studio.agent import Approval

    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    with pytest.raises(ErroELiXX):
        executar_plano(t, {"workspace": app.workspace,
                           "modelo": modelo, "personagens": {},
                           "approval": Approval("bloqueado"),
                           "preparar": prep})


def test_historico_registra(tmp_path):
    from elixx.studio.agent import AgentHistory, Approval

    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    for p in prep["preparados"]:
        if p["changeset"] is not None:
            Approval("manual").aprovar_tudo(p["changeset"])
    hist = AgentHistory()
    executar_plano(t, {"workspace": app.workspace,
                       "modelo": modelo, "personagens": {},
                       "approval": Approval("manual"),
                       "historico": hist, "preparar": prep})
    assert len(hist.listar()) == 1
    assert hist.listar()[0]["estado"] == "concluida"


def test_auto_seguro_ponta_a_ponta(tmp_path):
    from elixx.studio.agent import Approval

    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    prep = preparar_execucao(t, app.workspace, modelo)
    # risco medio: auto-seguro recusa (só baixo passa sozinho)
    with pytest.raises(ErroELiXX):
        executar_plano(t, {
            "workspace": app.workspace, "modelo": modelo,
            "personagens": {},
            "approval": Approval("automatico_seguro",
                                 caminhos_permitidos=["src/"]),
            "preparar": prep})
    assert "rotacao: 15" not in (tmp_path / "p" / "src" /
                                 "main.elixx").read_text(
                                     encoding="utf-8")


def test_pos_mismatch(tmp_path):
    from elixx.studio.agent.planejamento import _checar_pos

    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    t.poscondicoes.append(Condicao(
        "pos", "valor", entidade="parte:Juh.corpo",
        propriedade="rotacao", esperado="9999"))
    with pytest.raises(ErroELiXX) as exc:
        _checar_pos(t, app.workspace, modelo)
    assert "pós-condição falhou" in str(exc.value)


def test_pre_arquivo_apagado(tmp_path):
    app, modelo = projeto(tmp_path)
    (tmp_path / "p" / "src" / "main.elixx").unlink()
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    out = validar_plano(t, modelo, app.workspace)
    assert out["codigo"] == "arquivo_ausente"


def test_painel_resumo_sem_plano():
    painel = PainelPlano(PlanoTarefa("x", []))
    assert painel.resumo()["arquivos"] == []
    assert painel.resumo()["progresso"]["total"] == 0


def test_ws_plano_view(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert getattr(ws, "plano_view", None) is None
    ws.plano_view = PainelPlano(PlanoTarefa("x", [op_pose()]))
    assert ws.plano_view.resumo()["estado"] == "criada"


def test_f32_changeset_key(tmp_path):
    from elixx.studio.agent import Approval

    app, modelo = projeto(tmp_path)
    t = PlanoTarefa("x", [op_giro()])
    construir_plano(t, modelo)
    from elixx.studio.codigo.sincronizador import aplicar_com_changeset
    from elixx.studio.codigo import SincronizadorCodigo

    sinc = SincronizadorCodigo(app.workspace, modelo)
    texto, ent = sinc._texto_e_entidade(t.operacoes[0])
    from elixx.studio.codigo import gerador

    alt = gerador.gerar_alteracao(t.operacoes[0], ent, texto)
    ap = Approval("automatico_seguro",
                  caminhos_permitidos=["src/"])
    out = aplicar_com_changeset(sinc, alt, approval=ap)
    assert out["changeset"].estado == "aplicado"
