"""AgentResult (F26) — resumo estruturado final da tarefa."""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B
from .diagnostico import AgentDiagnostic

__all__ = ["AgentResult"]


class AgentResult:
    """Sucesso/falha + mudanças + arquivos + diagnósticos + preview."""

    def __init__(self, sucesso: bool, resumo: str = "",
                 alteracoes: list | None = None,
                 arquivos: list | None = None,
                 diagnosticos: list | None = None,
                 preview: dict | None = None) -> None:
        self.sucesso = bool(sucesso)
        self.resumo = str(resumo)[:500]
        self.alteracoes = [dict(a) for a in (alteracoes or [])]
        for a in self.alteracoes:
            if not B.e_dado(a):
                raise ErroELiXX("Agent: alteração inválida.")
        self.arquivos = B.ordenado(str(a) for a in
                                   (arquivos or []))
        self.diagnosticos = [d if isinstance(d, AgentDiagnostic)
                             else AgentDiagnostic(
                                 d.get("codigo", "ELX000"),
                                 d.get("mensagem", ""))
                             for d in (diagnosticos or [])]
        prev = dict(preview or {})
        if not B.e_dado(prev):
            raise ErroELiXX("Agent: preview inválido.")
        self.preview = prev

    def to_dict(self) -> dict:
        return {"sucesso": self.sucesso, "resumo": self.resumo,
                "alteracoes": list(self.alteracoes),
                "arquivos": list(self.arquivos),
                "diagnosticos": [d.to_dict()
                                 for d in self.diagnosticos],
                "preview": dict(self.preview)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return f"AgentResult(sucesso={self.sucesso})"
