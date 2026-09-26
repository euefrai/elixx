"""Testes do runtime: objetos, propriedades, eventos, ações,
semântica e animação/cor (tipos próprios)."""
import pytest

from elixx.animacao import MOVIMENTOS, criar_animacao
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.cores import para_cor
from elixx.erros import ErroExecucao, ErroSemantico
from elixx.runtime.nucleo import Executor
from elixx.unidades import categoria, tempo_para_ms


def executar(fonte):
    prog = analisar(fonte)
    avisos = validar(prog)
    return Executor().executar(prog, avisos)


def test_criacao_objetos_e_defaults():
    res = executar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n }\n}')
    jan = res.objetos[0]
    assert (jan.tipo, jan.nome) == ('janela', 'p')
    assert jan.tamanho == (800.0, 600.0)  # padrão documentado
    assert jan.filhos[0].tipo == 'botao'
    assert jan.filhos[0].visivel is True


def test_propriedade_tamanho_aplicada():
    res = executar('janela p {\n titulo: "T"\n tamanho: 800px 600px\n}')
    assert res.objetos[0].tamanho == (800.0, 600.0)


def test_evento_aparecer_dispara_sozinho():
    res = executar('janela p {\n titulo: "T"\n'
                   ' quando aparecer {\n mostrar("abriu")\n }\n}')
    assert res.saida == ['abriu']


def test_clicar_via_simulacao():
    prog = analisar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                    ' quando clicar {\n mostrar("clicado")\n }\n }\n}')
    validar(prog)
    ex = Executor()
    ex.executar(prog, [])
    assert ex.simular_clique('b') is True
    assert ex.ctx.saida == ['clicado']


def test_funcao_retornar_e_repetir():
    res = executar('função dobrar(v) {\n retornar v * 2\n}\n'
                   'janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                   ' quando aparecer {\n'
                   ' repetir 2 vezes {\n mostrar(dobrar(21))\n }\n }\n }\n}')
    assert res.saida == ['42', '42']


def test_se_senao():
    res = executar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                   ' quando aparecer {\n se 1 > 2 {\n mostrar("a")\n }\n'
                   ' senão {\n mostrar("b")\n }\n }\n }\n}')
    assert res.saida == ['b']


def test_evento_invalido_erro_com_sugestao():
    with pytest.raises(ErroSemantico) as exc:
        executar('janela p {\n titulo: "T"\n quando clikar {\n mostrar("x")\n }\n}')
    assert 'clicar' in str(exc.value)  # "você quis dizer"


def test_acao_invalida_erro_com_sugestao():
    with pytest.raises(ErroSemantico) as exc:
        executar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                 ' quando clicar {\n mostar("x")\n }\n }\n}')
    assert 'mostrar' in str(exc.value)


def test_propriedade_invalida_erro():
    with pytest.raises(ErroSemantico) as exc:
        executar('janela p {\n tamnaho: 1px\n}')
    assert 'tamanho' in str(exc.value)


def test_cor_nomeada_e_hex():
    assert para_cor('vermelho').hexadecimal == '#ff0000'
    assert para_cor('#F00').hexadecimal == '#ff0000'
    with pytest.raises(ErroSemantico):
        para_cor('verde-musgo')


def test_unidades_tempo():
    assert categoria('px') == 'comprimento'
    assert categoria('ms') == 'tempo'
    assert categoria('graus') == 'angulo'
    assert tempo_para_ms(2.0, 's') == 2000.0


def test_animacao_movimento_invalido_sugere():
    anim = criar_animacao('janela', {}, 500.0, 'suave')
    assert anim.movimento == 'suave'
    assert 'linear' in MOVIMENTOS
    with pytest.raises(ErroExecucao) as exc:
        criar_animacao('janela', {}, 500.0, 'suav')
    assert 'suave' in str(exc.value)


def test_repetir_sem_numero_executa_1x_com_aviso():
    ex = Executor()
    prog = analisar('janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                    ' quando aparecer {\n repetir {\n mostrar("x")\n }\n }\n }\n}')
    validar(prog)
    res = ex.executar(prog, [])
    assert res.saida == ['x']
    assert ex.avisos
