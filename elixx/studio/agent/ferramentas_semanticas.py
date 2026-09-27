"""Semantic Agent Tools (Fase 36A) — significado sem acesso arbitrário.

"O Agent recebe ferramentas sem receber acesso arbitrário ao computador."

Sobre F26/F27/F31/F32/F33/F34 sem duplicar: o registry F26 (19 tools
de runtime) fica intacto; aqui vivem TOOLS SEMÂNTICAS (consultar o
modelo, analisar contexto, localizar código, propor operação/plano).
Escrever = só via proposta → ChangeSet aprovado (nunca tool→arquivo).
"""
from __future__ import annotations

import json
import math

from ...erros import ErroELiXX
from . import _base as B

__all__ = [
    "CATEGORIAS_TOOL", "PERMISSOES_TOOL", "ESTADOS_CALL",
    "MAX_CALLS", "MAX_ARGS", "MAX_RESULTADOS", "MAX_PAYLOAD",
    "MAX_TRACE", "MAX_PROFUNDIDADE_TOOLS",
    "SemanticTool", "ToolResult", "SemanticToolRegistry",
    "AgentToolCall", "ToolTrace", "SemanticPermissions",
    "TOOLS",
    "executar_chamada", "executar_sequencia",
]

CATEGORIAS_TOOL = ("CONSULTA", "ANALISE", "LOCALIZACAO", "OPERACAO",
                   "PLANO", "CODIGO")
"""Categorias (§6; cada tool declara a sua)."""

PERMISSOES_TOOL = ("READ", "ANALYZE", "PROPOSE", "APPLY")
"""Níveis (§13): consulta=READ, análise=ANALYZE, proposta=PROPOSE;
APPLY nunca é concedido aqui (só Approval F26/F33)."""

ESTADOS_CALL = ("PENDENTE", "VALIDANDO", "EXECUTANDO", "CONCLUIDA",
                "FALHOU", "BLOQUEADA", "CANCELADA")
"""Estados de chamada (transições validadas)."""

MAX_CALLS = 1000
"""Teto de chamadas por trace (anti-explosão)."""

MAX_ARGS = 20
"""Teto de argumentos por chamada."""

MAX_RESULTADOS = 200
"""Teto de itens por resultado."""

MAX_PAYLOAD = 100_000
"""Teto serializado de argumentos+resultado."""

MAX_TRACE = 200
"""Teto de registros no trace."""

MAX_PROFUNDIDADE_TOOLS = 5
"""Teto de composição (sequência curta; sem recursão)."""

_TRANSICOES_CALL = {
    "PENDENTE": ("VALIDANDO", "CANCELADA", "BLOQUEADA"),
    "VALIDANDO": ("EXECUTANDO", "FALHOU", "BLOQUEADA",
                  "CANCELADA"),
    "EXECUTANDO": ("CONCLUIDA", "FALHOU", "CANCELADA"),
    "CONCLUIDA": (),
    "FALHOU": (),
    "BLOQUEADA": ("CANCELADA",),
    "CANCELADA": (),
}


class SemanticPermissions:
    """READ/ANALYZE/PROPOSE (APPLY sempre negado aqui)."""

    def __init__(self, concedidas: list | None = None) -> None:
        self.concedidas: set[str] = set()
        for p in (concedidas or []):
            self.conceder(p)

    def conceder(self, permissao: str) -> SemanticPermissions:
        nome = str(permissao).strip().upper()
        if nome == "APPLY":
            raise ErroELiXX("Tools: APPLY nunca concedido aqui "
                            "(só via Approval F26/F33).")
        if nome not in PERMISSOES_TOOL:
            raise ErroELiXX(f'Tools: permissão "{permissao}" '
                            "inválida.")
        self.concedidas.add(nome)
        return self

    def tem(self, permissao: str) -> bool:
        return str(permissao).strip().upper() in self.concedidas

    def exigir(self, permissao: str, o_que: str = "operação"
              ) -> None:
        if not self.tem(permissao):
            raise ErroELiXX(f'Tools: "{o_que}" exige {permissao} '
                            "(negada por padrão).")

    def listar(self) -> list[str]:
        return sorted(self.concedidas)

    def __repr__(self) -> str:
        return f"SemanticPermissions({self.listar()})"


class SemanticTool:
    """Definição: id, nome, descrição, categoria, permissão, limites."""

    def __init__(self, tool_id: str, nome: str, descricao: str,
                 categoria: str, permissao: str = "READ",
                 origem: str = "F36") -> None:
        self.id = B.id_valido(tool_id, "id da tool")
        self.nome = str(nome).strip() or self.id
        self.descricao = str(descricao)
        if categoria not in CATEGORIAS_TOOL:
            raise ErroELiXX(f'Tools: categoria "{categoria}" '
                            "inválida.")
        self.categoria = categoria
        perm = str(permissao).strip().upper()
        if perm not in PERMISSOES_TOOL:
            raise ErroELiXX(f'Tools: permissão "{permissao}".')
        self.permissao = perm
        self.origem = str(origem)

    def esquema(self) -> dict:
        return {"id": self.id, "nome": self.nome,
                "descricao": self.descricao,
                "categoria": self.categoria,
                "permissao": self.permissao, "origem": self.origem}

    def __repr__(self) -> str:
        return f"SemanticTool({self.id})"


class ToolResult:
    """Envelope estruturado (nunca string solta quando há dados)."""

    def __init__(self, sucesso: bool, dados=None,
                 mensagem: str = "", diagnostico: str = "",
                 origem: str = "", avisos: list | None = None,
                 erros: list | None = None) -> None:
        self.sucesso = bool(sucesso)
        dados_txt = dados if dados is not None else {}
        if not B.e_dado(dados_txt):
            raise ErroELiXX("Tools: dados inválidos (JSON).")
        if len(json.dumps(dados_txt, sort_keys=True)) > MAX_PAYLOAD:
            raise ErroELiXX("Tools: resultado além do teto.")
        self.dados = dados_txt
        self.mensagem = str(mensagem)[:500]
        self.diagnostico = str(diagnostico)[:300]
        self.origem = str(origem)
        self.avisos = [str(a)[:200] for a in (avisos or [])]
        self.erros = [str(e)[:200] for e in (erros or [])]

    def to_dict(self) -> dict:
        return {"sucesso": self.sucesso, "dados": self.dados,
                "mensagem": self.mensagem,
                "diagnostico": self.diagnostico,
                "origem": self.origem, "avisos": list(self.avisos),
                "erros": list(self.erros)}

    def __repr__(self) -> str:
        return f"ToolResult(sucesso={self.sucesso})"


class AgentToolCall:
    """Chamada registrada (auditoria sem segredos)."""

    _contador = 0

    def __init__(self, tool_id: str, argumentos: dict | None = None,
                 contexto: str = "", call_id: str = "") -> None:
        AgentToolCall._contador += 1
        self.id = str(call_id).strip() or \
            f"call_{AgentToolCall._contador:04d}"
        self.tool_id = B.id_valido(tool_id, "tool")
        args = dict(argumentos or {})
        if len(args) > MAX_ARGS:
            raise ErroELiXX(f"Tools: além de {MAX_ARGS} args.")
        if not B.e_dado(args):
            raise ErroELiXX("Tools: argumentos inválidos.")
        if len(json.dumps(args, sort_keys=True)) > MAX_PAYLOAD:
            raise ErroELiXX("Tools: payload além do teto.")
        self.argumentos = args
        self.contexto = str(contexto)[:500]
        self.estado = "PENDENTE"
        self.resultado = None

    def transitar(self, novo: str) -> AgentToolCall:
        if novo not in _TRANSICOES_CALL.get(self.estado, ()):
            raise ErroELiXX(f"Tools: {self.estado} → {novo} "
                            "inválido.")
        self.estado = novo
        return self

    def to_dict(self) -> dict:
        return {"id": self.id, "tool_id": self.tool_id,
                "argumentos": dict(self.argumentos),
                "contexto": self.contexto, "estado": self.estado,
                "resultado": (self.resultado.to_dict()
                              if self.resultado else None)}

    def __repr__(self) -> str:
        return f"AgentToolCall({self.tool_id} {self.estado})"


class ToolTrace:
    """Trilha ordenada (explicável, com teto, sem segredos)."""

    def __init__(self) -> None:
        self.chamadas: list[AgentToolCall] = []

    def registrar(self, chamada: AgentToolCall) -> AgentToolCall:
        if not isinstance(chamada, AgentToolCall):
            raise ErroELiXX("Trace espera AgentToolCall.")
        if len(self.chamadas) >= MAX_TRACE:
            raise ErroELiXX(f"Trace além de {MAX_TRACE}.")
        self.chamadas.append(chamada)
        return chamada

    def explicar(self) -> str:
        linhas = ["TOOL TRACE", ""]
        for i, chamada in enumerate(self.chamadas, start=1):
            marca = "✓" if chamada.estado == "CONCLUIDA" \
                else "×" if chamada.estado == "FALHOU" else "○"
            linhas.append(f"{i:02d} {marca} {chamada.tool_id}")
            if chamada.argumentos:
                resumo = ", ".join(
                    f"{k}={str(v)[:40]}"
                    for k, v in chamada.argumentos.items())
                linhas.append(f"   entrada: {resumo}")
            if chamada.resultado is not None:
                linhas.append(
                    f"   resultado: "
                    f"{chamada.resultado.mensagem[:100]}")
        return "\n".join(linhas)

    def to_dict(self) -> dict:
        return {"chamadas": [c.to_dict() for c in self.chamadas]}

    def __repr__(self) -> str:
        return f"ToolTrace({len(self.chamadas)} chamadas)"


# ----- implementações (reuso F27/F34/F32/F31/F33; só leitura/proposta)

def _modelo_de(ambiente):
    modelo = getattr(ambiente, "modelo", None)
    if modelo is None:
        raise ErroELiXX("Tools: ambiente sem modelo F27.")
    return modelo


def _workspace_de(ambiente):
    ws = getattr(ambiente, "workspace", None)
    if ws is None or not ws.aberto:
        raise ErroELiXX("Tools: workspace fechado.")
    return ws


def _ok(dados, mensagem: str = "", origem: str = "") -> ToolResult:
    if isinstance(dados, list):
        dados = dados[:MAX_RESULTADOS]
    return ToolResult(True, dados, mensagem, origem=origem)


def _falha(mensagem: str, origem: str = "") -> ToolResult:
    return ToolResult(False, {}, mensagem, origem=origem,
                      erros=[mensagem])


def t_buscar_entidade(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    nome = str(args.get("nome", "")).strip()
    if not nome:
        return _falha("nome vazio.", origem="buscar_entidade")
    achados = ConsultaSemantica(_modelo_de(ambiente)
                                ).encontrar_por_nome(nome)
    if not achados:
        return _falha(f'"{nome}" não encontrado.',
                      origem="buscar_entidade")
    return _ok({"entidade": achados[0].to_dict(),
                "total": len(achados)},
               f"encontrado: {achados[0].id}",
               origem="buscar_entidade")


def t_consultar_entidade(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    ent_id = str(args.get("id", "")).strip()
    try:
        viz = ConsultaSemantica(_modelo_de(ambiente)).vizinhanca(
            ent_id)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="consultar_entidade")
    return _ok(viz, f"entidade {ent_id}",
               origem="consultar_entidade")


def t_consultar_relacoes(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    ent_id = str(args.get("id", "")).strip()
    q = ConsultaSemantica(_modelo_de(ambiente))
    rels = [r.to_dict() for r in q.relacoes_de(ent_id)] + \
        [r.to_dict() for r in q.relacoes_para(ent_id)]
    return _ok({"relacoes": rels[:MAX_RESULTADOS],
                "total": len(rels)},
               f"{len(rels)} relações.",
               origem="consultar_relacoes")


def t_consultar_por_tipo(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    tipo = str(args.get("tipo", "")).strip()
    achados = ConsultaSemantica(_modelo_de(ambiente)
                                ).encontrar_por_tipo(tipo)
    return _ok({"ids": [e.id for e in
                        achados[:MAX_RESULTADOS]],
                "total": len(achados)},
               f"{len(achados)} do tipo {tipo}.",
               origem="consultar_por_tipo")


def t_consultar_por_arquivo(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    arq = str(args.get("arquivo", "")).strip()
    achados = ConsultaSemantica(_modelo_de(ambiente)
                                ).encontrar_por_arquivo(arq)
    return _ok({"ids": [e.id for e in
                        achados[:MAX_RESULTADOS]],
                "total": len(achados)},
               f"{len(achados)} em {arq}.",
               origem="consultar_por_arquivo")


def t_consultar_personagem(ambiente, args: dict) -> ToolResult:
    nome = str(args.get("nome", "")).strip()
    personagens = getattr(ambiente, "personagens", None) or {}
    if nome in personagens:
        perso = personagens[nome]
        return _ok(
            {"nome": perso.nome,
             "partes": sorted(perso.partes),
             "poses": sorted(perso.poses),
             "direcao": perso.direcao},
            f"personagem {nome} (F12).",
            origem="consultar_personagem")
    from ..modelo.consulta import ConsultaSemantica

    achados = [e.to_dict() for e in ConsultaSemantica(
        _modelo_de(ambiente)).encontrar_por_nome(nome)
        if e.tipo == "personagem"]
    if not achados:
        return _falha(f'personagem "{nome}" ausente.',
                      origem="consultar_personagem")
    return _ok({"personagem": achados[0]},
               f"personagem {nome} (F27).",
               origem="consultar_personagem")


def _partes_de(ambiente, nome: str) -> tuple:
    personagens = getattr(ambiente, "personagens", None) or {}
    if nome in personagens:
        return sorted(personagens[nome].partes), "F12"
    from ..modelo.consulta import ConsultaSemantica

    modelo = _modelo_de(ambiente)
    partes = [e.id for e in modelo.entidades()
              if e.tipo == "parte" and (
                  e.nome == nome or e.id.startswith(
                      f"parte:{nome}."))]
    return partes, "F27"


def t_consultar_partes(ambiente, args: dict) -> ToolResult:
    nome = str(args.get("nome", "")).strip()
    partes, origem = _partes_de(ambiente, nome)
    return _ok({"partes": partes[:MAX_RESULTADOS],
                "total": len(partes)},
               f"{len(partes)} partes.",
               origem="consultar_partes")


def t_consultar_poses(ambiente, args: dict) -> ToolResult:
    nome = str(args.get("nome", "")).strip()
    personagens = getattr(ambiente, "personagens", None) or {}
    if nome in personagens:
        poses = sorted(personagens[nome].poses)
        return _ok({"poses": poses}, f"{len(poses)} poses.",
                   origem="consultar_poses")
    from ..modelo.consulta import ConsultaSemantica

    poses = [e.id for e in ConsultaSemantica(
        _modelo_de(ambiente)).encontrar_por_tipo("pose")
        if nome in e.id]
    return _ok({"poses": poses[:MAX_RESULTADOS]},
               f"{len(poses)} poses (F27).",
               origem="consultar_poses")


def t_consultar_gestos(ambiente, args: dict) -> ToolResult:
    return _ok({"gestos": [], "nota": "gestos vivem no rig F23; "
                                     "vincule o rig no ambiente."},
               "sem gestos vinculados.",
               origem="consultar_gestos")


def t_consultar_animacoes(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    anims = [e.to_dict() for e in ConsultaSemantica(
        _modelo_de(ambiente)).encontrar_por_tipo("animacao")]
    return _ok({"animacoes": anims[:MAX_RESULTADOS]},
               f"{len(anims)} animações.",
               origem="consultar_animacoes")


def t_consultar_assets(ambiente, args: dict) -> ToolResult:
    from ..modelo.consulta import ConsultaSemantica

    assets = [e.to_dict() for e in ConsultaSemantica(
        _modelo_de(ambiente)).encontrar_por_tipo("asset")]
    return _ok({"assets": assets[:MAX_RESULTADOS]},
               f"{len(assets)} assets.",
               origem="consultar_assets")


def t_consultar_capabilities(ambiente, args: dict) -> ToolResult:
    nome = str(args.get("nome", "")).strip()
    personagens = getattr(ambiente, "personagens", None) or {}
    if nome in personagens:
        caps = sorted(personagens[nome].capacidades_compostas(
        ).nomes() if hasattr(personagens[nome].
                             capacidades_compostas(), "nomes")
                      else [])
        return _ok({"capabilities": caps},
                   f"{len(caps)} capabilities.",
                   origem="consultar_capabilities")
    return _ok({"capabilities": [],
                "nota": "vincule o Character F12 no ambiente."},
               "sem capabilities vinculadas.",
               origem="consultar_capabilities")


def t_construir_contexto(ambiente, args: dict) -> ToolResult:
    from .contexto_tarefa import (ContextoTarefa,
                                  construir_contexto)

    try:
        tarefa = ContextoTarefa(
            objetivo=str(args.get("objetivo", "")),
            alvo=str(args.get("alvo", "")),
            entidade_selecionada=str(args.get(
                "selecionado", "")),
            arquivo_atual=str(args.get("arquivo", "")),
            operacoes=list(args.get("operacoes") or []))
        resultado = construir_contexto(_modelo_de(ambiente),
                                       tarefa)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="construir_contexto")
    return _ok({"entidades": len(resultado.entidades),
                "relacoes": len(resultado.relacoes),
                "resumo": resultado.to_dict()},
               "contexto pronto.",
               origem="construir_contexto")


def t_explicar_contexto(ambiente, args: dict) -> ToolResult:
    ent_id = str(args.get("id", "")).strip()
    motivos = list(args.get("motivos") or [])
    if not ent_id or not motivos:
        return _falha("id + motivos.", origem="explicar_contexto")
    return _ok({"id": ent_id, "motivos": motivos[:20]},
               f"{ent_id}: {motivos[0]}" if motivos else ent_id,
               origem="explicar_contexto")


def t_listar_contexto(ambiente, args: dict) -> ToolResult:
    entidades = args.get("entidades")
    if not isinstance(entidades, list):
        return _falha("entidades em lista.",
                      origem="listar_contexto")
    return _ok({"ids": [str(e)[:200] for e in
                        entidades[:MAX_RESULTADOS]]},
               f"{len(entidades)} no contexto.",
               origem="listar_contexto")


def t_comparar_contexto(ambiente, args: dict) -> ToolResult:
    antes = set(args.get("antes") or [])
    depois = set(args.get("depois") or [])
    if not isinstance(antes, (set, list)) or not isinstance(
            depois, (set, list)):
        return _falha("listas antes/depois.",
                      origem="comparar_contexto")
    antes, depois = set(map(str, antes)), set(map(str, depois))
    return _ok({"adicionados": sorted(depois - antes),
                "removidos": sorted(antes - depois)},
               "comparado.",
               origem="comparar_contexto")


def t_localizar_codigo(ambiente, args: dict) -> ToolResult:
    from ..codigo.localizacao import localizar_entidade
    from ..modelo.consulta import ConsultaSemantica

    ent_id = str(args.get("id", "")).strip()
    try:
        ent = ConsultaSemantica(
            _modelo_de(ambiente)).indice.buscar_por_id(ent_id)
        texto = _workspace_de(ambiente).resolver(
            ent.arquivo).read_text(encoding="utf-8")
        loc = localizar_entidade(ent, texto)
    except (ErroELiXX, OSError) as exc:
        return _falha(str(exc)[:200],
                      origem="localizar_codigo")
    return _ok(loc.to_dict(), f"{ent_id} em {loc.arquivo}:"
                              f"{loc.inicio_linha}.",
               origem="localizar_codigo")


def t_consultar_regiao(ambiente, args: dict) -> ToolResult:
    arquivo = str(args.get("arquivo", "")).strip()
    try:
        inicio = int(args.get("inicio", 1))
        fim = int(args.get("fim", inicio))
    except (TypeError, ValueError):
        return _falha("linhas inteiras.",
                      origem="consultar_regiao_codigo")
    try:
        linhas = _workspace_de(ambiente).resolver(
            arquivo).read_text(encoding="utf-8").split("\n")
    except (ErroELiXX, OSError) as exc:
        return _falha(str(exc)[:200],
                      origem="consultar_regiao_codigo")
    if not 1 <= inicio <= fim <= len(linhas):
        return _falha("região fora do arquivo.",
                      origem="consultar_regiao_codigo")
    return _ok({"arquivo": arquivo, "inicio": inicio,
                "fim": fim,
                "trecho": "\n".join(linhas[inicio - 1:fim])},
               f"{arquivo}:{inicio}-{fim}.",
               origem="consultar_regiao_codigo")


def t_entidade_codigo(ambiente, args: dict) -> ToolResult:
    return t_localizar_codigo(ambiente, args)


def t_comparar_codigo(ambiente, args: dict) -> ToolResult:
    from ..codigo.sincronizador import diff_textual

    antes = args.get("antes")
    depois = args.get("depois")
    if not isinstance(antes, str) or not isinstance(depois,
                                                    str):
        return _falha("textos antes/depois.",
                      origem="comparar_codigo")
    try:
        diff = diff_textual(antes, depois)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="comparar_codigo")
    return _ok({"trocas": len(diff["trocas"])},
               f"{len(diff['trocas'])} troca(s).",
               origem="comparar_codigo")


def t_propor_operacao(ambiente, args: dict) -> ToolResult:
    from .operacoes import (SemanticOperation,
                            intent_para_operacao,
                            validar_operacao)

    if "operacao" in args and isinstance(args["operacao"],
                                         dict):
        try:
            op = SemanticOperation.from_dict(args["operacao"])
        except ErroELiXX as exc:
            return _falha(str(exc)[:200],
                          origem="propor_operacao")
    elif "pedido" in args:
        from .inteligencia import MockIntentProvider

        try:
            intent = MockIntentProvider().gerar_intencao(
                None, str(args["pedido"]))
            op = intent_para_operacao(intent)
        except ErroELiXX as exc:
            return _falha(str(exc)[:200],
                          origem="propor_operacao")
    else:
        return _falha("operacao ou pedido.",
                      origem="propor_operacao")
    valido = validar_operacao(op)
    if not valido["valido"]:
        return _falha(valido["motivo"],
                      origem="propor_operacao")
    return _ok({"operacao": op.to_dict()},
               f"proposta: {op.tipo} {op.alvo.nome} (sem "
               "executar).",
               origem="propor_operacao")


def t_validar_operacao(ambiente, args: dict) -> ToolResult:
    from .operacoes import SemanticOperation, validar_operacao

    try:
        op = SemanticOperation.from_dict(args.get("operacao",
                                                  {}))
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="validar_operacao")
    valido = validar_operacao(op)
    return _ok(valido, valido["motivo"],
               origem="validar_operacao")


def t_explicar_operacao(ambiente, args: dict) -> ToolResult:
    from .operacoes import SemanticOperation, explicar_operacao

    try:
        op = SemanticOperation.from_dict(args.get("operacao",
                                                  {}))
        texto = explicar_operacao(op)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="explicar_operacao")
    return _ok({"explicacao": texto}, texto,
               origem="explicar_operacao")


def t_listar_operacoes(ambiente, args: dict) -> ToolResult:
    from .operacoes import OPERACOES

    return _ok({"operacoes": list(OPERACOES)},
               f"{len(OPERACOES)} operações.",
               origem="listar_operacoes")


def t_proposta_plano(ambiente, args: dict) -> ToolResult:
    from .operacoes import SemanticOperation
    from .planejamento import PlanoTarefa, construir_plano

    try:
        ops = [SemanticOperation.from_dict(o) for o in
               args.get("operacoes", [])]
        tarefa = PlanoTarefa(str(args.get("objetivo",
                                          "plano")),
                             ops)
        construir_plano(tarefa)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="criar_proposta_plano")
    return _ok({"objetivo": tarefa.objetivo,
                "passos": len(tarefa.operacoes)},
               "proposta de plano (sem executar).",
               origem="criar_proposta_plano")


def t_consultar_plano(ambiente, args: dict) -> ToolResult:
    plano = getattr(ambiente, "plano_view", None)
    if plano is None:
        return _falha("sem plano anexado.",
                      origem="consultar_plano")
    return _ok(plano.resumo(), "plano atual.",
               origem="consultar_plano")


def t_explicar_plano(ambiente, args: dict) -> ToolResult:
    from .planejamento import PlanoTarefa, explicar_plano

    dados = args.get("plano")
    if not isinstance(dados, dict):
        return _falha("plano em dict.",
                      origem="explicar_plano")
    try:
        from .operacoes import SemanticOperation

        tarefa = PlanoTarefa(
            dados.get("objetivo", "plano"),
            [SemanticOperation.from_dict(o) for o in
             dados.get("operacoes", [])])
        from .planejamento import construir_plano

        construir_plano(tarefa)
        texto = explicar_plano(tarefa)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="explicar_plano")
    return _ok({"explicacao": texto}, texto.split("\n")[0],
               origem="explicar_plano")


def t_validar_plano(ambiente, args: dict) -> ToolResult:
    from .operacoes import SemanticOperation
    from .planejamento import (PlanoTarefa, construir_plano,
                               validar_plano)

    try:
        tarefa = PlanoTarefa(
            args.get("objetivo", "plano"),
            [SemanticOperation.from_dict(o) for o in
             args.get("operacoes", [])])
        construir_plano(tarefa)
        modelo = getattr(ambiente, "modelo", None)
        valido = validar_plano(tarefa, modelo)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="validar_plano")
    return _ok(valido, valido["motivo"],
               origem="validar_plano")


def t_simular_plano(ambiente, args: dict) -> ToolResult:
    from .operacoes import SemanticOperation
    from .planejamento import (PlanoTarefa, construir_plano,
                               dry_run)

    try:
        tarefa = PlanoTarefa(
            args.get("objetivo", "plano"),
            [SemanticOperation.from_dict(o) for o in
             args.get("operacoes", [])])
        construir_plano(tarefa)
        secs = dry_run(tarefa)
    except ErroELiXX as exc:
        return _falha(str(exc)[:200],
                      origem="simular_plano")
    return _ok({"passos": len(secs["passos"]),
                "arquivos": secs["arquivos"]},
               "simulado (nada escrito).",
               origem="simular_plano")


def t_consultar_trecho(ambiente, args: dict) -> ToolResult:
    return t_consultar_regiao(ambiente, args)


TOOLS = {
    "buscar_entidade": ("CONSULTA", "READ", t_buscar_entidade,
                        "Localiza entidade por nome exato."),
    "consultar_entidade": ("CONSULTA", "READ", t_consultar_entidade,
                           "Vizinhança completa de uma entidade."),
    "consultar_relacoes": ("CONSULTA", "READ", t_consultar_relacoes,
                           "Relações de/para uma entidade."),
    "consultar_por_tipo": ("CONSULTA", "READ", t_consultar_por_tipo,
                           "Entidades por tipo F27."),
    "consultar_por_arquivo": ("CONSULTA", "READ",
                              t_consultar_por_arquivo,
                              "Entidades por arquivo."),
    "consultar_personagem": ("CONSULTA", "READ",
                             t_consultar_personagem,
                             "Personagem F12 ou F27."),
    "consultar_partes": ("CONSULTA", "READ", t_consultar_partes,
                         "Partes de um personagem."),
    "consultar_poses": ("CONSULTA", "READ", t_consultar_poses,
                        "Poses (F12 vinculado ou F27)."),
    "consultar_gestos": ("CONSULTA", "READ", t_consultar_gestos,
                         "Gestos (rig F23 vinculado)."),
    "consultar_animacoes": ("CONSULTA", "READ",
                            t_consultar_animacoes,
                            "Animações do modelo."),
    "consultar_assets": ("CONSULTA", "READ", t_consultar_assets,
                         "Assets do modelo."),
    "consultar_capabilities": ("CONSULTA", "READ",
                               t_consultar_capabilities,
                               "Capabilities (F12 vinculado)."),
    "construir_contexto": ("ANALISE", "ANALYZE",
                           t_construir_contexto,
                           "Contexto F34 (só leitura)."),
    "explicar_contexto": ("ANALISE", "ANALYZE",
                          t_explicar_contexto,
                          "Motivos de uma entidade."),
    "listar_contexto": ("ANALISE", "ANALYZE", t_listar_contexto,
                        "IDs de um contexto dado."),
    "comparar_contexto": ("ANALISE", "ANALYZE",
                          t_comparar_contexto,
                          "Diff de dois conjuntos."),
    "localizar_codigo": ("LOCALIZACAO", "READ", t_localizar_codigo,
                         "Linha AST de uma entidade."),
    "consultar_regiao_codigo": ("LOCALIZACAO", "READ",
                                t_consultar_regiao,
                                "Trecho por arquivo/linhas."),
    "consultar_entidade_codigo": ("LOCALIZACAO", "READ",
                                  t_entidade_codigo,
                                  "Alias de localizar_codigo."),
    "comparar_codigo": ("LOCALIZACAO", "READ", t_comparar_codigo,
                        "Diff textual de dois textos."),
    "propor_operacao": ("OPERACAO", "PROPOSE", t_propor_operacao,
                        "Proposta validada (sem executar)."),
    "validar_operacao": ("OPERACAO", "READ", t_validar_operacao,
                         "Valida dict de operação."),
    "explicar_operacao": ("OPERACAO", "READ", t_explicar_operacao,
                          "Frase PT determinística."),
    "listar_operacoes": ("OPERACAO", "READ", t_listar_operacoes,
                         "Vocabulário F31."),
    "criar_proposta_plano": ("PLANO", "PROPOSE",
                             t_proposta_plano,
                             "Plano sem executar."),
    "consultar_plano": ("PLANO", "READ", t_consultar_plano,
                        "Resumo do plano anexado."),
    "explicar_plano": ("PLANO", "READ", t_explicar_plano,
                       "Texto PT do plano."),
    "validar_plano": ("PLANO", "READ", t_validar_plano,
                      "Validação sem executar."),
    "simular_plano": ("PLANO", "READ", t_simular_plano,
                      "Dry-run (nada escreve)."),
    "consultar_trecho": ("CODIGO", "READ", t_consultar_trecho,
                         "Alias de região de código."),
}
"""id → (categoria, permissão, impl, descrição). Escrever? Não há."""


class SemanticToolRegistry:
    """Registro explícito (sem plugins, sem import dinâmico)."""

    def __init__(self) -> None:
        self._tools: dict[str, SemanticTool] = {}
        for tool_id, (categoria, permissao, _impl,
                      descricao) in TOOLS.items():
            nome = tool_id
            self._tools[tool_id] = SemanticTool(
                tool_id, nome, descricao, categoria, permissao,
                origem="F36")

    def registrar(self, tool: SemanticTool) -> SemanticTool:
        if not isinstance(tool, SemanticTool):
            raise ErroELiXX("Registry espera SemanticTool.")
        if tool.id in self._tools:
            raise ErroELiXX(f'Tool "{tool.id}" duplicada.')
        self._tools[tool.id] = tool
        return tool

    def buscar(self, tool_id: str) -> SemanticTool:
        try:
            return self._tools[str(tool_id)]
        except KeyError:
            raise ErroELiXX(f'Tool "{tool_id}" desconhecida.')

    def listar(self, categoria: str | None = None) -> list[str]:
        if categoria is not None and categoria not in \
                CATEGORIAS_TOOL:
            raise ErroELiXX(f'Categoria "{categoria}" inválida.')
        return sorted(tid for tid, tool in self._tools.items()
                      if categoria is None
                      or tool.categoria == categoria)

    def validar(self, tool_id: str, argumentos: dict) -> dict:
        tool = self.buscar(tool_id)
        if not isinstance(argumentos, dict):
            return {"valido": False, "codigo": "args_invalidos",
                    "motivo": "Argumentos em dict."}
        if len(argumentos) > MAX_ARGS:
            return {"valido": False, "codigo": "args_demais",
                    "motivo": f"Máximo {MAX_ARGS}."}
        if not B.e_dado(argumentos):
            return {"valido": False, "codigo": "args_invalidos",
                    "motivo": "NaN/recursão/objetos."}
        if len(json.dumps(argumentos, sort_keys=True)) > \
                MAX_PAYLOAD:
            return {"valido": False, "codigo": "payload",
                    "motivo": "Payload além do teto."}
        return {"valido": True, "codigo": "ok",
                "motivo": f"Tool {tool.id} ({tool.categoria})."}

    def resolver(self, nome: str) -> SemanticTool:
        """Nome ou id (sem carregar nada dinamicamente)."""
        try:
            return self.buscar(nome)
        except ErroELiXX:
            for tool in self._tools.values():
                if tool.nome == str(nome):
                    return tool
            raise ErroELiXX(f'Tool "{nome}" desconhecida.')

    def __repr__(self) -> str:
        return f"SemanticToolRegistry({len(self._tools)} tools)"


def executar_chamada(registry: SemanticToolRegistry,
                     chamada: AgentToolCall,
                     ambiente=None,
                     permissoes=None) -> ToolResult:
    """Valida permissão+args, executa impl, registra resultado."""
    if not isinstance(registry, SemanticToolRegistry):
        raise ErroELiXX("Espera SemanticToolRegistry.")
    if not isinstance(chamada, AgentToolCall):
        raise ErroELiXX("Espera AgentToolCall.")
    tool = registry.buscar(chamada.tool_id)
    permissoes = permissoes or SemanticPermissions()
    if not isinstance(permissoes, SemanticPermissions):
        raise ErroELiXX("Espera SemanticPermissions.")
    chamada.transitar("VALIDANDO")
    valido = registry.validar(chamada.tool_id,
                              chamada.argumentos)
    if not valido["valido"]:
        chamada.transitar("FALHOU")
        chamada.resultado = ToolResult(
            False, {}, valido["motivo"], origem=tool.id,
            erros=[valido["codigo"]])
        return chamada.resultado
    try:
        permissoes.exigir(tool.permissao, tool.id)
    except ErroELiXX as exc:
        chamada.transitar("BLOQUEADA")
        chamada.resultado = ToolResult(
            False, {}, str(exc)[:200], origem=tool.id,
            erros=["permissao_negada"])
        return chamada.resultado
    chamada.transitar("EXECUTANDO")
    try:
        impl = TOOLS[tool.id][2]
        resultado = impl(ambiente, dict(chamada.argumentos))
    except ErroELiXX as exc:
        chamada.transitar("FALHOU")
        chamada.resultado = ToolResult(
            False, {}, str(exc)[:200], origem=tool.id,
            erros=["execucao"])
        return chamada.resultado
    if not isinstance(resultado, ToolResult):
        chamada.transitar("FALHOU")
        chamada.resultado = ToolResult(
            False, {}, "Impl sem ToolResult.", origem=tool.id,
            erros=["contrato"])
        return chamada.resultado
    chamada.transitar("CONCLUIDA")
    chamada.resultado = resultado
    return resultado


def executar_sequencia(registry: SemanticToolRegistry,
                       chamadas: list, ambiente=None,
                       permissoes=None,
                       profundidade: int = 3) -> ToolTrace:
    """Sequência curta e ordenada (sem recursão entre tools)."""
    try:
        prof = int(profundidade)
    except (TypeError, ValueError):
        raise ErroELiXX("Profundidade inteira.")
    if not 1 <= prof <= MAX_PROFUNDIDADE_TOOLS:
        raise ErroELiXX(f"Profundidade 1..{MAX_PROFUNDIDADE_TOOLS}.")
    if len(chamadas) > MAX_CALLS:
        raise ErroELiXX(f"Sequência além de {MAX_CALLS}.")
    trace = ToolTrace()
    for chamada in list(chamadas)[:prof]:
        if not isinstance(chamada, AgentToolCall):
            raise ErroELiXX("Sequência de AgentToolCall.")
        trace.registrar(chamada)
        resultado = executar_chamada(registry, chamada,
                                     ambiente, permissoes)
        if not resultado.sucesso:
            break  # para na primeira falha (sem cascata cega)
    return trace
