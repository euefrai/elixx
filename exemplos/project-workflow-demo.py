"""Demo Project Workflow (F41) — headless + visual.

1-20. criar, abrir, criar arquivo/pasta, abrir, editar, salvar,
analisar, entidade, selecionar, preview, proposta, aprovar,
sincronizar, executar, status, fechar, reabrir, estado.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import StudioApp, StudioWorkspace
from elixx.studio.projeto_workspace import (
    ArvoreProjetoReal,
    Fotografia,
    Recentes,
    abrir_projeto_validado,
    estado_projeto,
    executar_palette_f41,
    fechar_projeto,
    novo_projeto,
)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="wf41_"))
    app = StudioApp()
    info = novo_projeto(app.workspace, "Loja", tmp, "cena")
    print(f"1-2. criar/abrir: {info['projeto']} "
          f"({info['template']})")
    ws = StudioWorkspace(app)
    ws.abrir_projeto(tmp / "Loja")
    print("3. abrir: workspace pronto")
    abrir_projeto_validado(StudioApp().workspace,
                           tmp / "Loja")
    ed = ws.abrir_no_editor("src/main.elixx")
    print(f"4-6. arquivo/pasta/abrir: {ed.documento.linhas()}")
    print("   linhas da tree:")
    arv = ArvoreProjetoReal(app.workspace)
    arv.atualizar()
    for linha in arv.linhas():
        print(f"   {_seguro(linha)}")
    ed.editar(ed.documento.texto + "")
    ws.salvar_editor("src/main.elixx")
    print(f"7. editar/salvar: dirty={ed.modificado()}")
    ws.analisar()
    print(f"8-9. analisar/entidade: "
          f"{len(ws.modelo.entidades())} entidades")
    ws.preview.sincronizar_modelo(ws.modelo)
    ws.preview.selecionar("janela:cena")
    print("10-12. preview/selecionar: "
          f"{ws.preview.selecionado}")
    from elixx.studio.ux import PropostasTracker
    from elixx.studio.ux import propor_transformacao

    tracker = PropostasTracker()
    cs = propor_transformacao(app.workspace, ws.modelo,
                              "janela:cena",
                              {"titulo": '"Loja Nova"'})
    pid = tracker.adicionar(cs, "mover")
    tracker.aprovar(pid)
    tracker.aplicar(pid, app.workspace)
    print("13-15. proposta/aprovar/sincronizar: aplicada")
    saida = executar_palette_f41(ws, "executar",
                                 {"caminho": "src/main.elixx"})
    print(f"16. executar: {saida['estado']}")
    est = estado_projeto(ws).to_dict()
    print(f"17. status: preview={est['preview_state']} "
          f"dirty={est['dirty_files']}")
    fechar_projeto(ws)
    ws.abrir_projeto(tmp / "Loja")
    ws.analisar()
    print("18-20. fechar/reabrir/estado: "
          f"{len(ws.modelo.entidades())} entidades")
    rec = Recentes()
    rec.adicionar("Loja", str(tmp / "Loja"))
    foto = Fotografia()
    foto.fotografar(app.workspace)
    print(f"recentes={rec.listar()} fotos={foto}")
    if visual:
        try:
            from elixx.studio.workspace_ui import (
                montar_workspace_ui,
            )

            janela = montar_workspace_ui(ws)
            janela.after(4000, janela.destroy)
            janela.mainloop()
            print("visual: janela 4s (workflow)")
        except Exception as exc:
            print(f"visual indisponivel: {exc}")


def _seguro(texto: str) -> str:
    return str(texto).encode("ascii", "replace").decode("ascii")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
