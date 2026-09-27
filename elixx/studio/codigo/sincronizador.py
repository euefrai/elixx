"""Sincronizador bidirecional (F32 CP3-6) — código ↔ modelo.

codigo_para_modelo: arquivo → parser → F27 (atualizar_arquivo).
operacao_para_codigo: SemanticOperation → AlteracaoCodigo →
    ChangeSet F26 (aprovação externa) → aplicar → reparsear →
    modelo → diff.
SincronizadorBidirecional: guarda hash por arquivo (anti-loop: mesma
versão não ressincroniza) e orquestra os dois sentidos.
Integração Studio/Agent sem tocar F25/F26/F27/F28: funções que operam
sobre StudioWorkspace e AgentChat/loop existentes.
"""
from __future__ import annotations

import difflib
import hashlib

from ...erros import ErroELiXX
from .gerador import gerar_alteracao, validar_candidato
from .localizacao import localizar_entidade
from .mudanca import AlteracaoCodigo

__all__ = [
    "SincronizadorCodigo", "SincronizadorBidirecional",
    "diff_textual", "aplicar_com_changeset",
    "sincronizar_workspace",
]


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def diff_textual(antes: str, depois: str) -> dict:
    """Diff determinístico headless (linhas + entidades afetadas vêm
    da reanálise; aqui só texto)."""
    if not isinstance(antes, str) or not isinstance(depois, str):
        raise ErroELiXX("Código: diff precisa de textos.")
    a, b = antes.split("\n"), depois.split("\n")
    linhas = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            linhas.append({"op": tag, "antes": [i1 + 1, i2],
                            "depois": [j1 + 1, j2],
                            "removidas": a[i1:i2],
                            "adicionadas": b[j1:j2]})
    return {"trocas": linhas,
            "linhas_antes": len(a), "linhas_depois": len(b)}


class SincronizadorCodigo:
    """Um workspace + um modelo, sincronizados explicitamente."""

    def __init__(self, workspace, modelo) -> None:
        from ..modelo.modelo import ModeloSemantico
        from ..workspace import Workspace

        if not isinstance(workspace, Workspace):
            raise ErroELiXX("Código: espera Workspace.")
        if not isinstance(modelo, ModeloSemantico):
            raise ErroELiXX("Código: espera ModeloSemantico.")
        self.workspace = workspace
        self.modelo = modelo
        self._hashes: dict[str, str] = {}

    # ----- código → modelo -----

    def codigo_para_modelo(self, relativo: str) -> dict:
        """Reparseia e atualiza (externo ou pós-aplicação)."""
        from ..modelo.adaptador import atualizar_arquivo

        caminho = str(relativo).replace("\\", "/")
        texto = self.workspace.resolver(caminho).read_text(
            encoding="utf-8")
        out = atualizar_arquivo(self.modelo, caminho, texto)
        self._hashes[caminho] = _hash(texto)
        return {"arquivo": caminho, **out,
                "hash": self._hashes[caminho]}

    # ----- operação → código (gera; NÃO aplica sozinho) -----

    def operacao_para_codigo(self, operacao, entidade=None
                             ) -> AlteracaoCodigo:
        """SemanticOperation → AlteracaoCodigo validada no candidato."""
        from .gerador import suportado_pelo_gerador

        if not suportado_pelo_gerador(operacao):
            tipo = operacao.tipo if hasattr(operacao, "tipo") \
                else operacao.get("tipo", "")
            raise ErroELiXX(f"GERADOR_NAO_SUPORTADO: {tipo}.")
        texto_atual, ent = self._texto_e_entidade(operacao)
        if entidade is not None:
            ent = entidade
        alt = gerar_alteracao(operacao, ent, texto_atual)
        veredito = validar_candidato(alt, texto_atual, ent)
        if not veredito["ok"]:
            raise ErroELiXX(f"{veredito['codigo']}: "
                            f"{veredito['motivo']}")
        return alt

    def _texto_e_entidade(self, operacao):
        alt = operacao.alteracao if hasattr(operacao, "alteracao") \
            else operacao.get("alteracao", {})
        arquivo = str(alt.get("arquivo", ""))
        if not arquivo:
            raise ErroELiXX("CODIGO_ALVO_NAO_ENCONTRADO: operação "
                            "sem arquivo.")
        try:
            texto = self.workspace.resolver(arquivo).read_text(
                encoding="utf-8")
        except OSError as exc:
            raise ErroELiXX(f"CODIGO_ALVO_NAO_ENCONTRADO: {arquivo} "
                            f"ilegível ({exc}).")
        alvo = operacao.alvo if hasattr(operacao, "alvo") \
            else operacao.get("alvo", {})
        nome = alvo.nome if hasattr(alvo, "nome") \
            else alvo.get("nome", "")
        tipo = alvo.tipo if hasattr(alvo, "tipo") \
            else alvo.get("tipo")
        ent = next((e for e in self.modelo.entidades()
                    if e.nome == nome and (tipo is None
                                           or e.tipo == tipo)),
                   None)
        tipo_op = operacao.tipo if hasattr(operacao, "tipo") \
            else operacao.get("tipo", "")
        if ent is None and tipo_op != "adicionar":
            raise ErroELiXX(f"CODIGO_ALVO_NAO_ENCONTRADO: {nome}.")
        return texto, ent


def aplicar_com_changeset(sincronizador: SincronizadorCodigo,
                          alteracao: AlteracaoCodigo,
                          approval=None) -> dict:
    """Alteração → ChangeSet F26 → aprovação → aplicar → validar.

    Aprovação externa (manual prévia ou auto_seguro total); sem ela,
    CODIGO_APROVACAO_NECESSARIA. Pós-aplicação: reparse + modelo +
    diff; falha crítica = rollback F26 (CODIGO_ROLLBACK).
    """
    from ..agent.mudancas import ChangeSet
    from ..modelo.validacao import (SnapshotSemantico,
                                    comparar_snapshots)

    if not isinstance(alteracao, AlteracaoCodigo):
        raise ErroELiXX("Código: espera AlteracaoCodigo.")
    ws, modelo = sincronizador.workspace, sincronizador.modelo
    antes_texto = ws.resolver(alteracao.arquivo).read_text(
        encoding="utf-8")
    try:
        novo_texto = alteracao.aplicar_texto(antes_texto)
    except ErroELiXX as exc:
        return {"ok": False, "codigo": "CODIGO_REGIAO_ALTERADA",
                "motivo": str(exc)[:200]}
    from ..editor import diagnosticar_texto

    erros = [d for d in diagnosticar_texto(novo_texto,
                                           alteracao.arquivo)
             if d.severidade == "error"]
    if erros:
        return {"ok": False, "codigo": "CODIGO_RESULTADO_INVALIDO",
                "motivo": erros[0].mensagem[:200]}
    from ..agent.mudancas import AgentChange

    snap_antes = SnapshotSemantico.de_modelo(modelo)
    cs = ChangeSet([AgentChange(
        alteracao.arquivo,
        "editar" if ws.existe(alteracao.arquivo) else "criar",
        conteudo_novo=novo_texto,
        descricao=alteracao.motivo or "alteração F32")])
    if approval is None:
        return {"ok": False,
                "codigo": "CODIGO_APROVACAO_NECESSARIA",
                "motivo": "ChangeSet proposto, sem aprovação.",
                "changeset": cs.revisar()}
    from ..agent.aprovacao import Approval

    if not isinstance(approval, Approval):
        raise ErroELiXX("Código: approval F26 inválido.")
    if approval.modo == "manual":
        if cs.estado != "aprovado":
            return {"ok": False,
                    "codigo": "CODIGO_APROVACAO_NECESSARIA",
                    "motivo": "Modo manual exige aprovar_tudo.",
                    "changeset": cs.revisar()}
    elif approval.modo == "automatico_seguro":
        decisao = approval.decidir(cs)
        if decisao["pendentes"] or decisao["recusadas"]:
            return {"ok": False,
                    "codigo": "CODIGO_APROVACAO_NECESSARIA",
                    "motivo": "Auto-seguro recusou.",
                    "decisao": decisao}
        cs.aprovar()
    else:
        return {"ok": False, "codigo": "CODIGO_APROVACAO_NECESSARIA",
                "motivo": "Modo bloqueado."}
    try:
        aplicadas = cs.aplicar(ws)
    except ErroELiXX as exc:
        return {"ok": False, "codigo": "CODIGO_SINCRONIZACAO_FALHOU",
                "motivo": str(exc)[:200]}
    try:
        sincronizador.codigo_para_modelo(alteracao.arquivo)
    except ErroELiXX as exc:
        try:
            cs.desfazer(ws)
        except ErroELiXX:
            pass
        return {"ok": False, "codigo": "CODIGO_ROLLBACK",
                "motivo": f"Reanálise falhou e reverteu: "
                          f"{exc}"[:200]}
    snap_depois = SnapshotSemantico.de_modelo(modelo)
    return {"ok": True, "codigo": "ok",
            "motivo": "Aplicado e ressincronizado.",
            "arquivos": aplicadas.get("arquivos", []),
            "diff_textual": diff_textual(antes_texto, novo_texto),
            "diff": comparar_snapshots(snap_antes, snap_depois),
            "changeset": cs}


class SincronizadorBidirecional:
    """Dois sentidos com guarda anti-loop (hash por arquivo)."""

    def __init__(self, workspace, modelo) -> None:
        self.nucleo = SincronizadorCodigo(workspace, modelo)
        self.versao = 0

    @property
    def workspace(self):
        return self.nucleo.workspace

    @property
    def modelo(self):
        return self.nucleo.modelo

    def codigo_para_modelo(self, relativo: str) -> dict:
        caminho = str(relativo).replace("\\", "/")
        texto = self.workspace.resolver(caminho).read_text(
            encoding="utf-8")
        atual = _hash(texto)
        if self.nucleo._hashes.get(caminho) == atual:
            return {"arquivo": caminho, "sincronizado": False,
                    "hash": atual,
                    "motivo": "Sem mudanças (anti-loop)."}
        out = self.nucleo.codigo_para_modelo(caminho)
        out["sincronizado"] = True
        self.versao += 1
        out["versao"] = self.versao
        return out

    def operacao_para_codigo(self, operacao, entidade=None):
        return self.nucleo.operacao_para_codigo(operacao,
                                                entidade)

    def sincronizar(self, relativo: str) -> dict:
        """Externa ou pós-mudança: reparse + índice válido."""
        out = self.codigo_para_modelo(relativo)
        if out.get("sincronizado"):
            from ..modelo.validacao import validar_modelo

            out["valido"] = validar_modelo(self.modelo)["valido"]
        return out

    def comparar(self, antes, depois) -> dict:
        from ..modelo.validacao import comparar_snapshots

        return comparar_snapshots(antes, depois)

    def diagnosticar(self) -> dict:
        from ..modelo.validacao import validar_modelo

        return validar_modelo(self.modelo)


# ----- integração Studio/Agent (sem tocar F25/F26/F27/F28) -----

def sincronizar_workspace(ws) -> dict:
    """StudioWorkspace: reparseia editores sujos? Não — reanalisa o
    modelo a partir do disco, atualiza preview e diagnósticos."""
    from ..modelo.adaptador import analisar_projeto
    from ..modelo.modelo import ModeloSemantico
    from ..modelo.validacao import validar_modelo

    ws.app.workspace._exigir_aberto()
    modelo = ModeloSemantico(ws.app.workspace.projeto.nome)
    total = analisar_projeto(modelo, ws.app.workspace.raiz)
    ws.modelo = modelo
    ws.arvore.atualizar(modelo)
    out = {"modelo": len(modelo), "valido": validar_modelo(
        modelo)["valido"], **{k: total[k] for k in
                              ("arquivos", "entidades",
                               "relacoes", "erros")}}
    try:
        principal = ws.app.workspace.projeto.entrada
        texto = ws.app.workspace.resolver(principal).read_text(
            encoding="utf-8")
        ws.preview.executar(texto, principal)
        out["preview"] = True
    except (OSError, ErroELiXX) as exc:
        out["preview"] = False
        out["preview_motivo"] = str(exc)[:200]
    return out
