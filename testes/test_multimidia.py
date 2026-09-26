"""Testes da Fase 07 — multimídia: SVG, ícones, recursos, áudio, vídeo,
listas, gráficos reativos, HTML. Sem internet (servidor local)."""
import os
import time

import pytest

from servidor_teste import ServidorTeste
from elixx.compilador import ast as A
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroSemantico
from elixx.multimidia.audio import MotorWinsound, validar_wav
from elixx.multimidia.icones import ICONES, obter
from elixx.multimidia.recursos import (
    CacheRecursos,
    GerenciadorRecursos,
    baixar_bytes,
    detectar_tipo,
    resolver_caminho,
)
from elixx.multimidia.svg import DesenhoSVG, ErroSVG, parse_svg
from elixx.multimidia.video import MotorVideo, validar_video
from elixx.runtime.acoes import Contexto, executar_acao
from elixx.runtime.memoria import Memoria
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.reativo import Vinculador

ASSETS = "exemplos/assets"  # barras: escape \ da linguagem


@pytest.fixture(scope="module")
def srv():
    with ServidorTeste() as servidor:
        yield servidor


# ----- SVG -----

SVG_OK = ('<svg viewBox="0 0 24 24">'
          '<rect x="4" y="4" width="16" height="16" fill="#ff0000"/>'
          '<circle cx="12" cy="12" r="4" fill="blue"/>'
          '<line x1="0" y1="0" x2="24" y2="24" stroke="black"/>'
          '<path d="M2 20 L22 20 Z"/>'
          "</svg>")


def test_svg_formas_e_cores():
    desenho = parse_svg(SVG_OK)
    assert isinstance(desenho, DesenhoSVG)
    assert (desenho.largura, desenho.altura) == (24.0, 24.0)
    tipos = [op[0] for op in desenho.ops]
    assert tipos == ["rect", "oval", "line", "poly"]
    assert desenho.ops[0][5]["fill"] == "#ff0000"
    assert desenho.ops[1][4]["fill"] == "#0055ff"  # oval: índice 4


def test_svg_invalido_erro_em_portugues():
    with pytest.raises(ErroSVG):
        parse_svg("<svg><rect>")
    with pytest.raises(ErroSVG, match="raiz"):
        parse_svg("<g></g>")


def test_svg_nunca_executa_script():
    desenho = parse_svg(
        '<svg viewBox="0 0 10 10"><script>alert(1)</script>'
        '<rect width="5" height="5" onclick="x()"/>'
        '<animate/><text x="1" y="2">oi</text></svg>')
    tipos = [op[0] for op in desenho.ops]
    assert tipos == ["rect", "text"]
    assert any("ignorado" in aviso for aviso in desenho.avisos)


def test_svg_path_subset_e_curva_avisa():
    desenho = parse_svg('<svg viewBox="0 0 10 10">'
                        '<path d="M1 1 C2 2 3 3 4 4 L9 9"/></svg>')
    assert desenho.ops  # M/L preservados
    assert any("zier" in aviso for aviso in desenho.avisos)


def test_svg_arquivo_real():
    with open(os.path.join(ASSETS, "salvar.svg"), encoding="utf-8") as arq:
        desenho = parse_svg(arq.read())
    assert desenho.ops


# ----- ícones -----

def test_icones_embutidos_completos():
    assert len(ICONES) == 10
    for nome in ["salvar", "editar", "excluir", "fechar", "adicionar",
                 "config", "pesquisar", "voltar", "avancar", "menu"]:
        desenho = parse_svg(obter(nome))
        assert desenho.ops, nome


def test_icone_desconhecido_sugere():
    with pytest.raises(ErroELiXX, match="salvar"):
        obter("slavar")


# ----- recursos -----

def test_resolver_relativo_e_absoluto():
    juncao = os.path.join("exemplos", "assets", "logo.png")
    assert resolver_caminho("exemplos", "assets/logo.png") == juncao
    absoluto = os.path.abspath("x")
    assert resolver_caminho("exemplos", absoluto) == absoluto


def test_cache_hits_misses():
    cache = CacheRecursos()
    assert cache.obter("k") is None
    cache.guardar("k", b"v")
    assert cache.obter("k") == b"v"
    assert (cache.hits, cache.misses) == (1, 1)


def test_bytes_local_e_erro_pt():
    ger = GerenciadorRecursos("exemplos")
    dados = ger.bytes_local("assets/logo.png")
    assert dados[:8] == b"\x89PNG\r\n\x1a\n"
    assert ger.bytes_local("assets/logo.png") == dados  # cache
    assert ger.cache.hits >= 1
    with pytest.raises(ErroELiXX, match="não encontrado"):
        ger.bytes_local("assets/fantasma.png")


def test_detectar_tipo():
    assert detectar_tipo("a.png") == "imagem"
    assert detectar_tipo("a.JPG") == "imagem"
    assert detectar_tipo("a.svg") == "svg"
    assert detectar_tipo("a.wav") == "audio"
    assert detectar_tipo("a.mp4") == "video"
    assert detectar_tipo("a.xyz") == "desconhecido"


def test_baixar_async_com_cache(srv):
    ger = GerenciadorRecursos(".")
    recebidos = []
    ger.baixar_async(srv.url("/bytes"), recebidos.append)
    prazo = time.monotonic() + 5
    while not recebidos and time.monotonic() < prazo:
        time.sleep(0.05)
    assert recebidos and recebidos[0] == b"0123456789abcdef"
    recebidos2 = []
    ger.baixar_async(srv.url("/bytes"), recebidos2.append)
    assert recebidos2 == [b"0123456789abcdef"]  # veio do cache
    with pytest.raises(ErroELiXX, match="bloqueada"):
        baixar_bytes("ftp://x/y", 1)


# ----- áudio -----

def test_validar_wav_real_e_erros():
    info = validar_wav(os.path.join(ASSETS, "som.wav"))
    assert info["canais"] == 1 and info["duracao_s"] > 0
    with pytest.raises(ErroELiXX, match="não encontrado"):
        validar_wav(os.path.join(ASSETS, "fantasma.wav"))
    with pytest.raises(ErroELiXX, match="WAV"):
        validar_wav(os.path.join(ASSETS, "logo.png"))


def test_winsound_toca_para_volume():
    motor = MotorWinsound()
    msg = motor.reproduzir(os.path.abspath(
        os.path.join(ASSETS, "som.wav")))
    assert "tocando" in msg and motor.estado == "tocando"
    assert "sem efeito" in motor.definir_volume(30)
    assert motor.volume == 30
    motor.parar()
    assert motor.estado == "parado"
    assert "recomeça" in motor.pausar() or "nada" in motor.pausar()


# ----- vídeo honesto -----

def test_video_abstracao():
    motor = MotorVideo()
    # sem arquivo válido: erro honesto, nunca player falso
    with pytest.raises(ErroELiXX, match="não encontrado"):
        motor.reproduzir("falta.mp4")
    with pytest.raises(ErroELiXX, match="não suportado"):
        motor.reproduzir(os.path.join(ASSETS, "logo.png"))
    assert "futura" in motor.pausar()
    assert "futura" in motor.continuar()
    assert "futura" in motor.parar()
    assert motor.estado == "parado"
    assert "guardado" in motor.definir_volume(50)
    with pytest.raises(ErroELiXX, match="não encontrado"):
        validar_video("falta.mp4")
    with pytest.raises(ErroELiXX, match="não suportado"):
        validar_video(os.path.join(ASSETS, "logo.png"))


# ----- sintaxe multimídia -----

def test_parse_props_midias():
    prog = analisar('janela p {\n titulo: "T"\n'
                    ' imagem i {\n arquivo: "a.png"\n ajuste: "conter"\n }\n'
                    ' icone s {\n nome: "salvar"\n }\n'
                    ' audio m {\n arquivo: "a.wav"\n volume: 80\n'
                    '  repetir: verdadeiro\n }\n'
                    ' video v {\n arquivo: "a.mp4"\n }\n'
                    ' grafico g {\n tipo: "barras"\n'
                    '  origem: estado.nums\n }\n}\n'
                    'estado {\n nums: [1, 2]\n}\n')
    validar(prog)
    tipos = {c.tipo for c in prog.janelas[0].componentes}
    assert tipos == {"imagem", "icone", "audio", "video", "grafico"}


def test_props_midias_invalidas():
    for prop in ['ajuste: "torcer"', 'tipo: "3d"', "volume: 200",
                 "repetir: 5"]:
        fonte = ('janela p {\n titulo: "T"\n texto t {\n texto: "x"\n '
                 + prop + '\n }\n}\n')
        with pytest.raises(ErroSemantico):
            validar(analisar(fonte))


def test_icone_nome_padrao_e_cena():
    prog = analisar('janela p {\n titulo: "T"\n icone salvar {\n }\n'
                    ' imagem i {\n arquivo: "a.png"\n reserva: "b.png"\n'
                    '  ajuste: "esticar"\n }\n}\n')
    validar(prog)
    cena = ConstrutorCena().de_objetos(
        Executor().executar(prog, []).objetos)
    assert cena.buscar("salvar").nome_icone == "salvar"
    no = cena.buscar("i")
    assert (no.fonte_recurso, no.caminho_recurso) == ("arquivo", "a.png")
    assert (no.reserva, no.ajuste) == ("b.png", "esticar")


def test_lista_literal_parse_eval_estado():
    prog = analisar('estado {\n nums: [10, 25, 35]\n}\n'
                    'janela p {\n titulo: "T"\n'
                    ' botão b {\n texto: "x"\n quando clicar {\n'
                    '  estado.nums = [1, 2]\n }\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    assert executor.estado.obter("nums") == [10.0, 25.0, 35.0]
    executor.simular_clique("b")
    assert executor.estado.obter("nums") == [1.0, 2.0]
    assert isinstance(prog.janelas[0].componentes[0].eventos[0]
                      .bloco.comandos[0], A.Atribuicao)


# ----- gráficos reativos -----

def test_grafico_serie_substitui_e_reage():
    prog = analisar('estado {\n nums: [4, 9]\n}\n'
                    'janela p {\n titulo: "T"\n grafico g {\n'
                    ' tipo: "barras"\n origem: estado.nums\n }\n'
                    ' botão b {\n texto: "x"\n quando clicar {\n'
                    '  estado.nums = [4, 9, 6, 12]\n }\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(
        executor.ctx.objetos)
    vinc = Vinculador(cena, {}, executor.estado, executor,
                      intervalo_ms=1000000)
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(0.0))
    assert cena.buscar("g").serie == [4.0, 9.0]
    assert cena.buscar("g").tipo_grafico == "barras"
    executor.simular_clique("b")
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(9999999.0))
    assert cena.buscar("g").serie == [4.0, 9.0, 6.0, 12.0]
    assert pacotes["g"] == "12"


def test_grafico_historico_preservado():
    from elixx.visual.cena import NoVisual

    from elixx.visual.reativo import Vinculador as V

    cena_no = NoVisual(tipo="grafico", nome="g")
    from elixx.visual.cena import Cena

    cena = Cena(janelas=[])
    jan = NoVisual(tipo="janela", nome="j")
    jan.adicionar(cena_no)
    cena.janelas.append(jan)
    vinc = V(cena, {"f": __import__("elixx.dados", fromlist=["FonteFalsa"])
                    .FonteFalsa({"s": {"v": 10.0}})})
    cena_no.origem = "dados.f.s.v"
    cena_no.origem_expr = None
    vinc.vinculos.append(vinc._novo(cena_no, "dados", fonte="f",
                                    sub="s.v"))
    vinc.atualizar(0.0)
    assert cena_no.historico == [10.0]
    assert cena_no.serie == []


# ----- ações de mídia -----

def prog_midia():
    return ('janela p {\n titulo: "T"\n'
            ' audio m {\n arquivo: "ASSET"\n }\n'
            ' botão t {\n texto: "x"\n quando clicar {\n'
            '  reproduzir("m")\n }\n }\n'
            ' botão s {\n texto: "y"\n quando clicar {\n'
            '  parar("m")\n }\n }\n}\n').replace(
                "ASSET", ASSETS + "/som.wav")


def test_acoes_audio_reproduzir_parar():
    prog = analisar(prog_midia())
    validar(prog)
    executor = Executor()
    executor.executar(prog, [], base_dir=".")
    executor.ctx.ao_sincronizar = None
    executor.simular_clique("t")
    assert any("tocando" in linha for linha in executor.ctx.saida)
    executor.simular_clique("s")
    assert any("parado" in linha for linha in executor.ctx.saida)


def test_acoes_pausar_continuar_audio_e_animacao():
    prog = analisar(prog_midia())
    validar(prog)
    executor = Executor()
    executor.executar(prog, [], base_dir=".")
    ctx = Contexto(executor.ctx.objetos, Memoria())
    ctx.executor = executor
    executar_acao("pausar", ["m"], ctx)
    executar_acao("continuar", ["m"], ctx)
    executar_acao("volume", ["m", 50], ctx)
    assert any("volume" in linha for linha in ctx.saida)
    # sem alvo de mídia: comportamento de animação preservado
    ctx2 = Contexto([], Memoria())
    executar_acao("pausar", [], ctx2)
    assert "(sem motor" in ctx2.saida[-1]


def test_acao_video_honesta():
    prog = analisar('janela p {\n titulo: "T"\n video v {\n texto: "x"\n }\n'
                    ' botão t {\n texto: "y"\n quando clicar {\n'
                    '  reproduzir("v")\n }\n }\n}\n')
    validar(prog)
    executor = Executor()
    executor.executar(prog, [], base_dir=".")
    executor.simular_clique("t")
    assert any("futuro" in linha for linha in executor.ctx.saida)


# ----- HTML -----

def test_html_midias():
    from elixx.visual.html import gerar_html

    prog = analisar('janela p {\n titulo: "T"\n'
                    ' imagem i {\n arquivo: "a/logo.png"\n }\n'
                    ' audio m {\n arquivo: "a/som.wav"\n }\n'
                    ' video v {\n }\n'
                    ' icone s {\n nome: "salvar"\n }\n'
                    ' grafico g {\n tipo: "pizza"\n }\n}\n')
    validar(prog)
    pagina = gerar_html(Executor().executar(prog, []).objetos)
    assert '<img' in pagina and '<audio' in pagina
    assert "backend futuro" in pagina and "só no nativo" in pagina
