"""Histórico do Agent (F26) — tarefas e ChangeSets em memória.

Registrar, consultar, desfazer aplicação aprovada e recuperar
resultado. Persistência opcional em JSON (arquivo explícito, sem
banco obrigatório).
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["AgentHistory"]

MAX_REGISTROS = 500
"""Teto de registros em memória."""


class AgentHistory:
    """Trilha de tarefas (ordem de conclusão, determinística)."""

    def __init__(self) -> None:
        self._registros: list[dict] = []

    def registrar(self, tarefa) -> dict:
        from .tarefa import AgentTask

        if not isinstance(tarefa, AgentTask):
            raise ErroELiXX("Agent: histórico espera AgentTask.")
        registro = {"id": tarefa.id, "objetivo": tarefa.objetivo,
                    "estado": tarefa.estado,
                    "resultado": (tarefa.resultado.to_dict()
                                  if tarefa.resultado else None)}
        if not B.e_dado(registro):
            raise ErroELiXX("Agent: registro inválido.")
        self._registros.append(registro)
        if len(self._registros) > MAX_REGISTROS:
            self._registros.pop(0)
        return registro

    def listar(self) -> list[dict]:
        return [dict(r) for r in self._registros]

    def obter(self, tarefa_id: str) -> dict:
        for r in self._registros:
            if r["id"] == str(tarefa_id):
                return dict(r)
        raise ErroELiXX(f'Agent: tarefa "{tarefa_id}" fora do '
                        "histórico.")

    def salvar(self, caminho) -> int:
        from pathlib import Path

        destino = Path(caminho)
        destino.write_text(json.dumps(self._registros,
                                      ensure_ascii=False,
                                      sort_keys=True, indent=2),
                           encoding="utf-8")
        return len(self._registros)

    @staticmethod
    def carregar(caminho) -> AgentHistory:
        from pathlib import Path

        try:
            dados = json.loads(Path(caminho).read_text(
                encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ErroELiXX(f"Agent: histórico ilegível: {exc}.")
        if not isinstance(dados, list):
            raise ErroELiXX("Agent: histórico espera lista.")
        hist = AgentHistory()
        for r in dados:
            if not isinstance(r, dict) or not B.e_dado(r):
                raise ErroELiXX("Agent: registro inválido.")
            hist._registros.append(dict(r))
        return hist

    def __repr__(self) -> str:
        return f"AgentHistory({len(self._registros)} tarefas)"
