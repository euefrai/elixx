"""Áudio da ELiXX (Fase 07) — abstração + backend real (stdlib).

Backend: winsound no Windows (WAV real, assíncrono, sem travar a UI).
Limitações honestas do backend (documentadas em docs/audio.md):
- formatos: só WAV (validado de verdade via wave);
- pausar = para e marca a posição (winsound não pausa);
- continuar = recomeça do início;
- volume é guardado mas NÃO tem efeito no winsound.
"""
from __future__ import annotations

import os
import wave
from abc import ABC, abstractmethod

from ..erros import ErroELiXX

ESTADOS_AUDIO = ("parado", "tocando", "pausado")


def validar_wav(caminho_abs: str) -> dict:
    """Confere que é WAV legível. Erro em português se não for."""
    try:
        with wave.open(caminho_abs, "rb") as som:
            return {"canais": som.getnchannels(),
                    "taxa": som.getframerate(),
                    "duracao_s": (som.getnframes() / som.getframerate()
                                  if som.getframerate() else 0.0)}
    except FileNotFoundError:
        raise ErroELiXX(f"Áudio não encontrado: {caminho_abs}.")
    except (wave.Error, EOFError, OSError):
        raise ErroELiXX(
            f"Áudio inválido ou corrompido: {caminho_abs}. "
            "O backend atual só toca WAV.",
            sugestao="Converta para .wav (PCM).")


class MotorAudio(ABC):
    """Interface que todo backend de áudio implementa."""

    def __init__(self) -> None:
        self.estado = "parado"
        self.atual: str | None = None
        self.volume = 100

    @abstractmethod
    def reproduzir(self, caminho_abs: str, *, volume: int = 100,
                   repetir: bool = False) -> str:
        """Toca de forma assíncrona. Retorna mensagem PT do feito."""

    @abstractmethod
    def pausar(self) -> str:
        """Pausa (ou o equivalente honesto do backend)."""

    @abstractmethod
    def continuar(self) -> str:
        """Retoma (ou o equivalente honesto do backend)."""

    @abstractmethod
    def parar(self) -> str:
        """Para imediatamente."""

    def definir_volume(self, valor: int) -> str:
        self.volume = max(0, min(100, int(valor)))
        return self.aplicar_volume()

    def aplicar_volume(self) -> str:
        return f"(volume {self.volume} guardado)"


class MotorWinsound(MotorAudio):
    """Backend Windows (winsound). Fora do Windows: erro claro."""

    def __init__(self) -> None:
        super().__init__()
        if os.name != "nt":
            raise ErroELiXX(
                "Áudio nativo disponível só no Windows (winsound).")
        try:
            import winsound as _ws

            self._ws = _ws
        except ImportError as exc:
            raise ErroELiXX(f"winsound indisponível: {exc}.")

    def reproduzir(self, caminho_abs: str, *, volume: int = 100,
                   repetir: bool = False) -> str:
        info = validar_wav(caminho_abs)
        flags = self._ws.SND_FILENAME | self._ws.SND_ASYNC
        if repetir:
            flags |= self._ws.SND_LOOP
        self._ws.PlaySound(caminho_abs, flags)
        self.estado = "tocando"
        self.atual = caminho_abs
        self.volume = max(0, min(100, int(volume)))
        return (f"(tocando {os.path.basename(caminho_abs)}, "
                f"{info['duracao_s']:.1f}s)")

    def pausar(self) -> str:
        # winsound não pausa de verdade: para e marca (documentado).
        self._ws.PlaySound(None, self._ws.SND_PURGE)
        if self.estado == "tocando":
            self.estado = "pausado"
            return "(pausado — continuar recomeça do início)"
        return "(nada tocando)"

    def continuar(self) -> str:
        if self.estado == "pausado" and self.atual:
            return self.reproduzir(self.atual, volume=self.volume)
        return "(nada pausado)"

    def parar(self) -> str:
        self._ws.PlaySound(None, self._ws.SND_PURGE)
        self.estado = "parado"
        self.atual = None
        return "(áudio parado)"

    def aplicar_volume(self) -> str:
        return (f"(volume {self.volume} guardado — sem efeito no "
                "backend winsound)")
