"""Validação + snapshot do modelo (F27) — regras com evidência."""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from .modelo import ModeloSemantico, _e_dado

__all__ = ["SnapshotSemantico", "comparar_snapshots",
           "validar_modelo"]

TIPOS_ARQUIVO_OK = ("elixx",)
"""Tipos de arquivo aceitos no registro (resto = aviso, não erro)."""


def validar_modelo(modelo: ModeloSemantico) -> dict:
    """IDs únicos (garantido), refs existentes, paths contidos."""
    if not isinstance(modelo, ModeloSemantico):
        raise ErroELiXX("Semântico: espera modelo.")
    problemas = []
    for rel in modelo.relacoes():
        if rel.origem not in modelo:
            problemas.append(f"origem {rel.origem} ausente")
        if rel.destino not in modelo:
            problemas.append(f"destino {rel.destino} ausente")
    for ent in modelo.entidades():
        if ent.arquivo.startswith("/") or ".." in \
                ent.arquivo.split("/"):
            problemas.append(f"arquivo {ent.arquivo} fora")
        if not _e_dado(ent.dados):
            problemas.append(f"dados de {ent.id} inválidos")
    for arq in modelo.arquivos():
        if arq["tipo"] not in TIPOS_ARQUIVO_OK:
            problemas.append(f"arquivo {arq['caminho']} tipo "
                             f"{arq['tipo']}")
    if problemas:
        return {"valido": False, "codigo": "problemas",
                "motivo": "; ".join(sorted(set(problemas))[:5]),
                "total": len(problemas)}
    return {"valido": True, "codigo": "ok",
            "motivo": "Modelo válido.", "total": 0}


class SnapshotSemantico:
    """Cópia imutável (entidades, relações, arquivos, versão)."""

    def __init__(self, dados: dict) -> None:
        if not isinstance(dados, dict) or not _e_dado(dados):
            raise ErroELiXX("Semântico: snapshot inválido.")
        self._dados = json.loads(json.dumps(dados, sort_keys=True))
        self.versao = int(self._dados.get("versao", 1))

    @staticmethod
    def de_modelo(modelo: ModeloSemantico, versao: int = 1
                  ) -> SnapshotSemantico:
        if not isinstance(modelo, ModeloSemantico):
            raise ErroELiXX("Semântico: espera modelo.")
        dados = modelo.to_dict()
        dados["versao"] = int(versao)
        return SnapshotSemantico(dados)

    def entidades(self) -> dict:
        return {e["id"]: e for e in self._dados.get("entidades",
                                                    [])}

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self._dados, sort_keys=True))

    def __repr__(self) -> str:
        return (f"SnapshotSemantico(v{self.versao}: "
                f"{len(self.entidades())} entidades)")


def comparar_snapshots(antes: SnapshotSemantico,
                       depois: SnapshotSemantico) -> dict:
    """Diff por id: adicionados, removidos, alterados (ordenados)."""
    if not isinstance(antes, SnapshotSemantico) or not isinstance(
            depois, SnapshotSemantico):
        raise ErroELiXX("Semântico: comparar snapshots.")
    a, b = antes.entidades(), depois.entidades()
    ids_a, ids_b = set(a), set(b)
    alterados = sorted(i for i in ids_a & ids_b if a[i] != b[i])
    return {"adicionados": sorted(ids_b - ids_a),
            "removidos": sorted(ids_a - ids_b),
            "alterados": alterados}
