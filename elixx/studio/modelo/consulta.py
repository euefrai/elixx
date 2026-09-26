"""Consultas semânticas (F27 CP2) — API pequena e determinística."""
from __future__ import annotations

from .indice import IndiceSemantico
from .modelo import ModeloSemantico

__all__ = ["ConsultaSemantica"]


class ConsultaSemantica:
    """Fachada de leitura: nome, tipo, arquivo e relações."""

    def __init__(self, modelo: ModeloSemantico,
                 indice: IndiceSemantico | None = None) -> None:
        self.modelo = modelo
        self.indice = indice if indice is not None \
            else IndiceSemantico(modelo)

    def atualizar(self) -> ConsultaSemantica:
        """Reconstrói o índice após mutações no modelo."""
        self.indice.reconstruir()
        return self

    def encontrar_por_nome(self, nome: str) -> list:
        return self.indice.buscar_por_nome(nome)

    def encontrar_por_tipo(self, tipo: str) -> list:
        return self.indice.buscar_por_tipo(tipo)

    def encontrar_por_arquivo(self, arquivo: str) -> list:
        return self.indice.buscar_por_arquivo(arquivo)

    def relacoes_de(self, ent_id: str) -> list:
        return self.indice.buscar_relacoes_de(ent_id)

    def relacoes_para(self, ent_id: str) -> list:
        return self.indice.buscar_relacoes_para(ent_id)

    def vizinhanca(self, ent_id: str) -> dict:
        """Entidade + relações de saída e entrada (resumo)."""
        return {"entidade": self.indice.buscar_por_id(
            ent_id).to_dict(),
                "de": [r.to_dict() for r in self.relacoes_de(
                    ent_id)],
                "para": [r.to_dict() for r in self.relacoes_para(
                    ent_id)]}

    def __repr__(self) -> str:
        return "ConsultaSemantica()"
