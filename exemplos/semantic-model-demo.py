"""Demo Semantic Project Model (F27) — headless, sem LLM, sem rede.

1. projeto temporário; 2. pequeno .elixx; 3. analisar; 4. modelo;
5. entidades; 6. por nome; 7. por tipo; 8. relações; 9. localizar Juh;
10. origem; 11. snapshot; 12. alterar arquivo; 13. atualizar;
14. diferenças.
"""
import tempfile
from pathlib import Path

from elixx.studio.modelo import (
    ConsultaSemantica,
    ModeloSemantico,
    SnapshotSemantico,
    analisar_projeto,
    atualizar_arquivo,
    comparar_snapshots,
    validar_modelo,
)

FONTE = (
    "janela p {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    '   imagem: "corpo.png"\n'
    "  }\n"
    "  pose neutra {\n"
    "   corpo:\n"
    "    rotacao: 0deg\n"
    "  }\n"
    " }\n"
    " botao entrar {\n"
    '  texto: "Entrar"\n'
    " }\n"
    "}\n"
)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sem27_"))
    (tmp / "src").mkdir()
    (tmp / "src" / "main.elixx").write_text(FONTE, encoding="utf-8")
    print(f"1-2. projeto em {tmp.name} (+ main.elixx)")

    modelo = ModeloSemantico("loja")
    total = analisar_projeto(modelo, tmp)
    print(f"3-4. analisado: {total['arquivos']} arquivo(s), "
          f"{total['entidades']} entidades, "
          f"{total['relacoes']} relacoes; "
          f"valido={validar_modelo(modelo)['valido']}")

    q = ConsultaSemantica(modelo)
    print("5. entidades:",
          sorted(e.id for e in modelo.entidades()))
    print("6. por nome Juh:",
          [e.id for e in q.encontrar_por_nome("Juh")])
    print("7. personagens:",
          [e.id for e in q.encontrar_por_tipo("personagem")])
    print("8. relacoes de Juh:",
          [(r.tipo, r.destino) for r in
           q.relacoes_de("personagem:Juh")])

    viz = q.vizinhanca("personagem:Juh")
    print(f"9-10. Juh em {viz['entidade']['arquivo']}:"
          f"{viz['entidade']['linha']} "
          f"({len(viz['de'])} saidas, {len(viz['para'])} entradas)")

    antes = SnapshotSemantico.de_modelo(modelo, versao=1)
    print(f"11. snapshot v{antes.versao}: "
          f"{len(antes.entidades())} entidades")

    (tmp / "src" / "main.elixx").write_text(
        FONTE.replace('titulo: "Loja"', 'titulo: "Loja 2"')
        + "janela q {\n titulo: \"Q\"\n}\n",
        encoding="utf-8")
    print("12. arquivo alterado (+ janela q)")
    out = atualizar_arquivo(
        modelo, "src/main.elixx",
        (tmp / "src" / "main.elixx").read_text(encoding="utf-8"))
    print(f"13. atualizado: {out['entidades']} entidades")
    diff = comparar_snapshots(
        antes, SnapshotSemantico.de_modelo(modelo, versao=2))
    print(f"14. diff: +{diff['adicionados']} "
          f"-{diff['removidos']} ~{diff['alterados']}")


if __name__ == "__main__":
    main()
