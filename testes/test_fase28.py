"""Testes da Fase 28 — Semantic Agent Loop (ponte F26↔F27, sem LLM)."""
import json

import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent import (
    AgentContext,
    AgentIntent,
    Approval,
    ChangeSet,
    MockAgentProvider,
    PermissionSet,
)
from elixx.studio.agent.loop import (
    PlanoSemantico,
    SemanticContext,
    consultar_modelo,
    construir_contexto_semantico,
    diff_legivel,
    executar_loop,
    gerar_changeset,
    reanalisar_modelo,
    resolver_alvo,
    verificar_precondicoes,
)
from elixx.studio.modelo import (
    ModeloSemantico,
    analisar_projeto,
    analisar_texto,
)

FONTE = (
    "janela p {\n"
    ' titulo: "T"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    '   imagem: "corpo.png"\n'
    "  }\n"
    "  pose neutra {\n"
    "   corpo:\n"
    "    rotacao: 0deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


def modelo_juh():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    return m


def app_tmp(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "proj", "Loja")
    (tmp_path / "proj" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    return app


def perms_tudo():
    return PermissionSet(["READ", "WRITE", "RENAME", "DELETE",
                          "VALIDATE", "COMPILE", "PREVIEW"])


def pedido_novo():
    return {
        "objetivo": "adicionar tela ajuda",
        "nome": "Juh",
        "tipo_alvo": "personagem",
        "intencao": {"tipo": "criar_cena",
                     "objetivo": "ajuda"},
        "alteracoes": [{"arquivo": "src/ajuda.elixx",
                        "operacao": "criar",
                        "conteudo_novo":
                        "janela q {\n titulo: \"Q\"\n}\n",
                        "descricao": "tela ajuda",
                        "risco": "baixo"}],
    }


# ---------- CONTEXTO (1-6) ----------

def test_ctx_vazio():
    ctx = SemanticContext()
    assert ctx.to_dict() == {"entidades": [], "relacoes": [],
                             "arquivos": [], "origem": "modelo"}
    assert ctx.to_json()


def test_ctx_com_entidades():
    m = modelo_juh()
    ctx = construir_contexto_semantico(m, ["personagem:Juh"])
    assert any(e["id"] == "personagem:Juh"
               for e in ctx.entidades)
    assert any(r["tipo"] == "possui" for r in ctx.relacoes)
    assert ctx.arquivos == ["src/main.elixx"]


def test_ctx_serializacao():
    m = modelo_juh()
    ctx = construir_contexto_semantico(m, ["personagem:Juh"])
    copia = SemanticContext.from_dict(ctx.to_dict())
    assert copia.to_json() == ctx.to_json()
    with pytest.raises(ErroELiXX):
        SemanticContext.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        SemanticContext(entidades=["nao-dict"])


def test_ctx_limites():
    with pytest.raises(ErroELiXX):
        SemanticContext(entidades=[{"id": f"e{i}"}
                                   for i in range(201)])
    with pytest.raises(ErroELiXX):
        SemanticContext(relacoes=[{"a": 1}] * 501)


def test_ctx_sem_duplicadas():
    m = modelo_juh()
    ctx = construir_contexto_semantico(
        m, ["personagem:Juh", "personagem:Juh"])
    ids = [e["id"] for e in ctx.entidades]
    assert len(ids) == len(set(ids))


def test_ctx_multiplos_alvos():
    m = modelo_juh()
    ctx = construir_contexto_semantico(
        m, ["personagem:Juh", "janela:p"])
    assert {"personagem:Juh", "janela:p"} <= {e["id"] for e in
                                              ctx.entidades}


# ---------- CONSULTA (7-15) ----------

def test_consulta_id():
    m = modelo_juh()
    out = consultar_modelo(m, "id", id="personagem:Juh")
    assert out["total"] == 1
    assert out["resultados"][0]["nome"] == "Juh"
    vazio = consultar_modelo(m, "id", id="fantasma:x")
    assert vazio["total"] == 0  # nenhum resultado, sem erro


def test_consulta_nome():
    m = modelo_juh()
    out = consultar_modelo(m, "nome", nome="Juh")
    assert out["total"] == 1
    assert consultar_modelo(m, "nome",
                            nome="Ninguem")["total"] == 0


def test_consulta_tipo():
    m = modelo_juh()
    out = consultar_modelo(m, "tipo", tipo="parte")
    assert out["total"] == 1
    assert consultar_modelo(m, "tipo",
                            tipo="nave")["total"] == 0


def test_consulta_arquivo():
    m = modelo_juh()
    out = consultar_modelo(m, "arquivo", arquivo="src/main.elixx")
    assert out["total"] == len(m)
    assert consultar_modelo(m, "arquivo",
                            arquivo="outro.elixx")["total"] == 0


def test_consulta_relacoes():
    m = modelo_juh()
    de = consultar_modelo(m, "relacoes_de", id="personagem:Juh")
    para = consultar_modelo(m, "relacoes_para",
                            id="asset:corpo.png")
    assert de["total"] >= 2
    assert para["total"] == 1
    assert consultar_modelo(m, "relacoes_de",
                            id="fantasma")["total"] == 0


def test_consulta_entidade():
    m = modelo_juh()
    out = consultar_modelo(m, "entidade", id="personagem:Juh")
    assert out["total"] == 1
    assert out["resultados"][0]["entidade"]["nome"] == "Juh"


def test_consulta_multiplos():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, FONTE.replace("Juh", "Ana"), "src/b.elixx")
    out = consultar_modelo(m, "tipo", tipo="personagem")
    assert out["total"] == 2


def test_consulta_invalida():
    m = modelo_juh()
    with pytest.raises(ErroELiXX):
        consultar_modelo(m, "telepatia")
    with pytest.raises(ErroELiXX):
        consultar_modelo(m, 123)


def test_consulta_chama_f27():
    import elixx.studio.agent.loop as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "ConsultaSemantica" in fonte
    assert "class ConsultaSemantica" not in fonte  # sem duplicar


# ---------- AMBIGUIDADE / INEXISTENTE (16-18) ----------

def test_ambiguo():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao Juh(x) {\n retornar x\n}\n",
                   "src/b.elixx")
    out = resolver_alvo(m, "Juh")  # sem tipo: 2 candidatos
    assert out["status"] == "ambiguo"
    assert sorted(c["id"] for c in out["candidatos"]) == [
        "funcao:Juh", "personagem:Juh"]
    unico = resolver_alvo(m, "Juh", "personagem")
    assert unico["status"] == "unico"  # com tipo, desambigua


def test_ambiguo_sem_changeset(tmp_path):
    from elixx.studio.agent import Approval as _A

    app = app_tmp(tmp_path)
    (tmp_path / "proj" / "src" / "b.elixx").write_text(
        "janela p {\n titulo: \"T\"\n}\n"
        "funcao Juh(x) {\n retornar x\n}\n",
        encoding="utf-8")
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    pedido = pedido_novo()
    pedido.pop("tipo_alvo")  # sem tipo: ambíguo de verdade
    out = executar_loop(pedido, m, app.workspace,
                        approval=_A("automatico_seguro",
                                    caminhos_permitidos=["src/"]))
    assert out["status"] == "alvo_ambiguo"
    assert "changeset" not in out
    assert app.workspace.existe("src/ajuda.elixx") is False


def test_inexistente():
    m = modelo_juh()
    out = resolver_alvo(m, "Ana", "personagem")
    assert out == {"status": "nao_encontrado", "nome": "Ana",
                   "tipo": "personagem", "candidatos": []}
    out2 = resolver_alvo(m, "Juh", "nave")
    assert out2["status"] == "nao_encontrado"


def test_inexistente_sem_changeset(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    pedido = pedido_novo()
    pedido["nome"] = "Ana"
    out = executar_loop(pedido, m, app.workspace)
    assert out["status"] == "alvo_nao_encontrado"
    assert app.workspace.existe("src/ajuda.elixx") is False


def test_unico():
    out = resolver_alvo(modelo_juh(), "Juh")
    assert out["status"] == "unico"
    assert out["entidade"]["arquivo"] == "src/main.elixx"


# ---------- PLANEJAMENTO (19-24) ----------

def test_plano_intencao_valida():
    plano = PlanoSemantico(AgentIntent("criar_cena", objetivo="x"),
                           alvo={"status": "unico"})
    assert plano.alvo["status"] == "unico"
    assert plano.to_json()


def test_plano_alvo_existente():
    m = modelo_juh()
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(AgentIntent("modificar_personagem"),
                           alvo=alvo,
                           entidades=[alvo["entidade"]["id"]])
    assert plano.entidades == ["personagem:Juh"]


def test_plano_precondicoes_ok(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo=alvo,
        alteracoes_propostas=pedido_novo()["alteracoes"])
    pre = verificar_precondicoes(plano, app.workspace,
                                 perms_tudo())
    assert all(c["ok"] for c in pre)
    assert {c["nome"] for c in pre} >= {"alvo_existe",
                                       "arquivo_existe"}


def test_plano_precondicao_falha(tmp_path):
    app = app_tmp(tmp_path)
    plano = PlanoSemantico(
        AgentIntent("criar_cena"),
        alvo={"status": "nao_encontrado"},
        alteracoes_propostas=[{"arquivo": "../fora",
                               "operacao": "voar",
                               "conteudo_novo": "x" * 600_000}])
    pre = verificar_precondicoes(plano, app.workspace,
                                 PermissionSet(["READ"]))
    assert any(not c["ok"] for c in pre)
    with pytest.raises(ErroELiXX):
        gerar_changeset(plano)


def test_plano_deterministico():
    def montar():
        return PlanoSemantico(
            AgentIntent("criar_cena", objetivo="x"),
            alvo={"status": "unico"},
            alteracoes_propostas=[{"arquivo": "a",
                                   "operacao": "criar"}]).to_json()
    assert montar() == montar()


def test_plano_invalido():
    with pytest.raises(ErroELiXX):
        PlanoSemantico("nao-intencao")
    with pytest.raises(ErroELiXX):
        PlanoSemantico(AgentIntent("diagnosticar"),
                       alvo={"status": "talvez"})
    with pytest.raises(ErroELiXX):
        PlanoSemantico(AgentIntent("diagnosticar"),
                       alteracoes_propostas=["nao-dict"])


# ---------- CHANGESET (25-30) ----------

def test_changeset_geracao(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo=alvo,
        alteracoes_propostas=pedido_novo()["alteracoes"])
    verificar_precondicoes(plano, app.workspace, perms_tudo())
    cs = gerar_changeset(plano)
    assert isinstance(cs, ChangeSet)
    assert cs.revisar()[0]["caminho"] == "src/ajuda.elixx"


def test_changeset_conteudo(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo=alvo,
        alteracoes_propostas=pedido_novo()["alteracoes"])
    verificar_precondicoes(plano, app.workspace, perms_tudo())
    cs = gerar_changeset(plano)
    assert "janela q" in cs.mudancas[0].conteudo_novo


def test_changeset_reusa_f26():
    import elixx.studio.agent.loop as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class ChangeSet" not in fonte
    assert "class Approval" not in fonte
    assert "from .mudancas import" in fonte


def test_changeset_operacao_invalida(tmp_path):
    app = app_tmp(tmp_path)
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo={"status": "unico"},
        alteracoes_propostas=[{"arquivo": "a",
                               "operacao": "voar"}])
    pre = verificar_precondicoes(plano, app.workspace,
                                 perms_tudo())
    assert any(c["nome"] == "operacao_0" and not c["ok"]
               for c in pre)


def test_changeset_sem_alteracoes():
    plano = PlanoSemantico(AgentIntent("diagnosticar"),
                           alvo={"status": "unico"})
    plano.precondicoes = []
    with pytest.raises(ErroELiXX):
        gerar_changeset(plano)


# ---------- APROVAÇÃO (31-33) ----------

def test_nao_aprovado(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    out = executar_loop(pedido_novo(), m, app.workspace,
                        approval=Approval("manual"))
    assert out["status"] == "aguardando_aprovacao"
    assert out["changeset"][0]["caminho"] == "src/ajuda.elixx"
    assert app.workspace.existe("src/ajuda.elixx") is False


def test_aprovado_manual(tmp_path):
    from elixx.studio.agent import Approval as _A

    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    # manual pré-aprovado fora do loop, depois reexecuta o resto
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo=alvo,
        alteracoes_propostas=pedido_novo()["alteracoes"])
    verificar_precondicoes(plano, app.workspace, perms_tudo())
    cs = gerar_changeset(plano)
    _A("manual").aprovar_tudo(cs)
    cs.aplicar(app.workspace)
    assert app.workspace.existe("src/ajuda.elixx") is True
    cs.desfazer(app.workspace)
    assert app.workspace.existe("src/ajuda.elixx") is False


def test_rejeitado_bloqueado(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    out = executar_loop(pedido_novo(), m, app.workspace,
                        approval=Approval("bloqueado"))
    assert out["status"] == "aprovacao_recusada"
    assert app.workspace.existe("src/ajuda.elixx") is False


# ---------- APLICAÇÃO (34-36) ----------

def test_aplicacao_f26(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    out = executar_loop(
        pedido_novo(), m, app.workspace,
        approval=Approval("automatico_seguro",
                          caminhos_permitidos=["src/"]))
    assert out["status"] == "concluida"
    assert out["aplicadas"]["arquivos"] == ["src/ajuda.elixx"]


def test_aplicacao_validacao(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    pedido = pedido_novo()
    pedido["alteracoes"][0]["conteudo_novo"] = "janela p { titulo: "
    out = executar_loop(
        pedido, m, app.workspace,
        approval=Approval("automatico_seguro",
                          caminhos_permitidos=["src/"]))
    assert out["status"] == "concluida_com_erros"
    assert out["resultado"]["sucesso"] is False


def test_aplicacao_rollback(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    pedido = pedido_novo()
    pedido["alteracoes"].append({"arquivo": "src/fantasma.elixx",
                                 "operacao": "editar",
                                 "conteudo_novo": "x"})
    out = executar_loop(
        pedido, m, app.workspace,
        approval=Approval("automatico_seguro",
                          caminhos_permitidos=["src/"]))
    assert out["status"] == "aplicacao_falhou"
    assert app.workspace.existe("src/ajuda.elixx") is False


# ---------- REANÁLISE (37-40) ----------

def test_reanalise(tmp_path):
    from elixx.studio.modelo import atualizar_arquivo as _at

    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    n_antes = len(m)
    (tmp_path / "proj" / "src" / "extra.elixx").write_text(
        "janela q {\n titulo: \"Q\"\n}\n", encoding="utf-8")
    out = reanalisar_modelo(m, app.workspace, ["src/extra.elixx"])
    assert out["atualizados"] == ["src/extra.elixx"]
    assert len(m) == n_antes + 1
    assert out["diff"]["adicionados"] == ["janela:q"]
    _ = _at


def test_reanalise_remove(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    (tmp_path / "proj" / "src" / "main.elixx").write_text(
        "janela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    out = reanalisar_modelo(m, app.workspace, ["src/main.elixx"])
    assert "personagem:Juh" in out["diff"]["removidos"]
    assert "personagem:Juh" not in m


def test_reanalise_reflete(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    out = executar_loop(
        pedido_novo(), m, app.workspace,
        approval=Approval("automatico_seguro",
                          caminhos_permitidos=["src/"]))
    assert "+ janela:q" in out["diff_legivel"]
    assert "janela:q" in m  # modelo atualizado de verdade


# ---------- SEGURANÇA (41-49) ----------

def test_sec_traversal(tmp_path):
    app = app_tmp(tmp_path)
    m = modelo_juh()
    for ruim in ("../fora.elixx", "..\\fora.elixx", "C:\\x.elixx",
                 "/etc/x.elixx"):
        with pytest.raises(ErroELiXX):
            reanalisar_modelo(m, app.workspace, [ruim])
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo={"status": "unico"},
        alteracoes_propostas=[{"arquivo": "../fora",
                               "operacao": "criar"}])
    pre = verificar_precondicoes(plano, app.workspace,
                                 perms_tudo())
    assert any(not c["ok"] for c in pre)


def test_sec_payload(tmp_path):
    app = app_tmp(tmp_path)
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo={"status": "unico"},
        alteracoes_propostas=[{"arquivo": "a",
                               "operacao": "criar",
                               "conteudo_novo": "x" * 600_000}])
    pre = verificar_precondicoes(plano, app.workspace,
                                 perms_tudo())
    assert any(c["nome"] == "conteudo_0" and not c["ok"]
               for c in pre)


def test_sec_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    with pytest.raises(ErroELiXX):
        SemanticContext(entidades=[fundo])
    with pytest.raises(ErroELiXX):
        PlanoSemantico(AgentIntent("diagnosticar"),
                       alteracoes_propostas=[fundo])


def test_sec_strings():
    m = modelo_juh()
    out = resolver_alvo(m, "__import__('os')")
    assert out["status"] == "nao_encontrado"
    out2 = consultar_modelo(m, "nome", nome="<script>")
    assert out2["total"] == 0
    pedido = {"objetivo": "eval(x)", "nome": "Juh",
              "alteracoes": []}
    assert json.dumps(pedido)


def test_sec_sem_execucao():
    import elixx.studio.agent.loop as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [modulo.__file__]:
        fonte = open(arq, encoding="utf-8").read()
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "subprocess", "pickle",
                         "os.system"):
            assert proibido not in fonte, proibido
    assert base.name == "agent"


def test_sec_permissao_negada(tmp_path):
    app = app_tmp(tmp_path)
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "proj")
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        AgentIntent("criar_cena"), alvo=alvo,
        alteracoes_propostas=pedido_novo()["alteracoes"])
    pre = verificar_precondicoes(plano, app.workspace,
                                 PermissionSet(["READ"]))
    assert any(c["nome"] == "permissao_0" and not c["ok"]
               for c in pre)


def test_sec_pedido_invalido(tmp_path):
    app = app_tmp(tmp_path)
    m = modelo_juh()
    with pytest.raises(ErroELiXX):
        executar_loop("nao-dict", m, app.workspace)
    with pytest.raises(ErroELiXX):
        executar_loop({"objetivo": object()}, m, app.workspace)


# ---------- PERFORMANCE (50-52) ----------

def test_perf_entidades():
    import time as _t

    from elixx.studio.modelo import EntidadeSemantica

    for total in (100, 1000, 5000):
        m = ModeloSemantico("p")
        for i in range(total):
            m.adicionar_entidade(EntidadeSemantica(
                f"s:{i:05d}", "simbolo", f"S{i}"))
        t0 = _t.perf_counter()
        alvo = resolver_alvo(m, "S42")
        ctx = construir_contexto_semantico(m, ["s:00042"])
        dt = _t.perf_counter() - t0
        assert alvo["status"] == "unico" and dt < 30.0
        assert ctx.to_json()
        if total == 5000:
            print(f"\n5000 ent: consulta+ctx={dt:.2f}s")


def test_perf_consultas():
    import time as _t

    m = modelo_juh()
    t0 = _t.perf_counter()
    for _ in range(1000):
        consultar_modelo(m, "tipo", tipo="personagem")
        consultar_modelo(m, "relacoes_de", id="personagem:Juh")
    assert (_t.perf_counter() - t0) < 30.0


# ---------- DETERMINISMO + REGRESSÃO (53-55) ----------

def test_determinismo():
    m = modelo_juh()
    a = construir_contexto_semantico(m, ["personagem:Juh"])
    b = construir_contexto_semantico(m, ["personagem:Juh"])
    assert a.to_json() == b.to_json()
    assert resolver_alvo(m, "Juh") == resolver_alvo(m, "Juh")


def test_regressao_f26():
    from elixx.studio.agent import AgentTask, ChangeSet

    t = AgentTask("x")
    assert t.estado == "criada"
    assert ChangeSet().validar()["codigo"] == "vazio"
    import elixx.studio.agent.tarefa as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "loop" not in fonte  # F26 intocado pela F28


def test_regressao_f27():
    from elixx.studio.modelo import ConsultaSemantica

    q = ConsultaSemantica(modelo_juh())
    assert [e.id for e in q.encontrar_por_nome("Juh")] == \
        ["personagem:Juh"]
    import elixx.studio.modelo.adaptador as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "executar_loop" not in fonte  # F27 intocado


def test_regressao_imports():
    from elixx.studio.agent import loop as _loop

    assert "PlanoSemantico" in dir(_loop)
    assert "executar_loop" in dir(_loop)
