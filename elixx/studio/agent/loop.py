"""Semantic Agent Loop (Fase 28) — ponte F26 ↔ F27, sem LLM.

Ciclo (Modelo representa, Agent consulta, ChangeSet altera):

    pedido → consulta F27 → contexto → plano → ChangeSet F26
        → aprovação F26 → aplicação → validação → reanálise F27
        → modelo atualizado (+ diff)

Regras: sem ambiguidade não há ChangeSet; sem alvo não há ChangeSet;
sem aprovação não há aplicação; modelo nunca executa alteração
(ponte chama `ChangeSet.aplicar`, nunca escreve direto). Reuso total:
AgentIntent/AgentPlan/ChangeSet/Approval/PermissionSet (F26),
ConsultaSemantica/atualizar_arquivo/comparar_snapshots (F27).
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = [
    "MAX_ENTIDADES_CTX", "MAX_RELACOES_CTX", "MAX_BYTES_CTX",
    "STATUS_ALVO", "OPERACAO_PERMISSAO",
    "SemanticContext", "PlanoSemantico",
    "consultar_modelo", "resolver_alvo",
    "construir_contexto_semantico",
    "verificar_precondicoes", "gerar_changeset",
    "reanalisar_modelo", "diff_legivel", "executar_loop",
]

MAX_ENTIDADES_CTX = 200
"""Teto de entidades no contexto (sem cópias gigantes)."""

MAX_RELACOES_CTX = 500
"""Teto de relações no contexto."""

MAX_BYTES_CTX = 200_000
"""Teto serializado do contexto."""

STATUS_ALVO = ("unico", "ambiguo", "nao_encontrado")
"""Estados de resolução (ambíguo/nulo = sem ChangeSet)."""

OPERACAO_PERMISSAO = {
    "criar": "WRITE", "editar": "WRITE", "estruturada": "WRITE",
    "renomear": "RENAME", "mover": "RENAME", "excluir": "DELETE",
}
"""Alteração → permissão F26 exigida (falha fechada)."""


# ----- contexto semântico (ETAPA 2) -----

class SemanticContext:
    """Recorte do modelo para o Agent (só dados, com tetos)."""

    def __init__(self, entidades: list | None = None,
                 relacoes: list | None = None,
                 arquivos: list | None = None,
                 origem: str = "modelo") -> None:
        self.entidades = []
        for e in (entidades or []):
            if not isinstance(e, dict) or not B.e_dado(e):
                raise ErroELiXX("Loop: entidade inválida.")
            self.entidades.append(dict(e))
        if len(self.entidades) > MAX_ENTIDADES_CTX:
            raise ErroELiXX(f"Loop: contexto além de "
                            f"{MAX_ENTIDADES_CTX} entidades.")
        self.relacoes = []
        for r in (relacoes or []):
            if not isinstance(r, dict) or not B.e_dado(r):
                raise ErroELiXX("Loop: relação inválida.")
            self.relacoes.append(dict(r))
        if len(self.relacoes) > MAX_RELACOES_CTX:
            raise ErroELiXX(f"Loop: contexto além de "
                            f"{MAX_RELACOES_CTX} relações.")
        self.arquivos = [str(a) for a in (arquivos or [])]
        self.origem = str(origem)
        if len(self.to_json()) > MAX_BYTES_CTX:
            raise ErroELiXX(f"Loop: contexto além de {MAX_BYTES_CTX} "
                            "bytes.")

    def to_dict(self) -> dict:
        return {"entidades": list(self.entidades),
                "relacoes": list(self.relacoes),
                "arquivos": list(self.arquivos),
                "origem": self.origem}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> SemanticContext:
        if not isinstance(dados, dict):
            raise ErroELiXX("Loop: contexto precisa de dict.")
        return SemanticContext(
            dados.get("entidades") or [],
            dados.get("relacoes") or [],
            dados.get("arquivos") or [],
            origem=dados.get("origem", "modelo"))

    def __repr__(self) -> str:
        return (f"SemanticContext({len(self.entidades)} ent, "
                f"{len(self.relacoes)} rel)")


# ----- consultas (ETAPA 3; delegam ao F27) -----

def consultar_modelo(modelo, kind: str, **criterio) -> dict:
    """Consulta F27 → envelope determinístico (sem duplicar lógica)."""
    from ..modelo.consulta import ConsultaSemantica

    if not isinstance(kind, str):
        raise ErroELiXX("Loop: kind de consulta em texto.")
    q = ConsultaSemantica(modelo)
    chave = kind.strip()
    if chave == "id":
        try:
            resultados = [q.indice.buscar_por_id(
                str(criterio.get("id", ""))).to_dict()]
        except ErroELiXX:
            resultados = []
    elif chave == "nome":
        resultados = [e.to_dict() for e in q.encontrar_por_nome(
            str(criterio.get("nome", "")))]
    elif chave == "tipo":
        resultados = [e.to_dict() for e in q.encontrar_por_tipo(
            str(criterio.get("tipo", "")))]
    elif chave == "arquivo":
        resultados = [e.to_dict() for e in q.encontrar_por_arquivo(
            str(criterio.get("arquivo", "")))]
    elif chave == "relacoes_de":
        resultados = [r.to_dict() for r in q.relacoes_de(
            str(criterio.get("id", "")))]
    elif chave == "relacoes_para":
        resultados = [r.to_dict() for r in q.relacoes_para(
            str(criterio.get("id", "")))]
    elif chave == "entidade":
        resultados = [q.vizinhanca(str(criterio.get("id", "")))]
    else:
        raise ErroELiXX(f'Loop: consulta "{kind}" desconhecida '
                        "(id, nome, tipo, arquivo, relacoes_de, "
                        "relacoes_para, entidade).")
    return {"kind": chave, "criterio": {k: str(v) for k, v in
                                        criterio.items()},
            "total": len(resultados), "resultados": resultados}


def resolver_alvo(modelo, nome: str, tipo: str | None = None
                  ) -> dict:
    """Nome (+tipo) → unico | ambiguo | nao_encontrado.

    Ambíguo lista candidatos (id + arquivo, ordenados) e NUNCA escolhe
    sozinho: sem ChangeSet até desambiguar.
    """
    from ..modelo.consulta import ConsultaSemantica

    nome_txt = B.id_valido(nome, "nome do alvo")
    q = ConsultaSemantica(modelo)
    candidatos = [e for e in q.encontrar_por_nome(nome_txt)
                  if tipo is None or e.tipo == tipo]
    candidatos.sort(key=lambda e: (e.id, e.arquivo))
    if not candidatos:
        return {"status": "nao_encontrado", "nome": nome_txt,
                "tipo": tipo, "candidatos": []}
    if len(candidatos) > 1:
        return {"status": "ambiguo", "nome": nome_txt,
                "tipo": tipo,
                "candidatos": [
                    {"id": e.id, "tipo": e.tipo,
                     "arquivo": e.arquivo} for e in candidatos]}
    ent = candidatos[0]
    return {"status": "unico", "nome": nome_txt, "tipo": tipo,
            "entidade": ent.to_dict()}


def construir_contexto_semantico(modelo, alvo_ids: list,
                                 incluir_relacoes: bool = True
                                 ) -> SemanticContext:
    """Entidades-alvo (+ vizinhança) → contexto com tetos."""
    from ..modelo.consulta import ConsultaSemantica

    q = ConsultaSemantica(modelo)
    entidades, relacoes, arquivos = [], [], set()
    for eid in alvo_ids:
        viz = q.vizinhanca(str(eid))
        entidades.append(viz["entidade"])
        arquivos.add(viz["entidade"].get("arquivo", ""))
        if incluir_relacoes:
            relacoes.extend(viz["de"])
            relacoes.extend(viz["para"])
    vistos_e, vistos_r = set(), set()
    entidades = [e for e in entidades
                 if not (e["id"] in vistos_e or vistos_e.add(
                     e["id"]))]
    relacoes = [r for r in relacoes
                if not ((r["origem"], r["tipo"], r["destino"])
                        in vistos_r or vistos_r.add(
                            (r["origem"], r["tipo"],
                             r["destino"])))]
    return SemanticContext(entidades, relacoes,
                           sorted(a for a in arquivos if a))


# ----- plano semântico (ETAPA 4; compõe AgentPlan F26) -----

class PlanoSemantico:
    """Intenção + alvo + consultas + AgentPlan + pré-requisitos."""

    def __init__(self, intencao, alvo: dict | None = None,
                 entidades: list | None = None,
                 consultas: list | None = None,
                 plano=None, precondicoes: list | None = None,
                 alteracoes_propostas: list | None = None,
                 diagnosticos: list | None = None) -> None:
        from .intencao import AgentIntent
        from .plano import AgentPlan

        if not isinstance(intencao, AgentIntent):
            raise ErroELiXX("Loop: plano espera AgentIntent.")
        self.intencao = intencao
        alvo_txt = dict(alvo or {"status": "nao_encontrado"})
        if alvo_txt.get("status") not in STATUS_ALVO:
            raise ErroELiXX("Loop: status de alvo inválido.")
        self.alvo = alvo_txt
        self.entidades = [str(e) for e in (entidades or [])]
        self.consultas = []
        for c in (consultas or []):
            if not isinstance(c, dict) or not B.e_dado(c):
                raise ErroELiXX("Loop: consulta inválida.")
            self.consultas.append(dict(c))
        if plano is not None and not isinstance(plano, AgentPlan):
            raise ErroELiXX("Loop: plano F26 inválido.")
        self.plano = plano
        self.precondicoes = []
        for p in (precondicoes or []):
            if not isinstance(p, dict) or not B.e_dado(p):
                raise ErroELiXX("Loop: pré-condição inválida.")
            self.precondicoes.append(dict(p))
        self.alteracoes_propostas = []
        for a in (alteracoes_propostas or []):
            if not isinstance(a, dict) or not B.e_dado(a):
                raise ErroELiXX("Loop: alteração inválida.")
            self.alteracoes_propostas.append(dict(a))
        self.diagnosticos = []
        for d in (diagnosticos or []):
            if not isinstance(d, dict) or not B.e_dado(d):
                raise ErroELiXX("Loop: diagnóstico inválido.")
            self.diagnosticos.append(dict(d))

    def to_dict(self) -> dict:
        return {"intencao": self.intencao.to_dict(),
                "alvo": dict(self.alvo),
                "entidades": list(self.entidades),
                "consultas": list(self.consultas),
                "plano": (self.plano.to_dict()
                          if self.plano else None),
                "precondicoes": list(self.precondicoes),
                "alteracoes_propostas": list(
                    self.alteracoes_propostas),
                "diagnosticos": list(self.diagnosticos)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"PlanoSemantico({self.intencao.tipo} "
                f"alvo={self.alvo.get('status')})")


def verificar_precondicoes(plano: PlanoSemantico, workspace,
                           permissoes) -> list[dict]:
    """Alvo/arquivo/operação/limites/permissão (sem tocar disco)."""
    from .mudancas import OPERACOES

    checagens = []

    def _ok(nome: str, ok: bool, motivo: str) -> None:
        checagens.append({"nome": nome, "ok": bool(ok),
                          "motivo": motivo})

    alvo = plano.alvo
    _ok("alvo_existe", alvo.get("status") == "unico",
        "alvo único" if alvo.get("status") == "unico"
        else f"alvo {alvo.get('status')}")
    ent = (alvo.get("entidade") or {})
    _ok("arquivo_existe",
        bool(ent.get("arquivo")) and workspace.existe(
            ent["arquivo"]) if ent.get("arquivo") else False,
        f"arquivo {ent.get('arquivo', '?')}")
    for i, alt in enumerate(plano.alteracoes_propostas):
        op = str(alt.get("operacao", ""))
        _ok(f"operacao_{i}",
            op in OPERACOES, f"operação {op}")
        novo = alt.get("conteudo_novo")
        _ok(f"conteudo_{i}",
            novo is None or (isinstance(novo, str)
                             and len(novo) <= 500_000),
            "conteúdo dentro do limite")
        perm = OPERACAO_PERMISSAO.get(op)
        _ok(f"permissao_{i}",
            perm is not None and permissoes.tem(perm),
            f"permissão {perm}")
    plano.precondicoes = checagens
    return checagens


def gerar_changeset(plano: PlanoSemantico):
    """Propostas → ChangeSet F26 (só com pré-condições OK)."""
    from .mudancas import AgentChange, ChangeSet

    if any(not c.get("ok", False) for c in plano.precondicoes):
        raise ErroELiXX("Loop: pré-condição falhou (sem ChangeSet).")
    if not plano.alteracoes_propostas:
        raise ErroELiXX("Loop: sem alterações propostas.")
    cs = ChangeSet()
    for alt in plano.alteracoes_propostas:
        cs.adicionar(AgentChange(
            alt.get("arquivo", ""), alt.get("operacao", ""),
            conteudo_novo=alt.get("conteudo_novo"),
            destino=alt.get("destino"),
            descricao=alt.get("descricao", ""),
            risco=alt.get("risco", "baixo")))
    return cs


# ----- reanálise + diff (ETAPA 7; F27 puro) -----

def reanalisar_modelo(modelo, workspace, caminhos: list) -> dict:
    """Arquivos alterados → atualizar_arquivo → diff honesto."""
    from ..modelo.adaptador import atualizar_arquivo
    from ..modelo.validacao import (SnapshotSemantico,
                                    comparar_snapshots)

    antes = SnapshotSemantico.de_modelo(modelo)
    atualizados = []
    for caminho in caminhos:
        texto = workspace.resolver(str(caminho)).read_text(
            encoding="utf-8")
        atualizar_arquivo(modelo, str(caminho), texto)
        atualizados.append(str(caminho))
    depois = SnapshotSemantico.de_modelo(modelo)
    return {"atualizados": sorted(atualizados),
            "diff": comparar_snapshots(antes, depois)}


def diff_legivel(diff: dict) -> list[str]:
    """Diff → linhas '+id', '-id', '~id' (só informação)."""
    if not isinstance(diff, dict):
        raise ErroELiXX("Loop: diff precisa de dict.")
    linhas = ([f"+ {i}" for i in diff.get("adicionados", [])]
             + [f"- {i}" for i in diff.get("removidos", [])]
             + [f"~ {i}" for i in diff.get("alterados", [])])
    return sorted(linhas)


# ----- loop completo -----

def executar_loop(pedido: dict, modelo, workspace, provider=None,
                  approval=None, permissoes=None,
                  historico=None) -> dict:
    """Pedido → ... → modelo atualizado (sem LLM, sem rede).

    `pedido`: {intencao: {tipo, objetivo, ...}, nome?, tipo_alvo?,
    alteracoes: [{arquivo, operacao, ...}]}. Alterações com conteúdo
    explícito (sem geração mágica). Retorna envelope com status:
    concluida | aguardando_aprovacao | alvo_ambiguo |
    alvo_nao_encontrado | precondicao_falhou.
    """
    from ..editor import diagnosticar_texto
    from .aprovacao import Approval
    from .diagnostico import AgentDiagnostic
    from .intencao import AgentIntent
    from .provider import MockAgentProvider
    from .resultado import AgentResult
    from .tarefa import AgentTask

    if not isinstance(pedido, dict) or not B.e_dado(pedido):
        raise ErroELiXX("Loop: pedido em dict JSON.")
    provider = provider or MockAgentProvider()
    approval = approval or Approval("manual")
    task = AgentTask(str(pedido.get("objetivo", "loop")))
    task.transitar("analisando")

    bruto_intencao = pedido.get("intencao")
    if isinstance(bruto_intencao, dict):
        from .provider import StructuredAgentProvider

        intencao = StructuredAgentProvider().gerar_intencao(
            None, {"intencao": bruto_intencao})
    else:
        intencao = provider.gerar_intencao(None, task.objetivo)
    task.intencao = intencao

    alvo = resolver_alvo(modelo, str(pedido.get("nome", "")),
                         pedido.get("tipo_alvo"))
    if alvo["status"] != "unico":
        task.transitar("falhou")
        task.registrar_evento("alvo", {"status": alvo["status"]})
        return {"status": f"alvo_{alvo['status']}", "alvo": alvo,
                "tarefa": task.to_dict()}
    task.transitar("planejando")
    ctx = construir_contexto_semantico(
        modelo, [alvo["entidade"]["id"]])
    plano = PlanoSemantico(
        intencao, alvo=alvo,
        entidades=[alvo["entidade"]["id"]],
        consultas=[{"kind": "nome",
                    "criterio": alvo["nome"]}],
        alteracoes_propostas=list(pedido.get("alteracoes") or []))
    pre = verificar_precondicoes(
        plano, workspace,
        permissoes or _permissoes_padrao())
    if any(not c["ok"] for c in pre):
        task.transitar("falhou")
        task.registrar_evento("precondicao", {"falhas": [
            c["nome"] for c in pre if not c["ok"]]})
        return {"status": "precondicao_falhou",
                "precondicoes": pre, "tarefa": task.to_dict()}
    changeset = gerar_changeset(plano)
    task.changeset = changeset
    task.transitar("aguardando_aprovacao")
    if approval.modo == "automatico_seguro":
        decisao = approval.decidir(changeset)
        if (decisao["pendentes"] or decisao["recusadas"]
                or len(decisao["aprovadas"])
                != len(changeset.mudancas)):
            task.transitar("falhou")
            return {"status": "aprovacao_recusada",
                    "decisao": decisao,
                    "tarefa": task.to_dict()}
        changeset.aprovar()
    elif approval.modo == "bloqueado":
        task.transitar("falhou")
        return {"status": "aprovacao_recusada",
                "motivo": "modo bloqueado",
                "tarefa": task.to_dict()}
    else:
        if changeset.estado != "aprovado":
            return {"status": "aguardando_aprovacao",
                    "changeset": changeset.revisar(),
                    "tarefa": task.to_dict()}
    task.transitar("aplicando")
    try:
        aplicadas = changeset.aplicar(workspace)
    except ErroELiXX as exc:
        task.transitar("falhou")  # rollback parcial já feito
        task.registrar_evento("aplicacao_falhou",
                              {"motivo": str(exc)[:200]})
        return {"status": "aplicacao_falhou",
                "motivo": str(exc)[:300],
                "tarefa": task.to_dict()}
    task.registrar_evento("aplicacao", aplicadas)
    task.transitar("validando")
    diagnosticos = []
    for caminho in aplicadas.get("arquivos", []):
        try:
            texto = workspace.resolver(caminho).read_text(
                encoding="utf-8")
        except OSError:
            continue
        for d in diagnosticar_texto(texto, caminho):
            diagnosticos.append(AgentDiagnostic.do_studio(d))
    task.diagnosticos = diagnosticos
    task.transitar("executando")
    rean = reanalisar_modelo(modelo, workspace,
                             aplicadas.get("arquivos", []))
    task.transitar("observando")
    erros = [d for d in diagnosticos if d.severidade == "error"]
    task.resultado = AgentResult(
        sucesso=not erros,
        resumo=(f"{len(aplicadas.get('arquivos', []))} arquivo(s) "
                f"via loop; {len(erros)} erro(s)."),
        alteracoes=[{"caminho": m.caminho,
                     "operacao": m.operacao}
                    for m in changeset.mudancas],
        arquivos=aplicadas.get("arquivos", []),
        diagnosticos=diagnosticos,
        preview={"diff": rean["diff"]})
    task.progresso = 1.0
    task.transitar("concluida" if task.resultado.sucesso
                   else "falhou")
    if historico is not None:
        historico.registrar(task)
    return {"status": "concluida" if task.resultado.sucesso
            else "concluida_com_erros",
            "contexto": ctx.to_dict(), "plano": plano.to_dict(),
            "aplicadas": aplicadas, "diff": rean["diff"],
            "diff_legivel": diff_legivel(rean["diff"]),
            "resultado": task.resultado.to_dict(),
            "tarefa": task.to_dict()}


def _permissoes_padrao():
    from .permissao import PermissionSet

    return PermissionSet(["READ", "WRITE", "RENAME", "DELETE",
                          "VALIDATE", "COMPILE", "PREVIEW"])
