"""Demo Visual Polish (F40.5) — headless + visual.

Design System 3.0, layout, selecao, canvas, inspector, agent,
contexto, tools, reasoning, plano, changes, compacto, foco,
palette. Headless obrigatorio; visual com display.
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
    contraste,
    desenhar,
    paleta,
    validar_ds3,
)
from elixx.studio.ux import FocusState, PropostasTracker

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


class _Stub:
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
        return self._reg("r", *a, **k)

    def create_text(self, *a, **k):
        return self._reg("t", *a, **k)

    def create_line(self, *a, **k):
        return self._reg("l", *a, **k)

    def create_image(self, *a, **k):
        return self._reg("i", *a, **k)

    def create_oval(self, *a, **k):
        return self._reg("o", *a, **k)


def main(visual: bool = False) -> None:
    print(f"DS3: {validar_ds3()['motivo']}")
    print(f"paleta: {paleta()['background']} + "
          f"{paleta()['accent']}")
    print(f"contraste texto: "
          f"{contraste('#f3f3f7', '#171720'):.1f}")
    tmp = Path(tempfile.mkdtemp(prefix="ws405_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("projeto: Loja (layout DEFAULT)")
    ws.analisar()
    saida = cena_de_texto(FONTE)
    canvas = SceneCanvas(inspetor=app.inspetor,
                         eventos=app.eventos)
    canvas.montar(saida["cena"], saida["personagens"],
                  ws.modelo)
    print(f"canvas: {desenhar(_Stub(), canvas)}")
    sel = canvas.selecionar("personagem:Juh")
    print(f"selecao: {_seguro(sel)}")
    from elixx.studio.scene_canvas import ficha_objeto

    ficha = ficha_objeto(ws.modelo, "personagem:Juh",
                         saida["cena"], saida["personagens"])
    print(f"inspector: {sorted(ficha)}")
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    plano = ws.agent.planejar(ws.modelo, "Juh")
    print(f"agent/contexto/tools/reasoning/plano: "
          f"{ctx['entidades']} ent, {plano['status']}")
    cs = canvas.arrastar_para("janela:p", 150, 200,
                              ws.app.workspace, ws.modelo)
    tracker = PropostasTracker()
    pid = tracker.adicionar(cs, "mover")
    tracker.aprovar(pid)
    print(f"changes: {tracker.listar()}")
    ws.layout.definir_compacto(True)
    print(f"compacto: {ws.layout.compacto}")
    ws.layout.definir_compacto(False)
    foco = FocusState()
    foco.entrar(ws.layout, ["preview"])
    foco.sair(ws.layout)
    print("foco: entrar/sair OK")
    print(f"palette: {len(buscar_palette_f40(''))} F40")
    if visual:
        try:
            from elixx.studio.scene_canvas import (
                abrir_janela_cena,
            )

            janela = abrir_janela_cena(ws, FONTE)
            janela.after(4000, janela.destroy)
            janela.mainloop()
            print("visual: janela 4s (polish)")
        except Exception as exc:
            print(f"visual indisponivel: {exc}")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
