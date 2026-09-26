"""Testes da Fase 11 — Motion Core 2.0 (determinísticos, dt falso)."""
import math

import pytest

from elixx.animacao import MOVIMENTOS
from elixx.animacao.easing import EASINGS
from elixx.animacao.motion import (
    Keyframe,
    Motion,
    MotionGroup,
    Spring,
    avaliar_keyframes,
    curva,
    curva_parametrica,
    interpolar_angulo,
    interpolar_transform,
    interpolar_vetor,
    mover_por_ponto,
    progresso_tempo,
    vetor_para,
)
from elixx.animacao.motor import (
    ChaveAnimacao,
    DefinicaoAnimacao,
    MotorAnimacoes,
    definicao_de_ast,
)
from elixx.compilador import ast as A
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroExecucao, ErroSemantico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import Cena, ConstrutorCena, NoVisual
from elixx.visual.transform import Transform, Vector2


def analisar_expandir(fonte):
    prog = Parser(tokenizar(fonte)).parse()
    expandir_componentes(prog)
    return prog


def montar(fonte):
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    return executor, cena, prog


def no_fake(**kwargs):
    base = dict(tipo="texto", nome="n", x=0.0, y=0.0, largura=100.0,
                altura=50.0, escala=1.0, escala_x=1.0, escala_y=1.0,
                rotacao=0.0, opacidade=1.0, visivel=True)
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
    no = no or no_fake()
    cena = Cena(janelas=[])
    jan = NoVisual(tipo="janela", nome="jan")
    jan.adicionar(no)
    cena.janelas.append(jan)
    executor = Executor()
    motor = MotorAnimacoes(executor)
    motor.carregar(defs, cena)
    return motor, no, executor, cena


# ----- 1-4: Motion básico, progresso, duração, delay -----

def test_motion_basico():
    motor, no, _ex, _cena = motor_com([definicao()])
    motor.iniciar("a")
    motor.atualizar(500)
    assert (no.x, no.y) == (50.0, 25.0)
    motor.atualizar(500)
    assert (no.x, no.y) == (100.0, 50.0)
    assert motor.execucoes["a"].estado == "concluida"


def test_progresso_separado_da_curva():
    motor, no, _ex, _cena = motor_com([definicao(movimento="suave")])
    ex = motor.execucoes["a"]
    motor.iniciar("a")
    assert ex.progresso == 0.0
    motor.atualizar(500)
    assert ex.progresso == pytest.approx(0.5)
    # curva suave(0.5)=0.5 aqui; o ponto é: progresso é tempo puro.
    motor.atualizar(500)
    assert ex.progresso == 1.0


def test_duracao_respeitada():
    motor, no, _ex, _cena = motor_com([definicao(duracao_ms=2000.0)])
    motor.iniciar("a")
    motor.atualizar(1000)
    assert (no.x, no.y) == (50.0, 25.0)
    assert motor.execucoes["a"].estado == "rodando"


def test_delay_progresso_zero():
    motor, no, _ex, _cena = motor_com([definicao(atraso_ms=500.0)])
    motor.iniciar("a")
    motor.atualizar(400)
    assert (no.x, no.y) == (0.0, 0.0)
    assert motor.execucoes["a"].progresso == 0.0
    motor.atualizar(200)
    assert no.x > 0.0


# ----- 5-6: linear, easing -----

def test_linear_exato():
    assert EASINGS["linear"](0.3) == pytest.approx(0.3)


def test_easings_obrigatorios_presentes():
    for nome in ("linear", "suave", "rapido", "lento", "entrada", "saida",
                 "entrada_saida", "mola", "elastico", "quicar", "deslizar",
                 "expandir", "encolher", "sacudir", "aparecer",
                 "desaparecer"):
        assert nome in EASINGS, nome
        assert nome in MOVIMENTOS, nome
    assert EASINGS["entrada"](0.3) == EASINGS["desacelerar"](0.3)
    assert EASINGS["saida"](0.3) == EASINGS["acelerar"](0.3)
    assert EASINGS["entrada_saida"](0.3) == EASINGS["suave"](0.3)


def test_curva_parametrica_mola():
    f = curva_parametrica("mola", rigidez=180, amortecimento=12)
    assert f(0.0) == pytest.approx(0.0, abs=0.05)
    assert f(1.0) == pytest.approx(1.0, abs=0.05)
    assert f(0.5) == f(0.5)
    with pytest.raises(ErroELiXX):
        curva_parametrica("mola", rigidez=-1)
    with pytest.raises(ErroELiXX):
        curva_parametrica("foguete")
    with pytest.raises(ErroELiXX):
        curva("voar")


# ----- 7-10: posição, rotação, escala, opacidade -----

def test_motion_posicao():
    motor, no, _ex, _cena = motor_com([definicao(movimento="linear")])
    motor.iniciar("a")
    motor.atualizar(250)
    assert (no.x, no.y) == (25.0, 12.5)


def test_motion_rotacao():
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("rotacao", 0.0, 90.0)],
                   movimento="linear")])
    motor.iniciar("a")
    motor.atualizar(500)
    assert no.rotacao == pytest.approx(45.0)
    motor.atualizar(500)
    assert no.rotacao == pytest.approx(90.0)


def test_motion_escala_uniforme_preserva_eixos():
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("escala", 1.0, 2.0)],
                   movimento="linear")])
    motor.iniciar("a")
    motor.atualizar(500)
    assert (no.escala_x, no.escala_y, no.escala) == (1.5, 1.5, 1.5)


def test_motion_opacidade_clamp():
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("opacidade", 0.0, 1.0)],
                   movimento="linear")])
    motor.iniciar("a")
    motor.atualizar(500)
    assert no.opacidade == pytest.approx(0.5)


# ----- 11-12: vetor, Transform -----

def test_interpolar_vetor():
    r = interpolar_vetor(Vector2(100, 100), Vector2(300, 200), 0.5)
    assert r.tupla() == (200.0, 150.0)


def test_interpolar_transform():
    a = Transform(x=0, y=0, rotacao=0, escala_x=1, escala_y=1, opacidade=0)
    b = Transform(x=100, y=50, rotacao=90, escala_x=2, escala_y=2,
                  opacidade=1)
    r = interpolar_transform(a, b, 0.5)
    assert (r.x, r.y) == (50.0, 25.0)
    assert r.rotacao == pytest.approx(45.0)
    assert r.escala == (1.5, 1.5)
    assert r.opacidade == pytest.approx(0.5)


# ----- 13-14: rotação menor caminho, 350→10 -----

def test_rotacao_menor_caminho():
    assert interpolar_angulo(350, 10, 0.5) == pytest.approx(360.0)
    assert interpolar_angulo(10, 350, 0.5) == pytest.approx(0.0)
    assert interpolar_angulo(0, 90, 1.0) == pytest.approx(90.0)
    # voltas completas no sentido do movimento
    assert interpolar_angulo(0, 90, 1.0, voltas=1) == pytest.approx(450.0)


def test_motor_350_para_10_vai_por_360():
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("rotacao", 350.0, 10.0)],
                   movimento="linear")],
        no_fake(rotacao=350.0))
    motor.iniciar("a")
    motor.atualizar(500)
    assert no.rotacao == pytest.approx(360.0)
    motor.atualizar(500)
    assert no.rotacao == pytest.approx(10.0)  # snap exato


# ----- 15-16: keyframes -----

KEYS = ('janela p {\n titulo: "T"\n texto h {\n  texto: "x"\n }\n'
        ' animação passeio {\n  alvo: h\n  duração: 2s\n'
        '  movimento: linear\n'
        '  0% {\n   posição: 100px 100px\n  }\n'
        '  50% {\n   posição: 300px 200px\n  }\n'
        '  100% {\n   posição: 500px 100px\n  }\n }\n}\n')


def test_keyframes_parse_e_semantica():
    prog = analisar_expandir(KEYS)
    anim = prog.janelas[0].animacoes[0]
    assert [k.percent for k in anim.keyframes] == [0.0, 50.0, 100.0]
    validar(prog)


def test_keyframes_interpolacao():
    _ex, cena, prog = montar(KEYS)
    no = cena.buscar("h")
    motor = MotorAnimacoes(_ex)
    motor.carregar([definicao_de_ast(a) for a in prog.janelas[0].animacoes],
                   cena)
    motor.iniciar_automaticas()
    motor.atualizar(500)  # t=0.25 → meio do 1º segmento
    assert (no.x, no.y) == pytest.approx((200.0, 150.0))
    motor.atualizar(500)  # t=0.5 → quadro 50%
    assert (no.x, no.y) == pytest.approx((300.0, 200.0))
    motor.atualizar(1000)  # fim → snap exato
    assert (no.x, no.y) == (500.0, 100.0)


def test_keyframes_multiplos_props_e_snap():
    frames = [Keyframe(0.0, {"posicao": (0.0, 0.0), "opacidade": 0.0}),
              Keyframe(1.0, {"posicao": (100.0, 0.0), "opacidade": 1.0})]
    assert avaliar_keyframes(frames, "posicao", 0.5,
                             lambda u: u) == (50.0, 0.0)
    assert avaliar_keyframes(frames, "opacidade", 1.0) == 1.0
    assert avaliar_keyframes(frames, "opacidade", 0.0) == 0.0


def test_keyframes_erros_claros():
    base = ('janela p {\n titulo: "T"\n texto h {\n  texto: "x"\n }\n'
            ' animação k {\n  alvo: h\n  duração: 1s\n%s }\n}\n')
    with pytest.raises(ErroSemantico):  # 1 quadro só
        validar(analisar_expandir(base % '  0% {\n   posição: 0px 0px\n  }\n'))
    with pytest.raises(ErroELiXX):  # quadro repetido
        validar(analisar_expandir(
            base % ('  0% {\n   posição: 0px 0px\n  }\n'
                    '  0% {\n   posição: 1px 1px\n  }\n')))
    with pytest.raises(ErroSemantico):  # mesma prop em chaves e quadros
        validar(analisar_expandir(
            base % ('  posição: 0px 0px -> 10px 10px\n'
                    '  0% {\n   posição: 0px 0px\n  }\n'
                    '  100% {\n   posição: 10px 10px\n  }\n')))
    with pytest.raises(ErroSemantico):  # seta dentro do quadro
        validar(analisar_expandir(
            base % ('  0% {\n   posição: 0px 0px -> 5px 5px\n  }\n'
                    '  100% {\n   posição: 10px 10px\n  }\n')))


# ----- 17-19: sequência, paralelo, repetição -----

def test_sequencia_depois():
    motor, no, ex, _cena = motor_com([
        definicao("um", chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                              (100.0, 0.0))]),
        definicao("dois", chaves=[ChaveAnimacao("posicao", (100.0, 0.0),
                                                (100.0, 100.0))],
                  depois="um", inicio="manual")])
    motor.iniciar("um")
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 0.0)
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 100.0)
    assert motor.execucoes["dois"].estado == "concluida"


def test_paralelo_coexiste():
    motor, no, _ex, _cena = motor_com([
        definicao("pos", chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                               (100.0, 0.0))]),
        definicao("gir", chaves=[ChaveAnimacao("rotacao", 0.0, 90.0)])])
    motor.iniciar("pos")
    motor.iniciar("gir")
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 0.0)
    assert no.rotacao == pytest.approx(90.0)


def test_repeticao_n_e_infinita():
    motor, no, _ex, _cena = motor_com([definicao(repetir=3)])
    motor.iniciar("a")
    for _ in range(3):
        motor.atualizar(1000)
    assert motor.execucoes["a"].estado == "concluida"
    assert (no.x, no.y) == (100.0, 50.0)
    motor2, _n2, _e2, _c2 = motor_com([definicao(repetir="infinito")])
    motor2.iniciar("a")
    for _ in range(5):
        motor2.atualizar(1000)
    assert motor2.execucoes["a"].estado == "rodando"


# ----- 21: ping-pong -----

def test_ping_pong_ida_e_volta():
    motor, no, _ex, _cena = motor_com(
        [definicao(modo="ping_pong", repetir=2, movimento="linear")])
    motor.iniciar("a")
    motor.atualizar(1000)  # ida
    assert (no.x, no.y) == (100.0, 50.0)
    assert motor.execucoes["a"].estado == "rodando"
    motor.atualizar(1000)  # volta → snap no início
    assert (no.x, no.y) == (0.0, 0.0)
    assert motor.execucoes["a"].estado == "concluida"


def test_ping_pong_tres_pernas_termina_longe():
    motor, no, _ex, _cena = motor_com(
        [definicao(modo="ping_pong", repetir=3, movimento="linear")])
    motor.iniciar("a")
    for _ in range(3):
        motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 50.0)


def test_ping_pong_parse():
    prog = analisar_expandir(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
        ' animação a {\n  alvo: t\n  posição: 0px 0px -> 10px 0px\n'
        '  modo: ping_pong\n  repetir: 2\n }\n}\n')
    validar(prog)
    assert prog.janelas[0].animacoes[0].modo == "ping_pong"
    with pytest.raises(ErroSemantico):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
            ' animação a {\n  alvo: t\n  posição: 0px 0px -> 10px 0px\n'
            '  modo: ziguezague\n }\n}\n'))


# ----- 22-24: pausa, retomada, cancelamento -----

def test_pausa_retomada_tempo_congelado():
    motor, no, _ex, _cena = motor_com([definicao()])
    motor.iniciar("a")
    motor.atualizar(300)
    motor.pausar("a")
    motor.atualizar(5000)
    assert no.x == 30.0
    motor.continuar("a")
    motor.atualizar(200)
    assert no.x == pytest.approx(50.0)


def test_cancelamento_estados():
    for quando in ("inicio", "meio", "delay", "repeticao"):
        if quando == "inicio":
            defs = [definicao()]
        elif quando == "meio":
            defs = [definicao()]
        elif quando == "delay":
            defs = [definicao(atraso_ms=500.0)]
        else:
            defs = [definicao(repetir=5)]
        motor, no, _ex, _cena = motor_com(defs)
        motor.iniciar("a")
        if quando == "meio":
            motor.atualizar(500)
        if quando == "repeticao":
            motor.atualizar(1000)
        motor.cancelar("a")
        x_antes = no.x
        motor.atualizar(1000)
        assert motor.execucoes["a"].estado == "cancelada"
        assert no.x == x_antes


def test_callback_comecar_e_cancelar_uma_vez():
    _ex, cena, prog = montar(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
        ' animação a {\n  alvo: t\n  posição: 0px 0px -> 10px 0px\n'
        '  duração: 200ms\n'
        '  quando começar {\n   mostrar("ini")\n  }\n'
        '  quando terminar {\n   mostrar("fim")\n  }\n'
        '  quando cancelar {\n   mostrar("canc")\n  }\n }\n}\n')
    no = cena.buscar("t")
    motor = MotorAnimacoes(_ex)
    motor.carregar([definicao_de_ast(a) for a in prog.janelas[0].animacoes],
                   cena)
    motor.iniciar("a")
    motor.atualizar(100)
    assert _ex.ctx.saida == ["ini"]
    motor.atualizar(100)
    assert _ex.ctx.saida == ["ini", "fim"]
    motor.atualizar(500)
    assert _ex.ctx.saida == ["ini", "fim"]  # 1x cada
    # cancelar dispara o seu callback 1x
    motor2, no2, ex2, _c2 = motor_com([definicao(
        ao_cancelar=A.Bloco(comandos=[A.Acao(
            nome="mostrar", args=[A.TextoLit(valor="c")])]))])
    motor2.iniciar("a")
    motor2.atualizar(100)
    motor2.cancelar("a")
    motor2.cancelar("a")
    assert ex2.ctx.saida == ["c"]


# ----- 25: callbacks ordem determinística -----

def test_callbacks_ordem():
    motor, no, ex, _cena = motor_com([
        definicao("um", ao_terminar=A.Bloco(comandos=[A.Acao(
            nome="mostrar", args=[A.TextoLit(valor="1")])])),
        definicao("dois", depois="um", inicio="manual",
                  ao_terminar=A.Bloco(comandos=[A.Acao(
                      nome="mostrar", args=[A.TextoLit(valor="2")])]))])
    motor.iniciar("um")
    motor.atualizar(1000)
    motor.atualizar(1000)
    assert ex.ctx.saida == ["1", "2"]


# ----- 26-28: snap, dt variável, drift -----

def test_snap_final_exato():
    motor, no, _ex, _cena = motor_com([definicao(movimento="mola")])
    motor.iniciar("a")
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 50.0)


def test_dt_variavel_equivalente():
    def correr(dts):
        motor, no, _ex, _cena = motor_com(
            [definicao(movimento="suave")])
        motor.iniciar("a")
        for dt in dts:
            motor.atualizar(dt)
        return (no.x, no.y)
    r1 = correr([16] * 63)  # ~1008ms
    r2 = correr([50] * 20)  # 1000ms
    r3 = correr([33, 17, 100, 250, 600])
    assert r1 == pytest.approx(r2, abs=1.0)
    assert r2 == (100.0, 50.0)
    assert r3 == (100.0, 50.0)


def test_sem_drift_repetido():
    motor, no, _ex, _cena = motor_com(
        [definicao(repetir=10, movimento="linear")])
    motor.iniciar("a")
    for _ in range(10):
        motor.atualizar(333)
        motor.atualizar(333)
        motor.atualizar(334)
    assert (no.x, no.y) == (100.0, 50.0)
    assert motor.execucoes["a"].estado == "concluida"


# ----- 29: spring dinâmico -----

def test_spring_converge_e_snap():
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                         (100.0, 0.0))],
                   fisica="mola", rigidez=180.0, amortecimento=12.0,
                   massa=1.0, movimento="linear")])
    motor.iniciar("a")
    for _ in range(20):
        motor.atualizar(100)
    assert (no.x, no.y) == (100.0, 0.0)
    assert motor.execucoes["a"].estado == "concluida"


def test_spring_overshoot_controlado():
    mola = Spring(rigidez=180.0, amortecimento=12.0, massa=1.0)
    mola.fixar(0.0)
    amostras = [mola.passo(16.0, 100.0) for _ in range(200)]
    assert max(amostras) > 100.0  # ultrapassa (subamortecida)
    assert abs(amostras[-1] - 100.0) < 1.0  # assenta
    # crítica não explode nem ultrapassa muito
    rigida = Spring(rigidez=50.0, amortecimento=14.0, massa=1.0)
    rigida.fixar(0.0)
    amostras2 = [rigida.passo(16.0, 100.0) for _ in range(300)]
    assert max(amostras2) < 110.0
    assert abs(amostras2[-1] - 100.0) < 1.0
    with pytest.raises(ErroELiXX):
        Spring(rigidez=-5)
    with pytest.raises(ErroELiXX):
        Spring(amortecimento=float("inf"))


def test_spring_vs_easing_distintos():
    from elixx.animacao.motion import mola_parametrica as _mp

    f = _mp(180, 12)  # easing: função pura
    assert f(0.5) == f(0.5)
    s = Spring(180, 12, 1.0)  # dinâmica: tem estado
    s.fixar(0.0)
    assert s.passo(16.0, 100.0) != s.passo(16.0, 100.0)


def test_spring_linguagem():
    prog = analisar_expandir(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
        ' animação a {\n  alvo: t\n  posição: 0px 0px -> 100px 0px\n'
        '  fisica: mola\n  rigidez: 180\n  amortecimento: 12\n }\n}\n')
    validar(prog)
    anim = prog.janelas[0].animacoes[0]
    assert anim.fisica == "mola"
    with pytest.raises(ErroSemantico):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n }\n'
            ' animação a {\n  alvo: t\n  posição: 0px 0px -> 100px 0px\n'
            '  fisica: gravidade\n }\n}\n'))


# ----- 30-31: elastic, bounce -----

def test_elastic_deterministico():
    assert EASINGS["elastico"](0.0) == pytest.approx(0.0)
    assert EASINGS["elastico"](1.0) == pytest.approx(1.0, abs=0.01)
    assert EASINGS["elastico"](0.5) == EASINGS["elastico"](0.5)
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                         (100.0, 0.0))],
                   movimento="elastico")])
    motor.iniciar("a")
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 0.0)


def test_bounce_0_a_100():
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                         (100.0, 0.0))],
                   movimento="quicar")])
    motor.iniciar("a")
    vistos = []
    for _ in range(10):
        motor.atualizar(100)
        vistos.append(no.x)
    assert min(vistos) >= 0.0
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 0.0)


# ----- 32-33: relativo, para alvo -----

def test_movimento_relativo():
    _ex, cena, prog = montar(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "x"\n'
        '  posição: 100px 100px\n }\n'
        ' animação a {\n  alvo: t\n  posição: 0px 0px -> 50px 20px\n'
        '  relativo: verdadeiro\n  movimento: linear\n }\n}\n')
    no = cena.buscar("t")
    motor = MotorAnimacoes(_ex)
    motor.carregar([definicao_de_ast(a) for a in prog.janelas[0].animacoes],
                   cena)
    motor.iniciar("a")
    motor.atualizar(1000)
    assert (no.x, no.y) == (150.0, 120.0)


def test_mover_para_vetor_interno():
    origem, destino = Vector2(100, 100), Vector2(500, 300)
    desl = vetor_para(origem, destino)
    assert desl.tupla() == (400.0, 200.0)
    assert mover_por_ponto(origem, Vector2(50, 20)).tupla() == (150.0, 120.0)


def test_alvo_dinamico_callable():
    alvo = {"x": 300.0}
    motor, no, _ex, _cena = motor_com(
        [definicao(chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                         lambda: (alvo["x"], 0.0))])])
    alvo["x"] = 400.0  # muda antes do início
    motor.iniciar("a")
    motor.atualizar(1000)
    assert (no.x, no.y) == (400.0, 0.0)


# ----- 34-35: mesmo objeto, conflito -----

def test_motions_diferentes_coexistem():
    motor, no, _ex, _cena = motor_com([
        definicao("p", chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                             (100.0, 0.0))]),
        definicao("r", chaves=[ChaveAnimacao("rotacao", 0.0, 90.0)])])
    motor.iniciar("p")
    motor.iniciar("r")
    motor.atualizar(1000)
    assert (no.x, no.y) == (100.0, 0.0)
    assert no.rotacao == pytest.approx(90.0)


def test_conflito_novo_substitui_antigo():
    motor, no, _ex, _cena = motor_com([
        definicao("velha", chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                                 (100.0, 0.0))],
                  duracao_ms=2000.0),
        definicao("nova", chaves=[ChaveAnimacao("posicao", (0.0, 0.0),
                                                (0.0, 200.0))],
                  inicio="manual")])
    motor.iniciar("velha")
    motor.atualizar(500)
    assert no.x > 0.0
    motor.iniciar("nova")  # assume a mesma propriedade
    motor.atualizar(100)
    assert motor.execucoes["velha"].estado == "cancelada"
    assert motor.execucoes["velha"].substituida is True
    motor.atualizar(1000)
    assert (no.x, no.y) == (0.0, 200.0)


# ----- 36-38: hierarquia, grupo, viewport -----

def test_hierarquia_pai_filho_motions():
    _ex, cena, prog = montar(
        'janela p {\n titulo: "T"\n grupo g {\n  posição: 100px 100px\n'
        '  objeto f {\n   posição: 10px 0px\n  }\n }\n'
        ' animação mp {\n  alvo: g\n  posição: 100px 100px -> 200px 100px\n'
        '  movimento: linear\n }\n'
        ' animação mf {\n  alvo: f\n  posição: 10px 0px -> 50px 0px\n'
        '  movimento: linear\n }\n}\n')
    from elixx.visual.transform import combinar
    from elixx.visual.transform import transform_de_no

    g, f = cena.buscar("g"), cena.buscar("f")
    motor = MotorAnimacoes(_ex)
    motor.carregar([definicao_de_ast(a) for a in prog.janelas[0].animacoes],
                   cena)
    motor.iniciar("mp")
    motor.iniciar("mf")
    motor.atualizar(1000)
    assert (g.x, g.y) == (200.0, 100.0)
    assert (f.x, f.y) == (50.0, 0.0)
    global_f = combinar(transform_de_no(g), transform_de_no(f))
    assert (global_f.x, global_f.y) == (250.0, 100.0)


def test_grupo_move_filho_gira_outro_escala():
    from elixx.visual.transform import combinar, transform_de_no

    _ex, cena, prog = montar(
        'janela p {\n titulo: "T"\n grupo g {\n  posição: 0px 0px\n'
        '  objeto a {\n   posição: 10px 0px\n  }\n'
        '  objeto b {\n   posição: 0px 10px\n  }\n }\n'
        ' animação m1 {\n  alvo: g\n  posição: 0px 0px -> 100px 0px\n'
        '  movimento: linear\n }\n'
        ' animação m2 {\n  alvo: a\n  rotação: 0deg -> 90deg\n'
        '  movimento: linear\n }\n'
        ' animação m3 {\n  alvo: b\n  escala: 1 -> 2\n'
        '  movimento: linear\n }\n}\n')
    g, a, b = (cena.buscar(n) for n in ("g", "a", "b"))
    motor = MotorAnimacoes(_ex)
    motor.carregar([definicao_de_ast(x) for x in prog.janelas[0].animacoes],
                   cena)
    for nome in ("m1", "m2", "m3"):
        motor.iniciar(nome)
    motor.atualizar(1000)
    assert (g.x, g.y) == (100.0, 0.0)
    assert a.rotacao == pytest.approx(90.0)
    assert b.escala_x == pytest.approx(2.0)
    ga = combinar(transform_de_no(g), transform_de_no(a))
    assert (ga.x, ga.y) == pytest.approx((110.0, 0.0))


def test_viewport_com_motion():
    from elixx.visual.transform import Vector2 as V2

    _ex, cena, prog = montar(
        'janela p {\n titulo: "T"\n tamanho: 800px 600px\n'
        ' texto t {\n  texto: "x"\n  posição: 0px 0px\n }\n'
        ' animação a {\n  alvo: t\n  posição: 0px 0px -> 400px 300px\n'
        '  movimento: linear\n }\n}\n')
    no = cena.buscar("t")
    motor = MotorAnimacoes(_ex)
    motor.carregar([definicao_de_ast(x) for x in prog.janelas[0].animacoes],
                   cena)
    motor.iniciar("a")
    motor.atualizar(1000)
    tela = cena.viewport.mundo_para_tela(V2(no.x, no.y))
    assert tela.tupla() == (400.0, 300.0)


# ----- composição interna -----

def test_motion_plano_e_grupo():
    plano = Motion(alvo="n", propriedades=["posicao"],
                   inicio={"posicao": (0.0, 0.0)},
                   fim={"posicao": (100.0, 0.0)},
                   duracao_ms=1000.0, curva_nome="linear")
    assert plano.progresso(500) == pytest.approx(0.5)
    assert plano.avaliar(500) == {"posicao": (50.0, 0.0)}
    motor, no, _ex, _cena = motor_com([
        definicao("m1"), definicao("m2", depois="m1", inicio="manual")])
    grupo = MotionGroup("g", motor, ["m1", "m2"], modo="sequencia")
    grupo.preparar()
    grupo.iniciar()
    motor.atualizar(1000)
    motor.atualizar(1000)
    assert grupo.estado() == "concluida"


# ----- 39-40: Tk e HTML seguem renderer -----

def test_tk_recebe_estado_calculado():
    try:
        from elixx.visual.tk import RenderizadorTk
    except ImportError:
        pytest.skip("Tk indisponível")
    try:
        _ex, cena, prog = montar(
            'janela p {\n titulo: "T"\n tamanho: 400px 300px\n'
            ' texto t {\n  texto: "x"\n  posição: 0px 0px\n }\n'
            ' animação a {\n  alvo: t\n  posição: 0px 0px -> 120px 60px\n'
            '  movimento: linear\n  duração: 1000ms\n }\n}\n')
        no = cena.buscar("t")
        motor = MotorAnimacoes(_ex)
        motor.carregar(
            [definicao_de_ast(x) for x in prog.janelas[0].animacoes], cena)
        rend = RenderizadorTk(_ex)
        try:
            rend.montar(cena)
            rend.raiz.withdraw()
            # sem easing no renderer: só aplica geometria da cena
            assert "mola" not in dir(rend) and "easing" not in dir(rend)
            motor.iniciar("a")
            motor.atualizar(500)
            rend.atualizar(16.0)
            rend.raiz.update()
            assert (no.x, no.y) == (60.0, 30.0)
        finally:
            rend.fechar()
    except Exception as exc:
        import tkinter as _tk

        if isinstance(exc, _tk.TclError):
            pytest.skip(f"sem display: {exc}")
        raise


def test_html_sem_logica_motion():
    from elixx.visual.html import gerar_html

    _ex, _cena, _prog = montar(
        'janela p {\n titulo: "T"\n texto t {\n  texto: "oi"\n }\n}\n')
    pagina = gerar_html(_ex.ctx.objetos)
    assert "translate" not in pagina  # sem transform: saída legada


# ----- exemplo e regressão -----

def test_exemplo_motion_core():
    with open("exemplos/motion-core.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    assert cena.buscar("personagem") is not None
    assert len(prog.janelas[0].animacoes) >= 8
