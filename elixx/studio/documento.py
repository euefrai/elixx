"""Documentos do Studio (F25) — texto + dirty + cursor + undo/redo.

DocumentoELiXX é o modelo (sem Tk); o widget Tk apenas espelha. Vários
documentos via GerenciadorDocumentos.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["DocumentoELiXX", "GerenciadorDocumentos"]

MAX_HISTORICO = 100
"""Teto do undo/redo por documento."""


class DocumentoELiXX:
    """Texto editável com estado (versão, dirty, cursor, seleção)."""

    def __init__(self, caminho: str, texto: str = "") -> None:
        if not isinstance(caminho, str) or not caminho.strip():
            raise ErroELiXX("Documento precisa de caminho.")
        if not isinstance(texto, str):
            raise ErroELiXX("Documento precisa de texto.")
        self.caminho = caminho.strip()
        self.texto = texto
        self._salvo = texto
        self.versao = 1
        self.cursor = (1, 1)  # (linha, coluna) 1-based
        self.selecao: tuple | None = None
        self._desfazer: list[str] = []
        self._refazer: list[str] = []

    @property
    def dirty(self) -> bool:
        """True quando o texto difere do último save/load."""
        return self.texto != self._salvo

    # ----- edição -----

    def _registrar(self) -> None:
        self._desfazer.append(self.texto)
        if len(self._desfazer) > MAX_HISTORICO:
            self._desfazer.pop(0)
        self._refazer.clear()

    def definir_texto(self, texto: str) -> None:
        if not isinstance(texto, str):
            raise ErroELiXX("Texto precisa de string.")
        if texto == self.texto:
            return
        self._registrar()
        self.texto = texto
        self.versao += 1

    def inserir(self, trecho: str, linha: int = 1,
                coluna: int = 1) -> None:
        linhas = self.texto.split("\n")
        if not 1 <= linha <= len(linhas) + 1:
            raise ErroELiXX(f"Documento: linha {linha} fora do texto.")
        if linha == len(linhas) + 1:
            linhas.append("")
        atual = linhas[linha - 1]
        if not 1 <= coluna <= len(atual) + 1:
            raise ErroELiXX(f"Documento: coluna {coluna} inválida.")
        self._registrar()
        linhas[linha - 1] = (atual[:coluna - 1] + str(trecho)
                             + atual[coluna - 1:])
        self.texto = "\n".join(linhas)
        self.versao += 1

    def desfazer(self) -> bool:
        """Desfaz (False quando não há o que desfazer)."""
        if not self._desfazer:
            return False
        self._refazer.append(self.texto)
        self.texto = self._desfazer.pop()
        self.versao += 1
        return True

    def refazer(self) -> bool:
        if not self._refazer:
            return False
        self._desfazer.append(self.texto)
        self.texto = self._refazer.pop()
        self.versao += 1
        return True

    def mover_cursor(self, linha: int, coluna: int = 1) -> None:
        linhas = self.texto.split("\n")
        if not 1 <= linha <= len(linhas):
            raise ErroELiXX("Cursor: linha fora do texto.")
        if coluna < 1:
            raise ErroELiXX("Cursor: coluna ≥ 1.")
        self.cursor = (linha, coluna)
        self.selecao = None

    def selecionar(self, inicio: tuple, fim: tuple) -> None:
        self.selecao = (tuple(inicio), tuple(fim))

    # ----- persistência (via workspace; aqui só marca) -----

    def marcar_salvo(self, texto: str | None = None) -> None:
        self._salvo = self.texto if texto is None else str(texto)
        self._desfazer.clear()
        self._refazer.clear()

    def recarregar(self, texto: str) -> None:
        if not isinstance(texto, str):
            raise ErroELiXX("Recarregar precisa de texto.")
        self.texto = texto
        self.marcar_salvo(texto)
        self.versao += 1

    def linhas(self) -> int:
        return len(self.texto.split("\n"))

    def __repr__(self) -> str:
        estado = "dirty" if self.dirty else "limpo"
        return f"DocumentoELiXX({self.caminho} v{self.versao} {estado})"


class GerenciadorDocumentos:
    """Múltiplos documentos abertos (um ativo)."""

    def __init__(self) -> None:
        self._docs: dict[str, DocumentoELiXX] = {}
        self._ordem: list[str] = []
        self.ativo: str | None = None

    def abrir(self, caminho: str, texto: str = "") -> DocumentoELiXX:
        if caminho in self._docs:
            self.ativo = caminho
            return self._docs[caminho]
        doc = DocumentoELiXX(caminho, texto)
        self._docs[caminho] = doc
        self._ordem.append(caminho)
        self.ativo = caminho
        return doc

    def obter(self, caminho: str) -> DocumentoELiXX:
        try:
            return self._docs[caminho]
        except KeyError:
            raise ErroELiXX(f'Documento "{caminho}" não está aberto.')

    def fechar(self, caminho: str) -> DocumentoELiXX:
        doc = self.obter(caminho)
        del self._docs[caminho]
        self._ordem.remove(caminho)
        if self.ativo == caminho:
            self.ativo = self._ordem[-1] if self._ordem else None
        return doc

    def abertos(self) -> list[str]:
        return list(self._ordem)

    def sujos(self) -> list[str]:
        return [c for c in self._ordem if self._docs[c].dirty]

    def __repr__(self) -> str:
        return (f"GerenciadorDocumentos({len(self._docs)} abertos, "
                f"ativo={self.ativo})")
