"""Testes da Fase 19 — Environment Bridge + Structured Agent Runtime.

Determinísticos, stdlib, sem LLM, sem visão, sem código externo.
"""
import json
import math
import time
from types import SimpleNamespace

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.ambiente import (
    AIContextBuilder,
    Environment,
    EnvironmentBoundary,
    EnvironmentNode,
    EnvironmentRegion,
    EnvironmentSurface,
    InteractionDescriptor,
    InteractionExecutor,
    ambiente_de_dict,
    construir_grafo_de_ambiente,
    debug_ambiente,
    gerar_boundaries,
    gerar_surface,
    inferir_interacoes,
    vincular_ambiente,
)
from elixx.visual.mundo import Bounds2D
from elixx.visual.transform import Vector2


# ----- fábrica determinística -----

def ambiente_amostra():
    """Janela / Barra / Menu / Conteúdo / Painel / Botão."""
    env = Environment("env_demo", nome="Demo", tipo="web",
                      largura=800.0, altura=600.0)
    janela = EnvironmentNode("janela", nome="Janela", tipo="janela",
                             x=0, y=0, largura=800, altura=600)
    barra = EnvironmentNode("barra", nome="Barra superior", tipo="barra",
                            x=0, y=0, largura=800, altura=40)
    menu = EnvironmentNode("menu", nome="Menu lateral", tipo="menu",
                           x=0, y=40, largura=150, altura=560)
    inicio = EnvironmentNode("inicio", nome="Início", tipo="botao",
                             x=10, y=50, largura=130, altura=30,
                             interativo=True)
    config = EnvironmentNode("config", nome="Configurações", tipo="botao",
                             x=10, y=90, largura=130, altura=30,
                             interativo=True)
    perfil = EnvironmentNode("perfil", nome="Perfil", tipo="botao",
                             x=10, y=130, largura=130, altura=30,
                             interativo=True)
    conteudo = EnvironmentNode("conteudo", nome="Conteúdo", tipo="regiao",
                               x=150, y=40, largura=650, altura=560)
    painel = EnvironmentNode("painel", nome="Painel", tipo="painel",
                             x=170, y=60, largura=300, altura=150,
                             atributos={"superficie": True,
                                        "capacidades": ["andar"]})
    botao = EnvironmentNode("botao_ok", nome="Botão", tipo="botao",
                            x=180, y=70, largura=100, altura=30,
                            interativo=True)
    for no in (janela, barra, menu, inicio, config, perfil, conteudo,
               painel, botao):
        env.adicionar_no(no)
    janela.adicionar_filho(barra)
    janela.adicionar_filho(menu)
    janela.adicionar_filho(conteudo)
    menu.adicionar_filho(inicio)
    menu.adicionar_filho(config)
    menu.adicionar_filho(perfil)
    conteudo.adicionar_filho(painel)
    painel.adicionar_filho(botao)
    env.adicionar_regiao(EnvironmentRegion(
        "reg_menu", nome="menu", nos=["menu", "inicio", "config",
                                      "perfil"]))
    env.adicionar_regiao(EnvironmentRegion(
        "reg_conteudo", nome="conteúdo", nos=["conteudo", "painel",
                                              "botao_ok"]))
    sup = gerar_surface(painel)
    env.adicionar_superficie(sup)
    for limite in gerar_boundaries(painel):
        env.adicionar_limite(limite)
    for inter in inferir_interacoes(botao):
        try:
            env.adicionar_interacao(inter)
        except ErroELiXX:
            pass
    return env


# 1. Environment básico

def test_environment_basico():
    env = Environment("e1", nome="Site", tipo="web",
                      largura=1024, altura=768)
    assert env.id == "e1" and env.tipo == "web"
    assert (env.largura, env.altura) == (1024.0, 768.0)
    assert len(env) == 0
    with pytest.raises(ErroELiXX):
        Environment("e2", tipo="executavel_malicioso")


# 2. EnvironmentNode

def test_environment_node():
    no = EnvironmentNode("b1", nome="OK", tipo="botao", x=10, y=20,
                         largura=100, altura=30, interativo=True,
                         texto="OK", role="button")
    assert no.id == "b1" and no.interativo is True
    assert no.texto == "OK" and no.role == "button"


# 3. árvore pai/filho

def test_arvore_pai_filho():
    env = ambiente_amostra()
    assert env.obter_no("botao_ok").parent.id == "painel"
    assert [c.id for c in env.filhos_de("menu")] == ["inicio", "config",
                                                    "perfil"]
    assert env.validar()["valido"] is True


# 4. regiões

def test_regioes():
    env = ambiente_amostra()
    reg = env.regiao_por_id("reg_menu")
    assert reg.nome == "menu"
    assert env.regiao_por_nome("menu") == [reg]
    nos = env.nos_da_regiao("reg_menu")
    assert sorted(n.id for n in nos) == ["config", "inicio", "menu",
                                         "perfil"]


# 5. superfícies

def test_superficies():
    env = ambiente_amostra()
    sup = env._superficies["sup_painel"]
    assert sup.owner == "painel" and sup.tipo == "horizontal"
    assert sup.capacidades == ("andar",)
    assert sup.bloqueada is False and sup.navegavel() is True


# 6. boundaries

def test_boundaries():
    env = ambiente_amostra()
    limites = {l.lado: l for l in env._limites.values()
               if l.owner == "painel"}
    assert set(limites) >= {"topo", "base", "esquerda", "direita",
                            "externa"}
    assert limites["topo"].bounds().x == 170.0
    assert limites["base"].ponto().y == 210.0


# 7/8. geometria + derivados

def test_geometria_derivados():
    no = EnvironmentNode("g", tipo="caixa", x=100, y=200, largura=300,
                         altura=150)
    assert (no.left, no.right, no.top, no.bottom) == (100, 400, 200, 350)
    centro = no.center()
    assert isinstance(centro, Vector2)
    assert (centro.x, centro.y) == (250.0, 275.0)
    limites = no.bounds()
    assert isinstance(limites, Bounds2D)
    assert (limites.largura, limites.altura) == (300.0, 150.0)


# 9. interação

def test_interacao_descritor():
    no = EnvironmentNode("b", tipo="botao", x=0, y=0, largura=10,
                         altura=10, interativo=True)
    inters = inferir_interacoes(no)
    assert [i.tipo for i in inters] == ["clicar", "focar"]
    desc = inters[0]
    assert desc.alvo == "b"
    assert desc.validar_parametros({})["valido"] is True
    assert desc.validar_parametros({"x": 1})["codigo"] == \
        "parametro_desconhecido"


# 10. capabilities (reuso F14, sem duplicar)

def test_capabilities_reuso():
    import elixx.visual.ambiente as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class Capability" not in fonte
    assert "CapabilitySet" not in fonte
    env = ambiente_amostra()
    sup = env._superficies["sup_painel"]
    assert "andar" in sup.capacidades
    # executor exige capacidade do agente quando há requisito
    env.adicionar_interacao(InteractionDescriptor(
        "voar_painel", tipo="navegar", alvo="painel",
        requisitos=("voar",)))
    exe = InteractionExecutor(env)
    assert exe.validar("voar_painel", "painel",
                       agente={"nome": "a",
                               "capacidades": []})["codigo"] == \
        "capacidade_ausente"
    assert exe.validar("voar_painel", "painel",
                       agente={"nome": "a",
                               "capacidades": ["voar"]})["valido"] is True


# 11. Environment → World

def test_environment_para_world():
    env = ambiente_amostra()
    mundo = vincular_ambiente(env)
    assert "painel" in mundo and "botao_ok" in mundo
    painel = mundo.por_id("painel")
    assert painel.tipo == "plataforma"  # superfície horizontal navegável
    assert painel.props["env_tipo"] == "painel"
    assert painel.props["pai"] == "conteudo"
    limites = painel.bounds_global()
    assert (limites.x, limites.y) == (170.0, 60.0)
    assert "reg_menu" in mundo  # região virou área
    assert mundo.por_id("reg_menu").tipo == "area"


# 12. Environment → Navigation (sem pathfinding novo)

def test_environment_para_navegacao():
    import elixx.visual.ambiente as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "heapq" not in fonte and "Dijkstra" not in fonte
    env = ambiente_amostra()
    mundo = vincular_ambiente(env)
    grafo = construir_grafo_de_ambiente(mundo)
    assert "ent:painel" in grafo.nos
    assert "sup:painel" in grafo.superficies  # plataforma detectada
    assert grafo.edges  # só estruturais borda↔entidade
    from elixx.visual.navegacao import rota

    sem = rota(grafo, "ent:menu", "ent:botao_ok")
    assert sem["encontrado"] is False  # conservador: sem rota inventada
    grafo2 = construir_grafo_de_ambiente(
        mundo, ligacoes=[{"origem": "menu", "destino": "conteudo",
                           "modo": "andar"},
                         {"origem": "conteudo", "destino": "painel",
                           "modo": "andar"},
                         {"origem": "painel", "destino": "botao_ok",
                           "modo": "andar"}])
    com = rota(grafo2, "menu", "botao_ok")
    assert com["encontrado"] is True
    assert com["nos"] == ["ent:menu", "ent:conteudo", "ent:painel",
                          "ent:botao_ok"]


# 13. AIContextBuilder

def test_ai_context_builder():
    env = ambiente_amostra()
    mundo = vincular_ambiente(env)
    ctx = AIContextBuilder().construir(
        env, mundo, {"nome": "heroi", "x": 5.0, "y": 5.0,
                     "capacidades": ["andar"]})
    assert ctx["ambiente"]["id"] == "env_demo"
    assert ctx["agente"] == "heroi"
    assert ctx["posicao"] == {"x": 5.0, "y": 5.0}
    assert ctx["capacidades"] == ["andar"]
    assert any(r["id"] == "reg_menu" for r in ctx["regioes"])
    assert any(e["id"] == "botao_ok" for e in ctx["elementos"])
    assert any(s["id"] == "sup_painel" for s in ctx["superficies"])
    assert any(i["alvo"] == "botao_ok" for i in ctx["interacoes"])
    assert any(d["nome"] == "painel" for d in ctx["destinos_possiveis"])
    assert {"tipo": "filho_de", "de": "botao_ok",
            "para": "painel"} in ctx["relacoes"]
    assert ctx["rotas_disponiveis"] == []


# 14. serialização JSON

def test_serializacao_json():
    env = ambiente_amostra()
    texto = env.to_json()
    copia = Environment.from_json(texto)
    assert copia.to_json() == texto
    assert copia.obter_no("botao_ok").x == 180.0
    json.dumps(AIContextBuilder().construir(
        env, vincular_ambiente(env), {"nome": "a"}))


# 15. determinismo

def test_determinismo():
    a = ambiente_amostra().to_json()
    b = ambiente_amostra().to_json()
    assert a == b
    env = ambiente_amostra()
    mundo = vincular_ambiente(env)
    c1 = AIContextBuilder().construir(env, mundo, {"nome": "a"})
    c2 = AIContextBuilder().construir(env, mundo, {"nome": "a"})
    assert json.dumps(c1, sort_keys=True) == json.dumps(c2, sort_keys=True)


# 16. IDs duplicados

def test_ids_duplicados():
    env = Environment("e", tipo="generico")
    env.adicionar_no(EnvironmentNode("n1", tipo="caixa"))
    with pytest.raises(ErroELiXX):
        env.adicionar_no(EnvironmentNode("n1", tipo="caixa"))
    env.adicionar_regiao(EnvironmentRegion("r1"))
    with pytest.raises(ErroELiXX):
        env.adicionar_regiao(EnvironmentRegion("r1"))


# 17. referências inválidas

def test_referencias_invalidas():
    env = Environment("e", tipo="generico")
    env.adicionar_no(EnvironmentNode("n1", tipo="caixa"))
    env.adicionar_regiao(EnvironmentRegion("r1", nos=["fantasma"]))
    assert env.validar()["codigo"] == "referencia_invalida"
    with pytest.raises(ErroELiXX):
        env.obter_no("fantasma")
    with pytest.raises(ErroELiXX):
        vincular_ambiente(env)


# 18. ciclos

def test_ciclos():
    a = EnvironmentNode("a", tipo="caixa")
    b = EnvironmentNode("b", tipo="caixa")
    a.adicionar_filho(b)
    with pytest.raises(ErroELiXX):
        b.adicionar_filho(a)
    with pytest.raises(ErroELiXX):
        a.adicionar_filho(a)


# 19. tipos desconhecidos (dados, nunca código)

def test_tipos_desconhecidos():
    no = EnvironmentNode("x", tipo="holograma_quantico")
    assert no.tipo == "holograma_quantico"
    assert no.tipo_conhecido is False
    env = Environment("e", tipo="generico")
    env.adicionar_no(no)
    assert env.validar()["valido"] is True
    mundo = vincular_ambiente(env)
    assert mundo.por_id("x").tipo == "objeto"


# 20. strings maliciosas inertes

def test_strings_maliciosas():
    for maligno in ("__import__('os').system('x')", "../../../etc/passwd",
                    "<script>alert(1)</script>", "${7*7}", "{{7*7}}"):
        no = EnvironmentNode(maligno, nome=maligno, tipo="botao",
                             texto=maligno)
        assert no.id == maligno  # segue string, nunca executa
    env = Environment("e", tipo="generico")
    env.adicionar_no(EnvironmentNode(
        "__import__('os')", tipo="botao", x=0, y=0, largura=5,
        altura=5))
    mundo = vincular_ambiente(env)
    assert "__import__('os')" in mundo


# 21/22. NaN e infinito recusados

def test_nan_infinito():
    for ruim in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ErroELiXX):
            EnvironmentNode("n", tipo="caixa", x=ruim)
        with pytest.raises(ErroELiXX):
            Environment("e", largura=ruim)
    from elixx.visual.ai_bridge import AIIntent

    with pytest.raises(ErroELiXX):
        AIIntent.from_dict({"tipo": "mover", "personagem": "H",
                            "destino": {"x": float("nan"), "y": 0}})


# 23. estrutura vazia

def test_estrutura_vazia():
    env = Environment("vazio", tipo="generico")
    assert env.validar()["valido"] is True
    mundo = vincular_ambiente(env)
    assert len(mundo) == 0
    ctx = AIContextBuilder().construir(env, mundo, {"nome": "a"})
    assert ctx["elementos"] == [] and ctx["regioes"] == []
    assert env.to_json()


# 24. estrutura grande

def test_estrutura_grande():
    env = Environment("grande", tipo="web", largura=5000, altura=5000)
    for i in range(1000):
        env.adicionar_no(EnvironmentNode(
            f"n{i:05d}", tipo="item", x=i % 100, y=i // 100,
            largura=5, altura=5))
    assert len(env) == 1000
    assert env.validar()["valido"] is True
    mundo = vincular_ambiente(env)
    assert len(mundo) == 1000
    env.to_json()


def test_performance():
    for total in (100, 1000, 5000):
        env = Environment("p", tipo="web", largura=9000, altura=9000)
        for i in range(total):
            env.adicionar_no(EnvironmentNode(
                f"n{i:05d}", tipo="item", x=i % 200, y=i // 200,
                largura=4, altura=4))
        t0 = time.perf_counter()
        assert env.validar()["valido"] is True
        mundo = vincular_ambiente(env)
        AIContextBuilder().construir(env, mundo, {"nome": "a"})
        dt = time.perf_counter() - t0
        assert dt < 30.0, f"{total} nós em {dt:.1f}s"


# 25. interação inválida

def test_interacao_invalida():
    env = ambiente_amostra()
    exe = InteractionExecutor(env)
    assert exe.validar("fantasma", "botao_ok")["codigo"] == \
        "interacao_inexistente"
    assert exe.validar("botao_ok_clicar", "fantasma")["codigo"] == \
        "alvo_inexistente"
    assert exe.executar("fantasma", "botao_ok")["sucesso"] is False


# 26. capability ausente (já coberto em test_capabilities_reuso) + plano F15

def test_capacidade_ausente_navegacao():
    env = ambiente_amostra()
    sup = env._superficies["sup_painel"]
    sup.capacidades = ("voar",)
    mundo = vincular_ambiente(env)
    assert mundo.por_id("painel").props["capacidades"] == ["voar"]
    grafo = construir_grafo_de_ambiente(
        mundo, ligacoes=[{"origem": "conteudo", "destino": "painel",
                           "modo": "voar", "requer": "voar"}])
    from elixx.visual.capacidades import Capability, CapabilitySet
    from elixx.visual.navegacao import rota
    from elixx.visual.personagem import Character

    heroi = Character("Heroi", SimpleNamespace(
        x=0.0, y=0.0, escala_x=1.0, escala_y=1.0, rotacao=0.0,
        opacidade=1.0, pivo_x=50.0, pivo_y=50.0, pivo_unidade_x="%",
        pivo_unidade_y="%", pai=None), {}, {})
    sem = rota(grafo, "ent:conteudo", "ent:painel", holder=heroi,
               mundo=mundo)
    assert sem["encontrado"] is False
    assert "voar" in (sem.get("capacidades") or sem.get("requisitos"))
    heroi.capacidades.adicionar(Capability(nome="voar",
                                           provider="personagem:Heroi"))
    com = rota(grafo, "ent:conteudo", "ent:painel", holder=heroi,
               mundo=mundo)
    assert com["encontrado"] is True


# 27. dry-run (simular não executa; planejar não move)

def test_dry_run():
    env = ambiente_amostra()
    exe = InteractionExecutor(env)
    antes = len(exe.log)
    sim = exe.simular("botao_ok_clicar", "botao_ok")
    assert sim["sucesso"] is True and sim["simulado"] is True
    assert len(exe.log) == antes
    out = exe.executar("botao_ok_clicar", "botao_ok")
    assert out["sucesso"] is True and len(exe.log) == antes + 1


# 28. integração com F18 (Environment → contexto → provider → planner)

def test_integracao_f18():
    from elixx.visual.ai_bridge import (AIIntent, AIPlannerBridge,
                                        AIProvider)
    from elixx.visual.capacidades import Capability
    from elixx.visual.personagem import Character

    env = ambiente_amostra()
    mundo = vincular_ambiente(env)
    heroi = Character("Heroi", SimpleNamespace(
        nome="Heroi", x=160.0, y=50.0, escala_x=1.0, escala_y=1.0,
        rotacao=0.0, opacidade=1.0, pivo_x=50.0, pivo_y=50.0,
        pivo_unidade_x="%", pivo_unidade_y="%", pai=None), {}, {})
    heroi.capacidades.adicionar(Capability(nome="andar",
                                           provider="personagem:Heroi"))
    from elixx.visual.mundo import Bounds2D as _B, WorldEntity

    mundo.adicionar(WorldEntity("Heroi", "personagem", mundo,
                                character=heroi,
                                base=_B(160.0, 50.0, 0.0, 0.0)))
    grafo = construir_grafo_de_ambiente(
        mundo, ligacoes=[{"origem": "Heroi", "destino": "conteudo",
                           "modo": "andar"},
                         {"origem": "conteudo", "destino": "painel",
                           "modo": "andar"},
                         {"origem": "painel", "destino": "botao_ok",
                           "modo": "andar"}],
        nome="RotasEnv")
    ctx = AIContextBuilder().construir(env, mundo, heroi, grafo=grafo,
                                       destino="botao_ok")
    assert ctx["rotas_disponiveis"]
    assert ctx["rotas_disponiveis"][0]["nos"][-1] == "ent:botao_ok"

    class ProvedorDemo(AIProvider):
        def gerar_intencao(self, contexto):
            assert contexto["ambiente"]["id"] == "env_demo"
            return AIIntent.from_dict(
                {"tipo": "mover", "personagem": "Heroi",
                 "destino": "botao_ok", "modo": "andar"})

    intent = ProvedorDemo("demo").gerar_intencao(ctx)
    assert isinstance(intent, AIIntent)
    ponte = AIPlannerBridge(None, {"Heroi": heroi}, {"M": mundo},
                            {"RotasEnv": grafo})
    plano = ponte.planejar(intent)
    assert plano.viavel is True and plano.executavel is True
    assert plano.traversal_plan is not None
    assert plano.motion_plan is not None
    assert plano.behavior_plan is not None


# 29. regressão F01–F18 (amostra honesta: AI bridge + navegação base)

def test_regressao_f01_f18():
    from elixx.visual.ai_bridge import AIIntent, AIPlannerBridge
    from elixx.compilador.componentes import expandir_componentes
    from elixx.compilador.lexer import tokenizar
    from elixx.compilador.parser import Parser
    from elixx.compilador.semantica import validar
    from elixx.runtime.nucleo import Executor
    from elixx.visual.capacidades import vincular_itens
    from elixx.visual.cena import ConstrutorCena
    from elixx.visual.mundo import vincular_mundos
    from elixx.visual.navegacao import vincular_navegacao
    from elixx.visual.personagem import vincular_personagens

    with open("exemplos/ai-bridge.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = Parser(tokenizar(fonte)).parse()
    expandir_componentes(prog)
    validar(prog)
    executor = Executor()
    cena = ConstrutorCena().de_objetos(
        executor.executar(prog, []).objetos)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    grafos = vincular_navegacao(cena, prog, mundos)
    ponte = AIPlannerBridge(cena, pers, mundos, grafos, itens)
    plano = ponte.planejar(AIIntent.from_dict(
        {"tipo": "mover", "personagem": "Heroi", "destino": "plat_b"}))
    assert plano.viavel is True


# ----- segurança: sem eval/exec/import dinâmico -----

def test_sem_execucao_dinamica():
    import elixx.visual.ambiente as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("eval(", "exec(", "__import__", "importlib",
                     "subprocess", "compile(", "os.system", "getattr(__"):
        assert proibido not in fonte


# ----- adaptador único (HTML/app/desktop/elixx → Environment) -----

def test_adaptador_origens():
    for tipo in ("web", "aplicativo", "desktop", "elixx", "generico"):
        env = ambiente_de_dict(
            {"id": f"env_{tipo}", "tipo": tipo,
             "nos": [{"id": "n1", "tipo": "botao", "x": 1, "y": 2,
                      "largura": 3, "altura": 4}]})
        assert env.tipo == tipo
        assert vincular_ambiente(env).por_id("n1").tipo == "objeto"


# ----- inferência documentada (regras 1–6) -----

def test_regras_inferencia():
    assert [i.tipo for i in inferir_interacoes(
        EnvironmentNode("e", tipo="entrada", habilitado=True))] == \
        ["focar", "escrever", "selecionar", "limpar"]
    assert [i.tipo for i in inferir_interacoes(
        EnvironmentNode("l", tipo="lista", habilitado=True))] == \
        ["selecionar", "abrir", "navegar"]
    assert [i.tipo for i in inferir_interacoes(
        EnvironmentNode("j", tipo="janela"))] == \
        ["fechar", "minimizar", "maximizar"]
    assert inferir_interacoes(EnvironmentNode("t", tipo="texto")) == []
    sem_geo = EnvironmentNode("s", tipo="caixa")
    assert gerar_boundaries(sem_geo) == [] and gerar_surface(sem_geo) \
        is None
    painel = EnvironmentNode("p", tipo="painel", x=0, y=0, largura=10,
                             altura=10)
    assert gerar_surface(painel) is not None
    assert len(gerar_boundaries(painel)) == 5


# ----- debug textual -----

def test_debug_ambiente():
    texto = debug_ambiente(ambiente_amostra())
    for trecho in ("Environment env_demo", "NOS:", "REGIOES:",
                   "SUPERFICIES:", "INTERACOES:", "botao_ok"):
        assert trecho in texto


# ----- Tk: estrutura externa vira ambiente espacial -----

def test_tk_environment_visual():
    try:
        import tkinter as _tk

        from elixx.visual.tk import RenderizadorTk
    except ImportError:
        pytest.skip("Tk indisponível")
    try:
        from elixx.compilador.componentes import expandir_componentes
        from elixx.compilador.lexer import tokenizar
        from elixx.compilador.parser import Parser
        from elixx.compilador.semantica import validar
        from elixx.runtime.nucleo import Executor
        from elixx.visual.cena import ConstrutorCena
        from elixx.visual.navegacao import rota

        with open("exemplos/environment.elixx",
                  encoding="utf-8") as arq:
            fonte = arq.read()
        prog = Parser(tokenizar(fonte)).parse()
        expandir_componentes(prog)
        validar(prog)
        executor = Executor()
        cena = ConstrutorCena().de_objetos(
            executor.executar(prog, []).objetos)
        env = ambiente_amostra()
        mundo = vincular_ambiente(env)
        grafo = construir_grafo_de_ambiente(
            mundo, ligacoes=[{"origem": "menu", "destino": "conteudo",
                               "modo": "andar"},
                             {"origem": "conteudo",
                               "destino": "botao_ok", "modo": "andar"}])
        assert rota(grafo, "menu", "botao_ok")["encontrado"] is True
        rend = RenderizadorTk(executor)
        try:
            rend.montar(cena)
            rend.raiz.withdraw()
            rend.atualizar(16.0)
            rend.raiz.update()
            assert rend.raiz.winfo_exists()
        finally:
            rend.fechar()
    except Exception as exc:
        import tkinter as _tk2

        if isinstance(exc, _tk2.TclError):
            pytest.skip(f"sem display: {exc}")
        raise


# ----- exemplo programático -----

def test_exemplo_environment_elixx():
    with open("exemplos/environment.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    assert "environment" in fonte.lower() or "mundo" in fonte.lower()
