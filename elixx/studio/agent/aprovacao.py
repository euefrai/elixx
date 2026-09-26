"""Aprovação do Agent (F26) — manual, automático seguro, bloqueado.

Manual: propõe → usuário aprova → aplica. Automático seguro: só
operações de risco baixo em caminhos permitidos aplicam sozinhas;
o resto continua exigindo aprovação. Bloqueado: nada aplica.
"""
from __future__ import annotations

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["MODOS_APROVACAO", "Approval", "pode_auto_aprovar"]

MODOS_APROVACAO = ("manual", "automatico_seguro", "bloqueado")
"""Modos (padrão: manual)."""


def pode_auto_aprovar(mudanca, caminhos_permitidos: list | None = None
                      ) -> bool:
    """Segura = risco baixo + criar/editar + caminho permitido (se há)."""
    if mudanca.risco != "baixo":
        return False
    if mudanca.operacao not in ("criar", "editar"):
        return False
    if caminhos_permitidos:
        return any(mudanca.caminho == p or mudanca.caminho.startswith(
            p.rstrip("/") + "/") for p in caminhos_permitidos)
    return True


class Approval:
    """Política + decisões registradas (determinísticas)."""

    def __init__(self, modo: str = "manual",
                 caminhos_permitidos: list | None = None) -> None:
        modo_txt = str(modo).strip()
        if modo_txt not in MODOS_APROVACAO:
            raise ErroELiXX(f'Agent: modo "{modo}" inválido.')
        self.modo = modo_txt
        self.caminhos_permitidos = [str(p) for p in
                                    (caminhos_permitidos or [])]
        self.decisoes: list[dict] = []

    def decidir(self, changeset, aprovador: str = "usuario"
               ) -> dict:
        """Decide por mudança (sem aplicar): aprovadas/recusadas."""
        aprovadas, recusadas = [], []
        for mudanca in changeset.mudancas:
            if self.modo == "bloqueado":
                recusadas.append(mudanca.caminho)
            elif self.modo == "automatico_seguro" and \
                    pode_auto_aprovar(mudanca,
                                      self.caminhos_permitidos):
                aprovadas.append(mudanca.caminho)
            elif self.modo == "manual":
                pass  # decisão humana fora daqui (registrada depois)
            else:
                recusadas.append(mudanca.caminho)
        decisao = {"modo": self.modo, "aprovador": aprovador,
                   "aprovadas": B.ordenado(aprovadas),
                   "recusadas": B.ordenado(recusadas),
                   "pendentes": B.ordenado(
                       [m.caminho for m in changeset.mudancas
                        if m.caminho not in aprovadas
                        and m.caminho not in recusadas])}
        self.decisoes.append(decisao)
        return decisao

    def aprovar_tudo(self, changeset) -> None:
        """Aprovação humana explícita (modo manual)."""
        if self.modo == "bloqueado":
            raise ErroELiXX("Agent: modo bloqueado não aprova.")
        changeset.aprovar()

    def __repr__(self) -> str:
        return f"Approval({self.modo})"
