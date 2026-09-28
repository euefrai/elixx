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
    "ELIXX_GAP", "ELIXX_FONT_SIZE", "ELIXX_LINE_HEIGHT",
    "ELIXX_PANEL_WIDTH", "ELIXX_TOOLBAR_HEIGHT",
    "ELIXX_DS3", "ELIXX_TYPE", "ELIXX_SPACE", "ELIXX_RADIUS_V3",
    "validar_tokens", "validar_ds3", "aplicar_tema", "paleta",
    "estilizar_tk", "titulo_escuro", "contraste",
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

ELIXX_COLORS["surface_elevated"] = "#232330"
ELIXX_COLORS["surface_hover"] = "#2a2a38"
ELIXX_COLORS["surface_active"] = "#37335c"
ELIXX_COLORS["danger"] = "#e06c6c"
"""F38: superfícies de elevação/hover/ativo + danger (mesma base)."""

ELIXX_GAP = {
    "xs": 2, "sm": 4, "md": 8, "lg": 12,
}
"""Intervalos entre blocos (compacto por padrão)."""

ELIXX_FONT_SIZE = {
    "titulo": 13, "section": 10, "label": 9, "body": 9,
    "code": 9, "caption": 8,
}
"""Tamanhos em pt (espelham ELIXX_FONTS; sem número solto na UI)."""

ELIXX_LINE_HEIGHT = {
    "titulo": 18, "section": 14, "label": 12, "body": 12,
    "code": 13, "caption": 11,
}
"""Altura de linha por estilo (legibilidade sem aperto)."""

ELIXX_PANEL_WIDTH = {
    "project": 220, "inspector": 240, "agent_min": 260,
}
"""Larguras de referência (mínimos funcionais)."""

ELIXX_TOOLBAR_HEIGHT = 32
"""Altura da barra superior (compacta e fixa)."""


ELIXX_DS3 = {
    "bg_base": "#0d0d12",
    "bg_alt": "#111118",
    "surface": "#171720",
    "surface_elevated": "#1d1d27",
    "surface_active": "#242432",
    "border": "#30303d",
    "text_primary": "#f3f3f7",
    "text_secondary": "#b8b8c5",
    "text_muted": "#8e8e9e",
    "accent": "#8b5cf6",
    "accent_hover": "#9b6cff",
    "accent_active": "#7446d8",
    "success": "#58c98a",
    "warning": "#e0b45c",
    "danger": "#e06c6c",
    "info": "#6cb8e0",
    "selection": "#2c2456",
}
"""Design System 3.0: tokens semanticos (ELIXX_COLORS legado intacto)."""


ELIXX_TYPE = {
    "app_title": ("Segoe UI", 13, "bold"),
    "section_title": ("Segoe UI", 11, "bold"),
    "panel_title": ("Segoe UI", 10, "bold"),
    "subtitle": ("Segoe UI", 9, "bold"),
    "body": ("Segoe UI", 9, ""),
    "secondary": ("Segoe UI", 8, ""),
    "monospace": ("Consolas", 9, ""),
}
"""Hierarquia tipografica 3.0 (sistema + monospace; sem dependencia)."""


ELIXX_SPACE = {
    "xs": 2, "sm": 4, "md": 6, "lg": 8, "xl": 12, "x2": 16,
    "x3": 20, "x4": 24, "x5": 32,
}
"""Escala de espacamento 3.0 (2,4,6,8,12,16,20,24,32)."""


ELIXX_RADIUS_V3 = {
    "small": 3, "medium": 6, "large": 10,
}
"""Raios 3.0 (moderado; editor tecnico segue preciso)."""


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


def _luminancia(hex_cor: str) -> float:
    hex_cor = hex_cor.lstrip("#")
    rgb = [int(hex_cor[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    canal = [c / 12.92 if c <= 0.03928
             else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return (0.2126 * canal[0] + 0.7152 * canal[1]
            + 0.0722 * canal[2])


def contraste(frente: str, fundo: str) -> float:
    """Razao de contraste WCAG (texto/fundo; >= 4.5 legivel)."""
    import re

    for cor in (frente, fundo):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(cor)):
            raise ErroELiXX(f"Tema: cor invalida ({cor}).")
    lum_a = _luminancia(frente)
    lum_b = _luminancia(fundo)
    claro, escuro = max(lum_a, lum_b), min(lum_a, lum_b)
    return (claro + 0.05) / (escuro + 0.05)


def validar_ds3() -> dict:
    """Valida paleta/tipo/espaco/raios 3.0 (sem display)."""
    import re

    problemas = []
    for nome, cor in ELIXX_DS3.items():
        if not re.fullmatch(r"#[0-9a-f]{6}", cor):
            problemas.append(f"ds3 {nome}: {cor}")
    for par in (("text_primary", "surface"),
                ("text_secondary", "surface"),
                ("text_muted", "surface_elevated")):
        try:
            if contraste(ELIXX_DS3[par[0]],
                         ELIXX_DS3[par[1]]) < 4.5:
                problemas.append(f"contraste {par[0]}")
        except ErroELiXX as exc:
            problemas.append(str(exc))
    if list(ELIXX_SPACE.values()) != [2, 4, 6, 8, 12, 16, 20,
                                      24, 32]:
        problemas.append("espaco fora da escala")
    tipos = [ELIXX_TYPE[k][1] for k in
             ("app_title", "section_title", "panel_title",
              "body", "secondary")]
    if not (tipos[0] >= tipos[1] >= tipos[2] >= tipos[3]
            >= tipos[4]):
        problemas.append("tipo fora de ordem")
    raios = [ELIXX_RADIUS_V3[k] for k in ("small", "medium",
                                          "large")]
    if not (raios[0] < raios[1] < raios[2]):
        problemas.append("raios fora de ordem")
    if problemas:
        return {"valido": False, "codigo": "ds3_invalido",
                "motivo": "; ".join(problemas)}
    return {"valido": True, "codigo": "ok",
            "motivo": f"{len(ELIXX_DS3)} tokens, "
                      f"{len(ELIXX_TYPE)} niveis."}


def paleta() -> dict:
    """DS3 com aliases legados (fonte unica para a UI)."""
    d = ELIXX_DS3
    return {"background": d["bg_base"],
            "surface": d["surface"],
            "surface_alt": d["surface_elevated"],
            "surface_elevated": d["surface_elevated"],
            "surface_hover": d["surface_active"],
            "surface_active": d["surface_active"],
            "panel": d["surface"],
            "panel_hover": d["surface_active"],
            "border": d["border"],
            "text": d["text_primary"],
            "text_muted": d["text_muted"],
            "text_secondary": d["text_secondary"],
            "accent": d["accent"],
            "accent_hover": d["accent_hover"],
            "selection": d["selection"],
            "success": d["success"],
            "warning": d["warning"],
            "danger": d["danger"],
            "error": d["danger"],
            "info": d["info"]}


def aplicar_tema(janela) -> dict:
    """Aplica clam + DS3 em ttk (idempotente, com display)."""
    try:
        from tkinter import ttk
    except ImportError:
        raise ErroELiXX("Tema: Tk indisponível.")
    cores, tipos = ELIXX_DS3, ELIXX_TYPE
    estilo = ttk.Style(janela)
    estilo.theme_use("clam")
    estilo.configure(".", background=cores["bg_base"],
                     foreground=cores["text_primary"],
                     fieldbackground=cores["surface"],
                     font=(tipos["body"][0], tipos["body"][1]))
    estilo.configure("TFrame", background=cores["bg_base"])
    estilo.configure("TLabel", background=cores["bg_base"],
                     foreground=cores["text_primary"],
                     font=(tipos["body"][0],
                           tipos["body"][1]))
    estilo.configure("Header.TLabel",
                     font=(tipos["panel_title"][0],
                           tipos["panel_title"][1], "bold"),
                     foreground=cores["text_primary"])
    estilo.configure("TButton",
                     background=cores["surface_elevated"],
                     foreground=cores["text_primary"],
                     borderwidth=ELIXX_BORDERS["fina"],
                     relief="flat", padding=(8, 4))
    estilo.map("TButton",
               background=[("active",
                            cores["surface_active"]),
                           ("pressed", cores["selection"]),
                           ("disabled", cores["surface"])],
               foreground=[("disabled", cores["text_muted"])])
    estilo.configure("Accent.TButton",
                     background=cores["accent"],
                     foreground="#ffffff")
    estilo.map("Accent.TButton",
               background=[("active", cores["accent_hover"]),
                           ("pressed", cores["accent_active"])])
    estilo.configure("Danger.TButton",
                     background=cores["danger"],
                     foreground="#ffffff")
    estilo.configure("TEntry", fieldbackground=cores["surface"],
                     foreground=cores["text_primary"],
                     borderwidth=ELIXX_BORDERS["fina"])
    estilo.configure("TNotebook", background=cores["bg_base"],
                     borderwidth=0)
    estilo.configure("TNotebook.Tab",
                     background=cores["surface"],
                     foreground=cores["text_muted"],
                     padding=(10, 4))
    estilo.map("TNotebook.Tab",
               background=[("selected",
                            cores["surface_elevated"])],
               foreground=[("selected",
                            cores["text_primary"])])
    estilo.configure("Horizontal.TProgressbar",
                     background=cores["accent"])
    estilo.configure("Caption.TLabel",
                     background=cores["bg_base"],
                     foreground=cores["text_muted"],
                     font=(tipos["secondary"][0],
                           tipos["secondary"][1]))
    estilo.configure("Toolbar.TButton",
                     background=cores["surface"],
                     foreground=cores["text_primary"],
                     borderwidth=ELIXX_BORDERS["fina"],
                     relief="flat", padding=(6, 2),
                     font=(tipos["body"][0],
                           tipos["body"][1]))
    estilo.map("Toolbar.TButton",
               background=[("active",
                            cores["surface_active"]),
                           ("pressed", cores["selection"])])
    estilo.configure("Active.Toolbar.TButton",
                     background=cores["accent"],
                     foreground="#ffffff",
                     borderwidth=ELIXX_BORDERS["fina"],
                     relief="flat", padding=(6, 2),
                     font=(tipos["body"][0],
                           tipos["body"][1]))
    estilo.map("Active.Toolbar.TButton",
               background=[("active", cores["accent_hover"])])
    estilo.configure("TabActive.TButton",
                     background=cores["surface_active"],
                     foreground=cores["text_primary"],
                     borderwidth=ELIXX_BORDERS["fina"],
                     relief="flat", padding=(8, 3))
    estilo.map("TabActive.TButton",
               background=[("active",
                            cores["surface_elevated"])])
    try:
        janela.configure(background=cores["bg_base"])
    except Exception:
        pass
    return {"tema": "dark-premium",
            "cores": len(ELIXX_DS3)}


def estilizar_tk(widget, somente_leitura: bool = False):
    """Aplica o dark em Listbox/Text/Canvas/OptionMenu/Entry.

    Sem display não há widget; com widget, só `config` (nunca
    cria/destrói). Retorna o próprio widget (encadeável).
    """
    cores, tipos = ELIXX_DS3, ELIXX_TYPE
    try:
        classe = type(widget).__name__
    except Exception:
        raise ErroELiXX("Tema: widget inválido.")
    base = {"highlightthickness": 0, "borderwidth": 0,
            "relief": "flat"}
    try:
        if classe == "Listbox":
            widget.config(background=cores["surface"],
                          foreground=cores["text_primary"],
                          selectbackground=cores["accent"],
                          selectforeground="#ffffff",
                          activestyle="none",
                          font=(tipos["body"][0],
                                tipos["body"][1]), **base)
        elif classe == "Text":
            widget.config(background=cores["surface"],
                          foreground=cores["text_primary"],
                          selectbackground=cores["selection"],
                          selectforeground=cores["text_primary"],
                          insertbackground=cores["text_primary"],
                          font=(tipos["monospace"][0],
                                tipos["monospace"][1]), **base)
            try:
                widget.config(state="disabled" if somente_leitura
                              else "normal")
            except Exception:
                pass
        elif classe == "Canvas":
            widget.config(background=cores["bg_base"],
                          **base)
        elif classe == "OptionMenu":
            widget.config(background=cores["surface_elevated"],
                          foreground=cores["text_primary"],
                          activebackground=cores[
                              "surface_active"],
                          activeforeground=cores["text_primary"],
                          font=(tipos["body"][0],
                                tipos["body"][1]), **base)
            try:
                widget["menu"].config(
                    background=cores["surface"],
                    foreground=cores["text_primary"],
                    activebackground=cores["selection"],
                    activeforeground=cores["text_primary"],
                    borderwidth=0)
            except Exception:
                pass
        elif classe == "Entry":
            widget.config(background=cores["surface"],
                          foreground=cores["text_primary"],
                          insertbackground=cores[
                              "text_primary"],
                          font=(tipos["body"][0],
                                tipos["body"][1]), **base)
        else:
            raise ErroELiXX(f"Tema: widget {classe} sem estilo.")
    except ErroELiXX:
        raise
    except Exception as exc:
        raise ErroELiXX(f"Tema: falha ao estilizar ({exc}).")
    return widget


def titulo_escuro(janela) -> dict:
    """Titlebar escura no Windows (DWM; fora dele, no-op honesto)."""
    try:
        import ctypes
        import sys
    except ImportError:
        return {"ok": False, "motivo": "sem ctypes"}
    if not sys.platform.startswith("win"):
        return {"ok": False, "motivo": "sem DWM fora do Windows"}
    try:
        hwnd = janela.winfo_id()
        valor = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(valor),
            ctypes.sizeof(valor))
        return {"ok": True, "motivo": "DWM dark"}
    except Exception as exc:
        return {"ok": False,
                "motivo": str(exc)[:120]}
