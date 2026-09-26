"""Base de validação do Agent (F26) — só dados, sem código executável."""
from __future__ import annotations

import math

from ...erros import ErroELiXX

__all__ = ["e_dado", "id_valido", "ordenado", "finito_ou_nulo"]


def e_dado(valor, profundidade: int = 0, teto: int = 6) -> bool:
    """JSON puro, finito e raso (sem tupla, objeto ou código)."""
    if profundidade > teto:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, float) and not math.isfinite(valor):
            return False
        return True
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(e_dado(v, profundidade + 1, teto) for v in valor)
    if isinstance(valor, dict):
        return all(isinstance(k, str) and e_dado(v, profundidade + 1,
                                                 teto)
                   for k, v in valor.items())
    return False


def id_valido(valor, o_que: str = "id") -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'Agent: "{o_que}" precisa de texto não '
                        "vazio.")
    return valor.strip()


def ordenado(valores) -> list:
    return sorted(valores)


def finito_ou_nulo(valor, o_que: str):
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'Agent: "{o_que}" numérico '
                        f"(recebido {type(valor).__name__}).")
    if not math.isfinite(numero):
        raise ErroELiXX(f'Agent: "{o_que}" finito (NaN/Infinity).')
    return numero
