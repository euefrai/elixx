"""Testes da Fase 08 — temas, componentes, navegação, formulários,
abas, modal, menu, tabela, seleção, foco. Determinísticos (sem Tk)."""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.ast import mostrar_arvore
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroSemantico, ErroSintatico
from elixx.runtime.acoes import Contexto, executar_acao
from elixx.runtime.estado import Estado
from elixx.runtime.memoria import Memoria
from elixx.runtime.nucleo import Executor
from elixx.runtime.temas import medida_do_tema, resolver_temas
from elixx.runtime.validacao import validar_campo, validar_formulario
from elixx.visual.cena import ConstrutorCena, aplicar_tema


def analisar_expandir(fonte):
    from elixx.compilador.parser import Parser
    from elixx.compilador.lexer import tokenizar

    prog = Parser(tokenizar(fonte)).parse()
    expandir_componentes(prog)
    return prog


def programa_tema():
    return ('tema escuro {\n cores {\n fundo: "#14161f"\n texto: "#ffffff"\n }\n'
            ' tamanhos {\n normal: 14px\n }\n espacos {\n gap: 8px\n }\n}\n'
            'tema claro {\n cores {\n fundo: "#ffffff"\n }\n'
            ' tamanhos {\n normal: 14px\n }\n espacos {\n gap: 8px\n }\n}\n')


# ----- temas -----

def test_parse_tema_e_resolver():
    prog = analisar(programa_tema() + 'janela p {\n titulo: "T"\n}\n')
    validar(prog)
    assert len(prog.temas) == 2
    temas = resolver_temas(prog.temas)
    assert temas["escuro"]["cores"]["fundo"] == "#14161f"
    assert temas["escuro"]["tamanhos"]["normal"] == 14.0
    assert medida_do_tema(temas, "escuro", "gap") == 8.0
    assert medida_do_tema(temas, "escuro", "falta") is None
    assert "Tema escuro" in mostrar_arvore(prog)


def test_tema_duplicado_e_secao_invalida():
    with pytest.raises(ErroSemantico, match="duas vezes"):
        validar(analisar(programa_tema() + programa_tema()
                         + 'janela p {\n titulo: "T"\n}\n'))
    with pytest.raises(ErroSemantico, match="Medida|medida"):
        validar(analisar('tema t {\n cores {\n fundo: "#fff"\n }\n'
                         ' tamanhos {\n normal: "grande"\n }\n}\n'
                         'janela p {\n titulo: "T"\n}\n'))


def test_ref_tema_na_cena_e_troca():
    prog = analisar(programa_tema() +
                    'janela p {\n titulo: "T"\n tema: "escuro"\n'
                    ' texto t {\n cor: tema.texto\n fonte: tema.normal\n }\n'
                    ' botão b {\n texto: "x"\n fundo: tema.fundo\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(executor.ctx.objetos,
                                       executor.temas, executor.tema_atual)
    assert executor.tema_atual == "escuro"
    texto = cena.buscar("t")
    assert texto.cor_hex == "#ffffff"
    assert texto.fonte_px == 14.0
    assert texto.tema_refs == {"cor": "texto", "fonte": "normal"}
    assert cena.buscar("b").fundo_hex == "#14161f"
    aplicar_tema(cena, executor.temas, "claro")
    assert cena.buscar("b").fundo_hex == "#ffffff"
    assert texto.tema_usado == "claro"


def test_ref_tema_inexistente_erro():
    with pytest.raises(ErroSemantico, match="nenhum tema"):
        validar(analisar(programa_tema() +
                         'janela p {\n titulo: "T"\n texto t {\n'
                         ' cor: tema.fantasma\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="não definido"):
        validar(analisar('janela p {\n titulo: "T"\n tema: "noite"\n}\n'))


def test_usar_tema_acao():
    prog = analisar(programa_tema() + 'janela p {\n titulo: "T"\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    ctx = Contexto([], Memoria())
    ctx.executor = executor
    executar_acao("usar_tema", ["claro"], ctx)
    assert executor.tema_atual == "claro"
    assert "(tema claro)" in ctx.saida
    executar_acao("usar_tema", ["noite"], ctx)
    assert "não existe" in ctx.saida[-1]


# ----- componentes reutilizáveis -----

CARTAO = ('componente Cartao {\n propriedade titulo\n'
          ' propriedade detalhe: "sem detalhe"\n corpo {\n'
          '  texto rot {\n   conteúdo: param.titulo\n  }\n'
          '  texto det {\n   conteúdo: param.detalhe\n  }\n }\n}\n')


def test_definir_usar_e_isolar():
    prog = analisar_expandir(CARTAO + 'janela p {\n titulo: "T"\n'
                             ' Cartao a {\n  titulo: "Oi"\n }\n'
                             ' Cartao b {\n  titulo: "Tchau"\n }\n}\n')
    validar(prog)
    jan = prog.janelas[0]
    # corpo com 2 raízes × 2 instâncias = 4, nomes isolados
    assert [c.nome for c in jan.componentes] == [
        "a__rot", "a__det", "b__rot", "b__det"]
    textos = [p.valores[0].valor
              for c in jan.componentes for p in c.propriedades
              if p.nome in ("texto", "conteudo", "conteúdo")]
    assert textos == ["Oi", "sem detalhe", "Tchau", "sem detalhe"]
    assert "Componente Cartao(titulo, detalhe)" in mostrar_arvore(prog)


def test_slot_conteudo():
    prog = analisar_expandir(
        'componente Caixa {\n corpo {\n  painel base {\n   conteudo\n  }\n }\n}\n'
        'janela p {\n titulo: "T"\n Caixa c {\n  texto dentro {\n'
        '   texto: "x"\n  }\n }\n}\n')
    validar(prog)
    base = prog.janelas[0].componentes[0]
    assert base.nome == "c__base"
    # filhos do slot são públicos (nome do usuário, sem prefixo)
    assert [f.nome for f in base.filhos] == ["dentro"]


def test_componente_erros_pt():
    with pytest.raises(ErroSemantico, match="não definido"):
        expandir_componentes(analisar(
            'janela p {\n titulo: "T"\n Fantasma f {\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="recursivo"):
        expandir_componentes(analisar(
            'componente A {\n corpo {\n  B x {\n  }\n }\n}\n'
            'componente B {\n corpo {\n  A y {\n  }\n }\n}\n'
            'janela p {\n titulo: "T"\n A a {\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="Falta a propriedade"):
        expandir_componentes(analisar(
            CARTAO + 'janela p {\n titulo: "T"\n Cartao c {\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="não tem propriedade"):
        expandir_componentes(analisar(
            CARTAO + 'janela p {\n titulo: "T"\n Cartao c {\n'
            '  titulo: "x"\n  extra: 1\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="duas vezes"):
        validar(analisar(CARTAO + CARTAO
                         + 'janela p {\n titulo: "T"\n}\n'))


def test_evento_instancia_vai_para_raiz():
    prog = analisar_expandir(
        CARTAO + 'janela p {\n titulo: "T"\n Cartao c {\n  titulo: "x"\n'
        '  quando clicar {\n   mostrar("clicou")\n  }\n }\n}\n')
    validar(prog)
    raiz = prog.janelas[0].componentes[0]
    assert raiz.eventos[0].nome == "clicar"


# ----- telas e navegação -----

TELAS = ('tela inicio {\n titulo: "I"\n tamanho: 100px 100px\n'
         ' botão a {\n texto: "x"\n  quando clicar {\n   ir("perfil")\n  }\n }\n}\n'
         'tela perfil {\n titulo: "P"\n tamanho: 100px 100px\n'
         ' inicial: verdadeiro\n'
         ' botão b {\n texto: "y"\n  quando clicar {\n   voltar()\n  }\n }\n}\n')


def test_telas_parse_navegacao():
    prog = analisar(TELAS)
    validar(prog)
    assert [t.nome for t in prog.telas] == ["inicio", "perfil"]
    assert "Tela perfil" in mostrar_arvore(prog)
    executor = Executor()
    executor.executar(prog, [])
    nav = executor.navegador
    assert nav.atual == "perfil"  # inicial vence a primeira
    assert executor.ctx.objetos[0].visivel is False
    assert executor.ctx.objetos[1].visivel is True
    executor.simular_clique("b")  # voltar() na primeira: erro amigável
    assert "primeira tela" in executor.ctx.saida[-1]
    nav.ir("inicio")
    assert nav.pilha == ["perfil", "inicio"]
    assert nav.atual == "inicio"
    nav.voltar()
    assert nav.atual == "perfil" and nav.pilha == ["perfil"]
    nav.inicio()
    assert nav.atual == "perfil"
    with pytest.raises(Exception, match="desconhecida"):
        nav.ir("fantasma")


def test_tela_sem_janela_valida():
    prog = analisar('tela unica {\n titulo: "U"\n}\n')
    validar(prog)


def test_acoes_ir_voltar_inicio():
    prog = analisar(TELAS)
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    ctx = Contexto(executor.ctx.objetos, Memoria())
    ctx.executor = executor
    executar_acao("ir", ["inicio"], ctx)
    assert executor.navegador.atual == "inicio"
    executar_acao("voltar", [], ctx)
    assert executor.navegador.atual == "perfil"
    executar_acao("inicio", [], ctx)
    assert "(tela perfil)" in ctx.saida
    executar_acao("ir", [], ctx)
    assert "Uso:" in ctx.saida[-1]


# ----- ciclo de vida -----

def test_eventos_criar_mostrar_esconder():
    prog = analisar('janela p {\n titulo: "T"\n texto t {\n texto: "x"\n'
                    '  quando criar {\n   mostrar("criado")\n  }\n'
                    '  quando mostrar {\n   mostrar("mostrado")\n  }\n'
                    '  quando esconder {\n   mostrar("escondido")\n  }\n'
                    '  quando mudanca {\n   mostrar("mudou")\n  }\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert "criado" in executor.ctx.saida
    alvo = executor.ctx.objetos[0].buscar("t")
    executor.disparar(alvo, "mostrar")
    executor.disparar(alvo, "esconder")
    assert "mostrado" in executor.ctx.saida
    assert "escondido" in executor.ctx.saida


# ----- formulários e validação -----

def test_validar_campo_regras():
    from elixx.runtime.validacao import validar_campo

    assert validar_campo("", {"obrigatorio": True}) == (
        False, "preenchimento obrigatório")
    assert validar_campo("a@b.c", {"validar": "email"})[0] is True
    assert validar_campo("ruim", {"validar": "email"})[1] == "email inválido"
    assert validar_campo("x", {"validar": "numero"})[1] == "precisa ser número"
    assert validar_campo("ab", {"min_caracteres": 3})[1].startswith("mínimo")
    assert validar_campo("toolong", {"max_caracteres": 3})[1].startswith(
        "máximo")
    assert validar_campo(5, {"min_valor": 10})[1] == "mínimo 10"
    assert validar_campo("", {}) == (True, "")
    ok, erros = validar_formulario({"a": ("", {"obrigatorio": True}),
                                    "b": ("ok", {})})
    assert ok is False and erros == ["a: preenchimento obrigatório"]


def test_formulario_valida_via_estado():
    prog = analisar('estado {\n nome: ""\n email: ""\n}\n'
                    'janela p {\n titulo: "T"\n formulario f {\n'
                    '  entrada campo_nome {\n   ligado_a: estado.nome\n'
                    '   obrigatorio: verdadeiro\n  }\n'
                    '  entrada campo_email {\n   ligado_a: estado.email\n'
                    '   validar: "email"\n  }\n }\n'
                    ' botão ok {\n texto: "x"\n  quando clicar {\n'
                    '   validar("f")\n  }\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert executor.validar_formulario("f") is False
    assert executor.estado.obter("f_valido") is False
    assert len(executor.estado.obter("f_erros")) == 1
    executor.estado.definir("nome", "Ana")
    executor.estado.definir("email", "a@b.c")
    assert executor.validar_formulario("f") is True
    with pytest.raises(Exception, match="desconhecido"):
        executor.validar_formulario("fantasma")


def test_enviar_formulario_post():
    import time

    import servidor_teste
    from elixx.dados import FonteRemota

    with servidor_teste.ServidorTeste() as srv:
        prog = analisar('estado {\n nome: "Cid"\n}\n'
                        'dados novo {\n url: "URL"\n metodo: "POST"\n}\n'
                        'janela p {\n titulo: "T"\n formulario f {\n'
                        '  entrada n {\n   ligado_a: estado.nome\n'
                        '   obrigatorio: verdadeiro\n  }\n }\n'
                        ' botão ok {\n texto: "x"\n  quando clicar {\n'
                        '   enviar("f", "novo")\n  }\n }\n}\n'.replace(
                            "URL", srv.url("/usuarios")))
        validar(prog)
        executor = Executor(fontes={})
        executor.executar(prog, [], base_dir=".")
        ctx = Contexto(executor.ctx.objetos, Memoria())
        ctx.executor = executor
        executar_acao("enviar", ["f", "novo"], ctx)
        prazo = time.monotonic() + 5
        while executor.estado.obter("f_resposta") is None \
                and time.monotonic() < prazo:
            time.sleep(0.05)
        resposta = executor.estado.obter("f_resposta")
        assert resposta["status"] == 201
        assert resposta["valor"]["nome"] == "Cid"


# ----- abas, menu, tabela, modal, foco -----

def test_abas_menu_tabela_modal_parse():
    prog = analisar('janela p {\n titulo: "T"\n'
                    ' abas ab {\n  aba um {\n   texto: "A"\n  }\n'
                    '  aba dois {\n   texto: "B"\n  }\n }\n'
                    ' menu mn {\n  botão b {\n   texto: "x"\n  }\n }\n'
                    ' tabela tb {\n  colunas: "a" "b"\n'
                    '   origem: estado.linhas\n }\n'
                    ' modal md {\n  texto: "oi"\n }\n}\n'
                    'estado {\n linhas: 0\n}\n')
    validar(prog)
    tipos = {c.tipo for c in prog.janelas[0].componentes}
    assert tipos == {"abas", "menu", "tabela", "modal"}
    assert "Aba" not in tipos  # aba é filha, não raiz
    assert "Abas ab" in mostrar_arvore(prog)


def test_abrir_fechar_modal_e_tela():
    prog = analisar('janela p {\n titulo: "T"\n'
                    ' modal md {\n  texto: "oi"\n }\n'
                    ' botão a {\n texto: "x"\n  quando clicar {\n'
                    '   abrir("md")\n  }\n }\n'
                    ' botão f {\n texto: "y"\n  quando clicar {\n'
                    '   fechar("md")\n  }\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    modal = executor.ctx.objetos[0].buscar("md")
    assert modal.visivel is False  # nasce escondido
    executor.simular_clique("a")
    assert modal.visivel is True
    assert "(modal md aberto)" in executor.ctx.saida
    executor.simular_clique("f")
    assert modal.visivel is False


def test_focar_e_descricao():
    prog = analisar('janela p {\n titulo: "T"\n'
                    ' botão s {\n texto: "Salvar"\n'
                    '  descricao: "Salvar alterações"\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    ctx = Contexto(executor.ctx.objetos, Memoria())
    ctx.executor = executor
    executar_acao("focar", ["s"], ctx)  # sem janela: registra
    assert "(foco em s)" in ctx.saida


def test_tabela_colunas_nomes_e_reatividade():
    prog = analisar('estado {\n linhas: 0\n}\n'
                    'janela p {\n titulo: "T"\n tabela tb {\n'
                    '  colunas: "nome" "email"\n'
                    '  origem: estado.linhas\n }\n}\n')
    validar(prog)
    executor = Executor()
    cena = ConstrutorCena().de_objetos(
        executor.executar(prog, []).objetos)
    no = cena.buscar("tb")
    assert no.colunas_nomes == ["nome", "email"]


# ----- lista de literais e acessibilidade -----

def test_lista_literal_basico():
    prog = analisar('estado {\n nums: [1, 2]\n}\n'
                    'janela p {\n titulo: "T"\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert executor.estado.obter("nums") == [1.0, 2.0]


def test_html_fase08():
    from elixx.visual.html import gerar_html

    prog = analisar(programa_tema() +
                    'janela p {\n titulo: "T"\n tema: "escuro"\n'
                    ' tabela tb {\n  colunas: "a" "b"\n }\n'
                    ' abas ab {\n  aba um {\n   texto: "A"\n  }\n }\n'
                    ' modal md {\n  texto: "oi"\n }\n'
                    ' menu mn {\n  botão b {\n   texto: "x"\n  }\n }\n'
                    ' formulario ff {\n  entrada campo {\n   texto: "y"\n  }\n }\n'
                    ' botão s {\n texto: "Salvar"\n'
                    '  descricao: "Salvar alterações"\n }\n}\n')
    validar(prog)
    executor = Executor()
    pagina = gerar_html(executor.executar(prog, []).objetos,
                        temas=executor.temas,
                        tema_atual=executor.tema_atual)
    assert "--elx-fundo: #14161f" in pagina
    assert "<table" in pagina and "<th>a</th>" in pagina
    assert "<details>" in pagina
    assert "elx-modal" in pagina and "<form" in pagina
    assert "<nav" in pagina and 'aria-label="Salvar alterações"' in pagina


def test_lista_selecao_two_way_stubs():
    from elixx.visual.cena import NoVisual
    from elixx.visual.tk import RenderizadorTk

    estado = Estado({"sel": 0})
    renderer = RenderizadorTk.__new__(RenderizadorTk)
    renderer.executor = type("E", (), {"estado": estado})()
    renderer._paineis = {}
    renderer._itens = {}
    renderer._barras = []
    renderer.ultima_mensagem = ""

    class CaixaStub:
        def __init__(self):
            self.sel = set()

        def curselection(self):
            return tuple(sorted(self.sel))

        def selection_clear(self, ini, fim):
            self.sel.clear()

        def selection_set(self, indice):
            self.sel = {indice}

        def see(self, indice):
            pass

    no = NoVisual(tipo="lista", nome="l", ligado_a="sel")
    caixa = CaixaStub()
    renderer._paineis[id(no)] = {"kind": "lista", "caixa": caixa,
                                 "atual": []}
    renderer._itens[id(no)] = (caixa, {})
    renderer.definir_valor(no, 2)
    assert caixa.sel == {2}
    renderer.definir_valor(no, 2)  # igual: sem reescrita
    caixa.sel = {1}  # usuário selecionou outra
    renderer._selecionar_lista(no)
    assert estado.obter("sel") == 1


def test_abas_definir_e_estado():
    from elixx.visual.cena import NoVisual
    from elixx.visual.tk import RenderizadorTk

    renderer = RenderizadorTk.__new__(RenderizadorTk)
    renderer._tk = None
    renderer._paineis = {}
    renderer._itens = {}
    renderer._barras = []
    renderer.ultima_mensagem = ""
    renderer.executor = type("E", (), {"estado": Estado({"aba": 0})})()
    no = NoVisual(tipo="abas", nome="ab", ligado_a="aba")
    refs = {"kind": "abas", "botoes": [], "paineis": {}, "abas": [],
            "ativa": 0}
    renderer._paineis[id(no)] = refs
    renderer.definir_valor(no, 2)  # sem abas filhas: só registra
    assert refs["ativa"] == 0  # sem filhas, trava em 0
    assert renderer.executor.estado.obter("aba") == 0


def test_refrescar_tema_sem_janela():
    from elixx.visual.tk import RenderizadorTk

    renderer = RenderizadorTk.__new__(RenderizadorTk)
    renderer.cena = None
    renderer._itens = {}
    renderer._paineis = {}
    renderer._barras = []
    renderer.ultima_mensagem = ""
    renderer.refrescar_tema()  # sem cena: sem erro
    assert renderer.focar_em("qualquer") is False
