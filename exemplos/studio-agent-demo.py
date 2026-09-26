"""Demo Studio Agent (F26) — headless, sem LLM, sem rede.

Fluxo: criar projeto → contexto → intenção → plano → ChangeSet →
mostrar → aprovar → aplicar → validar → preview → diagnóstico →
resultado → histórico → desfazer. Depois: Juh → gesto → motion →
preview (via ferramentas de personagem).
"""
import tempfile
from pathlib import Path

from elixx.studio import StudioApp, StudioCommand
from elixx.studio.agent import (
    AgentContext,
    AgentHistory,
    AgentTask,
    Approval,
    MockAgentProvider,
    PermissionSet,
    ToolRegistry,
    executar_tarefa,
)
from elixx.studio.agent.tarefa import (
    etapa_aprovacao,
    etapa_ferramentas,
    etapa_intencao,
    etapa_plano,
    etapa_validar_preview,
)
from elixx.studio.inspetor import fluxo_personagem
from elixx.studio.integracao_agent import AgentAmbiente, AgentStudioBridge


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="agent_demo_"))
    app = StudioApp()
    app.workspace.criar_projeto(tmp / "loja", "Loja")

    # 1-2. projeto + contexto mínimo
    bridge = AgentStudioBridge(app)
    ctx = bridge.contexto_minimo()
    ctx.adicionar_arquivo("src/main.elixx", "janela p {}\n")
    print(f"1-2. contexto: {ctx.tamanho()}")

    # 3-4. intenção + plano (Mock, sem LLM)
    task = bridge.enviar_tarefa("criar tela de boas-vindas")
    provider = MockAgentProvider()
    etapa_intencao(task, provider, ctx)
    print(f"3. intencao: {task.intencao.tipo}")
    amb = AgentAmbiente(app, permissoes=PermissionSet(
        ["READ", "WRITE", "VALIDATE", "PREVIEW"]), contexto=ctx)
    amb.registro = ToolRegistry(amb.permissoes)
    # plano manual com mudança real (Mock não adivinha arquivos)
    from elixx.studio.agent import AgentIntent, AgentPlan, PlanStep

    task.intencao = AgentIntent("criar_cena",
                                objetivo="tela de boas-vindas")
    task.transitar("analisando")
    task.plano = AgentPlan(task.intencao, [
        PlanStep("criar", "criar tela",
                 ferramenta="criar_arquivo",
                 argumentos={"caminho": "src/boas.elixx",
                             "conteudo_novo":
                             "janela p {\n titulo: \"Oi\"\n}\n"},
                 risco="baixo"),
        PlanStep("prev", "prever", ferramenta="executar_preview",
                 argumentos={"caminho": "src/main.elixx"},
                 dependencias=["criar"], risco="baixo")])
    task.transitar("planejando")
    print(f"4. plano: {task.plano.ordem_execucao()}")

    # 5-8. ferramentas → changeset → mostrar → aprovar → aplicar
    etapa_ferramentas(task, amb.registro, amb)
    print(f"5-6. changeset: {task.changeset.revisar()}")
    Approval("manual").aprovar_tudo(task.changeset)
    print("7-8. aprovado e pronto p/ aplicar")

    # 9-12. validar → preview → diagnóstico → resultado
    etapa_validar_preview(task, amb)
    print(f"9-11. estado={task.estado} "
          f"sucesso={task.resultado.sucesso} "
          f"diagnosticos={len(task.diagnosticos)}")
    print(f"12. resultado: {task.resultado.resumo}")

    # 13-14. histórico + desfazer
    hist = AgentHistory()
    hist.registrar(task)
    print(f"13. historico: {len(hist.listar())} tarefa(s)")
    task.changeset.desfazer(app.workspace)
    print(f"14. desfeito: existe=" +
          str(app.workspace.existe("src/boas.elixx")))

    # Juh → gesto → motion → preview (ferramentas de personagem)
    rig, perso, _drig = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco"},
    ])
    amb2 = AgentAmbiente(
        app, permissoes=PermissionSet(["PREVIEW"]),
        personagens={"Juh": perso}, rig=rig,
        contexto=AgentContext("Loja"))
    amb2.registro = ToolRegistry(amb2.permissoes)
    reg = amb2.registro
    from elixx.studio.agent import executar_ferramenta

    g = executar_ferramenta(reg, "personagem_gesto",
                            {"gesto": "acenar"}, amb2)
    print(f"Juh: gesto={g['gesto']} passos={g['passos']}")
    t = executar_ferramenta(reg, "personagem_transform",
                            {"personagem": "Juh", "parte": "tronco",
                             "props": {"rotacao": 5.0}}, amb2)
    print(f"Juh: transform tocadas={t['tocadas']}")

    # pipeline completo de uma vez (modo manual pré-aprovado)
    task2 = AgentTask("diagnosticar")
    task2.intencao = provider.gerar_intencao(ctx, "ver erros")
    task2.transitar("analisando")
    print(f"extra: intencao direta={task2.intencao.tipo}")
    _ = StudioCommand  # (porta única de comandos F25)
    print("demo OK (sem LLM, sem rede)")


if __name__ == "__main__":
    main()
