"""Testes do parser: janela, botão, propriedades, eventos, blocos,
funções e erros (mensagens em português com exemplo)."""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.erros import ErroSintatico


def parse(fonte):
    return Parser(tokenizar(fonte)).parse()


EXEMPLO = '''
janela principal {
    titulo: "Minha primeira aplicação"
    tamanho: 800px 600px
    botão teste {
        texto: "Olá ELiXX"
        quando clicar {
            mostrar("Olá, mundo!")
        }
    }
}
'''


def test_janela_com_titulo_e_tamanho():
    prog = parse(EXEMPLO)
    jan = prog.janelas[0]
    assert jan.nome == 'principal'
    nomes = {p.nome for p in jan.propriedades}
    assert {'titulo', 'tamanho'} <= nomes


def test_medida_nao_vira_string():
    prog = parse(EXEMPLO)
    tam = next(p for p in prog.janelas[0].propriedades
               if p.nome == 'tamanho')
    assert isinstance(tam.valores[0], A.Medida)
    assert (tam.valores[0].valor, tam.valores[0].unidade) == (800.0, 'px')


def test_botao_com_evento():
    prog = parse(EXEMPLO)
    botao = prog.janelas[0].componentes[0]
    assert (botao.tipo, botao.nome) == ('botao', 'teste')
    assert botao.eventos[0].nome == 'clicar'
    acao = botao.eventos[0].bloco.comandos[0]
    assert isinstance(acao, A.Acao) and acao.nome == 'mostrar'


def test_texto_com_dois_pontos_eh_propriedade():
    prog = parse('janela a {\n titulo: "x"\n botão b {\n texto: "Oi"\n }\n}')
    botao = prog.janelas[0].componentes[0]
    assert botao.propriedades[0].nome == 'texto'


def test_novo_evento_nao_quebra_parser():
    # parser aceita qualquer nome; a semântica valida depois
    prog = parse('janela a {\n titulo: "x"\n quando arrastar {\n mostrar("f")\n }\n}')
    assert prog.janelas[0].eventos[0].nome == 'arrastar'


def test_funcao_se_repetir():
    prog = parse('função dobrar(v) {\n retornar v * 2\n}\n'
                 'janela a {\n titulo: "x"\n botão b {\n texto: "y"\n'
                 ' quando clicar {\n se 1 < 2 {\n mostrar("a")\n }\n'
                 ' repetir 2 vezes {\n mostrar("b")\n }\n }\n }\n}')
    assert prog.funcoes[0].nome == 'dobrar'
    cmds = prog.janelas[0].componentes[0].eventos[0].bloco.comandos
    assert isinstance(cmds[0], A.Se)
    assert isinstance(cmds[1], A.Repetir)


def test_janela_sem_chave_erro_em_portugues():
    with pytest.raises(ErroSintatico) as exc:
        parse('janela principal titulo: "x" }')
    msg = str(exc.value)
    assert 'Era esperado' in msg
    assert 'Exemplo correto' in msg


def test_propriedade_sem_valor_erro_com_exemplo():
    with pytest.raises(ErroSintatico) as exc:
        parse('janela a {\n titulo:\n}')
    assert 'tamanho' in str(exc.value)  # exemplo menciona tamanho


def test_programa_sem_janela_erro():
    with pytest.raises(ErroSintatico) as exc:
        parse('função f() {\n retornar 1\n}')
    assert 'janela' in str(exc.value).lower()


def test_cor_nomeada_e_hex():
    prog = parse('janela a {\n titulo: "x"\n fundo: azul\n cor: "#ff0000"\n}')
    props = {p.nome: p.valores[0] for p in prog.janelas[0].propriedades}
    assert isinstance(props['fundo'], A.CorLit)
    assert props['fundo'].formato == 'nomeada'
    assert props['cor'].formato == 'hex'
