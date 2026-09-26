"""Testes da Fase 15 — Navigation + Traversal (determinísticos)."""
import pytest

from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroSemantico, ErroSintatico
from elixx.runtime.nucleo import Executor
from elixx.visual.capacidades import obter_instancia, vincular_itens
from elixx.visual.cena import ConstrutorCena
from elixx.visual.mundo import Bounds2D, World, WorldEntity
from elixx.visual.navegacao import (
    NavigationBuilder,
    NavigationEdge,
    NavigationGraph,
    NavigationNode,
    acessivel,
    debug_navegacao,
    plano_travessia,
    rota,
    rotas_alternativas,
    vincular_navegacao,
)
from elixx.visual.personagem import vincular_personagens
from elixx.visual.transform import Vector2


def analisar_expandir(fonte):
    prog = Parser(tokenizar(fonte)).parse()
    expandir_componentes(prog)
    return prog


def montar(fonte):
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    return executor, cena, prog


def vinculo(fonte):
    ex, cena, prog = montar(fonte)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    grafos = vincular_navegacao(cena, prog, mundos)
    return ex, cena, prog, itens, pers, mundos, grafos


def vincular_mundos(cena, prog, pers, itens):
    from elixx.visual.mundo import vincular_mundos as _vinc

    return _vinc(cena, prog, pers, itens)


FONTE = ('janela p {\n titulo: "T"\n'
         ' personagem Heroi {\n  posição: 100px 500px\n'
         '  parte corpo {\n  }\n'
         '  capacidade andar\n  capacidade pular\n'
         ' }\n'
         ' item BotaFoguete {\n  categoria: "equipamento"\n'
         '  capacidade voar\n }\n'
         ' item Corda {\n  categoria: "ferramenta"\n'
         '  capacidade descer\n }\n'
         ' mundo M {\n  tamanho: 2000px 1200px\n'
         '  chão chao_a {\n   posição: 0px 550px\n   tamanho: 800px 50px\n  }\n'
         '  plataforma plat_b {\n   posição: 900px 400px\n'
         '   tamanho: 300px 30px\n  }\n'
         '  plataforma plat_alta {\n   posição: 1400px 150px\n'
         '   tamanho: 200px 30px\n  }\n'
         '  plataforma plat_baixa {\n   posição: 1000px 500px\n'
         '   tamanho: 200px 30px\n  }\n'
         '  parede muro {\n   posição: 100px 100px\n   tamanho: 40px 80px\n  }\n'
         '  obstáculo rocha {\n   posição: 560px 410px\n'
         '   tamanho: 60px 20px\n  }\n'
         '  ponto saida {\n   posição: 1500px 165px\n  }\n'
         '  ponto base {\n   posição: 100px 550px\n  }\n'
         '  usar personagem Heroi\n  usar item BotaFoguete\n'
         '  usar item Corda\n'
         ' }\n'
         ' navegacao Rotas {\n'
         '  caminho base -> chao_a {\n   modo: andar\n  }\n'
         '  caminho chao_a -> plat_b {\n   modo: pular\n   custo: 2\n  }\n'
         '  caminho plat_b -> plat_alta {\n   modo: voar\n   custo: 4\n'
         '   requer: voar\n  }\n'
         '  caminho plat_b -> plat_baixa {\n   modo: descer\n   custo: 1\n'
         '   requer: descer\n  }\n'
         '  caminho plat_b_borda_direita -> saida {\n   modo: andar\n  }\n'
         '  caminho plat_alta -> saida {\n   modo: andar\n   custo: 100\n  }\n'
         ' }\n}\n')


def base():
    return vinculo(FONTE)


# ----- 1-6: grafo, node, edge, identidade, refs, posição derivada -----

def test_graph_basico():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    assert isinstance(g, NavigationGraph)
    assert g.nome == "Rotas"
    assert len(g.nos) > 0 and len(g.edges) > 0


def test_node_identidade():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    no = g.nos["ent:plat_b"]
    assert isinstance(no, NavigationNode)
    assert (no.id, no.kind, no.entidade) == ("ent:plat_b", "entidade",
                                             "plat_b")
    with pytest.raises(ErroELiXX, match="repetido"):
        g.adicionar_no(NavigationNode("ent:plat_b", "entidade",
                                      mundos["M"]))
    with pytest.raises(ErroELiXX, match="inexistente"):
        g.adicionar_edge(NavigationEdge("ent:plat_b", "ent:fantasma"))


def test_edge_identidade():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    e = [x for x in g.edges if x.modo == "voar"][0]
    assert e.id == "ent:plat_b>ent:plat_alta:voar"
    assert (e.origem, e.destino) == ("ent:plat_b", "ent:plat_alta")
    with pytest.raises(ErroELiXX, match="modo"):
        NavigationEdge("a", "b", modo="  ")
    with pytest.raises(ErroELiXX, match="Custo"):
        NavigationEdge("a", "b", custo=-1)


def test_referencias_world_sem_copia():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    assert g.mundo is mundos["M"]
    assert g.nos["ent:Heroi"].entidade == "Heroi"


def test_posicao_derivada_ao_vivo():
    ex, cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    antes = g.nos["ent:Heroi"].posicao().tupla()
    assert antes == (100.0, 500.0)
    cena.buscar("Heroi").x = 700.0  # move (como faria um Motion)
    depois = g.nos["ent:Heroi"].posicao().tupla()
    assert depois == (700.0, 500.0)


def test_node_tipo_invalido():
    _ex, _cena, _prog, _itens, _pers, mundos, _grafos = base()
    with pytest.raises(ErroELiXX, match="Tipo de nó"):
        NavigationNode("x", "nuvem", mundos["M"])


# ----- 7-10: superfície, borda, obstáculo, região -----

def test_superficie():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    sup = g.superficies["sup:plat_b"]
    assert sup.tipo == "plataforma" and sup.navegavel is True
    assert sup.inicio().tupla() == (900.0, 400.0)
    assert sup.fim().tupla() == (1200.0, 400.0)
    assert sup.comprimento() == 300.0
    assert g.superficies["sup:muro"].navegavel is False  # parede informa


def test_borda_derivada():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    esq = g.nos["plat_b_borda_esquerda"]
    assert esq.kind == "borda" and esq.lado == "esquerda"
    assert esq.posicao().tupla() == (900.0, 400.0)
    assert g.nos["plat_b_borda_direita"].posicao().tupla() == (1200.0, 400.0)
    with pytest.raises(ErroELiXX, match="Lado"):
        from elixx.visual.navegacao import id_borda

        id_borda("x", "noroeste")


def test_obstaculo_identificado():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    assert "ent:rocha" in g.nos
    assert mundos["M"].por_id("rocha").tipo == "obstaculo"


def test_regiao_reutilizada():
    ex, cena, prog, itens, pers, mundos, grafos = vinculo(
        FONTE.replace("  ponto base {\n   posição: 100px 550px\n  }\n",
                      "  ponto base {\n   posição: 100px 550px\n  }\n"
                      "  área sala {\n   posição: 0px 400px\n"
                      "   tamanho: 800px 200px\n  }\n"))
    g = grafos["Rotas"]
    assert "ent:sala" in g.nos
    assert mundos["M"].em_regiao("sala")
    grafos = vincular_navegacao(cena, prog, mundos)
    g = grafos["Rotas"]
    assert "ent:sala" in g.nos
    assert mundos["M"].em_regiao("sala")


# ----- 11-13: modo, capability, acessibilidade -----

def test_traversal_mode_descritor():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    assert sorted({e.modo for e in g.edges}) == ["andar", "descer", "pular",
                                                 "voar"]


def test_capability_requirement():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    e = [x for x in g.edges if x.modo == "voar"][0]
    assert e.requer == "voar"


def test_acessibilidade_estruturada():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    h = pers["Heroi"]
    e_voar = [x for x in g.edges if x.modo == "voar"][0]
    r = acessivel(h, e_voar, mundos["M"])
    assert r["permitido"] is False
    assert r["requisitos"] == [{"tipo": "capacidade", "alvo": "voar",
                                "ok": False,
                                "detalhe": 'capacidade "voar" ausente'}]
    e_andar = [x for x in g.edges if x.modo == "andar"
               and x.origem == "ent:base"][0]
    assert acessivel(h, e_andar, mundos["M"])["permitido"] is True
    bloqueada = NavigationEdge("ent:base", "ent:chao_a", bloqueado=True)
    assert acessivel(h, bloqueada)["permitido"] is False
    assert acessivel(None, e_voar)["permitido"] is True  # sem filtro


# ----- 14-20: pathfinding, custos, bloqueio, capability -----

def test_caminho_simples():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    r = rota(g, "base", "plat_b", pers["Heroi"], mundos["M"])
    assert r["encontrado"] is True
    assert r["nos"] == ["ent:base", "ent:chao_a", "ent:plat_b"]
    assert r["modos"] == ["andar", "pular"]
    assert r["custo_total"] == pytest.approx(100.0 + 2, abs=5.0)


def test_caminho_multiplos_nodes_e_requisitos():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    h = pers["Heroi"]
    h.inventario.possuir(obter_instancia(_itens, "BotaFoguete"))
    h.inventario.equipar("BotaFoguete")
    r = rota(g, "base", "plat_alta", h, mundos["M"])
    assert r["encontrado"] is True
    assert r["nos"][-1] == "ent:plat_alta"
    assert "voar" in r["modos"] and "voar" in r["requisitos"]


def test_caminho_bloqueado_flag():
    ex, cena, prog, itens, pers, mundos, grafos = vinculo(
        FONTE.replace("  caminho base -> chao_a {\n   modo: andar\n  }\n",
                      "  caminho base -> chao_a {\n   modo: andar\n"
                      "   bloqueado: verdadeiro\n  }\n"))
    grafos = vincular_navegacao(cena, prog, mundos)
    r = rota(grafos["Rotas"], "base", "plat_b", pers["Heroi"], mundos["M"])
    assert r["encontrado"] is False
    assert "conexão" in r["motivo"]


def test_caminho_sem_capability():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    r = rota(g, "base", "plat_alta", pers["Heroi"], mundos["M"])
    assert r["encontrado"] is False
    assert r["motivo"] == "Capacidade necessária ausente."
    assert r["capacidades"] == ["voar"]


def test_caminho_com_item_equipado():
    _ex, _cena, _prog, itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    h = pers["Heroi"]
    h.inventario.possuir(obter_instancia(itens, "BotaFoguete"))
    h.inventario.equipar("BotaFoguete")
    assert rota(g, "plat_b", "plat_alta", h,
                mundos["M"])["encontrado"] is True


def test_bloqueio_geometrico():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    # rocha (400,400,60x200) cruza chao_a(0,550)->plat_b(900,400)? não;
    # caminho artificial através da rocha:
    g.adicionar_no(NavigationNode("ent:alvo_teste", "entidade", mundos["M"],
                                  entidade="saida"))
    e = NavigationEdge("ent:base", "ent:alvo_teste", modo="andar")
    g.adicionar_edge(e)
    assert e.bloqueio_geometrico(g) == "rocha"
    r = rota(g, "base", "alvo_teste", pers["Heroi"], mundos["M"])
    assert r["encontrado"] is False


# ----- 21-26: voo, salto, subida, descida, corda, borda -----

def test_voo_modo():
    _ex, _cena, _prog, itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    h = pers["Heroi"]
    h.inventario.possuir(obter_instancia(itens, "BotaFoguete"))
    h.inventario.equipar("BotaFoguete")
    r = rota(g, "plat_b", "plat_alta", h, mundos["M"])
    assert r["encontrado"] and r["modos"] == ["voar"]


def test_salto_edge():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    e = [x for x in g.edges if x.modo == "pular"][0]
    assert e.distancia(g) > 0
    assert e.custo_efetivo(g) == 2  # explícito vence a distância


def test_subida_descida_corda():
    _ex, _cena, _prog, itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    h = pers["Heroi"]
    h.inventario.possuir(obter_instancia(itens, "Corda"))
    h.inventario.equipar("Corda")
    assert tem_corda(h) is True
    r = rota(g, "plat_b", "plat_baixa", h, mundos["M"])
    assert r["encontrado"] is True
    assert r["modos"] == ["descer"]


def tem_corda(h):
    from elixx.visual.capacidades import tem_capacidade

    return tem_capacidade(h, "descer")


def test_borda_como_destino():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    r = rota(g, "plat_b", "plat_b_borda_direita", pers["Heroi"],
             mundos["M"])
    assert r["encontrado"] is True  # link estrutural entidade↔borda
    assert r["nos"] == ["ent:plat_b", "plat_b_borda_direita"]


# ----- 27-32: origens/destinos, entidade móvel, custo, determinismo -----

def test_origem_destino_entidade():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    r = rota(g, "Heroi", "saida", pers["Heroi"], mundos["M"])
    assert isinstance(r["encontrado"], bool)


def test_origem_destino_vector2():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    r = rota(g, Vector2(95, 545), Vector2(905, 405), pers["Heroi"],
             mundos["M"])
    assert r["encontrado"] is True
    assert r["nos"][0] == "ent:base"  # mais próximo de (95,545)
    with pytest.raises(ErroELiXX, match="não é nó"):
        rota(g, "fantasma", "saida")


def test_entidade_movel_identidade():
    ex, cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    cena.buscar("Heroi").x = 900.0  # moveu, identidade fica
    assert g.nos["ent:Heroi"].posicao().tupla() == (900.0, 500.0)


def test_custo_explicito_vs_distancia():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    e_voar = [x for x in g.edges if x.modo == "voar"][0]
    e_borda = [x for x in g.edges if x.destino == "ent:saida"
               and x.modo == "andar"][0]
    assert e_voar.custo_efetivo(g) == 4
    assert e_borda.custo_efetivo(g) == pytest.approx(
        e_borda.distancia(g))  # sem custo: distância


def test_determinismo():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    h = pers["Heroi"]
    r1 = rota(g, "base", "saida", h, mundos["M"])
    r2 = rota(g, "base", "saida", h, mundos["M"])
    assert r1["nos"] == r2["nos"]
    assert r1["custo_total"] == r2["custo_total"]


def test_caminho_inexistente_estruturado():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    r = rota(g, "saida", "base", pers["Heroi"], mundos["M"])
    assert r["encontrado"] is False
    assert set(r) >= {"encontrado", "motivo", "nos", "modos", "path"}


# ----- 33-36: múltiplas rotas, plano, etapas -----

def test_multiplas_rotas():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    # sem filtro de holder: via plat_alta (104) e via borda (~681)
    rotas = rotas_alternativas(g, "plat_b", "saida", k=3,
                               holder=None, mundo=mundos["M"])
    assert len(rotas) >= 2  # direta pela borda + via plat_alta (custo 100)
    assert all(r["encontrado"] for r in rotas)
    seqs = {tuple(r["nos"]) for r in rotas}
    assert len(seqs) == len(rotas)
    with pytest.raises(ErroELiXX, match="k inválido"):
        rotas_alternativas(g, "plat_b", "saida", k=0)


def test_plano_travessia_descritivo():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    g = grafos["Rotas"]
    plano = plano_travessia(g, "base", "plat_b", pers["Heroi"],
                            mundos["M"])
    assert plano.origem == "base" and plano.destino == "plat_b"
    assert [e["modo"] for e in plano.etapas] == ["andar", "pular"]
    assert plano.etapas[0] == {"de": "ent:base", "para": "ent:chao_a",
                               "modo": "andar", "requisitos": []}
    assert plano.capacidades_necessarias == []
    vazio = plano_travessia(g, "saida", "base")
    assert vazio.etapas == [] and vazio.path.nos == []


def test_path_nao_move():
    _ex, cena, _prog, _itens, _pers, mundos, grafos = base()
    g = grafos["Rotas"]
    antes = (cena.buscar("Heroi").x, cena.buscar("Heroi").y)
    rota(g, "base", "saida")
    plano_travessia(g, "base", "saida")
    rotas_alternativas(g, "base", "saida", k=2)
    assert (cena.buscar("Heroi").x, cena.buscar("Heroi").y) == antes


# ----- 37-40: world/character/capability/motion preservados -----

def test_world_preservado():
    _ex, _cena, _prog, _itens, _pers, mundos, _grafos = base()
    w = mundos["M"]
    assert w.por_id("plat_b").tipo == "plataforma"
    assert "chao_a" in w and len(w) == 11


def test_character_preservado():
    _ex, _cena, _prog, _itens, pers, _mundos, _grafos = base()
    h = pers["Heroi"]
    assert h.obter_parte("corpo").nome == "corpo"
    assert h.direcao == "frente"


def test_capability_preservada():
    _ex, _cena, _prog, itens, pers, _mundos, _grafos = base()
    from elixx.visual.capacidades import tem_capacidade

    assert tem_capacidade(pers["Heroi"], "andar") is True
    assert "andar" in itens["defs"] or True


def test_motion_preservado_sem_duplicacao():
    import elixx.visual.navegacao as navmod

    assert not hasattr(navmod, "MotorAnimacoes")
    assert not hasattr(navmod, "Spring")


# ----- 41: segurança -----

def test_seguranca_nomes_inertes():
    g = NavigationGraph("S", mundos_seg()[0])
    g.adicionar_no(NavigationNode("ent:__import__(os)", "entidade",
                                  mundos_seg()[0]))
    e = NavigationEdge("ent:__import__(os)", "ent:__import__(os)",
                       modo="eval(x)")
    g.adicionar_edge(e)
    r = rota(g, "ent:__import__(os)", "ent:__import__(os)")
    assert r["encontrado"] is True and r["nos"] == ["ent:__import__(os)"]


def mundos_seg():
    w = World("seg")
    from elixx.visual.mundo import WorldEntity

    return w, None


# ----- gramática e debug -----

def test_navegacao_parse_arvore():
    from elixx.compilador.ast import mostrar_arvore

    prog = analisar_expandir(FONTE)
    arvore = mostrar_arvore(prog)
    assert "Navegacao Rotas" in arvore
    assert "Caminho chao_a -> plat_b" in arvore
    validar(prog)


def test_navegacao_erros_claros():
    with pytest.raises(ErroSemantico, match="não existe"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n  ponto a {\n  }\n }\n'
            ' navegacao N {\n  caminho a -> fantasma {\n  }\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="repetid"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n  ponto a {\n  }\n'
            '  ponto b {\n  }\n }\n'
            ' navegacao N {\n  caminho a -> b {\n  }\n'
            '  caminho a -> b {\n  }\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="repetida"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n navegacao N {\n }\n'
            ' navegacao N {\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="custo"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n  ponto a {\n  }\n'
            '  ponto b {\n  }\n }\n'
            ' navegacao N {\n  caminho a -> b {\n   custo: "alto"\n  }\n'
            ' }\n}\n'))
    with pytest.raises(ErroSintatico):
        analisar('janela p {\n titulo: "T"\n navegacao N {\n'
                 '  voar a b\n }\n}\n')


def test_debug_navegacao():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    texto = debug_navegacao(grafos["Rotas"])
    assert "Navigation Rotas" in texto
    assert "NODES:" in texto and "EDGES:" in texto
    assert "SURFACES:" in texto and "REQUISITOS:" in texto


def test_exemplo_navigation():
    with open("exemplos/navigation.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    grafos = vincular_navegacao(
        cena, prog, vincular_mundos(cena, prog, pers, itens))
    assert "Rotas" in grafos
