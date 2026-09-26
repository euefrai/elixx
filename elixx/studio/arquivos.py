"""Árvore de arquivos do Studio (F25) — operações contidas no workspace.

Listar/abrir/criar/renomear/excluir com confirmação explícita para
exclusão. Tudo passa pela contenção do Workspace (anti traversal).
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["ArvoreArquivos"]


class ArvoreArquivos:
    """Painel PROJETO (modelo; widget Tk espelha `listar`)."""

    def __init__(self, workspace) -> None:
        from .workspace import Workspace

        if not isinstance(workspace, Workspace):
            raise ErroELiXX("ArvoreArquivos espera Workspace.")
        self.workspace = workspace

    def _exigir_aberto(self) -> None:
        if not self.workspace.aberto:
            raise ErroELiXX("Arquivos: nenhum projeto aberto.")

    def listar(self, relativo: str = ".") -> list[dict]:
        """Entradas ordenadas: pastas primeiro, depois arquivos."""
        self._exigir_aberto()
        base = self.workspace.resolver(relativo)
        if not base.is_dir():
            raise ErroELiXX(f'"{relativo}" não é pasta.')
        pastas, arquivos = [], []
        for item in sorted(base.iterdir(), key=lambda p: p.name):
            if item.name == "__pycache__":
                continue
            registro = {"nome": item.name, "tipo": (
                "pasta" if item.is_dir() else "arquivo")}
            (pastas if item.is_dir() else arquivos).append(registro)
        return pastas + arquivos

    def criar_arquivo(self, relativo: str,
                      conteudo: str = "") -> str:
        self._exigir_aberto()
        destino = self.workspace.resolver(relativo)
        if destino.exists():
            raise ErroELiXX(f'"{relativo}" já existe.')
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(str(conteudo), encoding="utf-8")
        return relativo

    def criar_pasta(self, relativo: str) -> str:
        self._exigir_aberto()
        destino = self.workspace.resolver(relativo)
        if destino.exists():
            raise ErroELiXX(f'"{relativo}" já existe.')
        destino.mkdir(parents=True)
        return relativo

    def renomear(self, origem: str, destino: str) -> str:
        self._exigir_aberto()
        src = self.workspace.resolver(origem)
        dst = self.workspace.resolver(destino)
        if not src.exists():
            raise ErroELiXX(f'"{origem}" não existe.')
        if dst.exists():
            raise ErroELiXX(f'"{destino}" já existe.')
        src.rename(dst)
        return destino

    def excluir(self, relativo: str, confirmar: bool = False) -> str:
        """Exclusão exige `confirmar=True` (proteção explícita)."""
        self._exigir_aberto()
        if confirmar is not True:
            raise ErroELiXX(f'Exclusão de "{relativo}" exige '
                            "confirmação explícita.")
        alvo = self.workspace.resolver(relativo)
        if not alvo.exists():
            raise ErroELiXX(f'"{relativo}" não existe.')
        if alvo.is_dir():
            import shutil

            shutil.rmtree(alvo)
        else:
            alvo.unlink()
        return relativo

    def atualizar(self, relativo: str = ".") -> list[dict]:
        """Releitura da árvore (lazy: só o nível pedido)."""
        return self.listar(relativo)

    def __repr__(self) -> str:
        return "ArvoreArquivos()"
