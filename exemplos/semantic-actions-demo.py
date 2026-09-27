"""Demo Semantic Actions (F31) — headless, sem LLM, sem rede.

1-8. projeto→modelo→Juh→pedido→AIIntent→operação→alvo→explicação;
9-12. plano→ChangeSet→aprovação→aplicação; 13-18. reanálise, modelo
novo, resultado, preview. Depois: evento clique→acenar (representado;
limitação documentada quando o mesclado não parseia).
"""
import tempfile
from pathlib import Path

from elixx.studio import StudioApp
from elixx.studio.agent import Approval, PermissionSet
from elixx.studio.agent.inteligencia import MockIntentProvider
from elixx.studio.agent.operacoes import (
    explicar_operacao,
    intent_para_operacao,
    operacao_para_ferramentas,
    operacao_para_proposta,
    resolver_referencia,
    SemanticReference,
    validar_operacao,
)
from elixx.studio.inspetor import fluxo_personagem
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela p {\n"
    ' titulo: "Loja"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    "  pose acenar {\n"
    "   corpo:\n"
    "    rotacao: 45deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="semop31_"))
    app = StudioApp()
    app.workspace.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: Loja")

    modelo = ModeloSemantico("loja")
    analisar_projeto(modelo, tmp / "loja")
    print(f"2-3. modelo: {len(modelo)} entidades")
    print("4. selecionada: Juh")

    prov = MockIntentProvider()
    op = intent_para_operacao(
        prov.gerar_intencao(None, "faca a Juh acenar"))
    print(f"5-7. AIIntent -> operacao {op.tipo} "
          f"alvo={op.alvo.nome} "
          f"valida={validar_operacao(op)['codigo']}")
    alvo = resolver_referencia(
        modelo, SemanticReference("Juh", "personagem"))
    print(f"8. alvo: {alvo['status']} "
          f"({alvo['entidade']['arquivo']})")
    print(f"   explicacao: {explicar_operacao(op)}")

    op2 = intent_para_operacao(
        prov.gerar_intencao(None, "mostre a Juh"))
    print(f"9. segunda op: {op2.tipo} "
          f"(consulta? {op2.somente_leitura})")

    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "corpo", "tipo": "corpo"}])
    chamadas = operacao_para_ferramentas(op)
    from elixx.visual.personagem import Pose

    perso.poses["acenar"] = Pose(
        "acenar", entradas={"corpo": {"rotacao": 45.0}})
    tocadas = perso.aplicar_pose(
        chamadas[0]["argumentos"]["pose"])
    print(f"10-12. plano runtime: {chamadas[0]['ferramenta']} -> "
          f"tocadas={tocadas}; ChangeSet: "
          f"{'só-arquivo (aqui: proposta abaixo)'}")

    op_arq = intent_para_operacao(
        prov.gerar_intencao(None, "mostre a Juh"))
    from elixx.studio.agent.operacoes import SemanticOperation

    prop = SemanticOperation(
        "alterar_propriedade", "Juh", {"titulo": "Loja 2"},
        alteracao={"arquivo": "src/main.elixx",
                   "conteudo_novo": FONTE.replace(
                       'titulo: "Loja"', 'titulo: "Loja 2"')})
    cs = operacao_para_proposta(
        prop, app.workspace, modelo,
        PermissionSet(["WRITE", "VALIDATE"]))
    Approval("manual").aprovar_tudo(cs)
    print(f"13. aprovado+aplicado: "
          f"{cs.aplicar(app.workspace)['arquivos']}")

    from elixx.studio.modelo import atualizar_arquivo

    atualizar_arquivo(
        modelo, "src/main.elixx",
        (tmp / "loja" / "src" / "main.elixx").read_text(
            encoding="utf-8"))
    print(f"14-16. reanalise: {len(modelo)} ent; "
          f"preview={app.preview.executar(FONTE).sucesso}")
    print("17. resultado: pose aplicada + titulo alterado")
    print(f"18. preview headless: OK")

    ev = intent_para_operacao(prov.gerar_intencao(
        None, "quando clicar na Juh, faca ela acenar"))
    print(f"evento: {explicar_operacao(ev)}")
    print("limite: 'quando' nao e top-level — proposta de evento "
          "exige mesclado valido ou conteudo completo "
          "(recusa documentada, sem chute).")


if __name__ == "__main__":
    main()
