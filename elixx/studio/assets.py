"""Assets do Studio (F25) — inventário sobre a F07 (sem duplicar).

Varredura contida no workspace; tipo via `detectar_tipo` (F07);
tamanho lido com teto (sem carregar bytes pesados); validação de
extensão e existência. Preview de conteúdo: só metadados nesta fase.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["Asset", "GerenciadorAssets", "CATEGORIAS", "EXTENSOES"]

CATEGORIAS = ("imagens", "sons", "videos", "personagens", "outros")
"""Categorias do painel de assets."""

EXTENSOES = {
    ".png": "imagens", ".jpg": "imagens", ".jpeg": "imagens",
    ".svg": "imagens", ".wav": "sons", ".mp3": "sons",
    ".mp4": "videos", ".webm": "videos", ".elixx": "personagens",
    ".fj": "personagens",
}
"""Extensão → categoria (desconhecida = outros)."""

MAX_BYTES_ASSET = 200 * 1024 * 1024
"""Teto de tamanho aceito (200MB; acima = erro claro)."""


class Asset:
    """Um arquivo de asset (metadados; sem carregar conteúdo)."""

    def __init__(self, nome: str, relativo: str, categoria: str = "",
                 tamanho: int = 0) -> None:
        if not isinstance(nome, str) or not nome.strip():
            raise ErroELiXX("Asset precisa de nome.")
        self.nome = nome.strip()
        self.relativo = str(relativo).replace("\\", "/")
        cat = str(categoria).strip() or "outros"
        if cat not in CATEGORIAS:
            raise ErroELiXX(f'Asset: categoria "{cat}" inválida.')
        self.categoria = cat
        try:
            tam = int(tamanho)
        except (TypeError, ValueError):
            raise ErroELiXX("Asset: tamanho inteiro.")
        if tam < 0 or tam > MAX_BYTES_ASSET:
            raise ErroELiXX(f'Asset "{self.nome}": tamanho inválido.')
        self.tamanho = tam

    def to_dict(self) -> dict:
        return {"nome": self.nome, "relativo": self.relativo,
                "categoria": self.categoria, "tamanho": self.tamanho}

    def __repr__(self) -> str:
        return f"Asset({self.categoria} {self.nome})"


class GerenciadorAssets:
    """Painel de assets (varredura lazy por pasta)."""

    def __init__(self, workspace) -> None:
        from .workspace import Workspace

        if not isinstance(workspace, Workspace):
            raise ErroELiXX("GerenciadorAssets espera Workspace.")
        self.workspace = workspace

    def varrer(self, relativo: str = "assets") -> list[Asset]:
        """Lista assets (metadados; sem ler bytes)."""
        if not self.workspace.aberto:
            return []
        base = self.workspace.resolver(relativo)
        if not base.is_dir():
            return []
        saidas = []
        for item in sorted(base.rglob("*"), key=lambda p: str(p)):
            if not item.is_file() or item.name == "__pycache__":
                continue
            try:
                rel = item.resolve().relative_to(
                    self.workspace.raiz)
            except ValueError:
                continue
            categoria = EXTENSOES.get(item.suffix.lower(), "outros")
            try:
                tamanho = item.stat().st_size
            except OSError:
                continue
            if tamanho > MAX_BYTES_ASSET:
                continue
            saidas.append(Asset(item.name, str(rel).replace("\\",
                                                            "/"),
                                categoria, tamanho))
        return saidas

    def validar(self, relativo: str) -> dict:
        """Existe + tamanho + tipo F07 (sem executar nada)."""
        caminho = self.workspace.resolver(relativo)
        if not caminho.is_file():
            return {"valido": False, "codigo": "ausente",
                    "motivo": f'Asset "{relativo}" não encontrado.'}
        try:
            tamanho = caminho.stat().st_size
        except OSError as exc:
            return {"valido": False, "codigo": "ilegivel",
                    "motivo": f'Asset "{relativo}" ilegível: {exc}.'}
        if tamanho > MAX_BYTES_ASSET:
            return {"valido": False, "codigo": "gigante",
                    "motivo": f'Asset "{relativo}" além do teto.'}
        try:
            from ..multimidia.recursos import detectar_tipo

            tipo = detectar_tipo(str(caminho))
        except Exception:
            tipo = "desconhecido"
        return {"valido": True, "codigo": "ok",
                "motivo": "Asset válido.",
                "tamanho": tamanho, "tipo": tipo}

    def por_categoria(self, relativo: str = "assets") -> dict:
        grupos: dict[str, list] = {c: [] for c in CATEGORIAS}
        for asset in self.varrer(relativo):
            grupos[asset.categoria].append(asset.nome)
        return grupos

    def __repr__(self) -> str:
        return "GerenciadorAssets()"
