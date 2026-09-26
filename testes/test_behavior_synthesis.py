"""Testes da Fase 17 — Behavior Synthesis (determinísticos, dt falso)."""
import time

import pytest

from elixx.animacao.motor import MotorAnimacoes
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.navegacao import plano_travessia
from elixx.visual.personagem import Gesture, vincular_personagens
from elixx.visual.transform import Vector2
from elixx.visual.mundo import vincular_mundos
from elixx.visual.capacidades import vincular_itens
from elixx.visual.sintese_movimento import MotionSynthesizer
from elixx.visual.sintese_comportamento import (
    BehaviorEvent,
    BehaviorPlan,
    BehaviorStep,
    BehaviorSynthesizer,
    BehaviorTrack,
    debug_comportamento,
)


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


def vinculo(fonte):
    ex, cena, prog = montar(fonte)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    from elixx.visual.navegacao import vincular_navegacao

    grafos = vincular_navegacao(cena, prog, mundos)
    return ex, cena, prog, itens, pers, mundos, grafos


FONTE = ('janela p {\n titulo: "T"\n'
         ' personagem Heroi {\n  posição: 100px 500px\n'
         '  parte corpo {\n   imagem: "corpo.png"\n  }\n'
         '  parte cabeca {\n   posição: 20px 0px\n  }\n'
         '  parte braco {\n   posição: 20px 0px\n  }\n'
         '  capacidade andar\n  capacidade pular\n  capacidade voar\n'
         '  pose repouso {\n   braco:\n    rotação: 0deg\n'
         '   cabeca:\n    rotação: 0deg\n  }\n'
         '  pose andar {\n   braco:\n    rotação: 20deg\n  }\n'
         '  pose pulo {\n   braco:\n    rotação: 40deg\n  }\n'
         '  expressao sorriso {\n   cabeca:\n    rotação: 5deg\n  }\n'
         '  expressao neutra {\n   cabeca:\n    rotação: 0deg\n  }\n'
         ' }\n'
         ' mundo M {\n  tamanho: 2000px 1200px\n'
         '  chão chao_a {\n   posição: 0px 550px\n   tamanho: 800px 50px\n  }\n'
         '  plataforma plat_b {\n   posição: 900px 400px\n'
         '   tamanho: 300px 30px\n  }\n'
         '  plataforma plat_alta {\n   posição: 1400px 150px\n'
         '   tamanho: 200px 30px\n  }\n'
         '  ponto base {\n   posição: 100px 550px\n  }\n'
         '  ponto saida {\n   posição: 1500px 165px\n  }\n'
         '  usar personagem Heroi\n'
         ' }\n'
         ' navegacao Rotas {\n'
         '  caminho base -> chao_a {\n   modo: andar\n  }\n'
         '  caminho chao_a -> plat_b {\n   modo: pular\n   custo: 2\n  }\n'
         '  caminho plat_b -> plat_alta {\n   modo: voar\n   custo: 4\n'
         '   requer: voar\n  }\n'
         '  caminho plat_alta -> saida {\n   modo: andar\n  }\n'
         ' }\n}\n')


def base():
    return vinculo(FONTE)


def sintetizar(destino="plat_b", origem="base", **kw_sint):
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    heroi = pers["Heroi"]
    tplano = plano_travessia(grafos["Rotas"], origem, destino, heroi,
                             mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"], heroi,
                                           heroi, mundos["M"])
    bplan = BehaviorSynthesizer(**kw_sint).sintetizar(mplan, heroi)
    return _ex, cena, heroi, mundos, grafos, bplan


def executar_ate_fim(motor, dt_ms=50, limite=2000):
    for _ in range(limite):
        motor.atualizar(dt_ms)
        estados = [ex.estado for ex in motor.execucoes.values()]
        if estados and all(e == "concluida" for e in estados):
            break
    return [ex.estado for ex in motor.execucoes.values()]


# ----- andar/correr/pular/voar + pose -----

def test_andar_com_pose():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar()
    assert bplan.viavel is True
    step = bplan.steps[0]
    assert step.pose == "andar"
    assert step.estado == "andando"
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(10)  # gancho de início dispara a pose
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (900.0, 400.0)


def test_pular_com_pose():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar()
    step = bplan.steps[1]
    assert step.pose == "pulo"
    assert step.estado == "pulando"
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    # pose restaurada ao fim (volta a 0)
    assert cena.buscar("braco").rotacao == pytest.approx(0.0)


def test_voar_com_pose():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    heroi = pers["Heroi"]
    tplano = plano_travessia(grafos["Rotas"], "plat_b", "plat_alta", heroi,
                             mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"], heroi,
                                           heroi, mundos["M"])
    bplan = BehaviorSynthesizer(
        poses={"voar": "pulo"}).sintetizar(mplan, heroi)
    assert bplan.steps[0].pose == "pulo"
    motor = MotorAnimacoes(_ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    assert cena.buscar("Heroi").x == pytest.approx(1400.0)


def test_correr_mapeia_pose():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    tplano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                             pers["Heroi"], mundos["M"])
    tplano.etapas = [dict(tplano.etapas[0], modo="correr")]
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                           pers["Heroi"])
    bplan = BehaviorSynthesizer(poses={"correr": "andar"}).sintetizar(
        mplan, pers["Heroi"])
    assert bplan.steps[0].pose == "andar"
    assert bplan.steps[0].estado == "correndo"


# ----- expressão, gesto, composição -----

def test_expressao_coexiste():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        expressoes={0: "sorriso"})
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(10)
    assert cena.buscar("cabeca").rotacao == pytest.approx(5.0)
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)
    executar_ate_fim(motor)


def test_gesto_dispara_e_conclui():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        gestos={1: Gesture(nome="acenar", passos=["andar", "repouso"])})
    assert bplan.steps[1].gesture.nome == "acenar"
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    assert heroi.gesto_atual == "acenar"
    assert (cena.buscar("Heroi").x,
            cena.buscar("Heroi").y) == (900.0, 400.0)


def test_pose_mais_expressao():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        expressoes={0: "sorriso"})
    step = bplan.steps[0]
    assert step.pose == "andar"
    assert step.expression == "sorriso"
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(10)
    # corpo da pose + camada separada da expressão
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)
    assert cena.buscar("cabeca").rotacao == pytest.approx(5.0)


def test_movimento_pose_expressao():
    ex, cena, heroi, mundos, _grafos, bplan = sintetizar(
        expressoes={1: "sorriso"})
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (900.0, 400.0)
    debug = debug_comportamento(bplan)
    assert "expressao=sorriso" in debug


# ----- tracks, sequência, callbacks -----

def test_tracks_paralelos():
    _ex, _cena, heroi, _mundos, _grafos, bplan = sintetizar(
        gestos={0: Gesture(nome="g", passos=["repouso"])},
        expressoes={0: "sorriso"})
    nomes = [t.nome for t in bplan.tracks]
    assert nomes == ["movimento", "pose", "gesto", "expressao"]
    por_nome = {t.nome: t for t in bplan.tracks}
    assert por_nome["movimento"].passos[0][1] == "passo_00_andar"
    assert por_nome["pose"].passos[0] == (0, "andar")
    assert por_nome["gesto"].passos[0] == (0, "g")
    assert por_nome["expressao"].passos[0] == (0, "sorriso")


def test_sequencia_ordem_steps():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        destino="plat_alta")
    assert [s.motion_step.modo for s in bplan.steps] == ["andar", "pular",
                                                         "voar"]
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(10)
    assert motor.execucoes[
        "behavior_s01_passo_01_pular"].estado == "aguardando"
    executar_ate_fim(motor)
    assert (cena.buscar("Heroi").x,
            cena.buscar("Heroi").y) == (1400.0, 150.0)


def test_callbacks_inicio_fim():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar()
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    ex_def = motor.execucoes["behavior_s00_passo_00_andar"]
    assert callable(ex_def.definicao.ao_comecar)
    assert callable(ex_def.definicao.ao_terminar)
    motor.atualizar(10)
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)


def test_callback_usuario_preservado():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar()
    step = bplan.steps[0]
    disparou = []
    step.motion_step.motion.ao_comecar = lambda: disparou.append("user")
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(10)
    assert disparou == ["user"]  # anterior preservado...
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)  # ...+pose


# ----- cancelamento, restauração, prioridade, conflito -----

def test_cancelamento_restaura():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        destino="plat_alta")
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(100)
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)
    motor.cancelar("behavior_s00_passo_00_andar")
    motor.atualizar(10)
    assert motor.execucoes[
        "behavior_s00_passo_00_andar"].estado == "cancelada"
    assert cena.buscar("braco").rotacao == pytest.approx(0.0)


def test_restauracao_preserva_permanente():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar()
    cena.buscar("cabeca").rotacao = 7.0  # estado permanente
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    assert cena.buscar("cabeca").rotacao == pytest.approx(7.0)
    assert cena.buscar("braco").rotacao == pytest.approx(0.0)


def test_prioridade_emergencia_vence():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        gestos={0: Gesture(nome="mexer", passos=["andar"])})
    step = bplan.steps[0]
    step.prioridade = "emergencia"
    step.pose = "pulo"  # braco 40deg vence o gesto ao fim
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    assert cena.buscar("braco").rotacao == pytest.approx(40.0)


def test_conflito_partes_deterministico():
    # expressão na mesma parte da pose corporal: corpo vence, expressão
    # registra o pulo e aplica no resto
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        expressoes={0: "andar"})
    step = bplan.steps[0]
    assert step.pose == "andar"  # braco 20 + cabeca 0
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    motor.atualizar(10)
    # "andar" como expressão toca braco (ocupado) → pulado
    assert step.metadados.get("expressao_pulada", []) == ["braco"]
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)


# ----- requisitos, capability, personagem, vazio, inválidos -----

def test_requisitos_validados():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    heroi = pers["Heroi"]
    tplano = plano_travessia(grafos["Rotas"], "plat_b", "plat_alta", heroi,
                             mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"], heroi,
                                           heroi, mundos["M"])
    bplan = BehaviorSynthesizer().sintetizar(mplan, heroi)
    assert bplan.viavel is True
    assert bplan.requisitos == ["voar"]


def test_capability_ausente_inviavel():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    tplano = plano_travessia(grafos["Rotas"], "plat_b", "plat_alta",
                             pers["Heroi"], mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                           pers["Heroi"])
    # holder sem voar (outro invasor sem capacidades)
    from elixx.visual.personagem import Character

    from elixx.visual.cena import NoVisual

    falso = Character(nome="Falso",
                      no_raiz=NoVisual(tipo="personagem", nome="Falso",
                                       x=0.0, y=0.0),
                      partes={}, poses={})
    from elixx.visual.capacidades import CapabilitySet, Inventario

    falso.capacidades = CapabilitySet()
    falso.inventario = Inventario(dono="Falso")
    bplan = BehaviorSynthesizer().sintetizar(mplan, pers["Heroi"], falso)
    assert bplan.viavel is False
    assert "voar" in bplan.motivo
    assert bplan.steps == []


def test_personagem_invalido_erro():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    tplano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                             pers["Heroi"], mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                           pers["Heroi"])
    with pytest.raises(ErroELiXX, match="sem nó root"):
        BehaviorSynthesizer().sintetizar(mplan, object())
    with pytest.raises(ErroELiXX, match="Alvo de síntese inválido"):
        MotionSynthesizer().sintetizar(tplano, grafos["Rotas"], None)


def test_plano_vazio():
    from elixx.visual.sintese_movimento import MotionPlan

    _ex, _cena, _prog, _itens, pers, _mundos, _grafos = base()
    bplan = BehaviorSynthesizer().sintetizar(
        MotionPlan(origem="a", destino="b"), pers["Heroi"])
    assert bplan.steps == [] and bplan.viavel is True
    motor = MotorAnimacoes(_ex)
    assert bplan.executar(motor, None, pers["Heroi"])["estado"] == "vazio"


def test_comportamento_invalido_erro():
    with pytest.raises(ErroELiXX, match="Prioridade inválida"):
        BehaviorStep(nome="x", prioridade="urgentissimo")
    with pytest.raises(ErroELiXX, match="Estado corporal inválido"):
        BehaviorStep(nome="x", estado="dormindo")
    with pytest.raises(ErroELiXX, match="BehaviorEvent"):
        BehaviorStep(nome="x", eventos=["nao-evento"])
    with pytest.raises(ErroELiXX, match="Evento inválido"):
        BehaviorEvent(quando="no_meio")
    with pytest.raises(ErroELiXX, match="Track inválida"):
        from elixx.visual.sintese_comportamento import BehaviorTrack

        BehaviorTrack(nome="luz")
    with pytest.raises(ErroELiXX, match="não registrado"):
        _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
        tplano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                                 pers["Heroi"], mundos["M"])
        mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                               pers["Heroi"])
        BehaviorSynthesizer(gestos={0: "sambarilove"}).sintetizar(
            mplan, pers["Heroi"])
    with pytest.raises(ErroELiXX, match="não encontrada"):
        _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
        tplano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                                 pers["Heroi"], mundos["M"])
        mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                               pers["Heroi"])
        BehaviorSynthesizer(poses={"andar": "rebolar"}).sintetizar(
            mplan, pers["Heroi"])


# ----- determinismo, segurança, mid, pose_fim -----

def test_determinismo():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    tplano = plano_travessia(grafos["Rotas"], "base", "plat_alta",
                             pers["Heroi"], mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                           pers["Heroi"], pers["Heroi"],
                                           mundos["M"])
    sint = BehaviorSynthesizer(expressoes={2: "sorriso"})
    a = debug_comportamento(sint.sintetizar(mplan, pers["Heroi"]))
    b = debug_comportamento(sint.sintetizar(mplan, pers["Heroi"]))
    assert a == b


def test_seguranca_sem_eval_exec():
    import inspect

    import elixx.visual.sintese_comportamento as modulo

    fonte = inspect.getsource(modulo)
    assert "eval(" not in fonte
    assert "exec(" not in fonte
    assert "importlib" not in fonte
    assert "__import__" not in fonte
    # nomes maliciosos continuam dados inertes
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    tplano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                             pers["Heroi"], mundos["M"])
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rotas"],
                                           pers["Heroi"])
    with pytest.raises(ErroELiXX, match="não encontrada"):
        BehaviorSynthesizer(
            poses={"andar": "__import__('os')"}).sintetizar(mplan,
                                                            pers["Heroi"])


def test_evento_meio_dispara_pose():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(
        eventos={0: [BehaviorEvent(quando="ao_meio", acao="pose",
                                   alvo="pulo")]})
    nomes = [m.motion_step.motion.nome if m.motion_step
             and m.motion_step.motion else None for m in bplan.steps]
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    assert any(n.endswith("_meio0") for n in motor.execucoes)
    executar_ate_fim(motor)
    # meio aplicou pulo (40), fim restaurou pose andar do step... e o
    # próprio fim do step restaura o snapshot (0)
    assert cena.buscar("braco").rotacao == pytest.approx(0.0)
    _ = nomes


def test_pose_fim_explicita():
    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar(restaurar=False)
    bplan.steps[-1].pose_fim = "repouso"
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    assert cena.buscar("braco").rotacao == pytest.approx(0.0)
    assert cena.buscar("cabeca").rotacao == pytest.approx(0.0)


def test_debug_comportamento():
    _ex, _cena, heroi, _mundos, _grafos, bplan = sintetizar(
        expressoes={1: "sorriso"})
    texto = debug_comportamento(bplan)
    assert "BehaviorPlan behavior (Heroi, 2 passos" in texto
    assert "estado=andando" in texto and "estado=pulando" in texto
    assert "motion=passo_00_andar" in texto
    assert "pose=andar" in texto
    assert "expressao=sorriso" in texto
    assert "etapas" not in texto  # etapas vivem nos steps, não no debug


def test_debug_inviavel():
    from elixx.visual.sintese_comportamento import debug_comportamento as db

    plano = BehaviorPlan(nome="x", viavel=False, motivo="sem rota")
    assert "motivo: sem rota" in db(plano)


# ----- HTML honesto -----

def test_html_compila_apos_behavior():
    from elixx.visual.html import gerar_html

    ex, cena, heroi, _mundos, _grafos, bplan = sintetizar()
    motor = MotorAnimacoes(ex)
    bplan.executar(motor, cena, heroi)
    executar_ate_fim(motor)
    pagina = gerar_html(ex.ctx.objetos)
    assert isinstance(pagina, str) and "<html" in pagina


# ----- Tk visual real -----

def test_tk_jornada_completa():
    try:
        from elixx.visual.tk import RenderizadorTk
    except ImportError:
        pytest.skip("Tk indisponível")
    try:
        _ex, cena, prog = montar(
            'janela p {\n titulo: "T"\n tamanho: 800px 600px\n'
            ' personagem Heroi {\n  posição: 50px 500px\n'
            '  parte corpo {\n   imagem: "corpo.png"\n  }\n'
            '  parte cabeca {\n   posição: 20px 0px\n  }\n'
            '  parte braco {\n   posição: 20px 0px\n  }\n'
            '  capacidade andar\n  capacidade pular\n  capacidade voar\n'
            '  pose repouso {\n   braco:\n    rotação: 0deg\n'
            '   cabeca:\n    rotação: 0deg\n  }\n'
            '  pose andar {\n   braco:\n    rotação: 20deg\n  }\n'
            '  pose pulo {\n   braco:\n    rotação: 40deg\n  }\n'
            '  expressao sorriso {\n   cabeca:\n    rotação: 5deg\n  }\n'
            ' }\n'
            ' mundo M {\n  tamanho: 2000px 1200px\n'
            '  ponto A {\n   posição: 50px 500px\n  }\n'
            '  ponto B {\n   posição: 250px 500px\n  }\n'
            '  ponto C {\n   posição: 450px 300px\n  }\n'
            '  ponto D {\n   posição: 650px 300px\n  }\n'
            '  usar personagem Heroi\n }\n'
            ' navegacao R {\n'
            '  caminho A -> B {\n   modo: andar\n  }\n'
            '  caminho B -> C {\n   modo: pular\n  }\n'
            '  caminho C -> D {\n   modo: voar\n  }\n'
            ' }\n}\n')
        itens = vincular_itens(prog)
        pers = vincular_personagens(cena, itens)
        mundos = vincular_mundos(cena, prog, pers, itens)
        from elixx.visual.navegacao import vincular_navegacao

        grafos = vincular_navegacao(cena, prog, mundos)
        heroi = pers["Heroi"]
        tplano = plano_travessia(grafos["R"], "A", "D", heroi, mundos["M"])
        mplan = MotionSynthesizer().sintetizar(tplano, grafos["R"], heroi,
                                               heroi, mundos["M"])
        bplan = BehaviorSynthesizer(
            expressoes={2: "sorriso"}).sintetizar(mplan, heroi)
        motor = MotorAnimacoes(_ex)
        rend = RenderizadorTk(_ex)
        try:
            rend.montar(cena)
            rend.raiz.withdraw()
            bplan.executar(motor, cena, heroi)
            no = cena.buscar("Heroi")
            viu_braco_erguido = False
            for _ in range(600):
                motor.atualizar(50)
                rend.atualizar(16.0)
                rend.raiz.update()
                if abs(cena.buscar("braco").rotacao - 40.0) < 1.0:
                    viu_braco_erguido = True
                estados = [e.estado for e in motor.execucoes.values()]
                if estados and all(e == "concluida" for e in estados):
                    break
            assert viu_braco_erguido  # pose pulo atuou no meio
            assert (no.x, no.y) == (650.0, 300.0)  # destino exato
            assert no.rotacao == pytest.approx(0.0)  # último: p/ direita
            assert cena.buscar("cabeca").rotacao == pytest.approx(0.0)
        finally:
            rend.fechar()
    except Exception as exc:
        import tkinter as _tk

        if isinstance(exc, _tk.TclError):
            pytest.skip(f"sem display: {exc}")
        raise


# ----- stress -----

def test_stress_sintese_execucao():
    from types import SimpleNamespace

    _ex, cena, _prog = montar(
        'janela p {\n titulo: "T"\n texto alvo {\n  texto: "x"\n }\n}\n')
    no = cena.buscar("alvo")
    for total in (10, 100, 500, 1000):
        nos = {f"n{i}": SimpleNamespace(
            posicao=(lambda i=i: Vector2(float(i * 10), 0.0)))
            for i in range(total + 1)}
        grafo = SimpleNamespace(nos=nos)
        from elixx.visual.navegacao import TraversalPlan

        etapas = [{"de": f"n{i}", "para": f"n{i + 1}", "modo": "andar",
                   "requisitos": []} for i in range(total)]
        travessia = TraversalPlan(origem="n0", destino=f"n{total}",
                                  etapas=etapas)
        inicio = time.perf_counter()
        sint = BehaviorSynthesizer()
        # personagem mínimo com as peças usadas pelos ganchos
        heroi = _heroi_fake()
        mp = MotionSynthesizer().sintetizar(travessia, grafo, "alvo")
        meio = time.perf_counter()
        bp = sint.sintetizar(mp, heroi)
        meio2 = time.perf_counter()
        assert len(bp.steps) == total
        assert len(bp.tracks) == 4
        motor = MotorAnimacoes(_ex)
        bp.executar(motor, cena, heroi)
        ticks = 0
        inicio_tick = time.perf_counter()
        for _ in range(1200):
            motor.atualizar(50)
            ticks += 1
            if all(e.estado == "concluida"
                   for e in motor.execucoes.values()):
                break
        fim = time.perf_counter()
        assert (no.x, no.y) == (float(total * 10), 0.0)
        sintese_ms = (meio - inicio) * 1000.0 + (meio2 - meio) * 1000.0
        tick_ms = (fim - inicio_tick) * 1000.0 / max(ticks, 1)
        assert sintese_ms < 30000 and tick_ms < 1000


def _heroi_fake():
    from elixx.visual.cena import NoVisual
    from elixx.visual.personagem import Character

    raiz = NoVisual(tipo="personagem", nome="alvo", x=0.0, y=0.0)
    return Character(nome="alvo", no_raiz=raiz, partes={}, poses={})


# ----- exemplo + demo integrado F13–F17 -----

def test_exemplo_behavior_synthesis():
    with open("exemplos/behavior-synthesis.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    from elixx.visual.navegacao import vincular_navegacao

    grafos = vincular_navegacao(cena, prog, mundos)
    assert "Rota" in grafos
    assert "Heroi" in pers
    assert "Mundo" in mundos


def test_demo_integrado_f13_f17():
    # F13 mundo + F14 item/equipar + F15 rota + F16 motion + F17 behavior.
    # Decisões explícitas no teste (sem autonomia): equipar, gestos, poses.
    with open("exemplos/behavior-synthesis.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    from elixx.visual.navegacao import vincular_navegacao

    grafos = vincular_navegacao(cena, prog, mundos)
    heroi = pers["Heroi"]
    mundo = mundos["Mundo"]
    # F14: equipa a corda explicitamente (sem decisão autônoma)
    from elixx.visual.capacidades import obter_instancia

    heroi.inventario.possuir(obter_instancia(itens, "Corda"))
    heroi.inventario.equipar("Corda")
    assert heroi.equipado("Corda")
    # F15: rota até o destino
    tplano = plano_travessia(grafos["Rota"], "inicio", "destino", heroi,
                             mundo)
    assert tplano.path is not None
    # F16: waypoints preservados, F17: corpo sincronizado
    mplan = MotionSynthesizer().sintetizar(tplano, grafos["Rota"], heroi,
                                           heroi, mundo)
    bplan = BehaviorSynthesizer(
        expressoes={3: "sorriso"},
        gestos={3: Gesture(nome="chegar",
                           passos=["repouso"])}).sintetizar(mplan, heroi)
    assert bplan.viavel is True
    motor = MotorAnimacoes(executor)
    resultado_exec = bplan.executar(motor, cena, heroi)
    assert resultado_exec["estado"] == "executando"
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (650.0, 250.0)  # destino exato
    assert heroi.gesto_atual == "chegar"
    texto = debug_comportamento(bplan)
    assert "BehaviorPlan" in texto and "Heroi" in texto
