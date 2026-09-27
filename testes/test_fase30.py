"""Testes da Fase 30 — Intelligence Provider (sem LLM, sem rede)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent import PermissionSet
from elixx.studio.agent.inteligencia import (
    ACOES_INTENT,
    AgentChat,
    IntentContext,
    IntelligenceProvider,
    MockIntentProvider,
    ProviderRegistry,
    contexto_de_intencao,
    explicar,
    intent_para_agentintent,
    intent_para_ferramentas,
    validar_intent,
)
from elixx.visual.ai_bridge import AIIntent, AIProvider


def intent(tipo="pose", alvo="Juh", params=None):
    return AIIntent.from_dict({
        "tipo": tipo, "personagem": alvo, "alvo": alvo,
        "parametros": params or {}})


def bruta(tipo, params):
    """AIIntent com parâmetros fora do from_dict (pós-construção)."""
    it = AIIntent.from_dict({"tipo": tipo, "personagem": "J",
                             "parametros": {}})
    it.parametros = params
    return it


# ---------- PROVIDER (1-7) ----------

def test_provider_criacao():
    p = IntelligenceProvider("teste")
    assert p.nome == "teste" and p.origem == "intelligence"
    assert isinstance(p, AIProvider)  # reuso F18, sem duplicar
    with pytest.raises(ErroELiXX):
        p.gerar_intencao(None, "oi")
    assert "PROVIDER_INDISPONIVEL" in str(p.indisponivel("x"))


def test_provider_mock_disponivel():
    p = MockIntentProvider()
    assert p.nome == "mock"


def test_provider_geracao():
    it = MockIntentProvider().gerar_intencao(None,
                                             "faça a Juh acenar")
    assert isinstance(it, AIIntent)
    assert it.tipo == "pose" and it.personagem == "Juh"


def test_provider_desconhecido():
    reg = ProviderRegistry()
    reg.registrar(MockIntentProvider())
    assert reg.listar() == ["mock"]
    assert reg.obter("mock").nome == "mock"
    with pytest.raises(ErroELiXX):
        reg.obter("local")
    with pytest.raises(ErroELiXX):
        reg.registrar(MockIntentProvider())  # duplicado
    with pytest.raises(ErroELiXX):
        reg.registrar("nao-provider")


def test_provider_invalido():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(None, "")
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(None, "x" * 2001)
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(None, 12345)


def test_provider_sem_duplicar():
    import elixx.studio.agent.inteligencia as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class AIIntent" not in fonte
    assert "class AIProvider" not in fonte
    assert "from ...visual.ai_bridge import" in fonte


# ---------- INTENT (8-20) ----------

def test_intent_mover():
    it = MockIntentProvider().gerar_intencao(
        None, "mova a Juh para a direita")
    assert (it.tipo, it.personagem,
            it.parametros) == ("mover", "Juh",
                               {"direcao": "direita"})


def test_intent_mostrar():
    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    assert it.tipo == "mostrar" and it.personagem == "Juh"


def test_intent_esconder():
    it = MockIntentProvider().gerar_intencao(None, "esconda a Juh")
    assert it.tipo == "esconder"


def test_intent_expressao():
    it = MockIntentProvider().gerar_intencao(
        None, "faça a Juh sorrir")
    assert it.tipo == "expressao"
    assert it.parametros == {"expressao": "sorrindo"}


def test_intent_pose():
    it = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    assert (it.tipo, it.parametros) == ("pose",
                                        {"pose": "acenar"})


def test_intent_selecionar():
    it = MockIntentProvider().gerar_intencao(
        None, "selecione a Juh")
    assert it.tipo == "selecionar"


def test_intent_consultar():
    it = MockIntentProvider().gerar_intencao(None, "o que é a Juh?")
    assert it.tipo == "consultar" and it.personagem == "Juh"


def test_intent_evento():
    it = MockIntentProvider().gerar_intencao(
        None, "quando clicar na Juh, faça ela acenar")
    assert it.tipo == "associar_evento"
    assert it.parametros == {"evento": "clique",
                             "efeito": "acenar"}


def test_intent_parametros():
    it = intent("mover", "Juh", {"direcao": "cima",
                                 "duracao": 500.0})
    assert validar_intent(it)["valido"] is True
    assert it.parametros["duracao"] == 500.0


def test_intent_serializacao():
    it = intent("pose", "Juh", {"pose": "acenar"})
    copia = AIIntent.from_json(it.to_json())
    assert copia.tipo == "pose" and copia.personagem == "Juh"
    assert "pose" in copia.to_dict()["parametros"]


def test_intent_acoes_tabela():
    assert set(ACOES_INTENT) >= {"mover", "mostrar", "esconder",
                                 "expressao", "pose", "selecionar",
                                 "consultar"}


# ---------- VALIDAÇÃO (21-28) ----------

def test_validacao_acao_invalida():
    it = AIIntent.from_dict({"tipo": "voar", "personagem": "Juh"})
    out = validar_intent(it)
    assert out == {"valido": False, "codigo": "acao_desconhecida",
                   "motivo": out["motivo"]}


def test_validacao_alvo_ausente():
    it = AIIntent.from_dict({"tipo": "pose"})
    out = validar_intent(it)
    assert out["codigo"] == "alvo_ausente"


def test_validacao_params_invalidos():
    it = intent("mover", "Juh", {"direcao": "narnia"})
    assert validar_intent(it)["codigo"] == "parametros_invalidos"
    it2 = bruta("pose", {"x": float("nan")})
    assert validar_intent(it2)["codigo"] == "parametros_invalidos"


def test_validacao_nan():
    it = bruta("pose", {"valor": float("nan")})
    assert validar_intent(it)["valido"] is False


def test_validacao_infinity():
    it = bruta("pose", {"valor": float("inf")})
    assert validar_intent(it)["valido"] is False


def test_validacao_payload():
    it = intent("consultar", "J",
                {f"p{i}": i for i in range(21)})
    assert validar_intent(it)["codigo"] == "payload_excedido"


def test_validacao_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    it = bruta("consultar", {"f": fundo})
    assert validar_intent(it)["valido"] is False


def test_validacao_nao_intent():
    assert validar_intent("nao-intent")["codigo"] == \
        "intencao_invalida"


# ---------- MOCK (29-35) ----------

def test_mock_suportados():
    p = MockIntentProvider()
    casos = [("mova a Juh para a esquerda", "mover"),
             ("mostre a Ana", "mostrar"),
             ("esconda o Bob", "esconder"),
             ("selecione a Juh", "selecionar"),
             ("faça a Juh sorrir", "expressao"),
             ("faça a Juh acenar", "pose"),
             ("quem é a Juh?", "consultar"),
             ("descreva a Juh", "consultar")]
    for pedido, tipo in casos:
        assert p.gerar_intencao(None, pedido).tipo == tipo, pedido


def test_mock_desconhecidos():
    p = MockIntentProvider()
    for pedido in ("faça a Juh voar até Saturno",
                   "Explique a teoria da relatividade",
                   "CTHULHU FHTAGN",
                   "mova para a direita"):
        with pytest.raises(ErroELiXX) as exc:
            p.gerar_intencao(None, pedido)
        assert "INTENT_NAO_SUPORTADA" in str(exc.value), pedido


def test_mock_determinismo():
    p = MockIntentProvider()
    a = p.gerar_intencao(None, "Faça a Juh Acenar").to_json()
    b = p.gerar_intencao(None, "Faça a Juh Acenar").to_json()
    assert a == b  # mesma entrada, mesma saída
    c = p.gerar_intencao(None, "faça a juh acenar").to_json()
    assert "juh" in c  # caixa do nome preservada (F27 case-sensitive)


def test_mock_portugues():
    p = MockIntentProvider()
    it = p.gerar_intencao(None, "MOVA A JUH PARA CIMA")
    assert (it.tipo, it.parametros) == ("mover",
                                        {"direcao": "cima"})


def test_mock_variacoes():
    p = MockIntentProvider()
    assert p.gerar_intencao(None,
                            "faça Juh sorrir").personagem == "Juh"
    assert p.gerar_intencao(
        None, "quando clicar em Juh, faça X acenar").tipo == \
        "associar_evento"


def test_mock_preserva_caixa():
    it = MockIntentProvider().gerar_intencao(None,
                                             "selecione a Juh")
    assert it.personagem == "Juh"  # para resolver no F27


# ---------- CONTEXTO (36-41) ----------

def test_contexto_vazio():
    ctx = IntentContext()
    assert ctx.to_dict()["entidades"] == []
    assert ctx.to_json()


def test_contexto_projeto():
    ctx = IntentContext(
        "Demo", "main.elixx",
        {"tipo": "personagem", "nome": "Juh"},
        [{"id": "personagem:Juh", "tipo": "personagem",
          "nome": "Juh", "segredo": "cortado"}])
    assert ctx.entidades[0] == {"id": "personagem:Juh",
                                "tipo": "personagem",
                                "nome": "Juh"}  # só permitidos
    assert ctx.selecionado["nome"] == "Juh"


def test_contexto_selecionada():
    d = contexto_de_intencao("P", "a.elixx",
                             {"nome": "Juh"}, [])
    assert d["selecionado"] == {"nome": "Juh"}
    assert d["acoes"] == list(ACOES_INTENT)


def test_contexto_limites():
    with pytest.raises(ErroELiXX):
        IntentContext(entidades=["nao-dict"])
    with pytest.raises(ErroELiXX):
        IntentContext(acoes=["voar"])
    with pytest.raises(ErroELiXX):
        IntentContext(selecionado={"f": object()})


def test_contexto_sanitizacao():
    ctx = IntentContext(
        "P", "", {},
        [{"id": "a", "tipo": "x", "token": "SEGREDO-123"}])
    assert "token" not in ctx.entidades[0]
    assert "SEGREDO-123" not in ctx.to_json()


# ---------- F28 (42-48) ----------

def modelo_juh():
    from elixx.studio.modelo import ModeloSemantico, analisar_texto

    m = ModeloSemantico("t")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n"
                      " personagem Juh {\n"
                      "  parte corpo {\n  }\n }\n}\n",
                   "src/main.elixx")
    return m


def test_f28_agentintent():
    from elixx.studio.agent import AgentIntent as _AI

    out = intent_para_agentintent(intent("pose", "Juh",
                                         {"pose": "acenar"}))
    assert isinstance(out, _AI)
    assert out.tipo == "modificar_personagem"
    assert out.parametros["alvo"] == "Juh"
    with pytest.raises(ErroELiXX):
        intent_para_agentintent(AIIntent.from_dict(
            {"tipo": "voar", "personagem": "Juh"}))


def test_f28_consulta():
    m = modelo_juh()
    it = intent("consultar", "Juh")
    assert intent_para_ferramentas(it) == []  # via loop, sem atalho
    from elixx.studio.agent.loop import resolver_alvo

    assert resolver_alvo(m, "Juh")["status"] == "unico"


def test_f28_plano():
    from elixx.studio.agent.loop import PlanoSemantico, resolver_alvo

    m = modelo_juh()
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        intent_para_agentintent(intent("pose", "Juh",
                                       {"pose": "acenar"})),
        alvo=alvo, entidades=[alvo["entidade"]["id"]])
    assert plano.alvo["status"] == "unico"


def test_f28_changeset(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import PermissionSet
    from elixx.studio.agent.loop import (
        PlanoSemantico,
        gerar_changeset,
        resolver_alvo,
        verificar_precondicoes,
    )

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    m = modelo_juh()
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        intent_para_agentintent(intent("pose", "Juh",
                                       {"pose": "acenar"})),
        alvo=alvo,
        alteracoes_propostas=[{
            "arquivo": "src/main.elixx", "operacao": "editar",
            "conteudo_novo": "janela p {}\n"}])
    # main.elixx existe (criar_projeto) + WRITE: tudo OK aqui;
    # falha seria sem permissão ou alvo ausente (outros testes)
    pre = verificar_precondicoes(
        plano, app.workspace,
        PermissionSet(["READ", "WRITE", "VALIDATE"]))
    assert all(c["ok"] for c in pre)
    cs = gerar_changeset(plano)
    assert cs.revisar()[0]["caminho"] == "src/main.elixx"
    sem_permissao = verificar_precondicoes(
        plano, app.workspace, PermissionSet(["READ"]))
    assert any(not c["ok"] for c in sem_permissao)


def test_f28_aprovacao(tmp_path):
    from elixx.studio import StudioApp
    from elixx.studio.agent import Approval, PermissionSet
    from elixx.studio.agent.loop import (
        PlanoSemantico,
        gerar_changeset,
        resolver_alvo,
        verificar_precondicoes,
    )

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "L")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela p {}\n", encoding="utf-8")
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    m = ModeloSemantico("p")
    analisar_projeto(m, tmp_path / "p")
    (tmp_path / "p" / "src" / "j.elixx").write_text(
        "janela p {\n personagem Juh {\n  parte corpo {\n  }\n }\n}\n",
        encoding="utf-8")
    from elixx.studio.modelo import atualizar_arquivo

    atualizar_arquivo(m, "src/j.elixx",
                      (tmp_path / "p" / "src" / "j.elixx"
                       ).read_text(encoding="utf-8"))
    alvo = resolver_alvo(m, "Juh", "personagem")
    plano = PlanoSemantico(
        intent_para_agentintent(intent("pose", "Juh",
                                       {"pose": "acenar"})),
        alvo=alvo,
        alteracoes_propostas=[{
            "arquivo": "src/j.elixx", "operacao": "editar",
            "conteudo_novo": "janela p {}\n"}])
    verificar_precondicoes(plano, app.workspace,
                           PermissionSet(["WRITE"]))
    cs = gerar_changeset(plano)
    Approval("manual").aprovar_tudo(cs)
    out = cs.aplicar(app.workspace)
    assert out["arquivos"] == ["src/j.elixx"]
    cs.desfazer(app.workspace)


def test_f28_aplicacao_personagem():
    from elixx.studio.agent import PermissionSet, ToolRegistry
    from elixx.studio.agent import executar_ferramenta
    from elixx.studio.inspetor import fluxo_personagem

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"}])
    pos = perso.partes["tronco"].no
    chamadas = intent_para_ferramentas(
        intent("mover", "Juh", {"direcao": "direita",
                                "parte": "tronco"}),
        base={"posicao": [pos.x, pos.y]})
    assert chamadas[0]["ferramenta"] == "personagem_transform"
    reg = ToolRegistry(PermissionSet(["PREVIEW"]))
    out = executar_ferramenta(
        reg, "personagem_transform",
        dict(chamadas[0]["argumentos"],
             **{"personagem": "Juh"}),
        _AmbientePersonagem({"Juh": perso}))
    assert out["tocadas"] == ["tronco"]
    assert pos.x == 30.0  # relativo à base, sem chute


class _AmbientePersonagem:
    def __init__(self, personagens):
        self.personagens = dict(personagens)
        self.workspace = None
        self.contexto = None
        self.preview = None
        self.registro = None


# ---------- STUDIO (49-54) ----------

def test_studio_envio():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    resp = chat.enviar("faça a Juh acenar")
    assert resp["ok"] is True
    assert resp["intencao"]["acao"] == "pose"
    assert resp["mock"] is True


def test_studio_resposta():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    resp = chat.enviar("faça a Juh voar")
    assert resp["ok"] is False
    assert resp["codigo"] == "INTENT_FALHOU"


def test_studio_contexto():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    resp = chat.enviar("selecione a Juh", modelo_juh())
    assert resp["resolucao"]["status"] == "unico"


def test_studio_intencao():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    resp = chat.enviar("mostre a Juh", modelo_juh())
    assert resp["intencao"]["parametros"] == {}
    assert resp["explicacao"]["pedido"] == "mostre a Juh"


def test_studio_plano():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    resp = chat.enviar("o que é a Juh?", modelo_juh())
    assert resp["intencao"]["acao"] == "consultar"
    assert resp["explicacao"]["consulta"]["status"] == "unico"


def test_studio_proposta():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    chat.enviar("faça a Juh acenar")
    assert len(chat.historico) == 1
    assert chat.historico[0]["pedido"] == "faça a Juh acenar"


def test_studio_erro():
    from elixx.studio.agent.inteligencia import AgentChat

    chat = AgentChat()
    resp = chat.enviar("")
    assert resp["ok"] is False


# ---------- SEGURANÇA (55-62) ----------

def test_sec_eval():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(None, "eval(1+1)")


def test_sec_exec():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "exec(open('x').read())")


def test_sec_importlib():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "importlib.import_module('os')")


def test_sec_pickle():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "pickle.loads(dados)")


def test_sec_subprocess():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "subprocess.call(['rm'])")


def test_sec_shell():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "os.system('format C:')")


def test_sec_traversal():
    it = MockIntentProvider().gerar_intencao(
        None, "selecione a Juh")
    assert validar_intent(it)["valido"] is True
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "selecione ../../../etc/passwd")


def test_sec_urls():
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "abra https://evil.example/x")


def test_sec_strings():
    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    assert "__import__" not in it.to_json()
    with pytest.raises(ErroELiXX):
        MockIntentProvider().gerar_intencao(
            None, "__import__('os').system('x')")


def test_sec_sem_execucao():
    import elixx.studio.agent.inteligencia as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [pathlib.Path(modulo.__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "subprocess", "pickle",
                         "os.system", "requests", "urlopen"):
            assert proibido not in fonte, proibido
    assert base.name == "agent"


# ---------- PERFORMANCE (63-64) ----------

def test_perf_intents():
    import time as _t

    p = MockIntentProvider()
    t0 = _t.perf_counter()
    for i in range(1000):
        it = p.gerar_intencao(None, "faça a Juh acenar")
        assert validar_intent(it)["valido"] is True
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_entidades():
    import time as _t

    from elixx.studio.agent.loop import (
        construir_contexto_semantico,
        resolver_alvo,
    )
    from elixx.studio.modelo import EntidadeSemantica, ModeloSemantico

    for total in (100, 1000, 5000):
        m = ModeloSemantico("p")
        for i in range(total):
            m.adicionar_entidade(EntidadeSemantica(
                f"personagem:P{i:04d}", "personagem",
                f"P{i:04d}"))
        t0 = _t.perf_counter()
        assert resolver_alvo(m, "P0042")["status"] == "unico"
        construir_contexto_semantico(m, ["personagem:P0042"])
        assert (_t.perf_counter() - t0) < 30.0


# ---------- REGRESSÃO (65-66) ----------

def test_regressao_f18():
    from elixx.visual.ai_bridge import AIIntent as _AI
    from elixx.visual.ai_bridge import AIProvider as _AP

    it = _AI.from_dict({"tipo": "mover", "personagem": "Juh"})
    assert it.tipo == "mover"
    assert _AP("x").nome == "x"
    import elixx.visual.ai_bridge as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "MockIntentProvider" not in fonte


def test_regressao_f26_f28():
    from elixx.studio.agent import MockAgentProvider
    from elixx.studio.agent.loop import consultar_modelo

    assert MockAgentProvider().disponivel() is True
    assert consultar_modelo(modelo_juh(), "nome",
                            nome="Juh")["total"] == 1
