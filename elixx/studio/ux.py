"""UX headless do Studio 2.0 (Fase 38) — modelos sem Tk.

Abas de editor, destaque via lexer oficial, árvore formatada,
resumo do agent, zoom de preview (estado) e seções do inspector.
Tudo testável sem display; Tk só espelha.
"""
from __future__ import annotations

from ..erros import ErroELiXX
from .workspace_ui import destacar_lexico

__all__ = [
    "ZOOM_NIVEIS", "AbasEditor", "SecaoInspector",
    "cabecalho_arquivo", "destacar_semantico",
    "formatar_arvore", "resumo_agente",
]

ZOOM_NIVEIS = (50, 75, 100, 125, 150, "Ajustar")
"""Níveis do controle de zoom (estado visual honesto)."""


def destacar_semantico(texto: str) -> list[tuple]:
    """Lexer oficial → [(ini, fim, classe)] (fallback lexical).

    Classes: palavra (PALAVRA), nome (IDENT), string (STRING),
    numero (NUMERO+). Erro léxico = fallback sem exceção.
    """
    if not isinstance(texto, str):
        raise ErroELiXX("Destaque precisa de texto.")
    try:
        from ..compilador.lexer import tokenizar

        tokens = tokenizar(texto)
    except Exception:
        return destacar_lexico(texto)
    linhas = texto.splitlines(keepends=True)
    inicios = [0]
    for linha in linhas:
        inicios.append(inicios[-1] + len(linha))
    marcas = []
    for tok in tokens:
        if tok.tipo == "EOF":
            continue
        classe = {"PALAVRA": "palavra", "STRING": "string",
                  "NUMERO": "numero"}.get(tok.tipo, "nome")
        try:
            base = inicios[tok.linha - 1]
        except IndexError:
            continue
        candidatos = [str(tok.valor)]
        try:
            numero = float(tok.valor)
            if numero.is_integer():
                candidatos.append(str(int(numero)))
        except (TypeError, ValueError):
            pass
        ini = -1
        fatia = ""
        for tentativa in candidatos:
            if texto[base + max(0, tok.coluna - 1):
                     base + max(0, tok.coluna - 1)
                     + len(tentativa)] == tentativa:
                ini = base + max(0, tok.coluna - 1)
                fatia = tentativa
                break
        if ini < 0:
            limite = base + len(linhas[tok.linha - 1]) \
                if tok.linha - 1 < len(linhas) else len(texto)
            for tentativa in candidatos:
                achou = texto.find(tentativa, base, limite)
                if achou >= 0:
                    ini, fatia = achou, tentativa
                    break
        if ini < 0:
            continue
        marcas.append((ini, ini + len(fatia), classe))
    marcas.sort()
    return marcas


def cabecalho_arquivo(caminho: str, dirty: bool) -> str:
    """`main.elixx ●` (● = não salvo) ou `main.elixx`."""
    nome = str(caminho).split("/")[-1].split("\\")[-1]
    if not nome:
        raise ErroELiXX("Cabeçalho precisa de caminho.")
    return f"{nome} ●" if dirty else nome


class AbasEditor:
    """Abas sobre GerenciadorDocumentos (sem duplicar docs)."""

    def __init__(self, gerenciador) -> None:
        from .documento import GerenciadorDocumentos

        if not isinstance(gerenciador, GerenciadorDocumentos):
            raise ErroELiXX("Abas esperam GerenciadorDocumentos.")
        self.gerenciador = gerenciador
        self.ativa: str | None = None

    def abrir(self, caminho: str, texto: str = ""):
        doc = self.gerenciador.abrir(caminho, texto)
        self.ativa = caminho
        return doc

    def trocar(self, caminho: str):
        self.gerenciador.obter(caminho)
        self.ativa = caminho
        return caminho

    def fechar(self, caminho: str):
        self.gerenciador.fechar(caminho)
        if self.ativa == caminho:
            abertos = self.gerenciador.abertos()
            self.ativa = abertos[-1] if abertos else None
        return self.ativa

    def lista(self) -> list[dict]:
        return [{"caminho": c,
                 "cabecalho": cabecalho_arquivo(
                     c, self.gerenciador.obter(c).dirty),
                 "ativa": c == self.ativa}
                for c in self.gerenciador.abertos()]

    def __repr__(self) -> str:
        return f"AbasEditor({len(self.gerenciador.abertos())})"


class SecaoInspector:
    """Seção ▾/▸ com campos reais (estado serializável)."""

    def __init__(self, titulo: str, campos: dict | None = None,
                 aberta: bool = True) -> None:
        if not str(titulo).strip():
            raise ErroELiXX("Seção precisa de título.")
        self.titulo = str(titulo)
        self.campos = dict(campos or {})
        self.aberta = bool(aberta)

    def alternar(self) -> bool:
        self.aberta = not self.aberta
        return self.aberta

    def to_dict(self) -> dict:
        return {"titulo": self.titulo,
                "campos": dict(self.campos),
                "aberta": self.aberta}

    def __repr__(self) -> str:
        marca = "▾" if self.aberta else "▸"
        return f"SecaoInspector({marca} {self.titulo})"


_ICONES_TIPO = {
    "pasta": "▾", "arquivo": "•", "personagem": "◆",
    "cena": "▣", "asset": "▤",
}
"""Ícones textuais por tipo (sem emoji, sem biblioteca)."""


def formatar_arvore(nos: list, atual: str | None = None,
                    sujos: list | None = None) -> list[str]:
    """Nós → linhas `[ícone] nome ●` (indentação por categoria).

    Categorias (arquivo/personagem/cena/asset) viram grupos com
    indentação; arquivo atual e dirty marcados. Só dados de entrada.
    """
    sujos_txt = set(sujos or [])
    grupos: dict[str, list] = {}
    for no in nos or []:
        if not isinstance(no, dict):
            raise ErroELiXX("Árvore: nós em dicts.")
        grupos.setdefault(str(no.get("tipo", "arquivo")),
                          []).append(no)
    ordem = ["arquivo", "cena", "personagem", "asset"]
    extras = sorted(set(grupos) - set(ordem))
    linhas = []
    for tipo in ordem + extras:
        itens = sorted(grupos.get(tipo, []),
                       key=lambda n: str(n.get("nome", "")))
        if not itens:
            continue
        icone = _ICONES_TIPO.get(tipo, "•")
        for item in itens:
            nome = str(item.get("nome", "?"))
            caminho = str(item.get("caminho", nome))
            marcas = ""
            if caminho == (atual or ""):
                marcas += " →"
            if caminho in sujos_txt:
                marcas += " ●"
            linhas.append(f"  {icone} {nome}{marcas}")
    return linhas


def resumo_agente(sessao) -> dict:
    """Header/status/conversa/contexto/tools/plano (só leitura)."""
    provider = getattr(sessao, "provider", None)
    return {
        "header": "ELiXX AGENT",
        "provider": getattr(provider, "nome", "MOCK") +
        " / DETERMINISTIC",
        "status": getattr(sessao, "estado", "IDLE"),
        "mensagens": len(getattr(sessao, "mensagens", [])),
        "tarefa": getattr(sessao, "tarefa", ""),
    }
