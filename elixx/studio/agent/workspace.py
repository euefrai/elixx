"""Agent Reasoning Workspace (Fase 35) — modelo headless + Tk opcional.

"O Agent mostra o que está considerando antes de agir."

"O grafo representa o contexto; não substitui o modelo semântico."

Sessão visual/operacional sobre estruturas reais (F27/F28/F30/F31/F32/
F33/F34): workflow em estágios + grafo 2D de contexto (nós/arestas com
origem real, layout determinístico, viewport com limites). O núcleo
não importa Tk; a UI é camada fina em `workspace_ui.py`.
"""
from __future__ import annotations

import json
import math

from ...erros import ErroELiXX
from . import _base as B

__all__ = [
    "ESTAGIOS", "ESTADOS", "TIPOS_NO", "ZOOMS", "AgentNode",
    "AgentEdge", "AgentWorkspace",
    "transicoes_permitidas",
]

ESTAGIOS = ("TASK", "CONTEXT", "TOOLS", "OPERATIONS", "PLAN",
            "CHANGES", "PREVIEW")
"""Etapas do workflow (F36 soma TOOLS entre CONTEXT e OPERATIONS)."""

ESTADOS = ("IDLE", "RECEIVED", "CONTEXT_ANALYZING",
           "CONTEXT_READY", "AMBIGUOUS", "OPERATIONS_READY",
           "PLANNING", "PLAN_READY", "WAITING_APPROVAL", "APPLYING",
           "VALIDATING", "PREVIEW_READY", "COMPLETED", "CANCELLED",
           "FAILED")
"""Estados determinísticos (refletem sistemas reais, sem teatro)."""

TIPOS_NO = ("TASK", "ENTITY", "RELATION", "FILE", "CHARACTER",
            "PART", "SCENE", "POSE", "GESTURE", "ANIMATION", "ASSET",
            "CAPABILITY", "OPERATION", "PLAN_STEP", "CHANGE",
            "TOOL")
"""Vocabulário de nós (só instancia com origem real; RELATION vive
como aresta tipada — sem nó duplicado, documentado)."""

ZOOMS = (0.5, 1.0, 1.5, 2.0, 3.0)
"""Níveis discretos (sem infinito)."""

MAX_NOS = 10000
MAX_ARESTAS = 20000
MAX_VISIVEIS = 100
MAX_BUSCA = 50
MAX_PROFUNDIDADE = 8

__all__ += ["MAX_NOS", "MAX_ARESTAS", "MAX_VISIVEIS", "MAX_BUSCA",
            "MAX_PROFUNDIDADE"]

_TRANSICOES = {
    "IDLE": ("RECEIVED", "CANCELLED"),
    "RECEIVED": ("CONTEXT_ANALYZING", "AMBIGUOUS", "CANCELLED",
                 "FAILED"),
    "CONTEXT_ANALYZING": ("CONTEXT_READY", "AMBIGUOUS", "FAILED",
                           "CANCELLED"),
    "CONTEXT_READY": ("OPERATIONS_READY", "AMBIGUOUS", "FAILED",
                      "CANCELLED"),
    "AMBIGUOUS": ("CONTEXT_ANALYZING", "CANCELLED", "FAILED"),
    "OPERATIONS_READY": ("PLANNING", "FAILED", "CANCELLED"),
    "PLANNING": ("PLAN_READY", "FAILED", "CANCELLED"),
    "PLAN_READY": ("WAITING_APPROVAL", "FAILED", "CANCELLED"),
    "WAITING_APPROVAL": ("APPLYING", "CANCELLED", "FAILED"),
    "APPLYING": ("VALIDATING", "FAILED", "CANCELLED"),
    "VALIDATING": ("PREVIEW_READY", "FAILED", "CANCELLED"),
    "PREVIEW_READY": ("COMPLETED", "FAILED", "CANCELLED"),
    "COMPLETED": (),
    "CANCELLED": (),
    "FAILED": (),
}
"""Transições válidas (falha/cancelamento sempre possíveis)."""


def transicoes_permitidas(estado: str) -> tuple:
    if estado not in _TRANSICOES:
        raise ErroELiXX(f"Workspace: estado {estado} inválido.")
    return _TRANSICOES[estado]


class AgentNode:
    """Nó do grafo (sempre com origem real: modelo/op/plano)."""

    def __init__(self, node_id: str, tipo: str, rotulo: str = "",
                 source_id: str = "", score=None,
                 motivos: list | None = None,
                 detalhe: dict | None = None) -> None:
        self.id = B.id_valido(node_id)
        if tipo not in TIPOS_NO:
            raise ErroELiXX(f"Workspace: nó {tipo} inválido.")
        self.tipo = tipo
        self.rotulo = str(rotulo) or self.id
        self.source_id = str(source_id)
        if score is not None:
            try:
                score = float(score)
            except (TypeError, ValueError):
                raise ErroELiXX("Workspace: score numérico.")
            if not math.isfinite(score):
                raise ErroELiXX("Workspace: score finito.")
        self.score = score
        self.motivos = [str(m) for m in (motivos or [])]
        detalhe_txt = dict(detalhe or {})
        if not B.e_dado(detalhe_txt):
            raise ErroELiXX("Workspace: detalhe inválido.")
        self.detalhe = detalhe_txt
        self.x = 0.0
        self.y = 0.0
        self.camada = 0
        self.expandido = False

    def to_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo,
                "rotulo": self.rotulo, "source_id": self.source_id,
                "score": self.score, "motivos": list(self.motivos),
                "detalhe": dict(self.detalhe), "x": self.x,
                "y": self.y, "camada": self.camada,
                "expandido": self.expandido}

    @staticmethod
    def from_dict(dados: dict) -> AgentNode:
        if not isinstance(dados, dict):
            raise ErroELiXX("Workspace: nó precisa de dict.")
        no = AgentNode(dados.get("id", ""), dados.get("tipo", ""),
                       rotulo=dados.get("rotulo", ""),
                       source_id=dados.get("source_id", ""),
                       score=dados.get("score"),
                       motivos=dados.get("motivos") or [],
                       detalhe=dict(dados.get("detalhe") or {}))
        no.x = float(dados.get("x", 0.0))
        no.y = float(dados.get("y", 0.0))
        no.camada = int(dados.get("camada", 0))
        no.expandido = bool(dados.get("expandido", False))
        return no

    def __repr__(self) -> str:
        return f"AgentNode({self.tipo} {self.id})"


class AgentEdge:
    """Aresta tipada com fonte (F27, F34 ou derivada declarada)."""

    def __init__(self, origem: str, tipo: str, destino: str,
                 fonte: str = "F27") -> None:
        self.origem = B.id_valido(origem, "origem")
        self.tipo = B.id_valido(tipo, "tipo")
        self.destino = B.id_valido(destino, "destino")
        self.fonte = str(fonte) or "F27"

    def to_dict(self) -> dict:
        return {"origem": self.origem, "tipo": self.tipo,
                "destino": self.destino, "fonte": self.fonte}

    @staticmethod
    def from_dict(dados: dict) -> AgentEdge:
        if not isinstance(dados, dict):
            raise ErroELiXX("Workspace: aresta precisa de dict.")
        return AgentEdge(dados.get("origem", ""),
                         dados.get("tipo", ""),
                         dados.get("destino", ""),
                         fonte=dados.get("fonte", "F27"))

    def __repr__(self) -> str:
        return (f"AgentEdge({self.origem} —{self.tipo}→ "
                f"{self.destino})")


class _AmbienteLeitura:
    """Ambiente só-leitura p/ tools (modelo F27, sem escrita)."""

    def __init__(self, modelo) -> None:
        self.modelo = modelo
        self.workspace = None
        self.personagens = {}
        self.contexto = None
        self.preview = None


class AgentWorkspace:
    """Sessão de raciocínio: estágios + grafo + seleção + vista."""

    _contador = 0

    def __init__(self, tarefa: str = "", origem: str = "chat",
                 sessao_id: str = "") -> None:
        AgentWorkspace._contador += 1
        self.id = str(sessao_id).strip() or \
            f"sessao_{AgentWorkspace._contador:03d}"
        self.tarefa = str(tarefa)[:2000]
        self.origem = str(origem)
        self.estado = "IDLE"
        self.estagios = {nome: {"id": nome.lower(),
                                "nome": nome,
                                "estado": "pendente",
                                "dados": {}, "quantidade": 0,
                                "erros": [], "warnings": []}
                         for nome in ESTAGIOS}
        self.nos: dict[str, AgentNode] = {}
        self.arestas: list[AgentEdge] = []
        self.selecao: str | None = None
        self.vista = {"modo": "workflow", "zoom": 1.0,
                      "pan": [0.0, 0.0], "filtros": [],
                      "busca": ""}
        self.sessoes: list[dict] = []
        self._bus = None

    # ----- eventos (bus F25 quando acoplado) -----

    def acoplar_bus(self, bus) -> None:
        self._bus = bus

    def _emitir(self, evento: str, dados: dict | None = None
                ) -> None:
        if self._bus is not None:
            try:
                self._bus.emitir(evento, dados or {})
            except ErroELiXX:
                pass  # bus sem o evento: workspace segue

    # ----- estados -----

    def transitar(self, novo: str) -> AgentWorkspace:
        if novo not in _TRANSICOES.get(self.estado, ()):
            raise ErroELiXX(f"Workspace: {self.estado} → {novo} "
                            "inválido.")
        self.estado = novo
        self._emitir("stage_changed", {"estado": novo})
        return self

    def marcar_estagio(self, estagio: str, estado: str,
                       dados: dict | None = None,
                       quantidade: int = 0) -> None:
        if estagio not in self.estagios:
            raise ErroELiXX(f"Workspace: estágio {estagio}.")
        if estado not in ("pendente", "processando", "pronto",
                          "atencao", "erro", "atual"):
            raise ErroELiXX(f"Workspace: estágio {estado}.")
        info = self.estagios[estagio]
        info["estado"] = estado
        if dados is not None:
            if not B.e_dado(dados):
                raise ErroELiXX("Workspace: dados inválidos.")
            info["dados"] = dict(dados)
        info["quantidade"] = int(quantidade)

    # ----- grafo (só origens reais) -----

    def adicionar_no(self, no: AgentNode) -> AgentNode:
        if not isinstance(no, AgentNode):
            raise ErroELiXX("Workspace: espera AgentNode.")
        if len(self.nos) >= MAX_NOS:
            raise ErroELiXX(f"Workspace: além de {MAX_NOS} nós "
                            "(visualização limitada).")
        if no.id in self.nos:
            raise ErroELiXX(f'Workspace: nó "{no.id}" duplicado.')
        self.nos[no.id] = no
        return no

    def adicionar_aresta(self, aresta: AgentEdge) -> AgentEdge:
        if not isinstance(aresta, AgentEdge):
            raise ErroELiXX("Workspace: espera AgentEdge.")
        if len(self.arestas) >= MAX_ARESTAS:
            raise ErroELiXX("Workspace: arestas além do teto.")
        if aresta.origem not in self.nos or \
                aresta.destino not in self.nos:
            raise ErroELiXX("Workspace: aresta sem nó "
                            "(sem relação inventada).")
        chave = (aresta.origem, aresta.tipo, aresta.destino)
        if any((a.origem, a.tipo, a.destino) == chave
               for a in self.arestas):
            raise ErroELiXX("Workspace: aresta duplicada.")
        self.arestas.append(aresta)
        return aresta

    def carregar_contexto(self, resultado) -> dict:
        """ContextoResultado F34 → nós ENTITY/FILE + arestas."""
        from .contexto_tarefa import ContextoResultado

        if not isinstance(resultado, ContextoResultado):
            raise ErroELiXX("Workspace: espera ContextoResultado.")
        n_nos, n_arestas = 0, 0
        mapa_tipos = {"personagem": "CHARACTER", "parte": "PART",
                      "tela": "SCENE", "janela": "SCENE",
                      "pose": "POSE", "expressao": "POSE",
                      "animacao": "ANIMATION", "asset": "ASSET"}
        for ent in resultado.entidades:
            tipo = mapa_tipos.get(ent.tipo, "ENTITY")
            if ent.id not in self.nos:
                self.adicionar_no(AgentNode(
                    f"ctx:{ent.id}", tipo, ent.nome or ent.id,
                    source_id=ent.id, score=ent.score,
                    motivos=list(ent.motivos),
                    detalhe={"arquivo": ent.arquivo,
                             "categoria": ent.categoria}))
                n_nos += 1
        for arq in resultado.arquivos:
            nid = f"file:{arq}"
            if nid not in self.nos:
                self.adicionar_no(AgentNode(
                    nid, "FILE", arq, source_id=arq,
                    detalhe={"arquivo": arq}))
                n_nos += 1
        for rel in resultado.relacoes:
            origem, destino = f"ctx:{rel['origem']}", \
                f"ctx:{rel['destino']}"
            if origem in self.nos and destino in self.nos:
                try:
                    self.adicionar_aresta(AgentEdge(
                        origem, rel["tipo"], destino,
                        fonte="F34"))
                    n_arestas += 1
                except ErroELiXX:
                    pass
        self.marcar_estagio("CONTEXT", "pronto",
                            {"entidades": n_nos},
                            quantidade=n_nos)
        self._emitir("context_updated", {"nos": n_nos})
        return {"nos": n_nos, "arestas": n_arestas}

    def carregar_operacoes(self, operacoes: list) -> dict:
        """SemanticOperations → nós OPERATION + aresta alvo."""
        from .operacoes import (SemanticEventOperation,
                                SemanticOperation)

        total = 0
        for i, op in enumerate(operacoes or []):
            if isinstance(op, SemanticEventOperation):
                nid = f"op:evento_{i}"
                self.adicionar_no(AgentNode(
                    nid, "OPERATION",
                    f"quando {op.gatilho}",
                    source_id=nid,
                    detalhe={"gatilho": op.gatilho,
                             "modo": op.modo}))
                total += 1
                for efeito in op.efeitos:
                    eid = f"op:evento_{i}.{efeito.tipo}"
                    self.adicionar_no(AgentNode(
                        eid, "OPERATION",
                        f"{efeito.tipo} {efeito.alvo.nome}",
                        source_id=eid,
                        detalhe=efeito.to_dict()))
                    self.adicionar_aresta(AgentEdge(
                        nid, "produz", eid, fonte="F31"))
                    total += 1
                continue
            if not isinstance(op, SemanticOperation):
                raise ErroELiXX("Workspace: espera operações F31.")
            nid = f"op:{i}.{op.tipo}"
            self.adicionar_no(AgentNode(
                nid, "OPERATION",
                f"{op.tipo} {op.alvo.nome}", source_id=nid,
                detalhe=op.to_dict()))
            total += 1
            alvo = f"ctx:{op.alvo.nome}" if ":" not in \
                op.alvo.nome else f"ctx:{op.alvo.nome}"
            for cand in (alvo, f"ctx:personagem:{op.alvo.nome}",
                         f"ctx:componente:{op.alvo.nome}"):
                if cand in self.nos:
                    try:
                        self.adicionar_aresta(AgentEdge(
                            nid, "alvo", cand, fonte="F31"))
                    except ErroELiXX:
                        pass
                    break
        self.marcar_estagio("OPERATIONS", "pronto",
                            {"operacoes": total},
                            quantidade=total)
        return {"operacoes": total}

    def carregar_plano(self, tarefa) -> dict:
        """PlanoTarefa F33 → PLAN_STEP em ordem topológica real."""
        if getattr(tarefa, "plano", None) is None:
            raise ErroELiXX("Workspace: tarefa sem plano "
                            "construído.")
        ordem = tarefa.plano.ordem_execucao()
        for pid in ordem:
            passo = tarefa.plano.passo(pid)
            nid = f"step:{pid}"
            if nid not in self.nos:
                self.adicionar_no(AgentNode(
                    nid, "PLAN_STEP",
                    passo.descricao or pid, source_id=pid,
                    detalhe={"dependencias": list(
                        passo.dependencias),
                        "estado": passo.estado,
                        "risco": passo.risco}))
        for pid in ordem:
            for dep in tarefa.plano.passo(pid).dependencias:
                try:
                    self.adicionar_aresta(AgentEdge(
                        f"step:{dep}", "precede", f"step:{pid}",
                        fonte="F33"))
                except ErroELiXX:
                    pass
        self.marcar_estagio("PLAN", "pronto",
                            {"ordem": ordem},
                            quantidade=len(ordem))
        return {"ordem": ordem}

    def carregar_tools(self, trace) -> dict:
        """ToolTrace F36 → nós TOOL + cadeia de uso (só leitura)."""
        total = 0
        anterior = None
        for chamada in getattr(trace, "chamadas", []):
            nid = f"tool:{chamada.id}"
            if nid not in self.nos:
                self.adicionar_no(AgentNode(
                    nid, "TOOL",
                    f"{chamada.tool_id} [{chamada.estado}]",
                    source_id=chamada.tool_id,
                    detalhe={"estado": chamada.estado,
                             "argumentos": dict(
                                 chamada.argumentos)}))
                total += 1
            if anterior is not None:
                try:
                    self.adicionar_aresta(AgentEdge(
                        anterior, "segue", nid, fonte="F36"))
                except ErroELiXX:
                    pass
            anterior = nid
        self.marcar_estagio("TOOLS", "pronto",
                            {"chamadas": total}, quantidade=total)
        self._emitir("context_updated", {"tools": total})
        return {"tools": total}

    def carregar_changes(self, proposals: list) -> dict:
        """Propostas F32 → nós CHANGE + aresta modifica."""
        total = 0
        for i, prop in enumerate(proposals or []):
            if not isinstance(prop, dict) or not B.e_dado(prop):
                raise ErroELiXX("Workspace: mudança inválida.")
            nid = f"change:{i}"
            self.adicionar_no(AgentNode(
                nid, "CHANGE",
                f"{prop.get('operacao', '?')} "
                f"{prop.get('arquivo', '?')}", source_id=nid,
                detalhe=prop))
            total += 1
            alvo = str(prop.get("arquivo", ""))
            for nid_f in (f"file:{alvo}",):
                if nid_f in self.nos:
                    try:
                        self.adicionar_aresta(AgentEdge(
                            nid, "modifica", nid_f, fonte="F32"))
                    except ErroELiXX:
                        pass
        self.marcar_estagio("CHANGES", "pronto",
                            {"mudancas": total}, quantidade=total)
        return {"mudancas": total}

    # ----- layout determinístico (camadas BFS, sem aleatório) -----

    def layout(self, dx: float = 220.0, dy: float = 64.0,
               max_iteracoes: int = 10000) -> dict:
        """BFS por profundidade a partir das sementes (ALVO/TASK).

        x = camada*dx, y = ordem*dy (vizinhos ordenados por id).
        Mesma entrada → mesmo layout, sempre.
        """
        for limite, valor, nome in ((10.0, dx, "dx"),
                                    (10.0, dy, "dy")):
            try:
                numero = float(valor)
            except (TypeError, ValueError):
                raise ErroELiXX(f"Workspace: {nome} numérico.")
            if not math.isfinite(numero) or numero <= 0:
                raise ErroELiXX(f"Workspace: {nome} positivo.")
        adj: dict[str, list] = {nid: [] for nid in self.nos}
        for aresta in self.arestas:
            adj[aresta.origem].append(aresta.destino)
            adj[aresta.destino].append(aresta.origem)
        for nid in adj:
            adj[nid] = sorted(set(adj[nid]))
        sementes = sorted(nid for nid, no in self.nos.items()
                          if no.tipo in ("TASK", "CHARACTER")
                          or (no.score or 0) >= 1.0) or \
            sorted(self.nos)
        camada: dict[str, int] = {}
        fila = [(0, s) for s in sementes]
        visitados = 0
        while fila and visitados < max_iteracoes:
            dist, nid = fila.pop(0)
            if nid in camada:
                continue
            camada[nid] = dist
            visitados += 1
            for viz in adj.get(nid, []):
                if viz not in camada:
                    fila.append((dist + 1, viz))
        for nid in self.nos:
            camada.setdefault(nid, max(camada.values() or [0]))
        por_camada: dict[int, list] = {}
        for nid, dist in camada.items():
            por_camada.setdefault(dist, []).append(nid)
        for dist in por_camada:
            por_camada[dist].sort(key=lambda nid: (
                -(self.nos[nid].score or 0.0), nid))
            for ordem, nid in enumerate(por_camada[dist]):
                no = self.nos[nid]
                no.camada = dist
                no.x = float(dist) * float(dx)
                no.y = float(ordem) * float(dy)
        return {"nos": len(self.nos), "camadas": len(por_camada)}

    # ----- viewport: zoom / pan / fit / visíveis -----

    def definir_zoom(self, nivel: float) -> float:
        try:
            numero = float(nivel)
        except (TypeError, ValueError):
            raise ErroELiXX("Workspace: zoom numérico.")
        if numero not in ZOOMS:
            raise ErroELiXX(f"Workspace: zoom em {ZOOMS}.")
        self.vista["zoom"] = numero
        return numero

    def aproximar(self) -> float:
        idx = ZOOMS.index(self.vista["zoom"])
        return self.definir_zoom(ZOOMS[min(idx + 1, len(ZOOMS)
                                           - 1)])

    def afastar(self) -> float:
        idx = ZOOMS.index(self.vista["zoom"])
        return self.definir_zoom(ZOOMS[max(idx - 1, 0)])

    def normalizar_zoom(self) -> float:
        return self.definir_zoom(1.0)

    def mover_pan(self, dx: float, dy: float) -> list:
        try:
            par = [float(dx), float(dy)]
        except (TypeError, ValueError):
            raise ErroELiXX("Workspace: pan numérico.")
        if not all(math.isfinite(v) for v in par):
            raise ErroELiXX("Workspace: pan finito.")
        self.vista["pan"] = [self.vista["pan"][0] + par[0],
                             self.vista["pan"][1] + par[1]]
        return list(self.vista["pan"])

    def enquadrar(self) -> dict:
        """Viewport nos visíveis (sem coordenada inválida)."""
        visiveis = self.visiveis()
        if not visiveis:
            self.vista["pan"] = [0.0, 0.0]
            return {"zoom": self.vista["zoom"], "nos": 0}
        xs = [n["x"] for n in visiveis]
        ys = [n["y"] for n in visiveis]
        if max(xs) - min(xs) < 0 or max(ys) - min(ys) < 0:
            raise ErroELiXX("Workspace: bbox inválida.")
        self.vista["pan"] = [float(min(xs)), float(min(ys))]
        return {"zoom": self.vista["zoom"],
                "nos": len(visiveis),
                "bbox": [min(xs), min(ys), max(xs), max(ys)]}

    def visiveis(self, limite: int = MAX_VISIVEIS) -> list[dict]:
        """Subconjunto: filtros + top score, teto MAX_VISIVEIS."""
        filtros = set(self.vista.get("filtros", []))
        busca = str(self.vista.get("busca", "")).lower()
        candidatos = []
        for no in self.nos.values():
            if filtros and no.tipo not in filtros:
                continue
            if busca and busca not in (
                    no.rotulo + " " + no.id).lower():
                continue
            candidatos.append(no)
        try:
            teto = int(limite)
        except (TypeError, ValueError):
            raise ErroELiXX("Workspace: limite inteiro.")
        candidatos.sort(key=lambda n: (-(n.score or 0.0), n.id))
        cortados = candidatos[:max(0, teto)]
        return [n.to_dict() for n in cortados]

    def filtrar(self, tipos: list) -> list[str]:
        for tipo in tipos:
            if tipo not in TIPOS_NO:
                raise ErroELiXX(f"Workspace: filtro {tipo}.")
        self.vista["filtros"] = list(tipos)
        return list(self.vista["filtros"])

    def buscar(self, texto: str, modelo=None) -> list[dict]:
        """Busca local (nós) + F27 quando há modelo (sem duplicar)."""
        termo = str(texto).strip().lower()
        if not termo:
            raise ErroELiXX("Workspace: busca não vazia.")
        achados = [n.to_dict() for n in self.nos.values()
                   if termo in (n.rotulo + " " + n.id).lower()]
        if modelo is not None:
            for ent in modelo.entidades():
                if termo in (ent.nome + " " + ent.id).lower() \
                        and not any(a["id"] == ent.id
                                    for a in achados):
                    achados.append({"id": ent.id, "tipo": ent.tipo,
                                    "rotulo": ent.nome,
                                    "fonte": "F27"})
        achados.sort(key=lambda a: a["id"])
        return achados[:MAX_BUSCA]

    # ----- expansão sob demanda (consulta F27; sem árvore paralela) -----

    def expandir(self, node_id: str, modelo=None) -> dict:
        """Filhos via relações possui/contem do F27 (modelo intacto)."""
        nid = B.id_valido(node_id)
        if nid not in self.nos:
            raise ErroELiXX(f'Workspace: nó "{nid}" ausente.')
        no = self.nos[nid]
        if no.expandido:
            return {"expandido": True, "novos": 0}
        novos = 0
        if modelo is not None and no.source_id:
            from ..modelo.consulta import ConsultaSemantica

            q = ConsultaSemantica(modelo)
            for rel in q.relacoes_de(no.source_id):
                if rel.tipo not in ("possui", "contem"):
                    continue
                try:
                    ent = q.indice.buscar_por_id(rel.destino)
                except ErroELiXX:
                    continue
                nid_filho = f"ctx:{ent.id}"
                if nid_filho not in self.nos:
                    self.adicionar_no(AgentNode(
                        nid_filho, "ENTITY", ent.nome or ent.id,
                        source_id=ent.id,
                        detalhe={"arquivo": ent.arquivo}))
                    novos += 1
                try:
                    self.adicionar_aresta(AgentEdge(
                        nid, rel.tipo, nid_filho, fonte="F27"))
                except ErroELiXX:
                    pass
        no.expandido = True
        return {"expandido": True, "novos": novos}

    def recolher(self, node_id: str) -> dict:
        """Esconde descendentes da vista (modelo intacto)."""
        nid = B.id_valido(node_id)
        if nid not in self.nos:
            raise ErroELiXX(f'Workspace: nó "{nid}" ausente.')
        self.nos[nid].expandido = False
        removidos = [a for a in self.arestas
                     if a.origem == nid]
        return {"expandido": False,
                "arestas_ocultas": len(removidos)}

    # ----- seleção bidirecional (sem estado duplicado) -----

    def selecionar(self, node_id: str) -> dict:
        nid = B.id_valido(node_id)
        if nid not in self.nos:
            raise ErroELiXX(f'Workspace: nó "{nid}" ausente.')
        self.selecao = nid
        self._emitir("node_selected", {"id": nid})
        return self.detalhe_selecao()

    def limpar_selecao(self) -> None:
        self.selecao = None

    def detalhe_selecao(self, modelo=None) -> dict:
        """Inspector da seleção: entidade/op/passo/change reais."""
        if self.selecao is None:
            raise ErroELiXX("Workspace: nada selecionado.")
        no = self.nos[self.selecao]
        base = {"id": no.id, "tipo": no.tipo,
                "rotulo": no.rotulo, "score": no.score,
                "motivos": list(no.motivos)}
        if no.tipo in ("ENTITY", "CHARACTER", "PART", "SCENE",
                       "FILE") and modelo is not None \
                and no.source_id:
            from ..modelo.consulta import ConsultaSemantica

            try:
                viz = ConsultaSemantica(modelo).vizinhanca(
                    no.source_id)
                base["entidade"] = viz["entidade"]
                base["relacoes"] = viz["de"] + viz["para"]
            except ErroELiXX as exc:
                base["erro"] = str(exc)[:200]
        else:
            base["detalhe"] = dict(no.detalhe)
        return base

    def explicar_aresta(self, origem: str, tipo: str,
                        destino: str) -> dict:
        for aresta in self.arestas:
            if (aresta.origem, aresta.tipo, aresta.destino) == \
                    (origem, tipo, destino):
                return {"origem": origem, "relacao": tipo,
                        "destino": destino,
                        "fonte": ("Modelo Semântico F27"
                                  if aresta.fonte == "F27"
                                  else f"Context Engine "
                                       f"{aresta.fonte}")}
        raise ErroELiXX("Workspace: relação ausente.")

    # ----- pipeline real (F30→F34→F31→F33→F32; sem LLM) -----

    def executar_pedido(self, pedido: str, ambiente: dict
                        ) -> dict:
        """Pedido em linguagem controlada → estágios reais."""
        modelo = ambiente.get("modelo")
        if modelo is None:
            raise ErroELiXX("Workspace: pipeline exige modelo.")
        self.transitar("RECEIVED")
        self.marcar_estagio("TASK", "processando",
                            {"pedido": str(pedido)[:500]})
        try:
            from .inteligencia import MockIntentProvider
            from .operacoes import intent_para_operacao

            self.transitar("CONTEXT_ANALYZING")
            intent = MockIntentProvider().gerar_intencao(
                None, pedido)
            self.marcar_estagio("TASK", "pronto",
                                {"intencao": intent.tipo})
            contexto = self._contexto_de(
                modelo, ambiente, intent)
            self.transitar("CONTEXT_READY")
            self.marcar_estagio(
                "CONTEXT", "pronto",
                {"entidades": len(contexto.entidades)},
                quantidade=len(contexto.entidades))
            self.carregar_contexto(contexto)
            self._executar_tools(intent, modelo)
            ops = self._operacoes_de(intent)
            self.transitar("OPERATIONS_READY")
            self.marcar_estagio("OPERATIONS", "pronto",
                                {"operacoes": len(ops)},
                                quantidade=len(ops))
            self.carregar_operacoes(ops)
            return {"intencao": intent.to_dict(),
                    "operacoes": [o.to_dict() for o in ops]}
        except ErroELiXX as exc:
            self.transitar("FAILED")
            self.marcar_estagio("TASK", "erro")
            return {"erro": str(exc)[:300]}

    def _contexto_de(self, modelo, ambiente, intent):
        from .contexto_tarefa import (ContextoConfig,
                                      ContextoTarefa,
                                      construir_contexto)

        tarefa = ContextoTarefa(
            objetivo=str(ambiente.get("objetivo", "")),
            alvo=intent.personagem or intent.alvo or "",
            entidade_selecionada=str(ambiente.get(
                "selecionado", "")),
            arquivo_atual=str(ambiente.get("arquivo", "")),
            operacoes=[intent.tipo] if intent.tipo in
            ("pose", "expressao", "mover", "animar", "mostrar",
             "esconder") else [])
        return construir_contexto(modelo, tarefa,
                                  ContextoConfig())

    def _executar_tools(self, intent, modelo) -> None:
        """TOOLS: buscar_entidade + consultar_relacoes (READ, F36)."""
        from .ferramentas_semanticas import (
            AgentToolCall, SemanticPermissions, SemanticToolRegistry,
            ToolTrace, executar_chamada)

        alvo = intent.personagem or intent.alvo or ""
        ambiente = _AmbienteLeitura(modelo)
        permissoes = SemanticPermissions(["READ"])
        registro = SemanticToolRegistry()
        trace = ToolTrace()
        for tool_id, args in (
                ("buscar_entidade", {"nome": alvo}),
                ("consultar_relacoes",
                 {"id": f"personagem:{alvo}"})):
            chamada = AgentToolCall(tool_id, args)
            trace.registrar(chamada)
            executar_chamada(registro, chamada, ambiente,
                             permissoes)
        self.carregar_tools(trace)

    def _operacoes_de(self, intent):
        from .operacoes import intent_para_operacao

        return [intent_para_operacao(intent)]

    # ----- ambiguidade / cancelamento / sessões -----

    def resolver_ambiguidade(self, ent_id: str) -> dict:
        if self.estado != "AMBIGUOUS":
            raise ErroELiXX("Workspace: sem ambiguidade ativa.")
        self.transitar("CONTEXT_ANALYZING")
        return {"resolvido": B.id_valido(ent_id)}

    def marcar_ambiguo(self, candidatos: list) -> dict:
        self.transitar("AMBIGUOUS")
        return {"ambiguidade": True,
                "candidatos": list(candidatos)}

    def cancelar(self) -> dict:
        if self.estado in ("COMPLETED", "CANCELLED", "FAILED"):
            raise ErroELiXX("Workspace: sessão já encerrada.")
        self.transitar("CANCELLED")
        for nome in ("TASK", "CONTEXT", "OPERATIONS", "PLAN",
                     "CHANGES", "PREVIEW"):
            if self.estagios[nome]["estado"] in ("processando",
                                                 "atual"):
                self.estagios[nome]["estado"] = "erro"
        return {"estado": "CANCELLED"}

    def encerrar_sessao(self, resumo: str = "") -> dict:
        registro = {"id": self.id, "tarefa": self.tarefa,
                    "estado": self.estado,
                    "resumo": str(resumo)[:300]}
        self.sessoes.append(registro)
        return registro

    def historico(self) -> list[dict]:
        return [dict(s) for s in self.sessoes]

    def importar_historico(self, historico) -> int:
        """Lê registros de AgentHistory F26 (sem duplicar lógica)."""
        total = 0
        for registro in historico.listar():
            self.sessoes.append(
                {"id": registro.get("id", "?"),
                 "tarefa": registro.get("objetivo", ""),
                 "estado": registro.get("estado", "?"),
                 "resumo": "via AgentHistory F26"})
            total += 1
        return total

    # ----- diagnóstico + serialização -----

    def diagnosticar(self) -> dict:
        return {
            "estado": self.estado,
            "estagios": {k: v["estado"] for k, v in
                         self.estagios.items()},
            "nos_analisados": len(self.nos),
            "arestas": len(self.arestas),
            "selecao": self.selecao,
            "vista": {"modo": self.vista["modo"],
                      "zoom": self.vista["zoom"]},
            "limitada": len(self.nos) >= MAX_NOS or
            len(self.visiveis()) >= MAX_VISIVEIS,
        }

    def to_dict(self) -> dict:
        dados = {"id": self.id, "tarefa": self.tarefa,
                 "origem": self.origem, "estado": self.estado,
                 "estagios": {k: dict(v) for k, v in
                              self.estagios.items()},
                 "nos": [n.to_dict() for _, n in sorted(
                     self.nos.items())],
                 "arestas": [a.to_dict() for a in self.arestas],
                 "selecao": self.selecao,
                 "vista": {"modo": self.vista["modo"],
                           "zoom": self.vista["zoom"],
                           "pan": list(self.vista["pan"]),
                           "filtros": list(
                               self.vista["filtros"]),
                           "busca": self.vista["busca"]},
                 "sessoes": list(self.sessoes)}
        if not B.e_dado(dados):
            raise ErroELiXX("Workspace: não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> AgentWorkspace:
        if not isinstance(dados, dict):
            raise ErroELiXX("Workspace: precisa de dict.")
        ws = AgentWorkspace(dados.get("tarefa", ""),
                            origem=dados.get("origem", "chat"),
                            sessao_id=dados.get("id", ""))
        if dados.get("estado", "IDLE") != "IDLE":
            raise ErroELiXX("Workspace: desserializa em IDLE "
                            "(sem retomar execução).")
        for item in (dados.get("nos") or []):
            ws.adicionar_no(AgentNode.from_dict(item))
        for item in (dados.get("arestas") or []):
            try:
                ws.adicionar_aresta(AgentEdge.from_dict(item))
            except ErroELiXX:
                pass
        for nome, info in (dados.get("estagios") or {}).items():
            if nome in ws.estagios and isinstance(info, dict):
                if info.get("estado") in ("pendente",
                                          "processando",
                                          "pronto", "atencao",
                                          "erro", "atual"):
                    ws.estagios[nome]["estado"] = info["estado"]
                if isinstance(info.get("dados"), dict) and \
                        B.e_dado(info["dados"]):
                    ws.estagios[nome]["dados"] = dict(
                        info["dados"])
                try:
                    ws.estagios[nome]["quantidade"] = int(
                        info.get("quantidade", 0))
                except (TypeError, ValueError):
                    pass
        if dados.get("selecao") in ws.nos:
            ws.selecao = dados["selecao"]
        vista = dados.get("vista") or {}
        if vista.get("modo") in ("workflow", "graph"):
            ws.vista["modo"] = vista["modo"]
        pan = vista.get("pan") or [0.0, 0.0]
        try:
            px, py = float(pan[0]), float(pan[1])
        except (TypeError, ValueError, IndexError):
            raise ErroELiXX("Workspace: pan inválido.")
        import math as _math

        if not (_math.isfinite(px) and _math.isfinite(py)):
            raise ErroELiXX("Workspace: pan finito.")
        ws.vista["pan"] = [px, py]
        if vista.get("zoom") in ZOOMS:
            ws.vista["zoom"] = vista["zoom"]
        ws.vista["filtros"] = [f for f in
                               (vista.get("filtros") or [])
                               if f in TIPOS_NO]
        ws.vista["busca"] = str(vista.get("busca", ""))
        for registro in (dados.get("sessoes") or []):
            if isinstance(registro, dict):
                ws.sessoes.append(dict(registro))
        return ws

    def __repr__(self) -> str:
        return (f"AgentWorkspace({self.id} {self.estado}: "
                f"{len(self.nos)} nós)")
