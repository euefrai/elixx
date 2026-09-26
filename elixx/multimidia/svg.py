"""SVG seguro da ELiXX (Fase 07) — subconjunto para ícones e formas.

Suportado: svg (viewBox/width/height), g, rect, circle, ellipse, line,
polyline, polygon, path (M/L/H/V/Z maiúsculos e minúsculos), text.
Atributos: fill, stroke, stroke-width, opacity (+ fill-/stroke-opacity).

NUNCA executado: <script>, <style>, atributos on*, referências externas
(href) são ignorados — SVG externo é recurso, não código. Erros em
português (ErroSVG). Saída: lista de operações primitivas que qualquer
renderer executa (Canvas Tk hoje, outros amanhã).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from ..erros import ErroELiXX

CORES_BASICAS = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000",
    "green": "#00aa00", "blue": "#0055ff", "yellow": "#ffdd00",
    "gray": "#888888", "grey": "#888888", "orange": "#ff8800",
    "purple": "#8800cc", "pink": "#ff88bb", "cyan": "#00cccc",
    "none": "",
}


class ErroSVG(ErroELiXX):
    """SVG inválido ou fora do subconjunto (mensagem em português)."""


def _numero(texto: str) -> float:
    texto = (texto or "").strip()
    texto = re.sub(r"(px|pt|pc|mm|cm|in)$", "", texto)
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _cor(texto: str | None, padrao: str = "") -> str:
    if texto is None:
        return padrao
    texto = texto.strip().lower()
    if texto in ("", "none", "transparent"):
        return ""
    if texto.startswith("#") and len(texto) in (4, 7, 9):
        return texto[:7]
    if texto in CORES_BASICAS:
        return CORES_BASICAS[texto]
    if texto == "currentcolor":
        return "currentcolor"
    return padrao


def _opacidade(no) -> float:
    try:
        return max(0.0, min(1.0, float(no.get("opacity", "1"))))
    except ValueError:
        return 1.0


def _estilo(no, padrao_preench: str = "") -> dict:
    return {
        "fill": _cor(no.get("fill"), padrao_preench),
        "stroke": _cor(no.get("stroke"), ""),
        "width": max(1.0, _numero(no.get("stroke-width", "1"))),
        "opacity": _opacidade(no),
    }


def _pontos(texto: str) -> list:
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", texto or "")]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _caminho_para_polilinhas(d: str) -> list:
    """Converte path (M/L/H/V/Z) em lista de polilinhas. Ignora curvas."""
    tokens = re.findall(r"[MmLlHhVvZz]|-?\d+(?:\.\d+)?", d or "")
    linhas: list[list] = []
    atual: list = []
    x = y = 0.0
    inicio = None
    comando = None
    i = 0

    def numero():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        tok = tokens[i]
        if tok in "MmLlHhVvZz":
            comando = tok
            i += 1
            if comando in "Zz":
                if atual and inicio is not None:
                    atual.append(inicio)
                    linhas.append(atual)
                    atual = []
                    x, y = inicio
                inicio = None
                continue
            continue
        if comando is None:
            i += 1
            continue
        if comando not in "MmLlHhVv":
            # Comando fora do subconjunto (ex. curvas): pula os números.
            if re.fullmatch(r"-?\d+(?:\.\d+)?", tok):
                i += 1
            else:
                i += 1
            continue
        if comando in "Mm":
            nx = numero()
            ny = numero()
            if comando == "m":
                nx += x
                ny += y
            x, y = nx, ny
            if atual:
                linhas.append(atual)
            atual = [(x, y)]
            inicio = (x, y)
            comando = "l" if comando == "m" else "L"
        elif comando in "Ll":
            nx = numero()
            ny = numero()
            if comando == "l":
                nx += x
                ny += y
            x, y = nx, ny
            atual.append((x, y))
        elif comando in "Hh":
            nx = numero()
            x = nx + x if comando == "h" else nx
            atual.append((x, y))
        elif comando in "Vv":
            ny = numero()
            y = ny + y if comando == "v" else ny
            atual.append((x, y))
    if atual:
        linhas.append(atual)
    return linhas


@dataclass
class DesenhoSVG:
    """Operações primitivas + tamanho de referência (viewBox)."""

    largura: float = 24.0
    altura: float = 24.0
    ops: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def _nome_local(tag: str) -> str:
    return tag.split("}")[-1].lower()


def parse_svg(texto: str) -> DesenhoSVG:
    """Interpreta SVG (subconjunto). Levanta ErroSVG em português."""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError as exc:
        raise ErroSVG(f"SVG inválido: {exc}.",
                      sugestao="Confira abertura/fechamento das tags.")
    if _nome_local(raiz.tag) != "svg":
        raise ErroSVG("O arquivo precisa ter <svg> como raiz.")
    desenho = DesenhoSVG()
    largura = _numero(raiz.get("width", "0"))
    altura = _numero(raiz.get("height", "0"))
    vista = raiz.get("viewBox", "").split()
    if len(vista) == 4:
        try:
            desenho.largura = float(vista[2])
            desenho.altura = float(vista[3])
        except ValueError:
            pass
    if largura > 0:
        desenho.largura = largura
    if altura > 0:
        desenho.altura = altura
    if desenho.largura <= 0 or desenho.altura <= 0:
        desenho.largura, desenho.altura = 24.0, 24.0
    _visitar(raiz, desenho, 0.0, 0.0)
    return desenho


def _visitar(no, desenho: DesenhoSVG, dx: float, dy: float) -> None:
    for filho in list(no):
        nome = _nome_local(filho.tag)
        if nome in ("script", "style", "foreignobject", "image", "use",
                    "animate", "set"):
            desenho.avisos.append(f"<{nome}> ignorado (não executado).")
            continue
        for chave in list(filho.attrib):
            if chave.lower().startswith("on"):
                del filho.attrib[chave]
        if nome == "g":
            _visitar(filho, desenho, dx, dy)
        elif nome == "rect":
            x = _numero(filho.get("x", "0")) + dx
            y = _numero(filho.get("y", "0")) + dy
            desenho.ops.append(("rect", x, y,
                                _numero(filho.get("width", "0")),
                                _numero(filho.get("height", "0")),
                                _estilo(filho)))
        elif nome == "circle":
            desenho.ops.append(("oval",
                                _numero(filho.get("cx", "0")) + dx,
                                _numero(filho.get("cy", "0")) + dy,
                                _numero(filho.get("r", "0")),
                                _estilo(filho)))
        elif nome == "ellipse":
            desenho.ops.append(("ellipse",
                                _numero(filho.get("cx", "0")) + dx,
                                _numero(filho.get("cy", "0")) + dy,
                                _numero(filho.get("rx", "0")),
                                _numero(filho.get("ry", "0")),
                                _estilo(filho)))
        elif nome == "line":
            desenho.ops.append(("line",
                                _numero(filho.get("x1", "0")) + dx,
                                _numero(filho.get("y1", "0")) + dy,
                                _numero(filho.get("x2", "0")) + dx,
                                _numero(filho.get("y2", "0")) + dy,
                                _estilo(filho)))
        elif nome in ("polyline", "polygon"):
            pts = [(_x + dx, _y + dy) for _x, _y in
                   _pontos(filho.get("points", ""))]
            if pts:
                desenho.ops.append(("poly", pts, _estilo(filho),
                                    nome == "polygon"))
        elif nome == "path":
            d_atual = filho.get("d", "")
            if re.search(r"[CcQqSsTtAa]", d_atual):
                desenho.avisos.append(
                    "Curvas Bézier ignoradas (subconjunto: M/L/H/V/Z).")
            for linha in _caminho_para_polilinhas(d_atual):
                pts = [(x + dx, y + dy) for x, y in linha]
                if len(pts) >= 2:
                    desenho.ops.append(("poly", pts, _estilo(filho), False))
        elif nome == "text":
            desenho.ops.append(("text",
                                _numero(filho.get("x", "0")) + dx,
                                _numero(filho.get("y", "0")) + dy,
                                (filho.text or ""),
                                _numero(filho.get("font-size", "12")),
                                _estilo(filho)))
        else:
            desenho.avisos.append(f"<{nome}> ignorado (fora do subconjunto).")
