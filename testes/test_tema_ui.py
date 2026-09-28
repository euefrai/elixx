"""Tema da interface (P1-P4 da correcao visual) — sem display.

estilizar_tk via stubs duck-typed; titulo_escuro nunca levanta;
varredura garante nenhum branco fixo e identificadores F38.
"""

import pytest

from elixx.erros import ErroELiXX
from elixx.studio.tema import estilizar_tk, titulo_escuro


class _Base:
    def __init__(self):
        self.cfg = {}

    def config(self, **kw):
        self.cfg.update(kw)

    def __setitem__(self, chave, valor):
        self.cfg[chave] = valor


class Listbox(_Base):
    pass


class Text(_Base):
    pass


class Canvas(_Base):
    pass


class Entry(_Base):
    pass


class _Menu(_Base):
    pass


class OptionMenu(_Base):
    def __init__(self):
        super().__init__()
        self._menu = _Menu()

    def __getitem__(self, chave):
        assert chave == "menu"
        return self._menu


class Botao(_Base):
    pass


def test_listbox_dark():
    from elixx.studio import ELIXX_COLORS

    w = Listbox()
    assert estilizar_tk(w) is w
    assert w.cfg["background"] == ELIXX_COLORS["surface"]
    assert w.cfg["foreground"] == ELIXX_COLORS["text"]
    assert w.cfg["selectbackground"] == \
        ELIXX_COLORS["selection"]
    assert w.cfg["highlightthickness"] == 0


def test_text_code_font():
    from elixx.studio import ELIXX_COLORS, ELIXX_FONTS

    w = Text()
    estilizar_tk(w)
    assert w.cfg["background"] == ELIXX_COLORS["surface"]
    assert w.cfg["insertbackground"] == ELIXX_COLORS["text"]
    assert w.cfg["font"][0] == ELIXX_FONTS["code"][0]


def test_canvas_surface():
    from elixx.studio import ELIXX_COLORS

    w = Canvas()
    estilizar_tk(w)
    assert w.cfg["background"] == ELIXX_COLORS["surface"]


def test_optionmenu_com_menu():
    from elixx.studio import ELIXX_COLORS

    w = OptionMenu()
    estilizar_tk(w)
    assert w.cfg["background"] == ELIXX_COLORS["surface_alt"]
    assert w._menu.cfg["background"] == ELIXX_COLORS["surface"]


def test_entry_dark():
    from elixx.studio import ELIXX_COLORS

    w = Entry()
    estilizar_tk(w)
    assert w.cfg["background"] == ELIXX_COLORS["surface"]


def test_widget_desconhecido():
    with pytest.raises(ErroELiXX):
        estilizar_tk(Botao())


def test_widget_invalido():
    with pytest.raises(ErroELiXX):
        estilizar_tk(None)


def test_titulo_escuro_nunca_levanta():
    class _Jan:
        def winfo_id(self):
            raise RuntimeError("sem display")

    saida = titulo_escuro(_Jan())
    assert set(saida) == {"ok", "motivo"}
    assert saida["ok"] is False


def test_sem_branco_fixo_na_ui():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert 'background="white"' not in fonte
    assert '"white"' not in fonte
    assert '"lightblue"' not in fonte
    assert "estilizar_tk" in fonte


def test_identificadores_f38_presentes():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for nome in ("rotulo_zoom", "OptionMenu",
                 "quadro_viewport", "tela_cena",
                 "rotulo_prev_status", "lista_prev"):
        assert nome in fonte, nome


def test_toolbar_sem_duplicacao():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    assert fonte.count('text="Executar"') <= 1


def test_caption_toolbar_styles():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/tema.py").read_text(
        encoding="utf-8")
    assert "Caption.TLabel" in fonte
    assert "Toolbar.TButton" in fonte
