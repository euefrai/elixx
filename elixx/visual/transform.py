"""Transform Core da ELiXX (Fase 10) — fundação matemática 2D.

Sistema de coordenadas (único em runtime, cena, animação e renderers):

- origem (0, 0) no canto superior esquerdo da área de conteúdo;
- X cresce para a direita, Y cresce para baixo (igual à Cena existente);
- ângulos em graus, sentido horário na tela (Y para baixo);
- opacidade em 0.0 (invisível) .. 1.0 (totalmente visível).

Toda a matemática vive aqui. Nenhum renderer contém cálculo central:
o backend recebe o estado transformado (posição, tamanho, ângulo,
opacidade, camada) e apenas desenha.

Mapeamento de nomes (padrão atual do projeto):

- Cena    = Scene2D (coleção de janelas + viewport);
- NoVisual = Node (objeto visual com transform local + pai);
- tipo "grupo"/"objeto" = Group (contêiner com transformação conjunta).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..erros import ErroELiXX

__all__ = [
    "Vector2", "Transform", "Viewport",
    "normalizar_graus", "graus_para_rad", "rad_para_graus",
    "validar_fator_escala", "validar_opacidade",
    "resolver_pivo", "combinar", "aplicar_ponto",
    "transform_de_no", "globais_da_cena", "ordem_visual",
]


# ----- validação numérica (Fase 10: NaN/infinito nunca entram) -----

def _finito(valor: float, o_que: str, linha: int = 0) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ErroELiXX(
            f'Transformação inválida: "{o_que}" precisa de número finito '
            "(recebido NaN ou infinito).",
            linha=linha,
            sugestao="Use valores como 100, 1.5, 45deg ou 80%.",
        )
    return numero


# ----- Vector2 -----

@dataclass
class Vector2:
    """Vetor 2D imutável-ish (operações devolvem novos vetores)."""

    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        self.x = float(self.x)
        self.y = float(self.y)

    def __add__(self, outro: Vector2) -> Vector2:
        return Vector2(self.x + outro.x, self.y + outro.y)

    def __sub__(self, outro: Vector2) -> Vector2:
        return Vector2(self.x - outro.x, self.y - outro.y)

    def __mul__(self, escalar: float) -> Vector2:
        return Vector2(self.x * float(escalar), self.y * float(escalar))

    __rmul__ = __mul__

    def __truediv__(self, escalar: float) -> Vector2:
        divisor = float(escalar)
        if divisor == 0.0:
            raise ErroELiXX(
                "Divisão por zero em vetor (vetor / 0).",
                sugestao="Use um divisor diferente de zero.",
            )
        return Vector2(self.x / divisor, self.y / divisor)

    def magnitude(self) -> float:
        """Comprimento do vetor (|v|)."""
        return math.hypot(self.x, self.y)

    def normalizado(self) -> Vector2:
        """Vetor unitário na mesma direção (zero vira zero, sem erro)."""
        mag = self.magnitude()
        if mag == 0.0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / mag, self.y / mag)

    def distancia(self, outro: Vector2) -> float:
        """Distância euclidiana até outro vetor."""
        return math.hypot(self.x - outro.x, self.y - outro.y)

    def direcao(self, outro: Vector2) -> Vector2:
        """Direção unitária deste vetor até outro (zero se coincidem)."""
        return (outro - self).normalizado()

    def dot(self, outro: Vector2) -> float:
        """Produto escalar (dot product)."""
        return self.x * outro.x + self.y * outro.y

    def tupla(self) -> tuple[float, float]:
        return (self.x, self.y)


# ----- ângulos -----

def normalizar_graus(graus: float, linha: int = 0) -> float:
    """Normaliza para [0, 360). Unidade interna: graus, sentido horário."""
    valor = _finito(graus, "rotação", linha=linha)
    return valor % 360.0


def graus_para_rad(graus: float) -> float:
    return math.radians(float(graus))


def rad_para_graus(rad: float) -> float:
    return math.degrees(float(rad))


def validar_fator_escala(valor: float, eixo: str = "escala",
                         linha: int = 0) -> float:
    """Escala precisa ser finita (0/negativa = colapso/espelho, permitido)."""
    return _finito(valor, eixo, linha=linha)


def validar_opacidade(valor: float, linha: int = 0) -> float:
    """Opacidade em 0.0..1.0. Fora da faixa é erro claro (não silencioso)."""
    numero = _finito(valor, "opacidade", linha=linha)
    if not 0.0 <= numero <= 1.0:
        raise ErroELiXX(
            f'Opacidade inválida: {valor!r}. Use 0% (invisível) até '
            "100% (totalmente visível).",
            linha=linha,
            exemplo="opacidade: 80%",
        )
    return numero


# ----- Transform -----

@dataclass
class Transform:
    """Transformação local: posição + rotação + escala + pivô + opacidade.

    Pivô em (valor, unidade) por eixo: "%" (do tamanho do objeto,
    padrão 50% = centro) ou "px" (absoluto). Apontar o pivô para
    ombro/quadril/pescoço no futuro é só trocar estes valores.
    """

    x: float = 0.0
    y: float = 0.0
    rotacao: float = 0.0  # graus, horário, normalizado em [0, 360)
    escala_x: float = 1.0
    escala_y: float = 1.0
    opacidade: float = 1.0
    pivo_x: float = 50.0
    pivo_y: float = 50.0
    pivo_unidade_x: str = "%"
    pivo_unidade_y: str = "%"

    def __post_init__(self) -> None:
        self.x = _finito(self.x, "posição x")
        self.y = _finito(self.y, "posição y")
        self.rotacao = normalizar_graus(self.rotacao)
        self.escala_x = validar_fator_escala(self.escala_x, "escala x")
        self.escala_y = validar_fator_escala(self.escala_y, "escala y")
        self.opacidade = validar_opacidade(self.opacidade)
        self.pivo_x = _finito(self.pivo_x, "pivô x")
        self.pivo_y = _finito(self.pivo_y, "pivô y")
        if self.pivo_unidade_x not in ("%", "px"):
            raise ErroELiXX(
                f'Pivô inválido no eixo x: {self.pivo_unidade_x!r}. '
                'Use % ou px (ex. pivô: 50% 50%).')
        if self.pivo_unidade_y not in ("%", "px"):
            raise ErroELiXX(
                f'Pivô inválido no eixo y: {self.pivo_unidade_y!r}. '
                'Use % ou px (ex. pivô: 50% 50%).')

    @property
    def posicao(self) -> Vector2:
        return Vector2(self.x, self.y)

    @property
    def escala(self) -> tuple[float, float]:
        return (self.escala_x, self.escala_y)


def resolver_pivo(transform: Transform, largura: float | None,
                  altura: float | None) -> tuple[float, float]:
    """Pivô em pixels a partir do canto superior esquerdo do objeto."""
    ref_l = float(largura) if largura else 0.0
    ref_a = float(altura) if altura else 0.0
    if transform.pivo_unidade_x == "%":
        px = transform.pivo_x / 100.0 * ref_l
    else:
        px = transform.pivo_x
    if transform.pivo_unidade_y == "%":
        py = transform.pivo_y / 100.0 * ref_a
    else:
        py = transform.pivo_y
    return (px, py)


def _girar(vx: float, vy: float, graus: float) -> tuple[float, float]:
    """Gira vetor em graus horários (tela com Y para baixo)."""
    rad = math.radians(graus)
    cosseno, seno = math.cos(rad), math.sin(rad)
    # Horário na tela (y desce) = anti-horário na matemática: (x, y) ->
    # (x*cos + y*sin, -x*sin + y*cos)... com y para baixo, a matriz
    # horária direta é (x*cos - y*sin, x*sin + y*cos) aplicada no
    # espaço da tela. Mantemos esta convenção em todo o motor.
    return (vx * cosseno - vy * seno, vx * seno + vy * cosseno)


def aplicar_ponto(transform: Transform, ponto: Vector2,
                  tamanho: tuple[float | None, float | None] = (None, None)
                  ) -> Vector2:
    """Aplica escala (ao redor do pivô) + rotação (ao redor do pivô)
    + translação a um ponto no espaço local do objeto."""
    px, py = resolver_pivo(transform, tamanho[0], tamanho[1])
    vx = (ponto.x - px) * transform.escala_x
    vy = (ponto.y - py) * transform.escala_y
    rx, ry = _girar(vx, vy, transform.rotacao)
    return Vector2(transform.x + px + rx, transform.y + py + ry)


def combinar(pai: Transform, filho: Transform) -> Transform:
    """Transform global do filho = pai composto com filho.

    Regras: pai move/gira/escala → filho acompanha. Opacidade multiplica
    (filho nunca mais visível que o pai). Pivô do resultado é o do filho.
    """
    origem_filho_global = aplicar_ponto(pai, Vector2(filho.x, filho.y))
    return Transform(
        x=origem_filho_global.x,
        y=origem_filho_global.y,
        rotacao=(pai.rotacao + filho.rotacao) % 360.0,
        escala_x=pai.escala_x * filho.escala_x,
        escala_y=pai.escala_y * filho.escala_y,
        opacidade=max(0.0, min(1.0, pai.opacidade * filho.opacidade)),
        pivo_x=filho.pivo_x,
        pivo_y=filho.pivo_y,
        pivo_unidade_x=filho.pivo_unidade_x,
        pivo_unidade_y=filho.pivo_unidade_y,
    )


# ----- ponte com NoVisual (sem importar cena: duck-typing) -----

def transform_de_no(no) -> Transform:
    """Lê o transform local de um NoVisual/Objeto (qualquer geração).

    Campos novos (Fase 10) com fallback para os legados: escala (uniforme),
    pivo (50%/50%), camada resolvida em ordem_visual.
    """
    escala_x = getattr(no, "escala_x", None)
    escala_y = getattr(no, "escala_y", None)
    legado = float(getattr(no, "escala", 1.0) or 1.0)
    sx = float(escala_x) if escala_x is not None else legado
    sy = float(escala_y) if escala_y is not None else legado
    return Transform(
        x=float(getattr(no, "x", 0.0) or 0.0),
        y=float(getattr(no, "y", 0.0) or 0.0),
        rotacao=float(getattr(no, "rotacao", 0.0) or 0.0),
        escala_x=sx,
        escala_y=sy,
        opacidade=float(getattr(no, "opacidade", 1.0)),
        pivo_x=float(getattr(no, "pivo_x", 50.0)),
        pivo_y=float(getattr(no, "pivo_y", 50.0)),
        pivo_unidade_x=getattr(no, "pivo_unidade_x", "%") or "%",
        pivo_unidade_y=getattr(no, "pivo_unidade_y", "%") or "%",
    )


def globais_da_cena(cena) -> dict[int, Transform]:
    """Transform global de cada nó: {id(no): Transform}.

    Percorre janelas em pré-ordem; filho compõe com o pai. O renderer
    usa quando precisa (ex. HTML emite o global); o Tk usa hierarquia
    de Frames para o mesmo efeito visual.
    """
    saida: dict[int, Transform] = {}

    def visitar(no, acumulado: Transform | None) -> None:
        local = transform_de_no(no)
        global_ = combinar(acumulado, local) if acumulado else local
        saida[id(no)] = global_
        for filho in getattr(no, "filhos", []):
            visitar(filho, global_)

    for janela in getattr(cena, "janelas", []):
        visitar(janela, None)
    return saida


def ordem_visual(raiz) -> list:
    """Filhos em ordem determinística: (camada, ordem de criação).

    Menor camada atrás, maior na frente; empate = ordem estável de
    criação. Não reordena a cena, só devolve a sequência de desenho.
    """
    filhos = list(getattr(raiz, "filhos", []))
    return sorted(filhos,
                  key=lambda n: (float(getattr(n, "camada", 0.0) or 0.0),
                                 getattr(n, "_seq", 0)))


# ----- Viewport -----

@dataclass
class Viewport:
    """Área visual exibida (fundação para futura câmera).

    Fase 10: só representa tamanho lógico + deslocamento + zoom.
    Câmera completa (seguir, limites, transições) é fase futura.
    """

    largura: float = 800.0
    altura: float = 600.0
    x: float = 0.0  # deslocamento do mundo visível
    y: float = 0.0
    zoom: float = 1.0

    def __post_init__(self) -> None:
        self.largura = _finito(self.largura, "viewport largura")
        self.altura = _finito(self.altura, "viewport altura")
        self.x = _finito(self.x, "viewport x")
        self.y = _finito(self.y, "viewport y")
        self.zoom = _finito(self.zoom, "viewport zoom")
        if self.largura <= 0 or self.altura <= 0:
            raise ErroELiXX(
                "Viewport precisa de largura e altura positivas.",
                sugestao="Use valores como 800x600.",
            )
        if self.zoom <= 0:
            raise ErroELiXX(
                "Zoom da viewport precisa ser positivo.",
                sugestao="Use zoom: 1.0 (normal).",
            )

    def mundo_para_tela(self, ponto: Vector2) -> Vector2:
        """Converte coordenada de mundo para tela (com zoom + offset)."""
        return Vector2((ponto.x - self.x) * self.zoom,
                       (ponto.y - self.y) * self.zoom)

    def tela_para_mundo(self, ponto: Vector2) -> Vector2:
        """Converte coordenada de tela para mundo."""
        return Vector2(ponto.x / self.zoom + self.x,
                       ponto.y / self.zoom + self.y)
