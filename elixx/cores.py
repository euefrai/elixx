"""Tipo Cor da ELiXX.

Formas aceitas na Fase 01:

    cor: vermelho        # nome em português
    cor: "#ff0000"       # hexadecimal entre aspas

Reservado para o futuro (projetado, não implementado):

    cor: vermelho.mais_claro(20%)
    cor: azul.transparente(50%)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .erros import ErroSemantico

CORES_NOMEADAS: dict[str, str] = {
    "branco": "#ffffff",
    "preto": "#000000",
    "vermelho": "#ff0000",
    "verde": "#00aa00",
    "azul": "#0055ff",
    "amarelo": "#ffdd00",
    "laranja": "#ff8800",
    "roxo": "#8800cc",
    "rosa": "#ff88bb",
    "marrom": "#8b5a2b",
    "cinza": "#888888",
    "cinzento": "#888888",
    "ciano": "#00cccc",
    "transparente": "#00000000",
}

HEX_RE = re.compile(r"^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$|^#[0-9a-fA-F]{8}$")


@dataclass
class Cor:
    """Valor de cor normalizado (sempre com hexadecimal)."""

    hexadecimal: str
    nome: str | None = None

    def __str__(self) -> str:
        return self.hexadecimal


def eh_hex(texto: str) -> bool:
    """Diz se um texto entre aspas é uma cor hexadecimal."""
    return bool(HEX_RE.match(texto.strip()))


def normalizar_hex(texto: str) -> str:
    """Expande '#f00' para '#ff0000' e padroniza em minúsculas."""
    texto = texto.strip().lower()
    if len(texto) == 4:  # #rgb
        texto = "#" + "".join(c * 2 for c in texto[1:])
    return texto


def para_cor(valor: str, *, linha: int | None = None) -> Cor:
    """Converte um nome em português ou hexadecimal em Cor.

    Levanta ErroSemantico em português se o valor não for uma cor válida.
    """
    texto = valor.strip()
    if eh_hex(texto):
        return Cor(hexadecimal=normalizar_hex(texto))
    chave = texto.lower()
    if chave in CORES_NOMEADAS:
        return Cor(hexadecimal=CORES_NOMEADAS[chave], nome=chave)
    from .erros import sugerir

    parecidas = sugerir(chave, sorted(CORES_NOMEADAS))
    dica = f" Você quis dizer: {', '.join(parecidas)}?" if parecidas else ""
    raise ErroSemantico(
        f"Cor desconhecida: {valor!r}.{dica} Use um nome em português "
        f"(ex. vermelho, azul) ou hexadecimal entre aspas (ex. \"#ff0000\").",
        linha=linha,
        trecho=valor,
        exemplo='cor: vermelho\ncor: "#ff0000"',
    )
