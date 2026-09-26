"""Cena e timeline do Studio (F25) — visualização, não edição completa.

ModeloCena resume a cena compilada (janelas, personagens). Timeline é
visualização de motions existentes (trilhas por alvo) + API para edição
futura. `timeline_de_motions` converte DefinicaoAnimacao F11.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["ModeloCena", "Timeline", "timeline_de_motions"]


class ModeloCena:
    """Resumo da cena compilada (para preview/inspetor/timeline)."""

    def __init__(self, janelas: int = 0, nos: int = 0,
                 personagens: list | None = None,
                 fonte: str = "") -> None:
        self.janelas = int(janelas)
        self.nos = int(nos)
        self.personagens = sorted(str(p) for p in
                                  (personagens or []))
        self.fonte = str(fonte)

    @staticmethod
    def da_cena(cena, fonte: str = "") -> ModeloCena:
        total = 0
        pilha = list(getattr(cena, "janelas", []))
        while pilha:
            no = pilha.pop()
            total += 1
            pilha.extend(getattr(no, "filhos", []))
        return ModeloCena(len(getattr(cena, "janelas", [])), total,
                          fonte=fonte)

    def to_dict(self) -> dict:
        return {"janelas": self.janelas, "nos": self.nos,
                "personagens": list(self.personagens),
                "fonte": self.fonte}

    def __repr__(self) -> str:
        return (f"ModeloCena({self.janelas} janelas, {self.nos} "
                f"nos)")


class Timeline:
    """Trilhas por alvo: [{alvo, blocos: [{nome, inicio, duracao}]}].

    Tempos em ms (finitos ≥ 0). Nesta fase: visualização + registro;
    edição de keyframes é futura (API já ordenada e determinística).
    """

    def __init__(self) -> None:
        self._trilhas: dict[str, list] = {}

    def _validar_tempo(self, valor, o_que: str) -> float:
        import math

        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ErroELiXX(f'Timeline: "{o_que}" numérico.')
        if not math.isfinite(numero) or numero < 0:
            raise ErroELiXX(f'Timeline: "{o_que}" finito ≥ 0.')
        return numero

    def adicionar(self, alvo: str, nome: str, inicio_ms: float = 0.0,
                  duracao_ms: float = 500.0) -> dict:
        if not str(alvo).strip() or not str(nome).strip():
            raise ErroELiXX("Timeline: alvo e nome não vazios.")
        bloco = {"nome": str(nome),
                 "inicio": self._validar_tempo(inicio_ms, "inicio"),
                 "duracao": self._validar_tempo(duracao_ms,
                                                "duracao")}
        trilha = self._trilhas.setdefault(str(alvo), [])
        trilha.append(bloco)
        trilha.sort(key=lambda b: (b["inicio"], b["nome"]))
        return bloco

    def trilhas(self) -> dict:
        return {alvo: list(blocos) for alvo, blocos in
                sorted(self._trilhas.items())}

    def duracao_total(self) -> float:
        total = 0.0
        for blocos in self._trilhas.values():
            for b in blocos:
                total = max(total, b["inicio"] + b["duracao"])
        return total

    def to_dict(self) -> dict:
        return {"trilhas": self.trilhas(),
                "duracao_total": self.duracao_total()}

    def __repr__(self) -> str:
        return (f"Timeline({len(self._trilhas)} trilhas, "
                f"{self.duracao_total():g}ms)")


def timeline_de_motions(definicoes: list) -> Timeline:
    """DefinicaoAnimacao F11 → Timeline (início 0, duração da def)."""
    linha = Timeline()
    for definicao in definicoes or []:
        alvo = getattr(definicao, "alvo", "?")
        nome = getattr(definicao, "nome", "?")
        duracao = float(getattr(definicao, "duracao_ms", 500.0))
        linha.adicionar(str(alvo), str(nome), 0.0, duracao)
    return linha
