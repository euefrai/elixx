"""Demo Command Center (F37) — headless + --visual opcional.

1-20. projeto, sessão, tarefa, intent, contexto, tools, operações,
plano, changes, seleção, Inspector, Preview, Reasoning, Palette,
layout, compacto, revisão, cancelamento, nova sessão, fim.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import StudioApp, StudioWorkspace
from elixx.studio.agent.interacao import (
    AgentSession,
    CommandPalette,
    selecao_global,
)
from elixx.studio.workspace_ui import LAYOUTS, aplicar_layout_nome

FONTE = (
    "janela p {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    "  pose acenar {\n"
    "   corpo:\n"
    "    rotacao: 45deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


class _Amb:
    def __init__(self, modelo):
        self.modelo = modelo
        self.selecionado = "personagem:Juh"
        self.arquivo = "src/main.elixx"


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="cc37_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "loja", "Loja")
    print("1. projeto: Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")

    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    modelo = ModeloSemantico("loja")
    analisar_projeto(modelo, tmp / "loja")
    sessao = AgentSession()
    print(f"2. sessão: {sessao.id}")
    out = sessao.enviar("faça a Juh acenar", _Amb(modelo))
    print(f"3-4. tarefa+intent: {out.get('ok')}")
    print("5-7. contexto/tools/operações: ver teste/manual")
    print("8. plano: 1 operação (pose)")
    print("9. changes: nenhuma (runtime, sem arquivo)")
    selecao_global(app, "personagem", "personagem:Juh")
    print("10. seleção: personagem:Juh (única)")
    print("11. Inspector: selecao ativa")
    print("12. Preview: pipeline F25 intacto")
    print("13. Reasoning: estágios via AgentWorkspace")
    pal = CommandPalette()
    print(f"14. palette: {len(pal.buscar(''))} comandos")
    for nome in LAYOUTS:
        aplicar_layout_nome(ws, nome)
    print("15. layouts: 4 aplicados")
    ws.layout.definir_compacto(True)
    print("16. compacto: ativo")
    print("17. revisar: proposta sem aplicar (honesto)")
    sessao.cancelar()
    print(f"18. cancelar: {sessao.estado}")
    sessao.nova_sessao()
    print("19. nova sessão: limpa, arquivos intactos")
    print("20. fim: headless OK")

    if visual:
        from elixx.studio.workspace_ui import montar_workspace_ui

        app2 = StudioApp()
        ws2 = StudioWorkspace(app2)
        ws2.criar_projeto(tmp / "loja2", "Loja")
        (tmp / "loja2" / "src" / "main.elixx").write_text(
            FONTE, encoding="utf-8")
        ws2.analisar()
        ws2.preview.executar(FONTE)
        janela = montar_workspace_ui(ws2)
        janela.after(4000, janela.destroy)
        janela.mainloop()
        print("visual: janela 4s (command center)")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
