"""AgentPlan (F26) — passos com dependências, risco e estado.

O plano NÃO executa sozinho: `avancar` só muda estado declarado
(útil para inspeção/UI); a execução real passa por ferramentas com
permissão + aprovação. Ciclos de dependência são recusados.
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["ESTADOS_PASSO", "NIVEIS_RISCO", "MAX_PASSOS", "PlanStep",
           "AgentPlan"]

ESTADOS_PASSO = ("pendente", "executando", "concluido", "falhou",
                 "cancelado", "bloqueado")
"""Estados de passo (transições validadas, sem pulo arbitrário)."""

NIVEIS_RISCO = ("baixo", "medio", "alto")
"""Risco declarado (guia aprovação; sem execução implícita)."""

MAX_PASSOS = 200
"""Teto de passos por plano."""

_TRANSICOES = {
    "pendente": ("executando", "cancelado", "bloqueado"),
    "bloqueado": ("pendente", "cancelado"),
    "executando": ("concluido", "falhou", "cancelado"),
    "concluido": (),
    "falhou": ("pendente", "cancelado"),
    "cancelado": (),
}
"""Transições permitidas (falhou→pendente = retry explícito)."""


class PlanStep:
    """Um passo: descrição, ferramenta, args, risco, dependências."""

    def __init__(self, passo_id: str, descricao: str = "",
                 tipo: str = "ferramenta",
                 dependencias: list | None = None,
                 ferramenta: str = "",
                 argumentos: dict | None = None,
                 risco: str = "baixo",
                 estado: str = "pendente") -> None:
        self.id = B.id_valido(passo_id, "id do passo")
        self.descricao = str(descricao)
        self.tipo = str(tipo).strip() or "ferramenta"
        deps = [str(d) for d in (dependencias or [])]
        if self.id in deps:
            raise ErroELiXX(f'Agent: passo "{self.id}" depende de si '
                            "mesmo.")
        self.dependencias = deps
        self.ferramenta = str(ferramenta)
        args = dict(argumentos or {})
        if not B.e_dado(args):
            raise ErroELiXX(f'Agent: argumentos de "{self.id}" '
                            "inválidos.")
        self.argumentos = args
        risco_txt = str(risco).strip() or "baixo"
        if risco_txt not in NIVEIS_RISCO:
            raise ErroELiXX(f'Agent: risco "{risco}" inválido.')
        self.risco = risco_txt
        if estado not in ESTADOS_PASSO:
            raise ErroELiXX(f'Agent: estado "{estado}" inválido.')
        self.estado = estado

    def transitar(self, novo: str) -> PlanStep:
        if novo not in _TRANSICOES[self.estado]:
            raise ErroELiXX(f'Agent: passo "{self.id}" não pode ir de '
                            f'"{self.estado}" para "{novo}".')
        self.estado = novo
        return self

    def to_dict(self) -> dict:
        return {"id": self.id, "descricao": self.descricao,
                "tipo": self.tipo,
                "dependencias": list(self.dependencias),
                "ferramenta": self.ferramenta,
                "argumentos": dict(self.argumentos),
                "risco": self.risco, "estado": self.estado}

    @staticmethod
    def from_dict(dados: dict) -> PlanStep:
        if not isinstance(dados, dict):
            raise ErroELiXX("Agent: passo precisa de dicionário.")
        return PlanStep(
            dados.get("id", ""), descricao=dados.get("descricao",
                                                     ""),
            tipo=dados.get("tipo", "ferramenta"),
            dependencias=dados.get("dependencias") or [],
            ferramenta=dados.get("ferramenta", ""),
            argumentos=dict(dados.get("argumentos") or {}),
            risco=dados.get("risco", "baixo"),
            estado=dados.get("estado", "pendente"))

    def __repr__(self) -> str:
        return f"PlanStep({self.id} {self.estado})"


class AgentPlan:
    """Plano: intenção + passos ordenáveis por dependência."""

    def __init__(self, intencao=None, passos: list | None = None,
                 estado: str = "pendente") -> None:
        from .intencao import AgentIntent

        if intencao is not None and not isinstance(intencao,
                                                   AgentIntent):
            raise ErroELiXX("Agent: plano espera AgentIntent.")
        self.intencao = intencao
        self.passos: dict[str, PlanStep] = {}
        for p in (passos or []):
            passo = (p if isinstance(p, PlanStep)
                     else PlanStep.from_dict(p))
            if passo.id in self.passos:
                raise ErroELiXX(f'Agent: passo "{passo.id}" '
                                "duplicado.")
            if len(self.passos) >= MAX_PASSOS:
                raise ErroELiXX(f"Agent: plano além de {MAX_PASSOS} "
                                "passos.")
            self.passos[passo.id] = passo
        if estado not in ("pendente", "executando", "concluido",
                          "falhou", "cancelado"):
            raise ErroELiXX(f'Agent: estado "{estado}" inválido.')
        self.estado = estado
        self._validar_dependencias()

    def _validar_dependencias(self) -> None:
        for pid, passo in self.passos.items():
            for dep in passo.dependencias:
                if dep not in self.passos:
                    raise ErroELiXX(f'Agent: passo "{pid}" depende de '
                                    f'"{dep}" inexistente.')
        # ciclo (DFS determinística por id ordenado)
        visitando: set[str] = set()
        visitado: set[str] = set()

        def _visita(pid: str, pilha: tuple) -> None:
            if pid in visitando:
                ciclo = "→".join(pilha + (pid,))
                raise ErroELiXX(f"Agent: ciclo no plano ({ciclo}).")
            if pid in visitado:
                return
            visitando.add(pid)
            for dep in sorted(self.passos[pid].dependencias):
                _visita(dep, pilha + (pid,))
            visitando.remove(pid)
            visitado.add(pid)

        for pid in sorted(self.passos):
            _visita(pid, ())

    def ordem_execucao(self) -> list[str]:
        """Topológica determinística (Kahn; empate por id)."""
        grau = {pid: 0 for pid in self.passos}
        for pid, passo in self.passos.items():
            for dep in passo.dependencias:
                grau[pid] += 1
        prontos = sorted(pid for pid, g in grau.items() if g == 0)
        ordem = []
        while prontos:
            pid = prontos.pop(0)
            ordem.append(pid)
            for outro, passo in self.passos.items():
                if pid in passo.dependencias:
                    grau[outro] -= 1
                    if grau[outro] == 0:
                        prontos.append(outro)
            prontos.sort()
        if len(ordem) != len(self.passos):
            raise ErroELiXX("Agent: ciclo no plano.")
        return ordem

    def prontos(self) -> list[str]:
        """Passos pendentes com dependências concluídas."""
        concluidos = {pid for pid, p in self.passos.items()
                      if p.estado == "concluido"}
        return sorted(pid for pid, p in self.passos.items()
                      if p.estado == "pendente" and set(
                          p.dependencias) <= concluidos)

    def passo(self, passo_id: str) -> PlanStep:
        try:
            return self.passos[str(passo_id)]
        except KeyError:
            raise ErroELiXX(f'Agent: passo "{passo_id}" ausente.')

    def to_dict(self) -> dict:
        return {"intencao": (self.intencao.to_dict()
                             if self.intencao else None),
                "passos": [self.passos[pid].to_dict()
                           for pid in sorted(self.passos)],
                "estado": self.estado}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"AgentPlan({len(self.passos)} passos, "
                f"{self.estado})")
