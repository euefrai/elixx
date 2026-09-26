"""Testes da Fase 10 — Visual Core 2D + Transform Foundation.

Determinísticos (sem rede, sem máquina). O único teste Tk pula sozinho
sem display (TclError → skip), como prova visual automatizada mínima.
"""
import math

import pytest

from elixx.animacao.motor import MotorAnimacoes, definicao_de_ast
from elixx.compilador import ast as A
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroSemantico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.transform import (Transform, Vector2, Viewport,
                                    aplicar_ponto, combinar,
                                    globais_da_cena, normalizar_graus,
                                    ordem_visual, resolver_pivo)


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


# ----- 1-8: Vector2 -----

def test_vetor_criacao():
    v = Vector2(10, 20)
    assert (v.x, v.y) == (10.0, 20.0)
    assert Vector2().tupla() == (0.0, 0.0)


def test_vetor_soma():
    assert (Vector2(1, 2) + Vector2(3, 4)).tupla() == (4.0, 6.0)


def test_vetor_subtracao():
    assert (Vector2(5, 5) - Vector2(2, 3)).tupla() == (3.0, 2.0)


def test_vetor_escala():
    assert (Vector2(2, 3) * 2).tupla() == (4.0, 6.0)
    assert (2 * Vector2(2, 3)).tupla() == (4.0, 6.0)
    assert (Vector2(4, 6) / 2).tupla() == (2.0, 3.0)
    with pytest.raises(ErroELiXX):
        Vector2(1, 1) / 0


def test_vetor_magnitude():
    assert Vector2(3, 4).magnitude() == 5.0


def test_vetor_normalizacao():
    n = Vector2(3, 4).normalizado()
    assert n.magnitude() == pytest.approx(1.0)
    assert Vector2(0, 0).normalizado().tupla() == (0.0, 0.0)


def test_vetor_distancia():
    assert Vector2(0, 0).distancia(Vector2(3, 4)) == 5.0


def test_vetor_direcao_dot():
    d = Vector2(0, 0).direcao(Vector2(10, 0))
    assert d.tupla() == (1.0, 0.0)
    assert Vector2(1, 0).direcao(Vector2(1, 0)).tupla() == (0.0, 0.0)
    assert Vector2(1, 2).dot(Vector2(3, 4)) == 11.0


# ----- 9-15: Transform base -----

def test_transform_padrao():
    t = Transform()
    assert (t.x, t.y, t.rotacao) == (0.0, 0.0, 0.0)
    assert t.escala == (1.0, 1.0) and t.opacidade == 1.0
    assert (t.pivo_x, t.pivo_y) == (50.0, 50.0)


def test_posicao_linha_e_bloco():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n texto a {\n  texto: "x"\n'
        '  posição: 100px 200px\n }\n'
        ' texto b {\n  texto: "y"\n  posição {\n   x: 30\n   y: 40\n  }\n }\n'
        '}\n')
    assert (cena.buscar("a").x, cena.buscar("a").y) == (100.0, 200.0)
    assert (cena.buscar("b").x, cena.buscar("b").y) == (30.0, 40.0)


def test_rotacao_unidades_normalizacao():
    assert normalizar_graus(720) == 0.0
    assert normalizar_graus(-90) == 270.0
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n'
        ' texto a {\n  texto: "x"\n  rotação: 30deg\n }\n'
        ' texto b {\n  texto: "y"\n  rotação: 1rad\n }\n'
        ' texto c {\n  texto: "z"\n  rotação: 45graus\n }\n'
        ' texto d {\n  texto: "w"\n  rotação: 90\n }\n'
        '}\n')
    assert cena.buscar("a").rotacao == 30.0
    assert cena.buscar("b").rotacao == pytest.approx(math.degrees(1))
    assert cena.buscar("c").rotacao == 45.0
    assert cena.buscar("d").rotacao == 90.0


def test_escala_uniforme_e_independente():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n'
        ' texto a {\n  texto: "x"\n  escala: 1.2\n }\n'
        ' texto b {\n  texto: "y"\n  escala: 1.2 0.8\n }\n'
        ' texto c {\n  texto: "z"\n  escala {\n   x: 2\n   y: 3\n  }\n }\n'
        '}\n')
    a, b, c = cena.buscar("a"), cena.buscar("b"), cena.buscar("c")
    assert (a.escala_x, a.escala_y, a.escala) == (1.2, 1.2, 1.2)
    assert (b.escala_x, b.escala_y) == (1.2, 0.8)
    assert (c.escala_x, c.escala_y) == (2.0, 3.0)


def test_opacidade_valores():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n'
        ' texto a {\n  texto: "x"\n  opacidade: 80%\n }\n'
        ' texto b {\n  texto: "y"\n  opacidade: 0.5\n }\n'
        '}\n')
    assert cena.buscar("a").opacidade == pytest.approx(0.8)
    assert cena.buscar("b").opacidade == pytest.approx(0.5)
    for ruim in ('opacidade: 150%', 'opacidade: 2', 'opacidade: -1'):
        with pytest.raises(ErroSemantico):
            validar(analisar_expandir(
                f'janela p {{\n titulo: "T"\n texto a {{\n  texto: "x"\n'
                f'  {ruim}\n }}\n}}\n'))


def test_pivo_padrao_e_formas():
    padrao = Transform()
    assert resolver_pivo(padrao, 100, 100) == (50.0, 50.0)
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n'
        ' texto a {\n  texto: "x"\n  pivô: 10px 20px\n }\n'
        ' texto b {\n  texto: "y"\n  pivô {\n   x: 25%\n   y: 75%\n  }\n }\n'
        ' texto c {\n  texto: "z"\n }\n'
        '}\n')
    a, b, c = cena.buscar("a"), cena.buscar("b"), cena.buscar("c")
    assert (a.pivo_x, a.pivo_unidade_x) == (10.0, "px")
    assert (b.pivo_x, b.pivo_unidade_y) == (25.0, "%")
    assert (c.pivo_x, c.pivo_unidade_x) == (50.0, "%")
    with pytest.raises(ErroSemantico):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n texto a {\n  texto: "x"\n'
            '  pivô: 10deg 20deg\n }\n}\n'))


# ----- 16-17: composta e hierarquia -----

def test_transformacao_composta_ponto():
    t = Transform(x=0, y=0, rotacao=90, escala_x=1, escala_y=1,
                  pivo_x=50, pivo_y=50, pivo_unidade_x="px",
                  pivo_unidade_y="px")
    got = aplicar_ponto(t, Vector2(100, 0), (100, 100))
    assert (got.x, got.y) == pytest.approx((100.0, 100.0))


def test_pai_filho_translacao():
    pai = Transform(x=100, y=100)
    filho = Transform(x=50, y=0)
    g = combinar(pai, filho)
    assert (g.x, g.y) == (150.0, 100.0)


def test_pai_filho_rotacao():
    pai = Transform(x=100, y=100, rotacao=90)
    filho = Transform(x=10, y=0)
    g = combinar(pai, filho)
    assert (g.x, g.y) == pytest.approx((100.0, 110.0))
    assert g.rotacao == 90.0


def test_pai_filho_escala():
    pai = Transform(x=100, y=100, escala_x=2, escala_y=2)
    filho = Transform(x=10, y=5)
    g = combinar(pai, filho)
    assert (g.x, g.y) == (120.0, 110.0)
    assert g.escala == (2.0, 2.0)


def test_pai_filho_combinado_e_opacidade():
    pai = Transform(x=100, y=100, rotacao=90, escala_x=2, escala_y=2,
                    opacidade=0.5)
    filho = Transform(x=10, y=0, rotacao=10, opacidade=0.5)
    g = combinar(pai, filho)
    assert (g.x, g.y) == pytest.approx((100.0, 120.0))
    assert g.rotacao == 100.0
    assert g.opacidade == pytest.approx(0.25)


# ----- 18-21: grupos, hierarquia, camadas -----

GRUPO = ('janela p {\n titulo: "T"\n grupo heroi {\n  posição: 300px 200px\n'
         '  rotação: 5deg\n  camada: 10\n'
         '  objeto braco {\n   posição: 40px 20px\n   rotação: 20deg\n  }\n'
         '  texto nome {\n   texto: "H"\n  }\n }\n'
         ' texto solto {\n  texto: "S"\n  camada: 20\n }\n}\n')


def test_grupo_parse_hierarquia():
    _ex, cena, _p = montar(GRUPO)
    heroi = cena.buscar("heroi")
    assert heroi is not None and heroi.tipo == "grupo"
    braco = cena.buscar("braco")
    assert braco is not None and braco.tipo == "objeto"
    assert braco.pai is heroi
    assert (heroi.x, heroi.y, heroi.rotacao, heroi.camada) == (
        300.0, 200.0, 5.0, 10.0)


def test_globais_tres_niveis():
    _ex, cena, _p = montar(GRUPO)
    globais = globais_da_cena(cena)
    heroi, braco = cena.buscar("heroi"), cena.buscar("braco")
    g_heroi = globais[id(heroi)]
    assert (g_heroi.x, g_heroi.y) == (300.0, 200.0)
    g_braco = globais[id(braco)]
    # filho (40,20) sob pai em (300,200) com 5°: acompanha a rotação.
    esperado = aplicar_ponto(
        Transform(x=300, y=200, rotacao=5), Vector2(40, 20))
    assert (g_braco.x, g_braco.y) == pytest.approx(
        (esperado.x, esperado.y))
    assert g_braco.rotacao == pytest.approx(25.0)


def test_camadas_ordem_deterministica():
    _ex, cena, _p = montar(GRUPO)
    ordem = [n.nome for n in ordem_visual(cena.janelas[0])]
    assert ordem.index("heroi") < ordem.index("solto")  # 10 < 20
    # empate: ordem estável de criação
    _ex2, cena2, _p2 = montar(
        'janela p {\n titulo: "T"\n texto a {\n  texto: "x"\n }\n'
        ' texto b {\n  texto: "y"\n }\n}\n')
    nomes = [n.nome for n in ordem_visual(cena2.janelas[0])]
    assert nomes == ["a", "b"]


# ----- 22-23: viewport e cena -----

def test_viewport_fundacao():
    vp = Viewport(largura=800, altura=600)
    assert vp.zoom == 1.0
    tela = vp.mundo_para_tela(Vector2(100, 50))
    assert tela.tupla() == (100.0, 50.0)
    mundo = vp.tela_para_mundo(Vector2(100, 50))
    assert mundo.tupla() == (100.0, 50.0)
    with pytest.raises(ErroELiXX):
        Viewport(largura=0, altura=600)
    with pytest.raises(ErroELiXX):
        Viewport(largura=800, altura=600, zoom=0)


def test_cena_tem_viewport_e_globais():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n tamanho: 800px 600px\n'
        ' texto a {\n  texto: "x"\n }\n}\n')
    assert cena.viewport.largura == 800.0
    assert cena.viewport.altura == 600.0
    assert isinstance(cena.globais(), dict)


# ----- 24-26: imagem, SVG, texto -----

def test_imagem_com_transform():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n imagem foto {\n'
        '  arquivo: "a.png"\n  posição: 300px 200px\n  escala: 1.5\n'
        '  rotação: 10deg\n  opacidade: 90%\n }\n}\n')
    no = cena.buscar("foto")
    assert no.fonte_recurso == "arquivo"
    assert (no.x, no.y) == (300.0, 200.0)
    assert (no.escala_x, no.rotacao, no.opacidade) == (
        1.5, 10.0, pytest.approx(0.9))


def test_svg_com_transform():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n imagem vet {\n'
        '  arquivo: "a.svg"\n  escala: 2 0.5\n  camada: 3\n }\n}\n')
    no = cena.buscar("vet")
    assert (no.escala_x, no.escala_y, no.camada) == (2.0, 0.5, 3.0)


def test_texto_com_transform():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "oi"\n'
        '  posição: 20px 30px\n  escala: 2\n }\n}\n')
    no = cena.buscar("t")
    assert (no.x, no.y, no.escala_x) == (20.0, 30.0, 2.0)


# ----- 27: layout preservado -----

def test_layout_compativel():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n tamanho: 800px 600px\n'
        ' texto a {\n  texto: "x"\n  posição: 50% 10%\n }\n'
        ' texto b {\n  texto: "y"\n  tamanho: 50vw 10vh\n }\n'
        ' coluna c {\n  texto d {\n   texto: "z"\n  }\n }\n'
        '}\n')
    assert cena.buscar("a").x == pytest.approx(400.0)
    assert cena.buscar("b").largura == pytest.approx(400.0)
    assert cena.buscar("c") is not None


# ----- animação mínima (Fase 10, sem Motion Core) -----

def test_animacao_rotacao_escala_opacidade():
    prog = analisar_expandir(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
        ' animação a {\n  alvo: t\n  rotação: 0deg -> 90deg\n'
        '  escala: 1 -> 2\n  opacidade: 100% -> 50%\n'
        '  duração: 1000ms\n  movimento: linear\n }\n}\n')
    validar(prog)
    defs = [definicao_de_ast(a) for a in prog.janelas[0].animacoes]
    chaves = {c.propriedade: (c.de, c.para) for c in defs[0].chaves}
    assert chaves["rotacao"] == (0.0, 90.0)
    assert chaves["escala"] == (1.0, 2.0)
    assert chaves["opacidade"] == (1.0, 0.5)


def test_animacao_rad_converte_graus():
    prog = analisar_expandir(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
        ' animação a {\n  alvo: t\n  rotação: 0rad -> 3.14159rad\n'
        '  duração: 500ms\n }\n}\n')
    validar(prog)
    defs = [definicao_de_ast(a) for a in prog.janelas[0].animacoes]
    assert defs[0].chaves[0].para == pytest.approx(180.0, abs=0.01)


def test_animacao_executa_no_motor():
    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
        ' animação a {\n  alvo: t\n  rotação: 0deg -> 90deg\n'
        '  duração: 1000ms\n  movimento: linear\n }\n}\n')
    no = cena.buscar("t")
    motor = MotorAnimacoes()
    motor.carregar([definicao_de_ast(a) for a in _p.janelas[0].animacoes],
                   cena)
    motor.iniciar_automaticas()
    motor.atualizar(500.0)
    assert no.rotacao == pytest.approx(45.0)


# ----- 28: Tk (pula sem display) -----

def test_tk_grupo_escala_camada():
    try:
        from elixx.visual.tk import RenderizadorTk
    except ImportError:
        pytest.skip("Tk indisponível")
    try:
        _ex, cena, _p = montar(
            'janela p {\n titulo: "T"\n tamanho: 400px 300px\n'
            ' grupo g {\n  posição: 10px 10px\n  camada: 1\n'
            '  texto dentro {\n   texto: "oi"\n  }\n }\n'
            ' texto frente {\n  texto: "f"\n  camada: 5\n }\n'
            ' texto scaled {\n  texto: "s"\n  tamanho: 100px 20px\n'
            '  escala: 2\n }\n'
            '}\n')
        rend = RenderizadorTk(_ex)
        rend.montar(cena)
        try:
            rend.raiz.withdraw()
            rend.atualizar(0.0)
            # escala real no tamanho do widget (estado visual aplicado)
            entrada = rend._itens.get(id(cena.buscar("scaled")))
            assert entrada is not None
            widget, _info = entrada
            widget.update_idletasks()
            assert widget.place_info().get("width") == "200"
            # camada: frente (5) desenhada depois de g (1)
            assinatura = rend._camadas_aplicadas
            assert assinatura != ()
        finally:
            rend.fechar()
    except Exception as exc:
        import tkinter as _tk

        if isinstance(exc, _tk.TclError):
            pytest.skip(f"sem display: {exc}")
        raise


# ----- 29: HTML -----

def test_html_transform():
    from elixx.visual.html import gerar_html

    _ex, cena, _p = montar(
        'janela p {\n titulo: "T"\n grupo g {\n  posição: 10px 20px\n'
        '  rotação: 30deg\n  escala: 2\n  opacidade: 50%\n  camada: 7\n '
        ' texto t {\n   texto: "oi"\n  }\n }\n'
        ' texto puro {\n  texto: "x"\n }\n'
        '}\n')
    pagina = gerar_html(_ex.ctx.objetos)
    assert "elx-grupo" in pagina
    assert "translate(10px, 20px)" in pagina
    assert "rotate(30deg)" in pagina
    assert "scale(2, 2)" in pagina
    assert "opacity: 0.5" in pagina
    assert "z-index: 7" in pagina
    # sem transformação → sem style (compatível com o legado)
    assert '<p class="elx-texto">x</p>' in pagina


# ----- 30: inválidos -----

def test_transform_bloco_invalido():
    with pytest.raises(ErroELiXX):
        analisar('janela p {\n titulo: "T"\n texto a {\n  texto: "x"\n'
                 '  posição {\n   x: 1\n  }\n }\n}\n')
    with pytest.raises(ErroELiXX):
        analisar('janela p {\n titulo: "T"\n texto a {\n  texto: "x"\n'
                 '  posição {\n   x: 1\n   z: 2\n  }\n }\n}\n')


def test_props_invalidas():
    for ruim in ('rotação: 10px', 'escala: "x"', 'escala: 1 2 3',
                 'camada: "alta"', 'posição: 1'):
        with pytest.raises(ErroSemantico):
            validar(analisar_expandir(
                f'janela p {{\n titulo: "T"\n texto a {{\n  texto: "x"\n'
                f'  {ruim}\n }}\n}}\n'))


def test_api_invalida():
    with pytest.raises(ErroELiXX):
        Transform(opacidade=2.0)
    with pytest.raises(ErroELiXX):
        Transform(escala_x=float("nan"))
    with pytest.raises(ErroELiXX):
        Transform(x=float("inf"))
    with pytest.raises(ErroELiXX):
        Viewport(largura=800, altura=600, zoom=-1)


# ----- exemplo F10 válido -----

def test_exemplo_visual_core():
    with open("exemplos/visual-core.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    assert cena.buscar("personagem") is not None
    assert cena.buscar("braco") is not None
    globais = cena.globais()
    assert globais[id(cena.buscar("braco"))].rotacao == pytest.approx(30.0)
