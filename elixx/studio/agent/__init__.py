"""ELiXX Studio Agent (Fase 26) — fundação, não LLM.

"A Fase 26 implementa a infraestrutura do Agent, não um LLM."

"O Agent trabalha sobre o modelo estruturado do ELiXX, não sobre
cliques arbitrários na interface."
"""
from elixx.studio.agent.aprovacao import Approval, pode_auto_aprovar
from elixx.studio.agent.contexto import AgentContext
from elixx.studio.agent.diagnostico import AgentDiagnostic
from elixx.studio.agent.ferramentas import (
    AgentTool,
    ToolRegistry,
    executar_ferramenta,
)
from elixx.studio.agent.historico import AgentHistory
from elixx.studio.agent.intencao import AgentIntent
from elixx.studio.agent.mudancas import AgentChange, ChangeSet
from elixx.studio.agent.permissao import PermissionSet
from elixx.studio.agent.plano import AgentPlan, PlanStep
from elixx.studio.agent.provider import (
    AgentProvider,
    MockAgentProvider,
    NullAgentProvider,
    StructuredAgentProvider,
)
from elixx.studio.agent.inteligencia import (
    AgentChat,
    IntentContext,
    IntelligenceProvider,
    MockIntentProvider,
    ProviderRegistry,
    contexto_de_intencao,
    explicar,
    intent_para_agentintent,
    intent_para_ferramentas,
    validar_intent,
)
from elixx.studio.agent.loop import (
    PlanoSemantico,
    SemanticContext,
    consultar_modelo,
    construir_contexto_semantico,
    diff_legivel,
    executar_loop,
    gerar_changeset,
    reanalisar_modelo,
    resolver_alvo,
    verificar_precondicoes,
)
from elixx.studio.agent.resultado import AgentResult
from elixx.studio.agent.tarefa import AgentTask, executar_tarefa

__all__ = [
    "Approval", "pode_auto_aprovar",
    "AgentContext",
    "AgentDiagnostic",
    "AgentTool", "ToolRegistry", "executar_ferramenta",
    "AgentHistory",
    "AgentIntent",
    "AgentChange", "ChangeSet",
    "PermissionSet",
    "AgentPlan", "PlanStep",
    "AgentProvider", "MockAgentProvider", "NullAgentProvider",
    "StructuredAgentProvider",
    "AgentResult",
    "AgentTask", "executar_tarefa",
    "AgentChat", "IntentContext", "IntelligenceProvider",
    "MockIntentProvider", "ProviderRegistry",
    "contexto_de_intencao", "explicar", "intent_para_agentintent",
    "intent_para_ferramentas", "validar_intent",
    "PlanoSemantico", "SemanticContext", "consultar_modelo",
    "construir_contexto_semantico", "diff_legivel",
    "executar_loop", "gerar_changeset", "reanalisar_modelo",
    "resolver_alvo", "verificar_precondicoes",
]
