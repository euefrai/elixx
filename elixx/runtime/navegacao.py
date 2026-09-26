"""Navegação da ELiXX (Fase 08) — pilha de telas previsível.

Só manipula visibilidade de Objetos (o tick sincroniza a tela).
Eventos `mostrar`/`esconder` disparam nas transições (se existirem).
Sem sistema paralelo: usa Executor.disparar e esconder/exibir.
"""
from __future__ import annotations

from ..erros import ErroExecucao, sugerir


class Navegador:
    """ir() empilha, voltar() desempilha, inicio() volta à primeira."""

    def __init__(self, executor) -> None:
        self.executor = executor
        self.telas: dict[str, object] = {}
        self.pilha: list[str] = []
        self.atual: str | None = None

    def registrar(self, telas: list, inicial: str | None = None) -> list[str]:
        """Guarda telas e esconde todas menos a inicial (sem eventos)."""
        self.telas = {t.nome: t for t in telas}
        self.pilha = []
        self.atual = None
        primeira = inicial if inicial in self.telas else None
        if primeira is None and telas:
            primeira = telas[0].nome
        for nome, tela in self.telas.items():
            tela.visivel = (nome == primeira)
        if primeira is not None:
            self.pilha = [primeira]
            self.atual = primeira
        return list(self.pilha)

    def _mostrar(self, nome: str) -> None:
        tela = self.telas[nome]
        tela.visivel = True
        self.executor.disparar(tela, "mostrar")

    def _esconder(self, nome: str) -> None:
        tela = self.telas[nome]
        tela.visivel = False
        self.executor.disparar(tela, "esconder")

    def ir(self, nome: str, *, linha: int = 0) -> None:
        if nome not in self.telas:
            parecidas = sugerir(nome, sorted(self.telas))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroExecucao(
                f'Tela desconhecida: "{nome}".{dica} '
                f"Telas: {', '.join(sorted(self.telas)) or 'nenhuma'}.",
                linha=linha,
            )
        if self.atual is not None and self.atual != nome:
            self._esconder(self.atual)
        if not self.pilha or self.pilha[-1] != nome:
            self.pilha.append(nome)
        self.atual = nome
        self._mostrar(nome)

    def voltar(self, *, linha: int = 0) -> None:
        if len(self.pilha) <= 1:
            raise ErroExecucao(
                "Nada para voltar: já está na primeira tela.",
                linha=linha,
            )
        self._esconder(self.pilha.pop())
        self.atual = self.pilha[-1]
        self._mostrar(self.atual)

    def inicio(self, *, linha: int = 0) -> None:
        if not self.pilha:
            return
        while len(self.pilha) > 1:
            self._esconder(self.pilha.pop())
        self.atual = self.pilha[-1]
        self._mostrar(self.atual)
