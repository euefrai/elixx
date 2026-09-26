"""Testes da Fase 13 — World & Scene Intelligence (determinísticos)."""
import pytest

from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroSemantico, ErroSintatico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.mundo import (
    Bounds2D,
    World,
    WorldEntity,
    vincular_mundos,
)
from elixx.visual.personagem import Pose, vincular_personagens
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


def mundos_de(fonte):
    ex, cena, prog = montar(fonte)
    pers = vincular_personagens(cena)
    return ex, cena, prog, vincular_mundos(cena, prog, pers)


MUNDO = ('janela p {\n titulo: "T"\n'
         ' personagem Heroi {\n  posição: 100px 100px\n'
         '  parte corpo {\n  }\n  parte mao {\n   posição: 10px 0px\n  }\n }\n'
         ' imagem caixa_visual {\n  arquivo: "a.png"\n'
         '  posição: 900px 300px\n  tamanho: 40px 40px\n }\n'
         ' mundo Principal {\n  tamanho: 2000px 1200px\n'
         '  chão piso {\n   posição: 0px 550px\n   tamanho: 2000px 50px\n  }\n'
         '  plataforma superior {\n   posição: 700px 350px\n'
         '   tamanho: 300px 30px\n  }\n'
         '  parede esquerda {\n   posição: 0px 0px\n   tamanho: 40px 600px\n  }\n'
         '  área sala {\n   posição: 100px 100px\n   tamanho: 500px 400px\n  }\n'
         '  área quarto {\n   posição: 150px 150px\n   tamanho: 100px 100px\n'
         '   pai: sala\n  }\n'
         '  ponto objetivo {\n   posição: 900px 300px\n  }\n'
         '  ponto spawn {\n  }\n'
         '  objeto caixa {\n   posição: 900px 300px\n   tamanho: 40px 40px\n'
         '   categoria: "caixa"\n   tag: "interativo"\n'
         '   visual: caixa_visual\n  }\n'
         '  obstáculo muro {\n   posição: 400px 400px\n'
         '   tamanho: 50px 50px\n  }\n'
         '  usar personagem Heroi\n }\n}\n')


def principal():
    _ex, _cena, _prog, mundos = mundos_de(MUNDO)
    return mundos["Principal"]


# ----- 1-5: World, entidade, identidade, tipo, tags -----

def test_world_basico():
    w = principal()
    assert isinstance(w, World)
    assert w.nome == "Principal"
    assert (w.bounds.largura, w.bounds.altura) == (2000.0, 1200.0)
    assert len(w) == 10


def test_entidade_identidade():
    w = principal()
    e = w.por_id("superior")
    assert isinstance(e, WorldEntity)
    assert (e.nome, e.tipo) == ("superior", "plataforma")
    assert "superior" in w
    with pytest.raises(ErroELiXX, match="não existe"):
        w.por_id("fantasma")


def test_tipos_semanticos():
    w = principal()
    assert w.por_id("Heroi").tipo == "personagem"
    assert w.por_id("caixa").tipo == "objeto"
    assert w.por_id("piso").tipo == "chao"
    assert w.por_tipo("parede")[0].nome == "esquerda"
    assert w.por_tipo("ponto")[0].nome in ("objetivo", "spawn")
    with pytest.raises(ErroELiXX):
        w.por_tipo("nave")


def test_tags_categoria():
    w = principal()
    assert w.por_id("caixa").categoria == "caixa"
    assert w.por_id("caixa").tags == ("interativo",)
    assert [e.nome for e in w.por_tag("interativo")] == ["caixa"]
    assert w.por_tag("ausente") == []


def test_entidade_duplicada_erro():
    w = principal()
    with pytest.raises(ErroELiXX, match="repetida"):
        w.adicionar(WorldEntity("caixa", "objeto", w))


# ----- 6-12: Bounds2D -----

def test_bounds_centro():
    b = Bounds2D(700, 350, 300, 30)
    assert b.centro().tupla() == (850.0, 365.0)


def test_contem_ponto():
    b = Bounds2D(100, 100, 500, 400)
    assert b.contem_ponto(Vector2(100, 100))  # borda inclusa
    assert b.contem_ponto(Vector2(350, 300))
    assert not b.contem_ponto(Vector2(601, 300))


def test_intersecao():
    a = Bounds2D(0, 0, 10, 10)
    assert a.intersecta(Bounds2D(5, 5, 10, 10))
    assert not a.intersecta(Bounds2D(10, 0, 5, 5))  # borda não conta
    assert not a.intersecta(Bounds2D(50, 50, 5, 5))


def test_toque_borda():
    a = Bounds2D(0, 0, 10, 10)
    assert a.toca(Bounds2D(10, 0, 5, 5))  # encosta sem área comum
    assert not a.toca(Bounds2D(5, 5, 10, 10))  # sobrepõe: não é toque
    assert not a.toca(Bounds2D(50, 50, 5, 5))
    assert a.toca(Bounds2D(0, 10, 10, 5))  # embaixo


def test_sobreposicao_contem_expandir_uniao():
    a = Bounds2D(0, 0, 10, 10)
    assert a.sobrepoe(Bounds2D(5, 5, 4, 4))
    assert a.contem(Bounds2D(2, 2, 3, 3))
    assert not a.contem(Bounds2D(5, 5, 10, 10))
    assert a.expandir(5) == Bounds2D(-5, -5, 20, 20)
    assert a.uniao(Bounds2D(20, 20, 5, 5)) == Bounds2D(0, 0, 25, 25)
    with pytest.raises(ErroELiXX):
        a.expandir(-1)


# ----- 13-18: distância, direção, relações -----

def test_distancia_centros():
    w = principal()
    d = w.distancia("Heroi", "objetivo")
    assert d == pytest.approx(Vector2(100, 100).distancia(Vector2(900, 300)))


def test_direcao_vetor():
    w = principal()
    v = w.direcao_de("Heroi", "objetivo")
    assert v.tupla() == (800.0, 200.0)


def test_acima_abaixo():
    w = principal()
    assert w.acima_de("superior", "piso")
    assert w.abaixo_de("piso", "superior")
    assert not w.acima_de("piso", "superior")


def test_esquerda_direita():
    w = principal()
    assert w.esquerda_de("esquerda", "superior")
    assert w.direita_de("superior", "esquerda")
    assert not w.esquerda_de("superior", "esquerda")


def test_proximidade():
    w = principal()
    assert w.perto_de("Heroi", "Heroi", raio=0)
    assert not w.perto_de("Heroi", "objetivo", raio=200)
    assert w.perto_de("caixa", "objetivo", raio=50)


def test_contem_dentro_sobrepoe_toca_mundo():
    w = principal()
    assert w.contem("sala", "Heroi")
    assert w.dentro_de("Heroi", "sala")
    assert w.sobrepoe("caixa", "objetivo") is False  # ponto sem área
    # parede atravessa a faixa do piso: há área comum (não é toque)
    assert w.sobrepoe("piso", "esquerda") is True
    assert w.toca("piso", "esquerda") is False
    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n mundo M {\n'
        '  objeto a {\n   posição: 0px 0px\n   tamanho: 10px 10px\n  }\n'
        '  objeto b {\n   posição: 10px 0px\n   tamanho: 10px 10px\n  }\n'
        ' }\n}\n')
    w2 = mundos["M"]
    assert w2.toca("a", "b") is True
    assert w2.sobrepoe("a", "b") is False


# ----- 19-21: região, subregião, POI -----

def test_regiao():
    w = principal()
    dentro = {e.nome for e in w.em_regiao("sala")}
    assert "Heroi" in dentro and "quarto" in dentro
    assert "objetivo" not in dentro
    with pytest.raises(ErroELiXX, match="não é área"):
        w.em_regiao("caixa")


def test_subregiao():
    w = principal()
    assert [a.nome for a in w.subregioes("sala")] == ["quarto"]
    assert w.subregioes("quarto") == []
    with pytest.raises(ErroSemantico, match="Ciclo"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n'
            '  área a {\n   pai: b\n  }\n  área b {\n   pai: a\n  }\n }\n}\n'))


def test_ponto_interesse():
    w = principal()
    poi = w.por_id("objetivo")
    assert poi.tipo == "ponto"
    assert poi.posicao_global().tupla() == (900.0, 300.0)
    assert w.por_id("spawn").posicao_global().tupla() == (0.0, 0.0)


# ----- 22-25: plataforma, parede, chão, obstáculo -----

def test_plataforma_parede_chao_obstaculo():
    w = principal()
    plat = w.por_id("superior")
    assert plat.bounds_global() == Bounds2D(700, 350, 300, 30)
    assert plat.rotacao_global() == 0.0
    assert w.por_id("esquerda").bounds_global().largura == 40.0
    assert w.por_id("piso").bounds_global() == Bounds2D(0, 550, 2000, 50)
    assert w.por_id("muro").tipo == "obstaculo"


# ----- 26-29: personagem, visual, sem-visual, sem-entidade -----

def test_personagem_no_mundo():
    ex, cena, prog, mundos = mundos_de(MUNDO)
    w = mundos["Principal"]
    hero = w.por_id("Heroi")
    assert hero.character is not None
    assert hero.character.nome == "Heroi"
    assert hero.posicao_global().tupla() == (100.0, 100.0)
    assert hero.character.obter_parte("mao") is not None


def test_referencia_visual():
    w = principal()
    caixa = w.por_id("caixa")
    assert caixa.no is not None
    assert caixa.no.nome == "caixa_visual"
    assert caixa.bounds_global() == Bounds2D(900, 300, 40, 40)


def test_entidade_sem_visual():
    w = principal()
    spawn = w.por_id("spawn")
    assert spawn.no is None and spawn.character is None
    assert spawn.bounds_global() == Bounds2D(0, 0, 0, 0)


def test_visual_sem_entidade():
    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n texto solto {\n  texto: "x"\n }\n'
        ' mundo M {\n  ponto a {\n   posição: 0px 0px\n  }\n }\n}\n')
    w = mundos["M"]
    assert "solto" not in w  # visual existe na cena, sem entidade
    assert cena.buscar("solto") is not None


# ----- 30-34: consultas -----

def test_consulta_por_nome():
    w = principal()
    assert w.por_nome("piso").tipo == "chao"


def test_consulta_por_tipo():
    w = principal()
    assert [e.nome for e in w.por_tipo("area")] == ["sala", "quarto"]


def test_consulta_por_tag():
    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n mundo M {\n'
        '  objeto a {\n   tags: "x" "y"\n  }\n'
        '  objeto b {\n   tag: "y"\n  }\n }\n}\n')
    w = mundos["M"]
    assert [e.nome for e in w.por_tag("y")] == ["a", "b"]
    assert [e.nome for e in w.por_tag("x")] == ["a"]


def test_consulta_espacial():
    w = principal()
    caixa = Bounds2D(0, 0, 1000, 400)
    nomes = {e.nome for e in w.na_area(caixa)}
    assert {"Heroi", "superior", "objetivo"} <= nomes
    assert "esquerda" not in nomes and "piso" not in nomes


def test_vizinhos():
    w = principal()
    viz = w.vizinhos("caixa", 100.0)
    assert [e.nome for e in viz] == ["superior", "objetivo"]
    assert w.vizinhos("caixa", 100.0, tipo="ponto")[0].nome == "objetivo"
    assert w.vizinhos("caixa", 1.0) == []
    with pytest.raises(ErroELiXX):
        w.vizinhos("caixa", -5)


def test_sobrepostos():
    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n mundo M {\n'
        '  objeto a {\n   posição: 0px 0px\n   tamanho: 10px 10px\n  }\n'
        '  objeto b {\n   posição: 5px 5px\n   tamanho: 10px 10px\n  }\n'
        '  objeto c {\n   posição: 50px 50px\n   tamanho: 5px 5px\n  }\n'
        ' }\n}\n')
    w = mundos["M"]
    assert [e.nome for e in w.sobrepostos("a")] == ["b"]


# ----- 35-36: viewport -----

def test_viewport_tamanho():
    _ex, cena, prog, mundos = mundos_de(MUNDO)
    assert mundos["Principal"].cena.viewport.largura == 800.0


def test_visibilidade_viewport():
    ex, cena, prog, mundos = mundos_de(MUNDO)
    w = mundos["Principal"]
    visiveis = {e.nome for e in w.visiveis_na_viewport()}
    assert "Heroi" in visiveis  # (100,100) dentro de 800x600
    assert "objetivo" not in visiveis  # x=900 fora
    cena.viewport.x = 800.0  # desloca: objetivo entra, Heroi sai
    visiveis2 = {e.nome for e in w.visiveis_na_viewport()}
    assert "objetivo" in visiveis2
    assert "Heroi" not in visiveis2


# ----- 37-38: snapshot -----

def test_snapshot():
    w = principal()
    snap = w.snapshot()
    assert snap.mundo == "Principal"
    assert len(snap.itens) == 10
    item = snap.por_id("Heroi")
    assert (item.x, item.y, item.tipo) == (100.0, 100.0, "personagem")
    assert ("Heroi", "personagem", 100.0, 100.0, 0.0,
            0.0) in snap.como_tuplas()


def test_snapshot_somente_leitura():
    w = principal()
    snap = w.snapshot()
    with pytest.raises(Exception):
        snap.itens[0].x = 999.0
    with pytest.raises(ErroELiXX, match="ausente"):
        snap.por_id("fantasma")
    antes = snap.como_tuplas()
    w.por_id("Heroi").character.no_raiz.x = 500.0  # mundo muda...
    assert snap.como_tuplas() == antes  # ...snapshot não


# ----- 39-40: character global -----

def test_character_global_no_mundo():
    _ex, _cena, _prog, mundos = mundos_de(MUNDO)
    hero = mundos["Principal"].por_id("Heroi")
    g = hero.character.obter_transform_global("mao")
    assert (g.x, g.y) == (110.0, 100.0)


def test_character_part_global_no_mundo():
    ex, cena, prog, mundos = mundos_de(MUNDO)
    hero = mundos["Principal"].por_id("Heroi")
    hero.character.aplicar_pose(
        Pose(nome="t", entradas={"mao": {"posicao": (50.0, 60.0)}}))
    g = hero.character.obter_transform_global("mao")
    assert (g.x, g.y) == (150.0, 160.0)


# ----- 41: Motion + World -----

def test_motion_world_acompanha():
    from elixx.animacao.motor import MotorAnimacoes, definicao_de_ast

    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n personagem H {\n'
        '  posição: 100px 100px\n  parte b {\n  }\n }\n'
        ' animação anda {\n  alvo: H\n  posição: 100px 100px -> 500px 100px\n'
        '  movimento: linear\n  duração: 1000ms\n }\n'
        ' mundo M {\n  usar personagem H\n }\n}\n')
    w = mundos["M"]
    motor = MotorAnimacoes(ex)
    motor.carregar([definicao_de_ast(a)
                    for a in prog.janelas[0].animacoes], cena)
    motor.iniciar_automaticas()
    assert w.por_id("H").posicao_global().tupla() == (100.0, 100.0)
    motor.atualizar(500)
    assert w.por_id("H").posicao_global().tupla() == (300.0, 100.0)
    motor.atualizar(500)
    assert w.por_id("H").posicao_global().tupla() == (500.0, 100.0)


# ----- 42-45: múltiplas, identidade, remoção, atualização -----

def test_multiplas_entidades():
    w = principal()
    assert len(w.por_tipo("objeto")) + len(w.por_tipo("area")) == 3


def test_identidade_estavel_motion():
    from elixx.animacao.motor import MotorAnimacoes, definicao_de_ast

    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n'
        '  posição: 0px 0px\n }\n'
        ' animação a {\n  alvo: t\n  posição: 0px 0px -> 10px 0px\n'
        '  movimento: linear\n  duração: 100ms\n }\n'
        ' mundo M {\n  objeto o {\n   visual: t\n  }\n }\n}\n')
    w = mundos["M"]
    motor = MotorAnimacoes(ex)
    motor.carregar([definicao_de_ast(a)
                    for a in prog.janelas[0].animacoes], cena)
    motor.iniciar_automaticas()
    motor.atualizar(100)
    assert w.por_id("o").nome == "o"  # identidade, não posição
    assert w.por_id("o").posicao_global().tupla() == (10.0, 0.0)


def test_remocao():
    w = principal()
    removida = w.remover("muro")
    assert removida.nome == "muro"
    assert "muro" not in w
    assert w.por_tipo("obstaculo") == []
    with pytest.raises(ErroELiXX, match="não existe"):
        w.remover("muro")


def test_atualizacao_sem_copia():
    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n'
        '  posição: 5px 5px\n }\n'
        ' mundo M {\n  objeto o {\n   visual: t\n  }\n }\n}\n')
    w = mundos["M"]
    assert w.por_id("o").posicao_global().tupla() == (5.0, 5.0)
    cena.buscar("t").x = 42.0  # muda a cena...
    assert w.por_id("o").posicao_global().tupla() == (42.0, 5.0)


# ----- gramática e semântica -----

def test_mundo_parse_arvore():
    prog = analisar_expandir(MUNDO)
    from elixx.compilador.ast import mostrar_arvore

    arvore = mostrar_arvore(prog)
    assert "Mundo Principal" in arvore
    assert "Entidade plataforma superior" in arvore
    validar(prog)


def test_mundo_erros_claros():
    with pytest.raises(ErroSemantico, match="repetida"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n'
            '  ponto a {\n  }\n  ponto a {\n  }\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="não encontrado"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n'
            '  usar personagem Fantasma\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="não encontrado"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n'
            '  objeto o {\n   visual: nada\n  }\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="não é personagem"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
            ' mundo M {\n  usar personagem t\n }\n}\n'))
    with pytest.raises(ErroSintatico):
        analisar('janela p {\n titulo: "T"\n mundo M {\n'
                 '  nave x {\n  }\n }\n}\n')


def test_tamanho_explicito_vence_visual():
    ex, cena, prog, mundos = mundos_de(
        'janela p {\n titulo: "T"\n imagem v {\n  arquivo: "a.png"\n'
        '  posição: 0px 0px\n  tamanho: 10px 10px\n }\n'
        ' mundo M {\n  objeto sem {\n   visual: v\n  }\n'
        '  objeto com {\n   visual: v\n   tamanho: 100px 20px\n  }\n'
        ' }\n}\n')
    w = mundos["M"]
    assert w.por_id("sem").bounds_global() == Bounds2D(0, 0, 10, 10)
    assert w.por_id("com").bounds_global() == Bounds2D(0, 0, 100, 20)


def test_debug_texto():
    w = principal()
    texto = w.debug_texto()
    assert "World Principal" in texto
    assert "[personagem] Heroi" in texto
    assert "região sala" in texto


def test_exemplo_world_core():
    with open("exemplos/world-core.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    pers = vincular_personagens(cena)
    mundos = vincular_mundos(cena, prog, pers)
    assert "Mundo" in mundos
