"""Editor e diagnósticos do Studio (F25).

EditorCodigo opera sobre DocumentoELiXX (números de linha, cursor,
seleção, localizar/substituir). Diagnósticos reusam o
parser/compilador oficial (nunca regex-gambiarra): ELX001 sintaxe,
ELX002 semântica, ELX000 interno.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["Diagnostic", "EditorCodigo", "diagnosticar_texto"]


class Diagnostic:
    """Achado estruturado (severidade, mensagem, arquivo, posição)."""

    def __init__(self, severidade: str, mensagem: str,
                 arquivo: str = "", linha: int | None = None,
                 coluna: int | None = None,
                 codigo: str = "ELX000") -> None:
        sev = str(severidade).strip().lower()
        if sev not in ("info", "warning", "error"):
            raise ErroELiXX(f'Diagnostic: severidade "{severidade}" '
                            "inválida.")
        self.severidade = sev
        self.mensagem = str(mensagem)
        self.arquivo = str(arquivo)
        self.linha = linha
        self.coluna = coluna
        self.codigo = str(codigo)

    def to_dict(self) -> dict:
        return {"severidade": self.severidade,
                "mensagem": self.mensagem, "arquivo": self.arquivo,
                "linha": self.linha, "coluna": self.coluna,
                "codigo": self.codigo}

    def __repr__(self) -> str:
        pos = ""
        if self.linha is not None:
            pos = f":{self.linha}"
            if self.coluna is not None:
                pos += f":{self.coluna}"
        return f"[{self.codigo}] {self.arquivo}{pos} {self.mensagem}"


def diagnosticar_texto(texto: str, arquivo: str = "") -> list[Diagnostic]:
    """Compilador oficial → diagnósticos (sem executar nada)."""
    if not isinstance(texto, str):
        raise ErroELiXX("Diagnosticar precisa de texto.")
    if not texto.strip():
        return [Diagnostic("info", "Arquivo vazio.", arquivo,
                           codigo="ELX000")]
    try:
        from ..compilador.lexer import tokenizar
        from ..compilador.parser import Parser
        from ..compilador.semantica import validar

        prog = Parser(tokenizar(texto)).parse()
        validar(prog)
        return [Diagnostic("info", "Sem erros.", arquivo,
                           codigo="ELX000")]
    except Exception as exc:  # pipeline oficial; mensagem amigável
        from ..erros import ErroLexico, ErroSemantico, ErroSintatico

        linha = getattr(exc, "linha", None)
        coluna = getattr(exc, "coluna", None)
        if isinstance(exc, (ErroLexico, ErroSintatico)):
            codigo = "ELX001"
        elif isinstance(exc, ErroSemantico):
            codigo = "ELX002"
        else:
            codigo = "ELX000"
        detalhe = getattr(exc, "mensagem", None) or str(exc)
        sugestao = getattr(exc, "sugestao", None)
        mensagem = str(detalhe).split("\n")[0][:300]
        if sugestao:
            mensagem += f" Sugestão: {sugestao}"
        return [Diagnostic("error", mensagem, arquivo, linha=linha,
                           coluna=coluna, codigo=codigo)]


class EditorCodigo:
    """Editor headless sobre um documento (undo/redo/busca)."""

    def __init__(self, documento) -> None:
        from .documento import DocumentoELiXX

        if not isinstance(documento, DocumentoELiXX):
            raise ErroELiXX("EditorCodigo espera DocumentoELiXX.")
        self.documento = documento

    # ----- delegação direta -----

    def definir_texto(self, texto: str) -> None:
        self.documento.definir_texto(texto)

    def inserir(self, trecho: str, linha: int = 1,
                coluna: int = 1) -> None:
        self.documento.inserir(trecho, linha, coluna)

    def desfazer(self) -> bool:
        return self.documento.desfazer()

    def refazer(self) -> bool:
        return self.documento.refazer()

    def mover_cursor(self, linha: int, coluna: int = 1) -> None:
        self.documento.mover_cursor(linha, coluna)

    def numero_linhas(self) -> int:
        return self.documento.linhas()

    # ----- busca -----

    def localizar(self, termo: str) -> list[tuple]:
        """[(linha, coluna)] de cada ocorrência (1-based)."""
        if not termo:
            raise ErroELiXX("Localizar precisa de termo.")
        achados = []
        for i, linha_txt in enumerate(
                self.documento.texto.split("\n"), start=1):
            inicio = 0
            while True:
                pos = linha_txt.find(termo, inicio)
                if pos < 0:
                    break
                achados.append((i, pos + 1))
                inicio = pos + len(termo)
        return achados

    def substituir(self, antigo: str, novo: str,
                   todas: bool = True) -> int:
        """Substitui e retorna o nº de trocas (0 = nada feito)."""
        if not antigo:
            raise ErroELiXX("Substituir precisa do termo antigo.")
        texto = self.documento.texto
        vezes = texto.count(antigo)
        if vezes == 0:
            return 0
        if todas:
            self.documento.definir_texto(texto.replace(antigo, novo))
            return vezes
        self.documento.definir_texto(texto.replace(antigo, novo, 1))
        return 1

    def diagnosticar(self) -> list[Diagnostic]:
        return diagnosticar_texto(self.documento.texto,
                                  self.documento.caminho)

    def __repr__(self) -> str:
        return f"EditorCodigo({self.documento.caminho})"
