"""Demo Context Intelligence (F34) — headless + --visual opcional.

1. projeto; 2. analisar; 3. intenção; 4. seleção; 5. contexto;
6. entidades; 7. relações; 8. scores; 9. motivos; 10. filtro;
11. incluir; 12. excluir; 13. expandido; 14. budget;
15. ambiguidade; 16. operação; 17. planner.
"""
import sys
import tempfile
from pathlib import Path

from elixx.studio.agent.contexto_tarefa import (
    ContextoConfig,
    ContextoTarefa,
    construir_contexto,
)
from elixx.studio.agent.inteligencia import MockIntentProvider
from elixx.studio.agent.operacoes import intent_para_operacao
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela principal {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte cabeca {\n"
    "  }\n"
    "  parte olhos {\n"
    "  }\n"
    "  pose olhar {\n"
    "   cabeca:\n"
    "    rotacao: 10deg\n"
    "  }\n"
    " }\n"
    " botao comprar {\n"
    '  texto: "Comprar"\n'
    " }\n"
    "}\n"
)


def main(visual: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ctx34_"))
    (tmp / "proj" / "src").mkdir(parents=True)
    (tmp / "proj" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: loja")

    modelo = ModeloSemantico("loja")
    analisar_projeto(modelo, tmp / "proj")
    print(f"2. modelo: {len(modelo)} entidades")

    it = MockIntentProvider().gerar_intencao(
        None, "faça a Juh acenar")
    print(f"3. intenção: {it.tipo} alvo={it.personagem}")
    print("4. seleção: personagem:Juh (simulada)")

    tarefa = ContextoTarefa(
        objetivo="fazer Juh olhar para o botao e depois acenar",
        alvo="Juh", entidade_selecionada="personagem:Juh",
        arquivo_atual="src/main.elixx",
        operacoes=["pose", "expressao"])
    ctx = construir_contexto(modelo, tarefa)
    print("5. contexto pronto")
    print("6. entidades:",
          [e.id for e in ctx.entidades])
    print("7. relações:", len(ctx.relacoes))
    print("8. scores:",
          [(e.id, e.score) for e in ctx.entidades[:4]])
    print("9. motivos Juh:", ctx.por_que("personagem:Juh")[:3])
    partes = [e.id for e in ctx.entidades
              if e.categoria == "PARTE"]
    print("10. filtro PARTE:", partes)

    t2 = ContextoTarefa(
        objetivo="ver", alvo="Juh",
        incluir=["componente:principal.comprar"],
        excluir=["pose:Juh.olhar"])
    ctx2 = construir_contexto(modelo, t2)
    print("11-12. overrides:",
          ctx2.diagnostico["overrides"],
          "| excluidas:",
          [e["id"] for e in ctx2.excluidas])

    ctx3 = construir_contexto(
        modelo, tarefa, ContextoConfig(modo="expandido"))
    print(f"13. expandido: {len(ctx3.entidades)} ent")
    cfg = ContextoConfig(max_entidades=3)
    ctx4 = construir_contexto(modelo, tarefa, cfg)
    print(f"14. budget 3: {[e.id for e in ctx4.entidades]} "
          f"+ {len(ctx4.excluidas)} excluídas")

    amb = construir_contexto(
        modelo, ContextoTarefa(objetivo="x", alvo="Zzz"))
    print(f"15. ambiguidade: {amb.ambiguidade.get('status')}")

    op = intent_para_operacao(it)
    print(f"16. operação: {op.tipo} alvo={op.alvo.nome}")
    print("17. planner: ids relevantes =",
          [e.id for e in ctx.entidades[:3]])

    if visual:
        from elixx.studio import StudioApp, StudioWorkspace
        from elixx.studio.workspace_ui import montar_workspace_ui

        app = StudioApp()
        ws = StudioWorkspace(app)
        ws.criar_projeto(tmp / "loja2", "Loja")
        (tmp / "loja2" / "src" / "main.elixx").write_text(
            FONTE, encoding="utf-8")
        ws.analisar()
        ws.preview.executar(FONTE)
        ws.preview.selecionar("personagem:Juh")
        janela = montar_workspace_ui(ws)
        janela.after(4000, janela.destroy)
        janela.mainloop()
        print("visual: janela 4s (seção CONTEXTO DA TAREFA)")


if __name__ == "__main__":
    main(visual="--visual" in sys.argv)
