"""Permissões do Agent (F26) — negação por padrão, falha fechada.

Categorias ativas: READ, WRITE, RENAME, DELETE, VALIDATE, COMPILE,
PREVIEW. NETWORK/PROCESS/SHELL existem como nomes reservados, sempre
negados nesta fase (futuro explícito). Sem permissão = erro claro.
"""
from __future__ import annotations

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["PERMISSOES", "RESERVADAS", "PermissionSet"]

PERMISSOES = ("READ", "WRITE", "RENAME", "DELETE", "VALIDATE",
              "COMPILE", "PREVIEW")
"""Categorias concedíveis nesta fase."""

RESERVADAS = ("NETWORK", "PROCESS", "SHELL")
"""Categorias futuras: pedir = erro explícito (nunca silencioso)."""


class PermissionSet:
    """Conjunto de permissões (padrão: nada concedido)."""

    def __init__(self, concedidas: list | None = None) -> None:
        self.concedidas: set[str] = set()
        for p in (concedidas or []):
            self.conceder(p)

    def conceder(self, permissao: str) -> PermissionSet:
        nome = str(permissao).strip().upper()
        if nome in RESERVADAS:
            raise ErroELiXX(f'Agent: "{nome}" reservada (NETWORK, '
                            "PROCESS e SHELL desabilitados).")
        if nome not in PERMISSOES:
            raise ErroELiXX(f'Agent: permissão "{permissao}" '
                            "inválida.")
        self.concedidas.add(nome)
        return self

    def revogar(self, permissao: str) -> PermissionSet:
        self.concedidas.discard(str(permissao).strip().upper())
        return self

    def tem(self, permissao: str) -> bool:
        return str(permissao).strip().upper() in self.concedidas

    def exigir(self, permissao: str, o_que: str = "operação"
              ) -> None:
        """Falha fechada e explícita quando ausente."""
        if not self.tem(permissao):
            raise ErroELiXX(f'Agent: "{o_que}" exige permissão '
                            f'"{str(permissao).strip().upper()}" '
                            "(negada por padrão).")

    def listar(self) -> list[str]:
        return B.ordenado(self.concedidas)

    def to_dict(self) -> dict:
        return {"concedidas": self.listar()}

    def __repr__(self) -> str:
        return f"PermissionSet({self.listar()})"
