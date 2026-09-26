"""Memória da ELiXX — variáveis com escopos (para funções)."""
from __future__ import annotations

from ..erros import ErroExecucao


class Memoria:
    def __init__(self) -> None:
        self.escopos: list[dict] = [{}]

    def entrar_escopo(self) -> None:
        self.escopos.append({})

    def sair_escopo(self) -> None:
        if len(self.escopos) > 1:
            self.escopos.pop()

    def definir(self, nome: str, valor: object) -> None:
        self.escopos[-1][nome] = valor

    def atribuir(self, nome: str, valor: object) -> None:
        for escopo in reversed(self.escopos):
            if nome in escopo:
                escopo[nome] = valor
                return
        self.escopos[-1][nome] = valor

    def obter(self, nome: str, *, linha: int | None = None) -> object:
        for escopo in reversed(self.escopos):
            if nome in escopo:
                return escopo[nome]
        raise ErroExecucao(
            f"Nome desconhecido: {nome!r}. Não há variável, objeto ou "
            "função com esse nome.",
            linha=linha,
            sugestao="Verifique a digitação ou crie uma função com esse nome.",
        )
