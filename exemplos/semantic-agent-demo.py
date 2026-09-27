"""Demo Semantic Agent Loop (F28) — headless, sem LLM, sem rede.

1. projeto; 2. analisar; 3. modelo; 4. consultar; 5. mostrar;
6. contexto; 7. plano; 8. mostrar; 9. ChangeSet; 10. mostrar;
11. aprovar; 12. aplicar; 13. reanalisar; 14. modelo atualizado;
15. diferença.
"""
import tempfile
from pathlib import Path

from elixx.studio import StudioApp
from elixx.studio.agent import Approval
from elixx.studio.agent.loop import (
    PlanoSemantico,
    construir_contexto_semantico,
    consultar_modelo,
    diff_legivel,
    gerar_changeset,
    reanalisar_modelo,
    resolver_alvo,
    verificar_precondicoes,
)
from elixx.studio.agent.intencao import AgentIntent
from elixx.studio.agent.permissao import PermissionSet
from elixx.studio.modelo import (
    ModeloSemantico,
    analisar_projeto,
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


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="loop28_"))
    app = StudioApp()
    app.workspace.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto criado")

    modelo = ModeloSemantico("loja")
    total = analisar_projeto(modelo, tmp / "loja")
    print(f"2-3. modelo: {total['entidades']} entidades, "
          f"{total['relacoes']} relacoes")

    out = consultar_modelo(modelo, "nome", nome="Juh")
    print(f"4-5. consulta Juh: {out['total']} resultado(s): "
          f"{[r['id'] for r in out['resultados']]}")

    alvo = resolver_alvo(modelo, "Juh", "personagem")
    ctx = construir_contexto_semantico(
        modelo, [alvo["entidade"]["id"]])
    print(f"6. contexto: {len(ctx.entidades)} ent, "
          f"{len(ctx.relacoes)} rel")

    plano = PlanoSemantico(
        AgentIntent("criar_cena", objetivo="tela ajuda"),
        alvo=alvo, entidades=[alvo["entidade"]["id"]],
        alteracoes_propostas=[{
            "arquivo": "src/ajuda.elixx", "operacao": "criar",
            "conteudo_novo": "janela q {\n titulo: \"Q\"\n}\n",
            "descricao": "tela ajuda", "risco": "baixo"}])
    print(f"7-8. plano: alvo={plano.alvo['status']} "
          f"alteracoes={len(plano.alteracoes_propostas)}")

    pre = verificar_precondicoes(
        plano, app.workspace,
        PermissionSet(["READ", "WRITE", "VALIDATE"]))
    print(f"   pre-condicoes: {all(c['ok'] for c in pre)}")
    cs = gerar_changeset(plano)
    print(f"9-10. changeset: {cs.revisar()}")

    Approval("manual").aprovar_tudo(cs)
    print("11. aprovado (manual explícito)")
    aplicadas = cs.aplicar(app.workspace)
    print(f"12. aplicado: {aplicadas['arquivos']}")

    rean = reanalisar_modelo(modelo, app.workspace,
                             aplicadas["arquivos"])
    print(f"13-14. modelo: {len(modelo)} entidades; "
          f"janela:q presente={'janela:q' in modelo}")
    print(f"15. diff: {diff_legivel(rean['diff'])}")


if __name__ == "__main__":
    main()
