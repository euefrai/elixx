"""Projeto ELiXX (Studio F25) — arquivo .elixxproj (JSON, só dados).

Carregar NUNCA executa conteúdo: valida tipos, caminhos (relativos,
dentro da raiz), versão e referências. Formato:

    {"nome": "Meu Projeto", "versao": 1, "entrada": "src/main.elixx"}
"""
from __future__ import annotations

import json

from ..erros import ErroELiXX

__all__ = ["ARQUIVO_PROJETO", "VERSAO_PROJETO", "ProjetoELiXX"]

ARQUIVO_PROJETO = "projeto.elixxproj"
"""Nome padrão do arquivo de projeto."""

VERSAO_PROJETO = 1
"""Versão atual do formato (outra versão = erro claro)."""


def _texto(valor, o_que: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'Projeto: "{o_que}" precisa de texto não '
                        "vazio.")
    return valor.strip()


class ProjetoELiXX:
    """Representação do projeto (metadados + entrada). Só dados."""

    def __init__(self, nome: str, entrada: str = "src/main.elixx",
                 versao: int = VERSAO_PROJETO,
                 descricao: str = "") -> None:
        self.nome = _texto(nome, "nome")
        self.entrada = _texto(entrada, "entrada")
        if "\\" in self.entrada or self.entrada.startswith("/"):
            raise ErroELiXX('Projeto: "entrada" usa barras "/" '
                            "relativas (sem drive, sem absoluto).")
        if ".." in self.entrada.split("/"):
            raise ErroELiXX('Projeto: "entrada" não pode conter "..".')
        if not isinstance(versao, int) or versao != VERSAO_PROJETO:
            raise ErroELiXX(f"Projeto: versão {versao!r} incompatível "
                            f"(esperada {VERSAO_PROJETO}).")
        self.versao = versao
        if not isinstance(descricao, str):
            raise ErroELiXX('Projeto: "descricao" precisa de texto.')
        self.descricao = descricao

    def to_dict(self) -> dict:
        return {"nome": self.nome, "versao": self.versao,
                "entrada": self.entrada, "descricao": self.descricao}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True, indent=2)

    @staticmethod
    def from_dict(dados: dict) -> ProjetoELiXX:
        if not isinstance(dados, dict):
            raise ErroELiXX("Projeto precisa de dicionário.")
        permitidas = {"nome", "versao", "entrada", "descricao"}
        for chave in dados:
            if chave not in permitidas:
                raise ErroELiXX(f'Projeto: chave "{chave}" '
                                "desconhecida.")
        return ProjetoELiXX(dados.get("nome", ""),
                            entrada=dados.get("entrada",
                                              "src/main.elixx"),
                            versao=dados.get("versao",
                                             VERSAO_PROJETO),
                            descricao=dados.get("descricao", ""))

    @staticmethod
    def from_json(texto: str) -> ProjetoELiXX:
        if not isinstance(texto, str):
            raise ErroELiXX("Projeto JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Projeto JSON inválido: {exc}.")
        return ProjetoELiXX.from_dict(dados)

    def __repr__(self) -> str:
        return f"ProjetoELiXX({self.nome} v{self.versao})"
