"""Preview do Studio (F25) — runtime real, duas frentes.

HeadlessPreview: valida + compila + executa o pipeline oficial sem
janela (logs estruturados). TkPreview: mesma execução com janela Tk
(import preguiçoso; `disponivel()` diz se há display). Abrir arquivo
NUNCA executa; só `executar()` roda, pelo pipeline oficial.
"""
from __future__ import annotations

from ..erros import ErroELiXX
from .editor import Diagnostic, diagnosticar_texto

__all__ = ["PreviewResultado", "StudioPreview", "HeadlessPreview",
           "TkPreview"]


class PreviewResultado:
    """Resultado de uma execução de preview (só dados + resumo)."""

    def __init__(self, sucesso: bool, entrada: str,
                 diagnosticos: list | None = None,
                 resumo: dict | None = None) -> None:
        self.sucesso = bool(sucesso)
        self.entrada = str(entrada)
        self.diagnosticos = list(diagnosticos or [])
        self.resumo = dict(resumo or {})

    def erros(self) -> list[Diagnostic]:
        return [d for d in self.diagnosticos
                if d.severidade == "error"]

    def to_dict(self) -> dict:
        return {"sucesso": self.sucesso, "entrada": self.entrada,
                "diagnosticos": [d.to_dict()
                                 for d in self.diagnosticos],
                "resumo": dict(self.resumo)}

    def __repr__(self) -> str:
        return (f"PreviewResultado(sucesso={self.sucesso} "
                f"{self.entrada})")


class StudioPreview:
    """Base: ciclo executar → parar → recarregar (sem janela)."""

    def __init__(self) -> None:
        self.rodando = False
        self.ultimo: PreviewResultado | None = None

    @property
    def nome(self) -> str:
        return type(self).__name__

    def executar(self, texto: str, entrada: str = "main.elixx",
                 ) -> PreviewResultado:
        raise ErroELiXX("Preview não implementa executar().")

    def parar(self) -> None:
        self.rodando = False

    def recarregar(self, texto: str,
                   entrada: str = "main.elixx") -> PreviewResultado:
        self.parar()
        return self.executar(texto, entrada)

    def _pipeline(self, texto: str,
                  entrada: str) -> PreviewResultado:
        """Pipeline oficial: diagnosticar → parse → executar → cena."""
        diags = diagnosticar_texto(texto, entrada)
        erros = [d for d in diags if d.severidade == "error"]
        if erros:
            return PreviewResultado(False, entrada,
                                    diagnosticos=diags)
        try:
            from ..compilador.componentes import expandir_componentes
            from ..compilador.lexer import tokenizar
            from ..compilador.parser import Parser
            from ..compilador.semantica import validar
            from ..runtime.nucleo import Executor
            from ..visual.cena import ConstrutorCena

            prog = Parser(tokenizar(texto)).parse()
            expandir_componentes(prog)
            validar(prog)
            cena = ConstrutorCena().de_objetos(
                Executor().executar(prog, []).objetos)
            total_nos = 0
            pilha = list(getattr(cena, "janelas", []))
            while pilha:
                no = pilha.pop()
                total_nos += 1
                pilha.extend(getattr(no, "filhos", []))
            resumo = {"janelas": len(getattr(cena, "janelas", [])),
                      "nos": total_nos}
            try:
                from ..visual.personagem import vincular_personagens

                resumo["personagens"] = sorted(
                    vincular_personagens(cena))
            except ErroELiXX:
                resumo["personagens"] = []
            self.rodando = True
            return PreviewResultado(True, entrada,
                                    diagnosticos=diags, resumo=resumo)
        except Exception as exc:
            linha = getattr(exc, "linha", None)
            coluna = getattr(exc, "coluna", None)
            detalhe = (getattr(exc, "mensagem", None)
                       or str(exc)).split("\n")[0][:300]
            diags = diags + [Diagnostic(
                "error", f"Falha no preview: {detalhe}", entrada,
                linha=linha, coluna=coluna, codigo="ELX000")]
            return PreviewResultado(False, entrada,
                                    diagnosticos=diags)


class HeadlessPreview(StudioPreview):
    """Preview sem janela (testes, CI, modo sem display)."""

    def executar(self, texto: str, entrada: str = "main.elixx",
                 ) -> PreviewResultado:
        if not isinstance(texto, str):
            raise ErroELiXX("Preview precisa de texto.")
        self.ultimo = self._pipeline(texto, entrada)
        if not self.ultimo.sucesso:
            self.rodando = False
        return self.ultimo


class TkPreview(StudioPreview):
    """Preview com janela Tk (import preguiçoso; sem display = erro)."""

    def __init__(self) -> None:
        super().__init__()
        self.janela = None

    @staticmethod
    def disponivel() -> bool:
        try:
            import tkinter as _tk

            raiz = _tk.Tk()
            raiz.withdraw()
            raiz.destroy()
            return True
        except Exception:
            return False

    def executar(self, texto: str, entrada: str = "main.elixx",
                 ) -> PreviewResultado:
        try:
            import tkinter as _tk
        except ImportError:
            raise ErroELiXX("Tk indisponível neste ambiente.")
        self.ultimo = self._pipeline(texto, entrada)
        if not self.ultimo.sucesso:
            self.rodando = False
            return self.ultimo
        try:
            self.janela = _tk.Tk()
            self.janela.title(f"ELiXX Preview — {entrada}")
            resumo = self.ultimo.resumo
            _tk.Label(
                self.janela,
                text=f"janelas={resumo.get('janelas', 0)} "
                     f"nos={resumo.get('nos', 0)}").pack()
            self.janela.update()
        except Exception as exc:
            self.janela = None
            self.rodando = False
            raise ErroELiXX(f"Preview Tk sem display: {exc}.")
        return self.ultimo

    def parar(self) -> None:
        if self.janela is not None:
            try:
                self.janela.destroy()
            except Exception:
                pass
            self.janela = None
        self.rodando = False
