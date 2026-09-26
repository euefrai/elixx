"""Workspace do Studio (F25) — raiz do projeto + contenção de paths.

Toda operação de arquivo passa por `_resolver`: caminhos absolutos ou
com ".." que escapem da raiz são recusados (anti traversal). Abrir
projeto/arquivo NUNCA executa conteúdo.
"""
from __future__ import annotations

from pathlib import Path

from ..erros import ErroELiXX
from .projeto import ARQUIVO_PROJETO, ProjetoELiXX

__all__ = ["Workspace"]


class Workspace:
    """Projeto atual + raiz contida (criar/abrir/fechar/salvar)."""

    def __init__(self) -> None:
        self.raiz: Path | None = None
        self.projeto: ProjetoELiXX | None = None

    # ----- ciclo de vida -----

    @property
    def aberto(self) -> bool:
        return self.raiz is not None and self.projeto is not None

    def criar_projeto(self, raiz, nome: str,
                      entrada: str = "src/main.elixx") -> ProjetoELiXX:
        base = Path(raiz)
        base.mkdir(parents=True, exist_ok=True)
        self.raiz = base.resolve()
        self.projeto = ProjetoELiXX(nome, entrada=entrada)
        (self.raiz / ARQUIVO_PROJETO).write_text(
            self.projeto.to_json(), encoding="utf-8")
        entrada_p = self._resolver(self.projeto.entrada)
        entrada_p.parent.mkdir(parents=True, exist_ok=True)
        if not entrada_p.exists():
            entrada_p.write_text("", encoding="utf-8")
        return self.projeto

    def abrir_projeto(self, raiz) -> ProjetoELiXX:
        base = Path(raiz).resolve()
        if not base.is_dir():
            raise ErroELiXX(f'Projeto: pasta "{base}" não existe.')
        arquivo = base / ARQUIVO_PROJETO
        if not arquivo.is_file():
            raise ErroELiXX(f'Projeto: "{ARQUIVO_PROJETO}" ausente em '
                            f'"{base}".')
        self.raiz = base
        self.projeto = ProjetoELiXX.from_json(
            arquivo.read_text(encoding="utf-8"))
        return self.projeto

    def fechar_projeto(self) -> None:
        self.raiz = None
        self.projeto = None

    def salvar_projeto(self) -> Path:
        self._exigir_aberto()
        destino = self.raiz / ARQUIVO_PROJETO
        destino.write_text(self.projeto.to_json(), encoding="utf-8")
        return destino

    def recarregar_projeto(self) -> ProjetoELiXX:
        self._exigir_aberto()
        self.projeto = ProjetoELiXX.from_json(
            (self.raiz / ARQUIVO_PROJETO).read_text(
                encoding="utf-8"))
        return self.projeto

    # ----- contenção -----

    def _exigir_aberto(self) -> None:
        if not self.aberto:
            raise ErroELiXX("Workspace: nenhum projeto aberto.")

    def _resolver(self, relativo: str) -> Path:
        """Caminho relativo contido na raiz (anti traversal)."""
        self._exigir_aberto()
        if not isinstance(relativo, str) or not relativo.strip():
            raise ErroELiXX("Workspace: caminho vazio.")
        texto = relativo.strip().replace("\\", "/")
        candidato = (self.raiz / texto).resolve()
        try:
            candidato.relative_to(self.raiz)
        except ValueError:
            raise ErroELiXX(f'Workspace: "{relativo}" escapa da raiz '
                            "do projeto (recusado).")
        return candidato

    def resolver(self, relativo: str) -> Path:
        """Versão pública da contenção (painéis usam esta)."""
        return self._resolver(relativo)

    def existe(self, relativo: str) -> bool:
        return self._resolver(relativo).exists()

    def __repr__(self) -> str:
        return f"Workspace({self.raiz})"
