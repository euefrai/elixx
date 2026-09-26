"""Testes da AST: estrutura correta, tipos e relações pai/filho."""
from elixx.compilador import ast as A
from elixx.compilador.parser import analisar
from elixx.compilador.ast import mostrar_arvore


def test_hierarquia_programa_janela_botao():
    prog = analisar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                    ' quando clicar {\n mostrar("oi")\n }\n }\n}')
    assert isinstance(prog, A.Programa)
    jan = prog.janelas[0]
    assert isinstance(jan, A.Janela)
    botao = jan.componentes[0]
    assert isinstance(botao, A.Componente) and botao.tipo == 'botao'
    assert jan.componentes[0] is botao  # relação pai/filho preservada


def test_mostrar_arvore_formato():
    prog = analisar('janela p {\n titulo: "T"\n}')
    arvore = mostrar_arvore(prog)
    linhas = arvore.splitlines()
    assert linhas[0] == 'Programa'
    assert linhas[1].startswith('  Janela p')


def test_bloco_e_acao_tipos():
    prog = analisar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                    ' quando aparecer {\n mostrar("a", "b")\n }\n }\n}')
    ev = prog.janelas[0].componentes[0].eventos[0]
    assert isinstance(ev, A.Evento)
    assert isinstance(ev.bloco, A.Bloco)
    acao = ev.bloco.comandos[0]
    assert isinstance(acao, A.Acao)
    assert len(acao.args) == 2


def test_componentes_aninhados():
    prog = analisar('janela p {\n titulo: "T"\n texto caixa {\n texto: "x"\n'
                    ' botão dentro {\n texto: "y"\n }\n }\n}')
    caixa = prog.janelas[0].componentes[0]
    assert caixa.filhos[0].tipo == 'botao'
