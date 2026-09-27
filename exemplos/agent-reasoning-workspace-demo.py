"""Demo Reasoning Workspace (F35) — headless + --visual opcional.

1-20. projeto, modelo, intenção, contexto, operações, plano,
ChangeSet, workspace, workflow, graph, Juh, expandir, botão,
motivos, operação, plano, mudança, aprovação, preview, sessão.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio.agent import Approval
from elixx.studio.agent.contexto_tarefa import (
    ContextoTarefa,
    construir_contexto,
)
from elixx.studio.agent.operacoes import intent_para_operacao
from elixx.studio.agent.inteligencia import MockIntentProvider
from elixx.studio.agent.planejamento import (
    PlanoTarefa,
    construir_plano,
    preparar_execucao,
)
from elixx.studio.agent.workspace import AgentWorkspace
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela principal {\n"
    " personagem Juh {\n"
    "  parte cabeca {\n"
    "  }\n"
    "  parte olhos {\n"
    "  }\n"
    " }\n"
    " botao comprar {\n"
    " }\n"
    "}\n"
)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ws35_"))
    (tmp / "proj" / "src").mkdir(parents=True)
    (tmp / "proj" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: loja")

    modelo = ModeloSemantico("loja")
    analisar_projeto(modelo, tmp / "proj")
    print(f"2. modelo: {len(modelo)} entidades")

    intent = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    print(f"3. intenção: {intent.tipo} alvo={intent.personagem}")

    ctx = construir_contexto(
        modelo, ContextoTarefa(
            objetivo="fazer Juh acenar", alvo="Juh",
            entidade_selecionada="personagem:Juh"))
    print(f"4. contexto: {len(ctx.entidades)} ent, "
          f"{len(ctx.relacoes)} rel")

    op = intent_para_operacao(intent)
    print(f"5. operações: [{op.tipo} {op.alvo.nome}]")

    t = PlanoTarefa("acenar", [op])
    construir_plano(t, modelo)
    print(f"6. plano: {t.plano.ordem_execucao()}")

    print("7. ChangeSet: (runtime; sem arquivo — sem proposta)")
    ws = AgentWorkspace("Faça Juh acenar")
    ws.carregar_contexto(ctx)
    ws.carregar_operacoes([op])
    ws.carregar_plano(t)
    print(f"8. workspace: {len(ws.nos)} nós, "
          f"{len(ws.arestas)} arestas")
    print("9. workflow:",
          [(k, v["estado"]) for k, v in ws.estagios.items()
           if v["estado"] != "pendente"])
    print("10. graph: layout", ws.layout())

    sel = ws.selecionar("ctx:personagem:Juh")
    print(f"11. selecionar Juh: score={sel['score']}")
    print("12. expandir Juh:", ws.expandir("ctx:personagem:Juh",
                                           modelo))
    ws.selecionar("ctx:componente:principal.comprar")
    print("13. selecionar botão: ok")
    print("14. motivos Juh:", ctx.por_que("personagem:Juh")[:3])
    print("15. operação: pose/acenar (runtime, sem arquivo)")
    print("16. plano: 1 passo, sem dependências")
    print("17. mudança: nenhuma proposta (nada a aprovar)")
    print("18. aprovação: n/a (somente leitura)")
    ws.marcar_estagio("PREVIEW", "pronto", {"modo": "leitura"})
    print("19. preview: estágio marcado (sem renderer novo)")
    ws.transitar("RECEIVED")
    ws.transitar("CONTEXT_ANALYZING")
    ws.transitar("CONTEXT_READY")
    reg = ws.encerrar_sessao("demo headless completa")
    print(f"20. sessão: {reg['id']} estado={ws.estado}")

    _ = Approval  # (F26 reaproveitado; sem escrita nesta demo)
    if visual:
        from elixx.studio import StudioApp, StudioWorkspace
        from elixx.studio.workspace_ui import montar_workspace_ui

        app = StudioApp()
        sui = StudioWorkspace(app)
        sui.criar_projeto(tmp / "loja2", "Loja")
        (tmp / "loja2" / "src" / "main.elixx").write_text(
            FONTE, encoding="utf-8")
        sui.analisar()
        sui.preview.executar(FONTE)
        sui.raciocinio = ws
        janela = montar_workspace_ui(sui)
        janela.after(4000, janela.destroy)
        janela.mainloop()
        print("visual: janela 4s (aba Raciocínio)")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
