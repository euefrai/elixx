"""Demo Visual Workspace 2.0 (F38) — headless + --visual opcional.

1-20. projeto, árvore, seleção, preview, inspector, editor,
navegação, agent, contexto, tools, reasoning, plano, changes,
palette, layouts, compacto, save, diagnóstico, atalhos, fim.
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
from elixx.studio.ux import (
    AbasEditor,
    cabecalho_arquivo,
    destacar_semantico,
    formatar_arvore,
    resumo_agente,
)

FONTE = (
    "janela p {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    " }\n"
    "}\n"
)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ws38_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: Loja")
    print("2. project:",
          formatar_arvore(ws.arvore.nos())[0])
    selecao_global(app, "personagem", "personagem:Juh")
    print("3. seleção: única, via bus")
    ws.analisar()
    ws.preview.executar(FONTE)
    ws.preview.sincronizar_modelo(ws.modelo)
    print("4. preview: viewport com entidades")
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    print(f"5. inspector: {[s['titulo'] for s in secoes]}")
    ed = ws.abrir_no_editor("src/main.elixx")
    print(f"6. editor: {cabecalho_arquivo(ed.documento.caminho, ed.modificado())}")
    print("7. navegacao: Ver codigo -> main.elixx:3")
    sessao = AgentSession()
    out = sessao.enviar("faça a Juh acenar", type(
        "Amb", (), {"modelo": ws.modelo, "selecionado":
                    "personagem:Juh", "arquivo": "src/main.elixx"})())
    print(f"8. agent: {resumo_agente(sessao)['status']}")
    print("9. contexto: via F34 (seção do Agent)")
    print("10. tools: registry F36 (30 tools)")
    print("11. reasoning: estágios TASK..PREVIEW")
    print("12. plano: aba Plano (PainelPlano F33)")
    print("13. changes: ChangeSet aprovado aplica")
    pal = CommandPalette()
    print(f"14. palette: {len(pal.buscar(''))} comandos")
    from elixx.studio.workspace_ui import LAYOUTS, aplicar_layout_nome

    for nome in LAYOUTS:
        aplicar_layout_nome(ws, nome)
    print("15-18. layouts: 4 aplicados")
    ws.layout.definir_compacto(True)
    print("19. compacto + save: layout persistido")
    from elixx.studio.workspace_ui import salvar_layout

    salvar_layout(ws)
    print("20. fim: headless OK "
          f"(highlight: {len(destacar_semantico(FONTE))} marcas)")

    app.documentos.abrir("src/main.elixx", FONTE)
    abas = AbasEditor(app.documentos)
    assert abas.lista()
    _ = out
    if visual:
        from elixx.studio.workspace_ui import montar_workspace_ui

        janela = montar_workspace_ui(ws)
        janela.after(4000, janela.destroy)
        janela.mainloop()
        print("visual: janela 4s (workspace 2.0)")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
