"""Testes do Renderer: interface abstrata, registro, fluxo de eventos
(gesto → objeto → runtime → ação) e CLI nativa com double.

Nenhum teste aqui abre janela real: usa RenderizadorMemoria (double de
teste registrado como "memoria"). Janela real é coberta pelos testes
manuais em docs/testes-manuais.md (NUNCA marcados como auto-aprovados).
"""
import pytest

from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroExecucao
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.renderizador import (
    Renderizador, obter_renderizador, registrar_renderizador,
)


class RenderizadorMemoria(Renderizador):
    """Double de teste: registra chamadas em vez de desenhar."""

    nome = "memoria"

    def __init__(self, executor=None):
        super().__init__(executor)
        self.chamadas: list = []
        self.mensagens: list = []
        self.agendados: list = []
        self.rodando = False
        self.fechado = False

    def montar(self, cena):
        self.cena = cena
        for jan in cena.janelas:
            self.chamadas.append(('janela', jan.nome, jan.largura, jan.altura))
            for filho in jan.todos()[1:]:
                if filho.tipo == 'texto':
                    self.desenhar_texto(filho, None)
                elif filho.tipo == 'botao':
                    self.desenhar_botao(filho, None)

    def criar_janela(self, no):
        self.chamadas.append(('janela', no.nome))
        return object()

    def desenhar_texto(self, no, pai):
        self.chamadas.append(('texto', no.nome, no.texto, no.fonte_px))
        return object()

    def desenhar_botao(self, no, pai):
        self.chamadas.append(('botao', no.nome, no.texto))
        return object()

    def atualizar(self, dt_ms):
        self.chamadas.append(('atualizar', dt_ms))

    def programar(self, ms, funcao):
        self.agendados.append((ms, funcao))

    def mostrar_mensagem(self, texto):
        self.mensagens.append(texto)

    def definir_valor(self, no, valor):
        self.chamadas.append(('valor', no.nome, valor))

    def executar_loop(self):
        self.rodando = True
        for _ms, funcao in self.agendados:
            funcao()

    def fechar(self):
        self.fechado = True
        self.rodando = False


registrar_renderizador("memoria", RenderizadorMemoria)

FONTE = ('janela principal {\n titulo: "App"\n tamanho: 800px 500px\n'
         ' botão abrir {\n texto: "Abrir"\n'
         ' quando clicar {\n mostrar("Olá, ELiXX!")\n }\n }\n}')


def montar_memoria(fonte=FONTE):
    prog = analisar(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    renderer = RenderizadorMemoria(executor)
    executor.ctx.ao_mostrar = renderer.mostrar_mensagem
    return executor, cena, renderer


def test_interface_abstrata_exige_metodos():
    with pytest.raises(TypeError):
        Renderizador()  # type: ignore[abstract]


def test_registro_e_obter():
    assert obter_renderizador("memoria") is RenderizadorMemoria
    with pytest.raises(ErroExecucao):
        obter_renderizador("inexistente")


def test_montar_cria_janela_texto_botao():
    _ex, cena, renderer = montar_memoria()
    renderer.montar(cena)
    assert ('janela', 'principal', 800.0, 500.0) in renderer.chamadas
    assert ('botao', 'abrir', 'Abrir') in renderer.chamadas


def test_clique_real_atravessa_evento_e_acao():
    # fluxo exigido: gesto → renderer → objeto → evento → runtime → ação
    _ex, cena, renderer = montar_memoria()
    renderer.montar(cena)
    renderer.ao_interagir(cena.buscar('abrir'), 'clicar')
    assert renderer.mensagens == ['Olá, ELiXX!']


def test_atualizar_recebe_delta_ms():
    _ex, cena, renderer = montar_memoria()
    renderer.atualizar(16.6)
    assert ('atualizar', 16.6) in renderer.chamadas


def test_imagem_no_nativo_erro_claro():
    # Imagem chega na Fase 03: o erro precisa dizer isso em português.
    from elixx.visual.renderizador import Renderizador
    from elixx.visual.tk import RenderizadorTk  # só a classe, sem Tk()
    prog = analisar('janela p {\n titulo: "T"\n imagem f {\n }\n}')
    validar(prog)
    ex = Executor()
    res = ex.executar(prog, [])
    cena = ConstrutorCena().de_objetos(res.objetos)
    tk_renderer = RenderizadorTk.__new__(RenderizadorTk)
    with pytest.raises(ErroExecucao) as exc:
        Renderizador.desenhar_imagem(tk_renderer, cena.janelas[0].filhos[0],
                                     None)
    assert 'Fase 03' in str(exc.value)


def test_cli_nativa_usada_por_padrao(tmp_path, monkeypatch, capsys):
    # sem --sem-janela, o CLI chama executar_nativo (aqui com double).
    from elixx.cli import main
    from elixx.visual import nativo

    alvo = tmp_path / 'interface.elixx'
    alvo.write_text(FONTE, encoding='utf-8')
    monkeypatch.setattr(nativo, 'RenderizadorTk', RenderizadorMemoria)
    assert main(['executar', str(alvo)]) == 0
    assert 'principal' in capsys.readouterr().out


def test_cli_clicar_agenda_interacao(tmp_path, monkeypatch, capsys):
    from elixx.cli import main
    from elixx.visual import nativo

    alvo = tmp_path / 'interface.elixx'
    alvo.write_text(FONTE, encoding='utf-8')
    monkeypatch.setattr(nativo, 'RenderizadorTk', RenderizadorMemoria)
    assert main(['executar', str(alvo), '--clicar', 'abrir']) == 0
    # o double executa agendados no loop: clique mostra a mensagem
    assert 'Olá, ELiXX!' in capsys.readouterr().out
