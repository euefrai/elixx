"""Demo Real Scene Canvas (F40) — headless + visual.

1-25. projeto, cena, tree, objetos, personagem, bbox, mover,
proposta, cancelar, mover, aprovar, code sync, modelo, canvas,
zoom, pan, grid, fit, inspector, agent, contexto, tools,
reasoning, plano, changes.

Headless obrigatorio; visual (Tk) quando houver display.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import (
    SceneCanvas,
    StudioApp,
    StudioWorkspace,
    buscar_palette_f40,
    cena_de_texto,
    desenhar,
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
    ' texto ola {\n'
    '  texto: "Ola"\n'
    " }\n"
    "}\n"
)


def _seguro(texto: str) -> str:
    return str(texto).encode("ascii", "replace").decode("ascii")


class _StubCanvas:
    def __init__(self):
        self.itens = []

    def delete(self, _t):
        self.itens = []

    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600

    def _reg(self, k, *a, **kw):
        self.itens.append((k, a, kw))
        return len(self.itens)

    def create_rectangle(self, *a, **k):
        return self._reg("rect", *a, **k)

    def create_text(self, *a, **k):
        return self._reg("text", *a, **k)

    def create_line(self, *a, **k):
        return self._reg("line", *a, **k)

    def create_image(self, *a, **k):
        return self._reg("image", *a, **k)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ws40_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: Loja")
    ws.analisar()
    saida = cena_de_texto(FONTE)
    print(f"2. cena: ok={saida['ok']} "
          f"personagens={list(saida['personagens'])}")
    canvas = SceneCanvas(inspetor=app.inspetor,
                         eventos=app.eventos)
    canvas.montar(saida["cena"], saida["personagens"],
                  ws.modelo)
    print("3. tree+objetos: "
          f"{[(o.kind, o.id) for o in canvas.ordem_render()]}")
    print(f"4-5. render: {desenhar(_StubCanvas(), canvas)}")
    sel = canvas.selecionar("personagem:Juh")
    print(f"6. selecionar Juh: {_seguro(sel)}")
    bb = canvas.por_id["personagem:Juh"].bbox_global(
        canvas.por_id)
    print(f"7. bbox: {_seguro(bb)}")
    cs = canvas.arrastar_para("janela:p", 180, 200,
                              ws.app.workspace, ws.modelo)
    print(f"8-9. mover->proposta: "
          f"{_seguro(cs.revisar()[0]['previa'][:60])} "
          "(sem escrita)")
    print("10. cancelar: proposta descartada (arquivo intacto)")
    tracker = PropostasTracker()
    cs2 = canvas.arrastar_para("janela:p", 180, 200,
                               ws.app.workspace, ws.modelo)
    pid = tracker.adicionar(cs2, "mover Juh 100->180")
    tracker.aprovar(pid)
    tracker.aplicar(pid, ws.app.workspace)
    print("11-12. aprovar+sync: arquivo atualizado")
    ws.analisar()
    diff = canvas.recarregar(
        (tmp / "loja" / "src" / "main.elixx").read_text(
            encoding="utf-8"))
    print(f"13-14. modelo+canvas: {_seguro(diff)}")
    canvas.viewport.set_zoom(150)
    canvas.viewport.mover(10, 5)
    canvas.viewport.grid = True
    print(f"15-17. zoom/pan/grid: {canvas.viewport.to_dict()}")
    print(f"18. fit: {_seguro(canvas.enquadrar(800, 600))}")
    from elixx.studio.scene_canvas import ficha_objeto

    ficha = ficha_objeto(ws.modelo, "personagem:Juh",
                         saida["cena"], saida["personagens"])
    print(f"19. inspector: {sorted(ficha)}")
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    plano = ws.agent.planejar(ws.modelo, "Juh")
    print(f"20-24. agent/contexto/tools/reasoning/plano: "
          f"{ctx['entidades']} ent, {plano['status']}")
    print(f"25. changes+palette: "
          f"{len(buscar_palette_f40(''))} comandos F40")
    if visual:
        try:
            from elixx.studio.scene_canvas import (
                abrir_janela_cena,
            )

            janela = abrir_janela_cena(ws, FONTE)
            janela.after(4000, janela.destroy)
            janela.mainloop()
            print("visual: janela 4s (scene canvas)")
        except Exception as exc:
            print(f"visual indisponivel: {exc}")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
