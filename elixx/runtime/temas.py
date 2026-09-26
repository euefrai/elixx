"""Temas visuais da ELiXX (Fase 08).

Tema = cores + tamanhos + espaços nomeados. Componentes referenciam
`cor: tema.destaque`, `fonte: tema.normal`. Resolução acontece na Cena
(backend-agnóstico); a troca (`usar_tema`) re-resolve sem reconstruir.
"""
from __future__ import annotations

from ..cores import para_cor
from ..erros import ErroELiXX
from ..compilador import ast as A


def resolver_temas(definicoes: list) -> dict:
    """TemaDef[] → {nome: {"cores": {k: hex}, "tamanhos": {k: px}, ...}}."""
    temas = {}
    for definicao in definicoes:
        cores = {}
        for prop in definicao.cores:
            valor = prop.valores[0]
            if isinstance(valor, A.CorLit):
                try:
                    cores[prop.nome] = para_cor(
                        valor.valor, linha=prop.linha).hexadecimal
                except ErroELiXX:
                    cores[prop.nome] = valor.valor
            else:
                cores[prop.nome] = str(valor)
        tamanhos = {p.nome: float(p.valores[0].valor)
                    for p in definicao.tamanhos}
        espacos = {p.nome: float(p.valores[0].valor)
                   for p in definicao.espacos}
        temas[definicao.nome] = {"cores": cores, "tamanhos": tamanhos,
                                 "espacos": espacos}
    return temas


def cor_do_tema(temas: dict, tema: str, chave: str,
                linha: int = 0) -> str | None:
    try:
        return temas[tema]["cores"][chave]
    except KeyError:
        return None


def medida_do_tema(temas: dict, tema: str, chave: str) -> float | None:
    for secao in ("tamanhos", "espacos"):
        try:
            return float(temas[tema][secao][chave])
        except KeyError:
            continue
    return None
