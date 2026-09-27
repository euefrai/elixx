"""Design System do ELiXX Studio (Fase 36B) — tokens + tema dark.

Honestidade de origem: os projetos-irmãos locais (Fajulto: extensão
VSCode com icon theme + gramática, sem tokens de cor; sem pastas
Juh/Kulia/principal_completo encontradas) NÃO possuem paleta
extraível. Estes tokens são DERIVADOS das convenções dark-editor
(fundo escuro, acento frio, texto de alto contraste) com identidade
própria ELiXX — documentados como escolha F36, não como medição.

Sem Tk no núcleo: só dados + `aplicar_tema(janela)` opcional.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = [
    "ELIXX_COLORS", "ELIXX_FONTS", "ELIXX_SPACING", "ELIXX_RADIUS",
    "ELIXX_BORDERS", "ELIXX_DENSITY", "ELIXX_METRICS",
    "validar_tokens", "aplicar_tema",
]

ELIXX_COLORS = {
    "background": "#16161d",
    "surface": "#1e1e26",
    "surface_alt": "#252532",
    "panel": "#1b1b22",
    "panel_hover": "#2a2a38",
    "border": "#343442",
    "text": "#e8e8f0",
    "text_muted": "#9a9ab0",
    "accent": "#7c6cf0",
    "accent_hover": "#9388f5",
    "success": "#58c98a",
    "warning": "#e0b45c",
    "error": "#e06c6c",
    "info": "#6cb8e0",
    "selection": "#37335c",
}
"""Paleta dark premium (fundo neutro-azulado, acento violeta ELiXX)."""

ELIXX_FONTS = {
    "titulo": ("Segoe UI", 13, "bold"),
    "section": ("Segoe UI", 10, "bold"),
    "label": ("Segoe UI", 9, ""),
    "body": ("Segoe UI", 9, ""),
    "code": ("Consolas", 9, ""),
    "caption": ("Segoe UI", 8, ""),
}
"""Hierarquia tipográfica (Segoe UI + Consolas; fallback Tk nativo)."""

ELIXX_SPACING = {
    "xs": 2, "sm": 4, "md": 8, "lg": 12, "xl": 16,
}
"""Espaçamento compacto (densidade sem poluição)."""

ELIXX_RADIUS = {
    "sm": 3, "md": 6, "lg": 10,
}
"""Raios simulados (Tk sem radius nativo; documentado)."""

ELIXX_BORDERS = {
    "fina": 1, "media": 2, "nenhuma": 0,
}
"""Espessuras (separadores sutis; sem bordas pesadas)."""

ELIXX_DENSITY = {
    "compacto": {"padx": 2, "pady": 1, "font_delta": 0},
    "normal": {"padx": 4, "pady": 3, "font_delta": 0},
}
"""Densidades (modo compacto F29 reaproveita chaves)."""

ELIXX_METRICS = {
    "altura_toolbar": 32, "largura_lateral": 220,
    "altura_editor_min": 120, "altura_console": 110,
}
"""Métricas de layout (mínimos testados em 800x500)."""


def validar_tokens() -> dict:
    """Valida hex, fontes, espaçamentos (sem display)."""
    import re

    problemas = []
    for nome, cor in ELIXX_COLORS.items():
        if not re.fullmatch(r"#[0-9a-f]{6}", cor):
            problemas.append(f"cor {nome}: {cor}")
    for nome, fonte in ELIXX_FONTS.items():
        if not (isinstance(fonte, tuple) and len(fonte) == 3
                and isinstance(fonte[1], int)):
            problemas.append(f"fonte {nome}")
    for nome, valor in ELIXX_SPACING.items():
        if not isinstance(valor, int) or valor < 0:
            problemas.append(f"espaço {nome}")
    if problemas:
        return {"valido": False, "codigo": "tokens_invalidos",
                "motivo": "; ".join(problemas)}
    return {"valido": True, "codigo": "ok",
            "motivo": f"{len(ELIXX_COLORS)} cores, "
                      f"{len(ELIXX_FONTS)} fontes."}


def aplicar_tema(janela) -> dict:
    """Aplica clam + cores em ttk (idempotente, com display)."""
    try:
        from tkinter import ttk
    except ImportError:
        raise ErroELiXX("Tema: Tk indisponível.")
    cores, fontes = ELIXX_COLORS, ELIXX_FONTS
    estilo = ttk.Style(janela)
    estilo.theme_use("clam")
    estilo.configure(".", background=cores["background"],
                     foreground=cores["text"],
                     fieldbackground=cores["surface"],
                     font=(fontes["body"][0], fontes["body"][1]))
    estilo.configure("TFrame", background=cores["background"])
    estilo.configure("TLabel", background=cores["background"],
                     foreground=cores["text"],
                     font=(fontes["label"][0],
                           fontes["label"][1]))
    estilo.configure("Header.TLabel",
                     font=(fontes["section"][0],
                           fontes["section"][1], "bold"),
                     foreground=cores["text"])
    estilo.configure("TButton", background=cores["surface_alt"],
                     foreground=cores["text"],
                     borderwidth=ELIXX_BORDERS["fina"],
                     relief="flat", padding=(8, 4))
    estilo.map("TButton",
               background=[("active", cores["panel_hover"]),
                           ("pressed", cores["selection"]),
                           ("disabled", cores["surface"])],
               foreground=[("disabled", cores["text_muted"])])
    estilo.configure("Accent.TButton",
                     background=cores["accent"],
                     foreground="#ffffff")
    estilo.map("Accent.TButton",
               background=[("active", cores["accent_hover"])])
    estilo.configure("Danger.TButton",
                     background=cores["error"],
                     foreground="#ffffff")
    estilo.configure("TEntry", fieldbackground=cores["surface"],
                     foreground=cores["text"],
                     borderwidth=ELIXX_BORDERS["fina"])
    estilo.configure("TNotebook", background=cores["background"],
                     borderwidth=0)
    estilo.configure("TNotebook.Tab",
                     background=cores["surface"],
                     foreground=cores["text_muted"],
                     padding=(10, 4))
    estilo.map("TNotebook.Tab",
               background=[("selected", cores["surface_alt"])],
               foreground=[("selected", cores["text"])])
    estilo.configure("Horizontal.TProgressbar",
                     background=cores["accent"])
    try:
        janela.configure(background=cores["background"])
    except Exception:
        pass
    return {"tema": "dark-premium",
            "cores": len(ELIXX_COLORS)}
