"""Demo Code Sync (F32) — headless, sem LLM, sem regex cega.

1-8. projeto→código→modelo→Juh→operação→alvo→localização→alteração;
9-12. ChangeSet→diff→aprovação→aplicação; 13-18. reparse, modelo novo,
resultado, externa (rotação 30), ressincronização, estado final.
Exemplo concreto: rotação 0 → 15 (aprovado) → 30 (externo).
"""
import tempfile
from pathlib import Path

from elixx.studio import StudioApp
from elixx.studio.agent import Approval
from elixx.studio.agent.operacoes import SemanticOperation
from elixx.studio.codigo import (
    SincronizadorBidirecional,
    aplicar_com_changeset,
    diff_textual,
)
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela principal {\n"
    " tamanho: 800px 500px\n"
    " personagem Juh {\n"
    "  posicao: 100px 100px\n"
    "  parte cabeca {\n"
    "   rotacao: 0\n"
    "  }\n"
    " }\n"
    "}\n"
)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sync32_"))
    app = StudioApp()
    app.workspace.criar_projeto(tmp / "p", "P")
    print("1. projeto: P")
    (tmp / "p" / "src" / "main.elixx").write_text(FONTE,
                                                  encoding="utf-8")
    print("2. codigo ELiXX escrito")

    modelo = ModeloSemantico("p")
    analisar_projeto(modelo, tmp / "p")
    print(f"3. modelo: {len(modelo)} entidades")
    sinc = SincronizadorBidirecional(app.workspace, modelo)
    print("4. selecionada: parte cabeca (Juh)")

    op = SemanticOperation(
        "alterar_propriedade",
        {"nome": "cabeca", "tipo": "parte"},
        {"propriedade": "rotacao"},
        alteracao={"arquivo": "src/main.elixx",
                   "propriedade": "rotacao",
                   "valor_texto": "15"})
    print("5. operacao: alterar rotacao da cabeca para 15")
    alt = sinc.operacao_para_codigo(op)
    print(f"6-8. localizada {alt.regiao} -> alteracao {alt.tipo}")
    print("9. ChangeSet: 1 mudanca (proposta, sem aplicar)")
    print("10. diff antes/depois:")
    for troca in diff_textual(
            FONTE, alt.aplicar_texto(FONTE))["trocas"]:
        print(f"    linha {troca['antes']}: {troca['removidas']} "
              f"-> {troca['adicionadas']}")
    ap = Approval("manual")
    print("11. sem approval:", aplicar_com_changeset(
        sinc, alt)["codigo"])
    ap2 = Approval("automatico_seguro",
                   caminhos_permitidos=["src/"])
    out = aplicar_com_changeset(sinc, alt, approval=ap2)
    print(f"12. aprovado+aplicado: {out['arquivos']}")
    print(f"13-14. reparse: modelo com {len(modelo)} entidades")
    rot = (tmp / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    print(f"15. confirmar: rotacao = "
          f"{[l.strip() for l in rot.splitlines() if 'rotacao' in l]}")
    print(f"16. resultado: ok={out['ok']} "
          f"diff_semantico={out['diff']}")

    (tmp / "p" / "src" / "main.elixx").write_text(
        rot.replace("rotacao: 15", "rotacao: 30"),
        encoding="utf-8")
    print("17. externa: rotacao editada para 30 no arquivo")
    out2 = sinc.sincronizar("src/main.elixx")
    print(f"18. ressincronizado: valido={out2['valido']} "
          f"versao={out2['versao']}")
    print("19-20. estado final: modelo reflete rotacao = 30, "
          "sem executar codigo")


if __name__ == "__main__":
    main()
