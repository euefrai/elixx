"""Módulos ELiXX (Fase 09) — `importar a.b.c` sem sair do parser/runtime.

Regras: caminhos com pontos relativos à RAIZ do projeto (pasta do
.elixx de entrada); `..`, absolutos e saída da raiz bloqueados;
ciclos detectados (A → B → A); cada arquivo uma vez; tudo fundido num
Programa só (janelas, telas, funções, ações, estado, fontes, temas,
componentes). Estado duplicado entre arquivos é erro claro.
"""
from __future__ import annotations

import os

from ..erros import ErroELiXX
from . import ast as A
from .lexer import tokenizar


def carregar_programa(caminho_entrada: str) -> A.Programa:
    """Lê o entry + imports e devolve o Programa fundido (sem executar)."""
    from .parser import Parser

    if not caminho_entrada.lower().endswith(".elixx"):
        raise ErroELiXX(
            f"Extensão inesperada: {caminho_entrada!r}. Arquivos ELiXX usam .elixx.",
            sugestao="Renomeie para programa.elixx.",
        )
    raiz = os.path.dirname(os.path.abspath(caminho_entrada))
    fundido = A.Programa()
    visitados: set[str] = set()
    pilha: list[str] = []

    def nome_rel(absoluto: str) -> str:
        try:
            return os.path.relpath(absoluto, raiz)
        except ValueError:
            return absoluto

    def carregar(absoluto: str) -> None:
        if absoluto in pilha:
            ciclo = " → ".join([nome_rel(p) for p in pilha + [absoluto]])
            raise ErroELiXX(
                f"Importação circular detectada: {ciclo}.",
                sugestao="Quebre o ciclo movendo o recurso compartilhado "
                         "para um terceiro módulo.",
            )
        if absoluto in visitados:
            return  # import duplicado: resolve uma vez
        visitados.add(absoluto)
        pilha.append(absoluto)
        try:
            with open(absoluto, encoding="utf-8") as arq:
                fonte = arq.read()
        except OSError:
            raise ErroELiXX(
                f"Módulo não encontrado: {nome_rel(absoluto)}.",
                sugestao="Confira o caminho a partir da raiz do projeto.",
            )
        parcial = Parser(tokenizar(fonte, absoluto)).parse(
            exigir_janela=False)
        for imp in parcial.imports:
            carregar(resolver(imp.caminho, imp.linha))
        fundir(fundido, parcial, nome_rel(absoluto))
        pilha.pop()

    def resolver(caminho: str, linha: int) -> str:
        if not caminho or not all(
                p and p not in (".", "..") for p in caminho.split(".")):
            raise ErroELiXX(
                f"Caminho de import inválido: {caminho!r}. Use "
                "pontos a partir da raiz (ex. componentes.card).",
                linha=linha,
                exemplo="importar componentes.card",
            )
        candidato = os.path.normpath(
            os.path.join(raiz, *caminho.split(".")) + ".elixx")
        if not _dentro(candidato, raiz):
            raise ErroELiXX(
                f"Import fora do projeto bloqueado: {caminho!r}.",
                linha=linha,
                sugestao="Imports vivem dentro da pasta do projeto.",
            )
        if not os.path.isfile(candidato):
            raise ErroELiXX(
                f"Módulo não encontrado: {caminho!r} "
                f"(esperado {nome_rel(candidato)}).",
                linha=linha,
            )
        return candidato

    def fundir(destino: A.Programa, parcial: A.Programa,
               origem: str) -> None:
        destino.janelas.extend(parcial.janelas)
        destino.telas.extend(parcial.telas)
        destino.funcoes.extend(parcial.funcoes)
        destino.acoes.extend(parcial.acoes)
        destino.fontes.extend(parcial.fontes)
        destino.temas.extend(parcial.temas)
        destino.componentes.extend(parcial.componentes)
        destino.imports.extend(parcial.imports)
        if parcial.estado is not None:
            if destino.estado is None:
                destino.estado = parcial.estado
            else:
                existentes = {p.nome for p in destino.estado.propriedades}
                for prop in parcial.estado.propriedades:
                    if prop.nome in existentes:
                        raise ErroELiXX(
                            f'Estado "{prop.nome}" declarado em dois '
                            f"módulos (agora em {origem}).",
                            linha=prop.linha,
                            sugestao="Renomeie uma das chaves.",
                        )
                    destino.estado.propriedades.append(prop)

    carregar(os.path.abspath(caminho_entrada))
    return fundido


def _dentro(candidato: str, raiz: str) -> bool:
    """True se o caminho normalizado fica dentro da raiz."""
    try:
        return os.path.commonpath(
            [os.path.abspath(candidato), os.path.abspath(raiz)]
        ) == os.path.abspath(raiz)
    except ValueError:
        return False
