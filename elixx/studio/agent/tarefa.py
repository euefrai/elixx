"""AgentTask + pipeline (F26) — máquina de estados testável por etapa.

pedido → contexto → intenção → plano → aprovação → changeset →
aplicação → validação → preview → diagnóstico → resultado.

Sem LLM: providers Mock/Structured geram intenção/plano; ferramentas
executam com permissão; escrita só via ChangeSet aprovado.
"""
from __future__ import annotations

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["ESTADOS_TAREFA", "AgentTask", "executar_tarefa",
           "etapa_intencao", "etapa_plano", "etapa_ferramentas",
           "etapa_aprovacao", "etapa_validar_preview"]

ESTADOS_TAREFA = ("criada", "analisando", "planejando",
                  "aguardando_aprovacao", "aplicando", "validando",
                  "executando", "observando", "corrigindo",
                  "concluida", "falhou", "cancelada")
"""Estados da tarefa (ordem do pipeline; sem salto arbitrário)."""


class AgentTask:
    """Tarefa: objetivo + intenção + plano + changeset + resultado."""

    _contador = 0

    def __init__(self, objetivo: str, tarefa_id: str = "") -> None:
        AgentTask._contador += 1
        self.id = (str(tarefa_id).strip()
                   or f"tarefa_{AgentTask._contador:03d}")
        if not self.id:
            raise ErroELiXX("Agent: tarefa precisa de id.")
        self.objetivo = str(objetivo)
        self.intencao = None
        self.plano = None
        self.changeset = None
        self.progresso = 0.0
        self.estado = "criada"
        self.eventos: list[dict] = []
        self.diagnosticos: list = []
        self.resultado = None
        self.saidas_ferramentas: list[dict] = []

    def transitar(self, novo: str) -> AgentTask:
        if novo not in ESTADOS_TAREFA:
            raise ErroELiXX(f'Agent: estado "{novo}" inválido.')
        ordem = list(ESTADOS_TAREFA)
        atual = ordem.index(self.estado)
        destino = ordem.index(novo)
        if novo in ("falhou", "cancelada"):
            pass  # terminal a qualquer momento (falha fechada)
        elif novo == "corrigindo" and self.estado not in (
                "observando", "validando"):
            raise ErroELiXX("Agent: corrigir só após observar.")
        elif destino < atual and novo not in ("falhou",
                                              "cancelada"):
            raise ErroELiXX(f'Agent: tarefa não volta de '
                            f'"{self.estado}" para "{novo}".')
        self.estado = novo
        return self

    def registrar_evento(self, evento: str,
                         dados: dict | None = None) -> None:
        carga = dict(dados or {})
        if not B.e_dado(carga):
            raise ErroELiXX("Agent: evento inválido.")
        self.eventos.append({"evento": B.id_valido(evento),
                             "dados": carga})

    def to_dict(self) -> dict:
        return {"id": self.id, "objetivo": self.objetivo,
                "estado": self.estado, "progresso": self.progresso,
                "eventos": list(self.eventos)}

    def __repr__(self) -> str:
        return f"AgentTask({self.id} {self.estado})"


# ----- etapas isoladas (cada uma testável sozinha) -----

def etapa_intencao(task: AgentTask, provider, contexto) -> AgentTask:
    """Pedido + contexto → intenção (analisando)."""
    from .provider import AgentProvider

    if not isinstance(provider, AgentProvider):
        raise ErroELiXX("Agent: provider inválido.")
    if not provider.disponivel():
        raise ErroELiXX(f'Agent: provider "{provider.nome}" '
                        "indisponível.")
    task.transitar("analisando")
    task.intencao = provider.gerar_intencao(contexto,
                                            task.objetivo)
    task.registrar_evento("intencao",
                          {"tipo": task.intencao.tipo})
    task.progresso = 0.2
    return task


def etapa_plano(task: AgentTask, provider, contexto=None
                ) -> AgentTask:
    """Intenção → plano validado (planejando)."""
    if task.intencao is None:
        raise ErroELiXX("Agent: sem intenção para planejar.")
    task.transitar("planejando")
    task.plano = provider.gerar_plano(task.intencao, contexto)
    task.registrar_evento("plano",
                          {"passos": len(task.plano.passos)})
    task.progresso = 0.4
    return task


def etapa_ferramentas(task: AgentTask, registro, ambiente
                      ) -> AgentTask:
    """Plano → saídas + ChangeSet proposto (sem tocar disco)."""
    from .ferramentas import executar_ferramenta
    from .mudancas import AgentChange, ChangeSet

    if task.plano is None:
        raise ErroELiXX("Agent: sem plano para executar.")
    mudancas = []
    for pid in task.plano.ordem_execucao():
        passo = task.plano.passo(pid)
        passo.transitar("executando")
        try:
            saida = executar_ferramenta(
                registro, passo.ferramenta,
                dict(passo.argumentos) | {"_passo": pid},
                ambiente)
        except ErroELiXX as exc:
            passo.transitar("falhou")
            task.registrar_evento("passo_falhou",
                                  {"passo": pid,
                                   "motivo": str(exc)[:200]})
            raise
        passo.transitar("concluido")
        task.saidas_ferramentas.append({"passo": pid,
                                        "saida": saida})
        if isinstance(saida, dict) and "mudanca" in saida:
            mudancas.append(AgentChange.from_dict(
                saida["mudanca"]))
    task.changeset = ChangeSet(mudancas)
    task.registrar_evento("changeset",
                          {"mudancas": len(mudancas)})
    task.progresso = 0.6
    return task


def etapa_aprovacao(task: AgentTask, approval) -> AgentTask:
    """ChangeSet → aprovado (manual exige `aprovar_tudo` antes)."""
    if task.changeset is None:
        raise ErroELiXX("Agent: sem changeset para aprovar.")
    task.transitar("aguardando_aprovacao")
    if approval.modo == "automatico_seguro":
        decisao = approval.decidir(task.changeset)
        if (decisao["pendentes"] or decisao["recusadas"]
                or len(decisao["aprovadas"])
                != len(task.changeset.mudancas)):
            raise ErroELiXX("Agent: auto-aprovação parcial recusada "
                            "(operação perigosa exige manual).")
        task.changeset.aprovar()
    elif approval.modo == "bloqueado":
        raise ErroELiXX("Agent: modo bloqueado não aplica.")
    else:
        if task.changeset.estado != "aprovado":
            raise ErroELiXX("Agent: modo manual exige aprovação "
                            "explícita (`aprovar_tudo`) antes.")
    task.registrar_evento("aprovacao", {"modo": approval.modo})
    task.progresso = 0.7
    return task


def etapa_validar_preview(task: AgentTask, ambiente) -> AgentTask:
    """Aplicar → validar → preview → observar (diagnósticos)."""
    from ..editor import diagnosticar_texto
    from .diagnostico import AgentDiagnostic

    ws = getattr(ambiente, "workspace", None)
    if ws is None:
        raise ErroELiXX("Agent: ambiente sem workspace.")
    task.transitar("aplicando")
    aplicadas = task.changeset.aplicar(ws)
    task.registrar_evento("aplicacao", aplicadas)
    task.transitar("validando")
    diagnosticos = []
    for caminho in aplicadas.get("arquivos", []):
        try:
            texto = ws.resolver(caminho).read_text(
                encoding="utf-8")
        except OSError:
            continue
        for d in diagnosticar_texto(texto, caminho):
            diagnosticos.append(AgentDiagnostic.do_studio(d))
    task.diagnosticos = diagnosticos
    task.transitar("executando")
    preview = getattr(ambiente, "preview", None)
    entrada = task.changeset.mudancas[0].caminho if \
        task.changeset.mudancas else ""
    saida_preview: dict = {}
    if preview is not None and entrada:
        try:
            texto = ws.resolver(entrada).read_text(
                encoding="utf-8")
            resultado = preview.executar(texto, entrada)
            saida_preview = resultado.to_dict()
        except OSError:
            saida_preview = {}
    task.transitar("observando")
    erros = [d for d in diagnosticos if d.severidade == "error"]
    ok_preview = (saida_preview.get("sucesso", True)
                  if saida_preview else True)
    from .resultado import AgentResult

    task.resultado = AgentResult(
        sucesso=not erros and ok_preview,
        resumo=(f"{len(aplicadas.get('arquivos', []))} arquivo(s), "
                f"{len(erros)} erro(s)."),
        alteracoes=[{"caminho": m.caminho,
                     "operacao": m.operacao}
                    for m in task.changeset.mudancas],
        arquivos=aplicadas.get("arquivos", []),
        diagnosticos=diagnosticos,
        preview=saida_preview.get("resumo", {}))
    task.progresso = 1.0
    task.transitar("concluida" if task.resultado.sucesso
                   else "falhou")
    task.registrar_evento("resultado",
                          {"sucesso": task.resultado.sucesso})
    return task


def executar_tarefa(task: AgentTask, ambiente, provider=None,
                    approval=None, historico=None) -> AgentTask:
    """Pipeline completo (cada etapa isolada acima é reutilizada)."""
    from .aprovacao import Approval
    from .provider import MockAgentProvider

    if not isinstance(task, AgentTask):
        raise ErroELiXX("Agent: tarefa inválida.")
    provider = provider or MockAgentProvider()
    approval = approval or Approval("manual")
    contexto = getattr(ambiente, "contexto", None)
    try:
        etapa_intencao(task, provider, contexto)
        etapa_plano(task, provider, contexto)
        registro = getattr(ambiente, "registro", None)
        if registro is None:
            from .ferramentas import ToolRegistry
            from .permissao import PermissionSet

            registro = ToolRegistry(PermissionSet(
                ["READ", "WRITE", "VALIDATE", "COMPILE",
                 "PREVIEW"]))
        etapa_ferramentas(task, registro, ambiente)
        etapa_aprovacao(task, approval)
        etapa_validar_preview(task, ambiente)
    except ErroELiXX as exc:
        if task.estado not in ("concluida", "falhou",
                               "cancelada"):
            task.transitar("falhou")
        task.registrar_evento("falha", {"motivo": str(exc)[:200]})
        raise
    finally:
        if historico is not None and task.estado in (
                "concluida", "falhou"):
            historico.registrar(task)
    return task
