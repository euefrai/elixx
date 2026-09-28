"""Asset runtime de personagens (Fase 41) — imagem -> personagem.

Cobre: AssetVisual (metadados + dimensoes stdlib), CharacterAsset
(convecao personagens/<nome>/ + 4 vistas + aliases + diagnostico
honesto), CharacterView/Layer/Part/Rig (abstracoes; sem IA, sem
bones: metodo "unidade"), personagem-unidade sobre Character F12,
animacoes sobre DefinicaoAnimacao F11, palco sobre RenderizadorTk.

Sem Studio; sem parser/modelo/renderer/motor novos; sem rede.
Reutiliza F07 (tipos), F10 (Transform), F11 (motor), F12
(Character), F16/F17 (sintese), F21 (Bounds2D).
"""

from __future__ import annotations

import math
import struct

from ..erros import ErroELiXX

__all__ = [
    "VISTAS",
    "ALIASES_VISTA",
    "EXTENSOES_IMAGEM",
    "MAX_BYTES_ASSET",
    "AssetVisual",
    "CharacterAsset",
    "CharacterView",
    "CharacterLayer",
    "CharacterPart",
    "CharacterRig",
    "resolver_vista",
    "criar_personagem_unidade",
    "animacao_respiracao",
    "animacao_inclinacao",
    "animacao_deslocamento",
    "abrir_palco",
]

VISTAS = ("frente", "tras", "lado_direito", "lado_esquerdo")
"""Quatro vistas de uma animacao completa de personagem."""

ALIASES_VISTA = {
    "frente": "frente",
    "tras": "tras",
    "trás": "tras",
    "costas": "tras",
    "lado_direito": "lado_direito",
    "direita": "lado_direito",
    "lado_esquerdo": "lado_esquerdo",
    "esquerda": "lado_esquerdo",
}
"""Aliases documentados (sem ambiguidade; 'lado' sozinho e erro)."""

EXTENSOES_IMAGEM = (".png", ".gif", ".jpg", ".jpeg")
"""PNG/GIF nativos; JPEG via Pillow quando disponivel."""

MAX_BYTES_ASSET = 20 * 1024 * 1024
"""Teto de leitura (20MB; sem copias gigantes)."""


def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f"Asset: {o_que} numerico.")
    if not math.isfinite(numero):
        raise ErroELiXX(f"Asset: {o_que} finito.")
    return numero


def _rel_seguro(relativo: str) -> str:
    texto = str(relativo).strip().replace("\\", "/")
    if not texto or len(texto) > 500:
        raise ErroELiXX("Asset: caminho curto e nao vazio.")
    if texto.startswith("/") or ".." in texto.split("/"):
        raise ErroELiXX("Asset: caminho contido na base.")
    for ch in texto:
        if ch == "\x00" or (ord(ch) < 32 and ch != "\t"):
            raise ErroELiXX("Asset: caminho sem controle.")
    return texto


def resolver_vista(nome: str) -> str:
    """Alias -> vista canonica (desconhecido e erro honesto)."""
    chave = str(nome).strip().lower()
    if chave not in ALIASES_VISTA:
        raise ErroELiXX(
            f'Asset: vista "{nome}" desconhecida '
            f"({', '.join(sorted(set(ALIASES_VISTA)))}, "
            "mais lado_direito/lado_esquerdo).")
    return ALIASES_VISTA[chave]


def _dimensoes_png(dados: bytes) -> tuple | None:
    if len(dados) < 24 or dados[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        largura, altura = struct.unpack(">II", dados[16:24])
    except struct.error:
        return None
    if not (1 <= largura <= 16384 and 1 <= altura <= 16384):
        return None
    return (largura, altura)


def _dimensoes_gif(dados: bytes) -> tuple | None:
    if len(dados) < 10 or dados[:6] not in (b"GIF87a",
                                            b"GIF89a"):
        return None
    try:
        largura, altura = struct.unpack("<HH", dados[6:10])
    except struct.error:
        return None
    if not (1 <= largura <= 16384 and 1 <= altura <= 16384):
        return None
    return (largura, altura)


def _dimensoes_jpeg(dados: bytes) -> tuple | None:
    if len(dados) < 4 or dados[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 4 < len(dados):
        if dados[pos] != 0xFF:
            pos += 1
            continue
        marcador = dados[pos + 1]
        if marcador in (0xC0, 0xC1, 0xC2):
            try:
                altura, largura = struct.unpack(
                    ">HH", dados[pos + 5:pos + 9])
            except struct.error:
                return None
            if 1 <= largura <= 16384 and 1 <= altura <= 16384:
                return (largura, altura)
            return None
        if marcador in (0xD8, 0xD9) or 0xD0 <= marcador <= 0xD7:
            pos += 2
            continue
        try:
            tamanho = struct.unpack(">H", dados[pos + 2:pos + 4])[0]
        except struct.error:
            return None
        if tamanho < 2:
            return None
        pos += 2 + tamanho
    return None


def dimensoes_imagem(dados: bytes, formato: str) -> tuple:
    """(largura, altura) via stdlib; Pillow so como reserva."""
    if not isinstance(dados, (bytes, bytearray)) or not dados:
        raise ErroELiXX("Asset: bytes de imagem vazios.")
    if len(dados) > MAX_BYTES_ASSET:
        raise ErroELiXX("Asset: imagem excede 20MB.")
    formato_txt = str(formato).lower()
    leitor = {"png": _dimensoes_png, "gif": _dimensoes_gif,
              "jpg": _dimensoes_jpeg,
              "jpeg": _dimensoes_jpeg}.get(formato_txt)
    if leitor is None:
        raise ErroELiXX(f'Asset: formato "{formato}" '
                        "sem leitor.")
    achado = leitor(bytes(dados))
    if achado is not None:
        return achado
    try:
        import io

        from PIL import Image
    except ImportError:
        raise ErroELiXX("Asset: imagem ilegivel "
                        "(cabeçalho invalido).")
    try:
        with Image.open(io.BytesIO(bytes(dados))) as img:
            largura, altura = img.size
    except Exception:
        raise ErroELiXX("Asset: imagem ilegivel.")
    if not (1 <= largura <= 16384 and 1 <= altura <= 16384):
        raise ErroELiXX("Asset: dimensoes absurdas.")
    return (int(largura), int(altura))


class AssetVisual:
    """Imagem de projeto (metadados + leitura tardia e limitada)."""

    def __init__(self, caminho: str, base_dir: str = ".",
                 permitir_absoluto: bool = False) -> None:
        from pathlib import Path

        rel = _rel_seguro(caminho)
        sufixo = Path(rel).suffix.lower()
        if sufixo not in EXTENSOES_IMAGEM:
            raise ErroELiXX(
                f'Asset: extensao "{sufixo}" invalida '
                f"({', '.join(EXTENSOES_IMAGEM)}).")
        base = Path(str(base_dir) or ".")
        alvo = (base / rel).resolve()
        try:
            base_resolvida = base.resolve()
            alvo.relative_to(base_resolvida)
        except ValueError:
            raise ErroELiXX("Asset: fora da base.")
        if alvo.is_absolute() and not permitir_absoluto \
                and Path(caminho).is_absolute():
            raise ErroELiXX("Asset: absoluto proibido "
                            "(use relativo a base).")
        self.caminho = rel
        self.base_dir = str(base)
        self.formato = sufixo.lstrip(".")
        self._absoluto = alvo
        self._dimensoes: tuple | None = None

    def existe(self) -> bool:
        try:
            return self._absoluto.is_file()
        except (OSError, ValueError):
            return False

    def tamanho(self) -> int:
        try:
            tamanho = self._absoluto.stat().st_size
        except OSError:
            raise ErroELiXX(f'Asset: "{self.caminho}" ilegivel.')
        if tamanho > MAX_BYTES_ASSET:
            raise ErroELiXX("Asset: excede 20MB.")
        return tamanho

    def dimensoes(self) -> tuple:
        """Le o minimo do arquivo (nunca a imagem inteira alem)."""
        if self._dimensoes is not None:
            return self._dimensoes
        self.tamanho()
        try:
            with open(self._absoluto, "rb") as fonte:
                cabeca = fonte.read(65536)
        except OSError:
            raise ErroELiXX(f'Asset: "{self.caminho}" ilegivel.')
        self._dimensoes = dimensoes_imagem(cabeca,
                                           self.formato)
        return self._dimensoes

    def bytes(self) -> bytes:
        """Conteudo (tardio; renderer usa o proprio cache)."""
        self.tamanho()
        try:
            with open(self._absoluto, "rb") as fonte:
                dados = fonte.read(MAX_BYTES_ASSET + 1)
        except OSError:
            raise ErroELiXX(f'Asset: "{self.caminho}" ilegivel.')
        if len(dados) > MAX_BYTES_ASSET:
            raise ErroELiXX("Asset: excede 20MB.")
        return dados

    def metadados(self) -> dict:
        largura, altura = self.dimensoes()
        return {"caminho": self.caminho,
                "tipo": self.formato,
                "largura": largura, "altura": altura,
                "formato": self.formato,
                "existe": True,
                "origem": self.base_dir,
                "tamanho": self.tamanho()}

    def to_dict(self) -> dict:
        try:
            return self.metadados()
        except ErroELiXX:
            return {"caminho": self.caminho,
                    "tipo": self.formato,
                    "existe": self.existe()}

    def __repr__(self) -> str:
        return f"AssetVisual({self.formato} {self.caminho})"


class CharacterAsset:
    """personagens/<nome>/ com ate 4 vistas (sem invencao)."""

    def __init__(self, nome: str, pasta: str,
                 base_dir: str = ".") -> None:
        from pathlib import Path

        nome_txt = str(nome).strip()
        if not nome_txt or len(nome_txt) > 80:
            raise ErroELiXX("Asset: nome curto e nao vazio.")
        if any(c in nome_txt for c in ('/', '\\', '\x00')):
            raise ErroELiXX("Asset: nome sem separadores.")
        self.nome = nome_txt
        self.pasta = _rel_seguro(pasta)
        self.base_dir = str(base_dir or ".")
        self._experimento: dict[str, str] = {}
        _ = Path

    def _candidatos(self, vista: str) -> list[str]:
        return [f"{vista}{ext}" for ext in EXTENSOES_IMAGEM]

    def mapear(self) -> dict[str, str | None]:
        """Vista -> arquivo real (ou None; nunca inventa)."""
        from pathlib import Path

        base = Path(self.base_dir) / self.pasta
        saida: dict[str, str | None] = {}
        for vista in VISTAS:
            achado = None
            for candidato in self._candidatos(vista):
                try:
                    if (base / candidato).is_file():
                        achado = candidato
                        break
                except (OSError, ValueError):
                    continue
            if achado is None and vista in self._experimento:
                marcador = self._experimento[vista]
                try:
                    if (base / marcador).is_file():
                        achado = marcador
                except (OSError, ValueError):
                    achado = None
            saida[vista] = achado
        return saida

    def diagnosticar(self) -> dict:
        """OK/AUSENTE por vista + COMPLETO/INCOMPLETO."""
        mapa = self.mapear()
        detalhe = {v: ("OK" if a else "AUSENTE")
                   for v, a in mapa.items()}
        experimental = sorted(
            v for v in mapa if mapa[v] and v in self._experimento
            and self._experimento[v] == mapa[v])
        return {"personagem": self.nome, "vistas": detalhe,
                "estado": ("COMPLETO" if all(mapa.values())
                           else "INCOMPLETO"),
                "experimental": experimental}

    def usar_como(self, vista: str, arquivo: str) -> str:
        """Mapeamento experimental explicito (ex.: 1 imagem)."""
        canonica = resolver_vista(vista)
        rel = _rel_seguro(arquivo)
        from pathlib import Path

        alvo = Path(self.base_dir) / self.pasta / rel
        try:
            existe = alvo.is_file()
        except (OSError, ValueError):
            existe = False
        if not existe:
            raise ErroELiXX(f'Asset: "{arquivo}" ausente '
                            f"em {self.pasta}.")
        self._experimento[canonica] = rel
        return rel

    def vista(self, nome: str) -> AssetVisual:
        """Vista canonica -> AssetVisual (ausente e erro)."""
        canonica = resolver_vista(nome)
        mapa = self.mapear()
        arquivo = mapa[canonica]
        if arquivo is None:
            raise ErroELiXX(
                f'Personagem "{self.nome}": {canonica} AUSENTE.')
        return AssetVisual(f"{self.pasta}/{arquivo}",
                           self.base_dir)

    def __repr__(self) -> str:
        return f"CharacterAsset({self.nome})"


class CharacterView:
    """Uma vista (nome + asset; sem pixels aqui)."""

    def __init__(self, nome: str, asset: AssetVisual) -> None:
        self.nome = resolver_vista(nome)
        if not isinstance(asset, AssetVisual):
            raise ErroELiXX("View: espera AssetVisual.")
        self.asset = asset

    def to_dict(self) -> dict:
        return {"vista": self.nome,
                "asset": self.asset.to_dict()}

    def __repr__(self) -> str:
        return f"CharacterView({self.nome})"


class CharacterLayer:
    """Camada de composicao futura (ordem; sem mesh)."""

    def __init__(self, nome: str, ordem: int = 0) -> None:
        nome_txt = str(nome).strip()
        if not nome_txt or len(nome_txt) > 80:
            raise ErroELiXX("Layer: nome curto e nao vazio.")
        self.nome = nome_txt
        self.ordem = int(ordem)

    def to_dict(self) -> dict:
        return {"layer": self.nome, "ordem": self.ordem}

    def __repr__(self) -> str:
        return f"CharacterLayer({self.nome} {self.ordem})"


class CharacterPart:
    """Parte futura (nome + vista/camada opcionais; sem IA)."""

    def __init__(self, nome: str, vista=None,
                 camada=None) -> None:
        nome_txt = str(nome).strip()
        if not nome_txt or len(nome_txt) > 80:
            raise ErroELiXX("Part: nome curto e nao vazio.")
        if vista is not None and not isinstance(
                vista, CharacterView):
            raise ErroELiXX("Part: vista espera CharacterView.")
        if camada is not None and not isinstance(
                camada, CharacterLayer):
            raise ErroELiXX("Part: camada espera CharacterLayer.")
        self.nome = nome_txt
        self.vista = vista
        self.camada = camada

    def to_dict(self) -> dict:
        return {"parte": self.nome,
                "vista": (self.vista.to_dict()
                          if self.vista else None),
                "camada": (self.camada.to_dict()
                           if self.camada else None)}

    def __repr__(self) -> str:
        return f"CharacterPart({self.nome})"


class CharacterRig:
    """Rig (metodo 'unidade'; outros, erro honesto futuro)."""

    METODOS = ("unidade",)

    def __init__(self, personagem, metodo: str = "unidade",
                 partes: dict | None = None,
                 camadas: list | None = None) -> None:
        from .personagem import Character as _Character

        if not isinstance(personagem, _Character):
            raise ErroELiXX("Rig: espera Character F12.")
        if metodo not in self.METODOS:
            raise ErroELiXX(
                f'Rig: metodo "{metodo}" nao suportado '
                f"nesta fase ({', '.join(self.METODOS)}).")
        self.personagem = personagem
        self.metodo = metodo
        self.partes = dict(partes or {})
        for nome, parte in self.partes.items():
            if not isinstance(parte, CharacterPart):
                raise ErroELiXX(f'Rig: parte "{nome}" '
                                "espera CharacterPart.")
        self.camadas = list(camadas or [])

    def to_dict(self) -> dict:
        return {"personagem": self.personagem.nome,
                "metodo": self.metodo,
                "partes": sorted(self.partes),
                "camadas": list(self.camadas)}

    def __repr__(self) -> str:
        return (f"CharacterRig({self.personagem.nome} "
                f"{self.metodo})")


_DIRECAO_DA_VISTA = {"frente": "frente", "tras": "costas",
                     "lado_direito": "direita",
                     "lado_esquerdo": "esquerda"}


def criar_personagem_unidade(character_asset: CharacterAsset,
                             vista: str = "frente",
                             x: float = 0.0, y: float = 0.0):
    """1 imagem = personagem animavel como unidade (F12 puro).

    Retorna (no_personagem, character, rig). Sem segmentacao:
    bracos/olhos/pernas/boca independentes NAO existem aqui.
    """
    from .cena import NoVisual
    from .personagem import Character as _Character

    if not isinstance(character_asset, CharacterAsset):
        raise ErroELiXX("Unidade: espera CharacterAsset.")
    canonica = resolver_vista(vista)
    asset = character_asset.vista(canonica)
    meta = asset.metadados()
    no = NoVisual(tipo="personagem", nome=character_asset.nome,
                  x=_finito(x, "x"), y=_finito(y, "y"),
                  largura=float(meta["largura"]),
                  altura=float(meta["altura"]))
    no.caminho_recurso = asset.caminho
    character = _Character(
        character_asset.nome, no, {}, {},
        direcao=_DIRECAO_DA_VISTA[canonica],
        representacoes={canonica: asset.caminho})
    rig = CharacterRig(character, "unidade")
    return no, character, rig


def _definicao(alvo: str, nome: str, prop: str, de, para,
               duracao_ms: float, repetir=1,
               modo: str = "normal") -> object:
    from ..animacao.motor import ChaveAnimacao, DefinicaoAnimacao

    duracao_ms = _finito(duracao_ms, "duracao_ms")
    if not 1 <= duracao_ms <= 60000:
        raise ErroELiXX("Animacao: duracao 1..60000ms.")
    if modo not in ("normal", "ping_pong"):
        raise ErroELiXX("Animacao: modo normal/ping_pong.")
    return DefinicaoAnimacao(
        nome=nome, alvo=str(alvo),
        chaves=[ChaveAnimacao(prop, de, para)],
        duracao_ms=duracao_ms, movimento="suave",
        repetir=repetir, modo=modo)


def animacao_respiracao(alvo: str, amplitude: float = 0.04,
                        duracao_ms: float = 1200.0,
                        repetir="infinito") -> object:
    """Escala suave 1 -> 1+amp (loop ping_pong)."""
    amplitude = _finito(amplitude, "amplitude")
    if not 0 < amplitude <= 0.25:
        raise ErroELiXX("Respiracao: amplitude 0..0.25.")
    return _definicao(alvo, "respirar", "escala", 1.0,
                      1.0 + amplitude, duracao_ms, repetir,
                      "ping_pong")


def animacao_inclinacao(alvo: str, graus: float = 6.0,
                        duracao_ms: float = 900.0,
                        repetir=2) -> object:
    """Rotacao 0 -> graus (ida/volta; sem fisica nova)."""
    graus = _finito(graus, "graus")
    if not -45 <= graus <= 45:
        raise ErroELiXX("Inclinacao: -45..45 graus.")
    return _definicao(alvo, "inclinar", "rotacao", 0.0, graus,
                      duracao_ms, repetir, "ping_pong")


def animacao_deslocamento(alvo: str, origem: tuple,
                          dx: float = 40.0, dy: float = 0.0,
                          duracao_ms: float = 800.0,
                          repetir=2) -> object:
    """Posicao origem -> origem+(dx,dy) (motion existente)."""
    try:
        x0, y0 = float(origem[0]), float(origem[1])
    except (TypeError, ValueError, IndexError):
        raise ErroELiXX("Deslocamento: origem (x, y).")
    dx_n, dy_n = _finito(dx, "dx"), _finito(dy, "dy")
    if not math.isfinite(x0) or not math.isfinite(y0):
        raise ErroELiXX("Deslocamento: origem finita.")
    return _definicao(alvo, "deslocar", "posicao", (x0, y0),
                      (x0 + dx_n, y0 + dy_n), duracao_ms,
                      repetir, "ping_pong")


def abrir_palco(cena, base_dir: str = ".", motor=None):
    """RenderizadorTk sobre a cena (adaptador minimo)."""
    from ..multimidia.recursos import GerenciadorRecursos
    from .tk import RenderizadorTk

    try:
        renderer = RenderizadorTk()
    except Exception as exc:
        raise ErroELiXX(f"Palco: Tk indisponivel ({exc}).")
    renderer.recursos = GerenciadorRecursos(str(base_dir))
    if motor is not None:
        renderer.motor = motor
    renderer.montar(cena)
    return renderer
