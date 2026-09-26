"""Testes da Fase 16 — Motion Synthesis (determinísticos, dt falso)."""
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
from elixx.visual.navegacao import TraversalPlan, plano_travessia
from elixx.visual.personagem import vincular_personagens
from elixx.visual.mundo import vincular_mundos
from elixx.visual.capacidades import vincular_itens
from elixx.visual.sintese_movimento import (
    MODOS_SINTESE,
    MotionPlan,
    MotionSynthesizer,
    debug_sintese_movimento,
    orientacao_graus,
)
from elixx.visual.transform import Vector2


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
         '  parte corpo {\n  }\n'
         '  capacidade andar\n  capacidade pular\n  capacidade voar\n'
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


def sintetizar_rota(grafos, origem, destino, heroi, mundo, **kw):
    plano = plano_travessia(grafos["Rotas"], origem, destino, heroi, mundo)
    sint = MotionSynthesizer(**kw)
    return sint.sintetizar(plano, grafos["Rotas"], heroi, heroi, mundo)


def executar_ate_fim(motor, dt_ms=100, limite=2000):
    for _ in range(limite):
        motor.atualizar(dt_ms)
        estados = [ex.estado for ex in motor.execucoes.values()]
        if estados and all(e == "concluida" for e in estados):
            break
    return [ex.estado for ex in motor.execucoes.values()]


# ----- modos -----

def test_modos_cobertos():
    assert set(MODOS_SINTESE) == {"andar", "correr", "pular", "escalar",
                                  "descer", "voar", "pairar", "teleportar"}


def test_andar_basico():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "base", "chao_a", pers["Heroi"],
                         mundos["M"])
    assert mp.viavel is True
    assert len(mp.steps) == 1
    step = mp.steps[0]
    assert step.modo == "andar"
    assert (step.waypoint_inicial.x, step.waypoint_inicial.y) == (100.0,
                                                                  550.0)
    assert (step.waypoint_final.x, step.waypoint_final.y) == (0.0, 550.0)
    assert step.duracao_ms == pytest.approx(500.0)  # 100px / 200px/s
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (0.0, 550.0)


def test_correr_velocidade():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    mp_andar = MotionSynthesizer().sintetizar(plano, grafos["Rotas"],
                                              "Heroi")
    plano2 = plano_travessia(grafos["Rotas"], "base", "chao_a",
                             pers["Heroi"], mundos["M"])
    # força modo correr via etapa direta
    plano2.etapas = [dict(plano2.etapas[0], modo="correr")]
    mp_correr = MotionSynthesizer().sintetizar(plano2, grafos["Rotas"],
                                               "Heroi")
    assert mp_correr.steps[0].duracao_ms == pytest.approx(
        mp_andar.steps[0].duracao_ms / 2.0)
    mp_custom = MotionSynthesizer(velocidades={"andar": 100.0})
    plano3 = plano_travessia(grafos["Rotas"], "base", "chao_a",
                             pers["Heroi"], mundos["M"])
    mp3 = mp_custom.sintetizar(plano3, grafos["Rotas"], "Heroi")
    assert mp3.steps[0].duracao_ms == pytest.approx(1000.0)


def test_pular_trajetoria():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "chao_a", "plat_b", pers["Heroi"],
                         mundos["M"])
    assert mp.viavel is True
    step = mp.steps[0]
    assert step.modo == "pular"
    quadros = step.motion.keyframes
    assert [q.tempo for q in quadros] == [0.0, 0.3, 0.5, 0.7, 1.0]
    apex = quadros[2].valores["posicao"]
    assert apex == (450.0, 475.0 - 60.0)  # meio − altura padrão
    inicio = quadros[0].valores["posicao"]
    fim = quadros[-1].valores["posicao"]
    assert inicio == (0.0, 550.0) and fim == (900.0, 400.0)
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (900.0, 400.0)


def test_pular_parametros():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "chao_a", "plat_b",
                            pers["Heroi"], mundos["M"])
    mp = MotionSynthesizer(altura_pulo=120.0, curva="linear").sintetizar(
        plano, grafos["Rotas"], "Heroi")
    apex = mp.steps[0].motion.keyframes[2].valores["posicao"]
    assert apex[1] == pytest.approx(475.0 - 120.0)
    assert mp.steps[0].motion.movimento == "linear"
    assert mp.steps[0].metadados["altura"] == 120.0


def test_escalar_descer():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "plat_b", "plat_alta",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="escalar")]
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    assert mp.steps[0].modo == "escalar"
    assert mp.steps[0].duracao_ms == pytest.approx(
        math_dist((900.0, 400.0), (1400.0, 150.0)) / 120.0 * 1000.0)
    plano.etapas = [dict(plano.etapas[0], modo="descer")]
    mp2 = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    motor = MotorAnimacoes(_ex)
    mp2.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (1400.0, 150.0)


def math_dist(a, b):
    import math as _m

    return _m.hypot(b[0] - a[0], b[1] - a[1])


def test_voar_continuo_e_opcoes():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "plat_b", "plat_alta", pers["Heroi"],
                         mundos["M"])
    step = mp.steps[0]
    assert step.modo == "voar"
    assert step.motion.movimento == "desacelerar"  # padrão
    mp2 = MotionSynthesizer(acelerar_voo=True,
                            desacelerar_voo=False).sintetizar(
        plano_travessia(grafos["Rotas"], "plat_b", "plat_alta",
                        pers["Heroi"], mundos["M"]),
        grafos["Rotas"], "Heroi")
    assert mp2.steps[0].motion.movimento == "acelerar"
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (1400.0, 150.0)


def test_pairar_oscila_e_termina_exato():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="pairar")]
    mp = MotionSynthesizer(amplitude_pairar=8.0).sintetizar(
        plano, grafos["Rotas"], "Heroi")
    step = mp.steps[0]
    quadros = step.motion.keyframes
    assert len(quadros) == 6
    assert quadros[-1].valores["posicao"] == (0.0, 550.0)
    assert quadros[2].valores["posicao"] == (0.0, 550.0 - 8.0)
    assert step.metadados["amplitude"] == 8.0
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (0.0, 550.0)


def test_teleportar_instantaneo():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="teleportar")]
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    assert mp.steps[0].duracao_ms == 0.0
    assert mp.steps[0].orientacao is None
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    motor.atualizar(0)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (0.0, 550.0)
    assert motor.execucoes["passo_00_teleportar"].estado == "concluida"


# ----- orientação -----

def test_orientacao_pontos_cardeais():
    assert orientacao_graus(Vector2(0, 0), Vector2(10, 0)) == 0.0
    assert orientacao_graus(Vector2(0, 0), Vector2(0, 10)) == 90.0
    assert orientacao_graus(Vector2(0, 0), Vector2(-10, 0)) in (180.0,
                                                                -180.0)
    assert orientacao_graus(Vector2(0, 0), Vector2(0, -10)) == -90.0
    assert orientacao_graus(Vector2(5, 5), Vector2(5, 5)) is None


def test_virar_durante_padrao():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "base", "chao_a", pers["Heroi"],
                         mundos["M"])
    step = mp.steps[0]
    assert step.orientacao == pytest.approx(180.0)
    props = [c.propriedade for c in step.motion.chaves]
    assert props == ["posicao", "rotacao"]
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (0.0, 550.0)
    assert no.rotacao == pytest.approx(180.0)


def test_virar_antes_sequencia():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    mp = MotionSynthesizer(virar_antes=True,
                           duracao_rotacao_ms=250.0).sintetizar(
        plano, grafos["Rotas"], "Heroi")
    assert len(mp.steps) == 2
    giro, move = mp.steps
    assert giro.motion.chaves[0].propriedade == "rotacao"
    assert giro.duracao_ms == 250.0
    assert giro.metadados.get("vira_antes") is True
    assert move.motion.depois == giro.motion.nome
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (0.0, 550.0)
    assert no.rotacao == pytest.approx(180.0)


def test_sem_orientar():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    mp = MotionSynthesizer(orientar=False).sintetizar(
        plano, grafos["Rotas"], "Heroi")
    assert mp.steps[0].orientacao is None
    assert [c.propriedade for c in
            mp.steps[0].motion.chaves] == ["posicao"]


# ----- waypoints, sequência, requisitos -----

def test_multiplos_waypoints_preservados():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "plat_alta",
                            pers["Heroi"], mundos["M"])
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"],
                                        pers["Heroi"], pers["Heroi"],
                                        mundos["M"])
    assert [s.modo for s in mp.steps] == ["andar", "pular", "voar"]
    assert (mp.steps[0].waypoint_inicial.x,
            mp.steps[0].waypoint_inicial.y) == (100.0, 550.0)
    assert (mp.steps[-1].waypoint_final.x,
            mp.steps[-1].waypoint_final.y) == (1400.0, 150.0)
    for anterior, proximo in zip(mp.steps, mp.steps[1:]):
        assert (anterior.waypoint_final.x,
                anterior.waypoint_final.y) == (
                    proximo.waypoint_inicial.x, proximo.waypoint_inicial.y)


def test_sequencia_executa_em_ordem():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "plat_b",
                            pers["Heroi"], mundos["M"])
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"],
                                        pers["Heroi"], pers["Heroi"],
                                        mundos["M"])
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    no = cena.buscar("Heroi")
    motor.atualizar(250)
    # primeiro step (andar 500ms) no meio; segundo ainda aguardando
    assert motor.execucoes["passo_01_pular"].estado == "aguardando"
    executar_ate_fim(motor)
    assert (no.x, no.y) == (900.0, 400.0)
    assert all(motor.execucoes[n].estado == "concluida"
               for n in ("passo_00_andar", "passo_01_pular"))


def test_requisito_nao_satisfeito_inviavel():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "plat_b",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="voar",
                         requisitos=["nadar"])]
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"],
                                        pers["Heroi"], pers["Heroi"],
                                        mundos["M"])
    assert mp.viavel is False
    assert mp.steps == []
    assert "inviável" in mp.motivo


def test_requisito_satisfeito_via_item():
    _ex, _cena, _prog, itens, pers, mundos, grafos = base()
    from elixx.visual.capacidades import ItemDefinition, nova_instancia

    heroi = pers["Heroi"]
    definicao = ItemDefinition(nome="AsaDelta", categoria="equipamento")
    from elixx.visual.capacidades import Capability

    definicao.capacidades.adicionar(Capability(nome="voar",
                                               provider="item:AsaDelta"))
    inst = nova_instancia(definicao, "asa1")
    heroi.inventario._defs_ref["AsaDelta"] = definicao
    heroi.inventario.possuir(inst)
    heroi.inventario.equipar("asa1")
    plano = plano_travessia(grafos["Rotas"], "base", "plat_b",
                            heroi, mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="voar",
                         requisitos=["voar"])]
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], heroi,
                                        heroi, mundos["M"])
    assert mp.viavel is True


# ----- personagem, transform, motion -----

def test_personagem_move_root_e_partes_seguem():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    heroi = pers["Heroi"]
    mp = sintetizar_rota(grafos, "base", "chao_a", heroi, mundos["M"])
    assert mp.nome_alvo == "Heroi"
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    antes = heroi.obter_transform_global("corpo")
    executar_ate_fim(motor)
    depois = heroi.obter_transform_global("corpo")
    assert (depois.x - antes.x) == pytest.approx(-100.0)
    assert (depois.y - antes.y) == pytest.approx(50.0)


def test_transform_base_f10():
    import inspect

    import elixx.visual.sintese_movimento as sintese

    fonte = inspect.getsource(sintese)
    # síntese não constrói Transform nem combina: só Vector2 de waypoint
    assert "combinar(" not in fonte
    assert "Transform(" not in fonte


def _fonte_sem_docstrings(modulo):
    import inspect

    return inspect.getsource(modulo)


def test_motion_f11_executa():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "base", "chao_a", pers["Heroi"],
                         mundos["M"])
    motor = MotorAnimacoes(_ex)
    resultado = mp.executar(motor, cena)
    assert resultado["estado"] == "executando"
    assert resultado["iniciados"] == ["passo_00_andar"]
    definicao = mp.steps[0].motion
    assert type(definicao).__name__ == "DefinicaoAnimacao"
    assert definicao.alvo == "Heroi"


def test_paralelo_e_espera():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    step = mp.steps[0]
    step.disparo = "paralelo"
    step.espera_ms = 200.0
    motor = MotorAnimacoes(_ex)
    nomes = mp.carregar(motor, cena)
    assert motor.execucoes[nomes[0]].definicao.atraso_ms == 200.0
    motor.iniciar(nomes[0])
    motor.atualizar(100)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (100.0, 500.0)  # ainda em espera
    executar_ate_fim(motor)
    assert (no.x, no.y) == (0.0, 550.0)


def test_plano_vazio_inviavel_estruturado():
    from elixx.visual.navegacao import TraversalPlan

    mp = MotionSynthesizer().sintetizar(TraversalPlan(origem="a",
                                                      destino="b"), None,
                                        "Heroi")
    assert isinstance(mp, MotionPlan)
    assert mp.viavel is False
    assert "vazio" in mp.motivo
    motor = MotorAnimacoes()
    assert mp.executar(motor, None)["estado"] == "vazio"


# ----- erros -----

def test_modo_invalido_erro_pt():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="nadar")]
    with pytest.raises(ErroELiXX, match="não suportado"):
        MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")


def test_etapa_sem_posicao_erro_pt():
    from elixx.visual.navegacao import NavigationGraph

    _ex, _cena, _prog, _itens, pers, mundos, _grafos = base()
    plano = plano_travessia(_grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    vazio = NavigationGraph("V", mundos["M"])
    with pytest.raises(ErroELiXX, match="fora do grafo"):
        MotionSynthesizer().sintetizar(plano, vazio, "Heroi")


def test_personagem_inexistente_erro_pt():
    _ex, _cena, _prog, _itens, _pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a", None,
                            mundos["M"])
    with pytest.raises(ErroELiXX, match="Alvo de síntese inválido"):
        MotionSynthesizer().sintetizar(plano, grafos["Rotas"], None)
    with pytest.raises(ErroELiXX, match="Alvo de síntese inválido"):
        MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "   ")


def test_nomes_maliciosos_sao_dados():
    sint = MotionSynthesizer(velocidades={"__import__('os')": 10.0})
    assert "__import__('os')" in sint.velocidades
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="eval(x)")]
    with pytest.raises(ErroELiXX, match="não suportado"):
        sint.sintetizar(plano, grafos["Rotas"], "Heroi")
    import elixx.visual.sintese_movimento as modulo
    import inspect

    fonte = inspect.getsource(modulo)
    assert "eval(" not in fonte.replace("sem eval", "")
    assert "exec(" not in fonte


def test_parametros_invalidos_erro_pt():
    with pytest.raises(ErroELiXX, match="Velocidade inválida"):
        MotionSynthesizer(velocidades={"andar": -5})
    with pytest.raises(ErroELiXX, match="Altura de pulo inválida"):
        MotionSynthesizer(altura_pulo=-1)
    with pytest.raises(ErroELiXX, match="Curva de síntese inválida"):
        MotionSynthesizer(curva="voar_para_longe")
    with pytest.raises(ErroELiXX, match="Duração de rotação inválida"):
        MotionSynthesizer(duracao_rotacao_ms=-1)
    with pytest.raises(ErroELiXX, match="Amplitude de pairar inválida"):
        MotionSynthesizer(amplitude_pairar=-2)


# ----- determinismo, destino exato, duração, velocidade -----

def test_determinismo():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "plat_alta",
                            pers["Heroi"], mundos["M"])
    mp1 = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    mp2 = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    assert [s.duracao_ms for s in mp1.steps] == [s.duracao_ms for s in
                                                 mp2.steps]
    assert [(s.waypoint_final.x, s.waypoint_final.y) for s in mp1.steps] == [
        (s.waypoint_final.x, s.waypoint_final.y) for s in mp2.steps]


def test_destino_exato_todos_modos():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    for modo in ["andar", "correr", "pular", "escalar", "descer", "voar",
                 "pairar", "teleportar"]:
        plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                                pers["Heroi"], mundos["M"])
        plano.etapas = [dict(plano.etapas[0], modo=modo, requisitos=[])]
        mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"],
                                            "Heroi")
        motor = MotorAnimacoes(_ex)
        mp.executar(motor, cena)
        cena.buscar("Heroi").x = 100.0
        cena.buscar("Heroi").y = 500.0
        for nome in list(motor.execucoes):
            motor.iniciar(nome)
        executar_ate_fim(motor)
        no = cena.buscar("Heroi")
        assert (no.x, no.y) == (0.0, 550.0), modo


def test_duracao_derivada_distancia_velocidade():
    _ex, _cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "plat_b", "plat_alta",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], modo="andar")]
    mp = MotionSynthesizer(velocidades={"andar": 200.0}).sintetizar(
        plano, grafos["Rotas"], "Heroi")
    dist = math_dist((900.0, 400.0), (1400.0, 150.0))
    assert mp.steps[0].duracao_ms == pytest.approx(dist / 200.0 * 1000.0)


def test_velocidade_zero_distancia_instantaneo():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "base",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [{"de": "ent:base", "para": "ent:base", "modo": "andar",
                     "requisitos": []}]
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    assert mp.steps[0].duracao_ms == 0.0
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (100.0, 550.0)


# ----- relativo, pose, debug, html -----

def test_sintese_relativa_reusa_f11():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], mundos["M"])
    plano.etapas = [dict(plano.etapas[0], relativo=True)]
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"], "Heroi")
    assert mp.steps[0].motion.relativo is True
    assert mp.steps[0].metadados["relativo"] is True
    assert mp.steps[0].motion.chaves[0].para == (-100.0, 0.0)
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    # relativo: desloca (-100, 0) a partir do atual (100, 500)
    assert (no.x, no.y) == (0.0, 500.0)


def test_pose_sugerida_sem_obrigar_f12():
    _ex, _cena, _prog, _itens, pers, _mundos, grafos = base()
    plano = plano_travessia(grafos["Rotas"], "base", "chao_a",
                            pers["Heroi"], _mundos["M"])
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rotas"],
                                        pers["Heroi"])
    assert mp.steps[0].pose_sugerida == "andar"
    assert mp.steps[0].metadados["pose_sugerida"] == "andar"
    assert pers["Heroi"].pose_atual is None


def test_debug_nao_executa():
    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "base", "plat_b", pers["Heroi"],
                         mundos["M"])
    texto = debug_sintese_movimento(mp)
    assert "MotionPlan base -> plat_b" in texto
    assert "andar" in texto and "pular" in texto
    assert "ori=" in texto and "req=" in texto
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (100.0, 500.0)  # nada se moveu
    vazio = MotionPlan(origem="a", destino="b", viavel=False,
                       motivo="X")
    assert "motivo: X" in debug_sintese_movimento(vazio)


def test_html_honesto():
    from elixx.visual.html import gerar_html

    _ex, cena, _prog, _itens, pers, mundos, grafos = base()
    mp = sintetizar_rota(grafos, "base", "chao_a", pers["Heroi"],
                         mundos["M"])
    motor = MotorAnimacoes(_ex)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    pagina = gerar_html(_ex.ctx.objetos)
    assert isinstance(pagina, str) and "T" in pagina


def test_exemplo_motion_synthesis():
    with open("exemplos/motion-synthesis.elixx", encoding="utf-8") as arq:
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
    plano = plano_travessia(grafos["Rota"], "inicio", "destino",
                            pers["Heroi"], mundos["Mundo"])
    mp = MotionSynthesizer().sintetizar(plano, grafos["Rota"],
                                        pers["Heroi"], pers["Heroi"],
                                        mundos["Mundo"])
    assert mp.viavel is True
    assert [s.modo for s in mp.steps] == ["andar", "pular", "voar",
                                          "andar"]
    motor = MotorAnimacoes(executor)
    mp.executar(motor, cena)
    executar_ate_fim(motor)
    no = cena.buscar("Heroi")
    assert (no.x, no.y) == (650.0, 250.0)


# ----- Tk visual real -----

def test_tk_rota_completa():
    try:
        from elixx.visual.tk import RenderizadorTk
    except ImportError:
        pytest.skip("Tk indisponível")
    try:
        _ex, cena, prog = montar(
            'janela p {\n titulo: "T"\n tamanho: 800px 600px\n'
            ' personagem Heroi {\n  posição: 50px 500px\n'
            '  parte corpo {\n  }\n }\n'
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
        plano = plano_travessia(grafos["R"], "A", "D", heroi, mundos["M"])
        mp = MotionSynthesizer().sintetizar(plano, grafos["R"], heroi,
                                            heroi, mundos["M"])
        assert [s.modo for s in mp.steps] == ["andar", "pular", "voar"]
        motor = MotorAnimacoes(_ex)
        rend = RenderizadorTk(_ex)
        try:
            rend.montar(cena)
            rend.raiz.withdraw()
            mp.executar(motor, cena)
            no = cena.buscar("Heroi")
            vistos = set()
            for _ in range(400):
                motor.atualizar(50)
                rend.atualizar(16.0)
                rend.raiz.update()
                vistos.add((round(no.x, 1), round(no.y, 1)))
                estados = [e.estado for e in motor.execucoes.values()]
                if estados and all(e == "concluida" for e in estados):
                    break
            # passou pelos waypoints e pousou exato no destino
            assert (250.0, 500.0) in vistos
            assert (no.x, no.y) == (650.0, 300.0)
            assert no.rotacao == pytest.approx(0.0)  # último: para direita
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
        etapas = [{"de": f"n{i}", "para": f"n{i + 1}", "modo": "andar",
                   "requisitos": []} for i in range(total)]
        # converte etapas F15: usa o plano direto
        from elixx.visual.navegacao import TraversalPlan

        travessia = TraversalPlan(origem="n0", destino=f"n{total}",
                                  etapas=etapas)
        inicio = time.perf_counter()
        mp = MotionSynthesizer().sintetizar(travessia, grafo, "alvo")
        meio = time.perf_counter()
        assert len(mp.steps) == total
        motor = MotorAnimacoes(_ex)
        mp.executar(motor, cena)
        ticks = 0
        inicio_tick = time.perf_counter()
        for _ in range(5000):
            motor.atualizar(16)
            ticks += 1
            if all(e.estado == "concluida"
                   for e in motor.execucoes.values()):
                break
        fim = time.perf_counter()
        assert (no.x, no.y) == (float(total * 10), 0.0)
        sintese_ms = (meio - inicio) * 1000.0
        tick_ms = (fim - inicio_tick) * 1000.0 / max(ticks, 1)
        assert sintese_ms < 30000 and tick_ms < 1000
