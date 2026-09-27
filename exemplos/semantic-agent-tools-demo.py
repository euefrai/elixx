"""Demo Semantic Agent Tools (F36) — headless + --visual opcional.

1-20. projeto, intent, contexto, registry, tools, Juh, partes,
gestos, explicação, operação, proposta, plano, ChangeSet, approval,
workspace, trace, graph, workflow, preview, fim.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import StudioApp
from elixx.studio.agent.contexto_tarefa import (
    ContextoTarefa,
    construir_contexto,
)
from elixx.studio.agent.ferramentas_semanticas import (
    AgentToolCall,
    SemanticPermissions,
    SemanticToolRegistry,
    executar_chamada,
    executar_sequencia,
)
from elixx.studio.agent.workspace import AgentWorkspace
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela principal {\n"
    " personagem Juh {\n"
    "  parte cabeca {\n"
    "  }\n"
    "  pose acenar {\n"
    "   cabeca:\n"
    "    rotacao: 45deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


class _Amb:
    def __init__(self, modelo):
        self.modelo = modelo
        self.workspace = None
        self.personagens = {}
        self.contexto = None
        self.preview = None
        self.plano_view = None
        self.rig = None


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="tools36_"))
    (tmp / "proj" / "src").mkdir(parents=True)
    (tmp / "proj" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: loja")

    from elixx.studio.agent.inteligencia import MockIntentProvider

    intent = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    print(f"2. intent: {intent.tipo} alvo={intent.personagem}")

    modelo = ModeloSemantico("loja")
    analisar_projeto(modelo, tmp / "proj")
    print(f"3. contexto: {len(modelo)} entidades no modelo")

    reg = SemanticToolRegistry()
    print(f"4-5. registry: {len(reg.listar())} tools "
          f"({sorted({t.categoria for t in reg._tools.values()})})")

    amb = _Amb(modelo)
    perms = SemanticPermissions(["READ", "ANALYZE", "PROPOSE"])
    trace_calls = [
        ("buscar_entidade", {"nome": "Juh"}),
        ("consultar_partes", {"nome": "Juh"}),
        ("consultar_gestos", {"nome": "Juh"}),
    ]
    for tool_id, args in trace_calls:
        out = executar_chamada(
            reg, AgentToolCall(tool_id, args), amb, perms)
        print(f"6-8. {tool_id}: ok={out.sucesso} "
              f"msg={out.mensagem[:60]}")

    out = executar_chamada(
        reg, AgentToolCall("propor_operacao",
                           {"pedido": "faça a Juh acenar"}),
        amb, perms)
    print(f"9-10. operação: {out.dados['operacao']['tipo']} "
          f"(proposta, sem executar)")
    print(f"11. proposta: {out.mensagem[:70]}")

    out = executar_chamada(
        reg, AgentToolCall("criar_proposta_plano",
                           {"objetivo": "acenar",
                            "operacoes": [out.dados["operacao"]]}),
        amb, perms)
    print(f"12. plano: {out.dados}")
    print("13. ChangeSet: via F26/F28 (aprovação externa)")
    print("14. approval: manual (nada auto-aplicado)")

    ws = AgentWorkspace("Fazer Juh acenar")
    ws.carregar_contexto(construir_contexto(
        modelo, ContextoTarefa(objetivo="acenar", alvo="Juh")))
    seq = executar_sequencia(
        reg, [AgentToolCall(t, a) for t, a in trace_calls],
        amb, SemanticPermissions(["READ"]))
    ws.carregar_tools(seq)
    print(f"15. workspace: {len(ws.nos)} nós "
          f"(TOOLS={ws.estagios['TOOLS']['quantidade']})")
    print("16. trace:\n" + seq.explicar().encode(
        "ascii", errors="replace").decode("ascii"))
    ws.layout()
    print(f"17. graph: {len(ws.visiveis())} visíveis")
    print("18. workflow:",
          [k for k, v in ws.estagios.items()
           if v["estado"] != "pendente"])
    print("19. preview: estágio do runtime F25 (sem renderer novo)")
    print("20. fim: APPLY só via Approval (negado aqui)")

    if visual:
        from elixx.studio import StudioWorkspace
        from elixx.studio.workspace_ui import montar_workspace_ui

        app = StudioApp()
        sui = StudioWorkspace(app)
        sui.criar_projeto(tmp / "loja2", "Loja")
        (tmp / "loja2" / "src" / "main.elixx").write_text(
            FONTE, encoding="utf-8")
        sui.analisar()
        sui.preview.executar(FONTE)
        sui._trace_tools = seq
        janela = montar_workspace_ui(sui)
        janela.after(4000, janela.destroy)
        janela.mainloop()
        print("visual: janela 4s (TOOLS + tema dark)")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
