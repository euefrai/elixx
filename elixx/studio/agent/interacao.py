"""Agent Interaction (Fase 37) — sessão, palette e seleção global.

O chat é interface; a verdade continua em Modelo/Contexto/Tools/
Operations/Planner/Code Sync. Sem LLM: provider Mock/determinístico,
pipeline real F30→F34→tools→F31→F33 (proposta, sem aplicar sozinho).
"""
from __future__ import annotations

import unicodedata

from ...erros import ErroELiXX
from . import _base as B

__all__ = [
    "TIPOS_MSG", "ESTADOS_SESSAO", "COMANDOS_PALETTE",
    "AgentMessage", "AgentSession", "CommandPalette",
    "resumo_chips", "selecao_global",
]

TIPOS_MSG = ("USER", "AGENT", "SYSTEM", "TOOL", "RESULT", "ERROR")
"""Tipos de mensagem (sem chat genérico: estrutura fixa)."""

ESTADOS_SESSAO = ("IDLE", "THINKING", "CONTEXT", "TOOLS",
                  "PLANNING", "REVIEW", "APPLYING", "DONE",
                  "ERROR", "CANCELLED")
"""Estados da sessão (cancelável; erro sem traceback)."""

COMANDOS_PALETTE = (
    ("abrir_preview", "Abrir Preview"),
    ("abrir_inspector", "Abrir Inspector"),
    ("abrir_arquivo", "Abrir arquivo"),
    ("abrir_codigo", "Abrir código"),
    ("mostrar_preview", "Mostrar Preview"),
    ("mostrar_inspector", "Mostrar Inspector"),
    ("focar_agent", "Focar Agent"),
    ("focar_codigo", "Focar código"),
    ("focar_preview", "Focar Preview"),
    ("executar_projeto", "Executar projeto"),
    ("parar_projeto", "Parar projeto"),
    ("salvar", "Salvar"),
    ("executar", "Executar"),
    ("parar", "Parar"),
    ("alternar_compacto", "Alternar modo compacto"),
    ("alternar_layout", "Alternar layout"),
    ("nova_sessao", "Nova sessão do Agent"),
    ("consultar_contexto", "Consultar contexto"),
    ("mostrar_tools", "Mostrar ferramentas"),
    ("mostrar_plano", "Mostrar plano"),
    ("mostrar_changes", "Mostrar mudanças"),
    ("mostrar_raciocinio", "Mostrar raciocínio"),
    ("atualizar_modelo", "Atualizar modelo"),
    ("sincronizar_projeto", "Sincronizar projeto"),
    ("inspecionar_selecao", "Inspecionar seleção"),
    ("consultar_entidade", "Consultar entidade"),
    ("mostrar_codigo", "Mostrar código"),
    ("mostrar_relacoes", "Mostrar relações"),
    ("adicionar_contexto", "Adicionar ao contexto"),
    ("remover_contexto", "Remover do contexto"),
)
"""Comandos disponíveis (ids estáveis; execução via StudioApp)."""


def _norm(texto: str) -> str:
    base = unicodedata.normalize(
        "NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


class AgentMessage:
    """Mensagem com ordem lógica (contador; sem relógio)."""

    _contador = 0

    def __init__(self, tipo: str, conteudo: str, msg_id: str = "",
                 estado: str = "pronto",
                 referencias: list | None = None) -> None:
        if tipo not in TIPOS_MSG:
            raise ErroELiXX(f"Mensagem: tipo {tipo} inválido.")
        self.tipo = tipo
        self.conteudo = str(conteudo)[:2000]
        AgentMessage._contador += 1
        self.ordem = AgentMessage._contador
        self.id = str(msg_id).strip() or f"msg_{self.ordem:04d}"
        if estado not in ("pronto", "processando", "erro"):
            raise ErroELiXX("Mensagem: estado inválido.")
        self.estado = estado
        refs = [dict(r) for r in (referencias or [])]
        for r in refs:
            if not B.e_dado(r):
                raise ErroELiXX("Mensagem: referência inválida.")
        self.referencias = refs

    def to_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo,
                "conteudo": self.conteudo, "ordem": self.ordem,
                "estado": self.estado,
                "referencias": list(self.referencias)}

    @staticmethod
    def from_dict(dados: dict) -> AgentMessage:
        if not isinstance(dados, dict):
            raise ErroELiXX("Mensagem precisa de dict.")
        msg = AgentMessage(dados.get("tipo", "SYSTEM"),
                           dados.get("conteudo", ""),
                           msg_id=dados.get("id", ""),
                           estado=dados.get("estado", "pronto"),
                           referencias=dados.get(
                               "referencias") or [])
        msg.ordem = int(dados.get("ordem", msg.ordem))
        return msg

    def __repr__(self) -> str:
        return f"AgentMessage({self.tipo} {self.id})"


class AgentSession:
    """Sessão: mensagens + tarefa + contexto + trace + plano."""

    _contador = 0

    def __init__(self, sessao_id: str = "") -> None:
        AgentSession._contador += 1
        self.id = str(sessao_id).strip() or \
            f"agent_{AgentSession._contador:03d}"
        self.mensagens: list[AgentMessage] = []
        self.estado = "IDLE"
        self.tarefa = ""
        self.contexto = None
        self.trace = None
        self.plano = None
        self.proposta = None
        self.erro = ""

    def _dizer(self, tipo: str, conteudo: str, **kwargs
               ) -> AgentMessage:
        msg = AgentMessage(tipo, conteudo, **kwargs)
        self.mensagens.append(msg)
        return msg

    def _estado(self, novo: str) -> None:
        if novo not in ESTADOS_SESSAO:
            raise ErroELiXX(f"Sessão: estado {novo}.")
        self.estado = novo

    def enviar(self, texto: str, ambiente=None) -> dict:
        """Pipeline real: intent→contexto→tools→operação→plano."""
        from .contexto_tarefa import (ContextoTarefa,
                                      construir_contexto)
        from .ferramentas_semanticas import (
            AgentToolCall, SemanticPermissions,
            SemanticToolRegistry, ToolTrace, executar_chamada)
        from .inteligencia import MockIntentProvider
        from .operacoes import intent_para_operacao
        from .planejamento import PlanoTarefa, construir_plano

        if not isinstance(texto, str) or not texto.strip():
            raise ErroELiXX("Sessão: tarefa vazia.")
        if ambiente is None:
            raise ErroELiXX("Sessão: exige ambiente Studio.")
        modelo = getattr(ambiente, "modelo", None)
        if modelo is None:
            raise ErroELiXX("Sessão: ambiente sem modelo.")
        self._estado("THINKING")
        self.tarefa = texto.strip()[:500]
        self._dizer("USER", self.tarefa)
        try:
            intent = MockIntentProvider().gerar_intencao(
                None, self.tarefa)
            self._estado("CONTEXT")
            tarefa_ctx = ContextoTarefa(
                objetivo=self.tarefa,
                alvo=intent.personagem or intent.alvo or "",
                entidade_selecionada=str(getattr(
                    ambiente, "selecionado", "")),
                arquivo_atual=str(getattr(ambiente, "arquivo",
                                          "")))
            self.contexto = construir_contexto(modelo,
                                               tarefa_ctx)
            self._estado("TOOLS")
            registro = SemanticToolRegistry()
            permissoes = SemanticPermissions(["READ",
                                              "ANALYZE"])
            trace = ToolTrace()
            nome = intent.personagem or intent.alvo or ""
            for tool_id, args in (
                    ("buscar_entidade", {"nome": nome}),
                    ("consultar_relacoes",
                     {"id": f"personagem:{nome}"})):
                chamada = AgentToolCall(tool_id, args)
                trace.registrar(chamada)
                executar_chamada(registro, chamada, ambiente,
                                 permissoes)
            self.trace = trace
            self._dizer("TOOL",
                        f"{len(trace.chamadas)} tools executadas.")
            op = intent_para_operacao(intent)
            self._estado("PLANNING")
            plano = PlanoTarefa(self.tarefa, [op])
            construir_plano(plano)
            self.plano = plano
            self._estado("REVIEW")
            self._dizer(
                "AGENT",
                f"Encontrei {intent.personagem or intent.alvo}. "
                f"Plano com 1 operação ({op.tipo}).",
                referencias=[{"id": intent.personagem or ""}])
            return {"ok": True, "intencao": intent.tipo,
                    "operacao": op.tipo,
                    "entidades": len(self.contexto.entidades),
                    "estado": self.estado}
        except ErroELiXX as exc:
            self._estado("ERROR")
            self.erro = str(exc)[:300]
            self._dizer("ERROR", self.erro)
            return {"ok": False, "erro": self.erro,
                    "estado": self.estado}

    def cancelar(self) -> dict:
        if self.estado in ("DONE", "CANCELLED"):
            raise ErroELiXX("Sessão já encerrada.")
        self._estado("CANCELLED")
        self._dizer("SYSTEM", "Sessão cancelada (nada aplicado).")
        return {"estado": "CANCELLED"}

    def nova_sessao(self) -> dict:
        """Limpa conversa (nunca apaga arquivos do projeto)."""
        total = len(self.mensagens)
        self.mensagens = []
        self._estado("IDLE")
        self.tarefa = ""
        self.contexto = None
        self.trace = None
        self.plano = None
        self.proposta = None
        self.erro = ""
        return {"limpas": total}

    def aprovar_proposta(self) -> dict:
        if self.proposta is None:
            raise ErroELiXX("Sessão: sem proposta.")
        self._estado("APPLYING")
        return {"estado": "APPLYING"}

    def to_dict(self) -> dict:
        return {"id": self.id, "estado": self.estado,
                "tarefa": self.tarefa, "erro": self.erro,
                "mensagens": [m.to_dict()
                              for m in self.mensagens]}

    def __repr__(self) -> str:
        return (f"AgentSession({self.id} {self.estado}: "
                f"{len(self.mensagens)} msgs)")


class CommandPalette:
    """Busca determinística de comandos (sem IA)."""

    def __init__(self) -> None:
        self.comandos = [{"id": cid, "titulo": titulo}
                         for cid, titulo in COMANDOS_PALETTE]

    def buscar(self, texto: str) -> list[dict]:
        termo = _norm(texto)
        if not termo:
            return list(self.comandos)
        return [c for c in self.comandos
                if termo in _norm(c["titulo"])
                or termo in _norm(c["id"])]

    def contextuais(self, selecao: dict | None = None
                    ) -> list[dict]:
        base = ["inspecionar_selecao", "consultar_entidade",
                "mostrar_codigo", "mostrar_relacoes",
                "adicionar_contexto", "remover_contexto"]
        if not isinstance(selecao, dict) or not selecao.get(
                "id"):
            return [c for c in self.comandos
                    if c["id"] not in base]
        return [c for c in self.comandos if c["id"] in base]

    def executar(self, app, comando_id: str,
                 argumentos: dict | None = None) -> dict:
        """Roteia para StudioApp real (só comandos seguros)."""
        cid = str(comando_id)
        if cid not in {c["id"] for c in self.comandos}:
            raise ErroELiXX(f'Comando "{cid}" desconhecido.')
        args = dict(argumentos or {})
        if cid == "executar_projeto":
            from ..comandos import StudioCommand

            doc = app.documentos.ativo or ""
            return app.executar_comando(StudioCommand(
                "executar", doc))
        if cid == "parar_projeto":
            from ..comandos import StudioCommand

            return app.executar_comando(StudioCommand("parar"))
        if cid in ("abrir_preview", "abrir_inspector",
                   "mostrar_raciocinio", "alternar_compacto",
                   "atualizar_modelo", "sincronizar_projeto",
                   "nova_sessao", "consultar_contexto",
                   "mostrar_tools", "mostrar_plano",
                   "mostrar_changes", "abrir_codigo",
                   "mostrar_preview", "mostrar_inspector",
                   "focar_agent", "focar_codigo",
                   "focar_preview", "alternar_layout"):
            return {"ok": True, "comando": cid,
                    "nota": "navegação/ação via UI ou API dedicada"}
        if cid in ("salvar", "executar", "parar"):
            from ..comandos import StudioCommand

            alvo = args.get("alvo", "")
            if cid == "salvar" and not alvo:
                alvo = app.documentos.ativo or ""
            return app.executar_comando(StudioCommand(cid,
                                                     alvo))
        if cid == "abrir_arquivo":
            alvo = str(args.get("alvo", ""))
            if not alvo:
                raise ErroELiXX('Comando "abrir_arquivo" exige '
                                "alvo.")
            caminho = app.workspace.resolver(alvo)
            if not caminho.is_file():
                raise ErroELiXX(f'Arquivo "{alvo}" ausente.')
            app.documentos.abrir(
                alvo, caminho.read_text(encoding="utf-8"))
            return {"ok": True, "comando": cid, "alvo": alvo}
        if cid in ("abrir_arquivo", "inspecionar_selecao",
                   "consultar_entidade", "mostrar_codigo",
                   "mostrar_relacoes", "adicionar_contexto",
                   "remover_contexto"):
            alvo = args.get("alvo", "")
            if not alvo:
                raise ErroELiXX(f'Comando "{cid}" exige alvo.')
            return {"ok": True, "comando": cid, "alvo": alvo}
        raise ErroELiXX(f'Comando "{cid}" sem executor seguro.')

    def __repr__(self) -> str:
        return f"CommandPalette({len(self.comandos)} comandos)"


def resumo_chips(resultado) -> list[dict]:
    """Entidades → chips {id, nome, tipo, incluído} (só leitura)."""
    return [{"id": e.id, "nome": e.nome, "tipo": e.tipo,
             "incluido": True} for e in resultado.entidades]


def selecao_global(app, tipo: str, ref_id: str) -> dict:
    """Fonte única: Inspetor F25 + evento (Preview acompanha via UI).

    Sem estado duplicado: o modelo de verdade mora em
    `app.inspetor.selecao`; aqui só escreve lá e notifica.
    """
    from ..inspetor import Selecao

    sel = Selecao(tipo, ref_id)
    app.inspetor.selecionar(sel)
    app.eventos.emitir("selecionado", sel.to_dict())
    return sel.to_dict()
