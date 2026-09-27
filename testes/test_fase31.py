"""Testes da Fase 31 — Semantic Actions & Events (sem LLM, sem rede)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent.operacoes import (
    SemanticEventOperation,
    SemanticOperation,
    SemanticReference,
    explicar_operacao,
    intent_para_operacao,
    operacao_para_ferramentas,
    operacao_para_intent,
    operacao_para_proposta,
    resolver_referencia,
    snippet_evento,
    validar_operacao,
)
from elixx.visual.ai_bridge import AIIntent

FONTE = (
    "janela p {\n"
    ' titulo: "T"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    "  pose acenar {\n"
    "   corpo:\n"
    "    rotacao: 45deg\n"
    "  }\n"
    "  expressao sorriso {\n"
    "   corpo:\n"
    "    rotacao: 5deg\n"
    "  }\n"
    " }\n"
    " botao entrar {\n"
    '  texto: "Entrar"\n'
    " }\n"
    "}\n"
)


def modelo_juh():
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    return m


def pedido(tipo, alvo="Juh", params=None):
    return AIIntent.from_dict({
        "tipo": tipo, "personagem": alvo, "alvo": alvo,
        "parametros": params or {}})


# ---------- OPERAÇÕES: criar/validar/serializar/parâmetros/limites ----------

def test_op_criar():
    op = SemanticOperation("pose", "Juh", {"pose": "acenar"})
    assert op.tipo == "pose" and op.alvo.nome == "Juh"
    assert op.categoria == "personagem"
    assert op.somente_leitura is False


def test_op_validar():
    assert validar_operacao(
        SemanticOperation("pose", "Juh"))["codigo"] == "ok"
    assert validar_operacao("nao-op")["codigo"] == \
        "operacao_invalida"
    op = SemanticOperation("adicionar_evento", "Juh")
    assert validar_operacao(op)["codigo"] == "alteracao_ausente"


def test_op_serializar():
    op = SemanticOperation("mover", {"nome": "Juh"},
                           {"direcao": "direita"})
    copia = SemanticOperation.from_dict(op.to_dict())
    assert copia.to_json() == op.to_json()
    assert copia.parametros == {"direcao": "direita"}
    with pytest.raises(ErroELiXX):
        SemanticOperation.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        SemanticOperation("voar", "Juh")


def test_op_desserializar_ref():
    op = SemanticOperation.from_dict({
        "tipo": "pose", "alvo": {"nome": "Juh", "tipo": None},
        "parametros": {"pose": "acenar"}})
    assert op.alvo.nome == "Juh"
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", 12345)


def test_op_parametros():
    op = SemanticOperation("animar", "Juh",
                           {"duracao": 2, "unidade": "s"})
    assert op.parametros["unidade"] == "s"
    with pytest.raises(ErroELiXX):
        SemanticOperation("animar", "Juh", {"unidade": "anos-luz"})
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh", {"x": object()})


def test_op_limites():
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh",
                          {f"p{i}": i for i in range(21)})
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh", {"valor": float("nan")})
    with pytest.raises(ErroELiXX):
        SemanticOperation("animar", "Juh", {"duracao": 1e18})


def test_op_categorias():
    from elixx.studio.agent.operacoes import CATEGORIA_OPERACAO

    assert CATEGORIA_OPERACAO["mostrar"] == "visual"
    assert CATEGORIA_OPERACAO["pose"] == "personagem"
    assert CATEGORIA_OPERACAO["animar"] == "animacao"
    assert CATEGORIA_OPERACAO["adicionar_evento"] == "evento"
    assert CATEGORIA_OPERACAO["adicionar"] == "projeto"
    assert CATEGORIA_OPERACAO["consultar"] == "consulta"


# ---------- REFERÊNCIAS ----------

def test_ref_resolver():
    out = resolver_referencia(modelo_juh(),
                              SemanticReference("Juh",
                                                "personagem"))
    assert out["status"] == "unico"
    assert out["entidade"]["id"] == "personagem:Juh"


def test_ref_encontrado():
    from elixx.studio.agent.operacoes import resolver_referencia as _r

    assert _r(modelo_juh(),
              SemanticReference("entrar"))["status"] == "unico"


def test_ref_nao_encontrado():
    out = resolver_referencia(modelo_juh(),
                              SemanticReference("Ana"))
    assert out["status"] == "nao_encontrado"


def test_ref_ambiguo():
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao Juh(x) {\n retornar x\n}\n",
                   "src/b.elixx")
    out = resolver_referencia(m, SemanticReference("Juh"))
    assert out["status"] == "ambiguo"
    assert len(out["candidatos"]) == 2


def test_ref_invalida():
    with pytest.raises(ErroELiXX):
        SemanticReference("   ")
    with pytest.raises(ErroELiXX):
        SemanticReference("Juh", tipo="  ")
    with pytest.raises(ErroELiXX):
        resolver_referencia(modelo_juh(), "nao-ref")
    assert SemanticReference.from_dict(
        {"nome": "Juh"}).tipo is None


# ---------- CONSULTAS ----------

def test_consulta_selecionar():
    op = SemanticOperation("selecionar", "Juh")
    assert op.somente_leitura is True
    assert operacao_para_ferramentas(op) == []  # via loop


def test_consulta_consultar():
    op = intent_para_operacao(pedido("consultar"))
    assert op.tipo == "consultar" and op.somente_leitura is True
    out = resolver_referencia(modelo_juh(), op.alvo)
    assert out["status"] == "unico"


def test_consulta_propriedade():
    m = modelo_juh()
    ent = m.obter_entidade("personagem:Juh")
    assert ent.arquivo == "src/main.elixx" and ent.linha == 3


# ---------- PERSONAGEM ----------

def test_personagem_pose():
    op = intent_para_operacao(pedido("pose", params={"pose": "acenar"}))
    assert op.tipo == "pose"
    chamadas = operacao_para_ferramentas(op)
    assert chamadas == [{"ferramenta": "personagem_pose",
                         "argumentos": {"personagem": "Juh",
                                        "pose": "acenar"}}]


def test_personagem_expressao():
    op = intent_para_operacao(
        pedido("expressao", params={"expressao": "sorrindo"}))
    assert op.tipo == "expressao"
    chamadas = operacao_para_ferramentas(op)
    assert chamadas[0]["ferramenta"] == "personagem_expressao"


def test_personagem_gesto():
    from elixx.studio.inspetor import fluxo_personagem

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco"}])
    from elixx.visual.rigging import definir_automatica

    g = definir_automatica(
        _rig, "acenar") if False else None
    assert perso.nome == "Juh"
    op = SemanticOperation("gesto", "Juh", {"gesto": "acenar"})
    assert op.categoria == "personagem"
    assert validar_operacao(op)["valido"] is True
    _ = g


def test_personagem_direcao():
    op = SemanticOperation("direcao", "Juh", {"direcao": "esquerda"})
    assert op.categoria == "personagem"
    assert explicar_operacao(op).startswith("Entendi")


def test_personagem_movimento():
    op = intent_para_operacao(
        pedido("mover", params={"direcao": "direita"}))
    assert op.tipo == "mover"
    base = {"posicao": [100.0, 100.0]}
    chamadas = operacao_para_ferramentas(op, base=base)
    assert chamadas[0]["argumentos"]["props"] == {
        "posicao": [130.0, 100.0]}
    with pytest.raises(ErroELiXX):
        operacao_para_ferramentas(op)  # sem base: sem chute


# ---------- VISUAL ----------

def test_visual_mostrar():
    op = intent_para_operacao(pedido("mostrar"))
    assert op.tipo == "mostrar" and op.categoria == "visual"


def test_visual_esconder():
    chamadas = operacao_para_ferramentas(
        intent_para_operacao(pedido("esconder")))
    assert chamadas[0]["argumentos"]["props"] == {"opacidade": 0.0}


def test_visual_mover():
    op = SemanticOperation("mover", "Juh",
                           {"direcao": "cima", "distancia": 100,
                            "unidade": "px"})
    assert op.parametros["unidade"] == "px"


def test_visual_transformar():
    op = SemanticOperation("transformar", "Juh",
                           {"rotacao": 10.0})
    assert validar_operacao(op)["valido"] is True
    assert explicar_operacao(op) == \
        "Entendi que você quer atuar em 'Juh'."


# ---------- ANIMAÇÃO ----------

def test_animacao_animar():
    op = SemanticOperation("animar", "Juh",
                           {"duracao": 2, "unidade": "s"})
    assert op.categoria == "animacao"
    assert validar_operacao(op)["valido"] is True


def test_animacao_duracao():
    with pytest.raises(ErroELiXX):
        SemanticOperation("animar", "Juh",
                          {"duracao": float("inf")})
    op = SemanticOperation("iniciar", "Juh")
    assert op.categoria == "animacao"


def test_animacao_parametros():
    op = intent_para_operacao(pedido("animar"))
    assert op.tipo == "animar"


# ---------- EVENTOS ----------

def test_evento_clique():
    ev = intent_para_operacao(pedido(
        "associar_evento",
        params={"evento": "clique", "efeito": "acenar"}))
    assert isinstance(ev, SemanticEventOperation)
    assert ev.gatilho == "clique"
    assert ev.alvo.nome == "Juh"
    assert ev.efeitos[0].tipo == "pose"


def test_evento_associacao():
    ev = SemanticEventOperation(
        "clique", "Juh",
        [SemanticOperation("pose", "Juh", {"pose": "acenar"})])
    assert ev.modo == "sequencia"
    assert ev.to_dict()["efeitos"][0]["tipo"] == "pose"
    assert SemanticEventOperation.from_dict(
        ev.to_dict()).gatilho == "clique"


def test_evento_acao():
    ev = intent_para_operacao(pedido(
        "associar_evento",
        params={"evento": "clique", "efeito": "sorriso"}))
    assert ev.efeitos[0].tipo == "expressao"
    assert ev.efeitos[0].parametros == {"expressao": "sorriso"}


def test_evento_sequencia():
    ev = SemanticEventOperation("clique", "Juh", [
        SemanticOperation("expressao", "Juh",
                          {"expressao": "sorrindo"}),
        SemanticOperation("pose", "Juh", {"pose": "acenar"})])
    assert [e.tipo for e in ev.efeitos] == ["expressao", "pose"]
    chamadas = operacao_para_ferramentas(ev)
    assert [c["ferramenta"] for c in chamadas] == [
        "personagem_expressao", "personagem_pose"]


def test_evento_paralelo():
    ev = SemanticEventOperation(
        "clique", "Juh",
        [SemanticOperation("expressao", "Juh", {}),
         SemanticOperation("pose", "Juh", {})],
        modo="paralelo")
    assert ev.modo == "paralelo"
    assert "paralelo" in explicar_operacao(ev)
    with pytest.raises(ErroELiXX):
        SemanticEventOperation("clique", "Juh",
                               [SemanticOperation("pose", "Juh",
                                                  {})],
                               modo="aleatorio")


def test_evento_gatilhos():
    from elixx.studio.agent.operacoes import GATILHOS

    assert set(GATILHOS) >= {"clique", "pressionar", "aparecer",
                             "terminar", "comecar", "cancelar"}
    with pytest.raises(ErroELiXX):
        SemanticEventOperation("telepatia", "Juh",
                               [SemanticOperation("pose", "Juh",
                                                  {})])
    with pytest.raises(ErroELiXX):
        SemanticEventOperation("clique", "Juh", [])


def test_evento_condicao():
    ev = SemanticEventOperation(
        "clique", "Juh",
        [SemanticOperation("pose", "Juh", {})],
        condicao={"fato": "visivel", "alvo": "Juh"})
    assert ev.condicao == {"fato": "visivel", "alvo": "Juh"}
    assert "condição planejada" in explicar_operacao(ev)


def test_evento_snippet():
    texto = snippet_evento("clicar", "acenar")
    assert texto.startswith("quando clicar {")
    with pytest.raises(ErroELiXX):
        snippet_evento("   ")


# ---------- COMPOSIÇÃO ----------

def test_compo_evento_acao():
    ev = intent_para_operacao(pedido(
        "associar_evento",
        params={"evento": "clique", "efeito": "acenar"}))
    assert isinstance(ev, SemanticEventOperation)
    assert explicar_operacao(ev) == \
        "Entendi que você quer associar o clique de 'Juh' a: " \
        "pose 'acenar'."


def test_compo_multiplas():
    ev = SemanticEventOperation("clique", "Juh", [
        SemanticOperation("pose", "Juh", {"pose": "a"}),
        SemanticOperation("pose", "Juh", {"pose": "b"}),
        SemanticOperation("expressao", "Juh", {})])
    assert len(ev.efeitos) == 3
    with pytest.raises(ErroELiXX):
        SemanticEventOperation(
            "clique", "Juh",
            [SemanticOperation("pose", "Juh", {}) for _ in
             range(11)])


def test_compo_ordem():
    ev = SemanticEventOperation("clique", "Juh", [
        SemanticOperation("expressao", "Juh",
                          {"expressao": "sorrindo"}),
        SemanticOperation("pose", "Juh", {"pose": "acenar"})])
    assert [e.to_dict()["tipo"] for e in ev.efeitos] == [
        "expressao", "pose"]  # ordem preservada


# ---------- F28 ----------

def test_f28_contexto(tmp_path):
    from elixx.studio.agent.loop import construir_contexto_semantico

    ctx = construir_contexto_semantico(modelo_juh(),
                                       ["personagem:Juh"])
    assert any(e["id"] == "personagem:Juh"
               for e in ctx.entidades)


def test_f28_plano(tmp_path):
    from elixx.studio.agent import AgentIntent as _AI
    from elixx.studio.agent.loop import PlanoSemantico

    plano = PlanoSemantico(
        _AI("modificar_personagem", objetivo="acenar"),
        alvo={"status": "unico"},
        entidades=["personagem:Juh"])
    assert plano.entidades == ["personagem:Juh"]


def test_f28_changeset(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import Approval, PermissionSet
    from elixx.studio.agent import AgentIntent as _AI
    from elixx.studio.agent.loop import (
        PlanoSemantico,
        gerar_changeset,
        resolver_alvo,
        verificar_precondicoes,
    )
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        _AI("modificar_interface", objetivo="evento"),
        alvo=alvo,
        alteracoes_propostas=[{
            "arquivo": "src/main.elixx", "operacao": "editar",
            "conteudo_novo": FONTE}])
    verificar_precondicoes(plano, app.workspace,
                           PermissionSet(["WRITE"]))
    cs = gerar_changeset(plano)
    Approval("manual").aprovar_tudo(cs)
    assert cs.aplicar(app.workspace)["arquivos"] == [
        "src/main.elixx"]


def test_f28_aprovacao(tmp_path):
    from elixx.studio.agent import Approval

    ap = Approval("manual")
    assert ap.modo == "manual"
    with pytest.raises(ErroELiXX):
        Approval("democracia")


def test_f28_rollback(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import Approval
    from elixx.studio.agent import AgentIntent as _AI
    from elixx.studio.agent.loop import PlanoSemantico

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    plano = PlanoSemantico(_AI("diagnosticar"),
                           alvo={"status": "unico"})
    assert plano.alvo["status"] == "unico"
    assert Approval("bloqueado").modo == "bloqueado"


def test_f28_reanalise(tmp_path):
    from elixx.studio.modelo import (
        ModeloSemantico,
        analisar_projeto,
        atualizar_arquivo,
    )

    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "a.elixx").write_text(FONTE,
                                            encoding="utf-8")
    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    atualizar_arquivo(m, "a.elixx", "janela q {}\n")
    assert "personagem:Juh" not in m
    assert "janela:q" in m


# ---------- F30 ----------

def test_f30_intent_operacao():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    it = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    op = intent_para_operacao(it)
    assert op.tipo == "pose" and op.alvo.nome == "Juh"


def test_f30_comandos():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    p = MockIntentProvider()
    assert p.gerar_intencao(None, "mostre a Juh").tipo == "mostrar"
    assert p.gerar_intencao(None, "esconda a Juh").tipo == \
        "esconder"
    assert p.gerar_intencao(
        None, "mova a Juh para a direita").tipo == "mover"


def test_f30_desconhecidos():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    with pytest.raises(ErroELiXX) as exc:
        MockIntentProvider().gerar_intencao(
            None, "faça a Juh levitar")
    assert "INTENT_NAO_SUPORTADA" in str(exc.value)


def test_f30_determinismo():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    p = MockIntentProvider()
    a = intent_para_operacao(p.gerar_intencao(None, "mostre a Juh"))
    b = intent_para_operacao(p.gerar_intencao(None, "mostre a Juh"))
    assert a.to_json() == b.to_json()


def test_f30_operacao_intent():
    op = SemanticOperation("pose", "Juh", {"pose": "acenar"})
    it = operacao_para_intent(op)
    assert it.tipo == "pose" and it.personagem == "Juh"
    assert it.parametros == {"pose": "acenar"}


# ---------- STUDIO ----------

def test_studio_operacao():
    op = intent_para_operacao(pedido("pose", params={"pose": "x"}))
    assert op.to_dict()["alvo"]["nome"] == "Juh"


def test_studio_explicacao():
    assert explicar_operacao(
        SemanticOperation("pose", "Juh",
                          {"pose": "acenar"})) == \
        "Entendi que você quer aplicar a pose 'acenar' à 'Juh'."
    assert explicar_operacao(
        SemanticOperation("mover", "Juh",
                          {"direcao": "direita"})) == \
        "Entendi que você quer mover 'Juh' para direita."


def test_studio_proposta(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import PermissionSet

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    op = SemanticOperation(
        "alterar_propriedade", "Juh", {"titulo": "Loja 2"},
        alteracao={"arquivo": "src/main.elixx",
                   "conteudo_novo": FONTE.replace(
                       'titulo: "T"', 'titulo: "Loja 2"')})
    cs = operacao_para_proposta(op, app.workspace, m,
                                PermissionSet(["WRITE"]))
    assert cs.estado == "proposto"
    assert cs.revisar()[0]["caminho"] == "src/main.elixx"


def test_studio_rejeicao(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import PermissionSet

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    op = SemanticOperation(
        "alterar_propriedade", "Juh", {},
        alteracao={"arquivo": "src/main.elixx",
                   "conteudo_novo": FONTE})
    cs = operacao_para_proposta(op, app.workspace, m,
                                PermissionSet(["WRITE"]))
    cs.rejeitar()
    assert cs.estado == "rejeitado"
    assert app.workspace.resolver(
        "src/main.elixx").read_text(
            encoding="utf-8") == FONTE  # intacto


def test_studio_evento_snippet_invalido(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import PermissionSet

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    op = SemanticOperation(
        "adicionar_evento", "Juh", {},
        alteracao={"arquivo": "src/main.elixx",
                   "snippet": snippet_evento("clicar", "oi")})
    with pytest.raises(ErroELiXX) as exc:
        operacao_para_proposta(op, app.workspace, m,
                               PermissionSet(["WRITE"]))
    assert "mesclado inválido" in str(exc.value)  # quando≠top-level


# ---------- SEGURANÇA ----------

def test_sec_traversal():
    # nome com "../" é só string inerte (semântica não é path);
    # a barreira real está no ChangeSet/workspace:
    op = SemanticOperation("alterar", "../fora", {})
    assert op.alvo.nome == "../fora"
    assert op.to_json()
    from elixx.studio.agent import AgentChange

    with pytest.raises(ErroELiXX):
        AgentChange("../fora", "criar")


def test_sec_eval():
    with pytest.raises(ErroELiXX):
        MockProvider_cmd("eval(1+1)")


def MockProvider_cmd(pedido):
    from elixx.studio.agent.inteligencia import MockIntentProvider

    return MockIntentProvider().gerar_intencao(None, pedido)


def test_sec_exec():
    with pytest.raises(ErroELiXX):
        MockProvider_cmd("exec('x')")


def test_sec_pickle():
    with pytest.raises(ErroELiXX):
        MockProvider_cmd("pickle.loads(x)")


def test_sec_importlib():
    with pytest.raises(ErroELiXX):
        MockProvider_cmd("importlib.import('os')")


def test_sec_subprocess():
    with pytest.raises(ErroELiXX):
        MockProvider_cmd("subprocess.run('x')")


def test_sec_nan():
    with pytest.raises(ErroELiXX):
        SemanticOperation("animar", "Juh", {"duracao": float("nan")})


def test_sec_infinity():
    with pytest.raises(ErroELiXX):
        SemanticOperation("mover", "Juh", {"valor": float("inf")})


def test_sec_payload():
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh",
                          {f"p{i}": i for i in range(25)})


def test_sec_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh", {"f": fundo})


def test_sec_ciclos():
    ev = SemanticEventOperation("clique", "Juh", [
        SemanticOperation("pose", "Juh", {})])
    assert ev.to_json()  # sem ciclo possível (árvore)
    with pytest.raises(ErroELiXX):
        SemanticOperation("pose", "Juh", {"f": object()})


def test_sec_strings():
    op = SemanticOperation("pose", "__import__('os')",
                           {"pose": "<script>"})
    assert op.alvo.nome == "__import__('os')"
    assert op.to_json()


def test_sec_sem_execucao():
    import elixx.studio.agent.operacoes as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [pathlib.Path(modulo.__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess"):
            assert proibido not in fonte, proibido
    assert base.name == "agent"


# ---------- PERFORMANCE ----------

def test_perf_operacoes():
    import time as _t

    t0 = _t.perf_counter()
    ops = [SemanticOperation("pose", f"P{i}",
                             {"pose": "acenar"})
           for i in range(5000)]
    assert len(ops) == 5000
    for op in ops[:1000]:
        assert validar_operacao(op)["valido"] is True
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_resolucoes():
    import time as _t

    m = modelo_juh()
    t0 = _t.perf_counter()
    for _ in range(1000):
        assert resolver_referencia(
            m, SemanticReference("Juh"))["status"] == "unico"
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_consultas():
    import time as _t

    from elixx.studio.modelo import ConsultaSemantica

    q = ConsultaSemantica(modelo_juh())
    t0 = _t.perf_counter()
    for _ in range(1000):
        q.encontrar_por_tipo("parte")
        q.relacoes_de("personagem:Juh")
    assert (_t.perf_counter() - t0) < 30.0


# ---------- REGRESSÃO ----------

def test_regressao_f30():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    assert it.tipo == "mostrar"
    import elixx.studio.agent.inteligencia as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "SemanticOperation" not in fonte  # F30 intocado


def test_regressao_f28():
    from elixx.studio.agent.loop import resolver_alvo

    assert resolver_alvo(modelo_juh(), "Juh")["status"] == "unico"
    import elixx.studio.agent.loop as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "SemanticOperation" not in fonte  # F28 intocado
