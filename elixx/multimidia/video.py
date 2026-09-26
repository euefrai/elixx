"""Vídeo da ELiXX (Fase 07) — abstração HONESTA, sem player falso.

Tkinter + stdlib não decodificam vídeo moderno (mp4/h264). Em vez de
fingir, a linguagem oferece: componente `video`, validação de arquivo,
estado e ações com erro claro indicando o backend futuro. O renderer
mostra placeholder informativo. Avaliação de dependencias externas em
docs/video.md (sem escolha nesta fase).
"""
from __future__ import annotations

import os

from ..erros import ErroELiXX
from .recursos import EXTENSOES_VIDEO


def validar_video(caminho_abs: str) -> dict:
    """Confere existência + extensão. Erro em português."""
    if not os.path.exists(caminho_abs):
        raise ErroELiXX(f"Vídeo não encontrado: {caminho_abs}.")
    if not caminho_abs.lower().endswith(EXTENSOES_VIDEO):
        raise ErroELiXX(
            f"Formato de vídeo não suportado: {caminho_abs}. "
            f"Extensões: {', '.join(EXTENSOES_VIDEO)}.")
    return {"arquivo": os.path.basename(caminho_abs),
            "tamanho_bytes": os.path.getsize(caminho_abs)}


class MotorVideo:
    """Guarda estado e explica a limitação (sem decodificação real)."""

    MENSAGEM = ("Vídeo: reprodução chega com backend dedicado "
                "(fase futura). Arquivo validado; nada foi tocado.")

    def __init__(self) -> None:
        self.estado = "parado"
        self.atual: str | None = None
        self.volume = 100

    def _futuro(self, caminho_abs: str | None = None) -> str:
        if caminho_abs is not None:
            validar_video(caminho_abs)
            self.atual = caminho_abs
        return self.MENSAGEM

    def reproduzir(self, caminho_abs: str, *, volume: int = 100) -> str:
        self.estado = "parado"
        return self._futuro(caminho_abs)

    def pausar(self) -> str:
        return self.MENSAGEM

    def continuar(self) -> str:
        return self.MENSAGEM

    def parar(self) -> str:
        self.estado = "parado"
        return self.MENSAGEM

    def definir_volume(self, valor: int) -> str:
        self.volume = max(0, min(100, int(valor)))
        return f"(volume {self.volume} guardado para o backend futuro)"
