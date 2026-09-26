"""Execução nativa: AST validada → Executor → Cena → Renderer.

O renderer recebe representação já processada (Cena); o parser nunca
encosta em backend gráfico. O HTML continua existindo como backend
separado (elixx compilar).
"""
from __future__ import annotations

from ..animacao.motor import MotorAnimacoes, definicao_de_ast
from ..erros import ErroELiXX
from ..multimidia.recursos import GerenciadorRecursos
from ..runtime.nucleo import Executor
from .cena import ConstrutorCena
from .reativo import Vinculador
from .tk import RenderizadorTk


def executar_nativo(programa, avisos, *, clicar: str | None = None,
                    fechar_apos_ms: int | None = None,
                    renderer_cls=None, base_dir: str = ".") -> int:
    """Roda o programa numa janela real. Retorna código de saída."""
    executor = Executor()
    resultado = executor.executar(programa, avisos, base_dir=base_dir)
    for linha in resultado.saida:
        print(linha)

    cena = ConstrutorCena().de_objetos(
        resultado.objetos, executor.temas, executor.tema_atual)
    cls = renderer_cls or RenderizadorTk
    renderer = cls(executor)
    # Fase 07: recursos relativos à pasta do .elixx.
    renderer.recursos = GerenciadorRecursos(base_dir)
    # Fase 08: ações enxergam o renderer (temas, foco).
    executor.ctx.renderer = renderer
    # Reatividade: Vinculador liga Cena ↔ fontes; ações o enxergam via ctx.
    vinculador = Vinculador(cena, executor.fontes, executor.estado,
                          executor)
    renderer.vinculador = vinculador
    executor.ctx.vinculador = vinculador
    executor.ctx.ao_sair = renderer.fechar
    # Fase 06: ação sincronizar() dispara buscas assíncronas.
    executor.ctx.ao_sincronizar = executor.sincronizar_fontes
    # Fase 03: motor de animação (definições da AST → Cena).
    motor = MotorAnimacoes(executor)
    definicoes = []
    for jan_ast in programa.janelas:
        for anim_ast in jan_ast.animacoes:
            definicoes.append(definicao_de_ast(anim_ast))
    motor.carregar(definicoes, cena)
    renderer.motor = motor
    executor.ctx.motor = motor
    # mostrar(...) aparece na barra de mensagens E no console (via saida)
    executor.ctx.ao_mostrar = renderer.mostrar_mensagem
    try:
        renderer.montar(cena)
    except Exception as exc:
        if "display" in str(exc).lower() or "couldn't connect" in str(exc):
            raise ErroELiXX(
                "Não foi possível abrir a janela gráfica neste ambiente.",
                sugestao="Use: elixx executar arquivo.elixx --sem-janela",
            )
        if exc.__class__.__name__ == "TclError":
            raise ErroELiXX(
                f"O sistema gráfico recusou a janela: {exc}",
                sugestao="Use: elixx executar arquivo.elixx --sem-janela",
            )
        raise
    print(f"[ELiXX] {resultado.texto_janelas()}")
    # Fase 05: primeira alimentação SÍNCRONA — componentes com origem
    # já nascem com o valor (nunca vazios até o primeiro tick/evento).
    try:
        for no, pacote in vinculador.primeira_carga():
            renderer.definir_valor(no, pacote)
    except Exception:
        pass
    if clicar:
        renderer.programar(400, lambda: _clicar(renderer, cena, clicar))
    if fechar_apos_ms is not None:
        renderer.programar(fechar_apos_ms, renderer.fechar)
    motor.iniciar_automaticas()
    # Fase 06: primeira busca das fontes remotas (assíncrona; a UI
    # continua responsiva e o estado avisa o Vinculador ao chegar).
    try:
        executor.iniciar_fontes()
    except Exception:
        pass
    renderer.executar_loop()
    # saída produzida durante a interação (após o loop fechar)
    for linha in executor.ctx.saida[len(resultado.saida):]:
        print(linha)
    for aviso_extra in executor.avisos:
        print(f"Aviso: {aviso_extra}")
    return 0


def _clicar(renderer, cena, nome: str) -> None:
    no = cena.buscar(nome)
    if no is None:
        print(f"O componente {nome!r} não existe para clicar.")
        return
    houve = False
    if renderer.executor is not None and no.ref_objeto is not None:
        houve = renderer.executor.disparar(no.ref_objeto, "clicar")
    if not houve:
        print(f"O componente {nome!r} não trata o evento clicar.")
