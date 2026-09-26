"""Testes da Fase 12 — Character/Puppet Core (determinísticos)."""
import pytest

from elixx.animacao.motion import MotionGroup
from elixx.animacao.motor import MotorAnimacoes, definicao_de_ast
from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroSemantico, ErroSintatico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.personagem import (
    Character,
    CharacterPart,
    Gesture,
    Joint,
    ManualAnalyzer,
    Pose,
    vincular_personagens,
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


HEROI = ('janela p {\n titulo: "T"\n personagem Heroi {\n'
         '  posição: 100px 100px\n'
         '  parte corpo {\n   imagem: "corpo.png"\n  }\n'
         '  parte cabeca {\n   posição: 20px 0px\n   pivô: 50% 100%\n  }\n'
         '  parte braco {\n   posição: 20px 0px\n   pivô: 10px 20px\n'
         '   junta: "ombro"\n   limite_min: 0deg\n   limite_max: 90deg\n'
         '   parte antebraco {\n    posição: 30px 0px\n'
         '    parte mao {\n     posição: 10px 0px\n    }\n   }\n  }\n'
         '  pose repouso {\n   braco:\n    rotação: 0deg\n'
         '   cabeca:\n    rotação: 0deg\n  }\n'
         '  pose acenando {\n   braco:\n    rotação: 45deg\n'
         '   antebraco:\n    rotação: 60deg\n  }\n'
         '  expressao sorriso {\n   cabeca:\n    rotação: 5deg\n  }\n'
         ' }\n}\n')


def heroi():
    _ex, cena, _prog = montar(HEROI)
    return _ex, vincular_personagens(cena)["Heroi"], cena


# ----- 1-5: básico, root, parte, aninhadas, identidade -----

def test_character_basico():
    _ex, h, _cena = heroi()
    assert isinstance(h, Character)
    assert h.nome == "Heroi"
    assert h.no_raiz.tipo == "personagem"


def test_root_controla_tudo():
    _ex, h, _cena = heroi()
    assert (h.no_raiz.x, h.no_raiz.y) == (100.0, 100.0)


def test_parte_e_no_visual():
    _ex, h, _cena = heroi()
    braco = h.obter_parte("braco")
    assert isinstance(braco, CharacterPart)
    assert braco.no.tipo == "parte"
    assert braco.no.x == 20.0


def test_partes_aninhadas():
    _ex, h, _cena = heroi()
    mao = h.obter_parte("mao")
    assert mao.pai.nome == "antebraco"
    assert mao.pai.pai.nome == "braco"
    assert [c.nome for c in h.obter_parte("braco").filhos] == ["antebraco"]


def test_identidade_estavel_e_erro_claro():
    _ex, h, _cena = heroi()
    assert h.obter_parte("mao").nome == "mao"
    h.aplicar_pose("acenando")
    assert h.obter_parte("mao").nome == "mao"
    with pytest.raises(ErroELiXX, match="não encontrada"):
        h.obter_parte("asa")


# ----- 6-8: transform local/global, pivô, joint -----

def test_transform_local():
    _ex, h, _cena = heroi()
    local = h.obter_parte("braco").transform_local()
    assert (local.x, local.y, local.rotacao) == (20.0, 0.0, 0.0)


def test_transform_global_cadeia():
    _ex, h, _cena = heroi()
    g = h.obter_transform_global("mao")
    assert (g.x, g.y) == (160.0, 100.0)  # 100+20+30+10
    h.no_raiz.x = 0.0
    h.no_raiz.y = 0.0
    cena2 = _cena
    g2 = h.obter_transform_global("mao")
    assert (g2.x, g2.y) == (60.0, 0.0)
    assert cena2 is not None


def test_transform_global_com_rotacao():
    _ex, h, cena = heroi()
    cena.buscar("braco").rotacao = 90.0
    g = h.obter_transform_global("mao")
    # braço a 90° com pivô (10px,20px): cadeia exata do motor
    assert (g.x, g.y) == pytest.approx((150.0, 150.0))


def test_pivo_usa_f10():
    _ex, h, _cena = heroi()
    cabeca = h.obter_parte("cabeca")
    assert (cabeca.no.pivo_x, cabeca.no.pivo_unidade_x) == (50.0, "%")
    assert (cabeca.no.pivo_y, cabeca.no.pivo_unidade_y) == (100.0, "%")
    braco = h.obter_parte("braco")
    assert (braco.no.pivo_x, braco.no.pivo_unidade_x) == (10.0, "px")


def test_joint_metadados():
    _ex, h, _cena = heroi()
    junta = h.obter_parte("braco").junta
    assert isinstance(junta, Joint)
    assert junta.nome == "ombro"
    assert h.obter_parte("corpo").junta is None


# ----- 10-11: limites -----

def test_limites_clamp_previsivel():
    _ex, h, cena = heroi()
    h.aplicar_pose("acenando")
    assert cena.buscar("braco").rotacao == 45.0
    # 120° além do máximo 90° → clamp (não erro, não volta completa)
    h.aplicar_pose(Pose(nome="x", entradas={"braco": {"rotacao": 120.0}}))
    assert cena.buscar("braco").rotacao == 90.0
    h.aplicar_pose(Pose(nome="y", entradas={"braco": {"rotacao": -30.0}}))
    assert cena.buscar("braco").rotacao == 0.0


def test_limites_invalidos_erro():
    with pytest.raises(ErroSemantico, match="limite_min"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n personagem H {\n'
            '  parte b {\n   limite_min: 90deg\n   limite_max: 0deg\n  }\n'
            ' }\n}\n'))


def test_joint_api():
    j = Joint(nome="c", parte="b", minimo=0.0, maximo=90.0)
    assert j.dentro_limites(45.0) and not j.dentro_limites(120.0)
    assert j.aplicar_limite(120.0) == 90.0
    assert Joint(nome="livre", parte="b").dentro_limites(720.0)


# ----- 11-12: hierarquia segue, ciclo impossível -----

def test_hierarquia_acompanha():
    _ex, h, cena = heroi()
    cena.buscar("braco").rotacao = 45.0
    antes = h.obter_transform_global("mao")
    cena.buscar("antebraco").rotacao = 30.0
    depois = h.obter_transform_global("mao")
    assert (antes.x, antes.y) != (depois.x, depois.y)


def test_sem_ciclo_arvore():
    _ex, h, _cena = heroi()
    vistos = set()

    def visitar(parte):
        assert parte.nome not in vistos
        vistos.add(parte.nome)
        for filho in parte.filhos:
            visitar(filho)

    for parte in h.partes.values():
        if parte.pai is None:
            visitar(parte)
    assert vistos == {"corpo", "cabeca", "braco", "antebraco", "mao"}


def test_nomes_duplicados_e_colisao():
    with pytest.raises(ErroSemantico, match="repetida"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n personagem H {\n'
            '  parte b {\n  }\n  parte b {\n  }\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="colide"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n texto b {\n  texto: "x"\n }\n'
            ' personagem H {\n  parte b {\n  }\n }\n}\n'))


# ----- 13-17: poses -----

def test_pose_dado():
    _ex, h, _cena = heroi()
    pose = h.obter_pose("acenando")
    assert pose.entradas["braco"]["rotacao"] == 45.0
    assert "cabeca" not in pose.entradas  # parcial


def test_pose_parcial_preserva_resto():
    _ex, h, cena = heroi()
    cena.buscar("cabeca").rotacao = 12.0
    h.aplicar_pose("acenando")
    assert cena.buscar("braco").rotacao == 45.0
    assert cena.buscar("cabeca").rotacao == 12.0
    assert h.pose_atual == "acenando"


def test_pose_invalida_erro_claro():
    with pytest.raises(ErroSemantico, match="não encontrada"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n personagem H {\n'
            '  parte b {\n  }\n  pose p {\n   fantasma:\n    rotação: 1deg\n'
            '  }\n }\n}\n'))
    _ex, h, _cena = heroi()
    with pytest.raises(ErroELiXX, match="não encontrada"):
        h.obter_pose("voar")
    with pytest.raises(ErroELiXX, match="não encontrada"):
        h.aplicar_pose("voar")


def test_aplicacao_pose_posicao_escala_opacidade():
    _ex, h, cena = heroi()
    h.aplicar_pose(Pose(nome="t", entradas={
        "braco": {"posicao": (1.0, 2.0), "escala": 2.0, "opacidade": 0.5}}))
    no = cena.buscar("braco")
    assert (no.x, no.y) == (1.0, 2.0)
    assert (no.escala_x, no.escala_y) == (2.0, 2.0)
    assert no.opacidade == 0.5


def test_transicao_pose_gera_motion():
    _ex, h, cena = heroi()
    defs = h.transicionar_pose("acenando", duracao_ms=1000.0)
    assert len(defs) == 2  # braco.rot + antebraco.rot
    alvos = {d.alvo for d in defs}
    assert alvos == {"braco", "antebraco"}
    motor = MotorAnimacoes(_ex)
    motor.carregar(defs, cena)
    motor.iniciar_automaticas()
    motor.atualizar(1000)
    assert cena.buscar("braco").rotacao == pytest.approx(45.0)
    assert cena.buscar("antebraco").rotacao == pytest.approx(60.0)


# ----- 18-25: motion, gesto, repetição -----

def test_motion_por_parte():
    _ex, h, cena = heroi()
    defs = h.transicionar_pose("acenando", duracao_ms=500.0,
                               movimento="linear")
    motor = MotorAnimacoes(_ex)
    motor.carregar(defs, cena)
    motor.iniciar_automaticas()
    motor.atualizar(250)
    assert cena.buscar("braco").rotacao == pytest.approx(22.5)


def test_motion_no_root():
    ex, cena, prog = montar(
        'janela p {\n titulo: "T"\n personagem H {\n'
        '  posição: 0px 0px\n  parte b {\n  }\n }\n'
        ' animação anda {\n  alvo: H\n  posição: 0px 0px -> 500px 0px\n'
        '  movimento: linear\n  duração: 1000ms\n }\n}\n')
    h = vincular_personagens(cena)["H"]
    motor = MotorAnimacoes(ex)
    motor.carregar([definicao_de_ast(a)
                    for a in prog.janelas[0].animacoes], cena)
    motor.iniciar_automaticas()
    motor.atualizar(500)
    assert (h.no_raiz.x, h.no_raiz.y) == (250.0, 0.0)


def test_motion_root_mais_parte():
    _ex, h, cena = heroi()
    defs = h.transicionar_pose("acenando", duracao_ms=1000.0)
    motor = MotorAnimacoes(_ex)
    motor.carregar(defs, cena)
    for d in motor.execucoes.values():
        d.definicao.duracao_ms = 1000.0
    motor.iniciar_automaticas()
    h.no_raiz.x = 200.0  # root move junto, sem quebrar a parte
    motor.atualizar(1000)
    g = h.obter_transform_global("mao")
    # cadeia com braço 45° + antebraço 60° sob root (200,100)
    assert (g.x, g.y) == pytest.approx((255.70, 129.66), abs=0.02)


def test_gesto_sequencial():
    _ex, h, cena = heroi()
    motor = MotorAnimacoes(_ex)
    motor.carregar([], cena)
    gesto = Gesture(nome="acenar", passos=["acenando", "repouso"],
                    modo="sequencia")
    grupo = h.executar_gesto(gesto, motor)
    assert isinstance(grupo, MotionGroup)
    assert grupo.modo == "sequencia"
    motor.atualizar(500)
    motor.atualizar(500)
    assert h.pose_atual == "repouso"  # intenção do último passo
    assert grupo.estado() == "concluida"


def test_gesto_paralelo_e_repeticao():
    _ex, h, cena = heroi()
    motor = MotorAnimacoes(_ex)
    motor.carregar([], cena)
    gesto = Gesture(nome="duplo", passos=["acenando", "sorriso"],
                    modo="paralelo", repetir=2)
    grupo = h.executar_gesto(gesto, motor)
    assert grupo.modo == "paralelo"
    for _ in range(4):
        motor.atualizar(500)
    assert grupo.estado() == "concluida"
    assert h.gesto_atual == "duplo"


# ----- 26-29: expressões e composição -----

def test_expressao_parcial():
    _ex, h, cena = heroi()
    tocadas = h.aplicar_pose("sorriso")
    assert tocadas == ["cabeca"]
    assert cena.buscar("cabeca").rotacao == 5.0
    assert h.poses["sorriso"].expressao is True


def test_expressao_parcial_composta():
    _ex, h, cena = heroi()
    tocadas = h.aplicar_pose("acenando", poses_extras=["sorriso"])
    assert sorted(tocadas) == ["antebraco", "braco", "cabeca"]
    assert cena.buscar("cabeca").rotacao == 5.0


def test_composicao_poses_ultima_vence():
    p1 = Pose(nome="a", entradas={"b": {"rotacao": 10.0}})
    p2 = Pose(nome="b", entradas={"b": {"rotacao": 20.0},
                                  "c": {"rotacao": 5.0}})
    fundida = p1.combinar(p2)
    assert fundida.entradas["b"]["rotacao"] == 20.0
    assert fundida.entradas["c"]["rotacao"] == 5.0


def test_conflito_pose_duplicada_erro():
    with pytest.raises(ErroSemantico, match="repetido"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n personagem H {\n'
            '  parte b {\n  }\n  pose p {\n   b:\n    rotação: 1deg\n'
            '    rotação: 2deg\n  }\n }\n}\n'))


# ----- 30-33: direção e representações -----

def test_direcao_fundacao():
    _ex, h, _cena = heroi()
    assert h.direcao == "frente"
    assert h.definir_direcao("direita") is None
    assert h.direcao == "direita"
    with pytest.raises(ErroELiXX):
        h.definir_direcao("nordeste")


def test_representacao_frontal_lateral():
    ex, cena, _prog = montar(
        'janela p {\n titulo: "T"\n personagem H {\n'
        '  imagem: "frente.png"\n  frente: "frente.png"\n'
        '  esquerda: "esq.png"\n  parte b {\n  }\n }\n}\n')
    h = vincular_personagens(cena)["H"]
    assert h.representacoes == {"frente": "frente.png",
                                "esquerda": "esq.png"}
    assert h.definir_direcao("esquerda") == "esq.png"
    no = cena.buscar("H")
    assert no.caminho_recurso == "frente.png"


def test_troca_representacao_estado():
    ex, cena, _prog = montar(
        'janela p {\n titulo: "T"\n personagem H {\n'
        '  direcao: "esquerda"\n  frente: "f.png"\n  esquerda: "e.png"\n'
        '  parte olho {\n   asset_fechado: "olho-f.png"\n  }\n }\n}\n')
    h = vincular_personagens(cena)["H"]
    assert h.direcao == "esquerda"
    assert h.definir_variante("olho", "fechado") == "olho-f.png"
    with pytest.raises(ErroELiXX, match="inexistente"):
        h.definir_variante("olho", "vesgo")
    with pytest.raises(ErroELiXX, match="não encontrada"):
        h.definir_variante("orelha", "x")


# ----- 34-35: imagem única e partes -----

def test_personagem_uma_imagem():
    ex, cena, _prog = montar(
        'janela p {\n titulo: "T"\n personagem H {\n'
        '  imagem: "heroi.png"\n }\n}\n')
    h = vincular_personagens(cena)["H"]
    assert h.partes == {}
    assert cena.buscar("H").caminho_recurso == "heroi.png"
    tocadas = h.aplicar_pose(Pose(nome="vazia", entradas={}))
    assert tocadas == []


def test_personagem_composto_livre():
    ex, cena, _prog = montar(
        'janela p {\n titulo: "T"\n personagem Robo {\n'
        '  parte corpo {\n  }\n  parte antena {\n  }\n'
        '  parte olho_esquerdo {\n  }\n  parte olho_direito {\n  }\n'
        ' }\n personagem Criatura {\n  parte corpo2 {\n  }\n'
        '  parte tentaculo_1 {\n  }\n }\n}\n')
    pers = vincular_personagens(cena)
    assert sorted(pers["Robo"].partes) == ["antena", "corpo",
                                           "olho_direito", "olho_esquerdo"]
    assert sorted(pers["Criatura"].partes) == ["corpo2", "tentaculo_1"]


# ----- 36-37: opacidade e camada -----

def test_opacidade_hierarquica_multiplicativa():
    _ex, h, cena = heroi()
    h.no_raiz.opacidade = 0.8
    cena.buscar("braco").opacidade = 0.5
    from elixx.visual.transform import combinar, transform_de_no

    g = combinar(transform_de_no(h.no_raiz),
                 transform_de_no(cena.buscar("braco")))
    assert g.opacidade == pytest.approx(0.4)


def test_camada_usa_ordem_visual():
    from elixx.visual.transform import ordem_visual

    _ex, cena, _prog = montar(
        'janela p {\n titulo: "T"\n personagem H {\n'
        '  parte frente {\n   camada: 1\n  }\n'
        '  parte tras {\n   camada: -1\n  }\n }\n}\n')
    nomes = [n.nome for n in ordem_visual(cena.buscar("H"))]
    assert nomes.index("tras") < nomes.index("frente")


# ----- 38-39: Tk e HTML -----

def test_tk_personagem():
    try:
        from elixx.visual.tk import RenderizadorTk
    except ImportError:
        pytest.skip("Tk indisponível")
    try:
        ex, cena, _prog = montar(HEROI)
        rend = RenderizadorTk(ex)
        try:
            rend.montar(cena)
            rend.raiz.withdraw()
            rend.atualizar(0.0)
            rend.raiz.update()
            nomes = [rend._nos[n].nome for n in rend._ordem
                     if rend._nos[n].tipo in ("personagem", "parte")]
            assert "Heroi" in nomes and "mao" in nomes
        finally:
            rend.fechar()
    except Exception as exc:
        import tkinter as _tk

        if isinstance(exc, _tk.TclError):
            pytest.skip(f"sem display: {exc}")
        raise


def test_html_personagem():
    from elixx.visual.html import gerar_html

    ex, _cena, _prog = montar(HEROI)
    pagina = gerar_html(ex.ctx.objetos)
    assert "elx-grupo" in pagina


# ----- analisador (fundação) -----

def test_analyzer_mock():
    from elixx.visual.personagem import CharacterAnalyzer

    analisador = ManualAnalyzer(
        [{"nome": "braco", "pai": None, "pivo": [10, 20]}])
    resultado = analisador.analisar("heroi.png")
    assert resultado.fonte == "manual"
    assert resultado.partes[0]["nome"] == "braco"
    with pytest.raises(NotImplementedError):
        CharacterAnalyzer().analisar("x.png")


# ----- estado e exemplo -----

def test_estado_resumo():
    _ex, h, _cena = heroi()
    h.aplicar_pose("repouso")
    resumo = h.estado_resumo()
    assert resumo["pose_atual"] == "repouso"
    assert resumo["direcao"] == "frente"
    assert resumo["gesto_atual"] is None


def test_exemplo_character_core():
    with open("exemplos/character-core.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    pers = vincular_personagens(cena)
    assert "Heroi" in pers
    assert len(pers["Heroi"].poses) >= 2
