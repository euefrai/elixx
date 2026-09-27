"""Demo Studio Workspace (F29) — headless + visual opcional.

1. abrir projeto; 2. árvore; 3. abrir main; 4. analisar; 5. modelo;
6. selecionar Juh; 7. inspector; 8. consultar Agent; 9. contexto;
10. plano; 11. proposta; 12. ChangeSet; 13. aprovar; 14. aplicar;
15. reanalisar; 16. preview; 17. diagnóstico; 18. salvar; 19. fechar.
Modo visual com --visual (Tk, se houver display).
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import StudioApp, StudioWorkspace
from elixx.studio.agent import Approval, PermissionSet

FONTE = (
    "janela p {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    "  pose neutra {\n"
    "   corpo:\n"
    "    rotacao: 0deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ws29_"))
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp / "loja", "Loja")
    print("1. projeto: Loja")
    print(f"2. arvore: {[n['nome'] for n in ws.arvore.nos()]}")

    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ed = ws.abrir_no_editor("src/main.elixx")
    print(f"3. editor: {ed.documento.linhas()} linhas")

    total = ws.analisar()
    print(f"4-5. modelo: {total['entidades']} entidades, "
          f"valido={total['valido']}")

    ws.preview.executar(FONTE)
    ws.preview.sincronizar_modelo(ws.modelo)
    sel = ws.preview.selecionar("personagem:Juh")
    print(f"6. selecao: {sel['id']}")
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    print(f"7. inspector: {[s['titulo'] for s in secoes]}")

    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    print(f"8-9. agent ctx: {ctx['entidades']} ent")
    plano = ws.agent.planejar(ws.modelo, "Juh", "personagem",
                              "tela ajuda")
    print(f"10. plano: {plano['status']} alvo={plano['alvo']}")
    prop = ws.agent.propor(
        app.workspace,
        [{"arquivo": "src/ajuda.elixx", "operacao": "criar",
          "conteudo_novo": "janela q {\n titulo: \"Q\"\n}\n"}],
        PermissionSet(["WRITE"]))
    print(f"11-12. proposta: {prop['status']} "
          f"{[m['caminho'] for m in prop['mudancas']]}")
    cs = ws.agent.ultima_proposta
    Approval("manual").aprovar_tudo(cs)
    print("13. aprovado")
    aplicadas = cs.aplicar(app.workspace)
    print(f"14. aplicado: {aplicadas['arquivos']}")
    ws.analisar()
    ws.preview.executar(
        (tmp / "loja" / "src" / "main.elixx").read_text(
            encoding="utf-8"))
    print(f"15-16. reanalisado: {len(ws.modelo)} ent; "
          f"preview ok")
    ws.diagnosticos.atualizar(ed.analisar())
    print(f"17. diagnosticos: {ws.diagnosticos.resumo()}")
    ws.salvar_editor("src/main.elixx")
    print(f"18. salvo: {ws.estado()['salvo']}")
    app.workspace.fechar_projeto()
    print("19. fechado")

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
        print("visual: janela exibida 4s")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
