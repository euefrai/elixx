"""Testes da Fase 04 — layout (puro, sem Tk) + componentes novos."""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroSemantico
from elixx.visual.cena import (
    Cena,
    NoVisual,
    aplicar_layout,
    recalcular,
    resolver_relativos,
)


def no(tipo="texto", nome="n", x=0.0, y=0.0, largura=None, altura=None,
       filhos=None, posicao_explicita=False):
    n = NoVisual(tipo=tipo, nome=nome, x=x, y=y, largura=largura,
                 altura=altura)
    for f in filhos or []:
        n.adicionar(f)
    if posicao_explicita:
        n.ref_objeto = _obj_com_posicao()
    return n


class _Obj:
    def __init__(self):
        self.bruto = {"posicao": [1]}


def _obj_com_posicao():
    return _Obj()


def cont(tipo, **kwargs):
    return no(tipo=tipo, **kwargs)


def test_coluna_empilha_com_espacamento():
    c = cont("coluna", largura=400.0, filhos=[
        no(largura=100.0, altura=30.0),
        no(largura=100.0, altura=30.0),
    ])
    c.layout["espacamento"] = 10.0
    aplicar_layout(c)
    a, b = c.filhos
    assert (a.x, a.y) == (0.0, 0.0)
    assert (b.x, b.y) == (0.0, 40.0)


def test_coluna_margem_e_alinhamento():
    c = cont("coluna", largura=400.0, filhos=[
        no(largura=100.0, altura=30.0),
    ])
    c.layout.update({"margem": (10.0, 20.0),
                     "preenchimento": (5.0, 5.0)})
    c.ref_objeto = _Alinh("centro")
    aplicar_layout(c)
    a = c.filhos[0]
    assert (a.x, a.y) == (15.0 + (400.0 - 30.0 - 100.0) / 2.0, 25.0)


class _Alinh:
    """Objeto fake com bruto de alinhamento (sem parser)."""

    def __init__(self, valor):
        self.bruto = {"alinhamento": [A.TextoLit(valor=valor)]}


def test_linha_horizontal_e_base():
    c = cont("linha", filhos=[
        no(largura=50.0, altura=20.0),
        no(largura=50.0, altura=40.0),
    ])
    c.layout["espacamento"] = 5.0
    c.ref_objeto = _Alinh("base")
    aplicar_layout(c)
    a, b = c.filhos
    assert (a.x, b.x) == (0.0, 55.0)
    assert (a.y, b.y) == (20.0, 0.0)


def test_grade_duas_colunas():
    c = cont("grade", largura=400.0, filhos=[
        no(largura=100.0, altura=30.0),
        no(largura=100.0, altura=30.0),
        no(largura=100.0, altura=30.0),
    ])
    c.layout.update({"colunas": 2, "espacamento": 10.0})
    aplicar_layout(c)
    a, b, d = c.filhos
    assert (a.x, a.y) == (0.0, 0.0)
    assert (b.x, b.y) == (200.0, 0.0)
    assert (d.x, d.y) == (0.0, 40.0)


def test_pilha_sobrepoe():
    c = cont("pilha", filhos=[
        no(largura=10.0, altura=10.0),
        no(largura=20.0, altura=20.0),
    ])
    aplicar_layout(c)
    assert [(f.x, f.y) for f in c.filhos] == [(0.0, 0.0), (0.0, 0.0)]


def test_posicao_explicita_vence_layout():
    c = cont("coluna", largura=400.0, filhos=[
        no(largura=100.0, altura=30.0, x=300.0, y=300.0,
           posicao_explicita=True),
        no(largura=100.0, altura=30.0),
    ])
    aplicar_layout(c)
    a, b = c.filhos
    assert (a.x, a.y) == (300.0, 300.0)
    assert (b.x, b.y) == (0.0, 0.0)


def test_auto_tamanho_do_conteiner():
    c = cont("coluna", filhos=[no(largura=100.0, altura=30.0)])
    c.layout["espacamento"] = 10.0
    aplicar_layout(c)
    assert c.largura == 100.0
    assert c.altura == 30.0  # sem gap após o último filho


def test_resolver_relativos_no_resize():
    jan = NoVisual(tipo="janela", nome="j", largura=800.0, altura=600.0)
    filho = no(largura=100.0, altura=10.0)
    filho.medidas = {"x": (50.0, "%")}
    filho.x = 400.0
    jan.adicionar(filho)
    cena = Cena(janelas=[jan])
    jan.largura = 1000.0
    resolver_relativos(cena)
    assert filho.x == 500.0


def test_largura_altura_minimo_maximo_na_cena():
    prog = analisar('janela p {\n titulo: "T"\n texto t {\n texto: "x"\n'
                    ' largura: 500px\n altura: 40px\n minimo: 100px\n'
                    ' maximo: 300px\n }\n}\n')
    validar(prog)
    from elixx.runtime.nucleo import Executor
    from elixx.visual.cena import ConstrutorCena

    cena = ConstrutorCena().de_objetos(
        Executor().executar(prog, []).objetos)
    t = cena.buscar("t")
    # mínimo/máximo limitam ambos os eixos (tamanho do componente)
    assert (t.largura, t.altura) == (300.0, 100.0)


def test_parse_tipos_novos_e_opcoes():
    prog = analisar('janela p {\n titulo: "T"\n coluna c {\n'
                    ' espacamento: 12px\n alinhamento: "centro"\n'
                    ' entrada campo {\n texto: "oi"\n }\n'
                    ' checkbox opt {\n texto: "ok"\n }\n'
                    ' selecao turno {\n opcoes: "a" "b"\n }\n'
                    ' separador div {\n }\n'
                    ' indicador ind {\n texto: "ok"\n }\n'
                    ' linha fileira {\n }\n grade matriz {\n colunas: 3\n }\n'
                    ' pilha monte {\n }\n}\n}\n')
    validar(prog)
    todos_tipos = set()
    pilha = list(prog.janelas[0].componentes)
    while pilha:
        componente = pilha.pop()
        todos_tipos.add(componente.tipo)
        pilha.extend(componente.filhos)
    assert todos_tipos >= {"coluna", "linha", "grade", "pilha", "entrada",
                           "checkbox", "selecao", "separador", "indicador"}


def test_semantica_alinhamento_e_opcoes_invalidos():
    with pytest.raises(ErroSemantico, match="alinhamento"):
        validar(analisar('janela p {\n titulo: "T"\n coluna c {\n'
                         ' alinhamento: "diagonal"\n }\n}\n'))
    with pytest.raises(ErroSemantico):
        validar(analisar('janela p {\n titulo: "T"\n selecao s {\n'
                         ' opcoes: 123\n }\n}\n'))
