"""Testes da Fase 21 — Visual Geometry Core.

Determinísticos, stdlib, sem CSS, sem visão, sem IA, sem navegador.
"""
import json
import time

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.geometria import (
    DIRECOES,
    GeometryMap,
    GeometryNode,
    GeometryRegion,
    GeometrySnapshot,
    Point2D,
    Size2D,
    bounds_baixo,
    bounds_esquerda,
    bounds_tamanho,
    bounds_topo,
    bounds_transladado,
    debug_geometria,
    direcao_entre,
    environment_para_geometria,
    geometria_para_world,
    parsear_mapa_explicito,
    vincular_geometria_world,
)
from elixx.visual.mundo import Bounds2D
from elixx.visual.transform import Vector2


def mapa_amostra():
    """Janela / cabeçalho / menu / conteúdo / card / botão / rodapé."""
    mapa = GeometryMap("demo")
    mapa.adicionar(GeometryNode("janela", Bounds2D(0, 0, 800, 600)))
    mapa.adicionar(GeometryNode("cabecalho", Bounds2D(0, 0, 800, 60),
                                parent_id="janela"))
    mapa.adicionar(GeometryNode("menu", Bounds2D(0, 60, 150, 480),
                                parent_id="janela"))
    mapa.adicionar(GeometryNode("conteudo", Bounds2D(150, 60, 650, 480),
                                parent_id="janela"))
    mapa.adicionar(GeometryNode("card", Bounds2D(20, 20, 300, 150),
                                parent_id="conteudo"))
    mapa.adicionar(GeometryNode("botao", Bounds2D(30, 90, 120, 40),
                                parent_id="card"))
    mapa.adicionar(GeometryNode("rodape", Bounds2D(0, 540, 800, 60),
                                parent_id="janela"))
    mapa.adicionar_regiao(GeometryRegion("reg_conteudo",
                                         Bounds2D(150, 60, 650, 480),
                                         tipo="area"))
    return mapa


# 1. Vector2 reutilizado (sem duplicar)

def test_vector2_reutilizado():
    import elixx.visual.geometria as modulo

    assert modulo.Vector2 is Vector2
    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class Vector2" not in fonte
    v = Vector2(1, 2) + Vector2(3, 4)
    assert (v.x, v.y) == (4.0, 6.0)
    assert (Vector2(5, 5) - Vector2(2, 1)).tupla() == (3.0, 4.0)
    assert (Vector2(2, 3) * 2).tupla() == (4.0, 6.0)
    assert Vector2(0, 0).distancia(Vector2(3, 4)) == 5.0
    assert Vector2(1, 1) == Vector2(1.0, 1.0)


# 2. Bounds2D reutilizado (sem duplicar)

def test_bounds2d_reutilizado():
    import elixx.visual.geometria as modulo

    assert modulo.Bounds2D is Bounds2D
    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class Bounds2D" not in fonte
    b = Bounds2D(10, 20, 100, 50)
    assert (b.direita, b.base) == (110.0, 70.0)
    assert b.centro().tupla() == (60.0, 45.0)


# 3. Size2D

def test_size2d():
    s = Size2D(120, 40)
    assert (s.largura, s.altura) == (120.0, 40.0)
    assert s.area == 4800.0
    assert Size2D.from_dict(s.to_dict()).area == 4800.0
    with pytest.raises(ErroELiXX):
        Size2D(-1, 5)
    with pytest.raises(ErroELiXX):
        Size2D(float("nan"), 1)


# 4. Point2D

def test_point2d():
    p = Point2D(3, 4)
    assert p.magnitude() == 5.0
    assert p.distancia(Point2D(0, 0)) == 5.0
    assert (p + Point2D(1, 1)).tupla() == (4.0, 5.0)
    assert Point2D.from_dict(p.to_dict()).tupla() == (3.0, 4.0)
    assert isinstance(p, Vector2)  # reuso, sem duplicar matemática


# 5. acessores bounds (esquerda/topo/baixo/tamanho/transladado/expand)

def test_acessores_bounds():
    b = Bounds2D(10, 20, 100, 50)
    assert bounds_esquerda(b) == 10.0
    assert bounds_topo(b) == 20.0
    assert bounds_baixo(b) == 70.0
    assert bounds_tamanho(b).area == 5000.0
    t = bounds_transladado(b, 5, -5)
    assert (t.x, t.y, t.largura, t.altura) == (15.0, 15.0, 100.0, 50.0)
    assert b.expandir(10).largura == 120.0


# 6. contains

def test_contains():
    mapa = mapa_amostra()
    no = mapa.obter("conteudo")
    assert no.contem_ponto(Point2D(200, 100)) is True
    assert no.contem_ponto(Point2D(10, 10)) is False
    g = mapa.bounds_global("botao")
    assert g.contem_ponto(mapa.centro_global("botao")) is True


# 7. intersects

def test_intersects():
    a = Bounds2D(0, 0, 100, 100)
    assert a.intersecta(Bounds2D(50, 50, 100, 100)) is True
    assert a.intersecta(Bounds2D(200, 200, 10, 10)) is False
    assert a.intersecta(Bounds2D(100, 0, 50, 50)) is False  # só borda


# 8. overlaps (alias honesto)

def test_overlaps():
    a = Bounds2D(0, 0, 100, 100)
    assert a.sobrepoe(Bounds2D(50, 50, 10, 10)) is True
    assert a.sobrepoe(Bounds2D(500, 500, 10, 10)) is False
    mapa = mapa_amostra()
    assert mapa.relacao("menu", "conteudo")["sobrepoe"] is False


# 9. touches

def test_touches():
    a = Bounds2D(0, 0, 100, 100)
    assert a.toca(Bounds2D(100, 0, 50, 50)) is True
    assert a.toca(Bounds2D(50, 50, 10, 10)) is False  # sobrepõe, não toca
    assert a.toca(Bounds2D(500, 500, 10, 10)) is False


# 10. distância

def test_distancia():
    a = Bounds2D(0, 0, 10, 10)
    b = Bounds2D(0, 0, 10, 10)
    assert a.distancia_para(b) == 0.0
    mapa = mapa_amostra()
    rel = mapa.relacao("cabecalho", "rodape")
    assert rel["distancia"] == pytest.approx(540.0)  # centros (400,30)-(400,570)
    no = mapa.obter("botao")
    assert no.distancia_para(Bounds2D(0, 0, 10, 10)) >= 0.0


# 11. direção (9 vias)

def test_direcao():
    c = Vector2(0, 0)
    assert direcao_entre(c, Vector2(0, 0)) == "centro"
    assert direcao_entre(c, Vector2(10, 0)) == "leste"
    assert direcao_entre(c, Vector2(-10, 0)) == "oeste"
    assert direcao_entre(c, Vector2(0, 10)) == "sul"  # Y desce
    assert direcao_entre(c, Vector2(0, -10)) == "norte"
    assert direcao_entre(c, Vector2(10, 10)) == "sudeste"
    assert direcao_entre(c, Vector2(-10, -10)) == "noroeste"
    assert direcao_entre(c, Vector2(10, -10)) == "nordeste"
    assert direcao_entre(c, Vector2(-10, 10)) == "sudoeste"
    assert set(DIRECOES) == {"norte", "sul", "leste", "oeste",
                             "nordeste", "noroeste", "sudeste",
                             "sudoeste", "centro"}


# 12. parent/child

def test_parent_child():
    mapa = mapa_amostra()
    assert [c.id for c in mapa.filhos("janela")] == ["cabecalho", "menu",
                                                    "conteudo", "rodape"]
    assert [c.id for c in mapa.filhos("card")] == ["botao"]
    assert mapa.obter("botao").parent_id == "card"


# 13. coordenadas locais

def test_coordenadas_locais():
    mapa = mapa_amostra()
    no = mapa.obter("botao")
    assert (no.bounds.x, no.bounds.y) == (30.0, 90.0)  # local ao card


# 14. coordenadas globais

def test_coordenadas_globais():
    mapa = mapa_amostra()
    # card(20,20) em conteudo(150,60): global (170,80); botão +(30,90).
    g = mapa.bounds_global("botao")
    assert (g.x, g.y) == (200.0, 170.0)
    assert (g.largura, g.altura) == (120.0, 40.0)
    c = mapa.centro_global("botao")
    assert (c.x, c.y) == (260.0, 190.0)
    # ida e volta
    p = mapa.local_para_global("card", Point2D(10, 10))
    assert (p.x, p.y) == (180.0, 90.0)
    q = mapa.global_para_local("card", p)
    assert (q.x, q.y) == pytest.approx((10.0, 10.0))


# 15. ciclos bloqueados

def test_ciclos():
    mapa = GeometryMap("c")
    mapa.adicionar(GeometryNode("a", Bounds2D(0, 0, 10, 10)))
    mapa.adicionar(GeometryNode("b", Bounds2D(0, 0, 5, 5),
                                parent_id="a"))
    with pytest.raises(ErroELiXX):
        mapa.atualizar("a", parent_id="b")  # fecharia A→B→A
    with pytest.raises(ErroELiXX):
        GeometryNode("x", parent_id="x")
    with pytest.raises(ErroELiXX):
        mapa.adicionar(GeometryNode("c", parent_id="fantasma"))


# 16. IDs duplicados

def test_ids_duplicados():
    mapa = GeometryMap("d")
    mapa.adicionar(GeometryNode("n1", Bounds2D(0, 0, 5, 5)))
    with pytest.raises(ErroELiXX):
        mapa.adicionar(GeometryNode("n1", Bounds2D(1, 1, 5, 5)))
    mapa.adicionar_regiao(GeometryRegion("r1", Bounds2D(0, 0, 5, 5)))
    with pytest.raises(ErroELiXX):
        mapa.adicionar_regiao(GeometryRegion("r1", Bounds2D(0, 0, 5, 5)))


# 17. GeometryMap CRUD

def test_mapa_crud():
    mapa = GeometryMap("m")
    assert len(mapa) == 0 and "x" not in mapa
    mapa.adicionar(GeometryNode("x", Bounds2D(1, 2, 3, 4), z_index=2))
    assert "x" in mapa and len(mapa) == 1
    mapa.atualizar("x", visible=False, z_index=5)
    assert mapa.obter("x").visible is False
    assert mapa.obter("x").z_index == 5
    mapa.atualizar("x", bounds=Bounds2D(9, 9, 9, 9))
    assert mapa.obter("x").bounds.x == 9.0
    mapa.remover("x")
    assert len(mapa) == 0
    with pytest.raises(ErroELiXX):
        mapa.obter("x")
    with pytest.raises(ErroELiXX):
        mapa.remover("x")


# 18. remover com filhos exige ordem

def test_remover_com_filhos():
    mapa = mapa_amostra()
    with pytest.raises(ErroELiXX):
        mapa.remover("conteudo")
    mapa.remover("botao")
    mapa.remover("card")
    assert "card" not in mapa


# 19. ancestrais/descendentes

def test_ancestrais_descendentes():
    mapa = mapa_amostra()
    assert [a.id for a in mapa.ancestrais("botao")] == ["card",
                                                       "conteudo",
                                                       "janela"]
    desc = sorted(d.id for d in mapa.descendentes("janela"))
    assert desc == ["botao", "cabecalho", "card", "conteudo", "menu",
                    "rodape"]


# 20. GeometrySnapshot imutável

def test_snapshot_imutavel():
    mapa = mapa_amostra()
    snap = mapa.snapshot()
    assert isinstance(snap, GeometrySnapshot)
    antes = snap.bounds_global("botao")
    mapa.atualizar("botao", bounds=Bounds2D(999, 999, 1, 1))
    mapa.remover("rodape")
    depois = snap.bounds_global("botao")
    assert antes == depois == {"x": 200.0, "y": 170.0, "largura": 120.0,
                               "altura": 40.0}
    assert "rodape" in snap.ids()  # snapshot preserva removido
    assert "botao" in debug_geometria(snap)


# 21. regiões: entidades dentro

def test_regiao_entidades():
    mapa = mapa_amostra()
    dentro = sorted(n.id for n in mapa.entidades_na_regiao("reg_conteudo"))
    assert dentro == ["botao", "card", "conteudo"]


# 22. regiões sobrepostas

def test_regioes_sobrepostas():
    mapa = GeometryMap("r")
    mapa.adicionar_regiao(GeometryRegion("a", Bounds2D(0, 0, 100, 100)))
    mapa.adicionar_regiao(GeometryRegion("b", Bounds2D(50, 50, 100, 100)))
    mapa.adicionar_regiao(GeometryRegion("c", Bounds2D(500, 500, 10, 10)))
    assert [r.id for r in mapa.regioes_sobrepostas("a")] == ["b"]
    assert [r.id for r in mapa.regioes_com_ponto(Point2D(60, 60))] == ["a",
                                                                      "b"]


# 23. visibilidade (estado, sem composição)

def test_visibilidade():
    mapa = GeometryMap("v")
    mapa.adicionar(GeometryNode("vis", Bounds2D(0, 0, 10, 10)))
    mapa.adicionar(GeometryNode("ocu", Bounds2D(0, 0, 10, 10),
                                visible=False))
    assert mapa.obter("vis").visible is True
    assert mapa.obter("ocu").visible is False
    mundo = geometria_para_world(mapa)
    assert "ocu" not in [e for e in mundo._ordem]  # invisível fora
    assert "vis" in [e for e in mundo._ordem]


# 24. z-index ordena deterministicamente

def test_zindex():
    mapa = GeometryMap("z")
    mapa.adicionar(GeometryNode("a", Bounds2D(0, 0, 5, 5), z_index=10))
    mapa.adicionar(GeometryNode("b", Bounds2D(0, 0, 5, 5), z_index=-1))
    mapa.adicionar(GeometryNode("c", Bounds2D(0, 0, 5, 5), z_index=10))
    assert [n.id for n in mapa.ordenar_z()] == ["b", "a", "c"]


# 25. buscar_por_ponto

def test_buscar_por_ponto():
    mapa = mapa_amostra()
    achados = sorted(n.id for n in mapa.buscar_por_ponto(Point2D(5, 5)))
    assert achados == ["cabecalho", "janela"]
    assert mapa.buscar_por_ponto(Point2D(5000, 5000)) == []


# 26. buscar_por_area

def test_buscar_por_area():
    mapa = mapa_amostra()
    achados = sorted(
        n.id for n in mapa.buscar_por_area(Bounds2D(0, 0, 800, 60)))
    assert "cabecalho" in achados and "menu" not in achados


# 27. buscar_por_regiao

def test_buscar_por_regiao():
    mapa = mapa_amostra()
    assert sorted(
        n.id for n in mapa.buscar_por_regiao("reg_conteudo")) == [
            "botao", "card", "conteudo"]


# 28. buscar_proximos (determinístico, empate por id)

def test_buscar_proximos():
    mapa = GeometryMap("p")
    mapa.adicionar(GeometryNode("a", Bounds2D(0, 0, 10, 10)))
    mapa.adicionar(GeometryNode("b", Bounds2D(100, 0, 10, 10)))
    mapa.adicionar(GeometryNode("c", Bounds2D(200, 0, 10, 10)))
    prox = mapa.buscar_proximos(Point2D(0, 0), limite=2)
    assert [p["id"] for p in prox] == ["a", "b"]
    assert prox[0]["distancia"] == pytest.approx(7.071, abs=0.01)
    assert mapa.buscar_proximos(Point2D(0, 0), limite=0) == []


# 29. buscar_direcao

def test_buscar_direcao():
    mapa = mapa_amostra()
    assert "rodape" in [n.id for n in mapa.buscar_direcao("cabecalho",
                                                          "sul")]
    assert "cabecalho" in [n.id for n in mapa.buscar_direcao("rodape",
                                                             "norte")]
    with pytest.raises(ErroELiXX):
        mapa.buscar_direcao("cabecalho", "cima")


# 30. buscar_intersecoes

def test_buscar_intersecoes():
    mapa = mapa_amostra()
    achados = sorted(n.id for n in mapa.buscar_intersecoes(
        Bounds2D(160, 70, 50, 50)))
    assert "conteudo" in achados


# 31. relações acima/abaixo/esquerda/direita/dentro/contem

def test_relacoes_direcionais():
    mapa = mapa_amostra()
    assert "cabecalho" in mapa.acima_de("rodape")
    assert "rodape" in mapa.abaixo_de("cabecalho")
    assert "menu" in mapa.a_esquerda_de("conteudo")
    assert "conteudo" in mapa.a_direita_de("menu")
    rel = mapa.relacao("conteudo", "card")
    assert rel["contem"] is True
    rel2 = mapa.relacao("card", "conteudo")
    assert rel2["dentro"] is True
    assert rel2["direcao"] in set(DIRECOES)


# 32. integração Environment (só explícita)

def test_environment_integration():
    from elixx.visual.ambiente import Environment, EnvironmentNode

    env = Environment("e", tipo="web")
    env.adicionar_no(EnvironmentNode("com_geo", tipo="botao", x=10,
                                     y=20, largura=30, altura=40))
    env.adicionar_no(EnvironmentNode("sem_geo", tipo="botao"))
    mapa, ausentes = environment_para_geometria(env)
    assert "com_geo" in mapa and "sem_geo" not in mapa
    assert ausentes == ["sem_geo"]  # ausente, sem inventar
    # explícita vence e inclui nó sem geometria própria
    mapa2, aus2 = environment_para_geometria(
        env, geometria={"sem_geo": {"x": 1, "y": 2, "largura": 3,
                                    "altura": 4}})
    assert "sem_geo" in mapa2 and aus2 == []
    assert mapa2.obter("sem_geo").metadata["fonte"] == "explicita"


# 33. integração World (sem duplicar)

def test_world_integration():
    mapa = mapa_amostra()
    mundo = geometria_para_world(mapa)
    assert mundo.por_id("botao").props["geo_id"] == "botao"
    assert mundo.por_id("reg_conteudo").tipo == "area"
    # vínculo em world existente: atualiza, não duplica
    n_antes = len(mundo)
    rel = vincular_geometria_world(mundo, mapa)
    assert len(mundo) == n_antes
    assert "botao" in rel["atualizadas"]


# 34. JSON/dict roundtrip

def test_json_roundtrip():
    mapa = mapa_amostra()
    texto = mapa.to_json()
    copia = GeometryMap.from_json(texto)
    assert copia.to_json() == texto
    assert copia.bounds_global("botao") == mapa.bounds_global("botao")
    json.dumps(mapa.snapshot().to_dict())


# 35. NaN recusado

def test_nan_recusado():
    with pytest.raises(ErroELiXX):
        GeometryNode("n", Bounds2D(float("nan"), 0, 1, 1))
    with pytest.raises(ErroELiXX):
        GeometryMap.from_json('{"nome": "x", "nos": [{"id": "a", '
                              '"bounds": {"x": NaN}}]}')
    with pytest.raises(ErroELiXX):
        parsear_mapa_explicito({"a": {"x": float("nan")}})


# 36. Infinity recusado

def test_infinity_recusado():
    with pytest.raises(ErroELiXX):
        Bounds2D(0, 0, float("inf"), 1) if False else GeometryNode(
            "n", Bounds2D(0, 0, float("inf"), 1))
    with pytest.raises(ErroELiXX):
        parsear_mapa_explicito({"a": {"y": float("-inf")}})


# 37. valores gigantes recusados

def test_gigantes_recusados():
    with pytest.raises(ErroELiXX):
        GeometryNode("g", Bounds2D(1e18, 0, 1, 1))
    with pytest.raises(ErroELiXX):
        parsear_mapa_explicito({"a": {"largura": 1e15}})


# 38. estruturas inválidas recusadas

def test_estruturas_invalidas():
    with pytest.raises(ErroELiXX):
        GeometryMap.from_dict({"nome": "x", "nos": "nao-lista"})
    with pytest.raises(ErroELiXX):
        GeometryMap.from_dict({"nome": "x", "nos": [{"id": ""}]})
    with pytest.raises(ErroELiXX):
        parsear_mapa_explicito({"a": [1, 2, 3]})
    with pytest.raises(ErroELiXX):
        parsear_mapa_explicito({"a": {"x": 1, "truque": "exec()"}})
    with pytest.raises(ErroELiXX):
        GeometryNode("n", Bounds2D(0, 0, 1, 1),
                     metadata={"f": object()})
    with pytest.raises(ErroELiXX):
        GeometryMap.from_json("{invalido")


# 39. determinismo

def test_determinismo():
    a = mapa_amostra().to_json()
    b = mapa_amostra().to_json()
    assert a == b
    m1, m2 = mapa_amostra(), mapa_amostra()
    assert (m1.buscar_proximos(Point2D(400, 300), 3)
            == m2.buscar_proximos(Point2D(400, 300), 3))
    assert (m1.relacao("menu", "conteudo")
            == m2.relacao("menu", "conteudo"))


# 40. segurança (sem execução dinâmica)

def test_seguranca():
    import elixx.visual.geometria as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("eval(", "exec(", "__import__", "importlib",
                     "subprocess", "os.system", "shell", "requests",
                     "urlopen", "socket", "playwright", "selenium",
                     "compile("):
        assert proibido not in fonte, proibido
    # strings maliciosas seguem inertes como ids/metadata
    mapa = GeometryMap("s")
    mapa.adicionar(GeometryNode("__import__('os')",
                                Bounds2D(0, 0, 5, 5),
                                metadata={"x": "<script>alert(1)</script>"}))
    assert "__import__('os')" in mapa
    assert mapa.to_json()


# 41. performance (criação, consultas, snapshot, relações)

def test_performance():
    for total in (100, 1000, 5000, 10000):
        mapa = GeometryMap("p")
        t0 = time.perf_counter()
        for i in range(total):
            mapa.adicionar(GeometryNode(
                f"n{i:05d}",
                Bounds2D(i % 200 * 5.0, i // 200 * 5.0, 4.0, 4.0)))
        t_cria = time.perf_counter()
        mapa.buscar_por_ponto(Point2D(10, 10))
        mapa.buscar_proximos(Point2D(10, 10), 5)
        mapa.buscar_por_area(Bounds2D(0, 0, 500, 500))
        t_cons = time.perf_counter()
        snap = mapa.snapshot()
        snap.ids()
        t_snap = time.perf_counter()
        mapa.relacao("n00000", f"n{total - 1:05d}")
        t_rel = time.perf_counter()
        assert (t_rel - t0) < 60.0, f"{total} nós passou de 60s"
        if total == 10000:
            print(f"\n10000 nós: cria={t_cria - t0:.2f}s "
                  f"consultas={t_cons - t_cria:.2f}s "
                  f"snapshot={t_snap - t_cons:.2f}s "
                  f"rel={t_rel - t_snap:.2f}s")


# 42. mapa explícito end-to-end (HTML-like: botão entrar)

def test_mapa_explicito_botao():
    mapa = parsear_mapa_explicito({
        "botao_entrar": {"x": 420, "y": 280, "largura": 120,
                         "altura": 40}})
    no = mapa.obter("botao_entrar")
    assert (no.bounds.x, no.bounds.y) == (420.0, 280.0)
    c = mapa.centro_global("botao_entrar")
    assert (c.x, c.y) == (480.0, 300.0)


# 43. F20 + F21: Environment HTML sem geometria → tudo ausente

def test_f20_sem_geometria_tudo_ausente():
    from elixx.visual.html_ambiente import HTMLAdapter

    env, _ = HTMLAdapter.parsear(
        "<main><button id='b'>OK</button></main>", env_id="p")
    mapa, ausentes = environment_para_geometria(env)
    assert len(mapa) == 0  # 0,0,0,0 não vira geometria falsa
    assert "b" in ausentes


# 44. debug legível

def test_debug():
    texto = debug_geometria(mapa_amostra())
    for trecho in ("GeometryMap demo", "botao", "pos=(200,170)",
                   "tam=120x40", "centro=(260,190)", "REGIOES:",
                   "reg_conteudo", "z="):
        assert trecho in texto, trecho


# 45. sem sistemas paralelos (sem Navigation/Motion/CSS próprios)

def test_sem_sistemas_paralelos():
    import elixx.visual.geometria as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("class NavigationGraph", "class Motion",
                     "class Transform", "playwright", "selenium",
                     "yolo", "tesseract", "openai", "cssutils"):
        assert proibido.lower() not in fonte.lower(), proibido
    # integração com F15 é só leitura futura: sem pathfinding aqui
    assert "heapq" not in fonte and "Dijkstra" not in fonte
