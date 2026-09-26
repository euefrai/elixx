"""Testes do lexer: palavras, números, strings, unidades, cores,
comentários e erros (mensagens em português)."""
import pytest

from elixx.compilador.lexer import (
    IDENT, NUMERO, PALAVRA, SINAL, STRING, UNIDADE, tokenizar,
)
from elixx.erros import ErroLexico


def tipos(fonte):
    return [(t.tipo, t.valor) for t in tokenizar(fonte)]


def test_palavras_reservadas():
    # Fase 02: só palavras estruturais são reservadas.
    toks = tipos('janela botão quando se repetir função retornar')
    assert all(t == PALAVRA for t, _ in toks[:-1])  # último é EOF


def test_vocabulario_nao_reservado_pode_ser_nome():
    # Fase 02: ações/eventos/propriedades lexam como IDENT ("botão abrir").
    toks = tipos('abrir clicar mostrar tamanho')
    assert all(t == IDENT for t, _ in toks[:-1])


def test_identificadores():
    toks = tokenizar('principal teste abrir_agora')
    assert [t.valor for t in toks if t.tipo == IDENT] == [
        'principal', 'teste', 'abrir_agora']


def test_numero_com_unidade_grudada():
    toks = tipos('tamanho: 800px 600px')
    nums = [t for t in toks if t[0] == NUMERO]
    unis = [t for t in toks if t[0] == UNIDADE]
    assert nums[0][1] == 800.0
    assert [u[1] for u in unis] == ['px', 'px']


def test_unidades_tempo_e_percentual():
    toks = tipos('duração: 500ms opacidade: 20% espera: 2s')
    unis = [t[1] for t in toks if t[0] == UNIDADE]
    assert unis == ['ms', '%', 's']


def test_unidade_desconhecida_erro_em_portugues():
    with pytest.raises(ErroLexico) as exc:
        tokenizar('tamanho: 10pt')
    msg = str(exc.value).lower()
    assert 'unidade desconhecida' in msg
    assert 'linha 1' in msg


def test_strings_com_escape():
    toks = tokenizar(r'texto: "diz \"oi\""')
    assert toks[2].tipo == STRING
    assert toks[2].valor == 'diz "oi"'


def test_string_nao_fechada_erro_em_portugues():
    with pytest.raises(ErroLexico) as exc:
        tokenizar('texto: "sem fim')
    assert 'aspas' in str(exc.value).lower()


def test_comentarios_hash_e_barra():
    toks = tipos('# comentário\njanela // outro')
    assert (PALAVRA, 'janela') in toks
    assert len([t for t in toks if t[0] == IDENT]) == 0


def test_sinais_e_seta_futura():
    toks = tipos('a: (1 + 2) → b')
    sinais = [t[1] for t in toks if t[0] == SINAL]
    assert sinais == [':', '(', '+', ')', '→']


def test_caractere_invalido_erro_em_portugues():
    with pytest.raises(ErroLexico) as exc:
        tokenizar('janela @')
    assert 'inesperado' in str(exc.value).lower()


def test_linha_e_coluna():
    toks = tokenizar('janela\n  botão')
    botao = [t for t in toks if t.valor == 'botão'][0]
    assert (botao.linha, botao.coluna) == (2, 3)
