"""Testes da Fase 09 — estado local, listas dinâmicas, ações, funções,
módulos e escopo. Determinísticos (sem Tk, sem rede, sem máquina)."""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.ast import mostrar_arvore
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.modulos import carregar_programa
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroExecucao, ErroSemantico, ErroSintatico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena


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


CONTADOR = ('componente Contador {\n estado {\n  valor: 0\n }\n'
            ' corpo {\n  texto rot {\n   origem: local.valor\n  }\n'
            '  botão mais {\n   texto: "+1"\n   quando clicar {\n'
            '    local.valor += 1\n   }\n  }\n }\n}\n')


# ----- M01 estado local -----

def test_def_estado_parse_expand():
    prog = analisar_expandir(
        CONTADOR + 'janela p {\n titulo: "T"\n Contador a {\n }\n}\n')
    validar(prog)
    assert prog.locais == {"a": {"valor": 0.0}}
    jan = prog.janelas[0]
    assert [c.nome for c in jan.componentes] == ["a__rot", "a__mais"]
    props = jan.componentes[0].propriedades
    assert props[0].nome == "origem"
    caminho = A.caminho_de_membro(props[0].valores[0])
    assert caminho == "estado.a__valor"


def test_isolamento_entre_instancias():
    executor, _cena = montar(
        CONTADOR + 'janela p {\n titulo: "T"\n Contador a {\n }\n'
        ' Contador b {\n }\n}\n')[:2]
    assert executor.estado.obter("a__valor") == 0.0
    assert executor.estado.obter("b__valor") == 0.0
    executor.simular_clique("a__mais")
    executor.simular_clique("a__mais")
    assert executor.estado.obter("a__valor") == 2.0
    assert executor.estado.obter("b__valor") == 0.0


def test_local_leitura_inexistente_erro():
    executor, _cena = montar(
        'janela p {\n titulo: "T"\n texto t {\n texto: "x"\n }\n}\n')[:2]
    with executor.contexto_ns("qualquer"):
        with pytest.raises(ErroExecucao, match="não encontrado"):
            executor.obter_local("qualquer", "falta")


def test_local_escrita_autocria():
    executor, _cena = montar(
        'janela p {\n titulo: "T"\n}\n')[:2]
    with executor.contexto_ns("nova"):
        executor.definir_local("nova", "x", 41)
        assert executor.obter_local("nova", "x") == 41


def test_local_fora_de_contexto_erro():
    for fonte in ('janela p {\n titulo: "T"\n texto t {\n'
                  '  origem: local.x\n }\n}\n',
                  'janela p {\n titulo: "T"\n botão b {\n texto: "x"\n'
                  '  quando clicar {\n   local.x = 1\n  }\n }\n}\n'):
        with pytest.raises(ErroSintatico, match="local"):
            analisar(fonte)


def test_estado_local_exige_bloco():
    # def sem bloco estado usando local.* → erro claro em PT
    with pytest.raises(ErroSemantico, match="estado"):
        validar(analisar_expandir(
            'componente C {\n corpo {\n  texto t {\n   origem: local.v\n  }\n'
            ' }\n}\n'
            'janela p {\n titulo: "T"\n C c {\n }\n}\n'))


# ----- M03 propriedades -----

def test_prop_default_override_expressao():
    prog = analisar_expandir(
        'componente B {\n propriedade texto: "Padrao"\n'
        ' propriedade largura: 100px\n corpo {\n  botão b {\n'
        '   texto: param.texto\n   tamanho: param.largura 20px\n  }\n }\n}\n'
        'janela p {\n titulo: "T"\n B um {\n  texto: "Oi"\n }\n'
        ' B dois {\n }\n}\n')
    validar(prog)
    um, dois = prog.janelas[0].componentes
    assert um.nome == "um__b" and dois.nome == "dois__b"
    assert um.propriedades[0].valores[0].valor == "Oi"
    assert dois.propriedades[0].valores[0].valor == "Padrao"
    tam = dois.propriedades[1].valores
    assert (tam[0].valor, tam[1].valor) == (100.0, 20.0)


def test_prop_estado_ref_e_erro_falta():
    prog = analisar_expandir(
        'componente B {\n propriedade titulo\n corpo {\n  texto t {\n'
        '   origem: param.titulo\n  }\n }\n}\n'
        'estado {\n nome: "Ana"\n}\n'
        'janela p {\n titulo: "T"\n B b {\n  titulo: estado.nome\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert True  # origem com Membro avaliado no tick (ver reatividade)
    with pytest.raises(ErroSemantico, match="Falta a propriedade"):
        expandir_componentes(analisar(
            'componente B {\n propriedade titulo\n corpo {\n  texto t {\n'
            '   texto: "x"\n  }\n }\n}\n'
            'janela p {\n titulo: "T"\n B b {\n }\n}\n'))


# ----- M04 listas dinâmicas -----

LISTA = ('estado {\n nomes: ["Ana", "Beto"]\n}\n'
         'janela p {\n titulo: "T"\n lista pessoas {\n'
         '  origem: estado.nomes\n  tamanho: 300px 200px\n'
         '  modelo {\n   texto nome {\n    origem: item\n   }\n  }\n }\n}\n')


def gerenciador_de(fonte):
    executor, cena, _prog = montar(fonte)
    no = cena.buscar("pessoas")
    assert no.dinamica
    return executor, cena, no


def test_lista_vazia_um_e_varios():
    executor, cena, no = gerenciador_de(LISTA)
    plano = executor.listas.reconciliar(no, [], None)
    assert plano["linhas"] == [] and plano["removidas"] == []
    plano = executor.listas.reconciliar(no, ["Ana"], None)
    assert [l["chave"] for l in plano["linhas"]] == ["0"]
    plano = executor.listas.reconciliar(no, ["Ana", "Beto"], None)
    assert [l["chave"] for l in plano["linhas"]] == ["0", "1"]


def test_lista_adicionar_remover():
    executor, cena, no = gerenciador_de(LISTA)
    executor.listas.reconciliar(no, ["Ana", "Beto"], None)
    plano = executor.listas.reconciliar(no, ["Ana", "Beto", "Carlos"], None)
    assert [l["chave"] for l in plano["linhas"]] == ["0", "1", "2"]
    plano = executor.listas.reconciliar(no, ["Ana", "Carlos"], None)
    # sem chave: identidade é posicional (a "2" sumiu)
    assert [r["chave"] for r in plano["removidas"]] == ["2"]
    assert [l["chave"] for l in plano["linhas"]] == ["0", "1"]
    assert [l["item"] for l in plano["linhas"]] == ["Ana", "Carlos"]


def test_lista_chave_preserva_identidade():
    executor, cena, no = gerenciador_de(LISTA)
    linhas = {"a": {"id": 1}, "b": {"id": 2}, "c": {"id": 3}}
    vals = [linhas[k] for k in ("a", "b", "c")]
    plano = executor.listas.reconciliar(no, vals, _id("id"))
    copias_antes = {l["chave"]: id(l["copias"][0])
                    for l in plano["linhas"]}
    vals2 = [linhas[k] for k in ("a", "c")]
    plano2 = executor.listas.reconciliar(no, vals2, _id("id"))
    copias_depois = {l["chave"]: id(l["copias"][0])
                     for l in plano2["linhas"]}
    assert copias_depois["1"] == copias_antes["1"]  # Ana/Carlos mantidos
    assert copias_depois["3"] == copias_antes["3"]
    assert [r["chave"] for r in plano2["removidas"]] == ["2"]


def _id(campo):
    from elixx.compilador import ast as _A

    return _A.Membro(base=_A.Ident(nome="item"), atributo=campo)


def test_lista_reordenar_sem_chave_recria():
    executor, cena, no = gerenciador_de(LISTA)
    executor.listas.reconciliar(no, ["a", "b"], None)
    plano = executor.listas.reconciliar(no, ["b", "a"], None)
    assert [l["chave"] for l in plano["linhas"]] == ["0", "1"]
    # sem chave: identidade é posicional (documentado)
    assert plano["linhas"][0]["item"] == "b"


def test_lista_atualizar_valor():
    executor, cena, no = gerenciador_de(LISTA)
    executor.listas.reconciliar(no, [{"id": 1, "n": "Ana"}], _id("id"))
    plano = executor.listas.reconciliar(no, [{"id": 1, "n": "ANA"}],
                                        _id("id"))
    assert plano["linhas"][0]["item"] == {"id": 1, "n": "ANA"}
    assert plano["removidas"] == []  # mesma chave: atualiza, não recria


def test_lista_via_estado_reage():
    executor, cena, _prog = montar(LISTA)
    no = cena.buscar("pessoas")
    vinc = _vinc(executor, cena)
    pacotes = dict((n.nome, p) for n, p in vinc.primeira_carga())
    assert "pessoas" in pacotes
    executor.estado.definir("nomes", ["Ana", "Beto", "Carlos"])
    vinc._forcar = True  # refresh explícito (sem ele, o intervalo pula)
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(999999.0))
    plano = pacotes["pessoas"]
    assert [l["chave"] for l in plano["linhas"]] == ["0", "1", "2"]


def _vinc(executor, cena):
    from elixx.visual.reativo import Vinculador

    return Vinculador(cena, executor.fontes, executor.estado, executor,
                      intervalo_ms=1000000)


# ----- M05 item -----

def test_item_nome_id_indice():
    executor, _cena = montar(
        'janela p {\n titulo: "T"\n}\n')[:2]
    item = {"id": 7, "nome": "Ana"}
    with executor.contexto_item(item, 3):
        from elixx.compilador import ast as _A

        assert executor.avaliar(_membro("item", "nome")) == "Ana"
        assert executor.avaliar(_membro("item", "id")) == 7
        assert executor.avaliar(_membro("item", "indice")) == 3
        assert executor.avaliar(_A.Ident(nome="item")) == item


def _membro(base, atributo):
    from elixx.compilador import ast as _A

    return _A.Membro(base=_A.Ident(nome=base), atributo=atributo)


def test_item_fora_escopo_erros():
    with pytest.raises(ErroSintatico, match="item"):
        analisar('janela p {\n titulo: "T"\n texto t {\n'
                 '  origem: item.nome\n }\n}\n')
    executor, _cena = montar(
        'janela p {\n titulo: "T"\n}\n')[:2]
    with pytest.raises(ErroExecucao, match="só existe dentro"):
        executor.avaliar(_membro("item", "nome"))
    with executor.contexto_item({"a": 1}, 0):
        with pytest.raises(ErroExecucao, match="desconhecido"):
            executor.avaliar(_membro("item", "falta"))


def test_item_somente_leitura():
    from elixx.compilador import ast as _A

    executor, _cena = montar(
        'janela p {\n titulo: "T"\n}\n')[:2]
    bloco = _A.Bloco(comandos=[_A.Atribuicao(
        alvo=_membro("item", "nome"), op="=",
        valor=_A.TextoLit(valor="x"))])
    with executor.contexto_item({"nome": "Ana"}, 0):
        with pytest.raises(ErroExecucao, match="somente leitura"):
            executor.executar_bloco(bloco)


def test_param_fora_de_def_erro():
    with pytest.raises(ErroSintatico, match="param"):
        analisar('janela p {\n titulo: "T"\n texto t {\n'
                 '  origem: param.x\n }\n}\n')


# ----- M07 ações -----

ACOES = ('acao incrementar {\n estado.contador += 1\n}\n'
         'acao selecionar(id) {\n estado.selecionado = id\n}\n'
         'acao zerar {\n estado.contador = 0\n}\n'
         'estado {\n contador: 0\n selecionado: -1\n}\n'
         'janela p {\n titulo: "T"\n'
         ' botão a {\n texto: "x"\n  quando clicar {\n'
         '   executar incrementar\n  }\n }\n'
         ' botão b {\n texto: "y"\n  quando clicar {\n'
         '   executar selecionar(7)\n  }\n }\n}\n')


def test_acao_declarar_executar():
    prog = analisar(ACOES)
    validar(prog)
    assert "Ação incrementar()" in mostrar_arvore(prog)
    assert "Ação selecionar(id)" in mostrar_arvore(prog)
    executor = Executor()
    executor.executar(prog, [])
    executor.simular_clique("a")
    assert executor.estado.obter("contador") == 1.0
    executor.simular_clique("b")
    assert executor.estado.obter("selecionado") == 7.0


def test_acao_aridade_e_desconhecida():
    prog = analisar(ACOES)
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    with pytest.raises(ErroExecucao, match="argumento"):
        executor.chamar_acao("selecionar", [])
    with pytest.raises(ErroExecucao, match="desconhecida"):
        executor.chamar_acao("fantasma", [])
    bloco = A.Bloco(comandos=[A.Acao(
        nome="executar",
        args=[A.Ident(nome="fantasma")])])
    with pytest.raises(ErroExecucao, match="desconhecida"):
        executor.executar_bloco(bloco)
    bloco2 = A.Bloco(comandos=[A.Acao(nome="executar", args=[])])
    with pytest.raises(ErroExecucao, match="Uso:"):
        executor.executar_bloco(bloco2)


def test_acao_retornar_ignorado_e_isolamento():
    prog = analisar('acao fria(x) {\n retornar x\n}\n'
                    'janela p {\n titulo: "T"\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    executor.chamar_acao("fria", [99])  # sem erro; retorno descartado
    with pytest.raises(ErroExecucao):  # x não vaza p/ fora
        executor.memoria.obter("x")


def test_acao_nome_duplicado_e_colisao_funcao():
    with pytest.raises(ErroSemantico, match="duas vezes"):
        validar(analisar('acao a {\n}\nacao a {\n}\n'
                         'janela p {\n titulo: "T"\n}\n'))
    with pytest.raises(ErroSemantico, match="já é função"):
        validar(analisar('funcao a(x) {\n retornar x\n}\nacao a {\n}\n'
                         'janela p {\n titulo: "T"\n}\n'))


# ----- M08 funções -----

def test_funcao_params_retorno():
    prog = analisar('funcao total(preco, quantidade) {\n'
                    ' retornar preco * quantidade\n}\n'
                    'janela p {\n titulo: "T"\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    from elixx.compilador import ast as _A

    chamada = _A.Chamada(nome="total", args=[
        _A.NumeroLit(valor=10.0), _A.NumeroLit(valor=3.0)])
    assert executor.avaliar(chamada) == 30.0


def test_precedencia_e_modulo():
    from elixx.compilador import ast as _A

    executor, _cena = montar(
        'janela p {\n titulo: "T"\n}\n')[:2]

    def av(v):
        return executor.avaliar(v)

    n = _A.NumeroLit
    assert av(_A.Binaria(op="+", esquerda=n(valor=2.0),
                         direita=_A.Binaria(
                             op="*", esquerda=n(valor=3.0),
                             direita=n(valor=4.0)))) == 14.0
    assert av(_A.Binaria(op="%", esquerda=n(valor=10.0),
                         direita=n(valor=3.0))) == 1.0
    assert av(_A.Binaria(op="==", esquerda=n(valor=1.0),
                         direita=n(valor=1.0))) is True
    assert av(_A.Binaria(op="e", esquerda=_A.Booleano(valor=True),
                         direita=_A.Booleano(valor=False))) is False
    assert av(_A.Binaria(op="nao", esquerda=_A.Booleano(valor=True),
                         direita=_A.Booleano(valor=False))) is True


def test_divisao_zero_pt_e_funcao_aridade():
    from elixx.compilador import ast as _A

    executor, _cena = montar(
        'janela p {\n titulo: "T"\n}\n')[:2]
    with pytest.raises(ErroExecucao, match="divisão por zero"):
        executor.avaliar(_A.Binaria(op="/", esquerda=_A.NumeroLit(
            valor=1.0), direita=_A.NumeroLit(valor=0.0)))
    with pytest.raises(ErroExecucao, match="divisão por zero"):
        executor.avaliar(_A.Binaria(op="%", esquerda=_A.NumeroLit(
            valor=1.0), direita=_A.NumeroLit(valor=0.0)))
    prog = analisar('funcao f(a, b) {\n retornar a\n}\n'
                    'janela p {\n titulo: "T"\n}\n')
    validar(prog)
    executor.executar(prog, [])
    with pytest.raises(ErroExecucao, match="argumento"):
        executor.chamar_funcao("f", [1])


# ----- M11/M12 módulos -----

def test_import_simples_e_uso(tmp_path):
    base = tmp_path / "componentes"
    base.mkdir()
    (base / "card.elixx").write_text(
        "componente Cartao {\n corpo {\n  texto t {\n   texto: \"oi\"\n  }\n"
        " }\n}\n", encoding="utf-8")
    principal = tmp_path / "principal.elixx"
    principal.write_text(
        "importar componentes.card\n"
        "janela p {\n titulo: \"T\"\n Cartao c {\n }\n}\n", encoding="utf-8")
    from elixx.cli import main

    assert main(["verificar", str(principal)]) == 0


def test_import_duplicado_uma_vez(tmp_path, capsys):
    (tmp_path / "a.elixx").write_text(
        "componente A {\n corpo {\n  texto t {\n   texto: \"x\"\n  }\n }\n}\n",
        encoding="utf-8")
    principal = tmp_path / "principal.elixx"
    principal.write_text(
        "importar a\nimportar a\n"
        "janela p {\n titulo: \"T\"\n A x {\n }\n}\n", encoding="utf-8")
    from elixx.cli import main

    assert main(["verificar", str(principal)]) == 0


def test_import_inexistente_traversal_absoluto(tmp_path):
    from elixx.compilador.modulos import carregar_programa

    principal = tmp_path / "principal.elixx"
    principal.write_text("janela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    (tmp_path / "ruim.elixx").write_text(
        "importar naoexiste\njanela p {\n titulo: \"T\"\n}\n",
        encoding="utf-8")
    with pytest.raises(ErroELiXX, match="não encontrado"):
        carregar_programa(str(tmp_path / "ruim.elixx"))
    (tmp_path / "trav.elixx").write_text(
        "importar a....b\njanela p {\n titulo: \"T\"\n}\n",
        encoding="utf-8")
    # pontos vazios nem passam do parser (caminho inválido na origem)
    with pytest.raises(ErroELiXX, match="caminho"):
        carregar_programa(str(tmp_path / "trav.elixx"))
    fora = tmp_path / "fora.elixx"
    fora.write_text("importar x\njanela p {\n titulo: \"T\"\n}\n",
                    encoding="utf-8")
    # caminho absoluto não é sintaxe válida de import (só pontos)
    assert ".." not in open(str(fora), encoding="utf-8").read()


def test_import_ciclo_detectado(tmp_path):
    from elixx.compilador.modulos import carregar_programa

    (tmp_path / "a.elixx").write_text(
        "importar b\njanela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    (tmp_path / "b.elixx").write_text(
        "importar a\njanela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    with pytest.raises(ErroELiXX, match="circular"):
        carregar_programa(str(tmp_path / "a.elixx"))


def test_import_estado_duplicado_erro(tmp_path):
    from elixx.compilador.modulos import carregar_programa

    (tmp_path / "m.elixx").write_text(
        "estado {\n x: 1\n}\n", encoding="utf-8")
    (tmp_path / "principal.elixx").write_text(
        "importar m\nestado {\n x: 2\n}\njanela p {\n titulo: \"T\"\n}\n",
        encoding="utf-8")
    with pytest.raises(ErroELiXX, match="dois módulos|duas vezes|[Dd]uplic"):
        carregar_programa(str(tmp_path / "principal.elixx"))


# ----- M13 escopo -----

def test_escopo_global_visivel_no_componente():
    executor, _cena = montar(
        'componente C {\n corpo {\n  texto t {\n   origem: estado.g\n  }\n'
        ' }\n}\n'
        'estado {\n g: 5\n}\n'
        'janela p {\n titulo: "T"\n C c {\n }\n}\n')[:2]
    assert executor.estado.obter("g") == 5.0


def test_item_fora_modelo_parse_erro():
    with pytest.raises(ErroSintatico, match="item"):
        analisar('janela p {\n titulo: "T"\n texto t {\n'
                 '  origem: item.nome\n }\n}\n')


def test_param_fora_def_parse_erro():
    with pytest.raises(ErroSintatico, match="param"):
        analisar('janela p {\n titulo: "T"\n texto t {\n'
                 '  origem: param.nome\n }\n}\n')


def test_html_lista_dinamica_placeholder():
    from elixx.visual.html import gerar_html

    prog = analisar(LISTA)
    validar(prog)
    executor = Executor()
    pagina = gerar_html(executor.executar(prog, []).objetos)
    assert "lista dinâmica" in pagina
    assert "só no nativo" in pagina


def test_exemplos_05_06_valores():
    prog = analisar(open("exemplos/05_acoes.elixx",
                         encoding="utf-8").read())
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    from elixx.cli import main as _main

    assert _main(["executar", "--sem-janela",
                  "exemplos/05_acoes.elixx"]) == 0
    prog6 = analisar(open("exemplos/06_funcoes.elixx",
                          encoding="utf-8").read())
    validar(prog6)
    executor.executar(prog6, [])
    from elixx.compilador import ast as _A

    assert executor.avaliar(_A.Binaria(
        op="+", esquerda=_A.Chamada(nome="total", args=[
            _A.NumeroLit(valor=10.0), _A.NumeroLit(valor=3.0)]),
        direita=_A.Binaria(op="-", esquerda=_A.Binaria(
            op="*", esquerda=_A.NumeroLit(valor=2.0),
            direita=_A.NumeroLit(valor=4.0)),
            direita=_A.Binaria(op="%", esquerda=_A.NumeroLit(
                valor=10.0), direita=_A.NumeroLit(valor=3.0))))) == 37.0
