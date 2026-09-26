"""Integração ELiXX ↔ Fajulto — interface EXPERIMENTAL (Fase 01).

Regra: a ELiXX funciona 100% sem Fajulto. Este módulo só define a forma
da ponte futura; chamar qualquer função aqui levanta erro explicando que
a especificação formal ainda não existe.

API futura prevista (não implementar até a especificação formal):

    elixx:    fajulto.executar("codigo ...")   # ELiXX chama Fajulto
    fajulto:  elixx.mostrar("texto")           # Fajulto chama ELiXX
"""
from __future__ import annotations

from ..erros import ErroExecucao

PONTE: dict = {
    "descricao": "Ponte ELiXX <-> Fajulto (experimental, Fase 01)",
    "disponivel": False,
    "futura_api_elixx": ["fajulto.executar(...)"],
    "futura_api_fajulto": ["elixx.mostrar(...)"],
}


def disponivel() -> bool:
    """Diz se a integração está ativa. Fase 01: sempre False."""
    return False


def executar(codigo: str):
    """Futuro: executa código Fajulto a partir da ELiXX."""
    raise ErroExecucao(
        "A integração com Fajulto ainda é experimental e está desativada "
        "na Fase 01. A ELiXX continua funcionando normalmente sem ela.",
        sugestao="Acompanhe o roadmap em docs/arquitetura-roadmap.md.",
    )
