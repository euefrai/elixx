"""Planejador semântico de tarefas (Fase 33) — organiza, não executa.

"Uma tarefa complexa é decomposta em operações semânticas verificáveis
antes de tocar no código."

"O Planner decide a ordem das operações; a F32 continua responsável
pela transformação segura em código."

Reuso (sem duplicar): AgentPlan/PlanStep/AgentTask/AgentHistory (F26:
DAG, ordem, rollback, histórico), SemanticOperation (F31), resolver e
ChangeSet/Approval (F28/F26), AlteracaoCodigo/aplicar (F32). Rollback
= evento + desfazer F26 (sem segunda máquina de estados).
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = [
    "ESTADOS_TAREFA33", "MAX_PASSOS_PLANO", "Condicao",
    "PlanoTarefa", "PainelPlano",
    "construir_plano", "validar_plano", "dry_run",
    "explicar_plano", "preparar_execucao", "executar_plano",
    "diff_semantico_passo",
]


def diff_semantico_passo(op, workspace, modelo) -> str:
    """entidade.prop: antes → depois (texto, sem aplicar)."""
    from ..codigo.localizacao import localizar_propriedade

    alt = op.alteracao if hasattr(op, "alteracao") else {}
    nome = op.alvo.nome if hasattr(op, "alvo") else "?"
    tipo = op.alvo.tipo if hasattr(op, "alvo") else None
    ent = next((e for e in modelo.entidades()
                if e.nome == nome and (tipo is None
                                       or e.tipo == tipo)), None)
    if ent is None:
        raise ErroELiXX(f"Diff: entidade '{nome}' ausente.")
    arquivo = str(alt.get("arquivo", ""))
    prop = str(alt.get("propriedade", ""))
    if not arquivo or not prop:
        return f"{nome}: sem diff textual (operação runtime)."
    texto = workspace.resolver(arquivo).read_text(
        encoding="utf-8")
    loc = localizar_propriedade(ent, texto, prop)
    antes = texto.split("\n")[loc.inicio_linha - 1].strip()
    depois = alt.get("valor_texto", "")
    return (f"{ent.id}.{prop}: {antes} "
            f"-> {prop}: {depois}")

ESTADOS_TAREFA33 = ("criada", "analisando", "planejada",
                    "aguardando_aprovacao", "executando",
                    "concluida", "falhou", "cancelada")
"""Espelho legível dos estados AgentTask F26 (sem duplicar)."""

MAX_PASSOS_PLANO = 5000
"""Teto de passos semânticos (só dados; AgentPlan F26 mantém o seu
teto próprio de 200 para execução assistida — planos maiores exigem
fatiamento explícito futuro)."""


class Condicao:
    """Pré/pós-condição declarada (fato verificável, sem código)."""

    def __init__(self, kind: str, descricao: str = "",
                 entidade: str = "", propriedade: str = "",
                 esperado=None) -> None:
        if kind not in ("pre", "pos"):
            raise ErroELiXX('Condição: kind "pre" ou "pos".')
        self.kind = kind
        self.descricao = str(descricao)
        self.entidade = str(entidade)
        self.propriedade = str(propriedade)
        if not B.e_dado(esperado):
            raise ErroELiXX("Condição: esperado em JSON.")
        self.esperado = esperado

    def to_dict(self) -> dict:
        return {"kind": self.kind, "descricao": self.descricao,
                "entidade": self.entidade,
                "propriedade": self.propriedade,
                "esperado": self.esperado}

    @staticmethod
    def from_dict(dados: dict) -> Condicao:
        if not isinstance(dados, dict):
            raise ErroELiXX("Condição precisa de dict.")
        return Condicao(dados.get("kind", "pre"),
                        descricao=dados.get("descricao", ""),
                        entidade=dados.get("entidade", ""),
                        propriedade=dados.get("propriedade", ""),
                        esperado=dados.get("esperado"))

    def __repr__(self) -> str:
        return f"Condicao({self.kind} {self.descricao[:40]})"


_CONTADOR_PLANO = 0


class PlanoTarefa:
    """Tarefa + operações + AgentPlan F26 + condições (só dados)."""

    def __init__(self, objetivo: str, operacoes: list | None = None,
                 dependencias: dict | None = None,
                 tarefa_id: str = "") -> None:
        from .tarefa import AgentTask

        global _CONTADOR_PLANO

        self.objetivo = B.id_valido(objetivo, "objetivo")
        _CONTADOR_PLANO += 1
        self.id = str(tarefa_id).strip() or \
            f"plano_{_CONTADOR_PLANO:05d}"
        ops = list(operacoes or [])
        if len(ops) > MAX_PASSOS_PLANO:
            raise ErroELiXX(f"Plano além de {MAX_PASSOS_PLANO} "
                            "passos.")
        for op in ops:
            _exigir_operacao(op)
        self.operacoes = ops
        deps = dict(dependencias or {})
        validos = {_op_id(ops, i) for i in range(len(ops))}
        for passo, ds in deps.items():
            if not isinstance(ds, list):
                raise ErroELiXX("Dependências em listas.")
            if str(passo) not in validos:
                raise ErroELiXX(f'Plano: passo "{passo}" '
                                "inexistente.")
            for d in ds:
                if str(d) not in validos:
                    raise ErroELiXX(f'Plano: dependência "{d}" '
                                    "inexistente.")
                if str(d) == str(passo):
                    raise ErroELiXX(f'Plano: "{passo}" depende de '
                                    "si.")
        self.dependencias = {str(k): sorted(set(str(d) for d in v))
                             for k, v in deps.items()}
        self.precondicoes: list[Condicao] = []
        self.poscondicoes: list[Condicao] = []
        self.plano = None  # AgentPlan F26 (construir_plano)
        self.task = AgentTask(objetivo, tarefa_id=self.id)
        self.diagnosticos: list[dict] = []

    def to_dict(self) -> dict:
        return {"id": self.id, "objetivo": self.objetivo,
                "operacoes": [_op_dict(op) for op in self.operacoes],
                "dependencias": {k: list(v) for k, v in
                                 self.dependencias.items()},
                "precondicoes": [c.to_dict()
                                 for c in self.precondicoes],
                "poscondicoes": [c.to_dict()
                                 for c in self.poscondicoes],
                "estado": self.task.estado}

    def __repr__(self) -> str:
        return (f"PlanoTarefa({self.id}: {len(self.operacoes)} "
                f"ops, {self.task.estado})")


def _exigir_operacao(op) -> None:
    from .operacoes import SemanticEventOperation, SemanticOperation

    if not isinstance(op, (SemanticOperation,
                           SemanticEventOperation)):
        raise ErroELiXX("Plano espera SemanticOperation.")


def _op_dict(op) -> dict:
    return op.to_dict()


def _op_id(operacoes: list, indice: int) -> str:
    return f"passo_{indice + 1}"


# ----- builder (operações → AgentPlan + condições) -----

def construir_plano(tarefa: PlanoTarefa, modelo=None) -> PlanoTarefa:
    """Resolve, descobre dependências, ordena e gera condições.

    Dependências explícitas (`dependencias`: {passo: [passos]}) +
    auto-cadeia: operações de arquivo no MESMO arquivo viram sequência
    (evita conflito de região sem adivinhar semântica). Referências
    resolvidas no modelo quando fornecido (alvo inexistente/ambíguo =
    diagnóstico + erro).
    """
    from .loop import resolver_alvo
    from .plano import AgentPlan, PlanStep

    ops = tarefa.operacoes
    ids = [_op_id(ops, i) for i in range(len(ops))]
    deps: dict[str, list] = {pid: [] for pid in ids}
    for passo, ds in tarefa.dependencias.items():
        if passo not in deps:
            raise ErroELiXX(f'Plano: passo "{passo}" inexistente.')
        for d in ds:
            if d not in deps:
                raise ErroELiXX(f'Plano: dependência "{d}" '
                                "inexistente.")
            if d == passo:
                raise ErroELiXX(f'Plano: "{passo}" depende de si.')
        deps[passo] = sorted(set(ds))
    # auto-cadeia por arquivo (determinística, documentada)
    por_arquivo: dict[str, list] = {}
    for i, op in enumerate(ops):
        arq = _arquivo_de(op)
        if arq:
            por_arquivo.setdefault(arq, []).append(ids[i])
    for arq, cadeia in por_arquivo.items():
        for anterior, posterior in zip(cadeia, cadeia[1:]):
            if anterior not in deps[posterior]:
                deps[posterior].append(anterior)
        for pid in cadeia:
            deps[pid] = sorted(set(deps[pid]))
    passos = []
    for i, op in enumerate(ops):
        nome_op = op.tipo if hasattr(op, "tipo") else "evento"
        passos.append(PlanStep(
            ids[i], descricao=_descrever_op(op),
            tipo="semantica" if nome_op not in (
                "adicionar", "alterar", "remover",
                "alterar_propriedade", "adicionar_evento",
                "remover_evento") else "codigo",
            dependencias=list(deps[ids[i]]),
            ferramenta="op_semantica",
            argumentos={"indice": i, "operacao": nome_op},
            risco="medio" if _toca_arquivo(op) else "baixo"))
    tarefa.plano = AgentPlan(None, passos,
                               teto=MAX_PASSOS_PLANO)
    tarefa.plano.ordem_execucao()  # valida ciclo aqui (falha cedo)
    if modelo is not None:
        for op in ops:
            for ref in _referencias_de(op):
                alvo = resolver_alvo(modelo, ref["nome"],
                                     ref.get("tipo"))
                if alvo["status"] != "unico":
                    tarefa.diagnosticos.append(
                        {"codigo": "alvo_invalido",
                         "alvo": ref["nome"],
                         "status": alvo["status"]})
        if any(d["codigo"] == "alvo_invalido"
               for d in tarefa.diagnosticos):
            raise ErroELiXX("Plano: alvo inexistente/ambíguo "
                            "(sem ChangeSet).")
    tarefa.precondicoes = _gerar_pre(tarefa, modelo)
    tarefa.poscondicoes = _gerar_pos(tarefa)
    tarefa.task.transitar("analisando")
    return tarefa


def _arquivo_de(op) -> str:
    alt = op.alteracao if hasattr(op, "alteracao") else {}
    if isinstance(alt, dict):
        return str(alt.get("arquivo", ""))
    return ""


def _toca_arquivo(op) -> bool:
    from .operacoes import OPERACOES_ARQUIVO

    if hasattr(op, "tipo"):
        return op.tipo in OPERACOES_ARQUIVO
    return True  # evento: pode virar arquivo


def _descrever_op(op) -> str:
    from .operacoes import explicar_operacao

    try:
        return explicar_operacao(op)
    except ErroELiXX:
        return f"Operação {getattr(op, 'tipo', '?')}"


def _referencias_de(op) -> list[dict]:
    refs = []
    alvos = [op.alvo] if hasattr(op, "alvo") else []
    if hasattr(op, "efeitos"):
        alvos.append(op.alvo)
        for efeito in op.efeitos:
            alvos.append(efeito.alvo)
    for alvo in alvos:
        nome = alvo.nome if hasattr(alvo, "nome") \
            else alvo.get("nome", "")
        tipo = alvo.tipo if hasattr(alvo, "tipo") \
            else alvo.get("tipo")
        if nome:
            refs.append({"nome": nome, "tipo": tipo})
    return refs


def _gerar_pre(tarefa: PlanoTarefa, modelo) -> list[Condicao]:
    conds = []
    for i, op in enumerate(tarefa.operacoes):
        for ref in _referencias_de(op):
            conds.append(Condicao(
                "pre", f"{_op_id(tarefa.operacoes, i)}: alvo "
                       f"'{ref['nome']}' único",
                entidade=ref["nome"]))
        arq = _arquivo_de(op)
        if arq:
            conds.append(Condicao(
                "pre", f"{_op_id(tarefa.operacoes, i)}: arquivo "
                       f"'{arq}' existe", entidade=arq))
    return conds


def _gerar_pos(tarefa: PlanoTarefa) -> list[Condicao]:
    conds = []
    for i, op in enumerate(tarefa.operacoes):
        for ref in _referencias_de(op):
            conds.append(Condicao(
                "pos", f"{_op_id(tarefa.operacoes, i)}: "
                       f"'{ref['nome']}' existe após",
                entidade=ref["nome"]))
    return conds


# ----- validador (só leitura) -----

def validar_plano(tarefa: PlanoTarefa, modelo=None,
                  workspace=None) -> dict:
    """IDs, DAG, operações, refs, limites (sem executar nada)."""
    if not isinstance(tarefa, PlanoTarefa):
        raise ErroELiXX("Validador espera PlanoTarefa.")
    if tarefa.plano is None:
        return {"valido": False, "codigo": "sem_plano",
                "motivo": "construir_plano antes."}
    try:
        ordem = tarefa.plano.ordem_execucao()
    except ErroELiXX as exc:
        return {"valido": False, "codigo": "dag_invalido",
                "motivo": str(exc)[:200]}
    if modelo is not None:
        from .loop import resolver_alvo

        for op in tarefa.operacoes:
            for ref in _referencias_de(op):
                alvo = resolver_alvo(modelo, ref["nome"],
                                     ref.get("tipo"))
                if alvo["status"] != "unico":
                    return {"valido": False,
                            "codigo": "alvo_invalido",
                            "motivo": f"'{ref['nome']}': "
                                      f"{alvo['status']}."}
    if workspace is not None:
        for op in tarefa.operacoes:
            arq = _arquivo_de(op)
            if not arq:
                continue
            try:
                existe = workspace.existe(arq)
            except ErroELiXX:
                return {"valido": False,
                        "codigo": "arquivo_ausente",
                        "motivo": f'"{arq}" inválido/traversal.'}
            if not existe:
                return {"valido": False,
                        "codigo": "arquivo_ausente",
                        "motivo": f'"{arq}" fora do workspace.'}
    return {"valido": True, "codigo": "ok",
            "motivo": f"{len(ordem)} passos ordenados.",
            "ordem": ordem}


# ----- dry-run (nada escreve) -----

def dry_run(tarefa: PlanoTarefa, modelo=None) -> dict:
    """O que seria feito: passos, arquivos, entidades, riscos."""
    if tarefa.plano is None:
        raise ErroELiXX("Dry-run exige plano construído.")
    ordem = tarefa.plano.ordem_execucao()
    por_id = {p.id: p for p in tarefa.plano.passos.values()}
    passos = []
    arquivos, entidades, riscos = set(), set(), set()
    for pid in ordem:
        passo = por_id[pid]
        idx = passo.argumentos.get("indice", 0)
        op = tarefa.operacoes[idx]
        arq = _arquivo_de(op)
        if arq:
            arquivos.add(arq)
        for ref in _referencias_de(op):
            entidades.add(ref["nome"])
        riscos.add(passo.risco)
        passos.append({"id": pid,
                       "descricao": passo.descricao,
                       "dependencias": list(passo.dependencias),
                       "risco": passo.risco, "arquivo": arq})
    return {"passos": passos, "ordem": ordem,
            "arquivos": sorted(arquivos),
            "entidades": sorted(entidades),
            "riscos": sorted(riscos)}


def explicar_plano(tarefa: PlanoTarefa) -> str:
    """Texto PT determinístico (sem LLM)."""
    n = len(tarefa.operacoes)
    linhas = [f"Vou executar {n} etapa(s).", ""]
    try:
        ordem = tarefa.plano.ordem_execucao() if tarefa.plano \
            else []
    except ErroELiXX:
        ordem = []
    por_id = {p.id: p for p in tarefa.plano.passos.values()} \
        if tarefa.plano else {}
    for numero, pid in enumerate(ordem, start=1):
        linhas.append(f"{numero}. {por_id[pid].descricao}")
    secs = dry_run(tarefa) if tarefa.plano else {"arquivos": [],
                                                 "entidades": []}
    linhas += ["",
                f"Arquivos: {', '.join(secs['arquivos']) or '—'}",
                f"Entidades: {', '.join(secs['entidades']) or '—'}",
                "Aprovação necessária antes de aplicar."]
    return "\n".join(linhas)


# ----- preparação + execução (F32 aplica; F26 desfaz) -----

def preparar_execucao(tarefa: PlanoTarefa, workspace, modelo,
                      permissoes=None) -> dict:
    """Constrói ChangeSets por passo de arquivo (sem aplicar)."""
    from ..codigo.sincronizador import SincronizadorCodigo
    from .loop import gerar_changeset, verificar_precondicoes

    sinc = SincronizadorCodigo(workspace, modelo)
    preparados = []
    for i, op in enumerate(tarefa.operacoes):
        pid = _op_id(tarefa.operacoes, i)
        if not _toca_arquivo(op):
            preparados.append({"passo": pid, "tipo": "runtime",
                               "changeset": None})
            continue
        alt = _alteracao_de(sinc, op)
        plano_sem = _plano_sem_para(op, alt, sinc, workspace)
        pre = verificar_precondicoes(
            plano_sem, workspace,
            permissoes or _permissoes_tudo())
        if any(not c["ok"] for c in pre):
            raise ErroELiXX(f"Plano: pré-condição de {pid} falhou "
                            f"({[c['nome'] for c in pre if not c['ok']]})")
        cs = gerar_changeset(plano_sem)
        preparados.append({"passo": pid, "tipo": "codigo",
                           "changeset": cs,
                           "alteracao": alt.to_dict()})
    return {"preparados": preparados}


def _alteracao_de(sinc, op):
    from ..codigo.gerador import gerar_alteracao, validar_candidato

    texto, ent = sinc._texto_e_entidade(op)
    alt = gerar_alteracao(op, ent, texto)
    veredito = validar_candidato(alt, texto, ent)
    if not veredito["ok"]:
        raise ErroELiXX(f"Plano: {veredito['codigo']}: "
                        f"{veredito['motivo']}")
    return alt


def _plano_sem_para(op, alt, sinc, workspace):
    from .intencao import AgentIntent
    from .loop import PlanoSemantico
    from .operacoes import operacao_para_intent

    try:
        aintent = operacao_para_intent(op)
    except ErroELiXX:
        aintent = AgentIntent("modificar_interface",
                             objetivo=f"aplicar {op.tipo}")
    texto_atual = workspace.resolver(
        alt.arquivo).read_text(encoding="utf-8")
    ent_id = alt.entidade_id
    ent = next((e for e in sinc.modelo.entidades()
                if e.id == ent_id), None)
    return PlanoSemantico(
        aintent,
        alvo={"status": "unico", "entidade": ent.to_dict()}
        if ent is not None else {"status": "unico"},
        entidades=[ent_id] if ent_id else [],
        alteracoes_propostas=[{
            "arquivo": alt.arquivo,
            "operacao": "editar",
            "conteudo_novo": alt.aplicar_texto(texto_atual),
            "descricao": alt.motivo, "risco": "medio"}])


def _permissoes_tudo():
    from .permissao import PermissionSet

    return PermissionSet(["READ", "WRITE", "RENAME", "DELETE",
                          "VALIDATE", "COMPILE", "PREVIEW"])


def executar_plano(tarefa: PlanoTarefa, ctx: dict) -> dict:
    """Ordem DAG → runtime/arquivo → pós-condições → rollback.

    `ctx`: workspace, modelo, personagens, permissoes, approval,
    historico?, preparar (saída de preparar_execucao; sem ela, nada
    de arquivo aplica). Retorna resumo; registra AgentTask F26.
    """
    workspace = ctx.get("workspace")
    modelo = ctx.get("modelo")
    personagens = ctx.get("personagens") or {}
    approval = ctx.get("approval")
    historico = ctx.get("historico")
    preparar = ctx.get("preparar")
    if tarefa.plano is None:
        raise ErroELiXX("Execução exige plano construído.")
    task = tarefa.task
    task.transitar("analisando")
    ordem = tarefa.plano.ordem_execucao()
    aplicados: list = []  # ChangeSets aplicados (rollback)
    tocadas: list = []
    try:
        task.transitar("planejando")
        task.transitar("aguardando_aprovacao")
        if approval is not None:
            from .aprovacao import Approval as _Ap

            if isinstance(approval, _Ap) and \
                    approval.modo == "bloqueado":
                raise ErroELiXX("Plano: modo bloqueado.")
        task.transitar("aplicando")
        pre = (preparar or {}).get("preparados", [])
        por_passo = {p["passo"]: p for p in pre}
        for pid in ordem:
            passo = tarefa.plano.passo(pid)
            passo.transitar("executando")
            idx = [p.id for p in tarefa.plano.passos.values()
                   ].index(pid)
            op = tarefa.operacoes[idx]
            if _toca_arquivo(op):
                _aplicar_passo_codigo(tarefa, pid, por_passo,
                                      workspace, modelo, approval,
                                      aplicados)
            else:
                tocadas.extend(_aplicar_passo_runtime(
                    op, personagens))
            passo.transitar("concluido")
        task.transitar("validando")
        _checar_pos(tarefa, workspace, modelo)
        task.transitar("executando")
        task.transitar("observando")
        from .resultado import AgentResult

        task.resultado = AgentResult(
            True, resumo=f"{len(ordem)} passo(s) aplicados.",
            arquivos=_arquivos_de(preparar), preview={})
        task.progresso = 1.0
        task.transitar("concluida")
    except ErroELiXX as exc:
        for cs in reversed(aplicados):
            try:
                cs.desfazer(workspace)
            except ErroELiXX:
                pass
        task.registrar_evento("rollback",
                              {"motivo": str(exc)[:200]})
        if task.estado not in ("concluida", "falhou",
                               "cancelada"):
            task.transitar("falhou")
        raise
    finally:
        if historico is not None and task.estado in (
                "concluida", "falhou"):
            historico.registrar(task)
    return {"ok": True, "ordem": ordem, "tocadas": tocadas,
            "aplicados": len(aplicados),
            "estado": task.estado}


def _arquivos_de(preparar) -> list:
    return sorted({a.get("alteracao", {}).get("arquivo", "")
                   for a in (preparar or {}).get("preparados", [])
                   if a.get("tipo") == "codigo"})


def _aplicar_passo_codigo(tarefa, pid, por_passo, workspace,
                          modelo, approval, aplicados) -> None:
    from ..codigo.sincronizador import aplicar_com_changeset
    from ..codigo.gerador import gerar_alteracao, validar_candidato
    from ..codigo.sincronizador import SincronizadorCodigo

    from ..codigo.gerador import gerar_alteracao, validar_candidato
    from ..codigo.sincronizador import SincronizadorCodigo

    prep = por_passo.get(pid)
    if prep is None or prep.get("changeset") is None:
        raise ErroELiXX(f"Plano: passo {pid} sem preparação "
                        "aprovável (prepare antes).")
    cs = prep["changeset"]
    if cs.estado != "aprovado":
        if approval is not None and getattr(
                approval, "modo", "") == "automatico_seguro":
            decisao = approval.decidir(cs)
            if decisao["pendentes"] or decisao["recusadas"]:
                raise ErroELiXX(f"Plano: passo {pid} recusado "
                                "pelo auto-seguro.")
            cs.aprovar()
        else:
            raise ErroELiXX(f"Plano: passo {pid} sem aprovação "
                            "(aprove o ChangeSet preparado).")
    idx = [p.id for p in tarefa.plano.passos.values()].index(pid)
    op = tarefa.operacoes[idx]
    sinc = SincronizadorCodigo(workspace, modelo)
    # anti-stale: regenera no conteúdo atual e compara
    texto, ent = sinc._texto_e_entidade(op)
    alt = gerar_alteracao(op, ent, texto)
    veredito = validar_candidato(alt, texto, ent)
    if not veredito["ok"]:
        raise ErroELiXX(f"Plano: {pid} obsoleto "
                        f"({veredito['codigo']}).")
    if alt.to_dict() != prep["alteracao"]:
        raise ErroELiXX(f"Plano: {pid} divergiu da preparação "
                        "(re-prepare e re-aprove).")
    aplicadas = cs.aplicar(workspace)
    sinc.codigo_para_modelo(alt.arquivo)  # reparse + índice
    aplicados.append(cs)


def _aplicar_passo_runtime(op, personagens) -> list:
    from .operacoes import operacao_para_ferramentas

    tocadas: list = []
    for chamada in operacao_para_ferramentas(op):
        ferramenta = chamada["ferramenta"]
        args = dict(chamada["argumentos"])
        nome = args.get("personagem", "")
        if nome not in personagens:
            raise ErroELiXX(f'Plano: personagem "{nome}" '
                            "indisponível.")
        perso = personagens[nome]
        if ferramenta == "personagem_pose":
            tocadas.extend(perso.aplicar_pose(args["pose"]))
        elif ferramenta == "personagem_expressao":
            pose = perso.obter_pose(args["expressao"])
            if not pose.expressao:
                raise ErroELiXX("Plano: não é expressão.")
            tocadas.extend(perso.aplicar_pose(pose))
        elif ferramenta == "personagem_transform":
            from ...visual.personagem import Pose

            parte = args.get("parte", "")
            tocadas.extend(perso.aplicar_pose(Pose(
                "passo_plano",
                entradas={parte: args.get("props", {})})))
        else:
            raise ErroELiXX(f'Plano: ferramenta "{ferramenta}" sem '
                            "executor seguro.")
    return tocadas


def _checar_pos(tarefa: PlanoTarefa, workspace, modelo) -> None:
    from ..codigo.localizacao import localizar_propriedade

    for cond in tarefa.poscondicoes:
        if cond.entidade and cond.propriedade and \
                cond.esperado is not None:
            ent = next((e for e in modelo.entidades()
                        if e.nome == cond.entidade or
                        e.id == cond.entidade), None)
            if ent is None:
                raise ErroELiXX(f"Plano: pós-condição sem "
                                f'"{cond.entidade}".')
            if cond.propriedade == "existe":
                continue
            texto = workspace.resolver(ent.arquivo).read_text(
                encoding="utf-8")
            loc = localizar_propriedade(ent, texto,
                                        cond.propriedade)
            linha = texto.split("\n")[loc.inicio_linha - 1]
            valor = linha.split(":", 1)[1].strip() \
                if ":" in linha else ""
            if str(cond.esperado) not in valor:
                raise ErroELiXX(
                    f"Plano: pós-condição falhou "
                    f"({cond.entidade}.{cond.propriedade} ≠ "
                    f"{cond.esperado}).")


# ----- painel headless (UI liga aqui; Tk não entra no núcleo) -----

class PainelPlano:
    """Visão do plano: estados, seleção, diffs, aprovação, progresso."""

    def __init__(self, tarefa: PlanoTarefa) -> None:
        if not isinstance(tarefa, PlanoTarefa):
            raise ErroELiXX("Painel espera PlanoTarefa.")
        self.tarefa = tarefa
        self.selecionado: str | None = None
        self.aprovado = False
        self._diffs: dict[str, dict] = {}

    def passos(self) -> list[dict]:
        if self.tarefa.plano is None:
            return []
        return [{"id": p.id, "descricao": p.descricao,
                 "estado": p.estado, "risco": p.risco,
                 "dependencias": list(p.dependencias)}
                for _, p in sorted(
                    self.tarefa.plano.passos.items())]

    def selecionar_passo(self, passo_id: str) -> dict:
        if self.tarefa.plano is None:
            raise ErroELiXX("Painel: sem plano.")
        passo = self.tarefa.plano.passo(passo_id)
        self.selecionado = passo_id
        return {"id": passo.id, "descricao": passo.descricao,
                "estado": passo.estado,
                "dependencias": list(passo.dependencias),
                "ferramenta": passo.ferramenta,
                "argumentos": dict(passo.argumentos)}

    def diff_passo(self, passo_id: str, workspace,
                   modelo) -> dict:
        """Código + semântico do passo (sem aplicar)."""
        from ..codigo.gerador import gerar_alteracao
        from ..codigo.sincronizador import (SincronizadorCodigo,
                                            diff_textual)

        if self.tarefa.plano is None:
            raise ErroELiXX("Painel: sem plano.")
        idx = [p.id for p in self.tarefa.plano.passos.values()
               ].index(passo_id)
        op = self.tarefa.operacoes[idx]
        sinc = SincronizadorCodigo(workspace, modelo)
        try:
            texto, ent = sinc._texto_e_entidade(op)
        except ErroELiXX as exc:
            diff = {"codigo": "PASSO_SEM_CODIGO",
                    "motivo": str(exc)[:200], "trocas": []}
            self._diffs[passo_id] = diff
            return diff
        alt = gerar_alteracao(op, ent, texto)
        novo = alt.aplicar_texto(texto)
        diff = diff_textual(texto, novo)
        diff["semantico"] = diff_semantico_passo(
            op, workspace, modelo)
        diff["codigo"] = "ok"
        self._diffs[passo_id] = diff
        return diff

    def aprovar(self) -> bool:
        self.aprovado = True
        return True

    def recusar(self) -> bool:
        self.aprovado = False
        if self.tarefa.plano:
            for passo in self.tarefa.plano.passos.values():
                if passo.estado == "pendente":
                    passo.transitar("cancelado")
        return False

    def cancelar(self) -> bool:
        return self.recusar()

    def progresso(self) -> dict:
        if self.tarefa.plano is None:
            return {"total": 0, "concluidos": 0,
                    "percentual": 0}
        passos = list(self.tarefa.plano.passos.values())
        concluidos = sum(1 for p in passos
                         if p.estado == "concluido")
        total = len(passos)
        return {"total": total, "concluidos": concluidos,
                "percentual": (100 * concluidos // total
                               if total else 0)}

    def resumo(self) -> dict:
        secs = dry_run(self.tarefa) if self.tarefa.plano else {
            "arquivos": [], "entidades": []}
        return {"objetivo": self.tarefa.objetivo,
                "estado": self.tarefa.task.estado,
                "aprovado": self.aprovado,
                "progresso": self.progresso(),
                "arquivos": secs["arquivos"],
                "entidades": secs["entidades"]}
