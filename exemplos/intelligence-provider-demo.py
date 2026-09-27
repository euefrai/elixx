"""Demo Intelligence Provider (F30) — headless, sem LLM, sem rede.

1. projeto; 2. analisar; 3. contexto; 4. selecionar Juh;
5. pedido natural; 6. intent; 7. mostrar; 8. consulta F27;
9. plano; 10. ChangeSet; 11. mostrar; 12. aprovação;
13. aplicação; 14. reanálise; 15. resultado; 16. preview headless.
"""
import tempfile
from pathlib import Path

from elixx.studio import StudioApp
from elixx.studio.agent import Approval, PermissionSet
from elixx.studio.agent.inteligencia import (
    AgentChat,
    MockIntentProvider,
    contexto_de_intencao,
    explicar,
    intent_para_agentintent,
    intent_para_ferramentas,
    validar_intent,
)
from elixx.studio.agent.loop import (
    PlanoSemantico,
    gerar_changeset,
    resolver_alvo,
    verificar_precondicoes,
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
    tmp = Path(tempfile.mkdtemp(prefix="intent30_"))
    app = StudioApp()
    app.workspace.criar_projeto(tmp / "loja", "Loja")
    (tmp / "loja" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    print("1. projeto: Loja")

    modelo = ModeloSemantico("loja")
    total = analisar_projeto(modelo, tmp / "loja")
    print(f"2. modelo: {total['entidades']} entidades")
    ctx = contexto_de_intencao(
        "Loja", "src/main.elixx",
        {"tipo": "personagem", "nome": "Juh",
         "arquivo": "src/main.elixx"})
    print(f"3. contexto: {ctx['selecionado']}")
    print("4. selecionada: Juh (personagem)")

    pedido = "faça a Juh acenar"
    print(f"5. pedido: {pedido!r}")
    chat = AgentChat(MockIntentProvider())
    resposta = chat.enviar(pedido, modelo)
    inter = resposta["intencao"]
    print(f"6-7. intent: acao={inter['acao']} alvo={inter['alvo']} "
          f"params={inter['parametros']}")

    alvo = resolver_alvo(modelo, "Juh", "personagem")
    print(f"8. consulta F27: {alvo['status']} "
          f"({alvo['entidade']['arquivo']})")
    aintent = intent_para_agentintent(
        MockIntentProvider().gerar_intencao(None, pedido))
    plano = PlanoSemantico(
        aintent, alvo=alvo,
        entidades=[alvo["entidade"]["id"]],
        alteracoes_propostas=[{
            "arquivo": "src/gesto.elixx", "operacao": "criar",
            "conteudo_novo": "janela q {\n titulo: \"Q\"\n}\n",
            "descricao": "gesto acenar", "risco": "baixo"}])
    print(f"9. plano: alvo={plano.alvo['status']}")
    pre = verificar_precondicoes(
        plano, app.workspace,
        PermissionSet(["READ", "WRITE", "VALIDATE"]))
    print(f"   pre-condicoes: {all(c['ok'] for c in pre)}")
    cs = gerar_changeset(plano)
    print(f"10-11. changeset: {cs.revisar()}")
    Approval("manual").aprovar_tudo(cs)
    print("12. aprovado (manual explícito)")
    aplicadas = cs.aplicar(app.workspace)
    print(f"13. aplicado: {aplicadas['arquivos']}")

    from elixx.studio.modelo import atualizar_arquivo

    atualizar_arquivo(
        modelo, "src/gesto.elixx",
        (tmp / "loja" / "src" / "gesto.elixx").read_text(
            encoding="utf-8"))
    print(f"14. reanalise: {len(modelo)} entidades; "
          f"janela:q={'janela:q' in modelo}")
    print(f"15. preview headless: "
          f"{app.preview.executar(FONTE).sucesso}")

    # pose via ferramentas (Juh acena de verdade no F12)
    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "corpo", "tipo": "corpo"}])
    it = MockIntentProvider().gerar_intencao(None, pedido)
    assert validar_intent(it)["valido"] is True
    chamadas = intent_para_ferramentas(it)
    print(f"extra. ferramenta: {chamadas[0]['ferramenta']} "
          f"{chamadas[0]['argumentos']}")
    print("extra. explicacao:",
          explicar(pedido, it, alvo)["intencao"])


if __name__ == "__main__":
    main()
