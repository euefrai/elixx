"""Lexer da ELiXX: transforma o código-fonte em tokens.

Reconhece: identificadores, palavras reservadas (português), números,
unidades (px, %, vw, vh, ms, s, graus), strings, operadores, delimitadores
e comentários (# ou //).

Decisão de design: `800px` gera dois tokens — NUMERO(800) + UNIDADE(px) —
para que medidas nunca sejam tratadas como texto. O parser combina os dois
em um nó Medida da AST.

Comentários: `#` sempre inicia comentário (por isso cores hexadecimais
só valem entre aspas: cor: "#ff0000").
"""
from __future__ import annotations

from dataclasses import dataclass

from ..erros import ErroLexico
from ..unidades import UNIDADES_VALIDAS

PALAVRA = "PALAVRA"
IDENT = "IDENT"
NUMERO = "NUMERO"
UNIDADE = "UNIDADE"
STRING = "STRING"
SINAL = "SINAL"
EOF = "EOF"

# Vocabulário inicial. A linguagem cresce acrescentando palavras aqui e
# regras no parser — nunca quebrando o que já existe.
#
# Fase 02: só palavras ESTRUTURAIS são reservadas. Ações (mostrar, abrir...),
# eventos (clicar, aparecer...) e propriedades (titulo, tamanho, cor...)
# são vocabulário: lexam como IDENT e podem ser usadas como nomes
# (ex. "botão abrir" do marco da Fase 02). O parser aceita IDENT em todos
# esses pontos, então programas da Fase 01 continuam válidos.
PALAVRAS_RESERVADAS = frozenset(
    {
        # estrutura (reservadas: dão forma ao programa)
        "criar", "janela", "quando", "função", "funcao", "retornar",
        # Fase 03: bloco de animação (dispatch no parser)
        "animação", "animacao",
        # Fase 05: bloco de estado global (dispatch no parser)
        "estado",
        # Fase 06: bloco de fonte de dados (dispatch no parser)
        "dados",
        # Fase 08: blocos e tipos (dispatch no parser)
        "tema", "tela", "componente", "propriedade", "corpo",
        "conteudo", "conteúdo", "aba", "abas", "menu", "tabela",
        "formulario", "modal",
        # Fase 09: ação reutilizável e import (dispatch no parser)
        "acao", "importar",
        # tipos de componente (reservados: "texto x {" é componente,
        # "texto: ..." é propriedade — a distinção exige reserva)
        "botão", "botao", "texto", "imagem", "vídeo", "video",
        "áudio", "audio",
        # Extensão dashboard: contêineres e visualização de dados
        # (adição — nenhum programa existente quebra).
        "painel", "cartao", "cartão", "barra", "grafico", "gráfico",
        "lista",
        # Fase 04: layouts e componentes de formulário
        "linha", "coluna", "grade", "pilha", "entrada", "checkbox",
        "selecao", "seleção", "separador", "indicador",
        # Fase 07: ícone (tipo; props como arquivo/url continuam livres)
        "icone", "ícone",
        # controle
        "depois", "se", "senão", "senao", "repetir", "vezes",
        # lógica (reservadas: o parser de expressões depende delas)
        "e", "ou", "não", "nao", "verdadeiro", "falso",
    }
)

SINAIS_DUPLOS = {"==", "!=", "->", ">=", "<=", "+=", "-=", "*=", "/="}
SINAIS_SIMPLES = set(":{}(),.=><+-*/;[]%")


@dataclass
class Token:
    tipo: str
    valor: str | float
    linha: int
    coluna: int

    def __repr__(self) -> str:
        return f"Token({self.tipo}, {self.valor!r}, {self.linha}:{self.coluna})"


def tokenizar(fonte: str, nome_arquivo: str = "<memória>") -> list[Token]:
    """Converte o código-fonte em lista de tokens. Erros em português."""
    tokens: list[Token] = []
    i = 0
    linha = 1
    coluna = 1
    total = len(fonte)

    def erro(mensagem: str, sugestao: str | None = None,
             exemplo: str | None = None) -> ErroLexico:
        inicio = max(0, i - 20)
        fim = min(total, i + 20)
        trecho = fonte[inicio:fim].replace("\n", "⏎")
        return ErroLexico(mensagem, linha=linha, coluna=coluna,
                          trecho=f"{nome_arquivo} → ...{trecho}...",
                          sugestao=sugestao, exemplo=exemplo)

    while i < total:
        ch = fonte[i]

        # espaços e quebras de linha
        if ch in " \t\r":
            i += 1
            coluna += 1
            continue
        if ch == "\n":
            i += 1
            linha += 1
            coluna = 1
            continue

        # comentário com #
        if ch == "#":
            while i < total and fonte[i] != "\n":
                i += 1
            continue
        # comentário com //
        if ch == "/" and i + 1 < total and fonte[i + 1] == "/":
            while i < total and fonte[i] != "\n":
                i += 1
            continue

        # strings com aspas duplas
        if ch == '"':
            col_ini = coluna
            i += 1
            coluna += 1
            partes: list[str] = []
            fechada = False
            while i < total:
                c = fonte[i]
                if c == "\n":
                    raise erro(
                        "Texto entre aspas não foi fechado antes do fim da linha.",
                        sugestao="Feche o texto com aspas na mesma linha.",
                        exemplo='texto: "Olá ELiXX"',
                    )
                if c == "\\" and i + 1 < total:
                    prox = fonte[i + 1]
                    mapa = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                    partes.append(mapa.get(prox, prox))
                    i += 2
                    coluna += 2
                    continue
                if c == '"':
                    fechada = True
                    i += 1
                    coluna += 1
                    break
                partes.append(c)
                i += 1
                coluna += 1
            if not fechada:
                raise erro(
                    "Texto entre aspas não foi fechado até o fim do arquivo.",
                    sugestao="Adicione aspas duplas no final do texto.",
                    exemplo='texto: "Olá ELiXX"',
                )
            tokens.append(Token(STRING, "".join(partes), linha, col_ini))
            continue

        # seta longa → (futuro: animação com origem → destino)
        if ch == "→":
            tokens.append(Token(SINAL, "→", linha, coluna))
            i += 1
            coluna += 1
            continue

        # números (com unidade opcional grudada: 800px, 20%, 500ms)
        if ch.isdigit():
            col_ini = coluna
            ini = i
            while i < total and fonte[i].isdigit():
                i += 1
                coluna += 1
            if i < total and fonte[i] == "." and i + 1 < total and fonte[i + 1].isdigit():
                i += 1
                coluna += 1
                while i < total and fonte[i].isdigit():
                    i += 1
                    coluna += 1
            texto_num = fonte[ini:i] if fonte[ini] != "." else fonte[ini:i]
            # % grudado (ex. 20%)
            if i < total and fonte[i] == "%":
                tokens.append(Token(NUMERO, float(texto_num), linha, col_ini))
                tokens.append(Token(UNIDADE, "%", linha, coluna))
                i += 1
                coluna += 1
                continue
            # letras grudadas (ex. 800px, 500ms)
            j = i
            while j < total and (fonte[j].isalpha()):
                j += 1
            if j > i:
                unidade = fonte[i:j]
                if unidade not in UNIDADES_VALIDAS:
                    raise erro(
                        f"Unidade desconhecida: {unidade!r} depois do número {texto_num}.",
                        sugestao=f"Unidades válidas: {', '.join(sorted(UNIDADES_VALIDAS))}.",
                        exemplo="tamanho: 800px 600px",
                    )
                tokens.append(Token(NUMERO, float(texto_num), linha, col_ini))
                tokens.append(Token(UNIDADE, unidade, linha, coluna))
                coluna += j - i
                i = j
                continue
            tokens.append(Token(NUMERO, float(texto_num), linha, col_ini))
            continue

        # identificadores e palavras reservadas (aceitam acentos)
        if ch.isalpha() or ch == "_":
            col_ini = coluna
            ini = i
            while i < total and (fonte[i].isalnum() or fonte[i] == "_"):
                i += 1
                coluna += 1
            palavra = fonte[ini:i]
            if palavra in PALAVRAS_RESERVADAS:
                tokens.append(Token(PALAVRA, palavra, linha, col_ini))
            else:
                tokens.append(Token(IDENT, palavra, linha, col_ini))
            continue

        # sinais de dois caracteres
        par = fonte[i : i + 2]
        if par in SINAIS_DUPLOS:
            tokens.append(Token(SINAL, par, linha, coluna))
            i += 2
            coluna += 2
            continue
        if ch in SINAIS_SIMPLES:
            tokens.append(Token(SINAL, ch, linha, coluna))
            i += 1
            coluna += 1
            continue

        raise erro(
            f"Caractere inesperado: {ch!r}.",
            sugestao="Verifique se não há símbolo estranho ou aspas abertas.",
            exemplo='botão teste {\n    texto: "Olá ELiXX"\n}',
        )

    tokens.append(Token(EOF, "", linha, coluna))
    return tokens
