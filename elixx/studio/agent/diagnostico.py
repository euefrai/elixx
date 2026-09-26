"""Diagnóstico e resultado do Agent (F26) — estruturas sem traceback.

AgentDiagnostic espelha Diagnostic do Studio (código, mensagem,
arquivo, linha, coluna, severidade, origem, sugestão). AgentResult
resume a tarefa (sucesso, mudanças, arquivos, diagnósticos, preview).
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["AgentDiagnostic"]


class AgentDiagnostic:
    """Achado do Agent (nunca inventa correção)."""

    def __init__(self, codigo: str, mensagem: str,
                 arquivo: str = "", linha=None, coluna=None,
                 severidade: str = "error", origem: str = "preview",
                 sugestao: str = "") -> None:
        self.codigo = str(codigo).strip() or "ELX000"
        texto = str(mensagem).split("\n")[0][:300]
        if "Traceback" in texto:
            texto = "Erro interno (detalhe sem stack)."
        self.mensagem = texto
        self.arquivo = str(arquivo)
        self.linha = linha
        self.coluna = coluna
        sev = str(severidade).strip().lower()
        if sev not in ("info", "warning", "error"):
            raise ErroELiXX("Agent: severidade inválida.")
        self.severidade = sev
        self.origem = str(origem)
        self.sugestao = str(sugestao)[:300]

    @staticmethod
    def do_studio(diagnostico) -> AgentDiagnostic:
        return AgentDiagnostic(
            getattr(diagnostico, "codigo", "ELX000"),
            getattr(diagnostico, "mensagem", ""),
            arquivo=getattr(diagnostico, "arquivo", ""),
            linha=getattr(diagnostico, "linha", None),
            coluna=getattr(diagnostico, "coluna", None),
            severidade=getattr(diagnostico, "severidade", "error"),
            origem="studio",
            sugestao=getattr(diagnostico, "mensagem", ""))

    def to_dict(self) -> dict:
        return {"codigo": self.codigo, "mensagem": self.mensagem,
                "arquivo": self.arquivo, "linha": self.linha,
                "coluna": self.coluna, "severidade": self.severidade,
                "origem": self.origem, "sugestao": self.sugestao}

    def __repr__(self) -> str:
        return f"AgentDiagnostic({self.codigo} {self.arquivo})"
