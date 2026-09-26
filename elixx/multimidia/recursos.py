"""Recursos da ELiXX — caminhos, bytes, cache (Fase 07).

- Caminho `arquivo:` é relativo à pasta do `.elixx` (base_dir do
  Executor), nunca ao diretório atual do PowerShell.
- Cache em memória: mesma imagem duas vezes não recarrega.
- Remoto: download assíncrono (thread daemon) via stdlib; nunca bloqueia.
- Erros em português; nada derruba a aplicação.
"""
from __future__ import annotations

import os
import threading
import urllib.parse
import urllib.request

from ..erros import ErroELiXX

EXTENSOES_IMAGEM = (".png", ".gif", ".jpg", ".jpeg")
EXTENSOES_AUDIO = (".wav",)
EXTENSOES_VIDEO = (".mp4", ".avi", ".mkv", ".mov", ".webm")


def resolver_caminho(base_dir: str, caminho: str) -> str:
    """Absoluto passa direto; relativo ancora na pasta do .elixx."""
    if os.path.isabs(caminho):
        return caminho
    return os.path.normpath(os.path.join(base_dir or ".", caminho))


def ler_bytes(caminho_abs: str) -> bytes:
    try:
        with open(caminho_abs, "rb") as arq:
            return arq.read()
    except FileNotFoundError:
        raise ErroELiXX(
            f"Arquivo não encontrado: {caminho_abs}.",
            sugestao="Confira a pasta assets/ ao lado do .elixx.",
        )
    except OSError as exc:
        raise ErroELiXX(f"Não foi possível ler: {caminho_abs} ({exc}).")


def baixar_bytes(url: str, timeout_s: float = 10.0) -> bytes:
    esquema = urllib.parse.urlparse(url).scheme.lower()
    if esquema not in ("http", "https"):
        raise ErroELiXX(f"URL bloqueada (só http/https): {url}.")
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ELiXX/0.2"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.read()
    except Exception as exc:
        raise ErroELiXX(f"Download falhou: {url} ({exc}).")


def detectar_tipo(caminho: str) -> str:
    nome = caminho.lower().split("?")[0]
    if nome.endswith(".svg"):
        return "svg"
    if nome.endswith(EXTENSOES_IMAGEM):
        return "imagem"
    if nome.endswith(EXTENSOES_AUDIO):
        return "audio"
    if nome.endswith(EXTENSOES_VIDEO):
        return "video"
    return "desconhecido"


class CacheRecursos:
    """Cache em memória com estatísticas (para testes e docs)."""

    def __init__(self) -> None:
        self._itens: dict = {}
        self.hits = 0
        self.misses = 0

    def obter(self, chave: str):
        if chave in self._itens:
            self.hits += 1
            return self._itens[chave]
        self.misses += 1
        return None

    def guardar(self, chave: str, valor: object) -> None:
        self._itens[chave] = valor

    def limpar(self) -> None:
        self._itens.clear()


class GerenciadorRecursos:
    """Resolve + baixa + cacheia recursos (imagens/SVG/áudio)."""

    def __init__(self, base_dir: str = ".",
                 cache: CacheRecursos | None = None) -> None:
        self.base_dir = base_dir
        self.cache = cache or CacheRecursos()

    def caminho_local(self, caminho: str) -> str:
        return resolver_caminho(self.base_dir, caminho)

    def bytes_local(self, caminho: str) -> bytes:
        """Bytes com cache (chave = caminho absoluto)."""
        absoluto = self.caminho_local(caminho)
        achado = self.cache.obter("arq:" + absoluto)
        if achado is not None:
            return achado
        dados = ler_bytes(absoluto)
        self.cache.guardar("arq:" + absoluto, dados)
        return dados

    def baixar_async(self, url: str, pronto, timeout_s: float = 10.0) -> None:
        """Baixa em thread daemon; chama pronto(bytes) ou pronto(None)."""
        achado = self.cache.obter("url:" + url)
        if achado is not None:
            pronto(achado)
            return

        def trabalho():
            try:
                dados = baixar_bytes(url, timeout_s)
            except ErroELiXX:
                pronto(None)
                return
            self.cache.guardar("url:" + url, dados)
            pronto(dados)

        threading.Thread(target=trabalho, daemon=True,
                         name="elixx-recurso").start()
