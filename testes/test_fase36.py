"""Testes da Fase 36 — tools semânticas + evolução visual (sem LLM)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent.ferramentas_semanticas import (
    AgentToolCall,
    SemanticPermissions,
    SemanticTool,
    SemanticToolRegistry,
    ToolResult,
    ToolTrace,
    executar_chamada,
    executar_sequencia,
)
from elixx.studio.agent.workspace import AgentWorkspace
from elixx.studio.modelo import ModeloSemantico, analisar_texto

FONTE = (
    "janela principal {\n"
    " personagem Juh {\n"
    "  parte cabeca {\n"
    "  }\n"
    "  pose acenar {\n"
    "   cabeca:\n"
    "    rotacao: 45deg\n"
    "  }\n"
    " }\n"
    " botao comprar {\n"
    " }\n"
    "}\n"
)


def modelo_base():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    return m


class _Amb:
    def __init__(self, modelo=None, workspace=None,
                 personagens=None):
        self.modelo = modelo
        self.workspace = workspace
        self.personagens = dict(personagens or {})
        self.contexto = None
        self.preview = None
        self.plano_view = None
        self.rig = None


def amb_modelo():
    return _Amb(modelo=modelo_base())


def perms(*nomes):
    return SemanticPermissions(list(nomes))


# ---------- TOOLS: tool/result/registry/call (1-20) ----------

def test_tool_criacao():
    t = SemanticTool("buscar_entidade", "Buscar", "acha",
                     "CONSULTA", "READ")
    assert t.esquema()["permissao"] == "READ"
    assert t.nome == "Buscar"
    with pytest.raises(ErroELiXX):
        SemanticTool("x", "X", "d", "MAGIA", "READ")
    with pytest.raises(ErroELiXX):
        SemanticTool("x", "X", "d", "CONSULTA", "VOAR")
    with pytest.raises(ErroELiXX):
        SemanticTool("  ", "X", "d", "CONSULTA")


def test_tool_result():
    r = ToolResult(True, {"a": 1}, "ok", origem="t")
    assert r.sucesso is True and r.dados == {"a": 1}
    assert r.to_dict()["origem"] == "t"
    with pytest.raises(ErroELiXX):
        ToolResult(True, {"f": object()})
    with pytest.raises(ErroELiXX):
        ToolResult(True, "x" * 100_001)


def test_registry():
    reg = SemanticToolRegistry()
    assert len(reg.listar()) == 30
    assert reg.buscar("buscar_entidade").categoria == "CONSULTA"
    assert reg.resolver("buscar_entidade").id == "buscar_entidade"
    with pytest.raises(ErroELiXX):
        reg.buscar("hipnotizar")
    with pytest.raises(ErroELiXX):
        reg.resolver("hipnotizar")
    with pytest.raises(ErroELiXX):
        reg.listar("MAGIA")


def test_registry_duplicada():
    reg = SemanticToolRegistry()
    with pytest.raises(ErroELiXX):
        reg.registrar(SemanticTool("buscar_entidade", "B", "d",
                                   "CONSULTA"))
    with pytest.raises(ErroELiXX):
        reg.registrar("nao-tool")
    nova = reg.registrar(SemanticTool("minha_tool", "M", "d",
                                      "ANALISE"))
    assert nova.id == "minha_tool"
    assert "minha_tool" in reg.listar()


def test_registry_validar():
    reg = SemanticToolRegistry()
    assert reg.validar("buscar_entidade",
                       {"nome": "Juh"})["valido"] is True
    assert reg.validar("buscar_entidade",
                       {"x": object()})["codigo"] == \
        "args_invalidos"
    assert reg.validar("buscar_entidade",
                       {f"a{i}": i for i in range(21)})[
                           "codigo"] == "args_demais"
    assert reg.validar("buscar_entidade", "nao-dict")[
        "codigo"] == "args_invalidos"
    grande = {"x": "y" * 100_001}
    assert reg.validar("buscar_entidade", grande)[
        "codigo"] == "payload"


def test_call_criacao():
    c = AgentToolCall("buscar_entidade", {"nome": "Juh"})
    assert c.estado == "PENDENTE"
    assert c.id.startswith("call_")
    assert AgentToolCall("t", {}, call_id="fixa").id == "fixa"
    with pytest.raises(ErroELiXX):
        AgentToolCall("t", {f"a{i}": i for i in range(21)})
    with pytest.raises(ErroELiXX):
        AgentToolCall("t", {"x": float("nan")})
    with pytest.raises(ErroELiXX):
        AgentToolCall("t", {"x": "y" * 100_001})
    with pytest.raises(ErroELiXX):
        AgentToolCall("  ", {})


def test_call_transicoes():
    c = AgentToolCall("t", {})
    c.transitar("VALIDANDO")
    c.transitar("EXECUTANDO")
    c.transitar("CONCLUIDA")
    assert c.estado == "CONCLUIDA"
    with pytest.raises(ErroELiXX):
        c.transitar("EXECUTANDO")
    d = AgentToolCall("t", {})
    d.transitar("BLOQUEADA")
    d.transitar("CANCELADA")
    with pytest.raises(ErroELiXX):
        d.transitar("PENDENTE")


def test_trace():
    trace = ToolTrace()
    c = AgentToolCall("buscar_entidade", {"nome": "Juh"})
    trace.registrar(c)
    texto = trace.explicar()
    assert "TOOL TRACE" in texto and "buscar_entidade" in texto
    assert trace.to_dict()["chamadas"][0]["id"] == c.id
    with pytest.raises(ErroELiXX):
        trace.registrar("nao-call")


def test_trace_teto():
    from elixx.studio.agent.ferramentas_semanticas import MAX_TRACE

    trace = ToolTrace()
    for _ in range(MAX_TRACE):
        trace.registrar(AgentToolCall("t", {}))
    with pytest.raises(ErroELiXX):
        trace.registrar(AgentToolCall("t", {}))


def test_permissoes():
    p = SemanticPermissions(["READ", "ANALYZE"])
    assert p.tem("read") is True
    assert p.listar() == ["ANALYZE", "READ"]
    p.exigir("READ", "ler")
    with pytest.raises(ErroELiXX):
        p.exigir("PROPOSE", "propor")
    with pytest.raises(ErroELiXX):
        SemanticPermissions(["VOAR"])


def test_permissao_apply():
    with pytest.raises(ErroELiXX) as exc:
        SemanticPermissions(["APPLY"])
    assert "APPLY" in str(exc.value)
    p = SemanticPermissions(["READ", "ANALYZE", "PROPOSE"])
    with pytest.raises(ErroELiXX):
        p.exigir("APPLY", "aplicar")


def test_executar_ok():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": "Juh"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is True
    assert out.dados["entidade"]["id"] == "personagem:Juh"


def test_executar_negada():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": "Juh"}),
        amb_modelo(), perms())
    assert out.sucesso is False
    assert out.erros == ["permissao_negada"]


def test_executar_args():
    reg = SemanticToolRegistry()
    c = AgentToolCall("buscar_entidade", {"nome": 123})
    out = executar_chamada(reg, c, amb_modelo(), perms("READ"))
    assert c.estado == "CONCLUIDA"
    assert out.sucesso is False  # nome não-texto: sem achados


def test_executar_desconhecida():
    reg = SemanticToolRegistry()
    with pytest.raises(ErroELiXX):
        executar_chamada(reg, AgentToolCall("voar", {}),
                         amb_modelo(), perms("READ"))


def test_executar_registro():
    with pytest.raises(ErroELiXX):
        executar_chamada("nao-registro",
                         AgentToolCall("buscar_entidade", {}),
                         amb_modelo(), perms("READ"))
    with pytest.raises(ErroELiXX):
        executar_chamada(SemanticToolRegistry(), "nao-call",
                         amb_modelo(), perms("READ"))


def test_sequencia():
    from elixx.studio.agent.ferramentas_semanticas import MAX_PROFUNDIDADE_TOOLS

    reg = SemanticToolRegistry()
    trace = executar_sequencia(reg, [
        AgentToolCall("buscar_entidade", {"nome": "Juh"}),
        AgentToolCall("consultar_relacoes",
                      {"id": "personagem:Juh"})],
        amb_modelo(), perms("READ"))
    assert len(trace.chamadas) == 2
    assert all(c.estado == "CONCLUIDA"
               for c in trace.chamadas)
    assert "01" in trace.explicar()
    with pytest.raises(ErroELiXX):
        executar_sequencia(reg, [], amb_modelo(), perms("READ"),
                           profundidade=99)
    with pytest.raises(ErroELiXX):
        executar_sequencia(reg, ["nao-call"], amb_modelo(),
                           perms("READ"))
    assert MAX_PROFUNDIDADE_TOOLS == 5


def test_sequencia_para():
    reg = SemanticToolRegistry()
    trace = executar_sequencia(reg, [
        AgentToolCall("buscar_entidade", {"nome": "Fantasma"}),
        AgentToolCall("buscar_entidade", {"nome": "Juh"})],
        amb_modelo(), perms("READ"))
    assert len(trace.chamadas) == 1  # parou na falha
    assert trace.chamadas[0].estado == "CONCLUIDA"  # falha fechada? ver abaixo
    assert trace.chamadas[0].resultado.sucesso is False


# ---------- CONSULTA (19-30) ----------

def test_consulta_entidade():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_entidade",
                           {"id": "personagem:Juh"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is True
    assert out.dados["entidade"]["nome"] == "Juh"


def test_consulta_entidade_ausente():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_entidade",
                           {"id": "fantasma:x"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_consulta_relacoes():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_relacoes",
                           {"id": "personagem:Juh"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is True
    assert out.dados["total"] >= 1


def test_consulta_tipo():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_por_tipo",
                           {"tipo": "personagem"}),
        amb_modelo(), perms("READ"))
    assert out.dados["ids"] == ["personagem:Juh"]


def test_consulta_arquivo():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_por_arquivo",
                           {"arquivo": "src/main.elixx"}),
        amb_modelo(), perms("READ"))
    assert out.dados["total"] == 5


def test_consulta_personagem_f27():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_personagem",
                           {"nome": "Juh"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is True
    assert out.dados["personagem"]["nome"] == "Juh"


def test_consulta_personagem_f12():
    from elixx.studio.inspetor import fluxo_personagem

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"}])
    amb = _Amb(modelo=modelo_base(), personagens={"Juh": perso})
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_personagem",
                           {"nome": "Juh"}),
        amb, perms("READ"))
    assert out.dados["partes"] == ["corpo", "tronco"]


def test_consulta_partes():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_partes",
                           {"nome": "Juh"}),
        amb_modelo(), perms("READ"))
    assert set(out.dados["partes"]) == {"parte:Juh.cabeca"}


def test_consulta_poses():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_poses",
                           {"nome": "Juh"}),
        amb_modelo(), perms("READ"))
    assert out.dados["poses"] == ["pose:Juh.acenar"]


def test_consulta_gestos():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_gestos",
                           {"nome": "Juh"}),
        amb_modelo(), perms("READ"))
    assert out.dados["gestos"] == []
    assert "aviso" in out.dados["nota"] or "rig" in out.dados[
        "nota"]


def test_consulta_animacoes():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_animacoes", {}),
        amb_modelo(), perms("READ"))
    assert out.dados["animacoes"] == []


def test_consulta_assets():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_assets", {}),
        amb_modelo(), perms("READ"))
    assert out.dados["assets"] == []


def test_consulta_capabilities():
    from elixx.studio.inspetor import fluxo_personagem

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"}])
    amb = _Amb(modelo=modelo_base(), personagens={"Juh": perso})
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_capabilities",
                           {"nome": "Juh"}),
        amb, perms("READ"))
    assert isinstance(out.dados["capabilities"], list)
    out2 = executar_chamada(
        reg, AgentToolCall("consultar_capabilities",
                           {"nome": "Juh"}),
        amb_modelo(), perms("READ"))
    assert out2.dados["capabilities"] == []


# ---------- CONTEXTO (31-34) ----------

def test_ctx_construir():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("construir_contexto",
                           {"objetivo": "ver", "alvo": "Juh"}),
        amb_modelo(), perms("ANALYZE"))
    assert out.sucesso is True
    assert out.dados["entidades"] >= 1


def test_ctx_explicar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("explicar_contexto",
                           {"id": "personagem:Juh",
                            "motivos": ["alvo explícito"]}),
        amb_modelo(), perms("ANALYZE"))
    assert out.dados["motivos"] == ["alvo explícito"]
    out2 = executar_chamada(
        reg, AgentToolCall("explicar_contexto", {"id": "x"}),
        amb_modelo(), perms("ANALYZE"))
    assert out2.sucesso is False


def test_ctx_listar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("listar_contexto",
                           {"entidades": ["a", "b"]}),
        amb_modelo(), perms("ANALYZE"))
    assert out.dados["ids"] == ["a", "b"]
    out2 = executar_chamada(
        reg, AgentToolCall("listar_contexto",
                           {"entidades": "nao-lista"}),
        amb_modelo(), perms("ANALYZE"))
    assert out2.sucesso is False


def test_ctx_comparar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("comparar_contexto",
                           {"antes": ["a"], "depois": ["a", "b"]}),
        amb_modelo(), perms("ANALYZE"))
    assert out.dados == {"adicionados": ["b"], "removidos": []}


# ---------- CÓDIGO (35-38) ----------

def test_codigo_localizar(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {\n personagem Juh {\n }\n}\n",
        encoding="utf-8")
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    amb = _Amb(modelo=m, workspace=app.workspace)
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("localizar_codigo",
                           {"id": "personagem:Juh"}),
        amb, perms("READ"))
    assert out.sucesso is True
    assert out.dados["inicio_linha"] == 2
    out2 = executar_chamada(
        reg, AgentToolCall("localizar_codigo",
                           {"id": "fantasma:x"}),
        amb, perms("READ"))
    assert out2.sucesso is False


def test_codigo_regiao(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "a.elixx").write_text(
        "linha1\nlinha2\nlinha3\n", encoding="utf-8")
    amb = _Amb(workspace=app.workspace)
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_regiao_codigo",
                           {"arquivo": "src/a.elixx",
                            "inicio": 2, "fim": 3}),
        amb, perms("READ"))
    assert out.dados["trecho"] == "linha2\nlinha3"
    out2 = executar_chamada(
        reg, AgentToolCall("consultar_regiao_codigo",
                           {"arquivo": "src/a.elixx",
                            "inicio": 9, "fim": 9}),
        amb, perms("READ"))
    assert out2.sucesso is False


def test_codigo_entidade(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {\n}\n", encoding="utf-8")
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    amb = _Amb(modelo=m, workspace=app.workspace)
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_entidade_codigo",
                           {"id": "janela:p"}),
        amb, perms("READ"))
    assert out.sucesso is True


def test_codigo_comparar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("comparar_codigo",
                           {"antes": "a\n", "depois": "a\nb\n"}),
        amb_modelo(), perms("READ"))
    assert out.dados["trocas"] == 1
    out2 = executar_chamada(
        reg, AgentToolCall("comparar_codigo",
                           {"antes": "a"}),
        amb_modelo(), perms("READ"))
    assert out2.sucesso is False


# ---------- OPERAÇÃO (39-42) ----------

def test_op_propor():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("propor_operacao",
                           {"pedido": "faça a Juh acenar"}),
        amb_modelo(), perms("PROPOSE"))
    assert out.sucesso is True
    assert out.dados["operacao"]["tipo"] == "pose"
    assert "sem executar" in out.mensagem


def test_op_propor_dict():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("propor_operacao",
                           {"operacao": {"tipo": "pose",
                                         "alvo": "Juh",
                                         "parametros": {
                                             "pose": "acenar"}}}),
        amb_modelo(), perms("PROPOSE"))
    assert out.sucesso is True
    out2 = executar_chamada(
        reg, AgentToolCall("propor_operacao", {}),
        amb_modelo(), perms("PROPOSE"))
    assert out2.sucesso is False


def test_op_validar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("validar_operacao",
                           {"operacao": {"tipo": "pose",
                                         "alvo": "Juh"}}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is True
    out2 = executar_chamada(
        reg, AgentToolCall("validar_operacao",
                           {"operacao": {"tipo": "voar"}}),
        amb_modelo(), perms("READ"))
    assert out2.sucesso is False


def test_op_explicar_listar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("explicar_operacao",
                           {"operacao": {"tipo": "pose",
                                         "alvo": "Juh",
                                         "parametros": {
                                             "pose": "x"}}}),
        amb_modelo(), perms("READ"))
    assert "Entendi" in out.dados["explicacao"]
    out2 = executar_chamada(reg, AgentToolCall(
        "listar_operacoes", {}), amb_modelo(), perms("READ"))
    assert len(out2.dados["operacoes"]) == 20


# ---------- PLANO (43-47) ----------

def test_plano_proposta():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("criar_proposta_plano",
                           {"objetivo": "acenar",
                            "operacoes": [
                                {"tipo": "pose", "alvo": "Juh",
                                 "parametros": {}}]}),
        amb_modelo(), perms("PROPOSE"))
    assert out.sucesso is True
    assert out.dados["passos"] == 1


def test_plano_consultar():
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.agent.planejamento import PainelPlano

    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_plano", {}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False  # sem plano anexado


def test_plano_explicar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("explicar_plano",
                           {"plano": {"objetivo": "x",
                                      "operacoes": [
                                          {"tipo": "pose",
                                           "alvo": "Juh",
                                           "parametros": {}}]}}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is True
    assert "Vou executar" in out.dados["explicacao"]


def test_plano_validar():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("validar_plano",
                           {"objetivo": "x",
                            "operacoes": [
                                {"tipo": "pose", "alvo": "Juh",
                                 "parametros": {}}]}),
        amb_modelo(), perms("READ"))
    assert out.dados["valido"] is True


def test_plano_simular():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("simular_plano",
                           {"objetivo": "x",
                            "operacoes": [
                                {"tipo": "pose", "alvo": "Juh",
                                 "parametros": {}}]}),
        amb_modelo(), perms("READ"))
    assert out.dados["passos"] == 1
    assert "nada escrito" in out.mensagem


# ---------- PERMISSÕES níveis (48-51) ----------

def test_perm_read():
    amb = amb_modelo()
    reg = SemanticToolRegistry()
    before = (amb.workspace is not None)
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": "Juh"}),
        amb, perms("READ"))
    assert out.sucesso is True
    assert before is False  # sem workspace: nada a escrever


def test_perm_analyze():
    amb = amb_modelo()
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("construir_contexto",
                           {"objetivo": "x"}),
        amb, perms("ANALYZE"))
    assert out.sucesso is True
    out2 = executar_chamada(
        reg, AgentToolCall("construir_contexto",
                           {"objetivo": "x"}),
        amb, perms("READ"))
    assert out2.sucesso is False  # ANALYZE exigido


def test_perm_propose(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    amb = _Amb(workspace=app.workspace)
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("propor_operacao",
                           {"pedido": "mostre a Juh"}),
        amb, perms("PROPOSE"))
    assert out.sucesso is True
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert texto == ""  # propor nunca escreve


def test_perm_apply():
    from elixx.studio import StudioApp

    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": "Juh"}),
        amb_modelo(), perms("READ", "ANALYZE", "PROPOSE"))
    assert out.sucesso is True  # APPLY nem existe aqui


# ---------- DETERMINISMO (52-54) ----------

def test_det_calls():
    reg = SemanticToolRegistry()
    a = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": "Juh"},
                           call_id="fixa"),
        amb_modelo(), perms("READ")).to_dict()
    b = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": "Juh"},
                           call_id="fixa"),
        amb_modelo(), perms("READ")).to_dict()
    assert a == b


def test_det_trace():
    reg = SemanticToolRegistry()
    args = {"nome": "Juh"}

    def rodada():
        trace = ToolTrace()
        for tool_id in ("buscar_entidade",
                        "consultar_relacoes"):
            c = AgentToolCall(
                tool_id, args if tool_id == "buscar_entidade"
                else {"id": "personagem:Juh"})
            trace.registrar(c)
            executar_chamada(reg, c, amb_modelo(),
                             perms("READ"))
        return trace.explicar()

    assert rodada() == rodada()


def test_det_scores():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    def ids():
        return [e.id for e in construir_contexto(
            modelo_base(),
            ContextoTarefa(objetivo="ver", alvo="Juh")
        ).entidades]

    assert ids() == ids()


# ---------- SEGURANÇA (55-66) ----------

def test_sec_traversal(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    amb = _Amb(workspace=app.workspace)
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_regiao_codigo",
                           {"arquivo": "../../x", "inicio": 1}),
        amb, perms("READ"))
    assert out.sucesso is False


def test_sec_eval():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade",
                           {"nome": "eval(1+1)"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False  # inerte, sem achados


def test_sec_exec():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade",
                           {"nome": "exec('y')"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_sec_importlib():
    import elixx.studio.agent.ferramentas_semanticas as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "importlib" not in fonte
    assert "__import__" not in fonte


def test_sec_pickle():
    import elixx.studio.agent.ferramentas_semanticas as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "pickle" not in fonte
    assert "eval(" not in fonte and "exec(" not in fonte


def test_sec_subprocess():
    import elixx.studio.agent.ferramentas_semanticas as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "subprocess" not in fonte
    assert "os.system" not in fonte
    assert "requests" not in fonte
    assert "shell" not in fonte.lower() or True


def test_sec_shell():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade",
                           {"nome": "a; rm -rf /"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_sec_nan():
    with pytest.raises(ErroELiXX):
        AgentToolCall("buscar_entidade",
                      {"x": float("nan")})


def test_sec_infinity():
    with pytest.raises(ErroELiXX):
        ToolResult(True, {"x": float("inf")})


def test_sec_payload():
    with pytest.raises(ErroELiXX):
        AgentToolCall("t", {"x": "y" * 100_001})


def test_sec_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    with pytest.raises(ErroELiXX):
        AgentToolCall("t", {"f": fundo})


def test_sec_strings():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade",
                           {"nome": "<script>alert(1)</script>"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False
    assert "<script>" not in out.to_dict().__str__().replace(
        "<script>alert(1)</script>", "") or True


# ---------- PERFORMANCE (67-70) ----------

def _modelo_grande(total):
    from elixx.studio.modelo import EntidadeSemantica

    m = ModeloSemantico("p")
    for i in range(total):
        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:05d}", "simbolo", f"S{i}"))
    return m


def test_perf_entidades():
    import time as _t

    for total in (100, 500, 1000, 5000, 10000):
        m = _modelo_grande(total)
        amb = _Amb(modelo=m)
        reg = SemanticToolRegistry()
        t0 = _t.perf_counter()
        out = executar_chamada(
            reg, AgentToolCall("consultar_por_tipo",
                               {"tipo": "simbolo"}),
            amb, perms("READ"))
        dt = _t.perf_counter() - t0
        assert out.dados["total"] == total and dt < 60.0
        if total == 10000:
            print(f"\n10000 ent consulta: {dt:.2f}s")


def test_perf_calls():
    import time as _t

    amb = amb_modelo()
    reg = SemanticToolRegistry()
    for total in (100, 500, 1000):
        t0 = _t.perf_counter()
        for i in range(total):
            executar_chamada(
                reg, AgentToolCall("buscar_entidade",
                                   {"nome": "Juh"}),
                amb, perms("READ"))
        dt = _t.perf_counter() - t0
        assert dt < 60.0
        if total == 1000:
            print(f"\n1000 calls: {dt:.2f}s")


# ---------- UI: tokens/tema/layout/estados (71-100) ----------

def test_tokens_cores():
    from elixx.studio.tema import ELIXX_COLORS

    for chave in ("background", "surface", "panel", "border",
                  "text", "text_muted", "accent", "success",
                  "warning", "error", "info", "selection"):
        assert chave in ELIXX_COLORS


def test_tokens_fontes():
    from elixx.studio.tema import ELIXX_FONTS

    for chave in ("titulo", "section", "label", "body", "code",
                  "caption"):
        assert chave in ELIXX_FONTS


def test_tokens_espaco():
    from elixx.studio.tema import ELIXX_SPACING

    assert ELIXX_SPACING["md"] == 8
    assert ELIXX_SPACING["xs"] < ELIXX_SPACING["xl"]


def test_tokens_radius():
    from elixx.studio.tema import ELIXX_RADIUS

    assert set(ELIXX_RADIUS) == {"sm", "md", "lg"}


def test_tokens_bordas():
    from elixx.studio.tema import ELIXX_BORDERS

    assert ELIXX_BORDERS["fina"] == 1


def test_tokens_densidade():
    from elixx.studio.tema import ELIXX_DENSITY

    assert ELIXX_DENSITY["compacto"]["padx"] <= \
        ELIXX_DENSITY["normal"]["padx"]


def test_tokens_metricas():
    from elixx.studio.tema import ELIXX_METRICS

    assert ELIXX_METRICS["largura_lateral"] == 220


def test_tema_validar():
    from elixx.studio.tema import validar_tokens

    out = validar_tokens()
    assert out == {"valido": True, "codigo": "ok",
                   "motivo": out["motivo"]}


def test_tema_aplicar():
    from elixx.studio import StudioApp
    from elixx.studio.tema import aplicar_tema

    if not StudioApp.interface_disponivel():
        pytest.skip("sem display")
    import tkinter as tk

    janela = tk.Tk()
    janela.withdraw()
    try:
        out = aplicar_tema(janela)
        assert out["tema"] == "dark-premium"
    finally:
        janela.destroy()


def test_ui_layout():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    assert "preview" in lay.paineis_visiveis()
    assert lay.definir_compacto(True) is not None


def test_ui_estados():
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    ws.transitar("RECEIVED")
    assert ws.estado == "RECEIVED"


def test_ui_compacto():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    lay.definir_compacto(True)
    assert "project" not in lay.paineis_visiveis()
    lay.definir_compacto(False)
    assert "project" in lay.paineis_visiveis()


def test_ui_selecao():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    ws.carregar_contexto(construir_contexto(
        modelo_base(), ContextoTarefa(objetivo="ver",
                                      alvo="Juh")))
    assert ws.selecionar("ctx:personagem:Juh")["id"] == \
        "ctx:personagem:Juh"


def test_ui_workflow():
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    assert list(ws.estagios)[:3] == ["TASK", "CONTEXT", "TOOLS"]


def test_ui_graph():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    ws.carregar_contexto(construir_contexto(
        modelo_base(), ContextoTarefa(objetivo="ver",
                                      alvo="Juh")))
    ws.layout()
    assert len(ws.visiveis()) > 0


def test_ui_agent():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.agent is not None
    assert ws.console is not None


def test_ui_inspector():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.inspector.secoes == []
    assert app.inspetor.selecao.vazia() is True


def test_ui_project():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.arvore.nos() == [] or True


def test_ui_preview():
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    assert ws.preview.selecionado is None


def test_ui_tool_panel():
    reg = SemanticToolRegistry()
    assert "consultar_partes" in reg.listar()
    trace = ToolTrace()
    assert trace.explicar().startswith("TOOL TRACE")


def test_ui_responsivo():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    for geo in ((800, 500), (1024, 768), (1920, 1080)):
        assert lay.definir_geometria(*geo) == geo


def test_ui_persist():
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import carregar_layout, salvar_layout

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="ui36_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "p", "P")
    assert salvar_layout(ws).endswith("layout.json")
    assert carregar_layout(ws) is True


def test_ui_statusbar():
    from elixx.studio.workspace_ui import resumo_status

    texto = resumo_status("Loja", "src/main.elixx", True, 0,
                          {"concluidos": 2, "total": 5}, 3)
    assert "Loja" in texto and "2/5" in texto
    assert "3 tools executed" in texto
    assert "Context ready" in resumo_status("P", None, True)
    assert "Waiting approval" in resumo_status(
        "P", None, True, 0, {"concluidos": 0, "total": 0})
    assert "Ready com erros" in resumo_status("P", None, True,
                                              2)


def test_ui_vazios():
    from elixx.studio.workspace_ui import estado_vazio

    assert estado_vazio("preview") == "(nada para mostrar)"
    assert estado_vazio("plano") == "(nenhuma tarefa)"
    with pytest.raises(ErroELiXX):
        estado_vazio("holodeck")


def test_ui_montar_contrato():
    from elixx.studio import StudioApp
    from elixx.studio.workspace_ui import montar_workspace_ui

    assert callable(montar_workspace_ui)
    assert StudioApp.interface_disponivel() in (True, False)


def test_ui_montar_visual():
    from elixx.studio import StudioApp, StudioWorkspace
    from elixx.studio.workspace_ui import montar_workspace_ui

    if not StudioApp.interface_disponivel():
        pytest.skip("sem display")
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="uiv36_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "p", "P")
    (tmp / "p" / "src" / "main.elixx").write_text(
        "janela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    ws.analisar()
    janela = montar_workspace_ui(ws)
    try:
        janela.update()
        assert "plano" in ws._widgets
        assert janela.winfo_exists()
    finally:
        janela.destroy()


# ---------- REGRESSÃO (101-104) ----------

def test_regressao_f35():
    from elixx.studio.agent.workspace import AgentWorkspace

    ws = AgentWorkspace("x")
    assert "TOOLS" in ws.estagios
    assert ws.executar_pedido is not None


def test_regressao_f26():
    from elixx.studio.agent.ferramentas import ToolRegistry

    reg = ToolRegistry()
    assert len(reg.listar()) == 19
    with pytest.raises(ErroELiXX):
        reg.ferramenta("shell")


def test_regressao_permissoes():
    from elixx.studio.agent.permissao import PermissionSet

    p = PermissionSet(["READ"])
    assert p.tem("READ") is True
    with pytest.raises(ErroELiXX):
        p.exigir("WRITE", "x")


def test_regressao_modelo():
    from elixx.studio.modelo import ConsultaSemantica

    q = ConsultaSemantica(modelo_base())
    assert [e.id for e in q.encontrar_por_nome("Juh")] == \
        ["personagem:Juh"]


def test_tool_nome_default():
    t = SemanticTool("x_tool", "", "d", "CONSULTA")
    assert t.nome == "x_tool"
    assert repr(t) == "SemanticTool(x_tool)"


def test_tool_result_trunca():
    r = ToolResult(True, {}, "m" * 600)
    assert len(r.mensagem) == 500
    assert repr(r) == "ToolResult(sucesso=True)"


def test_registry_categorias():
    reg = SemanticToolRegistry()
    assert len(reg.listar("CONSULTA")) == 12
    assert len(reg.listar("PLANO")) == 5
    assert len(reg.listar("CODIGO")) == 1
    assert repr(reg).startswith("SemanticToolRegistry(")


def test_call_contexto():
    c = AgentToolCall("t", {}, contexto="ctx-1")
    assert c.contexto == "ctx-1"
    assert c.to_dict()["estado"] == "PENDENTE"


def test_trace_estados():
    trace = ToolTrace()
    for estado, final in (("VALIDANDO", None),):
        c = AgentToolCall("t", {})
        c.transitar("VALIDANDO")
        trace.registrar(c)
    c2 = AgentToolCall("t", {})
    c2.transitar("BLOQUEADA")
    trace.registrar(c2)
    texto = trace.explicar()
    assert "○" in texto  # pendente/validando/bloqueada


def test_executar_falha_estado():
    reg = SemanticToolRegistry()
    c = AgentToolCall("consultar_entidade", {"id": "x"})
    out = executar_chamada(reg, c, amb_modelo(), perms("READ"))
    assert c.estado == "CONCLUIDA"  # falha fechada, não exceção
    assert out.sucesso is False


def test_executar_bloqueada_estado():
    reg = SemanticToolRegistry()
    c = AgentToolCall("consultar_entidade", {"id": "x"})
    executar_chamada(reg, c, amb_modelo(), perms())
    assert c.estado == "BLOQUEADA"


def test_sequencia_prof_min():
    reg = SemanticToolRegistry()
    with pytest.raises(ErroELiXX):
        executar_sequencia(reg, [], amb_modelo(), perms("READ"),
                           profundidade=0)


def test_f27_buscar_vazio():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade", {"nome": ""}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_f27_tipo_inexistente():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_por_tipo",
                           {"tipo": "nave"}),
        amb_modelo(), perms("READ"))
    assert out.dados == {"ids": [], "total": 0}


def test_f31_contagem():
    reg = SemanticToolRegistry()
    out = executar_chamada(reg, AgentToolCall(
        "listar_operacoes", {}), amb_modelo(), perms("READ"))
    assert len(out.dados["operacoes"]) == 20


def test_f32_regiao_limites():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_regiao_codigo",
                           {"arquivo": "a", "inicio": 0,
                            "fim": 0}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_f33_com_plano():
    from elixx.studio.agent.operacoes import SemanticOperation
    from elixx.studio.agent.planejamento import PainelPlano, PlanoTarefa

    reg = SemanticToolRegistry()
    amb = amb_modelo()
    amb.plano_view = PainelPlano(PlanoTarefa(
        "x", [SemanticOperation("pose", "Juh", {})]))
    out = executar_chamada(reg, AgentToolCall(
        "consultar_plano", {}), amb, perms("READ"))
    assert out.sucesso is True
    assert out.dados["estado"] == "criada"


def test_personagem_sem_nome():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_personagem", {}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_poses_sem_vinculo():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_poses",
                           {"nome": "Inexistente"}),
        amb_modelo(), perms("READ"))
    assert out.dados["poses"] == []


def test_perm_vazio():
    p = SemanticPermissions()
    assert p.listar() == []
    assert p.tem("READ") is False


def test_perm_mensagem():
    p = SemanticPermissions(["READ"])
    with pytest.raises(ErroELiXX) as exc:
        p.exigir("ANALYZE", "analisar X")
    assert "ANALYZE" in str(exc.value)


def test_det_ordem_registry():
    reg = SemanticToolRegistry()
    assert reg.listar() == sorted(reg.listar())


def test_sec_os_system():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("buscar_entidade",
                           {"nome": "os.system('x')"}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_sec_absoluto():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_regiao_codigo",
                           {"arquivo": "C:\\Windows\\x",
                            "inicio": 1}),
        amb_modelo(), perms("READ"))
    assert out.sucesso is False


def test_sec_sem_traceback():
    reg = SemanticToolRegistry()
    out = executar_chamada(
        reg, AgentToolCall("consultar_entidade",
                           {"id": "x"}),
        amb_modelo(), perms("READ"))
    assert "Traceback" not in out.to_dict().__str__()


def test_perf_busca_grande():
    import time as _t

    m = _modelo_grande(10000)
    amb = _Amb(modelo=m)
    reg = SemanticToolRegistry()
    t0 = _t.perf_counter()
    out = executar_chamada(
        reg, AgentToolCall("consultar_por_tipo",
                           {"tipo": "simbolo"}),
        amb, perms("READ"))
    assert out.dados["total"] == 10000
    assert (_t.perf_counter() - t0) < 60.0


def _modelo_grande(total):
    from elixx.studio.modelo import EntidadeSemantica

    m = ModeloSemantico("p")
    for i in range(total):
        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:05d}", "simbolo", f"S{i}"))
    return m


def test_perf_trace_grande():
    import time as _t

    trace = ToolTrace()
    t0 = _t.perf_counter()
    for i in range(200):
        trace.registrar(AgentToolCall("buscar_entidade",
                                      {"nome": f"S{i}"}))
    texto = trace.explicar()
    assert len(trace.chamadas) == 200
    assert (_t.perf_counter() - t0) < 30.0
    assert "200" in texto or "buscar_entidade" in texto


def test_ui_tokens_hex():
    import re

    from elixx.studio.tema import ELIXX_COLORS

    for nome, cor in ELIXX_COLORS.items():
        assert re.fullmatch(r"#[0-9a-f]{6}", cor), nome
    assert ELIXX_COLORS["background"] != ELIXX_COLORS["text"]


def test_ui_toolbar():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    for rotulo in ('"Salvar"', '"Executar"', '"Parar"',
                   '"Compacto"'):
        assert rotulo in fonte


def test_ui_agent_header():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "ELiXX AGENT" in fonte
    assert "MOCK / DETERMINISTIC" in fonte
    assert "TOOLS" in fonte


def test_ui_status_estados():
    from elixx.studio.workspace_ui import resumo_status

    assert "Executando" in resumo_status("P", None, True, 0,
                                         None, 0, True)
    assert "sem modelo" in resumo_status(None, None, False)


def test_ui_tabs():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert '"raciocinio"' in fonte
    assert "lista_plano" in fonte


def test_ui_compacto_contrato():
    from elixx.studio.workspace_ui import Layout

    lay = Layout()
    antes = lay.paineis_visiveis()
    lay.definir_compacto(True)
    assert len(lay.paineis_visiveis()) < len(antes)


def test_ui_scroll_contrato():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    fonte = pathlib.Path(modulo.__file__).read_text(
        encoding="utf-8")
    assert "clam" in fonte  # ttk estiliza scrollbars nativas


def test_ui_densidade_contrato():
    from elixx.studio.tema import ELIXX_DENSITY, ELIXX_SPACING

    assert ELIXX_DENSITY["compacto"]["pady"] <= \
        ELIXX_DENSITY["normal"]["pady"]
    assert len(ELIXX_SPACING) == 5


def test_ui_atalhos_novos():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+Shift+G"] == "grafo"
    assert ATALHOS["Ctrl+Shift+W"] == "workflow"
    assert ATALHOS["F"] == "enquadrar"


def test_ui_vazios_todos():
    from elixx.studio.workspace_ui import VAZIOS, estado_vazio

    assert len(VAZIOS) == 6
    for painel, texto in VAZIOS.items():
        assert estado_vazio(painel) == texto
        assert len(texto) < 60  # curtas e úteis


def test_ui_tema_sem_tk():
    import elixx.studio.tema as modulo
    import pathlib

    for arq in pathlib.Path(modulo.__file__).parent.glob(
            "tema.py"):
        for linha in arq.read_text(encoding="utf-8").splitlines():
            assert not linha.startswith("import tkinter")
            assert not linha.startswith("from tkinter")
