"""Hardening Fase 09.5 — integração, bordas e regressão dirigida.

M02-M11: combinações F08+F09, aninhamento, reconciliação extrema,
chaves, eventos em lista, contexto, escopo negativo, módulos e ciclos.
Determinísticos (sem Tk, sem rede, sem máquina).
"""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.modulos import carregar_programa
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroExecucao, ErroSemantico, ErroSintatico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.reativo import Vinculador


def analisar_expandir(fonte):
    prog = Parser(tokenizar(fonte)).parse()
    expandir_componentes(prog)
    return prog


def montar(fonte, fontes=None):
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor(fontes=fontes)
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    return executor, cena, prog


def reconciliar(executor, cena, nome_lista, valores, chave=None):
    no = cena.buscar(nome_lista)
    return executor.listas.reconciliar(no, valores, chave)


# ----- M02: integração F08+F09 -----

def test_integracao_tema_estado_local_lista_acao_funcao():
    fonte = (
        'tema escuro {\n cores {\n  fundo: "#111111"\n }\n}\n'
        'estado {\n titulo_app: "Loja"\n}\n'
        'componente Cartao {\n'
        ' propriedade titulo\n'
        ' estado {\n  vezes: 0\n }\n'
        ' corpo {\n  texto rot {\n   origem: local.vezes\n  }\n'
        '  botão ver {\n   texto: param.titulo\n   quando clicar {\n'
        '    local.vezes += 1\n   }\n  }\n }\n}\n'
        'funcao dobra(x) {\n retornar x * 2\n}\n'
        'acao registrar(nome) {\n estado.ultimo = nome\n}\n'
        'janela principal {\n titulo: "App"\n tema: "escuro"\n'
        ' fundo: tema.fundo\n'
        ' Cartao c1 {\n  titulo: "Loja"\n }\n'
        ' Cartao c2 {\n  titulo: "Extra"\n }\n'
        ' lista itens {\n  origem: estado.nomes\n'
        '  modelo {\n   texto nome {\n    origem: item\n   }\n  }\n }\n'
        ' botão sel {\n texto: "ok"\n  quando clicar {\n'
        '   executar registrar("ana")\n  }\n }\n}\n'
        'estado_extra_ignorado: 0\n')
    # estado extra fora de bloco é erro de parse; remove a linha:
    fonte = fonte.replace('estado_extra_ignorado: 0\n', '')
    prog = analisar_expandir(
        fonte.replace('estado {\n titulo_app: "Loja"\n}\n',
                      'estado {\n titulo_app: "Loja"\n nomes: ["a"]\n'
                      ' ultimo: ""\n}\n'))
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert executor.estado.obter("c1__vezes") == 0.0
    executor.simular_clique("c1__ver")
    assert executor.estado.obter("c1__vezes") == 1.0
    assert executor.estado.obter("c2__vezes") == 0.0
    executor.simular_clique("sel")
    assert executor.estado.obter("ultimo") == "ana"
    assert executor.tema_atual == "escuro"
    assert executor.avaliar(A.Chamada(
        nome="dobra", args=[A.NumeroLit(valor=21.0)])) == 42.0


# ----- M03: componente dentro de componente -----

def test_aninhamento_tres_niveis_isolado():
    fonte = (
        'componente C {\n'
        ' estado {\n  v: 1\n }\n'
        ' corpo {\n  texto t {\n   origem: local.v\n  }\n }\n}\n'
        'componente B {\n'
        ' propriedade titulo\n'
        ' estado {\n  v: 10\n }\n'
        ' corpo {\n  texto tb {\n   origem: local.v\n  }\n'
        '  C interno {\n  }\n }\n}\n'
        'componente A {\n corpo {\n  B meio {\n   titulo: "x"\n  }\n }\n}\n'
        'janela p {\n titulo: "T"\n A topo {\n }\n}\n')
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert executor.estado.obter("topo__meio__v") == 10.0
    assert executor.estado.obter("topo__meio__interno__v") == 1.0
    # nomes internos não vazam para o escopo global
    with pytest.raises(ErroExecucao):
        executor.estado.obter("v")


def test_ciclo_tres_niveis_detectado():
    fonte = (
        'componente A {\n corpo {\n  B x {\n  }\n }\n}\n'
        'componente B {\n corpo {\n  C y {\n  }\n }\n}\n'
        'componente C {\n corpo {\n  A z {\n  }\n }\n}\n'
        'janela p {\n titulo: "T"\n A topo {\n }\n}\n')
    with pytest.raises(ErroSemantico, match="recursivo"):
        expandir_componentes(analisar(fonte))


def test_ciclo_quatro_niveis_detectado():
    corpo_a = 'componente A {\n corpo {\n  B x {\n  }\n }\n}\n'
    corpo_b = 'componente B {\n corpo {\n  C y {\n  }\n }\n}\n'
    corpo_c = 'componente C {\n corpo {\n  D z {\n  }\n }\n}\n'
    corpo_d = 'componente D {\n corpo {\n  A w {\n  }\n }\n}\n'
    fonte = (corpo_a + corpo_b + corpo_c + corpo_d +
             'janela p {\n titulo: "T"\n A topo {\n }\n}\n')
    with pytest.raises(ErroSemantico, match="A.*B.*C.*D"):
        expandir_componentes(analisar(fonte))


# ----- M05: reconciliação extrema -----

def test_reconciliacao_extrema_sequencia():
    executor, cena, _prog = montar(
        'estado {\n itens: []\n}\n'
        'janela p {\n titulo: "T"\n lista itens {\n'
        '  origem: estado.itens\n  tamanho: 300px 200px\n'
        '  modelo {\n   texto nome {\n    origem: item.nome\n   }\n  }\n }\n}\n')
    no = cena.buscar("itens")
    ger = executor.listas
    seqs = [[], ["A"], ["A", "B"], ["A", "B", "C"], ["C", "B", "A"],
            ["B", "C"], ["C"], [], ["A", "B", "C", "D", "E"]]
    esperados = [[], ["0"], ["0", "1"], ["0", "1", "2"], ["0", "1", "2"],
                 ["0", "1"], ["0"], [], ["0", "1", "2", "3", "4"]]
    for valores, chaves in zip(seqs, esperados):
        plano = ger.reconciliar(no, valores, None)
        assert [l["chave"] for l in plano["linhas"]] == chaves
    # depois de tudo: namespaces das 5 linhas vivas
    assert set(executor.locais) == {f"itens#{i}" for i in range(5)}
    # destruir tudo e recriar não deixa referências
    plano = ger.reconciliar(no, [], None)
    assert plano["linhas"] == []
    assert ger.linhas[id(no)] == {}


def test_reconciliacao_preserva_estado_local():
    executor, cena, _prog = montar(
        'janela p {\n titulo: "T"\n lista itens {\n'
        '  origem: estado.itens\n  tamanho: 300px 200px\n'
        '  modelo {\n   texto nome {\n    origem: item.nome\n   }\n  }\n }\n}\n'
        'estado {\n itens: []\n}\n')
    no = cena.buscar("itens")
    ger = executor.listas
    itens = [{"id": 1, "nome": "Ana"}, {"id": 2, "nome": "Beto"}]
    ger.reconciliar(no, itens, _membro_id())
    ns_beto = "itens#2"
    executor.definir_local(ns_beto, "nota", "vip")
    itens2 = [{"id": 1, "nome": "Ana"}, {"id": 2, "nome": "Beto"},
              {"id": 3, "nome": "Carlos"}]
    ger.reconciliar(no, itens2, _membro_id())
    assert executor.obter_local(ns_beto, "nota") == "vip"
    assert f"itens#3" in executor.locais


def _membro_id():
    return A.Membro(base=A.Ident(nome="item"), atributo="id")


# ----- M06: chaves -----

def test_chave_duplicada_ultimo_vence_documentado():
    executor, cena, _prog = montar(
        'janela p {\n titulo: "T"\n lista itens {\n'
        '  origem: estado.itens\n  tamanho: 300px 200px\n'
        '  modelo {\n   texto nome {\n    origem: item.nome\n   }\n  }\n }\n}\n'
        'estado {\n itens: []\n}\n')
    no = cena.buscar("itens")
    plano = executor.listas.reconciliar(
        no, [{"id": 1, "nome": "A"}, {"id": 1, "nome": "B"}], _membro_id())
    assert [l["chave"] for l in plano["linhas"]] == ["1"]
    assert plano["linhas"][0]["item"] == {"id": 1, "nome": "B"}


def test_chave_inexistente_cai_para_indice():
    executor, cena, _prog = montar(
        'janela p {\n titulo: "T"\n lista itens {\n'
        '  origem: estado.itens\n  tamanho: 300px 200px\n'
        '  modelo {\n   texto nome {\n    origem: item.nome\n   }\n  }\n }\n}\n'
        'estado {\n itens: []\n}\n')
    no = cena.buscar("itens")
    plano = executor.listas.reconciliar(
        no, [{"nome": "Ana"}], _membro_id())
    assert [l["chave"] for l in plano["linhas"]] == ["0"]


def test_item_sem_chave_expressao_invalida_erro():
    prog = analisar_expandir(
        'janela p {\n titulo: "T"\n lista itens {\n'
        '  origem: estado.itens\n  chave: 123\n'
        '  modelo {\n   texto nome {\n    origem: item.nome\n   }\n  }\n }\n}\n'
        'estado {\n itens: []\n}\n')
    with pytest.raises(ErroSemantico, match="caminho"):
        validar(prog)


def test_atualizacao_parcial_mesma_chave():
    executor, cena, _prog = montar(
        'janela p {\n titulo: "T"\n lista itens {\n'
        '  origem: estado.itens\n  tamanho: 300px 200px\n'
        '  modelo {\n   texto nome {\n    origem: item.nome\n   }\n  }\n }\n}\n'
        'estado {\n itens: []\n}\n')
    no = cena.buscar("itens")
    ger = executor.listas
    ger.reconciliar(no, [{"id": 1, "nome": "Ana"}], _membro_id())
    copias_antes = [id(c) for c in ger.linhas[id(no)]["1"]["copias"]]
    plano = ger.reconciliar(no, [{"id": 1, "nome": "Ana Maria"}],
                            _membro_id())
    assert plano["removidas"] == []
    copias_depois = [id(c) for c in ger.linhas[id(no)]["1"]["copias"]]
    assert copias_antes == copias_depois  # mesma identidade
    assert ger.linhas[id(no)]["1"]["item"] == {"id": 1, "nome": "Ana Maria"}


# ----- M07: eventos em lista (item correto, sempre) -----

def _lista_com_botao():
    return ('componente Linha {\n'
            ' corpo {\n  texto nome {\n   origem: item.nome\n  }\n'
            '  botão excluir {\n   texto: "X"\n   quando clicar {\n'
            '    executar apagar(item.id)\n   }\n  }\n }\n}\n'
            'acao apagar(id) {\n estado.apagado = id\n}\n'
            'estado {\n apagado: -1\n itens: []\n}\n'
            'janela p {\n titulo: "T"\n lista itens {\n'
            '  origem: estado.itens\n  chave: item.id\n'
            '  tamanho: 300px 200px\n'
            '  modelo {\n   Linha linha {\n   }\n  }\n }\n}\n')


def _disparar_linha(executor, cena, chave):
    no = cena.buscar("itens")
    ger = executor.listas
    linha = ger.linhas[id(no)][chave]
    for copia in linha["copias"]:
        for sub in [copia] + copia.todos()[1:]:
            if sub.tipo == "botao":
                assert ger.despachar_no(sub, "clicar", linha) is True
                return
    raise AssertionError("botão não encontrado na linha")


def test_evento_na_linha_certa_A_B_C():
    executor, cena, _prog = montar(_lista_com_botao())
    no = cena.buscar("itens")
    ger = executor.listas
    ger.reconciliar(no, [
        {"id": 1, "nome": "Ana"}, {"id": 2, "nome": "Beto"},
        {"id": 3, "nome": "Carlos"}], _membro_id())
    _disparar_linha(executor, cena, "2")
    assert executor.estado.obter("apagado") == 2
    _disparar_linha(executor, cena, "1")
    assert executor.estado.obter("apagado") == 1
    _disparar_linha(executor, cena, "3")
    assert executor.estado.obter("apagado") == 3


def test_evento_correto_apos_reordenar_e_trocar():
    executor, cena, _prog = montar(_lista_com_botao())
    no = cena.buscar("itens")
    ger = executor.listas
    ger.reconciliar(no, [
        {"id": 1, "nome": "Ana"}, {"id": 2, "nome": "Beto"}], _membro_id())
    _disparar_linha(executor, cena, "2")
    assert executor.estado.obter("apagado") == 2
    # reordena e troca a coleção inteira
    ger.reconciliar(no, [
        {"id": 9, "nome": "Zoe"}, {"id": 2, "nome": "Beto 2"}], _membro_id())
    _disparar_linha(executor, cena, "9")
    assert executor.estado.obter("apagado") == 9
    _disparar_linha(executor, cena, "2")
    assert executor.estado.obter("apagado") == 2
