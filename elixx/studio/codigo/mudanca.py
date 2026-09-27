"""Mudança estruturada de código (F32) — serializável em JSON.

AlteracaoCodigo: arquivo + região + INSERIR/SUBSTITUIR/REMOVER +
antes/depois + motivo + entidade + operação de origem. Só dados.
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from .localizacao import LocalizacaoCodigo, RegiaoCodigo

__all__ = ["TIPOS_ALTERACAO", "MAX_TAMANHO_MUDANCA",
           "AlteracaoCodigo"]

TIPOS_ALTERACAO = ("INSERIR", "SUBSTITUIR", "REMOVER")
"""Tipos com uso seguro (MOVER fica para fase futura)."""

MAX_TAMANHO_MUDANCA = 100_000
"""Teto de conteúdo novo por alteração (anti payload)."""


def _e_dado(valor, prof: int = 0) -> bool:
    import math

    if prof > 6:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        return not (isinstance(valor, float)
                    and not math.isfinite(valor))
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(v, prof + 1) for v in valor)
    if isinstance(valor, dict):
        return all(isinstance(k, str) and _e_dado(v, prof + 1)
                   for k, v in valor.items())
    return False


class AlteracaoCodigo:
    """Uma edição cirúrgica (imutável após construção)."""

    def __init__(self, arquivo: str, regiao=None,
                 tipo: str = "SUBSTITUIR",
                 conteudo_anterior: str = "",
                 conteudo_novo: str = "",
                 motivo: str = "",
                 entidade_id: str = "",
                 operacao_origem: str = "") -> None:
        tipo_txt = str(tipo).strip().upper()
        if tipo_txt not in TIPOS_ALTERACAO:
            raise ErroELiXX(f"Código: tipo {tipo} inválido "
                            f'({", ".join(TIPOS_ALTERACAO)}).')
        self.tipo = tipo_txt
        if isinstance(regiao, RegiaoCodigo):
            self.regiao = regiao
        elif isinstance(regiao, dict):
            self.regiao = RegiaoCodigo(
                regiao.get("arquivo", arquivo),
                regiao.get("inicio", 1), regiao.get("fim", 1),
                regiao.get("conteudo_esperado", ""))
        else:
            raise ErroELiXX("Código: região (RegiaoCodigo/dict).")
        if self.regiao.local.arquivo != str(arquivo).strip():
            raise ErroELiXX("Código: arquivo ≠ arquivo da região.")
        self.arquivo = str(arquivo).strip()
        for rotulo, valor in (("anterior", conteudo_anterior),
                              ("novo", conteudo_novo)):
            if not isinstance(valor, str):
                raise ErroELiXX(f"Código: conteúdo {rotulo} em "
                                "texto.")
            if len(valor) > MAX_TAMANHO_MUDANCA:
                raise ErroELiXX(f"Código: conteúdo {rotulo} além "
                                f"de {MAX_TAMANHO_MUDANCA}.")
        self.conteudo_anterior = conteudo_anterior
        self.conteudo_novo = conteudo_novo
        self.motivo = str(motivo)
        self.entidade_id = str(entidade_id)
        self.operacao_origem = str(operacao_origem)

    def aplicar_texto(self, texto_atual: str) -> str:
        """Aplica em memória (região validada; sem disco)."""
        veredito = self.regiao.verificar(texto_atual)
        if not veredito["ok"]:
            raise ErroELiXX(f"{veredito['codigo']}: "
                            f"{veredito['motivo']}")
        linhas = texto_atual.split("\n")
        ini, fim = self.regiao.local.inicio_linha, \
            self.regiao.local.fim_linha
        if self.tipo == "SUBSTITUIR":
            novas = self.conteudo_novo.split("\n")
            return "\n".join(linhas[:ini - 1] + novas +
                             linhas[fim:])
        if self.tipo == "REMOVER":
            return "\n".join(linhas[:ini - 1] + linhas[fim:])
        # INSERIR: após a linha fim (fim pode ser len+1 = append)
        novas = self.conteudo_novo.split("\n")
        return "\n".join(linhas[:fim] + novas + linhas[fim:])

    def to_dict(self) -> dict:
        dados = {"arquivo": self.arquivo,
                 "regiao": self.regiao.to_dict(), "tipo": self.tipo,
                 "conteudo_anterior": self.conteudo_anterior,
                 "conteudo_novo": self.conteudo_novo,
                 "motivo": self.motivo,
                 "entidade_id": self.entidade_id,
                 "operacao_origem": self.operacao_origem}
        if not _e_dado(dados):
            raise ErroELiXX("Código: alteração não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> AlteracaoCodigo:
        if not isinstance(dados, dict):
            raise ErroELiXX("Código: alteração precisa de dict.")
        regiao = dados.get("regiao") or {}
        return AlteracaoCodigo(
            dados.get("arquivo", ""), regiao,
            tipo=dados.get("tipo", "SUBSTITUIR"),
            conteudo_anterior=dados.get("conteudo_anterior", ""),
            conteudo_novo=dados.get("conteudo_novo", ""),
            motivo=dados.get("motivo", ""),
            entidade_id=dados.get("entidade_id", ""),
            operacao_origem=dados.get("operacao_origem", ""))

    def __repr__(self) -> str:
        return (f"AlteracaoCodigo({self.tipo} {self.arquivo}:"
                f"{self.regiao.local.inicio_linha}-"
                f"{self.regiao.local.fim_linha})")
