"""Ponte Studio ↔ Agent (F26) — integração sem tornar Agent obrigatório.

O Studio funciona normalmente com o Agent desativado (ponte ausente =
comportamento F25 intacto). A ponte expõe: enviar tarefa, estado,
plano, mudanças, aprovação, resultado e diagnósticos — só API interna
nesta fase (UI mínima de inspeção futura).
"""
from __future__ import annotations

from ..erros import ErroELiXX
from .agent.aprovacao import Approval
from .agent.contexto import AgentContext
from .agent.ferramentas import ToolRegistry
from .agent.historico import AgentHistory
from .agent.permissao import PermissionSet
from .agent.provider import MockAgentProvider
from .agent.tarefa import AgentTask, executar_tarefa

__all__ = ["AgentStudioBridge"]


class AgentAmbiente:
    """Ambiente das ferramentas (workspace + preview + personagens)."""

    def __init__(self, app, permissoes=None, personagens=None,
                 rig=None, contexto=None) -> None:
        self.app = app
        self.workspace = app.workspace
        self.preview = app.preview
        self.permissoes = permissoes
        self.personagens = dict(personagens or {})
        self.rig = rig
        self.contexto = contexto
        self.registro = ToolRegistry(
            permissoes or PermissionSet(["READ", "VALIDATE"]))


class AgentStudioBridge:
    """Agent plugado ao StudioApp (opcional, sem dependência reversa)."""

    def __init__(self, app, provider=None, approval=None,
                 permissoes=None) -> None:
        from .app import StudioApp

        if not isinstance(app, StudioApp):
            raise ErroELiXX("Ponte espera StudioApp.")
        self.app = app
        self.provider = provider or MockAgentProvider()
        self.approval = approval or Approval("manual")
        self.permissoes = permissoes or PermissionSet(
            ["READ", "WRITE", "VALIDATE", "COMPILE", "PREVIEW"])
        self.historico = AgentHistory()
        self.tarefa_atual: AgentTask | None = None

    @property
    def ativo(self) -> bool:
        return self.tarefa_atual is not None and \
            self.tarefa_atual.estado not in ("concluida", "falhou",
                                             "cancelada")

    def contexto_minimo(self) -> AgentContext:
        """Projeto + arquivo ativo (incremental; resto sob demanda)."""
        ws = self.app.workspace
        ctx = AgentContext(
            ws.projeto.nome if ws.aberto else "",
            self.app.documentos.ativo or "")
        if self.app.documentos.ativo:
            doc = self.app.documentos.obter(
                self.app.documentos.ativo)
            ctx.adicionar_arquivo(doc.caminho, doc.texto)
        return ctx

    def enviar_tarefa(self, objetivo: str,
                      personagens=None) -> AgentTask:
        """Cria a tarefa (não executa: pipeline é explícito)."""
        task = AgentTask(objetivo)
        self.tarefa_atual = task
        self.app.logs.info(f"Agent: tarefa {task.id} criada.")
        self._ambiente_personagens = dict(personagens or {})
        return task

    def executar(self, task: AgentTask | None = None) -> AgentTask:
        """Roda o pipeline (aprovação manual precisa de aval prévio)."""
        task = task or self.tarefa_atual
        if task is None:
            raise ErroELiXX("Agent: nenhuma tarefa enviada.")
        ambiente = AgentAmbiente(
            self.app, permissoes=self.permissoes,
            personagens=getattr(self, "_ambiente_personagens",
                                {}),
            contexto=self.contexto_minimo())
        ambiente.registro = ToolRegistry(self.permissoes)
        return executar_tarefa(task, ambiente, self.provider,
                               self.approval, self.historico)

    def estado(self) -> dict:
        if self.tarefa_atual is None:
            return {"ativa": False}
        t = self.tarefa_atual
        return {"ativa": self.ativo, "id": t.id,
                "estado": t.estado, "progresso": t.progresso,
                "objetivo": t.objetivo}

    def plano_atual(self) -> dict:
        if self.tarefa_atual is None or \
                self.tarefa_atual.plano is None:
            raise ErroELiXX("Agent: sem plano na tarefa atual.")
        return self.tarefa_atual.plano.to_dict()

    def mudancas_atuais(self) -> list[dict]:
        if self.tarefa_atual is None or \
                self.tarefa_atual.changeset is None:
            raise ErroELiXX("Agent: sem changeset na tarefa atual.")
        return self.tarefa_atual.changeset.revisar()

    def aprovar(self) -> dict:
        if self.tarefa_atual is None or \
                self.tarefa_atual.changeset is None:
            raise ErroELiXX("Agent: nada para aprovar.")
        self.approval.aprovar_tudo(self.tarefa_atual.changeset)
        self.app.logs.info("Agent: changeset aprovado.")
        return {"aprovado": True}

    def resultado_atual(self) -> dict:
        if self.tarefa_atual is None or \
                self.tarefa_atual.resultado is None:
            raise ErroELiXX("Agent: sem resultado ainda.")
        return self.tarefa_atual.resultado.to_dict()

    def diagnosticos_atuais(self) -> list[dict]:
        if self.tarefa_atual is None:
            return []
        return [d.to_dict() if hasattr(d, "to_dict") else dict(d)
                for d in self.tarefa_atual.diagnosticos]

    def __repr__(self) -> str:
        return f"AgentStudioBridge(ativo={self.ativo})"
