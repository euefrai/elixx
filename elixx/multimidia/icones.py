"""Ícones embutidos da ELiXX (Fase 07) — SVG inline, sem arquivos.

Traço simples 24x24 (estilo currentColor: a cor vem do componente).
Uso: icone salvar { nome: "salvar" } (propriedade `nome`, não `arquivo`).
"""
from __future__ import annotations

from ..erros import ErroELiXX, sugerir

_BASE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="2">')


def _svg(corpo: str) -> str:
    return _BASE + corpo + "</svg>"


ICONES: dict[str, str] = {
    "salvar": _svg('<path d="M5 3h11l3 3v15H5z M8 3v5h7V3 M8 21v-8h8v8"/>'),
    "editar": _svg('<path d="M4 20l1-4L16 5l3 3L8 19z M14 7l3 3"/>'),
    "excluir": _svg('<path d="M4 7h16 M9 7V4h6v3 M6 7l1 14h10l1-14"/>'),
    "fechar": _svg('<path d="M6 6l12 12 M18 6L6 18"/>'),
    "adicionar": _svg('<path d="M12 5v14 M5 12h14"/>'),
    "config": _svg('<circle cx="12" cy="12" r="3"/>'
                   '<path d="M12 2v4 M12 18v4 M2 12h4 M18 12h4"/>'),
    "pesquisar": _svg('<circle cx="11" cy="11" r="6"/>'
                      '<path d="M16 16l5 5"/>'),
    "voltar": _svg('<path d="M15 5l-7 7 7 7"/>'),
    "avancar": _svg('<path d="M9 5l7 7-7 7"/>'),
    "menu": _svg('<path d="M4 7h16 M4 12h16 M4 17h16"/>'),
}


def obter(nome: str) -> str:
    """SVG do ícone (erro PT com sugestão se não existir)."""
    chave = (nome or "").strip().lower()
    if chave in ICONES:
        return ICONES[chave]
    parecidos = sugerir(chave, sorted(ICONES))
    dica = f" Você quis dizer: {', '.join(parecidos)}?" if parecidos else ""
    raise ErroELiXX(
        f"Ícone desconhecido: {nome!r}.{dica} "
        f"Ícones: {', '.join(sorted(ICONES))}.",
        sugestao="Use arquivo: \"assets/icone.svg\" para SVG próprio.",
    )
