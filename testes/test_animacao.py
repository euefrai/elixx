"""Testes da Fase 03 — animação real: easings, motor (dt falso, sem Tk),
sintaxe do bloco animação, semântica e ações (generalidade: ≥2 casos)."""
import pytest

from elixx.animacao import MOVIMENTOS, criar_animacao
from elixx.animacao.easing import EASINGS
from elixx.animacao.motor import (
    ChaveAnimacao,
    DefinicaoAnimacao,
    MotorAnimacoes,
    definicao_de_ast,
)
from elixx.compilador import ast as A
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroExecucao, ErroSemantico, ErroSintatico
from elixx.runtime.acoes import Contexto, executar_acao
from elixx.runtime.memoria import Memoria
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import NoVisual


def no_fake(**kwargs):
    base = dict(tipo="texto", nome="n", x=0.0, y=0.0, largura=100.0,
                altura=50.0, escala=1.0, rotacao=0.0, opacidade=1.0,
                visivel=True)
    base.update(kwargs)
    return NoVisual(**base)


def definicao(nome="a", alvo="n", chaves=None, **kwargs):
    base = dict(nome=nome, alvo=alvo,
                chaves=chaves or [ChaveAnimacao("posicao", (0.0, 0.0),
                                               (100.0, 50.0))],
                duracao_ms=1000.0, atraso_ms=0.0, movimento="linear",
                repetir=None, depois=None, inicio="automatico",
                ao_terminar=None)
    base.update(kwargs)
    return DefinicaoAnimacao(**base)


def motor_com(defs, no=None):
    from elixx.visual.cena import Cena

    no = no or no_fake()
    cena = Cena(janelas=[])
    from elixx.visual.cena import NoVisual as NV

    jan = NV(tipo="janela", nome="jan")
    jan.adicionar(no)
    cena.janelas.append(jan)
    executor = Executor()
    motor = MotorAnimacoes(executor)
    motor.carregar(defs, cena)
    return motor, no, executor


# ----- easings -----

def test_todos_easings_contrato():
    assert set(MOVIMENTOS) == set(EASINGS)
    for nome, fn in EASINGS.items():
        assert fn(0.0) == pytest.approx(0.0), nome
        assert fn(1.0) == pytest.approx(1.0, abs=0.01), nome
        assert fn(0.5) == fn(0.5), f"{nome} determinístico"


def test_easings_valores_conhecidos():
    assert EASINGS["linear"](0.5) == 0.5
    assert EASINGS["suave"](0.25) == pytest.approx(0.15625)
    assert EASINGS["suave"](0.75) == pytest.approx(0.84375)
    assert EASINGS["acelerar"](0.5) == 0.25
    picos = [EASINGS["mola"](t / 20.0) for t in range(21)]
    assert max(picos) > 1.0  # mola ultrapassa o alvo e assenta
    assert EASINGS["quicar"](0.5) != EASINGS["linear"](0.5)


def test_criar_animacao_compativel():
    assert criar_animacao("j", {}, 500.0, "suave").movimento == "suave"
    with pytest.raises(ErroExecucao) as exc:
        criar_animacao("j", {}, 500.0, "suav")
    assert "suave" in str(exc.value)


# ----- motor: interpolação -----

def test_posicao_linear_metade():
    motor, no, _ex = motor_com([definicao()])
    motor.iniciar("a")
    motor.atualizar(250)
    assert (no.x, no.y) == (25.0, 12.5)
    motor.atualizar(250)
    assert (no.x, no.y) == (50.0, 25.0)


def test_snap_exato_no_fim():
    motor, no, _ex = motor_com([definicao(movimento="mola")])
    motor.iniciar("a")
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 50.0)
    assert motor.execucoes["a"].estado == "concluida"


def test_de_none_captura_atual():
    no = no_fake(x=10.0, y=20.0)
    motor, no, _ex = motor_com(
        [definicao(chaves=[ChaveAnimacao("posicao", None, (110.0, 70.0))])],
        no)
    motor.iniciar("a")
    motor.atualizar(500)
    assert (no.x, no.y) == (60.0, 45.0)


def test_opacidade_e_tamanho_e_escala():
    no = no_fake(opacidade=0.0, largura=100.0, altura=100.0, escala=1.0)
    defs = [definicao("op", chaves=[ChaveAnimacao("opacidade", 0.0, 1.0)],
                      movimento="linear"),
            definicao("tm", chaves=[ChaveAnimacao("tamanho", (100.0, 100.0),
                                                 (200.0, 50.0))]),
            definicao("es", chaves=[ChaveAnimacao("escala", 1.0, 2.0)])]
    motor, no, _ex = motor_com(defs, no)
    for nome in ("op", "tm", "es"):
        motor.iniciar(nome)
    motor.atualizar(500)
    assert no.opacidade == 0.5
    assert (no.largura, no.altura) == (150.0, 75.0)
    assert no.escala == 1.5


def test_atraso_segura_inicio():
    motor, no, _ex = motor_com([definicao(atraso_ms=200.0)])
    motor.iniciar("a")
    motor.atualizar(100)
    assert (no.x, no.y) == (0.0, 0.0)
    motor.atualizar(150)
    assert no.x > 0.0


def test_repetir_duas_vezes_callback_uma():
    motor, no, ex = motor_com(
        [definicao(repetir=2,
                   ao_terminar=A.Bloco(
                       comandos=[A.Acao(nome="mostrar",
                                        args=[A.TextoLit(valor="fim")])]))])
    motor.iniciar("a")
    motor.atualizar(1000)  # 1a rodada
    assert motor.execucoes["a"].estado == "rodando"
    assert ex.ctx.saida == []
    motor.atualizar(1000)  # 2a rodada → conclui + callback
    assert ex.ctx.saida == ["fim"]


def test_infinito_nao_conclui():
    motor, _no, _ex = motor_com([definicao(repetir="infinito")])
    motor.iniciar("a")
    for _ in range(5):
        motor.atualizar(1000)
    assert motor.execucoes["a"].estado == "rodando"


def test_depois_sequencia_ordem():
    motor, no, ex = motor_com([
        definicao("primeira",
                  ao_terminar=A.Bloco(comandos=[A.Acao(
                      nome="mostrar", args=[A.TextoLit(valor="1")])])),
        definicao("segunda", depois="primeira", inicio="manual",
                  ao_terminar=A.Bloco(comandos=[A.Acao(
                      nome="mostrar", args=[A.TextoLit(valor="2")])]))])
    motor.iniciar("primeira")
    motor.atualizar(500)
    assert ex.ctx.saida == []
    motor.atualizar(500)  # primeira conclui
    motor.atualizar(1000)  # segunda roda e conclui
    assert ex.ctx.saida == ["1", "2"]


def test_pausar_continuar_cancelar():
    motor, no, _ex = motor_com([definicao()])
    motor.iniciar("a")
    motor.atualizar(400)
    motor.pausar("a")
    motor.atualizar(500)
    assert no.x == 40.0  # congelou
    motor.continuar("a")
    motor.atualizar(100)
    assert no.x == 50.0
    motor.cancelar("a")
    motor.atualizar(500)
    assert no.x == 50.0  # parado onde estava


def test_aparecer_desaparecer_visibilidade():
    no = no_fake(visivel=False)
    motor, no, _ex = motor_com(
        [definicao("e1", movimento="aparecer", chaves=[])], no)
    motor.iniciar("e1")
    motor.atualizar(10)
    assert no.visivel is True
    motor2, no2, _ex2 = motor_com(
        [definicao("e2", movimento="desaparecer", chaves=[])],
        no_fake(visivel=True))
    motor2.iniciar("e2")
    motor2.atualizar(1000)
    assert no2.visivel is False


def test_alvo_inexistente_erro_em_portugues():
    from elixx.visual.cena import Cena, NoVisual as NV

    cena = Cena(janelas=[NV(tipo="janela", nome="jan")])
    motor = MotorAnimacoes()
    with pytest.raises(ErroExecucao) as exc:
        motor.carregar([definicao(alvo="fantasma")], cena)
    assert "não existe" in str(exc.value)


def test_iniciar_automaticas_respeita_manual():
    motor, _no, _ex = motor_com(
        [definicao("auto"), definicao("man", inicio="manual")])
    motor.iniciar_automaticas()
    assert motor.execucoes["auto"].estado in ("atraso", "rodando")
    assert motor.execucoes["man"].estado == "manual"
    motor.atualizar(5000)
    assert motor.execucoes["man"].estado == "manual"  # parada até iniciar()
    motor.iniciar("man")
    motor.atualizar(100)
    assert motor.execucoes["man"].estado == "rodando"


def test_acoes_animacao_via_contexto():
    motor, _no, _ex = motor_com([definicao()])
    ctx = Contexto([], Memoria())
    ctx.motor = motor
    executar_acao("iniciar", ["a"], ctx)
    motor.atualizar(500)
    assert motor.execucoes["a"].estado == "rodando"
    executar_acao("pausar", ["a"], ctx)
    executar_acao("continuar", ["a"], ctx)
    executar_acao("cancelar", ["a"], ctx)
    assert motor.execucoes["a"].estado == "cancelada"
    ctx2 = Contexto([], Memoria())  # sem motor: mensagem, sem erro
    assert executar_acao("iniciar", ["a"], ctx2) is None
    assert "sem motor" in ctx2.saida[-1]


# ----- sintaxe -----

EXEMPLO_ANIM = ('janela p {\n titulo: "T"\n cartao c {\n texto: "x"\n }\n'
                ' animação chegada {\n alvo: c\n'
                ' posição: 0px 90px → 0px 40px\n duração: 600ms\n'
                ' movimento: suave\n atraso: 100ms\n repetir: 2\n'
                ' início: automatico\n'
                ' quando terminar {\n mostrar("pronto")\n }\n }\n}\n')


def test_parse_bloco_animacao():
    prog = analisar(EXEMPLO_ANIM)
    anim = prog.janelas[0].animacoes[0]
    assert isinstance(anim, A.AnimacaoDef)
    assert (anim.nome, anim.alvo) == ("chegada", "c")
    assert anim.duracao_ms == 600.0
    assert anim.atraso_ms == 100.0
    assert anim.repetir == 2
    chave = anim.chaves[0]
    assert chave.propriedade == "posicao"
    assert chave.de == (("px", 0.0), ("px", 90.0))
    assert anim.ao_terminar is not None
    validar(prog)


def test_parse_seta_ascii_e_valor_unico():
    prog = analisar('janela p {\n titulo: "T"\n texto t {\n texto: "x"\n }\n'
                    ' animação a {\n alvo: t\n opacidade: 0 -> 1\n'
                    ' escala: 2\n }\n}\n')
    anim = prog.janelas[0].animacoes[0]
    assert anim.chaves[0].de == ("px", 0.0)
    assert anim.chaves[1].de is None
    validar(prog)


def test_semantica_alvo_inexistente_sugere():
    prog = analisar(EXEMPLO_ANIM.replace("alvo: c", "alvo: cc"))
    with pytest.raises(ErroSemantico) as exc:
        validar(prog)
    assert "não existe" in str(exc.value)


def test_semantica_movimento_e_depois_e_unidade():
    base = EXEMPLO_ANIM
    with pytest.raises(ErroSemantico,
                       match="movimento desconhecido"):
        validar(analisar(base.replace("movimento: suave",
                                      "movimento: voar")))
    prog = analisar(base + "")
    prog.janelas[0].animacoes[0].depois = "fantasma"
    with pytest.raises(ErroSemantico, match="inexistente"):
        validar(prog)
    with pytest.raises(ErroSemantico, match="pixels"):
        validar(analisar(base.replace("0px 90px → 0px 40px",
                                      "0% 0% → 100% 100%")))


def test_semantica_inicio_invalido_e_nome_duplicado():
    prog = analisar(EXEMPLO_ANIM.replace("início: automatico",
                                        "início: sempre"))
    with pytest.raises(ErroSemantico, match="automatico"):
        validar(prog)
    prog2 = analisar(EXEMPLO_ANIM)
    prog2.janelas[0].animacoes.append(prog2.janelas[0].animacoes[0])
    with pytest.raises(ErroSemantico, match="repetido"):
        validar(prog2)


def test_semantica_propriedade_desconhecida():
    with pytest.raises((ErroSintatico, ErroSemantico)):
        validar(analisar(
            EXEMPLO_ANIM.replace("posição: 0px 90px → 0px 40px",
                                 "cheiro: bom → ótimo")))


def test_arvore_mostra_animacao(capsys):
    from elixx.compilador.ast import mostrar_arvore

    arvore = mostrar_arvore(analisar(EXEMPLO_ANIM))
    assert "Animação chegada → c" in arvore


def test_definicao_de_ast_converte():
    anim = analisar(EXEMPLO_ANIM).janelas[0].animacoes[0]
    from elixx.animacao.motor import definicao_de_ast

    d = definicao_de_ast(anim)
    assert d.chaves[0].de == (0.0, 90.0)
    assert d.duracao_ms == 600.0
    motor, no, _ex = motor_com([d], no_fake(nome="c", x=0.0, y=0.0))
    motor.iniciar("chegada")
    motor.atualizar(300)
    assert (no.x, no.y) == (0.0, 65.0)  # 90 → 40, suave(0.5) = 0.5
