"""Índice semântico (F27 CP2) — acesso O(1) amortizado, sem fuzzy."""
from __future__ import annotations

from ...erros import ErroELiXX
from .modelo import ModeloSemantico

__all__ = ["IndiceSemantico"]


class IndiceSemantico:
    """Índices sobre um ModeloSemantico (reconstruídos sob demanda).

    Por id, nome, tipo e arquivo; relações por origem e por destino.
    Sem embeddings, sem banco vetorial, sem fuzzy.
    """

    def __init__(self, modelo: ModeloSemantico) -> None:
        if not isinstance(modelo, ModeloSemantico):
            raise ErroELiXX("Semântico: índice espera modelo.")
        self.modelo = modelo
        self._por_nome: dict[str, list] = {}
        self._por_tipo: dict[str, list] = {}
        self._por_arquivo: dict[str, list] = {}
        self._de: dict[str, list] = {}
        self._para: dict[str, list] = {}
        self.reconstruir()

    def reconstruir(self) -> IndiceSemantico:
        """Relê o modelo inteiro (O(n); sem cache desatualizável)."""
        self._por_nome = {}
        self._por_tipo = {}
        self._por_arquivo = {}
        self._de = {}
        self._para = {}
        for ent in self.modelo.entidades():
            self._por_nome.setdefault(ent.nome, []).append(ent.id)
            self._por_tipo.setdefault(ent.tipo, []).append(ent.id)
            self._por_arquivo.setdefault(ent.arquivo, []).append(
                ent.id)
        for rel in self.modelo.relacoes():
            self._de.setdefault(rel.origem, []).append(rel)
            self._para.setdefault(rel.destino, []).append(rel)
        return self

    def buscar_por_id(self, ent_id: str):
        return self.modelo.obter_entidade(ent_id)

    def buscar_por_nome(self, nome: str) -> list:
        return [self.modelo.obter_entidade(eid) for eid in
                self._por_nome.get(str(nome), [])]

    def buscar_por_tipo(self, tipo: str) -> list:
        return [self.modelo.obter_entidade(eid) for eid in
                self._por_tipo.get(str(tipo), [])]

    def buscar_por_arquivo(self, arquivo: str) -> list:
        return [self.modelo.obter_entidade(eid) for eid in
                self._por_arquivo.get(str(arquivo), [])]

    def buscar_relacoes_de(self, ent_id: str) -> list:
        return list(self._de.get(str(ent_id), []))

    def buscar_relacoes_para(self, ent_id: str) -> list:
        return list(self._para.get(str(ent_id), []))

    def __repr__(self) -> str:
        return (f"IndiceSemantico({len(self.modelo)} entidades)")
