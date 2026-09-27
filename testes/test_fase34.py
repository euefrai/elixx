"""Testes da Fase 34 — Context Intelligence (sem LLM, sem rede)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent.contexto_tarefa import (
    ContextoConfig,
    ContextoEntidade,
    ContextoResultado,
    ContextoTarefa,
    carregar_preferencias,
    construir_contexto,
    ids_relevantes,
    salvar_preferencias,
)
from elixx.studio.modelo import ModeloSemantico, analisar_texto

FONTE = (
    "janela principal {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte cabeca {\n"
    "   rotacao: 0\n"
    "  }\n"
    "  parte olhos {\n"
    "  }\n"
    "  pose olhar {\n"
    "   cabeca:\n"
    "    rotacao: 10deg\n"
    "  }\n"
    " }\n"
    " botao comprar {\n"
    '  texto: "Comprar"\n'
    " }\n"
    "}\n"
)


def modelo_base():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/main.elixx")
    return m


def tarefa_juh():
    return ContextoTarefa(
        objetivo="fazer Juh olhar para o botao e depois acenar",
        alvo="Juh", entidade_selecionada="personagem:Juh",
        arquivo_atual="src/main.elixx",
        operacoes=["pose", "expressao"])


# ---------- criação de contexto (1-5) ----------

def test_criacao():
    t = ContextoTarefa(objetivo="x", alvo="Juh")
    assert t.objetivo == "x" and t.alvo == "Juh"
    assert t.to_dict()["operacoes"] == []


def test_criacao_invalida():
    with pytest.raises(ErroELiXX):
        ContextoTarefa(operacoes=["voar"])
    with pytest.raises(ErroELiXX):
        ContextoTarefa(orcamento={"x": object()})
    with pytest.raises(ErroELiXX):
        ContextoTarefa(profundidade=-1)
    with pytest.raises(ErroELiXX):
        ContextoTarefa(profundidade="funda")


def test_config():
    cfg = ContextoConfig()
    assert cfg.modo == "expandido" and cfg.max_entidades == 50
    copia = ContextoConfig.from_dict(cfg.to_dict())
    assert copia.to_dict() == cfg.to_dict()
    with pytest.raises(ErroELiXX):
        ContextoConfig(modo="total")
    with pytest.raises(ErroELiXX):
        ContextoConfig(max_entidades=-1)
    with pytest.raises(ErroELiXX):
        ContextoConfig.from_dict("nao-dict")


def test_config_orcamento_tarefa():
    t = ContextoTarefa(orcamento={"max_entidades": 3})
    r = construir_contexto(modelo_base(), t)
    assert len(r.entidades) <= 3


def test_entidade_classe():
    e = ContextoEntidade("a:b", "personagem", "B", "a.elixx",
                         0.5, ["motivo"], "PERSONAGEM", "auto")
    assert e.score == 0.5
    with pytest.raises(ErroELiXX):
        ContextoEntidade("  ")
    with pytest.raises(ErroELiXX):
        ContextoEntidade("a", categoria="NAVE")
    with pytest.raises(ErroELiXX):
        ContextoEntidade("a", origem="alien")
    with pytest.raises(ErroELiXX):
        ContextoEntidade("a", score="alta")


# ---------- entidades/relações/arquivos (6-10) ----------

def test_entidades():
    r = construir_contexto(modelo_base(), tarefa_juh())
    ids = {e.id for e in r.entidades}
    assert "personagem:Juh" in ids
    assert "parte:Juh.cabeca" in ids


def test_relacoes():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert any(x["tipo"] == "possui" for x in r.relacoes)
    for x in r.relacoes:
        assert x["origem"] in {e.id for e in r.entidades}
        assert x["destino"] in {e.id for e in r.entidades}


def test_relacoes_cortadas():
    cfg = ContextoConfig(max_relacoes=1)
    r = construir_contexto(modelo_base(), tarefa_juh(), cfg)
    assert len(r.relacoes) <= 1
    assert r.limites["cortadas_relacoes"] >= 0


def test_arquivos():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert r.arquivos == ["src/main.elixx"]


def test_recursos():
    r = construir_contexto(modelo_base(), tarefa_juh())
    tipos = {x["tipo"] for x in r.recursos}
    assert "pose" in tipos


# ---------- relevância/score/explicabilidade (11-16) ----------

def test_relevancia_alvo():
    r = construir_contexto(modelo_base(), tarefa_juh())
    topo = r.entidades[0]
    assert topo.id == "personagem:Juh" and topo.score == 1.00


def test_score_ordem():
    r = construir_contexto(modelo_base(), tarefa_juh())
    scores = [e.score for e in r.entidades]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.00 for s in scores)


def test_explicabilidade():
    r = construir_contexto(modelo_base(), tarefa_juh())
    motivos = r.por_que("personagem:Juh")
    assert "alvo explícito" in motivos
    assert len(motivos) >= 3
    with pytest.raises(ErroELiXX):
        r.por_que("fantasma:x")


def test_desempate():
    m = ModeloSemantico("t")
    analisar_texto(m, "janela p {\n botao a {\n }\n botao b {\n "
                      "}\n}\n", "src/a.elixx")
    t = ContextoTarefa(objetivo="ver botoes")
    r = construir_contexto(m, t)
    ids = [e.id for e in r.entidades
           if e.score == r.entidades[0].score]
    assert ids == sorted(ids)  # empate: id estável


def test_motivos_tipo():
    r = construir_contexto(modelo_base(), tarefa_juh())
    todos = [m for e in r.entidades for m in e.motivos]
    assert any("p/ ação" in m for m in todos)


# ---------- ordenação (17) ----------

def test_ordenacao_estavel():
    m = modelo_base()
    t = tarefa_juh()
    a = [e.id for e in construir_contexto(m, t).entidades]
    b = [e.id for e in construir_contexto(m, t).entidades]
    assert a == b


# ---------- expansão/profundidade (18-20) ----------

def test_expansao():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert "parte:Juh.olhos" in {e.id for e in r.entidades}


def test_profundidade_zero():
    t = ContextoTarefa(objetivo="ver Juh", alvo="Juh")
    t.profundidade = 0
    r = construir_contexto(modelo_base(), t)
    assert "personagem:Juh" in {e.id for e in r.entidades}
    # profundidade 0 = sem bônus de expansão; alvo segue no topo
    por_id = {e.id: e.score for e in r.entidades}
    assert por_id["personagem:Juh"] > por_id.get(
        "componente:principal.comprar", 0.0)


def test_profundidade_modos():
    cfg = ContextoConfig(modo="minimo")
    r = construir_contexto(modelo_base(), tarefa_juh(), cfg)
    assert len(r.entidades) >= 1
    with pytest.raises(ErroELiXX):
        ContextoTarefa(profundidade="funda")


# ---------- budget (21-24) ----------

def test_budget_entidades():
    cfg = ContextoConfig(max_entidades=2)
    r = construir_contexto(modelo_base(), tarefa_juh(), cfg)
    assert len(r.entidades) == 2
    assert r.limites["entidades"] == "2/2"
    assert len(r.excluidas) > 0
    assert r.excluidas[0]["motivo"] == "orçamento de entidades"


def test_budget_categoria():
    cfg = ContextoConfig(max_por_categoria=1)
    r = construir_contexto(modelo_base(), tarefa_juh(), cfg)
    from collections import Counter

    cont = Counter(e.categoria for e in r.entidades)
    assert all(v <= 1 for v in cont.values())


def test_budget_arquivos():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, FONTE.replace("Juh", "Ana"), "src/b.elixx")
    cfg = ContextoConfig(max_arquivos=1)
    r = construir_contexto(
        m, ContextoTarefa(objetivo="ver", alvo="Juh"), cfg)
    assert len(r.arquivos) == 1


def test_budget_bytes():
    cfg = ContextoConfig(max_bytes=10)
    with pytest.raises(ErroELiXX):
        construir_contexto(modelo_base(), tarefa_juh(), cfg)


# ---------- categorias (25-26) ----------

def test_categorias():
    r = construir_contexto(modelo_base(), tarefa_juh())
    cats = {e.categoria for e in r.entidades}
    assert {"ALVO", "PARTE"} <= cats
    from elixx.studio.agent.contexto_tarefa import CATEGORIAS

    assert set(CATEGORIAS) >= {"ALVO", "SUPORTE", "CENA",
                               "ASSET", "POSE"}


def test_categoria_alvo():
    r = construir_contexto(modelo_base(), tarefa_juh())
    alvos = [e for e in r.entidades if e.categoria == "ALVO"]
    assert alvos and alvos[0].id == "personagem:Juh"


# ---------- mínimo/expandido (27-28) ----------

def test_minimo():
    r = construir_contexto(modelo_base(), tarefa_juh(),
                           ContextoConfig(modo="minimo"))
    assert "personagem:Juh" in {e.id for e in r.entidades}


def test_expandido():
    r_min = construir_contexto(modelo_base(), tarefa_juh(),
                               ContextoConfig(modo="minimo"))
    r_exp = construir_contexto(modelo_base(), tarefa_juh(),
                               ContextoConfig(modo="expandido"))
    assert len(r_exp.entidades) >= len(r_min.entidades)


# ---------- ambiguidade (29-30) ----------

def test_ambiguidade():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao Juh(x) {\n retornar x\n}\n",
                   "src/b.elixx")
    r = construir_contexto(m, ContextoTarefa(objetivo="ver Juh",
                                             alvo="Juh"))
    assert r.ambiguidade["status"] == "ambiguo"
    assert len(r.ambiguidade["candidatos"]) == 2
    assert r.diagnostico["estado"] == "ambiguo"


def test_ambiguidade_sem_escolha():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, FONTE, "src/b.elixx")
    r = construir_contexto(
        m, ContextoTarefa(objetivo="ver", alvo="Juh"))
    # mesmo id deduplica entre arquivos: segue único, sem chute
    assert r.ambiguidade == {}
    assert r.entidades[0].id == "personagem:Juh"


# ---------- exclusões + manual (31-34) ----------

def test_exclusoes():
    cfg = ContextoConfig(max_entidades=2)
    r = construir_contexto(modelo_base(), tarefa_juh(), cfg)
    assert all("motivo" in e and "id" in e for e in r.excluidas)


def test_incluir_manual():
    t = tarefa_juh()
    t.incluir = ["componente:principal.comprar"]
    r = construir_contexto(modelo_base(), t)
    ent = next(e for e in r.entidades
               if e.id == "componente:principal.comprar")
    assert ent.origem == "manual"
    assert "INCLUIDO_MANUALMENTE" in ent.motivos
    assert r.diagnostico["overrides"]["inclusoes"] >= 1


def test_excluir_manual():
    t = tarefa_juh()
    t.excluir = ["personagem:Juh"]
    r = construir_contexto(modelo_base(), t)
    assert "personagem:Juh" not in {e.id for e in r.entidades}
    assert any(e["id"] == "personagem:Juh" and
               e["motivo"] == "EXCLUIDO_MANUALMENTE"
               for e in r.excluidas)


def test_override_invalido_ignorado():
    t = tarefa_juh()
    t.incluir = ["fantasma:x"]
    r = construir_contexto(modelo_base(), t)
    assert "fantasma:x" not in {e.id for e in r.entidades}


# ---------- seleção/arquivo (35-36) ----------

def test_selecao_studio():
    t = ContextoTarefa(objetivo="ver",
                       entidade_selecionada="personagem:Juh")
    r = construir_contexto(modelo_base(), t)
    assert "entidade selecionada" in r.por_que("personagem:Juh")


def test_arquivo_atual():
    t = ContextoTarefa(objetivo="ver",
                       arquivo_atual="src/main.elixx")
    r = construir_contexto(modelo_base(), t)
    assert any("arquivo atual" in m for e in r.entidades
               for m in e.motivos)


# ---------- integrações (37-42) ----------

def test_f27():
    from elixx.studio.modelo import ConsultaSemantica

    q = ConsultaSemantica(modelo_base())
    assert [e.id for e in q.encontrar_por_nome("Juh")] == \
        ["personagem:Juh"]
    import elixx.studio.agent.contexto_tarefa as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "class ModeloSemantico" not in fonte  # sem duplicar


def test_f30():
    from elixx.studio.agent.inteligencia import MockIntentProvider

    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    t = ContextoTarefa(objetivo="mostre a Juh",
                       alvo=it.personagem or "")
    r = construir_contexto(modelo_base(), t)
    assert r.entidades[0].id == "personagem:Juh"


def test_f31():
    from elixx.studio.agent.operacoes import intent_para_operacao
    from elixx.studio.agent.inteligencia import MockIntentProvider

    it = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    op = intent_para_operacao(it)
    t = ContextoTarefa(objetivo="acenar", alvo=op.alvo.nome,
                       operacoes=[op.tipo])
    r = construir_contexto(modelo_base(), t)
    assert "personagem:Juh" in {e.id for e in r.entidades}


def test_f33_ids():
    r = construir_contexto(modelo_base(), tarefa_juh())
    ids = ids_relevantes(r)
    assert ids[0] == "personagem:Juh"
    assert set(ids_relevantes(r, categoria="PARTE")) == {
        "parte:Juh.cabeca", "parte:Juh.olhos"}
    # menção ("olhar") também vira semente ALVO — sem chute
    assert set(ids_relevantes(r, categoria="ALVO")) == {
        "personagem:Juh", "pose:Juh.olhar"}
    with pytest.raises(ErroELiXX):
        ids_relevantes("nao-resultado")


def test_f32_arquivos():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert r.arquivos == ["src/main.elixx"]  # guia reanálise


def test_f33_planner_usa_contexto():
    from elixx.studio.agent.planejamento import PlanoTarefa
    from elixx.studio.agent.operacoes import SemanticOperation

    r = construir_contexto(modelo_base(), tarefa_juh())
    t = PlanoTarefa("ctx", [SemanticOperation("pose", "Juh",
                                              {})])
    assert t.objetivo == "ctx"
    assert set(ids_relevantes(r, "ALVO")) == {
        "personagem:Juh", "pose:Juh.olhar"}


# ---------- serialização/limites/segurança (43-50) ----------

def test_serializacao():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert r.to_json()
    dados = r.to_dict()
    for e in dados["entidades"]:
        e["ent_id"] = e.pop("id")
    copia = ContextoResultado(**dados)
    assert copia.to_json() == r.to_json()


def test_limites_info():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert r.limites["entidades"].endswith("/50")
    assert r.diagnostico["entidades_analisadas"] == 6


def test_seguranca_strings():
    r = construir_contexto(
        modelo_base(),
        ContextoTarefa(objetivo="__import__('os')",
                       alvo="<script>"))
    assert r.to_json()
    assert r.ambiguidade.get("status") in ("nao_encontrado",)


def test_seguranca_traversal():
    t = ContextoTarefa(arquivo_atual="../../etc/passwd")
    r = construir_contexto(modelo_base(), t)
    assert all(e.arquivo != "../../etc/passwd"
               for e in r.entidades)


def test_seguranca_payload():
    with pytest.raises(ErroELiXX):
        ContextoConfig(max_bytes=-1)
    t = ContextoTarefa(objetivo="x" * 2001)
    assert len(t.objetivo) == 2000  # teto silencioso e seguro


def test_seguranca_nan():
    with pytest.raises(ErroELiXX):
        ContextoEntidade("a", score=float("nan"))


def test_seguranca_recursao():
    fundo: dict = {}
    atual = fundo
    for _ in range(10):
        atual["n"] = {}
        atual = atual["n"]
    with pytest.raises(ErroELiXX):
        ContextoTarefa(orcamento=fundo)


def test_sem_execucao():
    import elixx.studio.agent.contexto_tarefa as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [pathlib.Path(modulo.__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess",
                         "os.system", "requests"):
            assert proibido not in fonte, proibido
    assert base.name == "agent"


# ---------- performance (51-53) ----------

def _modelo_grande(total):
    m = ModeloSemantico("p")
    for i in range(total):
        from elixx.studio.modelo import EntidadeSemantica

        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:05d}", "simbolo", f"S{i}", arquivo="a.elixx"))
    return m


def test_perf_construcao():
    import time as _t

    for total in (100, 500, 1000, 5000, 10000):
        m = _modelo_grande(total)
        t0 = _t.perf_counter()
        r = construir_contexto(
            m, ContextoTarefa(objetivo="ver S42", alvo="S42"))
        dt = _t.perf_counter() - t0
        assert r.entidades[0].id == "s:00042" and dt < 60.0
        if total == 10000:
            print(f"\n10000 ent: contexto={dt:.2f}s")


def test_perf_ordenacao():
    import time as _t

    m = _modelo_grande(5000)
    t0 = _t.perf_counter()
    for _ in range(5):
        construir_contexto(m, ContextoTarefa(objetivo="ver"))
    assert (_t.perf_counter() - t0) < 60.0


def test_perf_serializacao():
    import time as _t

    r = construir_contexto(modelo_base(), tarefa_juh())
    t0 = _t.perf_counter()
    for _ in range(200):
        r.to_json()
    assert (_t.perf_counter() - t0) < 30.0


# ---------- determinismo (54-56) ----------

def test_determinismo():
    m = modelo_base()
    t = tarefa_juh()
    assert construir_contexto(m, t).to_json() == \
        construir_contexto(m, t).to_json()


def test_determinismo_scores():
    m = modelo_base()
    a = [(e.id, e.score) for e in
         construir_contexto(m, tarefa_juh()).entidades]
    b = [(e.id, e.score) for e in
         construir_contexto(m, tarefa_juh()).entidades]
    assert a == b


def test_determinismo_motivos():
    m = modelo_base()
    a = construir_contexto(m, tarefa_juh()).por_que(
        "personagem:Juh")
    b = construir_contexto(m, tarefa_juh()).por_que(
        "personagem:Juh")
    assert a == b


# ---------- orçamento/diagnóstico/UX/persistência (57-64) ----------

def test_orcamento_diagnostico():
    r = construir_contexto(modelo_base(), tarefa_juh())
    d = r.diagnostico
    assert d["estado"] == "pronto"
    assert d["relacoes_analisadas"] >= 1
    assert d["overrides"] == {"inclusoes": 0, "exclusoes": 0}


def test_modo_completo():
    r = construir_contexto(modelo_base(), tarefa_juh(),
                           ContextoConfig(modo="completo"))
    assert len(r.entidades) == 6  # tudo, com teto respeitado


def test_filtros():
    r = construir_contexto(modelo_base(), tarefa_juh())
    partes = [e for e in r.entidades if e.categoria == "PARTE"]
    assert {e.id for e in partes} == {"parte:Juh.cabeca",
                                     "parte:Juh.olhos"}


def test_incluir_excluir_dados():
    t = ContextoTarefa(incluir=["a"], excluir=["b"])
    assert t.to_dict()["incluir"] == ["a"]
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert isinstance(r.to_dict()["excluidas"], list)


def test_ver_contexto_dados():
    r = construir_contexto(modelo_base(), tarefa_juh())
    ent = r.entidades[0]
    assert {"id", "tipo", "arquivo", "score"} <= set(
        ent.to_dict())
    assert r.to_dict()["ambiguidade"] == {}


def test_persistir_prefs(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    cfg = ContextoConfig(modo="minimo", max_entidades=10)
    rel = salvar_preferencias(app.workspace, cfg)
    assert rel == ".elixx/contexto.json"
    copia = carregar_preferencias(app.workspace)
    assert copia.to_dict() == cfg.to_dict()
    with pytest.raises(ErroELiXX):
        salvar_preferencias(app.workspace, "nao-config")


def test_carregar_ausente(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    assert carregar_preferencias(app.workspace).modo == \
        "expandido"


def test_selecao_atualiza(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    t = ContextoTarefa(
        objetivo="ver",
        entidade_selecionada="personagem:Juh")
    r = construir_contexto(ws.modelo, t)
    assert "entidade selecionada" in r.por_que("personagem:Juh")


# ---------- regressão (65-66) ----------

def test_regressao_f27():
    from elixx.studio.modelo import ConsultaSemantica

    q = ConsultaSemantica(modelo_base())
    assert [e.id for e in q.encontrar_por_nome("Juh")] == \
        ["personagem:Juh"]
    import elixx.studio.modelo.consulta as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "construir_contexto" not in fonte


def test_regressao_agent():
    from elixx.studio.agent import AgentContext, MockAgentProvider

    assert MockAgentProvider().disponivel() is True
    assert AgentContext("P").simbolos == []
    import elixx.studio.agent.contexto as nucleo

    fonte = open(nucleo.__file__, encoding="utf-8").read()
    assert "ContextoTarefa" not in fonte


def test_mesma_cena():
    r = construir_contexto(modelo_base(), tarefa_juh())
    botao = next(e for e in r.entidades
                 if e.id == "componente:principal.comprar")
    assert any("mesmo arquivo" in m for m in botao.motivos)


def test_pai_filha_motivos():
    r = construir_contexto(modelo_base(), tarefa_juh())
    cabeca = next(e for e in r.entidades
                  if e.id == "parte:Juh.cabeca")
    assert any("em personagem:Juh" in m for m in cabeca.motivos)
    juh = next(e for e in r.entidades
               if e.id == "personagem:Juh")
    assert any("possui" in m for m in juh.motivos)


def test_recurso_motivo():
    r = construir_contexto(modelo_base(), tarefa_juh())
    pose = next(e for e in r.entidades
                if e.id == "pose:Juh.olhar")
    assert "recurso pose" in pose.motivos


def test_transitiva_dist2():
    r = construir_contexto(modelo_base(), tarefa_juh())
    botao = next(e for e in r.entidades
                 if e.id == "componente:principal.comprar")
    assert any("2 passo(s)" in m for m in botao.motivos)


def test_operacao_compativel():
    t = ContextoTarefa(objetivo="mover", operacoes=["mover"])
    r = construir_contexto(modelo_base(), t)
    juh = next(e for e in r.entidades
               if e.id == "personagem:Juh")
    assert any("p/ ação" in m for m in juh.motivos)


def test_modelo_vazio():
    r = construir_contexto(ModeloSemantico("v"),
                           ContextoTarefa(objetivo="ver"))
    assert r.entidades == [] and r.diagnostico[
        "entidades_analisadas"] == 0


def test_sem_alvo_nem_semente():
    t = ContextoTarefa(objetivo="zzz")
    a = [(e.id, e.score) for e in
         construir_contexto(modelo_base(), t).entidades]
    b = [(e.id, e.score) for e in
         construir_contexto(modelo_base(), t).entidades]
    assert a == b  # determinístico mesmo sem sementes
    assert a == sorted(a, key=lambda p: (-p[1], p[0]))


def test_acentos():
    r = construir_contexto(
        modelo_base(),
        ContextoTarefa(objetivo="olhar o botão"))
    assert "componente:principal.comprar" in {
        e.id for e in r.entidades}


def test_prefs_json_ruim(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / ".elixx").mkdir(exist_ok=True)
    (tmp_path / "p" / ".elixx" / "contexto.json").write_text(
        "{ruim", encoding="utf-8")
    assert carregar_preferencias(app.workspace).modo == \
        "expandido"


def test_teto_relacoes_registrado():
    cfg = ContextoConfig(max_relacoes=2)
    r = construir_contexto(modelo_base(), tarefa_juh(), cfg)
    assert r.limites["relacoes"].endswith("/2")
    assert r.limites["cortadas_relacoes"] >= 0


def test_ambiguidade_candidatos():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE, "src/a.elixx")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao Juh(x) {\n retornar x\n}\n",
                   "src/b.elixx")
    r = construir_contexto(m, ContextoTarefa(objetivo="x",
                                             alvo="Juh"))
    ids = {c["id"] for c in r.ambiguidade["candidatos"]}
    assert ids == {"personagem:Juh", "funcao:Juh"}


def test_profundidade_override():
    t = tarefa_juh()
    t.profundidade = 5
    r = construir_contexto(modelo_base(), t,
                           ContextoConfig(max_profundidade=1))
    assert "componente:principal.comprar" in {
        e.id for e in r.entidades}  # tarefa vence config


def test_categoria_dependencia():
    from elixx.studio.agent.contexto_tarefa import CATEGORIAS

    assert "DEPENDENCIA" in CATEGORIAS
    e = ContextoEntidade("d:x", categoria="DEPENDENCIA")
    assert e.categoria == "DEPENDENCIA"


def test_tarefa_dict():
    t = tarefa_juh()
    d = t.to_dict()
    assert d["alvo"] == "Juh" and d["profundidade"] is None
    assert d["operacoes"] == ["pose", "expressao"]


def test_resultado_repr():
    r = construir_contexto(modelo_base(), tarefa_juh())
    assert repr(r).startswith("ContextoResultado(")
    assert repr(r.entidades[0]).startswith("ContextoEntidade(")
