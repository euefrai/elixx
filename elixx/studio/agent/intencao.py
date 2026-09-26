"""AgentIntent (F26) — intenção estruturada (sem LLM nesta fase).

Tipos: criar/modificar interface/componente/animação/personagem/cena,
diagnosticar, corrigir_erro, executar_preview, explicar_projeto.
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["TIPOS_INTENCAO", "AgentIntent"]

TIPOS_INTENCAO = ("criar_interface", "modificar_interface",
                  "criar_componente", "modificar_componente",
                  "criar_animacao", "modificar_animacao",
                  "modificar_personagem", "criar_cena",
                  "diagnosticar", "corrigir_erro",
                  "executar_preview", "explicar_projeto")
"""Intenções conhecidas (nova = erro claro; sem adivinhação)."""


class AgentIntent:
    """O que fazer + com o quê + por quê (só dados validados)."""

    def __init__(self, tipo: str, objetivo: str = "",
                 parametros: dict | None = None,
                 contexto_necessario: list | None = None,
                 origem: str = "usuario",
                 confianca=None,
                 metadata: dict | None = None) -> None:
        tipo_txt = str(tipo).strip()
        if tipo_txt not in TIPOS_INTENCAO:
            raise ErroELiXX(f'Agent: intenção "{tipo}" desconhecida '
                            f'({", ".join(TIPOS_INTENCAO)}).')
        self.tipo = tipo_txt
        self.objetivo = str(objetivo)
        params = dict(parametros or {})
        if not B.e_dado(params):
            raise ErroELiXX("Agent: parâmetros inválidos (JSON).")
        self.parametros = params
        ctx = [str(c) for c in (contexto_necessario or [])]
        self.contexto_necessario = ctx
        self.origem = str(origem).strip() or "usuario"
        self.confianca = B.finito_ou_nulo(confianca, "confiança")
        if (self.confianca is not None
                and not 0.0 <= self.confianca <= 1.0):
            raise ErroELiXX("Agent: confiança 0..1.")
        meta = dict(metadata or {})
        if not B.e_dado(meta):
            raise ErroELiXX("Agent: metadata inválida.")
        self.metadata = meta

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "objetivo": self.objetivo,
                "parametros": dict(self.parametros),
                "contexto_necessario": list(
                    self.contexto_necessario),
                "origem": self.origem, "confianca": self.confianca,
                "metadata": dict(self.metadata)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> AgentIntent:
        if not isinstance(dados, dict):
            raise ErroELiXX("Agent: intenção precisa de dicionário.")
        return AgentIntent(
            dados.get("tipo", ""),
            objetivo=dados.get("objetivo", ""),
            parametros=dict(dados.get("parametros") or {}),
            contexto_necessario=dados.get("contexto_necessario")
            or [],
            origem=dados.get("origem", "usuario"),
            confianca=dados.get("confianca"),
            metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"AgentIntent({self.tipo})"
