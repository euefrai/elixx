"""Gerador HTML da ELiXX — saída funcional da Fase 01.

Converte a árvore de Objetos em uma página standalone: cada janela vira
um painel dimensionado e cada botão vira um <button> real. Manipuladores
`quando clicar { mostrar("...") }` simples viram `alert(...)`; eventos
mais complexos viram log no console. É uma prévia, não o renderer final.
"""
from __future__ import annotations

import html as _html

from ..compilador import ast as A
from ..runtime.objetos import Objeto


def _esc(texto: object) -> str:
    return _html.escape(str(texto), quote=True)


def _estilo_texto(obj: Objeto, prop: str) -> str | None:
    valor = obj.estilo.get(prop)
    if isinstance(valor, A.TextoLit):
        return valor.valor
    if isinstance(valor, str):
        return valor
    return None


def _alerta_clique(obj: Objeto) -> str | None:
    bloco = obj.eventos.get("clicar")
    if bloco is None:
        return None
    for cmd in bloco.comandos:
        if isinstance(cmd, A.Acao) and cmd.nome == "mostrar" and cmd.args:
            primeiro = cmd.args[0]
            if isinstance(primeiro, A.TextoLit):
                return primeiro.valor
    return None


def _colunas(obj: Objeto) -> list:
    for nome, valores in getattr(obj, "bruto", {}).items():
        if nome == "colunas":
            return [v.valor for v in valores
                    if isinstance(v, A.TextoLit)] or ["coluna"]
    return ["coluna"]


def _recurso(obj: Objeto, chave: str) -> str | None:
    valor = obj.estilo.get(chave)
    if isinstance(valor, A.TextoLit):
        return valor.valor
    return None


def _texto_prop(obj: Objeto, chave: str) -> str | None:
    for nome, valores in getattr(obj, "bruto", {}).items():
        if nome == chave and valores and isinstance(valores[0], A.TextoLit):
            return valores[0].valor
    return None


def _numero(no, chave: str, padrao: float) -> float:
    try:
        return float(getattr(no, chave, padrao) or padrao)
    except (TypeError, ValueError):
        return padrao


def _estilo_transform(no) -> str:
    """CSS de transformação (Fase 10: só emite o não-padrão).

    Layout continua em fluxo; transform move o visual (translate),
    gira (rotate), deforma (scale), ancora (transform-origin), mostra
    (opacity) e empilha (z-index). Sem transformação → sem atributo.
    """
    pos = getattr(no, "posicao", None)
    if pos is not None:
        # Objeto do runtime (pré-Cena): posição é tupla.
        try:
            x, y = float(pos[0]), float(pos[1])
        except (TypeError, ValueError, IndexError):
            x, y = 0.0, 0.0
    else:
        x, y = _numero(no, "x", 0.0), _numero(no, "y", 0.0)
    rot = _numero(no, "rotacao", 0.0) % 360.0
    esc = getattr(no, "escala", 1.0)
    try:
        sx = float(getattr(no, "escala_x", None)
                   if getattr(no, "escala_x", None) is not None else esc)
        sy = float(getattr(no, "escala_y", None)
                   if getattr(no, "escala_y", None) is not None else esc)
    except (TypeError, ValueError):
        sx, sy = 1.0, 1.0
    op = _numero(no, "opacidade", 1.0)
    camada = _numero(no, "camada", 0.0)
    partes: list[str] = []
    moves: list[str] = []
    if x or y:
        moves.append(f"translate({x:g}px, {y:g}px)")
    if rot:
        moves.append(f"rotate({rot:g}deg)")
    if sx != 1.0 or sy != 1.0:
        moves.append(f"scale({sx:g}, {sy:g})")
    if moves:
        partes.append("transform: " + " ".join(moves))
        px, py = getattr(no, "pivo_x", 50.0), getattr(no, "pivo_y", 50.0)
        ux, uy = (getattr(no, "pivo_unidade_x", "%") or "%",
                  getattr(no, "pivo_unidade_y", "%") or "%")
        if (px, py, ux, uy) != (50.0, 50.0, "%", "%"):
            partes.append(f"transform-origin: {px:g}{ux} {py:g}{uy}")
    if op != 1.0:
        partes.append(f"opacity: {op:g}")
    if camada:
        partes.append(f"z-index: {int(camada)}")
    if not partes:
        return ""
    return ' style="' + "; ".join(partes) + '"'


def _aria(obj: Objeto) -> str:
    descricao = _estilo_texto(obj, "descricao") or _estilo_texto(
        obj, "descrição")
    return f' aria-label="{_esc(descricao)}"' if descricao else ""


def _render_objeto(obj: Objeto) -> str:
    if obj.tipo == "tabela":
        colunas = _colunas(obj)
        cabecalho = "".join(f"<th>{_esc(c)}</th>" for c in colunas)
        return (f'<table class="elx-tabela"{_estilo_transform(obj)}>'
                f"<thead><tr>{cabecalho}</tr>"
                "</thead><tbody>"
                '<tr><td colspan="99">(linhas ao vivo só no nativo)</td></tr>'
                "</tbody></table>")
    if obj.tipo in ("grupo", "objeto", "personagem", "parte"):
        # Fase 10/12: contêiner visual (hierarquia + transformação).
        # Fase 12: `imagem:` vira <img> de fundo do contêiner.
        dentro = "\n".join(_render_objeto(f) for f in obj.filhos)
        fundo = ""
        src = _recurso(obj, "arquivo") or _recurso(obj, "url")
        if not src and obj.tipo in ("personagem", "parte"):
            # Fase 12: `imagem:` do personagem/parte (prop direta).
            for _nome, _valores in getattr(obj, "bruto", {}).items():
                if _nome == "imagem" and _valores:
                    primeiro = _valores[0]
                    if isinstance(primeiro, A.TextoLit):
                        src = primeiro.valor
                    break
        if src and obj.tipo in ("personagem", "parte"):
            alt = _estilo_texto(obj, "texto") or obj.nome or "imagem"
            fundo = (f'<img class="elx-img" src="{_esc(src)}" '
                     f'alt="{_esc(alt)}">\n')
        return (f'<div class="elx-grupo"{_estilo_transform(obj)}>\n'
                f"{fundo}{dentro}\n</div>")
    if obj.tipo == "abas":
        partes = []
        for filho in obj.filhos:
            if filho.tipo != "aba":
                continue
            titulo = _estilo_texto(filho, "texto") or filho.nome or "Aba"
            dentro = "\n".join(_render_objeto(n) for n in filho.filhos)
            partes.append(f"<details><summary>{_esc(titulo)}</summary>\n"
                            f"{dentro}\n</details>")
        return (f'<div class="elx-abas"{_estilo_transform(obj)}>\n'
                + "\n".join(partes) + "\n</div>")
    if obj.tipo == "modal":
        dentro = "\n".join(_render_objeto(f) for f in obj.filhos)
        return f'<div class="elx-modal"{_estilo_transform(obj)}>\n{dentro}\n</div>'
    if obj.tipo == "menu":
        dentro = "\n".join(_render_objeto(f) for f in obj.filhos)
        return f'<nav class="elx-menu"{_estilo_transform(obj)}>\n{dentro}\n</nav>'
    if obj.tipo == "formulario":
        dentro = "\n".join(_render_objeto(f) for f in obj.filhos)
        return f'<form class="elx-form"{_estilo_transform(obj)}>\n{dentro}\n</form>'
    if obj.tipo == "entrada":
        rotulo = _estilo_texto(obj, "texto") or obj.nome or ""
        return (f'<input class="elx-entrada"{_estilo_transform(obj)} '
                f'placeholder="{_esc(rotulo)}"'
                f"{_aria(obj)}>")
    if obj.tipo == "botao":
        rotulo = _estilo_texto(obj, "texto") or obj.nome or "Botão"
        estilo = _estilo_transform(obj)
        alerta = _alerta_clique(obj)
        if alerta is not None:
            onclick = f"alert({_esc(repr(alerta))})".replace("&quot;", '"')
            return (f'<button class="elx-btn"{estilo} onclick="alert({js_str(alerta)})"'
                    f"{_aria(obj)}>"
                    f"{_esc(rotulo)}</button>")
        return (f'<button class="elx-btn"{estilo} '
                f'onclick="console.log(\'clicar:{_esc(obj.nome)}\')"'
                f"{_aria(obj)}>"
                f"{_esc(rotulo)}</button>")
    if obj.tipo == "texto":
        conteudo = _estilo_texto(obj, "texto") or obj.nome
        return f'<p class="elx-texto"{_estilo_transform(obj)}>{_esc(conteudo)}</p>'
    if obj.tipo == "imagem":
        # Fase 07: arquivo local vira <img> (caminho relativo mantido);
        # remoto vira <img src>; sem fonte, placeholder honesto.
        src = _recurso(obj, "arquivo") or _recurso(obj, "url")
        alt = _estilo_texto(obj, "texto") or obj.nome or "imagem"
        estilo = _estilo_transform(obj)
        if src:
            return (f'<img class="elx-img"{estilo} src="{_esc(src)}" '
                    f'alt="{_esc(alt)}">')
        return (f'<div class="elx-midia"{estilo}>[imagem {_esc(obj.nome)} '
                "— sem arquivo]</div>")
    if obj.tipo == "icone":
        return (f'<div class="elx-midia"{_estilo_transform(obj)}>'
                f'[ícone {_esc(obj.nome)} '
                "— só no nativo]</div>")
    if obj.tipo == "audio":
        src = _recurso(obj, "arquivo") or _recurso(obj, "url")
        estilo = _estilo_transform(obj)
        if src:
            return (f'<audio class="elx-audio"{estilo} controls '
                    f'src="{_esc(src)}"></audio>')
        return (f'<div class="elx-midia"{estilo}>[áudio {_esc(obj.nome)} '
                "— sem arquivo]</div>")
    if obj.tipo == "video":
        src = _recurso(obj, "arquivo") or _recurso(obj, "url")
        estilo = _estilo_transform(obj)
        if src:
            return (f'<video class="elx-video"{estilo} controls '
                    f'src="{_esc(src)}"></video>')
        return (f'<div class="elx-midia"{estilo}>[vídeo {_esc(obj.nome)} '
                "— backend futuro]</div>")
    if obj.tipo == "grafico":
        return (f'<div class="elx-midia"{_estilo_transform(obj)}>'
                f'[gráfico {_esc(obj.nome)} '
                "— só no nativo]</div>")
    if obj.tipo == "lista" and getattr(obj, "modelo", []):
        # Fase 09: lista dinâmica — HTML estático não reconcilia.
        return (f'<div class="elx-midia"{_estilo_transform(obj)}>'
                f'[lista dinâmica {_esc(obj.nome)} '
                "— linhas ao vivo só no nativo]</div>")
    partes = [f'<div class="elx-generico"{_estilo_transform(obj)}>'
              f'{_esc(obj.nome)}']
    for filho in obj.filhos:
        partes.append(_render_objeto(filho))
    partes.append("</div>")
    return "\n".join(partes)


def _css_tema(temas: dict | None, tema_atual: str | None) -> str:
    """Variáveis CSS do tema atual (Fase 08; nativo faz o resto)."""
    if not temas or tema_atual not in (temas or {}):
        return ""
    linhas = []
    for secao in ("cores", "tamanhos", "espacos"):
        for chave, valor in temas[tema_atual].get(secao, {}).items():
            sufixo = "" if secao == "cores" else "px"
            linhas.append(f"  --elx-{chave}: {valor}{sufixo};")
    return ":root {\n" + "\n".join(linhas) + "\n}\n" if linhas else ""


def js_str(texto: str) -> str:
    return "'" + texto.replace("\\", "\\\\").replace("'", "\\'").replace(
        "\n", "\\n") + "'"


def gerar_html(objetos: list[Objeto], titulo: str = "Aplicação ELiXX",
               temas: dict | None = None,
               tema_atual: str | None = None) -> str:
    paineis = []
    for obj in objetos:
        larg, alt = obj.tamanho
        titulo_jan = _estilo_texto(obj, "titulo") or obj.nome or titulo
        filhos = "\n".join(_render_objeto(f) for f in obj.filhos)
        paineis.append(
            f'<section class="elx-janela" '
            f'style="width:{larg:g}px;min-height:{alt:g}px">\n'
            f"<h1>{_esc(titulo_jan)}</h1>\n{filhos}\n</section>")
    corpo = "\n".join(paineis)
    variaveis = _css_tema(temas, tema_atual)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{_esc(titulo)}</title>
<style>
{variaveis}body {{ font-family: sans-serif; background: #1e1e2e; color: #eee;
       display: flex; gap: 16px; padding: 24px; }}
.elx-janela {{ background: #fff; color: #111; border-radius: 12px;
              padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,.4); }}
.elx-btn {{ font-size: 16px; padding: 10px 22px; border-radius: 8px;
           border: none; background: #4f6df5; color: #fff; cursor: pointer; }}
.elx-btn:hover {{ background: #3b55c9; }}
.elx-texto {{ font-size: 18px; }}
.elx-midia {{ border: 1px dashed #999; padding: 8px; margin: 6px 0; }}
.elx-img {{ max-width: 100%; }}
.elx-audio, .elx-video {{ margin: 6px 0; max-width: 100%; }}
.elx-tabela {{ border-collapse: collapse; margin: 6px 0; }}
.elx-tabela th, .elx-tabela td {{ border: 1px solid #999; padding: 4px 10px; }}
.elx-modal {{ border: 2px solid #999; border-radius: 10px; padding: 12px; }}
.elx-menu {{ display: flex; gap: 8px; }}
.elx-form {{ display: flex; flex-direction: column; gap: 8px; }}
.elx-abas details {{ margin: 4px 0; }}
</style>
</head>
<body>
<!-- Gerado pela ELiXX Fase 01 -->
{corpo}
</body>
</html>
"""
