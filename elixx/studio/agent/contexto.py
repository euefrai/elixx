"""AgentContext (F26) — contexto incremental, limitado e serializável.

Nunca carrega o projeto inteiro: começa mínimo (projeto + arquivo
atual) e cresce por adição explícita (arquivo, símbolo, diagnóstico,
cena, personagem, asset), com tetos de quantidade e tamanho.
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["MAX_ARQUIVOS", "MAX_BYTES_ARQUIVO", "MAX_ITENS",
           "AgentContext"]

MAX_ARQUIVOS = 50
"""Teto de arquivos no contexto (incremental; acima = erro claro)."""

MAX_BYTES_ARQUIVO = 100_000
"""Teto de conteúdo por arquivo (sem cópias gigantes na memória)."""

MAX_ITENS = 200
"""Teto por categoria (símbolos, diagnósticos, assets...)."""


class AgentContext:
    """Contexto estruturado do Agent (projeto + recortes explícitos)."""

    def __init__(self, projeto: str = "",
                 arquivo_atual: str = "") -> None:
        self.projeto = str(projeto)
        self.arquivo_atual = str(arquivo_atual)
        self.arquivos: dict[str, str] = {}
        self.simbolos: list[dict] = []
        self.diagnosticos: list[dict] = []
        self.cenas: list[dict] = []
        self.personagens: list[dict] = []
        self.assets: list[dict] = []
        self.preview: dict = {}
        self.historico: list[str] = []

    # ----- adição incremental (com tetos) -----

    def adicionar_arquivo(self, caminho: str, conteudo: str
                          ) -> AgentContext:
        caminho_txt = B.id_valido(caminho, "caminho do arquivo")
        if not isinstance(conteudo, str):
            raise ErroELiXX("Agent: conteúdo de arquivo em texto.")
        if len(conteudo) > MAX_BYTES_ARQUIVO:
            raise ErroELiXX(f'Agent: "{caminho_txt}" além de '
                            f"{MAX_BYTES_ARQUIVO} chars no contexto "
                            "(adicione recorte menor).")
        if (caminho_txt not in self.arquivos
                and len(self.arquivos) >= MAX_ARQUIVOS):
            raise ErroELiXX(f"Agent: contexto além de {MAX_ARQUIVOS} "
                            "arquivos.")
        self.arquivos[caminho_txt] = conteudo
        return self

    def _adicionar_item(self, lista: list, item: dict, o_que: str,
                        teto: int = MAX_ITENS) -> None:
        if not isinstance(item, dict) or not B.e_dado(item):
            raise ErroELiXX(f"Agent: {o_que} precisa de dicionário "
                            "JSON.")
        if len(lista) >= teto:
            raise ErroELiXX(f"Agent: {o_que} além de {teto}.")
        lista.append(dict(item))

    def adicionar_simbolo(self, simbolo: dict) -> AgentContext:
        self._adicionar_item(self.simbolos, simbolo, "símbolo")
        return self

    def adicionar_diagnostico(self, diagnostico: dict
                              ) -> AgentContext:
        self._adicionar_item(self.diagnosticos, diagnostico,
                             "diagnóstico")
        return self

    def adicionar_cena(self, cena: dict) -> AgentContext:
        self._adicionar_item(self.cenas, cena, "cena")
        return self

    def adicionar_personagem(self, personagem: dict
                             ) -> AgentContext:
        self._adicionar_item(self.personagens, personagem,
                             "personagem")
        return self

    def adicionar_asset(self, asset: dict) -> AgentContext:
        self._adicionar_item(self.assets, asset, "asset")
        return self

    def definir_preview(self, resumo: dict) -> AgentContext:
        if not isinstance(resumo, dict) or not B.e_dado(resumo):
            raise ErroELiXX("Agent: preview precisa de dicionário.")
        self.preview = dict(resumo)
        return self

    def registrar_evento(self, evento: str) -> AgentContext:
        self.historico.append(B.id_valido(evento, "evento"))
        if len(self.historico) > MAX_ITENS:
            self.historico.pop(0)
        return self

    # ----- inspeção / serialização -----

    def tamanho(self) -> dict:
        return {"arquivos": len(self.arquivos),
                "bytes": sum(len(v) for v in
                             self.arquivos.values()),
                "simbolos": len(self.simbolos),
                "diagnosticos": len(self.diagnosticos),
                "cenas": len(self.cenas),
                "personagens": len(self.personagens),
                "assets": len(self.assets)}

    def to_dict(self) -> dict:
        dados = {"projeto": self.projeto,
                 "arquivo_atual": self.arquivo_atual,
                 "arquivos": dict(self.arquivos),
                 "simbolos": list(self.simbolos),
                 "diagnosticos": list(self.diagnosticos),
                 "cenas": list(self.cenas),
                 "personagens": list(self.personagens),
                 "assets": list(self.assets),
                 "preview": dict(self.preview),
                 "historico": list(self.historico)}
        if not B.e_dado(dados):
            raise ErroELiXX("Agent: contexto não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> AgentContext:
        if not isinstance(dados, dict):
            raise ErroELiXX("Agent: contexto precisa de dicionário.")
        ctx = AgentContext(str(dados.get("projeto", "")),
                           str(dados.get("arquivo_atual", "")))
        for caminho, conteudo in (dados.get("arquivos") or {}).items():
            ctx.adicionar_arquivo(caminho, conteudo)
        for item in (dados.get("simbolos") or []):
            ctx.adicionar_simbolo(item)
        for item in (dados.get("diagnosticos") or []):
            ctx.adicionar_diagnostico(item)
        for item in (dados.get("cenas") or []):
            ctx.adicionar_cena(item)
        for item in (dados.get("personagens") or []):
            ctx.adicionar_personagem(item)
        for item in (dados.get("assets") or []):
            ctx.adicionar_asset(item)
        if dados.get("preview"):
            ctx.definir_preview(dados["preview"])
        for evento in (dados.get("historico") or []):
            ctx.registrar_evento(evento)
        return ctx

    def __repr__(self) -> str:
        return (f"AgentContext({self.projeto}: "
                f"{len(self.arquivos)} arquivos)")
