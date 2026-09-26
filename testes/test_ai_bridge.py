"""Testes da Fase 18 — AI Bridge (determinísticos, sem LLM)."""
import pytest

from elixx.animacao.motor import MotorAnimacoes
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX
from elixx.runtime.nucleo import Executor
from elixx.visual.ai_bridge import (
    AIIntent,
    AIPlan,
    AIPlannerBridge,
    AIProvider,
    IntentValidator,
    texto_para_intencao,
)
from elixx.visual.capacidades import obter_instancia, vincular_itens
from elixx.visual.cena import ConstrutorCena
from elixx.visual.mundo import vincular_mundos
from elixx.visual.navegacao import vincular_navegacao
from elixx.visual.personagem import vincular_personagens


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
    grafos = vincular_navegacao(cena, prog, mundos)
    return ex, cena, prog, itens, pers, mundos, grafos


FONTE = ('janela p {\n titulo: "T"\n'
         ' personagem Heroi {\n  posição: 100px 500px\n'
         '  parte corpo {\n  }\n'
         '  parte braco {\n   posição: 20px 0px\n  }\n'
         '  parte cabeca {\n   posição: 20px 30px\n  }\n'
         '  capacidade andar\n  capacidade pular\n'
         '  pose repouso {\n   braco:\n    rotação: 0deg\n'
         '   cabeca:\n    rotação: 0deg\n  }\n'
         '  pose andar {\n   braco:\n    rotação: 20deg\n  }\n'
         '  expressao feliz {\n   cabeca:\n    rotação: 10deg\n  }\n'
         '  expressao neutra {\n   cabeca:\n    rotação: 0deg\n  }\n'
         ' }\n'
         ' item BotaFoguete {\n  categoria: "equipamento"\n'
         '  capacidade voar\n }\n'
         ' item Corda {\n  categoria: "ferramenta"\n'
         '  capacidade descer\n }\n'
         ' mundo M {\n  tamanho: 2000px 1200px\n'
         '  chão chao_a {\n   posição: 0px 550px\n   tamanho: 800px 50px\n  }\n'
         '  plataforma plat_b {\n   posição: 900px 400px\n'
         '   tamanho: 300px 30px\n  }\n'
         '  plataforma plat_alta {\n   posição: 1400px 150px\n'
         '   tamanho: 200px 30px\n  }\n'
         '  parede muro {\n   posição: 100px 100px\n   tamanho: 40px 80px\n  }\n'
         '  obstáculo rocha {\n   posição: 560px 410px\n'
         '   tamanho: 60px 20px\n  }\n'
         '  ponto Torre {\n   posição: 1500px 165px\n  }\n'
         '  ponto saida {\n   posição: 1500px 165px\n  }\n'
         '  ponto base {\n   posição: 100px 550px\n  }\n'
         '  ponto ilha {\n   posição: 1900px 1100px\n  }\n'
         '  usar personagem Heroi\n  usar item BotaFoguete\n'
         '  usar item Corda\n'
         ' }\n'
         ' navegacao Rotas {\n'
         '  caminho Heroi -> base {\n   modo: andar\n  }\n'
         '  caminho base -> chao_a {\n   modo: andar\n  }\n'
         '  caminho chao_a -> plat_b {\n   modo: pular\n   custo: 2\n  }\n'
         '  caminho plat_b -> plat_alta {\n   modo: voar\n   custo: 4\n'
         '   requer: voar\n  }\n'
         '  caminho plat_b_borda_direita -> saida {\n   modo: andar\n  }\n'
         '  caminho plat_alta -> saida {\n   modo: andar\n   custo: 100\n  }\n'
         '  caminho plat_alta -> Torre {\n   modo: andar\n  }\n'
         ' }\n}\n')


def base():
    ex, cena, prog, itens, pers, mundos, grafos = vinculo(FONTE)
    ponte = AIPlannerBridge(cena, pers, mundos, grafos, itens)
    return ex, cena, prog, itens, pers, mundos, grafos, ponte


def test_intencao_valida():
    _ex, _cena, _prog, _itens, pers, mundos, grafos, ponte = base()
    plano = ponte.planear = ponte.planejar({
        "tipo": "mover", "personagem": "Heroi", "destino": "plat_b",
        "modo": "andar", "pose": "andar", "expressao": "feliz",
    })
    assert isinstance(plano, AIPlan)
    assert plano.viavel is True
    assert plano.executavel is True
    assert plano.validacao["codigo"] == "ok"
    assert plano.behavior_plan is not None
    assert plano.motion_plan is not None
    assert plano.traversal_plan is not None


def test_intencao_invalida_tipo():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "dancar", "personagem": "Heroi",
                            "destino": "plat_b"})
    assert plano.viavel is False
    assert plano.validacao["codigo"] == "tipo_desconhecido"
    assert plano.executavel is False


def test_personagem_inexistente():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Fantasma",
                            "destino": "plat_b"})
    assert plano.viavel is False
    assert plano.validacao["codigo"] == "personagem_inexistente"


def test_destino_inexistente():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "Atlantida"})
    assert plano.viavel is False
    assert plano.validacao["codigo"] == "destino_inexistente"


def test_modo_invalido():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b", "modo": "nadar"})
    assert plano.viavel is False
    assert plano.validacao["codigo"] == "modo_invalido"


def test_capability_presente_e_ausente():
    ex, cena, _prog, itens, pers, mundos, grafos, ponte = base()
    heroi = pers["Heroi"]
    heroi.inventario.possuir(obter_instancia(itens, "BotaFoguete"))
    heroi.inventario.equipar("BotaFoguete")
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_alta", "modo": "voar"})
    assert plano.viavel is True
    assert plano.executavel is True
    motor = MotorAnimacoes(ex)
    res = ponte.executar(plano, motor)
    assert res["sucesso"] is True
    for _ in range(2000):
        motor.atualizar(50)
        estados = [e.estado for e in motor.execucoes.values()]
        if estados and all(e == "concluida" for e in estados):
            break
    no = cena.buscar("Heroi")
    assert (round(no.x, 1), round(no.y, 1)) == (1400.0, 150.0)


def test_capability_ausente_inviavel():
    _ex, _cena, _prog, _itens, pers, mundos, grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_alta", "modo": "voar"})
    assert plano.viavel is False
    assert "voar" in plano.motivo
    assert plano.executavel is False
    assert plano.behavior_plan is None


def test_rota_inexistente_estruturada():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "ilha"})
    assert plano.viavel is False
    assert plano.executavel is False
    assert isinstance(plano.motivo, str) and plano.motivo


def test_multiplas_rotas_requer_escolha():
    ex, cena, _prog, itens, pers, mundos, grafos, ponte = base()
    heroi = pers["Heroi"]
    heroi.inventario.possuir(obter_instancia(itens, "BotaFoguete"))
    heroi.inventario.equipar("BotaFoguete")
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "saida"})
    assert plano.viavel is True
    assert plano.requer_escolha is True
    assert len(plano.rotas) >= 2
    assert plano.behavior_plan is None
    resumo = plano.resumo_rotas()
    assert all(set(r) >= {"nos", "modos", "custo_total", "requisitos"}
               for r in resumo)
    res = ponte.executar(plano, MotorAnimacoes(ex))
    assert res["sucesso"] is False
    assert res["codigo"] == "plano_inviavel"


def test_dry_run_nao_move():
    ex, cena, _prog, _itens, pers, mundos, grafos, ponte = base()
    no = cena.buscar("Heroi")
    antes = (no.x, no.y)
    plano = ponte.simular({"tipo": "mover", "personagem": "Heroi",
                           "destino": "plat_b"})
    assert plano.viavel is True
    assert (no.x, no.y) == antes
    plano2 = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                             "destino": "plat_b"})
    assert (no.x, no.y) == antes
    assert plano2.behavior_plan is not None


def test_plano_executavel_campos():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "ir", "personagem": "Heroi",
                            "destino": "plat_b"})
    assert plano.viavel and plano.executavel and plano.suportado
    assert plano.traversal_plan is not None
    assert plano.motion_plan is not None
    assert plano.behavior_plan is not None
    assert isinstance(plano.requisitos, list)
    assert isinstance(plano.avisos, list)
    assert isinstance(plano.eventos, list) and plano.eventos


def test_execucao_move_personagem():
    ex, cena, _prog, _itens, pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b"})
    motor = MotorAnimacoes(ex)
    res = ponte.executar(plano, motor)
    assert res["sucesso"] is True
    assert res["iniciados"]
    for _ in range(2000):
        motor.atualizar(50)
        estados = [e.estado for e in motor.execucoes.values()]
        if estados and all(e == "concluida" for e in estados):
            break
    no = cena.buscar("Heroi")
    assert (round(no.x, 1), round(no.y, 1)) == (900.0, 400.0)


def test_cancelamento():
    ex, cena, _prog, _itens, pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b"})
    motor = MotorAnimacoes(ex)
    res = ponte.executar(plano, motor)
    assert res["sucesso"] is True
    motor.atualizar(50)
    out = ponte.cancelar(motor, res["iniciados"])
    assert out["sucesso"] is True
    assert out["cancelados"]
    for nome in out["cancelados"]:
        assert motor.execucoes[nome].estado == "cancelada"


def test_resultado_estruturado():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "olhar", "personagem": "Heroi"})
    assert plano.suportado is False
    assert plano.viavel is False
    res = ponte.executar(plano, MotorAnimacoes(_ex))
    assert set(res) >= {"sucesso", "codigo", "motivo", "iniciados"}
    assert res["sucesso"] is False


def test_contexto_estrutura():
    _ex, _cena, _prog, _itens, pers, mundos, grafos, ponte = base()
    ctx = ponte.contexto("Heroi", destino="Torre")
    assert ctx["personagem"] == "Heroi"
    assert ctx["posicao"] == {"x": 100.0, "y": 500.0}
    assert "andar" in ctx["capacidades"] and "pular" in ctx["capacidades"]
    assert isinstance(ctx["equipados"], list)
    assert any(d["nome"] == "Torre" for d in ctx["destinos"])
    assert any(d["nome"] == "saida" for d in ctx["destinos"])
    assert ctx["rotas_possiveis"] == []  # sem voar: nada viável até Torre
    pers["Heroi"].inventario.possuir(obter_instancia(_itens, "BotaFoguete"))
    pers["Heroi"].inventario.equipar("BotaFoguete")
    ctx2 = ponte.contexto("Heroi", destino="Torre")
    assert ctx2["rotas_possiveis"]
    assert ctx2["rotas_possiveis"][0]["nos"][-1] == "ent:Torre"
    assert isinstance(ctx["entidades_proximas"], list)
    assert ctx["estado"]["personagem"] == "Heroi"
    with pytest.raises(ErroELiXX):
        ponte.contexto("Fantasma")


def test_world_snapshot_usado():
    _ex, _cena, _prog, _itens, _pers, mundos, _grafos, ponte = base()
    ctx = ponte.contexto("Heroi")
    assert ctx["mundo"] == "M"
    snap = mundos["M"].snapshot()
    assert snap.por_id("Heroi").x == 100.0


def test_nomes_maliciosos_inertes():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    for campo in ("personagem", "destino", "modo", "pose"):
        dados = {"tipo": "mover", "personagem": "Heroi",
                 "destino": "plat_b", campo: "__import__('os')"}
        plano = ponte.planejar(dados)
        assert plano.viavel is False
    plano = ponte.planejar({"tipo": "eval('x')", "personagem": "Heroi",
                            "destino": "plat_b"})
    assert plano.viavel is False
    assert plano.validacao["codigo"] == "tipo_desconhecido"


def test_sem_eval_exec_import():
    import inspect

    import elixx.visual.ai_bridge as modulo

    fonte = inspect.getsource(modulo)
    assert "eval(" not in fonte
    assert "exec(" not in fonte
    assert "__import__" not in fonte
    assert "importlib" not in fonte
    assert "subprocess" not in fonte
    assert "compile(" not in fonte


def test_determinismo():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    dados = {"tipo": "mover", "personagem": "Heroi", "destino": "plat_b",
             "pose": "andar", "expressao": "feliz"}
    a = ponte.debug_ai_plan(ponte.planejar(dados))
    b = ponte.debug_ai_plan(ponte.planejar(dados))
    assert a == b


def test_planejamento_nao_move_personagem():
    _ex, cena, _prog, _itens, pers, mundos, grafos, ponte = base()
    no = cena.buscar("Heroi")
    antes = (no.x, no.y)
    for _ in range(5):
        ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                        "destino": "plat_b"})
    assert (no.x, no.y) == antes
    assert pers["Heroi"].pose_atual is None


def test_execucao_move_personagem():
    ex, cena, _prog, _itens, pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b", "pose": "andar",
                            "expressao": "feliz"})
    motor = MotorAnimacoes(ex)
    ponte.executar(plano, motor)
    for _ in range(2000):
        motor.atualizar(50)
        estados = [e.estado for e in motor.execucoes.values()]
        if estados and all(e == "concluida" for e in estados):
            break
    no = cena.buscar("Heroi")
    assert (round(no.x, 1), round(no.y, 1)) == (900.0, 400.0)


def test_f15_f16_f17_integrados():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b"})
    assert plano.traversal_plan is not None
    assert plano.motion_plan is not None
    assert plano.behavior_plan is not None
    assert len(plano.behavior_plan.steps) > 0
    assert plano.behavior_plan.viavel is True


def test_json_e_dict():
    intent = AIIntent.from_json(
        '{"tipo": "mover", "personagem": "Heroi", "destino": "plat_b"}')
    assert intent.tipo == "mover" and intent.destino == "plat_b"
    assert AIIntent.from_dict(intent.to_dict()).to_dict() == intent.to_dict()
    with pytest.raises(ErroELiXX):
        AIIntent.from_json("{invalido")
    with pytest.raises(ErroELiXX):
        AIIntent.from_dict(["mover"])
    with pytest.raises(ErroELiXX):
        AIIntent.from_dict({"tipo": "mover", "hack": 1})
    with pytest.raises(ErroELiXX):
        AIIntent.from_dict({"tipo": "mover", "destino": {"x": 1}})
    with pytest.raises(ErroELiXX):
        AIIntent.from_dict({"tipo": "", "destino": "x"})
    with pytest.raises(ErroELiXX):
        AIIntent.from_dict({"tipo": "mover", "modo": 42,
                            "destino": "x"})


def test_provider_neutro_e_fronteira_texto():
    base = AIProvider()
    assert base.nome == "externo"
    with pytest.raises(NotImplementedError):
        base.gerar_intencao({})
    with pytest.raises(ErroELiXX, match="não implementada"):
        texto_para_intencao("Vá até a torre.")


def test_debug_ai_plan_conteudo():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b", "modo": "andar"})
    texto = ponte.debug_ai_plan(plano)
    for trecho in ("INTENÇÃO", "Heroi", "ROTA", "MOVIMENTO", "COMPORTAMENTO",
                   "EXECUTÁVEL", "sim", "VALIDAÇÃO", "REQUISITOS"):
        assert trecho in texto


def test_eventos_registrados():
    _ex, _cena, _prog, _itens, _pers, _mundos, _grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b"})
    nomes = [e["evento"] for e in plano.eventos]
    assert nomes[:2] == ["ai_plano_criado", "ai_plano_validado"]
    motor = MotorAnimacoes(_ex)
    ponte.executar(plano, motor)
    assert plano.eventos[-1] == {"evento": "ai_execucao_iniciada"}
    ruim = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                           "destino": "ilha"})
    assert ruim.eventos[-1] == {"evento": "ai_plano_rejeitado"}
    ponte.executar(ruim, motor)
    assert ruim.eventos[-1] == {"evento": "ai_execucao_falhou"}


def test_pose_expressao_aplicadas():
    ex, cena, _prog, _itens, pers, mundos, grafos, ponte = base()
    plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                            "destino": "plat_b", "pose": "andar",
                            "expressao": "feliz"})
    assert plano.viavel is True
    motor = MotorAnimacoes(ex)
    ponte.executar(plano, motor)
    motor.atualizar(10)
    assert cena.buscar("braco").rotacao == pytest.approx(20.0)
    assert cena.buscar("cabeca").rotacao == pytest.approx(10.0)


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
            '  expressao feliz {\n   cabeca:\n    rotação: 10deg\n  }\n'
            ' }\n'
            ' mundo M {\n  tamanho: 2000px 1200px\n'
            '  ponto A {\n   posição: 50px 500px\n  }\n'
            '  ponto B {\n   posição: 250px 500px\n  }\n'
            '  ponto C {\n   posição: 450px 300px\n  }\n'
            '  ponto D {\n   posição: 650px 300px\n  }\n'
            '  usar personagem Heroi\n }\n'
            ' navegacao R {\n'
            '  caminho Heroi -> A {\n   modo: andar\n  }\n'
            '  caminho A -> B {\n   modo: andar\n  }\n'
            '  caminho B -> C {\n   modo: pular\n  }\n'
            '  caminho C -> D {\n   modo: voar\n  }\n'
            ' }\n}\n')
        itens = vincular_itens(prog)
        pers = vincular_personagens(cena, itens)
        mundos = vincular_mundos(cena, prog, pers, itens)
        from elixx.visual.navegacao import vincular_navegacao

        grafos = vincular_navegacao(cena, prog, mundos)
        ponte = AIPlannerBridge(cena, pers, mundos, grafos, itens)
        plano = ponte.planejar({"tipo": "mover", "personagem": "Heroi",
                                "destino": "D", "pose": "andar",
                                "expressao": "feliz"})
        assert plano.viavel is True
        motor = MotorAnimacoes(_ex)
        rend = RenderizadorTk(_ex)
        try:
            rend.montar(cena)
            rend.raiz.withdraw()
            res = ponte.executar(plano, motor)
            assert res["sucesso"] is True
            no = cena.buscar("Heroi")
            for _ in range(600):
                motor.atualizar(50)
                rend.atualizar(16.0)
                rend.raiz.update()
                estados = [e.estado for e in motor.execucoes.values()]
                if estados and all(e == "concluida" for e in estados):
                    break
            assert (no.x, no.y) == (650.0, 300.0)
        finally:
            rend.fechar()
    except Exception as exc:
        import tkinter as _tk

        if isinstance(exc, _tk.TclError):
            pytest.skip(f"sem display: {exc}")
        raise


def test_stress_planejamento():
    import time

    _ex, cena, prog, itens, pers, mundos, grafos, ponte = base()
    tempos = {"validacao": 0.0, "planejamento": 0.0, "sintese": 0.0}
    for total in (10, 100, 500, 1000):
        dados = {"tipo": "mover", "personagem": "Heroi",
                 "destino": "plat_b"}
        t0 = time.perf_counter()
        for _ in range(total):
            intent = AIIntent.from_dict(dados)
            ponte.validador.validar(intent, pers, mundos, grafos)
        t1 = time.perf_counter()
        planos = [ponte.planejar(dados) for _ in range(total)]
        t2 = time.perf_counter()
        assert all(p.viavel for p in planos)
        assert all(p.behavior_plan is not None for p in planos)
        tempos = {"validacao": (t1 - t0) * 1000.0 / total,
                  "planejamento": (t2 - t1) * 1000.0 / total,
                  "sintese": 0.0}
    assert tempos["validacao"] < 100.0
    assert tempos["planejamento"] < 1000.0


def test_exemplo_ai_bridge():
    with open("exemplos/ai-bridge.elixx", encoding="utf-8") as arq:
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
    assert "Mundo" in mundos and "Heroi" in pers and "Rotas" in grafos
