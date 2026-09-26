"""Console/log do Studio (F25) — INFO/WARNING/ERROR amigáveis.

Nunca expõe traceback bruto como única mensagem: registra mensagem
curta + detalhe opcional (sem stack). Painel Tk espelha `entradas`.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["PainelLogs"]


class PainelLogs:
    """Log ordenado e limitado (determinístico)."""

    def __init__(self, teto: int = 1000) -> None:
        self.teto = int(teto)
        self.entradas: list[dict] = []

    def _registrar(self, nivel: str, mensagem: str,
                   detalhe: str = "") -> dict:
        if nivel not in ("INFO", "WARNING", "ERROR"):
            raise ErroELiXX(f'Log: nível "{nivel}" inválido.')
        texto = str(mensagem).split("\n")[0][:300]
        if "Traceback" in texto:
            texto = "Erro interno (ver detalhe sem stack)."
        registro = {"nivel": nivel, "mensagem": texto,
                    "detalhe": str(detalhe)[:500]}
        self.entradas.append(registro)
        if len(self.entradas) > self.teto:
            self.entradas.pop(0)
        return registro

    def info(self, mensagem: str) -> dict:
        return self._registrar("INFO", mensagem)

    def warning(self, mensagem: str, detalhe: str = "") -> dict:
        return self._registrar("WARNING", mensagem, detalhe)

    def error(self, mensagem: str, detalhe: str = "") -> dict:
        return self._registrar("ERROR", mensagem, detalhe)

    def por_nivel(self, nivel: str) -> list[dict]:
        return [e for e in self.entradas if e["nivel"] == nivel]

    def limpar(self) -> None:
        self.entradas.clear()

    def __repr__(self) -> str:
        return f"PainelLogs({len(self.entradas)} entradas)"
