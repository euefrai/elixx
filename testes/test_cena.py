"""Testes da árvore visual (Cena): criação, pai/filho, propriedades,
resolução de unidades e coordenadas."""
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import (
    ConstrutorCena, NoVisual, resolver_medida,
)
from elixx.compilador import ast as A


def cena_de(fonte):
    prog = analisar(fonte)
    validar(prog)
    resultado = Executor().executar(prog, [])
    return ConstrutorCena().de_objetos(resultado.objetos)


def test_janela_titulo_tamanho():
    cena = cena_de('janela principal {\n titulo: "App"\n tamanho: 800px 500px\n}')
    jan = cena.janelas[0]
    assert (jan.tipo, jan.nome) == ('janela', 'principal')
    assert jan.titulo == 'App'
    assert (jan.largura, jan.altura) == (800.0, 500.0)


def test_pai_filho_e_busca():
    cena = cena_de('janela p {\n titulo: "T"\n botão abrir {\n texto: "Abrir"\n'
                   ' quando clicar {\n mostrar("oi")\n }\n }\n}')
    jan = cena.janelas[0]
    botao = jan.filhos[0]
    assert botao.pai is jan
    assert cena.buscar('abrir') is botao
    assert botao.ref_objeto is not None  # ponte para o runtime
    assert 'clicar' in botao.eventos  # Bloco AST preservado


def test_botao_sem_posicao_ganha_posicao_provisoria():
    cena = cena_de('janela p {\n titulo: "T"\n botão abrir {\n texto: "Abrir"\n }\n}')
    botao = cena.buscar('abrir')
    assert (botao.x, botao.y) == (20.0, 20.0)


def test_posicao_explicita_respeitada():
    cena = cena_de('janela p {\n titulo: "T"\n tamanho: 800px 500px\n'
                   ' botão b {\n texto: "x"\n posição: 100px 200px\n }\n}')
    botao = cena.buscar('b')
    assert (botao.x, botao.y) == (100.0, 200.0)


def test_porcentagem_resolve_contra_janela():
    cena = cena_de('janela p {\n titulo: "T"\n tamanho: 800px 500px\n'
                   ' botão b {\n texto: "x"\n posição: 50% 10%\n'
                   ' tamanho: 25% 10%\n }\n}')
    botao = cena.buscar('b')
    assert (botao.x, botao.y) == (400.0, 50.0)
    assert (botao.largura, botao.altura) == (200.0, 50.0)


def test_texto_conteudo_fonte_cor():
    cena = cena_de('janela p {\n titulo: "T"\n texto t {\n'
                   ' conteúdo: "Olá"\n fonte: 24px\n cor: vermelho\n }\n}')
    no = cena.buscar('t')
    assert no.texto == 'Olá'
    assert no.fonte_px == 24.0
    assert no.cor_hex == '#ff0000'


def test_alias_texto_preservado():
    cena = cena_de('janela p {\n titulo: "T"\n botão b {\n texto: "Oi"\n }\n}')
    assert cena.buscar('b').texto == 'Oi'


def test_resolver_medida_unidades():
    assert resolver_medida(A.Medida(valor=10, unidade='px'), 800) == 10.0
    assert resolver_medida(A.Medida(valor=50, unidade='%'), 800) == 400.0
    assert resolver_medida(A.Medida(valor=10, unidade='vw'), 800) == 80.0
    assert resolver_medida(A.NumeroLit(valor=7), 800) == 7.0
    assert resolver_medida(A.TextoLit(valor='x'), 800) is None
    assert resolver_medida(A.Medida(valor=1, unidade='graus'), 800) is None


def test_no_todos_pre_ordem():
    cena = cena_de('janela p {\n titulo: "T"\n botão a {\n texto: "x"\n }\n'
                   ' botão b {\n texto: "y"\n }\n}')
    nomes = [n.nome for n in cena.janelas[0].todos()]
    assert nomes == ['p', 'a', 'b']
    assert isinstance(cena.janelas[0], NoVisual)
