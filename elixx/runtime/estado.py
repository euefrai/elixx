"""Estado da ELiXX — variáveis reativas do programa (Fase 05).

O Estado guarda valores nomeados com versão por chave. O Vinculador usa
as versões para atualizar SOMENTE os consumidores do que mudou (pull,
sem callbacks encadeados — por isso ciclos não causam recursão).

Somente leitura externa via obter(); escrita via definir() (erros em
português listando chaves disponíveis, contra typos). Atribuição a chave
inexistente é erro — contadores usam a ação `incrementar`, que cria.
"""
from __future__ import annotations

from ..erros import ErroExecucao, sugerir


class Estado:
    """Dicionário reativo nome → valor, com versão por chave."""

    def __init__(self, iniciais: dict | None = None) -> None:
        self._valores: dict[str, object] = dict(iniciais or {})
        self._versoes: dict[str, int] = {k: 0 for k in self._valores}

    def __contains__(self, nome: str) -> bool:
        return nome in self._valores

    def __len__(self) -> int:
        return len(self._valores)

    def chaves(self) -> list[str]:
        return sorted(self._valores)

    def versao(self, nome: str) -> int:
        return self._versoes.get(nome, -1)

    def obter(self, nome: str, *, linha: int | None = None) -> object:
        try:
            return self._valores[nome]
        except KeyError:
            parecidas = sugerir(nome, self.chaves())
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroExecucao(
                f'Estado "{nome}" não existe.{dica} '
                f"Disponíveis: {', '.join(self.chaves()) or 'nenhum'} "
                "(declare no bloco estado).",
                linha=linha,
            )

    def definir(self, nome: str, valor: object, *,
                linha: int | None = None) -> None:
        if nome not in self._valores:
            parecidas = sugerir(nome, self.chaves())
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroExecucao(
                f'Estado "{nome}" não existe.{dica} Declare no bloco '
                "estado (ou use incrementar para contadores).",
                linha=linha,
            )
        self._valores[nome] = valor
        self._versoes[nome] = self._versoes.get(nome, 0) + 1

    def garantir(self, nome: str, inicial: object = None) -> None:
        """Cria a chave se não existir (fontes remotas; sem erro)."""
        if nome not in self._valores:
            self._valores[nome] = inicial
            self._versoes[nome] = 0

    def incrementar(self, nome: str, passo: float = 1.0,
                    *, linha: int | None = None) -> float:
        """Soma passo (cria com 0 se não existir). Retorna o novo valor."""
        atual = self._valores.get(nome, 0.0)
        if isinstance(atual, bool) or not isinstance(atual, (int, float)):
            raise ErroExecucao(
                f'Estado "{nome}" não é número e não pode incrementar.',
                linha=linha,
            )
        novo = float(atual) + float(passo)
        self._valores[nome] = novo
        self._versoes[nome] = self._versoes.get(nome, 0) + 1
        return novo
