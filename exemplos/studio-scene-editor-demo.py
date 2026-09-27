"""Demo Scene Editor + Adaptive Workspace (F39) — headless + visual.

1-20. projeto, cena, arvore, selecao, viewport, zoom, pan, grid,
inspector, transformacao, proposta, aprovacao, code sync, agent,
contexto, tools, reasoning, plano, changes, layouts.

Headless obrigatorio; visual (Tk) quando houver display.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import (
    BottomWorkspace,
    SceneEditor,
    SceneToolbar,
    StatusBar,
    StudioApp,
    StudioWorkspace,
    WorkspaceModes,
    buscar_palette_f39,
    montar_status,
)
from elixx.studio.ux import PropostasTracker

FONTE = (
    "janela p {\n"
    ' titulo: "Loja"\n'
    " posicao: 100 200\n"
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    " }\n"
    "}\n"
)


def _seguro(texto: str) -> str:
    """ASCII seguro no console Windows (cp1252)."""
    return str(texto).encode("ascii", "replace").decode("ascii")


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ws39_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: Loja")
    ws.analisar()
    print("2. cena: "
          f"{len(ws.modelo.entidades())} entidades, "
          f"{len(ws.modelo.relacoes())} relacoes")

    ed = SceneEditor(inspetor=app.inspetor, eventos=app.eventos)
    ed.construir_arvore(ws.modelo)
    print("3. arvore:")
    for linha in ed.arvore.linhas():
        print(f"   {_seguro(linha)}")

    print(f"4. selecao: {ed.selecionar('personagem:Juh')}")
    ed.definir_zoom(150)
    ed.pan(10, 5)
    ed.alternar_grid()
    ed.definir_snap(5)
    print(f"5-8. viewport: zoom={ed.viewport.zoom} "
          f"offset=({ed.viewport.offset_x}, {ed.viewport.offset_y}) "
          f"grid={ed.viewport.grid} snap={ed.viewport.snap}")

    barra = SceneToolbar(ed)
    print(f"9. inspector: {ed.selecao_atual()}")
    print(f"   toolbar: {len(barra.itens())} itens")

    cs = ed.propor_mover(ws.app.workspace, ws.modelo,
                         "janela:p", 150, 200)
    print(f"10-11. proposta: {_seguro(cs.revisar()[0]['previa'][:80])}")
    tracker = PropostasTracker()
    pid = tracker.adicionar(cs, "Juh posicao 100 200 -> 150 200")
    tracker.aprovar(pid)
    tracker.aplicar(pid, ws.app.workspace)
    print("12. aprovacao: aplicada; reanalisando...")
    ws.analisar()
    ed.construir_arvore(ws.modelo)
    print(f"13. code sync: {len(ws.modelo.entidades())} entidades")

    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    print(f"14-16. agent/contexto/tools: {ctx}")
    plano = ws.agent.planejar(ws.modelo, "Juh")
    print(f"17-18. reasoning/plano: {plano['status']}")

    modos = WorkspaceModes()
    for modo in ("DEFAULT", "CODE", "SCENE", "AGENT", "REVIEW"):
        modos.aplicar(ws.layout, modo)
    print("19. layouts: 5 modos aplicados")

    fundo = BottomWorkspace()
    fundo.abrir("AGENT")
    barra_status = StatusBar(montar_status(
        "Loja", "src/main.elixx",
        len(ws.modelo.entidades()), 1, "ready", True))
    print(f"20. fundo={fundo.aberta} status={barra_status.texto} "
          f"palette={len(buscar_palette_f39(''))} comandos F39")

    if visual:
        try:
            from elixx.studio.workspace_ui import (
                montar_workspace_ui,
            )

            janela = montar_workspace_ui(ws)
            janela.after(4000, janela.destroy)
            janela.mainloop()
            print("visual: janela 4s (scene editor)")
        except Exception as exc:
            print(f"visual indisponivel: {exc}")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
