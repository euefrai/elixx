"""Erros da ELiXX.

Princípio da linguagem: todo erro é escrito em português e, sempre que
possível, indica linha, coluna, trecho do código, explicação do problema
e sugestão de correção com exemplo.
"""
from __future__ import annotations

import difflib


class ErroELiXX(Exception):
    """Erro base de todos os erros da linguagem."""

    def __init__(
        self,
        mensagem: str,
        *,
        linha: int | None = None,
        coluna: int | None = None,
        trecho: str | None = None,
        sugestao: str | None = None,
        exemplo: str | None = None,
    ) -> None:
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna
        self.trecho = trecho
        self.sugestao = sugestao
        self.exemplo = exemplo
        super().__init__(str(self))

    def __str__(self) -> str:
        partes = []
        if self.linha is not None:
            local = f"Erro ELiXX na linha {self.linha}"
            if self.coluna is not None:
                local += f", coluna {self.coluna}"
            partes.append(local + ":")
        else:
            partes.append("Erro ELiXX:")
        partes.append(self.mensagem)
        if self.trecho:
            partes.append(f"Trecho: {self.trecho}")
        if self.sugestao:
            partes.append(f"Sugestão: {self.sugestao}")
        if self.exemplo:
            partes.append(f"Exemplo correto:\n{self.exemplo}")
        return "\n".join(partes)


class ErroLexico(ErroELiXX):
    """Erro na tokenização (caractere ou sequência inválida)."""


class ErroSintatico(ErroELiXX):
    """Erro na estrutura do programa (gramática)."""


class ErroSemantico(ErroELiXX):
    """Programa bem formado, mas com significado inválido."""


class ErroExecucao(ErroELiXX):
    """Erro durante a execução do programa."""


def sugerir(nome: str, candidatos: list[str], limite: int = 3) -> list[str]:
    """Sugere nomes parecidos (para 'você quis dizer...?').

    Problema que resolve: erros de digitação em português (ex. 'tamnaho'
    em vez de 'tamanho') geram mensagens úteis em vez de 'nome inválido'.
    """
    return difflib.get_close_matches(nome, list(candidatos), n=limite, cutoff=0.6)
