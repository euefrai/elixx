"""Configuração do Studio (F25) — só dados seguros e locais.

Tema, fonte, painéis, último projeto/cena. Sem tokens, sem API keys,
sem segredos (recusados explicitamente na validação).
"""
from __future__ import annotations

import json

from ..erros import ErroELiXX

__all__ = ["Configuracao"]

CHAVES_SEGREDO = ("token", "api_key", "apikey", "secret", "senha",
                  "password", "credential")
"""Chaves proibidas na configuração (nunca persistir segredo)."""


class Configuracao:
    """Preferências locais (memória + JSON opcional)."""

    def __init__(self, tema: str = "claro",
                 tamanho_fonte: int = 12,
                 paineis: dict | None = None,
                 ultimo_projeto: str = "",
                 ultima_cena: str = "") -> None:
        tema_txt = str(tema).strip().lower()
        if tema_txt not in ("claro", "escuro"):
            raise ErroELiXX('Config: tema "claro" ou "escuro".')
        self.tema = tema_txt
        try:
            fonte = int(tamanho_fonte)
        except (TypeError, ValueError):
            raise ErroELiXX("Config: tamanho_fonte inteiro.")
        if not 8 <= fonte <= 32:
            raise ErroELiXX("Config: fonte entre 8 e 32.")
        self.tamanho_fonte = fonte
        paineis_txt = dict(paineis or {"projeto": True,
                                       "inspetor": True,
                                       "console": True,
                                       "timeline": True})
        for chave, valor in paineis_txt.items():
            if not isinstance(valor, bool):
                raise ErroELiXX(f'Config: painel "{chave}" booleano.')
        self.paineis = {str(k): v for k, v in paineis_txt.items()}
        self.ultimo_projeto = str(ultimo_projeto)
        self.ultima_cena = str(ultima_cena)

    def to_dict(self) -> dict:
        return {"tema": self.tema,
                "tamanho_fonte": self.tamanho_fonte,
                "paineis": dict(self.paineis),
                "ultimo_projeto": self.ultimo_projeto,
                "ultima_cena": self.ultima_cena}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True, indent=2)

    @staticmethod
    def from_dict(dados: dict) -> Configuracao:
        if not isinstance(dados, dict):
            raise ErroELiXX("Config precisa de dicionário.")
        for chave in dados:
            if (not isinstance(chave, str) or chave.lower() in
                    CHAVES_SEGREDO):
                raise ErroELiXX(f'Config: chave "{chave}" proibida '
                                "(segredo não persistido).")
        return Configuracao(
            tema=dados.get("tema", "claro"),
            tamanho_fonte=dados.get("tamanho_fonte", 12),
            paineis=dados.get("paineis"),
            ultimo_projeto=dados.get("ultimo_projeto", ""),
            ultima_cena=dados.get("ultima_cena", ""))

    @staticmethod
    def from_json(texto: str) -> Configuracao:
        if not isinstance(texto, str):
            raise ErroELiXX("Config JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Config JSON inválida: {exc}.")
        return Configuracao.from_dict(dados)

    def __repr__(self) -> str:
        return (f"Configuracao({self.tema} fonte={self.tamanho_fonte})")
