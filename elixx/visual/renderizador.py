"""Abstração de Renderer da ELiXX.

Todo backend (nativo, HTML, futuros) implementa esta interface. O runtime
nunca importa o backend: ele entrega a Cena pronta e o renderer desenha.

    Renderer
     ├── montar(cena)
     ├── criar_janela(no)
     ├── desenhar_texto(no)
     ├── desenhar_botao(no)
     ├── desenhar_imagem(no)
     ├── atualizar(dt_ms)
     ├── programar(ms, funcao)
     ├── mostrar_mensagem(texto)
     ├── executar_loop()
     └── fechar()
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..erros import ErroExecucao

REGISTRO_RENDERIZADORES: dict[str, type] = {}


def registrar_renderizador(nome: str, classe: type) -> None:
    """Registra um backend (usado pelo CLI e pelos testes com doubles)."""
    REGISTRO_RENDERIZADORES[nome] = classe


def obter_renderizador(nome: str) -> type:
    try:
        return REGISTRO_RENDERIZADORES[nome]
    except KeyError:
        raise ErroExecucao(
            f"Renderer desconhecido: {nome!r}. "
            f"Válidos: {', '.join(sorted(REGISTRO_RENDERIZADORES))}.",
        )


class Renderizador(ABC):
    """Interface que todo backend gráfico da ELiXX implementa."""

    nome = "base"

    def __init__(self, executor=None) -> None:
        # executor: Executor do runtime (para disparar eventos ELiXX).
        # Opcional para que testes construam renderers sem programa.
        self.executor = executor
        self.cena = None
        # vinculador: Vinculador reativo (extensão dashboard). O tick o
        # consulta e aplica cada pacote via definir_valor.
        self.vinculador = None
        # motor: MotorAnimacoes (Fase 03). O tick o avança com dt real.
        self.motor = None

    @abstractmethod
    def montar(self, cena) -> None:
        """Cria as janelas/widgets a partir da Cena."""

    @abstractmethod
    def criar_janela(self, no) -> object:
        """Cria uma janela nativa a partir de um NoVisual tipo janela."""

    @abstractmethod
    def desenhar_texto(self, no, pai) -> object:
        """Desenha um texto."""

    @abstractmethod
    def desenhar_botao(self, no, pai) -> object:
        """Desenha um botão clicável ligado ao evento ELiXX."""

    def desenhar_imagem(self, no, pai) -> object:
        """Desenha uma imagem (backend decide; base levanta erro claro)."""
        raise ErroExecucao(
            "Imagens no renderer nativo chegam na Fase 03. "
            "Use elixx compilar para a prévia HTML.",
            linha=no.linha,
        )

    @abstractmethod
    def atualizar(self, dt_ms: float) -> None:
        """Sincroniza estado runtime → tela (visibilidade etc.)."""

    @abstractmethod
    def programar(self, ms: int, funcao) -> None:
        """Agenda uma função daqui a N ms (base do futuro delta-time)."""

    def mostrar_mensagem(self, texto: str) -> None:
        """Exibe um mostrar(...) na tela (base: ignora; nativo: barra)."""

    def definir_valor(self, no, valor) -> None:
        """Aplica um pacote do Vinculador ao widget (base: ignora)."""

    @abstractmethod
    def executar_loop(self) -> None:
        """Roda o loop de eventos até fechar."""

    @abstractmethod
    def fechar(self) -> None:
        """Fecha todas as janelas e encerra o loop."""

    # ----- fluxo de eventos (idêntico em todo backend) -----

    def ao_interagir(self, no, evento: str) -> None:
        """Caminho: gesto físico → renderer → objeto → evento → runtime.

        Não existe sistema paralelo de eventos: o renderer só traduz o
        gesto para (objeto, nome-do-evento) e o Executor faz o resto
        (inclusive validar o nome do evento).
        """
        if self.executor is None:
            return
        objeto = no.ref_objeto
        if objeto is None:
            return
        self.executor.disparar(objeto, evento)
