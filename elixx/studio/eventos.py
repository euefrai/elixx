"""Event bus do Studio (F25) — entrega ordenada, sem threads.

Eventos: arquivo_aberto/alterado/salvo, projeto_aberto/fechado,
selecionado, preview_iniciado/parado, erro, warning.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["EVENTOS", "EventBus"]

EVENTOS = ("arquivo_aberto", "arquivo_alterado", "arquivo_salvo",
           "projeto_aberto", "projeto_fechado", "selecionado",
           "preview_iniciado", "preview_parado", "erro", "warning")
"""Eventos conhecidos (novo evento = string registrada, sem código)."""


class EventBus:
    """Assinatura + emissão síncrona em ordem de registro."""

    def __init__(self) -> None:
        self._ouvintes: dict[str, list] = {}
        self.historico: list[dict] = []

    def assinar(self, evento: str, ouvinte) -> None:
        if evento not in EVENTOS:
            raise ErroELiXX(f'Evento "{evento}" desconhecido.')
        if not callable(ouvinte):
            raise ErroELiXX("Ouvinte precisa ser chamável.")
        self._ouvintes.setdefault(evento, []).append(ouvinte)

    def emitir(self, evento: str, dados: dict | None = None) -> int:
        """Emite para ouvintes em ordem; retorna nº notificados."""
        if evento not in EVENTOS:
            raise ErroELiXX(f'Evento "{evento}" desconhecido.')
        carga = dict(dados or {})
        self.historico.append({"evento": evento, "dados": carga})
        total = 0
        for ouvinte in list(self._ouvintes.get(evento, [])):
            ouvinte(evento, dict(carga))
            total += 1
        return total

    def eventos_emitidos(self) -> list[str]:
        return [h["evento"] for h in self.historico]

    def __repr__(self) -> str:
        return f"EventBus({len(self.historico)} emitidos)"
