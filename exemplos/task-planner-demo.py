"""Demo Task Planner (F33) — headless + --visual opcional.

Juh: criar base, aparecer, acenar e girar a cabeça — com dependências:
1. pose neutra (runtime) 2. mostrar (runtime) 3. acenar (runtime)
4. girar cabeça rotacao→15 (código, ChangeSet aprovado).
Passos: projeto, modelo, objetivo, operações, plano, dependências,
validação, explicação, dry-run, changesets, diff, aprovação,
execução, pós-condições, reanálise, modelo, resultado, histórico.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio import StudioApp
from elixx.studio.agent import (AgentHistory, Approval,
                                PermissionSet)
from elixx.studio.agent.operacoes import SemanticOperation
from elixx.studio.agent.planejamento import (
    PainelPlano,
    PlanoTarefa,
    construir_plano,
    dry_run,
    executar_plano,
    explicar_plano,
    preparar_execucao,
    validar_plano,
)
from elixx.studio.inspetor import fluxo_personagem
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela p {\n"
    ' titulo: "Palco"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "   rotacao: 0\n"
    "  }\n"
    " }\n"
    "}\n"
)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="plan33_"))
    app = StudioApp()
    app.workspace.criar_projeto(tmp / "palco", "Palco")
    print("1. projeto: Palco")
    (tmp / "palco" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")

    modelo = ModeloSemantico("palco")
    analisar_projeto(modelo, tmp / "palco")
    print(f"2. modelo: {len(modelo)} entidades")

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "corpo", "tipo": "corpo"}])
    from elixx.visual.personagem import Pose

    for nome, props in (("neutra", {"corpo": {"rotacao": 0.0}}),
                        ("aparecer",
                         {"corpo": {"opacidade": 1.0}}),
                        ("acenar",
                         {"corpo": {"rotacao": 45.0}})):
        perso.poses[nome] = Pose(nome, entradas=dict(props))
    personagens = {"Juh": perso}

    ops = [
        SemanticOperation("pose", "Juh", {"pose": "neutra"}),
        SemanticOperation("pose", "Juh", {"pose": "aparecer"}),
        SemanticOperation("pose", "Juh", {"pose": "acenar"}),
        SemanticOperation(
            "alterar_propriedade", {"nome": "corpo"},
            {"propriedade": "rotacao"},
            alteracao={"arquivo": "src/main.elixx",
                       "propriedade": "rotacao",
                       "valor_texto": "15"}),
    ]
    print("3-4. objetivo + 4 operações (pose×3, código×1)")
    t = PlanoTarefa("Juh entra e acena", ops, dependencias={
        "passo_2": ["passo_1"], "passo_3": ["passo_2"],
        "passo_4": ["passo_3"]})
    construir_plano(t, modelo)
    print(f"5-6. plano: {t.plano.ordem_execucao()}")
    print(f"7. válido: {validar_plano(t, modelo, app.workspace)}")
    print("8. explicação:\n" + explicar_plano(t))
    secs = dry_run(t)
    print(f"9. dry-run: {len(secs['passos'])} passos, arquivos="
          f"{secs['arquivos']}, sem escrita")

    prep = preparar_execucao(t, app.workspace, modelo)
    n_code = sum(1 for p in prep["preparados"]
                 if p["tipo"] == "codigo")
    print(f"10. changesets: {n_code} de código "
          f"(+ {len(secs['passos']) - n_code} runtime)")
    painel = PainelPlano(t)
    print("11. diff passo_4:",
          painel.diff_passo("passo_4", app.workspace,
                            modelo)["semantico"])
    for p in prep["preparados"]:
        if p["changeset"] is not None:
            Approval("manual").aprovar_tudo(p["changeset"])
    print("12. aprovado (manual explícito)")
    hist = AgentHistory()
    out = executar_plano(t, {
        "workspace": app.workspace, "modelo": modelo,
        "personagens": personagens,
        "approval": Approval("manual"),
        "permissoes": PermissionSet(["PREVIEW"]),
        "historico": hist, "preparar": prep})
    print(f"13-14. executado: {out}; "
          f"pós-condições OK (sem exceção)")
    print(f"15-16. reanálise: {len(modelo)} ent; "
          f"rotacao=15 no disco: "
          f"{'rotacao: 15' in (tmp / 'palco' / 'src' / 'main.elixx').read_text(encoding='utf-8')}")
    print(f"17. resultado: {t.task.resultado.resumo}")
    print(f"18. histórico: {len(hist.listar())} tarefa(s)")

    if visual:
        from elixx.studio import StudioWorkspace
        from elixx.studio.workspace_ui import montar_workspace_ui

        app2 = StudioApp()
        ws2 = StudioWorkspace(app2)
        ws2.criar_projeto(tmp / "palco2", "Palco")
        (tmp / "palco2" / "src" / "main.elixx").write_text(
            FONTE, encoding="utf-8")
        ws2.analisar()
        ws2.preview.executar(FONTE)
        ws2.plano_view = painel
        janela = montar_workspace_ui(ws2)
        janela.after(4000, janela.destroy)
        janela.mainloop()
        print("visual: janela 4s com aba Plano")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
