"""Testes da Fase 35 — reasoning workspace (sem LLM, sem display)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent.workspace import (
    AgentEdge,
    AgentNode,
    AgentWorkspace,
    transicoes_permitidas,
)
from elixx.studio.modelo import ModeloSemantico, analisar_texto

FONTE = (
    "janela principal {\n"
    " personagem Juh {\n"
    "  parte cabeca {\n"
    "  }\n"
    "  parte olhos {\n"
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


def ctx_base():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    return construir_contexto(
        modelo_base(),
        ContextoTarefa(objetivo="fazer Juh acenar", alvo="Juh"))


def ws_com_contexto():
    ws = AgentWorkspace("fazer Juh acenar")
    ws.carregar_contexto(ctx_base())
    return ws


# ---------- AgentWorkspace (1-8) ----------

def test_ws_criacao():
    ws = AgentWorkspace("fazer X")
    assert ws.estado == "IDLE"
    assert set(ws.estagios) == {"TASK", "CONTEXT", "TOOLS",
                                "OPERATIONS", "PLAN", "CHANGES",
                                "PREVIEW"}
    assert ws.id.startswith("sessao_")


def test_ws_ids():
    a = AgentWorkspace("x")
    b = AgentWorkspace("x")
    assert a.id != b.id  # contador, sem relógio
    assert AgentWorkspace("x", sessao_id="fixa").id == "fixa"


def test_ws_tarefa_vazia():
    ws = AgentWorkspace()
    assert ws.tarefa == ""


def test_ws_transicao():
    ws = AgentWorkspace("x")
    ws.transitar("RECEIVED")
    assert ws.estado == "RECEIVED"
    with pytest.raises(ErroELiXX):
        ws.transitar("COMPLETED")  # salto inválido
    assert transicoes_permitidas("IDLE") == ("RECEIVED",
                                             "CANCELLED")
    with pytest.raises(ErroELiXX):
        transicoes_permitidas("VOANDO")


def test_ws_estagio():
    ws = AgentWorkspace("x")
    ws.marcar_estagio("TASK", "processando",
                      {"pedido": "oi"}, quantidade=1)
    assert ws.estagios["TASK"]["estado"] == "processando"
    with pytest.raises(ErroELiXX):
        ws.marcar_estagio("SONHO", "pronto")
    with pytest.raises(ErroELiXX):
        ws.marcar_estagio("TASK", "voando")
    with pytest.raises(ErroELiXX):
        ws.marcar_estagio("TASK", "pronto",
                          dados={"f": object()})


def test_ws_eventos():
    from elixx.studio import EventBus

    ws = AgentWorkspace("x")
    bus = EventBus()
    ouvidos = []
    bus.assinar("stage_changed",
                lambda e, d: ouvidos.append(d["estado"]))
    ws.acoplar_bus(bus)
    ws.transitar("RECEIVED")
    assert ouvidos == ["RECEIVED"]


def test_ws_sem_bus():
    ws = AgentWorkspace("x")
    ws.transitar("RECEIVED")  # sem bus: segue normal
    assert ws.estado == "RECEIVED"


# ---------- stages/estados (9-14) ----------

def test_states_lista():
    from elixx.studio.agent.workspace import ESTADOS

    assert len(ESTADOS) >= 14
    assert "AMBIGUOUS" in ESTADOS and "FAILED" in ESTADOS


def test_states_finais():
    ws = AgentWorkspace("x")
    ws.transitar("RECEIVED")
    ws.transitar("CANCELLED")
    with pytest.raises(ErroELiXX):
        ws.transitar("RECEIVED")
    with pytest.raises(ErroELiXX):
        ws.cancelar()  # já encerrada


def test_states_falha():
    ws = AgentWorkspace("x")
    with pytest.raises(ErroELiXX):
        ws.transitar("FAILED")  # IDLE→FAILED inválido
    ws.transitar("RECEIVED")
    ws.transitar("FAILED")
    assert ws.estado == "FAILED"


def test_cancelamento():
    ws = ws_com_contexto()
    ws.transitar("RECEIVED")
    out = ws.cancelar()
    assert out == {"estado": "CANCELLED"}
    assert ws.estado == "CANCELLED"


def test_cancelamento_seguro():
    ws = AgentWorkspace("x")
    ws.cancelar()
    assert ws.estado == "CANCELLED"


# ---------- Context Result (15-18) ----------

def test_context_result():
    ws = ws_com_contexto()
    assert len(ws.nos) == 6  # 5 ent + 1 arquivo
    assert ws.estagios["CONTEXT"]["estado"] == "pronto"


def test_context_scores():
    ws = ws_com_contexto()
    juh = ws.nos["ctx:personagem:Juh"]
    assert juh.score == 1.00
    assert "alvo explícito" in juh.motivos


def test_context_arquivos():
    ws = ws_com_contexto()
    assert "file:src/main.elixx" in ws.nos
    assert ws.nos["file:src/main.elixx"].tipo == "FILE"


# ---------- graph/nodes/edges (19-28) ----------

def test_graph_nos():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("n1", "TASK", "tarefa"))
    assert ws.nos["n1"].rotulo == "tarefa"
    with pytest.raises(ErroELiXX):
        ws.adicionar_no(AgentNode("n1", "TASK"))
    with pytest.raises(ErroELiXX):
        ws.adicionar_no("nao-no")
    with pytest.raises(ErroELiXX):
        AgentNode("  ", "TASK")


def test_graph_tipos():
    for tipo in ("ENTITY", "FILE", "CHARACTER", "PART", "SCENE",
                 "POSE", "ANIMATION", "ASSET", "OPERATION",
                 "PLAN_STEP", "CHANGE"):
        assert AgentNode(f"n-{tipo}", tipo).tipo == tipo
    with pytest.raises(ErroELiXX):
        AgentNode("n", "NAVE")


def test_graph_arestas():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("a", "TASK"))
    ws.adicionar_no(AgentNode("b", "ENTITY"))
    ws.adicionar_aresta(AgentEdge("a", "possui", "b"))
    assert len(ws.arestas) == 1
    with pytest.raises(ErroELiXX):
        ws.adicionar_aresta(AgentEdge("a", "possui", "b"))
    with pytest.raises(ErroELiXX):
        ws.adicionar_aresta(AgentEdge("a", "x", "fantasma"))
    with pytest.raises(ErroELiXX):
        ws.adicionar_aresta("nao-aresta")


def test_graph_sem_duplicacao():
    ws = ws_com_contexto()
    ids = list(ws.nos)
    assert len(ids) == len(set(ids))
    chaves = [(a.origem, a.tipo, a.destino)
              for a in ws.arestas]
    assert len(chaves) == len(set(chaves))


def test_graph_sem_inventadas():
    ws = ws_com_contexto()
    for aresta in ws.arestas:
        assert aresta.origem in ws.nos
        assert aresta.destino in ws.nos


def test_graph_fontes():
    ws = ws_com_contexto()
    fontes = {a.fonte for a in ws.arestas}
    assert fontes <= {"F27", "F34", "F31", "F33", "F32"}


def test_node_serializacao():
    no = AgentNode("n", "ENTITY", "Juh", source_id="personagem:Juh",
                   score=1.0, motivos=["alvo"],
                   detalhe={"arquivo": "a"})
    copia = AgentNode.from_dict(no.to_dict())
    assert copia.to_dict() == no.to_dict()
    assert copia.x == 0.0 and copia.expandido is False
    with pytest.raises(ErroELiXX):
        AgentNode.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        AgentNode("n", "ENTITY", score=float("nan"))


def test_edge_serializacao():
    ar = AgentEdge("a", "possui", "b", fonte="F34")
    assert AgentEdge.from_dict(ar.to_dict()).fonte == "F34"
    assert repr(ar).startswith("AgentEdge(")
    with pytest.raises(ErroELiXX):
        AgentEdge.from_dict([])
    with pytest.raises(ErroELiXX):
        AgentEdge("", "possui", "b")


def test_edge_explicacao():
    ws = ws_com_contexto()
    a = ws.arestas[0]
    out = ws.explicar_aresta(a.origem, a.tipo, a.destino)
    assert out["origem"] == a.origem
    assert "F27" in out["fonte"] or "F34" in out["fonte"]
    with pytest.raises(ErroELiXX):
        ws.explicar_aresta("x", "y", "z")


# ---------- layout determinístico (29-32) ----------

def test_layout_camadas():
    ws = ws_com_contexto()
    out = ws.layout()
    assert out["camadas"] >= 2
    assert all(n.camada >= 0 for n in ws.nos.values())


def test_layout_reproduzivel():
    def montar():
        ws = ws_com_contexto()
        ws.layout()
        return [(nid, n.x, n.y) for nid, n in sorted(
            ws.nos.items())]

    assert montar() == montar()


def test_layout_limites():
    ws = ws_com_contexto()
    with pytest.raises(ErroELiXX):
        ws.layout(dx=0)
    with pytest.raises(ErroELiXX):
        ws.layout(dx=float("inf"))
    with pytest.raises(ErroELiXX):
        ws.layout(dx="larga")


def test_layout_vazio():
    ws = AgentWorkspace("x")
    assert ws.layout() == {"nos": 0, "camadas": 0}


# ---------- seleção (33-36) ----------

def test_selecao():
    ws = ws_com_contexto()
    out = ws.selecionar("ctx:personagem:Juh")
    assert out["id"] == "ctx:personagem:Juh"
    assert ws.selecao == "ctx:personagem:Juh"
    ws.limpar_selecao()
    assert ws.selecao is None
    with pytest.raises(ErroELiXX):
        ws.selecionar("fantasma")


def test_selecao_detalhe_modelo():
    ws = ws_com_contexto()
    ws.selecionar("ctx:personagem:Juh")
    out = ws.detalhe_selecao(modelo_base())
    assert out["entidade"]["nome"] == "Juh"
    assert any(r["tipo"] == "possui" for r in out["relacoes"])


def test_selecao_sem_modelo():
    ws = ws_com_contexto()
    ws.selecionar("ctx:personagem:Juh")
    out = ws.detalhe_selecao()
    assert out["tipo"] == "CHARACTER"
    assert out["motivos"]


def test_selecao_nada():
    ws = AgentWorkspace("x")
    with pytest.raises(ErroELiXX):
        ws.detalhe_selecao()


# ---------- expansão/colapso (37-40) ----------

def test_expansao():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("ctx:personagem:Juh", "CHARACTER",
                              "Juh", source_id="personagem:Juh"))
    out = ws.expandir("ctx:personagem:Juh", modelo_base())
    assert out["expandido"] is True
    assert out["novos"] >= 2  # cabeça, olhos
    assert "ctx:parte:Juh.cabeca" in ws.nos


def test_expansao_idempotente():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("ctx:personagem:Juh", "CHARACTER",
                              "Juh", source_id="personagem:Juh"))
    ws.expandir("ctx:personagem:Juh", modelo_base())
    n = len(ws.nos)
    out = ws.expandir("ctx:personagem:Juh", modelo_base())
    assert out == {"expandido": True, "novos": 0}
    assert len(ws.nos) == n


def test_colapso():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("ctx:personagem:Juh", "CHARACTER",
                              "Juh", source_id="personagem:Juh"))
    ws.expandir("ctx:personagem:Juh", modelo_base())
    out = ws.recolher("ctx:personagem:Juh")
    assert out == {"expandido": False, "arestas_ocultas": 2}
    assert "personagem:Juh" in modelo_base().obter_entidade(
        "personagem:Juh").id  # modelo intacto
    with pytest.raises(ErroELiXX):
        ws.expandir("fantasma")
    with pytest.raises(ErroELiXX):
        ws.recolher("fantasma")


def test_expansao_sem_modelo():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("n", "ENTITY", source_id="a:b"))
    out = ws.expandir("n")
    assert out == {"expandido": True, "novos": 0}


# ---------- filtros/busca (41-44) ----------

def test_filtros():
    ws = ws_com_contexto()
    assert ws.filtrar(["CHARACTER", "PART"]) == ["CHARACTER",
                                                 "PART"]
    vis = ws.visiveis()
    assert all(n["tipo"] in ("CHARACTER", "PART") for n in vis)
    ws.filtrar([])
    assert len(ws.visiveis()) == len(ws.nos)
    with pytest.raises(ErroELiXX):
        ws.filtrar(["NAVE"])


def test_busca():
    ws = ws_com_contexto()
    achados = ws.buscar("juh")
    assert {a["id"] for a in achados} >= {"ctx:personagem:Juh"}
    assert ws.buscar("zzz-nada") == []
    with pytest.raises(ErroELiXX):
        ws.buscar("   ")


def test_busca_modelo():
    ws = AgentWorkspace("x")
    achados = ws.buscar("Juh", modelo_base())
    assert any(a.get("fonte") == "F27" for a in achados)


def test_busca_limite():
    ws = AgentWorkspace("x")
    for i in range(60):
        ws.adicionar_no(AgentNode(f"n{i:02d}", "ENTITY",
                                  f"coisa {i}"))
    assert len(ws.buscar("coisa")) == 50  # teto MAX_VISIVEIS


# ---------- zoom/pan/fit (45-49) ----------

def test_zoom():
    ws = AgentWorkspace("x")
    assert ws.definir_zoom(2.0) == 2.0
    assert ws.aproximar() == 3.0
    assert ws.aproximar() == 3.0  # teto
    assert ws.afastar() == 2.0
    assert ws.normalizar_zoom() == 1.0
    with pytest.raises(ErroELiXX):
        ws.definir_zoom(42.0)
    with pytest.raises(ErroELiXX):
        ws.definir_zoom("perto")


def test_pan():
    ws = AgentWorkspace("x")
    assert ws.mover_pan(10, -5) == [10.0, -5.0]
    assert ws.mover_pan(1, 1) == [11.0, -4.0]
    with pytest.raises(ErroELiXX):
        ws.mover_pan(float("inf"), 0)
    with pytest.raises(ErroELiXX):
        ws.mover_pan("a", 0)


def test_fit():
    ws = ws_com_contexto()
    ws.layout()
    out = ws.enquadrar()
    assert out["nos"] == len(ws.nos)
    assert len(out["bbox"]) == 4
    vazio = AgentWorkspace("x")
    assert vazio.enquadrar() == {"zoom": 1.0, "nos": 0}


def test_viewport_limite():
    ws = AgentWorkspace("x")
    for i in range(150):
        ws.adicionar_no(AgentNode(f"n{i:03d}", "ENTITY",
                                  f"e{i}", score=0.0))
    assert len(ws.visiveis()) == 100  # sem travar
    assert ws.diagnosticar()["limitada"] is True


# ---------- workflow (50-53) ----------

def test_workflow_etapas():
    ws = AgentWorkspace("fazer X")
    assert list(ws.estagios) == ["TASK", "CONTEXT", "TOOLS",
                                 "OPERATIONS", "PLAN", "CHANGES",
                                 "PREVIEW"]


def test_workflow_pipeline():
    ws = AgentWorkspace("faça a Juh acenar")
    out = ws.executar_pedido("faça a Juh acenar", {
        "modelo": modelo_base(), "objetivo": "acenar",
        "selecionado": "personagem:Juh",
        "arquivo": "src/main.elixx"})
    assert ws.estado == "OPERATIONS_READY"
    assert out["intencao"]["tipo"] == "pose"
    assert ws.estagios["CONTEXT"]["estado"] == "pronto"


def test_workflow_erro_amigavel():
    ws = AgentWorkspace("x")
    out = ws.executar_pedido("faça a Juh levitar", {
        "modelo": modelo_base()})
    assert ws.estado == "FAILED"
    assert "INTENT_NAO_SUPORTADA" in out["erro"]
    assert "Traceback" not in out["erro"]


def test_workflow_sem_modelo():
    ws = AgentWorkspace("x")
    with pytest.raises(ErroELiXX):
        ws.executar_pedido("faça a Juh acenar", {})


# ---------- context/operations/plan/changes (54-60) ----------

def test_stage_context():
    ws = ws_com_contexto()
    assert ws.estagios["CONTEXT"]["quantidade"] == 6


def test_stage_operations():
    from elixx.studio.agent.operacoes import SemanticOperation

    ws = AgentWorkspace("x")
    out = ws.carregar_operacoes(
        [SemanticOperation("pose", "Juh", {"pose": "acenar"})])
    assert out == {"operacoes": 1}
    assert ws.estagios["OPERATIONS"]["estado"] == "pronto"
    with pytest.raises(ErroELiXX):
        ws.carregar_operacoes(["nao-op"])


def test_stage_operations_evento():
    from elixx.studio.agent.operacoes import SemanticEventOperation

    ws = AgentWorkspace("x")
    ev = SemanticEventOperation(
        "clique", "Juh",
        [{"tipo": "pose", "alvo": "Juh",
          "parametros": {"pose": "acenar"}}])
    out = ws.carregar_operacoes([ev])
    assert out == {"operacoes": 2}  # evento + efeito


def test_stage_plan():
    from elixx.studio.agent.operacoes import SemanticOperation
    from elixx.studio.agent.planejamento import (
        PlanoTarefa,
        construir_plano,
    )

    ws = AgentWorkspace("x")
    t = PlanoTarefa("x", [SemanticOperation("pose", "Juh", {})])
    construir_plano(t)
    out = ws.carregar_plano(t)
    assert out == {"ordem": ["passo_1"]}
    assert ws.estagios["PLAN"]["estado"] == "pronto"


def test_stage_plan_ordem():
    from elixx.studio.agent.operacoes import SemanticOperation
    from elixx.studio.agent.planejamento import (
        PlanoTarefa,
        construir_plano,
    )

    ws = AgentWorkspace("x")
    t = PlanoTarefa("x", [SemanticOperation("pose", "Juh", {}),
                          SemanticOperation("pose", "Juh", {})],
                    dependencias={"passo_2": ["passo_1"]})
    construir_plano(t)
    out = ws.carregar_plano(t)
    assert out["ordem"] == ["passo_1", "passo_2"]
    arestas = [(a.origem, a.tipo, a.destino)
               for a in ws.arestas]
    assert ("step:passo_1", "precede", "step:passo_2") in arestas


def test_stage_changes():
    ws = AgentWorkspace("x")
    out = ws.carregar_changes(
        [{"arquivo": "src/main.elixx", "operacao": "editar"}])
    assert out == {"mudancas": 1}
    assert ws.estagios["CHANGES"]["estado"] == "pronto"
    with pytest.raises(ErroELiXX):
        ws.carregar_changes(["nao-dict"])


def test_stage_preview():
    ws = AgentWorkspace("x")
    ws.marcar_estagio("PREVIEW", "pronto", {"ok": True},
                      quantidade=1)
    assert ws.estagios["PREVIEW"]["quantidade"] == 1


# ---------- preview/inspector/code/semantic (61-64) ----------

def test_preview_integration():
    ws = ws_com_contexto()
    ws.marcar_estagio("PREVIEW", "atual")
    assert ws.estagios["PREVIEW"]["estado"] == "atual"


def test_inspector_integration():
    ws = ws_com_contexto()
    out = ws.selecionar("ctx:personagem:Juh")
    assert "motivos" in out and "score" in out


def test_code_integration():
    ws = ws_com_contexto()
    ws.selecionar("ctx:personagem:Juh")
    out = ws.detalhe_selecao(modelo_base())
    assert out["entidade"]["arquivo"] == "src/main.elixx"


def test_semantic_integration():
    ws = ws_com_contexto()
    assert ws.nos["ctx:personagem:Juh"].source_id == \
        "personagem:Juh"


# ---------- F26/F27/F30/F31/F32/F33/F34 (65-71) ----------

def test_f26_bus():
    from elixx.studio import EventBus

    ws = AgentWorkspace("x")
    bus = EventBus()
    n = []
    bus.assinar("node_selected",
                lambda e, d: n.append(d["id"]))
    ws.acoplar_bus(bus)
    ws_com = ws_com_contexto()
    ws_com.acoplar_bus(bus)
    ws_com.selecionar("ctx:personagem:Juh")
    assert n == ["ctx:personagem:Juh"]


def test_f27_fonte():
    ws = ws_com_contexto()
    assert ws.explicar_aresta(
        ws.arestas[0].origem, ws.arestas[0].tipo,
        ws.arestas[0].destino)["fonte"] in ("Modelo Semântico F27",
                                            "Context Engine F34")


def test_f30_intent():
    ws = AgentWorkspace("faça a Juh acenar")
    out = ws.executar_pedido("mostre a Juh", {
        "modelo": modelo_base()})
    assert out["intencao"]["tipo"] == "mostrar"
    assert out["intencao"]["personagem"] == "Juh"


def test_f31_ops():
    ws = AgentWorkspace("x")
    out = ws.executar_pedido(
        "quando clicar na Juh, faça ela acenar",
        {"modelo": modelo_base()})
    assert ws.estado == "OPERATIONS_READY"
    tipos = [n.tipo for n in ws.nos.values()
             if n.tipo == "OPERATION"]
    assert len(tipos) == 2  # evento + efeito


def test_f32_changes_vazias():
    ws = AgentWorkspace("x")
    assert ws.carregar_changes([]) == {"mudancas": 0}


def test_f33_planos():
    from elixx.studio.agent.planejamento import PainelPlano

    ws = AgentWorkspace("x")
    assert isinstance(ws.estagios, dict)
    assert PainelPlano is not None


def test_f34_scores():
    ws = ws_com_contexto()
    assert ws.nos["ctx:personagem:Juh"].score == 1.00


# ---------- ambiguidade/overrides/erros/cancel (72-77) ----------

def test_ambiguidade():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao Juh(x) {\n retornar x\n}\n",
                   "src/b.elixx")
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    r = construir_contexto(m, ContextoTarefa(objetivo="x",
                                             alvo="Juh"))
    assert r.ambiguidade["status"] == "ambiguo"
    ws = AgentWorkspace("ver Juh")
    ws.transitar("RECEIVED")
    out = ws.marcar_ambiguo(r.ambiguidade["candidatos"])
    assert ws.estado == "AMBIGUOUS"
    assert len(out["candidatos"]) == 2
    resolvido = ws.resolver_ambiguidade("personagem:Juh")
    assert resolvido == {"resolvido": "personagem:Juh"}
    assert ws.estado == "CONTEXT_ANALYZING"


def test_ambiguidade_sem_estado():
    ws = AgentWorkspace("x")
    with pytest.raises(ErroELiXX):
        ws.resolver_ambiguidade("personagem:Juh")
    with pytest.raises(ErroELiXX):
        ws.resolver_ambiguidade("   ")


def test_overrides():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    t = ContextoTarefa(objetivo="ver", alvo="Juh",
                       excluir=["personagem:Juh"])
    r = construir_contexto(modelo_base(), t)
    assert "personagem:Juh" not in {e.id for e in r.entidades}
    assert any(e["motivo"] == "EXCLUIDO_MANUALMENTE"
               for e in r.excluidas)


def test_erros_sem_traceback():
    ws = AgentWorkspace("x")
    out = ws.executar_pedido("", {"modelo": modelo_base()})
    assert ws.estado == "FAILED"
    assert "Traceback" not in out.get("erro", "")


def test_cancelamento_limpo():
    ws = ws_com_contexto()
    ws.transitar("RECEIVED")
    ws.cancelar()
    assert ws.estado == "CANCELLED"
    assert ws.nos  # nada apagado


# ---------- serialização (78-79) ----------

def test_serializacao():
    ws = ws_com_contexto()
    ws.layout()
    ws.selecionar("ctx:personagem:Juh")
    copia = AgentWorkspace.from_dict(ws.to_dict())
    assert copia.to_json() == ws.to_json()
    assert copia.selecao == "ctx:personagem:Juh"


def test_serializacao_regras():
    ws = AgentWorkspace("x")
    d = ws.to_dict()
    d["estado"] = "APPLYING"
    with pytest.raises(ErroELiXX):
        AgentWorkspace.from_dict(d)  # sem retomar execução
    with pytest.raises(ErroELiXX):
        AgentWorkspace.from_dict("nao-dict")
    d2 = ws.to_dict()
    d2["vista"]["zoom"] = 42.0
    assert AgentWorkspace.from_dict(d2).vista["zoom"] == 1.0


# ---------- segurança (80-86) ----------

def test_sec_traversal():
    ws = AgentWorkspace("../../etc")
    assert ws.tarefa == "../../etc"  # string inerte
    assert ws.to_json()


def test_sec_strings():
    ws = AgentWorkspace("<script>alert(1)</script>")
    assert "<script>" in ws.tarefa
    ws.adicionar_no(AgentNode("__import__('os')", "ENTITY"))
    assert "__import__('os')" in ws.nos


def test_sec_eval():
    assert AgentNode("eval(1)", "ENTITY").id == "eval(1)"
    ws = AgentWorkspace("x")
    assert ws.buscar("eval") == []  # inerte, sem achados


def test_sec_exec():
    assert AgentEdge("a", "exec(x)", "b").tipo == "exec(x)"


def test_sec_pickle():
    import pickle  # noqa: checar ausência no módulo

    assert pickle.__name__ == "pickle"
    import elixx.studio.agent.workspace as modulo

    assert "pickle" not in open(modulo.__file__,
                                encoding="utf-8").read()


def test_sec_subprocess():
    import elixx.studio.agent.workspace as modulo

    assert "subprocess" not in open(modulo.__file__,
                                    encoding="utf-8").read()


def test_sec_sem_execucao():
    import elixx.studio.agent.workspace as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [pathlib.Path(modulo.__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess",
                         "os.system", "requests"):
            assert proibido not in fonte, proibido
    assert base.name == "agent"


# ---------- performance (87-89) ----------

def _modelo_grande(total):
    from elixx.studio.modelo import EntidadeSemantica

    m = ModeloSemantico("p")
    for i in range(total):
        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:05d}", "simbolo", f"S{i}"))
    return m


def _ws_grande(total):
    from elixx.studio.agent.contexto_tarefa import (
        ContextoConfig,
        ContextoTarefa,
        construir_contexto,
    )

    ws = AgentWorkspace("ver tudo")
    ctx = construir_contexto(
        _modelo_grande(total), ContextoTarefa(objetivo="ver"),
        ContextoConfig(max_entidades=total,
                       max_por_categoria=total,
                       max_bytes=10_000_000))
    ws.carregar_contexto(ctx)
    return ws


def test_perf_nos():
    import time as _t

    for total in (100, 500, 1000, 5000, 10000):
        t0 = _t.perf_counter()
        ws = _ws_grande(total)
        assert len(ws.nos) == total
        dt = _t.perf_counter() - t0
        assert dt < 60.0
        if total == 10000:
            print(f"\n10000 nos: {dt:.2f}s")


def test_perf_layout_selecao():
    import time as _t

    ws = _ws_grande(1000)
    t0 = _t.perf_counter()
    ws.layout()
    ws.selecionar("ctx:s:00500")
    ws.buscar("s:00")
    ws.filtrar(["ENTITY"])
    assert (_t.perf_counter() - t0) < 30.0


# ---------- determinismo (90-91) ----------

def test_determinismo():
    def montar():
        ws = AgentWorkspace("fazer Juh acenar",
                            sessao_id="fixa")
        ws.carregar_contexto(ctx_base())
        ws.layout()
        return ws.to_json()

    assert montar() == montar()


def test_determinismo_layout():
    def montar():
        ws = ws_com_contexto()
        ws.layout(dx=100.0, dy=50.0)
        return [(nid, n.x, n.y) for nid, n in sorted(
            ws.nos.items())]

    assert montar() == montar()


# ---------- headless/regressão (92-96) ----------

def test_headless():
    import elixx.studio.agent.workspace as modulo
    import pathlib

    for arq in pathlib.Path(modulo.__file__).parent.glob(
            "workspace.py"):
        for linha in arq.read_text(encoding="utf-8").splitlines():
            assert not linha.startswith("import tkinter")
            assert not linha.startswith("from tkinter")


def test_regressao_f25():
    from elixx.studio import EventBus

    bus = EventBus()
    bus.emitir("node_selected", {"id": "x"})
    assert bus.eventos_emitidos() == ["node_selected"]
    bus.emitir("selecionado", {})
    assert len(bus.eventos_emitidos()) == 2


def test_regressao_f34():
    from elixx.studio.agent.contexto_tarefa import (
        ContextoTarefa,
        construir_contexto,
    )

    r = construir_contexto(
        modelo_base(),
        ContextoTarefa(objetivo="ver", alvo="Juh"))
    assert r.entidades[0].id == "personagem:Juh"


def test_regressao_imports():
    from elixx.studio.agent import (
        AgentNode,
        AgentWorkspace,
    )

    assert AgentWorkspace("x").estado == "IDLE"
    assert AgentNode("n", "TASK").tipo == "TASK"


def test_transicoes_tabela():
    from elixx.studio.agent.workspace import ESTADOS, _TRANSICOES

    assert set(_TRANSICOES) == set(ESTADOS)
    for origem, destinos in _TRANSICOES.items():
        for d in destinos:
            assert d in ESTADOS


def test_plano_sem_construir():
    from elixx.studio.agent.planejamento import PlanoTarefa
    from elixx.studio.agent.operacoes import SemanticOperation

    ws = AgentWorkspace("x")
    t = PlanoTarefa("x", [SemanticOperation("pose", "Juh", {})])
    with pytest.raises(ErroELiXX):
        ws.carregar_plano(t)


def test_operacoes_multiplas():
    from elixx.studio.agent.operacoes import SemanticOperation

    ws = AgentWorkspace("x")
    out = ws.carregar_operacoes(
        [SemanticOperation("pose", "Juh", {}),
         SemanticOperation("mostrar", "Juh", {})])
    assert out == {"operacoes": 2}


def test_bus_silencioso():
    from elixx.studio import EventBus

    ws = ws_com_contexto()
    ws.acoplar_bus(EventBus())  # sem node_selected: segue
    assert ws.selecionar("ctx:personagem:Juh")["id"] == \
        "ctx:personagem:Juh"


def test_expandir_sem_source():
    ws = AgentWorkspace("x")
    ws.adicionar_no(AgentNode("n", "ENTITY", "x"))
    assert ws.expandir("n") == {"expandido": True, "novos": 0}


def test_zoom_cadeia():
    ws = AgentWorkspace("x")
    assert ws.aproximar() == 1.5
    assert ws.aproximar() == 2.0
    assert ws.afastar() == 1.5
    assert ws.normalizar_zoom() == 1.0


def test_pan_acumula():
    ws = AgentWorkspace("x")
    ws.mover_pan(5, 5)
    assert ws.mover_pan(-5, -5) == [0.0, 0.0]


def test_filtros_limpar():
    ws = ws_com_contexto()
    ws.filtrar(["ENTITY"])
    assert ws.filtrar([]) == []
    assert len(ws.visiveis()) == len(ws.nos)


def test_busca_maiusculas():
    ws = ws_com_contexto()
    assert {a["id"] for a in ws.buscar("JUH")} >= \
        {"ctx:personagem:Juh"}


def test_historico_vazio():
    ws = AgentWorkspace("x")
    assert ws.historico() == []
    assert ws.encerrar_sessao()["estado"] == "IDLE"


def test_importar_historico():
    from elixx.studio.agent import AgentHistory, AgentTask

    ws = AgentWorkspace("x")
    hist = AgentHistory()
    t = AgentTask("fazer X")
    t.transitar("concluida")
    hist.registrar(t)
    assert ws.importar_historico(hist) == 1
    assert ws.historico()[0]["resumo"] == "via AgentHistory F26"


def test_diagnosticar_limitada():
    ws = AgentWorkspace("x")
    for i in range(150):
        ws.adicionar_no(AgentNode(f"n{i:03d}", "ENTITY"))
    diag = ws.diagnosticar()
    assert diag["limitada"] is True
    assert diag["nos_analisados"] == 150


def test_workflow_task_dados():
    ws = AgentWorkspace("pedido Y")
    ws.marcar_estagio("TASK", "processando", {"pedido": "Y"})
    assert ws.estagios["TASK"]["dados"] == {"pedido": "Y"}
