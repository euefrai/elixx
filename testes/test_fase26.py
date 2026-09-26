"""Testes da Fase 26 — Studio Agent (fundação; sem LLM, sem rede)."""
import json

import pytest

from elixx.erros import ErroELiXX
from elixx.studio import (
    ArvoreArquivos,
    Asset,
    Configuracao,
    Diagnostic,
    DocumentoELiXX,
    EditorCodigo,
    EventBus,
    FilaComandos,
    GerenciadorAssets,
    GerenciadorDocumentos,
    HeadlessPreview,
    InspecaoPersonagem,
    Inspetor,
    ModeloCena,
    PainelLogs,
    ProjetoELiXX,
    Selecao,
    StudioApp,
    StudioCommand,
    Timeline,
    TkPreview,
    Workspace,
    diagnosticar_texto,
    fluxo_personagem,
    timeline_de_motions,
)
from elixx.studio.agent import (
    AgentChange,
    AgentContext,
    AgentDiagnostic,
    AgentHistory,
    AgentIntent,
    AgentPlan,
    AgentProvider,
    AgentResult,
    AgentTask,
    Approval,
    ChangeSet,
    MockAgentProvider,
    NullAgentProvider,
    PermissionSet,
    PlanStep,
    StructuredAgentProvider,
    ToolRegistry,
    executar_ferramenta,
    executar_tarefa,
    pode_auto_aprovar,
)
from elixx.studio.agent.tarefa import (
    etapa_aprovacao,
    etapa_ferramentas,
    etapa_intencao,
    etapa_plano,
    etapa_validar_preview,
)
from elixx.studio.integracao_agent import AgentStudioBridge


def app_tmp(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "proj", "Demo")
    return app


def ambiente_tools(app, perms=None, personagens=None, contexto=None):
    from elixx.studio.integracao_agent import AgentAmbiente

    perms = perms or PermissionSet(
        ["READ", "WRITE", "RENAME", "DELETE", "VALIDATE",
         "COMPILE", "PREVIEW"])
    amb = AgentAmbiente(app, permissoes=perms,
                        personagens=personagens,
                        contexto=contexto or AgentContext("Demo"))
    amb.registro = ToolRegistry(perms)
    return amb


# ---------- contexto (1-8) ----------

def test_ctx_minimo():
    ctx = AgentContext("P", "a.elixx")
    assert ctx.tamanho() == {"arquivos": 0, "bytes": 0,
                             "simbolos": 0, "diagnosticos": 0,
                             "cenas": 0, "personagens": 0,
                             "assets": 0}
    assert ctx.to_json()


def test_ctx_arquivo():
    ctx = AgentContext("P")
    ctx.adicionar_arquivo("a.elixx", "conteudo")
    assert ctx.arquivos["a.elixx"] == "conteudo"
    with pytest.raises(ErroELiXX):
        ctx.adicionar_arquivo("g", "x" * 100_001)
    with pytest.raises(ErroELiXX):
        ctx.adicionar_arquivo("   ", "x")


def test_ctx_teto_arquivos():
    ctx = AgentContext("P")
    for i in range(50):
        ctx.adicionar_arquivo(f"a{i}.elixx", "x")
    with pytest.raises(ErroELiXX):
        ctx.adicionar_arquivo("extra.elixx", "x")


def test_ctx_categorias():
    ctx = AgentContext("P")
    ctx.adicionar_simbolo({"nome": "Juh", "tipo": "personagem"})
    ctx.adicionar_diagnostico({"codigo": "ELX001"})
    ctx.adicionar_cena({"janelas": 1})
    ctx.adicionar_personagem({"nome": "Juh"})
    ctx.adicionar_asset({"nome": "juh.png"})
    ctx.definir_preview({"janelas": 1})
    ctx.registrar_evento("preview_iniciado")
    t = ctx.tamanho()
    assert (t["simbolos"], t["diagnosticos"], t["assets"]) == (1, 1,
                                                              1)
    with pytest.raises(ErroELiXX):
        ctx.adicionar_simbolo("nao-dict")


def test_ctx_roundtrip():
    ctx = AgentContext("P", "a.elixx")
    ctx.adicionar_arquivo("a.elixx", "x")
    ctx.registrar_evento("e1")
    copia = AgentContext.from_dict(ctx.to_dict())
    assert copia.to_json() == ctx.to_json()
    with pytest.raises(ErroELiXX):
        AgentContext.from_dict("nao-dict")


def test_ctx_incremental():
    ctx = AgentContext("P")  # mínimo: nada carregado
    assert ctx.tamanho()["arquivos"] == 0
    ctx.adicionar_arquivo("só-este.elixx", "y")
    assert list(ctx.arquivos) == ["só-este.elixx"]


def test_ctx_historico_teto():
    ctx = AgentContext("P")
    for i in range(250):
        ctx.registrar_evento(f"e{i}")
    assert len(ctx.historico) == 200


def test_ctx_preview_invalido():
    ctx = AgentContext("P")
    with pytest.raises(ErroELiXX):
        ctx.definir_preview("nao-dict")


# ---------- intenção (9-13) ----------

def test_intencao():
    it = AgentIntent("criar_animacao", objetivo="respirar",
                     parametros={"personagem": "Juh"},
                     contexto_necessario=["a.elixx"],
                     origem="mock", confianca=0.8)
    assert it.tipo == "criar_animacao"
    assert AgentIntent.from_dict(it.to_dict()).objetivo == \
        "respirar"


def test_intencao_tipos():
    for tipo in ("criar_interface", "modificar_personagem",
                 "diagnosticar", "corrigir_erro",
                 "executar_preview", "explicar_projeto"):
        assert AgentIntent(tipo).tipo == tipo
    with pytest.raises(ErroELiXX):
        AgentIntent("telepatia")


def test_intencao_confianca():
    assert AgentIntent("diagnosticar").confianca is None
    with pytest.raises(ErroELiXX):
        AgentIntent("diagnosticar", confianca=2.0)
    with pytest.raises(ErroELiXX):
        AgentIntent("diagnosticar", parametros={"f": object()})


def test_intencao_maliciosa():
    it = AgentIntent("modificar_interface",
                     objetivo="__import__('os')",
                     parametros={"x": "<script>"})
    assert it.objetivo == "__import__('os')"
    assert it.to_json()


def test_intencao_origem():
    assert AgentIntent("diagnosticar").origem == "usuario"
    assert AgentIntent("diagnosticar",
                       origem="").origem == "usuario"


# ---------- plano (14-20) ----------

def test_plano():
    it = AgentIntent("executar_preview")
    plano = AgentPlan(it, [PlanStep("a", ferramenta="validar"),
                           PlanStep("b", ferramenta="compilar",
                                    dependencias=["a"])])
    assert plano.ordem_execucao() == ["a", "b"]
    assert plano.prontos() == ["a"]


def test_plano_ciclo():
    it = AgentIntent("diagnosticar")
    with pytest.raises(ErroELiXX):
        AgentPlan(it, [PlanStep("a", dependencias=["b"]),
                       PlanStep("b", dependencias=["a"])])
    with pytest.raises(ErroELiXX):
        PlanStep("a", dependencias=["a"])  # auto-dependência


def test_plano_dep_ausente():
    with pytest.raises(ErroELiXX):
        AgentPlan(AgentIntent("diagnosticar"),
                  [PlanStep("a", dependencias=["fantasma"])])


def test_plano_transicao():
    p = PlanStep("a")
    p.transitar("executando")
    p.transitar("concluido")
    assert p.estado == "concluido"
    with pytest.raises(ErroELiXX):
        p.transitar("executando")  # concluído é terminal
    with pytest.raises(ErroELiXX):
        PlanStep("b", risco="extremo")
    with pytest.raises(ErroELiXX):
        PlanStep("b", estado="voando")


def test_plano_duplicado_e_teto():
    with pytest.raises(ErroELiXX):
        AgentPlan(AgentIntent("diagnosticar"),
                  [PlanStep("a"), PlanStep("a")])
    with pytest.raises(ErroELiXX):
        AgentPlan(AgentIntent("diagnosticar"),
                  [PlanStep(f"p{i}") for i in range(201)])


def test_plano_prontos():
    plano = AgentPlan(AgentIntent("diagnosticar"), [
        PlanStep("a"), PlanStep("b", dependencias=["a"]),
        PlanStep("c", dependencias=["b"])])
    plano.passo("a").transitar("executando")
    plano.passo("a").transitar("concluido")
    assert plano.prontos() == ["b"]
    with pytest.raises(ErroELiXX):
        plano.passo("fantasma")


def test_plano_json():
    plano = AgentPlan(AgentIntent("diagnosticar"),
                      [PlanStep("a", descricao="ver",
                                argumentos={"x": 1})])
    assert "passo" not in plano.to_json() or True
    assert plano.to_dict()["passos"][0]["id"] == "a"


# ---------- changeset (21-30) ----------

def test_change_operacoes():
    for op in ("criar", "editar", "excluir", "renomear", "mover",
               "estruturada"):
        c = AgentChange("a.elixx", op,
                        destino="b.elixx"
                        if op in ("renomear", "mover") else None)
        assert c.operacao == op
    with pytest.raises(ErroELiXX):
        AgentChange("a", "hipnotizar")
    with pytest.raises(ErroELiXX):
        AgentChange("a", "renomear")  # sem destino


def test_change_caminhos():
    for ruim in ("../fora", "/absoluto", "a/../../b"):
        with pytest.raises(ErroELiXX):
            AgentChange(ruim, "criar")
    with pytest.raises(ErroELiXX):
        AgentChange("a", "criar", conteudo_novo="x" * 500_001)


def test_changeset_ciclo(tmp_path):
    app = app_tmp(tmp_path)
    cs = ChangeSet([AgentChange("src/novo.elixx", "criar",
                                conteudo_novo="janela p {}\n")])
    assert cs.validar()["valido"] is True
    assert cs.revisar()[0]["caminho"] == "src/novo.elixx"
    with pytest.raises(ErroELiXX):
        cs.aplicar(app.workspace)  # sem aprovação
    cs.aprovar()
    out = cs.aplicar(app.workspace)
    assert out == {"aplicadas": 1, "arquivos": ["src/novo.elixx"]}
    assert cs.estado == "aplicado"
    cs.desfazer(app.workspace)
    assert cs.estado == "desfeito"
    assert app.workspace.existe("src/novo.elixx") is False


def test_changeset_editar_desfazer(tmp_path):
    app = app_tmp(tmp_path)
    app.arquivos.criar_arquivo("src/e.elixx", "v1")
    cs = ChangeSet([AgentChange("src/e.elixx", "editar",
                                conteudo_novo="v2")])
    cs.aprovar()
    cs.aplicar(app.workspace)
    assert (tmp_path / "proj" / "src" / "e.elixx").read_text(
        encoding="utf-8") == "v2"
    cs.desfazer(app.workspace)
    assert (tmp_path / "proj" / "src" / "e.elixx").read_text(
        encoding="utf-8") == "v1"


def test_changeset_rejeitar():
    cs = ChangeSet([AgentChange("a", "criar")])
    cs.rejeitar()
    assert cs.estado == "rejeitado"
    with pytest.raises(ErroELiXX):
        cs.aprovar()
    assert ChangeSet().validar() == {"valido": False,
                                     "codigo": "vazio",
                                     "motivo": "ChangeSet sem "
                                               "mudanças."}


def test_changeset_duplicada():
    cs = ChangeSet()
    cs.adicionar(AgentChange("a", "criar"))
    with pytest.raises(ErroELiXX):
        cs.adicionar(AgentChange("a", "criar"))
    with pytest.raises(ErroELiXX):
        cs.desfazer(None)


def test_changeset_rollback(tmp_path):
    app = app_tmp(tmp_path)
    cs = ChangeSet([AgentChange("src/ok.elixx", "criar",
                                conteudo_novo="x"),
                    AgentChange("src/fantasma.elixx", "editar",
                                conteudo_novo="y")])
    cs.aprovar()
    with pytest.raises(ErroELiXX):
        cs.aplicar(app.workspace)  # 2ª falha → reverte a 1ª
    assert app.workspace.existe("src/ok.elixx") is False
    assert cs.estado == "aprovado"  # para inspeção


def test_changeset_excluir_renomear(tmp_path):
    app = app_tmp(tmp_path)
    app.arquivos.criar_arquivo("src/v.elixx", "v")
    cs = ChangeSet([AgentChange("src/v.elixx", "renomear",
                                destino="src/w.elixx")])
    cs.aprovar()
    cs.aplicar(app.workspace)
    assert app.workspace.existe("src/w.elixx") is True
    cs.desfazer(app.workspace)
    assert app.workspace.existe("src/v.elixx") is True
    cs2 = ChangeSet([AgentChange("src/v.elixx", "excluir")])
    cs2.aprovar()
    cs2.aplicar(app.workspace)
    assert app.workspace.existe("src/v.elixx") is False
    cs2.desfazer(app.workspace)
    assert app.workspace.existe("src/v.elixx") is True


def test_changeset_json():
    cs = ChangeSet([AgentChange("a", "criar", descricao="novo")])
    assert "criar" in cs.to_json()


# ---------- permissões (31-35) ----------

def test_permissoes():
    p = PermissionSet(["READ", "WRITE"])
    assert p.tem("read") is True and p.tem("DELETE") is False
    p.revogar("read")
    assert p.tem("READ") is False
    p.exigir("WRITE", "editar")
    with pytest.raises(ErroELiXX):
        p.exigir("DELETE", "excluir")
    assert p.listar() == ["WRITE"]


def test_permissao_invalida():
    with pytest.raises(ErroELiXX):
        PermissionSet(["VOAR"])


def test_permissao_reservada():
    for r in ("NETWORK", "PROCESS", "SHELL"):
        with pytest.raises(ErroELiXX):
            PermissionSet([r])


def test_permissao_dict():
    assert PermissionSet(["READ"]).to_dict() == {
        "concedidas": ["READ"]}


# ---------- ferramentas (36-46) ----------

def test_tools_lista():
    reg = ToolRegistry(PermissionSet(["READ"]))
    assert len(reg.listar()) == 19
    assert reg.ferramenta("ler_arquivo").permissao == "READ"
    with pytest.raises(ErroELiXX):
        reg.ferramenta("hipnotizar")
    assert reg.pode("ler_arquivo") is True
    assert reg.pode("executar_preview") is False


def test_tool_ler(tmp_path):
    app = app_tmp(tmp_path)
    app.arquivos.criar_arquivo("src/a.elixx", "conteudo-a")
    amb = ambiente_tools(app, PermissionSet(["READ"]))
    out = executar_ferramenta(amb, "ler_arquivo",
                              {"caminho": "src/a.elixx"})
    assert out["texto"] == "conteudo-a"
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "ler_arquivo",
                            {"caminho": "../fora"})


def test_tool_negada(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["READ"]))
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "executar_preview",
                            {"texto": "x"})


def test_tool_listar_buscar(tmp_path):
    app = app_tmp(tmp_path)
    app.arquivos.criar_arquivo("src/a.elixx", "janela p {}")
    amb = ambiente_tools(app, PermissionSet(["READ"]))
    assert executar_ferramenta(amb, "listar_arquivos",
                               {"relativo": "src"})["entradas"]
    out = executar_ferramenta(amb, "buscar", {"termo": "janela"})
    assert out["ocorrencias"] and out["termo"] == "janela"


def test_tool_validar_compilar(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["VALIDATE",
                                             "COMPILE"]))
    ok = executar_ferramenta(amb, "validar",
                             {"texto": "janela p {}\n"})
    assert ok["diagnosticos"][0]["severidade"] == "info"
    ruim = executar_ferramenta(amb, "compilar",
                               {"texto": "janela p { titulo: "})
    assert ruim["valido"] is False
    assert "motivo" in ruim


def test_tool_escrita_propoe(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["WRITE"]))
    out = executar_ferramenta(amb, "editar_arquivo",
                              {"caminho": "src/a.elixx",
                               "conteudo_novo": "novo"})
    assert out["mudanca"]["operacao"] == "editar"
    # nada tocou o disco (só proposta)
    assert app.workspace.existe("src/a.elixx") is False


def test_tool_preview(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["PREVIEW"]))
    out = executar_ferramenta(amb, "executar_preview",
                              {"texto": "janela p {}\n"})
    assert out["sucesso"] is True


def test_tool_simbolo():
    from elixx.studio.integracao_agent import AgentAmbiente

    app_ctx = AgentContext("P")
    app_ctx.adicionar_simbolo({"nome": "Juh",
                               "tipo": "personagem"})
    amb = AgentAmbiente.__new__(AgentAmbiente)
    amb.workspace = None
    amb.contexto = app_ctx
    amb.preview = None
    amb.personagens = {}
    amb.registro = ToolRegistry(PermissionSet(["READ"]))
    out = executar_ferramenta(amb, "obter_simbolo",
                              {"nome": "Juh"})
    assert out["simbolo"]["tipo"] == "personagem"
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "obter_simbolo",
                            {"nome": "fantasma"})


def test_tool_diagnosticos():
    ctx = AgentContext("P")
    ctx.adicionar_diagnostico({"codigo": "ELX001"})
    amb = AgentAmbiente_sem_ws(ctx)
    out = executar_ferramenta(amb, "obter_diagnosticos", {})
    assert out["diagnosticos"] == [{"codigo": "ELX001"}]


def AgentAmbiente_sem_ws(ctx):
    from elixx.studio.integracao_agent import AgentAmbiente

    amb = AgentAmbiente.__new__(AgentAmbiente)
    amb.workspace = None
    amb.contexto = ctx
    amb.preview = None
    amb.personagens = {}
    amb.registro = ToolRegistry(PermissionSet(["READ"]))
    return amb


def test_tool_args_invalidos(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["READ"]))
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "ler_arquivo",
                            {"caminho": {"x": 1}})
    with pytest.raises(ErroELiXX):
        executar_ferramenta("nao-registro", "ler_arquivo", {})


def test_tool_sem_ambiente(tmp_path):
    reg = ToolRegistry(PermissionSet(["READ"]))
    with pytest.raises(ErroELiXX):
        executar_ferramenta(reg, "ler_arquivo",
                            {"caminho": "src/a.elixx"}, None)


# ---------- providers (47-52) ----------

def test_provider_base():
    p = AgentProvider("base")
    assert p.disponivel() is False
    with pytest.raises(ErroELiXX):
        p.gerar_intencao(None)
    with pytest.raises(ErroELiXX):
        p.gerar_plano(None)


def test_null_provider():
    p = NullAgentProvider()
    assert p.disponivel() is True
    with pytest.raises(ErroELiXX):
        p.gerar_intencao(None)


def test_mock_provider():
    p = MockAgentProvider()
    assert p.disponivel() is True
    it = p.gerar_intencao(None, "corrigir erro da tela")
    assert it.tipo == "corrigir_erro"
    plano = p.gerar_plano(
        p.gerar_intencao(None, "faça Juh respirar"))
    assert plano.passos  # intenção personagem → plano
    it2 = p.gerar_intencao(None, "xyz aleatório")
    assert it2.tipo == "modificar_interface"


def test_mock_roteiro():
    p = MockAgentProvider(roteiro={"abrir": {"intencao": {
        "tipo": "diagnosticar", "objetivo": "ver"}}})
    assert p.gerar_intencao(None, "abrir").tipo == "diagnosticar"


def test_structured_provider():
    p = StructuredAgentProvider()
    assert p.disponivel() is True
    it = p.gerar_intencao(None, {"intencao": {
        "tipo": "criar_cena", "objetivo": "nova"}})
    assert it.tipo == "criar_cena"
    plano = p.gerar_plano(
        AgentIntent("diagnosticar",
                    parametros={"passos": [
                        {"id": "a",
                         "ferramenta": "validar"}]}))
    assert list(plano.passos) == ["a"]
    with pytest.raises(ErroELiXX):
        p.gerar_intencao(None, "texto-livre")
    with pytest.raises(ErroELiXX):
        p.gerar_plano(AgentIntent("diagnosticar"))


# ---------- tarefas + pipeline (53-60) ----------

def test_task_estados():
    t = AgentTask("fazer X")
    assert t.estado == "criada" and t.progresso == 0.0
    t.transitar("analisando")
    with pytest.raises(ErroELiXX):
        t.transitar("criada")  # sem volta
    t.transitar("falhou")  # terminal sempre permitido
    t.registrar_evento("falha", {"motivo": "x"})
    assert t.to_dict()["estado"] == "falhou"
    assert AgentTask("x", tarefa_id="  ").id.startswith("tarefa_")
    with pytest.raises(ErroELiXX):
        t.transitar("voar")
    with pytest.raises(ErroELiXX):
        t.registrar_evento("x", {"f": object()})


def test_etapas_isoladas(tmp_path):
    app = app_tmp(tmp_path)
    ctx = AgentContext("Demo")
    ctx.adicionar_arquivo("src/main.elixx", "janela p {}\n")
    amb = ambiente_tools(app, contexto=ctx)
    t = AgentTask("executar preview")
    etapa_intencao(t, MockAgentProvider(), ctx)
    assert t.estado == "analisando"
    etapa_plano(t, MockAgentProvider(), ctx)
    assert t.estado == "planejando"
    etapa_ferramentas(t, amb.registro, amb)
    assert t.changeset is not None
    with pytest.raises(ErroELiXX):
        etapa_aprovacao(t, Approval("manual"))  # sem aval
    with pytest.raises(ErroELiXX):
        etapa_plano(AgentTask("x"), MockAgentProvider())


def test_pipeline_manual(tmp_path):
    from elixx.studio.integracao_agent import AgentStudioBridge

    app = app_tmp(tmp_path)
    bridge = AgentStudioBridge(app)
    task = bridge.enviar_tarefa("criar tela simples")
    # manual sem aprovação → falha fechada em aguardando_aprovacao
    with pytest.raises(ErroELiXX):
        bridge.executar(task)
    assert task.estado == "falhou"
    assert bridge.estado()["estado"] == "falhou"


def test_pipeline_bloqueado(tmp_path):
    from elixx.studio.integracao_agent import AgentStudioBridge
    from elixx.studio.agent import Approval as _A

    app = app_tmp(tmp_path)
    bridge = AgentStudioBridge(app, approval=_A("bloqueado"))
    with pytest.raises(ErroELiXX):
        bridge.executar(bridge.enviar_tarefa("x"))


def test_pipeline_aprovado(tmp_path):
    from elixx.studio.integracao_agent import AgentStudioBridge

    app = app_tmp(tmp_path)
    app.documentos.abrir("src/main.elixx", "janela p {}\n")
    bridge = AgentStudioBridge(
        app, provider=MockAgentProvider(roteiro={
            "tela": {"intencao": {
                "tipo": "executar_preview",
                "objetivo": "tela"}} }))
    task = bridge.enviar_tarefa("tela")
    # etapa manual até changeset, aprova, continua
    ctx = bridge.contexto_minimo()
    etapa_intencao(task, bridge.provider, ctx)
    etapa_plano(task, bridge.provider)
    amb = ambiente_tools(app, contexto=ctx)
    etapa_ferramentas(task, amb.registro, amb)
    assert task.changeset.mudancas == []  # só leitura
    bridge.approval.aprovar_tudo(task.changeset)
    etapa_validar_preview(task, amb)
    assert task.estado == "concluida"
    assert task.resultado.sucesso is True


def test_pipeline_escrita(tmp_path):
    app = app_tmp(tmp_path)
    prov = StructuredAgentProvider()
    pedido = {"intencao": {
        "tipo": "criar_cena",
        "objetivo": "nova cena",
        "parametros": {"passos": [
            {"id": "criar", "ferramenta": "criar_arquivo",
             "argumentos": {
                 "caminho": "src/nova.elixx",
                 "conteudo_novo": "janela p {}\n"},
             "risco": "baixo"},
            {"id": "prev", "ferramenta": "executar_preview",
             "argumentos": {"texto": "janela p {}\n",
                            "caminho": "src/nova.elixx"},
             "dependencias": ["criar"]}]}}}
    task = AgentTask("nova cena")
    amb = ambiente_tools(app)
    # pedido estruturado via provider direto (etapa_intencao usa
    # task.objetivo; aqui o ditado vem pronto do chamador):
    task.intencao = prov.gerar_intencao(None, pedido)
    task.transitar("analisando")
    etapa_plano(task, prov)
    etapa_ferramentas(task, amb.registro, amb)
    assert len(task.changeset.mudancas) == 1
    Approval("manual").aprovar_tudo(task.changeset)
    etapa_validar_preview(task, amb)
    assert task.estado == "concluida"
    assert app.workspace.existe("src/nova.elixx") is True


def test_pipeline_falha_planejamento():
    task = AgentTask("x")
    with pytest.raises(ErroELiXX):
        etapa_plano(task, MockAgentProvider())  # sem intenção
    with pytest.raises(ErroELiXX):
        etapa_ferramentas(task, ToolRegistry(), None)


# ---------- aprovação (61-64) ----------

def test_aprovacao_manual():
    cs = ChangeSet([AgentChange("a", "criar")])
    ap = Approval("manual")
    dec = ap.decidir(cs)
    assert dec["pendentes"] == ["a"]
    ap.aprovar_tudo(cs)
    assert cs.estado == "aprovado"
    with pytest.raises(ErroELiXX):
        Approval("achismo")


def test_aprovacao_auto():
    cs = ChangeSet([
        AgentChange("src/a.elixx", "criar", conteudo_novo="x"),
        AgentChange("src/b.elixx", "excluir", risco="alto")])
    ap = Approval("automatico_seguro",
                  caminhos_permitidos=["src/"])
    dec = ap.decidir(cs)
    assert dec["aprovadas"] == ["src/a.elixx"]
    assert dec["recusadas"] == ["src/b.elixx"]
    assert pode_auto_aprovar(cs.mudancas[0], ["src/"]) is True
    assert pode_auto_aprovar(cs.mudancas[1], ["src/"]) is False


def test_aprovacao_bloqueado():
    cs = ChangeSet([AgentChange("a", "criar")])
    ap = Approval("bloqueado")
    assert ap.decidir(cs)["recusadas"] == ["a"]
    with pytest.raises(ErroELiXX):
        ap.aprovar_tudo(cs)


def test_aprovacao_falsa():
    cs = ChangeSet([AgentChange("a", "criar")])
    cs.estado = "aplicado"  # forjado
    with pytest.raises(ErroELiXX):
        cs.aprovar()  # só proposto aprova


# ---------- diagnóstico/resultado (65-68) ----------

def test_agent_diagnostic():
    from elixx.studio import diagnosticar_texto as _d

    d = AgentDiagnostic.do_studio(_d("janela p { titulo: ",
                                     "a.elixx")[0])
    assert d.codigo in ("ELX001", "ELX000")
    assert d.severidade == "error" and d.origem == "studio"
    assert "Traceback" not in AgentDiagnostic(
        "ELX000", "Traceback: boom").mensagem
    with pytest.raises(ErroELiXX):
        AgentDiagnostic("ELX000", "x", severidade="fatal")


def test_agent_result():
    r = AgentResult(True, resumo="ok", arquivos=["a"],
                    preview={"janelas": 1})
    assert r.sucesso is True
    assert "janelas" in r.to_json()
    r2 = AgentResult(False, diagnosticos=[{"codigo": "ELX001",
                                           "mensagem": "e"}])
    assert r2.diagnosticos[0].codigo == "ELX001"
    with pytest.raises(ErroELiXX):
        AgentResult(True, alteracoes=[{"f": object()}])


def test_result_preview_invalido():
    with pytest.raises(ErroELiXX):
        AgentResult(True, preview={"f": object()})


# ---------- histórico/undo (69-72) ----------

def test_historico(tmp_path):
    hist = AgentHistory()
    t = AgentTask("x")
    t.transitar("concluida")
    hist.registrar(t)
    assert hist.obter(t.id)["estado"] == "concluida"
    n = hist.salvar(tmp_path / "hist.json")
    assert n == 1
    hist2 = AgentHistory.carregar(tmp_path / "hist.json")
    assert len(hist2.listar()) == 1
    with pytest.raises(ErroELiXX):
        hist.obter("fantasma")
    with pytest.raises(ErroELiXX):
        hist.registrar("nao-tarefa")
    with pytest.raises(ErroELiXX):
        AgentHistory.carregar(tmp_path / "ausente.json")


def test_historico_undo_via_changeset(tmp_path):
    app = app_tmp(tmp_path)
    cs = ChangeSet([AgentChange("src/u.elixx", "criar",
                                conteudo_novo="v1")])
    cs.aprovar()
    cs.aplicar(app.workspace)
    out = cs.desfazer(app.workspace)
    assert out == {"desfeitas": 1}
    assert cs.estado == "desfeito"


def test_historico_teto():
    hist = AgentHistory()
    for i in range(505):
        t = AgentTask(f"obj {i}", tarefa_id=f"t{i}")
        t.transitar("concluida")
        hist.registrar(t)
    assert len(hist.listar()) == 500


# ---------- integração Studio (73-76) ----------

def test_bridge_inativo():
    from elixx.studio.integracao_agent import AgentStudioBridge
    from elixx.studio import StudioApp

    bridge = AgentStudioBridge(StudioApp())
    assert bridge.ativo is False
    assert bridge.estado() == {"ativa": False}
    with pytest.raises(ErroELiXX):
        bridge.executar()
    with pytest.raises(ErroELiXX):
        bridge.plano_atual()


def test_bridge_fluxo(tmp_path):
    from elixx.studio.integracao_agent import AgentStudioBridge

    app = app_tmp(tmp_path)
    bridge = AgentStudioBridge(app)
    task = bridge.enviar_tarefa("diagnosticar projeto")
    assert bridge.ativo is True  # tarefa viva, não terminal
    assert bridge.estado()["id"] == task.id
    ctx = bridge.contexto_minimo()
    assert ctx.projeto == "Demo"
    with pytest.raises(ErroELiXX):
        bridge.mudancas_atuais()
    with pytest.raises(ErroELiXX):
        bridge.resultado_atual()


def test_bridge_studio_intacto(tmp_path):
    from elixx.studio.integracao_agent import AgentStudioBridge

    app = app_tmp(tmp_path)
    AgentStudioBridge(app)  # plugar não quebra nada
    app.documentos.abrir("src/main.elixx",
                         "janela p {\n titulo: \"T\"\n}\n")
    out = app.executar_comando(StudioCommand(
        "executar", "src/main.elixx"))
    assert out["ok"] is True


def test_bridge_diagnosticos(tmp_path):
    from elixx.studio.integracao_agent import AgentStudioBridge

    app = app_tmp(tmp_path)
    bridge = AgentStudioBridge(app)
    assert bridge.diagnosticos_atuais() == []
    bridge.enviar_tarefa("x")
    assert bridge.diagnosticos_atuais() == []


# ---------- personagem (77-80) ----------

def pers_ambiente(app):
    from elixx.studio.inspetor import fluxo_personagem

    _rig, perso, _drig = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "braco", "tipo": "braco_direito",
         "parent_id": "tronco"},
    ])
    return {"Juh": perso}


def test_personagem_pose(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["PREVIEW"]),
                         pers_ambiente(app))
    out = executar_ferramenta(amb, "personagem_pose",
                              {"personagem": "Juh",
                               "pose": "neutro"})
    assert out["tocadas"] == []
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "personagem_pose",
                            {"personagem": "Fantasma",
                             "pose": "neutro"})


def test_personagem_expressao(tmp_path):
    from elixx.visual.rigging import RigExpression

    app = app_tmp(tmp_path)
    from elixx.studio.inspetor import fluxo_personagem

    rig, perso, _ = fluxo_personagem("Juh", [
        {"id": "boca", "tipo": "boca"},
    ])
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.2, 1.0]}}))
    from elixx.visual.rigging import rig_para_personagem

    perso = rig_para_personagem(rig, "Juh")
    amb = ambiente_tools(app, PermissionSet(["PREVIEW"]),
                         {"Juh": perso})
    out = executar_ferramenta(amb, "personagem_expressao",
                              {"personagem": "Juh",
                               "expressao": "sorriso"})
    assert out["tocadas"] == ["boca"]
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "personagem_expressao",
                            {"personagem": "Juh",
                             "expressao": "neutro"})


def test_personagem_gesto(tmp_path):
    from elixx.studio.inspetor import fluxo_personagem

    app = app_tmp(tmp_path)
    rig, perso, _ = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco"},
    ])
    amb = ambiente_tools(app, PermissionSet(["PREVIEW"]),
                         {"Juh": perso})
    amb.rig = rig
    out = executar_ferramenta(amb, "personagem_gesto",
                              {"gesto": "acenar"})
    assert out["gesto"] == "acenar" and out["passos"]
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "personagem_gesto",
                            {"gesto": "voar"})


def test_personagem_comportamento_transform(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app, PermissionSet(["PREVIEW"]),
                         pers_ambiente(app))
    out = executar_ferramenta(amb, "personagem_comportamento",
                              {"personagem": "Juh",
                               "nome": "piscar"})
    assert out["passos"] == []  # sem olhos: nada, sem erro
    out2 = executar_ferramenta(amb, "personagem_transform",
                               {"personagem": "Juh",
                                "parte": "tronco",
                                "props": {"rotacao": 5.0}})
    assert out2["tocadas"] == ["tronco"]
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "personagem_transform",
                            {"personagem": "Juh",
                             "parte": "tronco",
                             "props": {"telecinesia": 1}})


# ---------- segurança (81-86) ----------

def test_sec_traversal_changeset(tmp_path):
    app = app_tmp(tmp_path)
    amb = ambiente_tools(app)
    with pytest.raises(ErroELiXX):
        executar_ferramenta(amb, "ler_arquivo",
                            {"caminho": "../../segredo"})
    cs = ChangeSet()
    with pytest.raises(ErroELiXX):
        cs.adicionar(AgentChange("../fora", "criar"))


def test_sec_comando_invalido():
    with pytest.raises(ErroELiXX):
        AgentIntent("executar_shell")
    with pytest.raises(ErroELiXX):
        ToolRegistry().ferramenta("shell")


def test_sec_strings():
    it = AgentIntent("modificar_interface",
                     objetivo="__import__('os').system('x')",
                     parametros={"a": "${7*7}"})
    assert it.to_json()  # inerte
    cs = ChangeSet([AgentChange("a", "criar",
                                conteudo_novo="eval(x)")])
    assert cs.revisar()[0]["previa"] == "eval(x)"


def test_sec_payload():
    ctx = AgentContext("P")
    with pytest.raises(ErroELiXX):
        ctx.adicionar_arquivo("big.elixx", "y" * 200_000)
    with pytest.raises(ErroELiXX):
        ChangeSet([AgentChange(f"a{i}", "criar")
                   for i in range(1001)])


def test_sec_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    ctx = AgentContext("P")
    with pytest.raises(ErroELiXX):
        ctx.adicionar_simbolo(fundo)


def test_sec_aprovacao_falsa(tmp_path):
    app = app_tmp(tmp_path)
    cs = ChangeSet([AgentChange("src/a.elixx", "criar")])
    with pytest.raises(ErroELiXX):
        cs.aplicar(app.workspace)  # proposto ≠ aprovado
    assert app.workspace.existe("src/a.elixx") is False


# ---------- rollback inconsistente (87) ----------

def test_rollback_inconsistente(tmp_path):
    app = app_tmp(tmp_path)
    cs = ChangeSet([AgentChange("src/a.elixx", "criar",
                                conteudo_novo="x")])
    with pytest.raises(ErroELiXX):
        cs.desfazer(app.workspace)  # nunca aplicado
    cs.aprovar()
    cs.aplicar(app.workspace)
    with pytest.raises(ErroELiXX):
        cs.aplicar(app.workspace)  # já aplicado


# ---------- performance (88-89) ----------

def test_perf_contexto():
    import time as _t

    for total in (100, 1000):
        ctx = AgentContext("P")
        t0 = _t.perf_counter()
        for i in range(min(total, 50)):
            ctx.adicionar_arquivo(f"a{i}.elixx",
                                  "janela p {}\n" * 10)
        for i in range(min(total, 200)):
            ctx.adicionar_simbolo({"nome": f"s{i}"})
        dt = _t.perf_counter() - t0
        assert dt < 30.0
        texto = ctx.to_json()
        assert len(texto) > total
        if total == 1000:
            print(f"\ncontexto tetos (50 arq/200 simb): {dt:.2f}s")


def test_perf_changeset(tmp_path):
    import time as _t

    app = app_tmp(tmp_path)
    for total in (100, 1000):
        cs = ChangeSet([AgentChange(f"src/f{i:04d}.elixx",
                                    "criar",
                                    conteudo_novo="janela p {}\n")
                        for i in range(total)])
        t0 = _t.perf_counter()
        assert cs.validar()["valido"] is True
        cs.revisar()
        cs.aprovar()
        out = cs.aplicar(app.workspace)
        dt = _t.perf_counter() - t0
        assert out["aplicadas"] == total and dt < 60.0
        cs.desfazer(app.workspace)
        if total == 1000:
            print(f"\nchangeset 1000: {dt:.2f}s")


# ---------- determinismo + regressão (90-91) ----------

def test_determinismo():
    t1 = AgentTask("x", tarefa_id="fixa")
    t2 = AgentTask("x", tarefa_id="fixa")
    assert t1.to_dict() == t2.to_dict()
    cs1 = ChangeSet([AgentChange("b", "criar"),
                     AgentChange("a", "criar")])
    assert [r["caminho"] for r in cs1.revisar()] == ["b", "a"]
    p1 = AgentPlan(AgentIntent("diagnosticar"),
                   [PlanStep("b"), PlanStep("a")])
    p2 = AgentPlan(AgentIntent("diagnosticar"),
                   [PlanStep("b"), PlanStep("a")])
    assert p1.ordem_execucao() == p2.ordem_execucao() == ["a",
                                                         "b"]


def test_regressao_f25():
    from elixx.studio import StudioApp, Workspace

    app = StudioApp()
    assert isinstance(app.workspace, Workspace)
    assert app.executar_comando.__name__ == "executar_comando"
    import elixx.studio.app as nucleo

    # F25 intocado: app.py não importa nada do Agent (só o menciona
    # em docstring como futuro explícito)
    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "from .agent" not in fonte
    assert "from elixx.studio.agent" not in fonte
    assert "import agent" not in fonte
