"""Automatic Character Rigging da ELiXX (Fase 23) — análise vira puppet.

Fluxo (IA prepara, o motor executa; runtime sem LLM, sem rede):

    ImageFrame/dados ──→ CharacterAnalyzer ──→ CharacterAnalysis
        ──→ construir_rig ──→ CharacterRig ──→ rig_para_personagem
        ──→ Character (F12) ──→ Motion Core (F11) ──→ Renderer

Modos: automático (analyzer entrega tudo), assistido (mesclar
correções via `mesclar_analise`) e profissional (hierarquia, pivôs,
joints, camadas, máscaras, views, expressões e poses explícitos).

Reuso (sem duplicar): Vector2/Point2D/Bounds2D (F10/F13/F21),
Transform (F10), Character/CharacterPart/Pose/Gesture/Joint e
DIRECOES (F12), PerceptionObservation/PerceptionResult (F22, entrada
opcional). Sem física, sem IK solver, sem mesh pesado: puppet 2D por
partes + transformações hierárquicas.

Honestidade: uma imagem não contém o que não mostra. Vista ausente,
parte parcial ou oculta vira aviso estruturado — nunca geometria
inventada.
"""
from __future__ import annotations

import json
import math

from ..erros import ErroELiXX
from .mundo import Bounds2D
from .personagem import DIRECOES as VISTAS
from .transform import Vector2

__all__ = [
    "VISTAS",
    "PARTES_CONHECIDAS",
    "TIPOS_JUNTA",
    "AUTOMATICAS",
    "MAX_PARTES",
    "MAX_PROFUNDIDADE_RIG",
    "MAX_VALOR_RIG",
    "CharacterMask",
    "CharacterPartDetection",
    "CharacterAnalysis",
    "RigJoint",
    "RigPart",
    "RigLayer",
    "RigView",
    "RigExpression",
    "RigPose",
    "CharacterRig",
    "CharacterAnalyzer",
    "NullCharacterAnalyzer",
    "MockCharacterAnalyzer",
    "StructuredCharacterAnalyzer",
    "mesclar_analise",
    "construir_rig",
    "rig_para_personagem",
    "definir_automatica",
    "analise_de_percepcao",
    "debug_rigging",
]

PARTES_CONHECIDAS = (
    "cabeca", "pescoco", "tronco", "corpo",
    "braco_esquerdo", "braco_direito",
    "antebraco_esquerdo", "antebraco_direito",
    "mao_esquerda", "mao_direita",
    "perna_esquerda", "perna_direita",
    "pe_esquerdo", "pe_direito",
    "olho_esquerdo", "olho_direito", "olhos",
    "sobrancelha_esquerda", "sobrancelha_direita", "sobrancelhas",
    "nariz", "boca", "cabelo", "orelha_esquerda", "orelha_direita",
    "acessorio",
)
"""Partes conhecidas (dica, não obrigação). Tipo novo segue como dado
customizado — nunca descartado."""

TIPOS_JUNTA = ("pivo", "deslizante", "fixa")
"""Tipos de articulação (estrutura; sem solver nesta fase)."""

AUTOMATICAS = ("respirar", "piscar", "olhar", "falar", "acenar",
               "andar", "parar", "balancar_cabelo")
"""Animações automáticas disponíveis como definição estruturada."""

MAX_PARTES = 5000
"""Teto anti-gigante (1000 partes passam; acima: erro claro)."""

MAX_PROFUNDIDADE_RIG = 32
"""Teto anti-ciclo/recursão na hierarquia."""

MAX_VALOR_RIG = 1.0e9
"""Módulo máximo de coordenadas/tamanhos/pivôs."""

_PROF_DADOS = 6
"""Aninhamento máximo de metadados (só JSON raso)."""


# ----- validação de dados (só dados; sem código) -----

def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'"{o_que}" precisa de número '
                        f"(recebido {type(valor).__name__}).")
    if not math.isfinite(numero):
        raise ErroELiXX(f'"{o_que}" precisa de número finito '
                        "(recebido NaN ou infinito).")
    if abs(numero) > MAX_VALOR_RIG:
        raise ErroELiXX(f'"{o_que}" gigante ({numero:g}; teto '
                        f"{MAX_VALOR_RIG:g}).")
    return numero


def _e_dado(valor, profundidade: int = 0) -> bool:
    if profundidade > _PROF_DADOS:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, float) and not math.isfinite(valor):
            return False
        return True
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(i, profundidade + 1) for i in valor)
    if isinstance(valor, dict):
        return all(isinstance(c, str)
                   and _e_dado(i, profundidade + 1)
                   for c, i in valor.items())
    return False


def _id_valido(valor, o_que: str = "id") -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'"{o_que}" precisa de texto não vazio.')
    return valor.strip()


def _ordenado(valores) -> list:
    return sorted(valores)


def _confianca(valor) -> float | None:
    if valor is None:
        return None
    numero = _finito(valor, "confiança")
    if not 0.0 <= numero <= 1.0:
        raise ErroELiXX(f'"confiança" precisa de 0..1 (recebido '
                        f"{numero:g}).")
    return numero


def _bounds_de(bruto, dono: str) -> Bounds2D:
    if not isinstance(bruto, dict):
        raise ErroELiXX(f'Bounds de "{dono}" precisa de dicionário.')
    b = Bounds2D(_finito(bruto.get("x", 0.0), f"x de {dono}"),
                 _finito(bruto.get("y", 0.0), f"y de {dono}"),
                 _finito(bruto.get("largura", 0.0),
                         f"largura de {dono}"),
                 _finito(bruto.get("altura", 0.0),
                         f"altura de {dono}"))
    if b.largura < 0 or b.altura < 0:
        raise ErroELiXX(f'"{dono}": tamanho negativo.')
    return b


def _bounds_dict(b: Bounds2D) -> dict:
    return {"x": b.x, "y": b.y, "largura": b.largura,
            "altura": b.altura}


def _validar_bounds(b: Bounds2D, dono: str) -> Bounds2D:
    """Bounds direto (não via dict): finitude + tamanho ≥ 0.

    Bounds2D da F13 é estrutura pura sem validação; aqui o rig exige
    números finitos (anti NaN/Infinity/gigante). x/y negativos são
    válidos (parte à esquerda/acima da origem).
    """
    if not isinstance(b, Bounds2D):
        raise ErroELiXX(f'"{dono}": bounds precisa de Bounds2D.')
    for campo in ("x", "y", "largura", "altura"):
        _finito(getattr(b, campo), f"{campo} de {dono}")
    if b.largura < 0 or b.altura < 0:
        raise ErroELiXX(f'"{dono}": tamanho negativo.')
    return b


def _normalizar_ajustes(ajustes: dict, dono: str) -> dict:
    """{parte → {prop → valor}} com tuplas virando listas (JSON-safe).

    Poses F12 usam tuplas em memória; o rig serializável normaliza
    para listas na entrada (determinístico; nunca código).
    """
    def _norm(valor):
        if isinstance(valor, tuple):
            return [_norm(v) for v in valor]
        if isinstance(valor, list):
            return [_norm(v) for v in valor]
        if isinstance(valor, dict):
            return {str(k): _norm(v) for k, v in valor.items()}
        return valor
    aj = dict(ajustes or {})
    saida = {}
    for parte, props in aj.items():
        if not isinstance(props, dict):
            raise ErroELiXX(f'"{dono}": ajustes de "{parte}" '
                            "precisam de dicionário.")
        norm = {str(p): _norm(v) for p, v in props.items()}
        if not _e_dado(norm):
            raise ErroELiXX(f'"{dono}": ajustes de "{parte}" '
                            "inválidos (só JSON finito).")
        saida[str(parte)] = norm
    return saida


# ----- CharacterMask -----

class CharacterMask:
    """Região visual de uma parte (bounds/polígono/referência). Só dados.

    `kind`: "bounds" (retângulo), "poligono" (lista de pontos) ou
    "referencia" (asset/segmentação externa, só string). Sem bitmap
    pesado nesta fase.
    """

    def __init__(self, mask_id: str, parte_id: str,
                 kind: str = "bounds",
                 bounds: Bounds2D | None = None,
                 pontos: list | None = None,
                 imagem_ref: str | None = None,
                 confianca: float | None = None,
                 origem: str = "analyzer") -> None:
        self.id = _id_valido(mask_id, "id da máscara")
        self.parte_id = _id_valido(parte_id, "parte da máscara")
        kind_txt = str(kind).strip() or "bounds"
        if kind_txt not in ("bounds", "poligono", "referencia"):
            raise ErroELiXX(f'Máscara "{self.id}": kind "{kind_txt}" '
                            "inválido (bounds, poligono, referencia).")
        self.kind = kind_txt
        if bounds is None:
            bounds = Bounds2D(0.0, 0.0, 0.0, 0.0)
        self.bounds = _validar_bounds(
            bounds if bounds is not None
            else Bounds2D(0.0, 0.0, 0.0, 0.0),
            f"máscara {self.id}")
        pts = []
        for p in (pontos or []):
            if isinstance(p, (Vector2,)):
                pts.append(Vector2(_finito(p.x, f"ponto de {self.id}"),
                                   _finito(p.y, f"ponto de {self.id}")))
            elif isinstance(p, dict):
                pts.append(Vector2(
                    _finito(p.get("x", 0.0), f"ponto de {self.id}"),
                    _finito(p.get("y", 0.0), f"ponto de {self.id}")))
            else:
                raise ErroELiXX(f'Máscara "{self.id}": ponto precisa de '
                                "{x, y}.")
        if self.kind == "poligono" and len(pts) < 3:
            raise ErroELiXX(f'Máscara "{self.id}": polígono precisa de '
                            "≥ 3 pontos.")
        self.pontos = pts
        self.imagem_ref = (str(imagem_ref) if imagem_ref is not None
                           else None)
        self.confianca = _confianca(confianca)
        self.origem = str(origem).strip() or "analyzer"

    def to_dict(self) -> dict:
        dados = {"id": self.id, "parte_id": self.parte_id,
                 "kind": self.kind, "bounds": _bounds_dict(self.bounds),
                 "pontos": [{"x": p.x, "y": p.y} for p in self.pontos],
                 "imagem_ref": self.imagem_ref,
                 "confianca": self.confianca, "origem": self.origem}
        if not _e_dado(dados):
            raise ErroELiXX(f'Máscara "{self.id}" não serializável.')
        return dados

    @staticmethod
    def from_dict(dados: dict) -> CharacterMask:
        if not isinstance(dados, dict):
            raise ErroELiXX("Máscara precisa de dicionário.")
        return CharacterMask(
            dados.get("id", ""), dados.get("parte_id", ""),
            kind=dados.get("kind", "bounds"),
            bounds=_bounds_de(dados.get("bounds") or {},
                              dados.get("id", "?")),
            pontos=dados.get("pontos") or [],
            imagem_ref=dados.get("imagem_ref"),
            confianca=dados.get("confianca"),
            origem=dados.get("origem", "analyzer"))

    def __repr__(self) -> str:
        return f"CharacterMask({self.kind} {self.id})"


# ----- CharacterPartDetection -----

class CharacterPartDetection:
    """Parte detectada/declarada (tipo + bounds + confiança). Só dados."""

    def __init__(self, det_id: str, tipo: str = "desconhecido",
                 bounds: Bounds2D | None = None,
                 confianca: float | None = None,
                 texto: str | None = None,
                 origem: str = "analyzer",
                 parent_id: str | None = None,
                 visibilidade: str = "visivel",
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(det_id)
        self.tipo = str(tipo).strip() or "desconhecido"
        if bounds is None:
            bounds = Bounds2D(0.0, 0.0, 0.0, 0.0)
        self.bounds = _validar_bounds(
            bounds if bounds is not None
            else Bounds2D(0.0, 0.0, 0.0, 0.0),
            f"detecção {self.id}")
        self.confianca = _confianca(confianca)
        self.texto = (str(texto) if texto is not None else None)
        self.origem = str(origem).strip() or "analyzer"
        self.parent_id = (str(parent_id).strip() or None
                          if parent_id is not None else None)
        vis = str(visibilidade).strip() or "visivel"
        if vis not in ("visivel", "parcial", "oculta"):
            raise ErroELiXX(f'Detecção "{self.id}": visibilidade "{vis}" '
                            "inválida (visivel, parcial, oculta).")
        self.visibilidade = vis
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Detecção "{self.id}": metadata inválida.')
        self.metadata = meta

    @property
    def customizada(self) -> bool:
        """True quando o tipo não está no vocabulário conhecido."""
        return self.tipo not in PARTES_CONHECIDAS

    def to_dict(self) -> dict:
        dados = {"id": self.id, "tipo": self.tipo,
                 "bounds": _bounds_dict(self.bounds),
                 "confianca": self.confianca, "texto": self.texto,
                 "origem": self.origem, "parent_id": self.parent_id,
                 "visibilidade": self.visibilidade,
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX(f'Detecção "{self.id}" não serializável.')
        return dados

    @staticmethod
    def from_dict(dados: dict) -> CharacterPartDetection:
        if not isinstance(dados, dict):
            raise ErroELiXX("Detecção precisa de dicionário.")
        return CharacterPartDetection(
            dados.get("id", ""), tipo=dados.get("tipo",
                                                "desconhecido"),
            bounds=_bounds_de(dados.get("bounds") or {},
                              dados.get("id", "?")),
            confianca=dados.get("confianca"), texto=dados.get("texto"),
            origem=dados.get("origem", "analyzer"),
            parent_id=dados.get("parent_id"),
            visibilidade=dados.get("visibilidade", "visivel"),
            metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"CharacterPartDetection({self.tipo} {self.id})"


# ----- CharacterAnalysis -----

class CharacterAnalysis:
    """Análise de personagem: detecções + avisos honestos. Só dados."""

    def __init__(self, analysis_id: str, deteccoes: list | None = None,
                 origem: str = "analyzer",
                 avisos: list | None = None,
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(analysis_id, "id da análise")
        dets = list(deteccoes or [])
        if len(dets) > MAX_PARTES:
            raise ErroELiXX(f"Análise com {len(dets)} partes (teto "
                            f"{MAX_PARTES}).")
        for d in dets:
            if not isinstance(d, CharacterPartDetection):
                raise ErroELiXX("deteccoes espera "
                                "CharacterPartDetection.")
        vistos = set()
        for d in dets:
            if d.id in vistos:
                raise ErroELiXX(f'Detecção "{d.id}" duplicada.')
            vistos.add(d.id)
        self.deteccoes = dets
        self.origem = str(origem).strip() or "analyzer"
        self.avisos = []
        for a in (avisos or []):
            if not isinstance(a, dict) or not _e_dado(a):
                raise ErroELiXX("Aviso precisa de dicionário JSON.")
            self.avisos.append(dict(a))
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX("Metadata da análise inválida.")
        self.metadata = meta
        self._completar_avisos()

    def _completar_avisos(self) -> None:
        """Avisos derivados (honestidade técnica, determinísticos)."""
        for d in sorted(self.deteccoes, key=lambda x: x.id):
            if d.visibilidade == "parcial":
                self.avisos.append(
                    {"codigo": "parte_parcial",
                     "motivo": f'"{d.id}" parcialmente visível '
                               "(geometria incompleta)."})
            elif d.visibilidade == "oculta":
                self.avisos.append(
                    {"codigo": "parte_oculta",
                     "motivo": f'"{d.id}" oculta (sem geometria '
                               "confiável)."})
            if d.customizada:
                self.avisos.append(
                    {"codigo": "parte_customizada",
                     "motivo": f'"{d.id}" tipo "{d.tipo}" fora do '
                               "vocabulário (preservado)."})

    def __len__(self) -> int:
        return len(self.deteccoes)

    def __contains__(self, det_id: str) -> bool:
        return any(d.id == str(det_id) for d in self.deteccoes)

    def por_id(self, det_id: str) -> CharacterPartDetection:
        for d in self.deteccoes:
            if d.id == str(det_id):
                return d
        raise ErroELiXX(f'Detecção "{det_id}" ausente.')

    def to_dict(self) -> dict:
        dados = {"id": self.id,
                 "deteccoes": [d.to_dict() for d in self.deteccoes],
                 "origem": self.origem,
                 "avisos": [dict(a) for a in self.avisos],
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX("Análise não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> CharacterAnalysis:
        if not isinstance(dados, dict):
            raise ErroELiXX("Análise precisa de dicionário.")
        dets_txt = dados.get("deteccoes") or []
        if not isinstance(dets_txt, list):
            raise ErroELiXX("deteccoes precisa de lista.")
        # Avisos derivados seriam duplicados: reconstrói sem eles.
        base = CharacterAnalysis.__new__(CharacterAnalysis)
        base.id = _id_valido(dados.get("id", ""), "id da análise")
        base.deteccoes = [CharacterPartDetection.from_dict(d)
                          for d in dets_txt]
        if len(base.deteccoes) > MAX_PARTES:
            raise ErroELiXX("Análise gigante.")
        vistos = set()
        for d in base.deteccoes:
            if d.id in vistos:
                raise ErroELiXX(f'Detecção "{d.id}" duplicada.')
            vistos.add(d.id)
        base.origem = str(dados.get("origem", "analyzer") or "analyzer")
        base.avisos = []
        for a in (dados.get("avisos") or []):
            if not isinstance(a, dict) or not _e_dado(a):
                raise ErroELiXX("Aviso inválido.")
            base.avisos.append(dict(a))
        meta = dict(dados.get("metadata") or {})
        if not _e_dado(meta):
            raise ErroELiXX("Metadata inválida.")
        base.metadata = meta
        return base

    @staticmethod
    def from_json(texto: str) -> CharacterAnalysis:
        if not isinstance(texto, str):
            raise ErroELiXX("Análise JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Análise JSON inválida: {exc}.")
        return CharacterAnalysis.from_dict(dados)

    def __repr__(self) -> str:
        return (f"CharacterAnalysis({self.id}: {len(self)} partes, "
                f"{len(self.avisos)} avisos)")


def mesclar_analise(base: CharacterAnalysis,
                    correcoes: list) -> CharacterAnalysis:
    """Modo assistido: correções (mesmo formato) mescladas por id.

    Mesmo id = substitui; id novo = adiciona. Determinístico; nunca
    apaga silenciosamente o que não foi mencionado (só soma/substitui
    o declarado). Retorna análise nova (origem "assistido").
    """
    if not isinstance(base, CharacterAnalysis):
        raise ErroELiXX("mesclar_analise espera CharacterAnalysis.")
    novas: dict[str, CharacterPartDetection] = {
        d.id: d for d in base.deteccoes}
    for bruto in (correcoes or []):
        det = (bruto if isinstance(bruto, CharacterPartDetection)
               else CharacterPartDetection.from_dict(bruto))
        novas[det.id] = det
    return CharacterAnalysis(f"{base.id}+assistido",
                             [novas[k] for k in _ordenado(novas)],
                             origem="assistido",
                             metadata={"base": base.id,
                                       "origem_base": base.origem})


# ----- RigJoint / RigPart / RigLayer / RigView / RigExpression / RigPose -----

class RigJoint:
    """Articulação do rig (estrutura; sem solver)."""

    def __init__(self, nome: str, parent: str, child: str,
                 pivot_x: float = 50.0, pivot_unidade_x: str = "%",
                 pivot_y: float = 50.0, pivot_unidade_y: str = "%",
                 minimo: float | None = None,
                 maximo: float | None = None,
                 tipo: str = "pivo") -> None:
        self.nome = _id_valido(nome, "nome da junta")
        self.parent = _id_valido(parent, "pai da junta")
        self.child = _id_valido(child, "filho da junta")
        if self.parent == self.child:
            raise ErroELiXX(f'Junta "{self.nome}": pai e filho iguais.')
        self.pivot_x = _finito(pivot_x, f"pivô x de {self.nome}")
        self.pivot_y = _finito(pivot_y, f"pivô y de {self.nome}")
        for unid, eixo in ((pivot_unidade_x, "x"), (pivot_unidade_y, "y")):
            if unid not in ("%", "px"):
                raise ErroELiXX(f'Junta "{self.nome}": pivô {eixo} '
                                 f'"{unid}" inválido (%, px).')
        self.pivot_unidade_x = pivot_unidade_x
        self.pivot_unidade_y = pivot_unidade_y
        if minimo is not None:
            minimo = _finito(minimo, f"mínimo de {self.nome}")
        if maximo is not None:
            maximo = _finito(maximo, f"máximo de {self.nome}")
        if (minimo is not None and maximo is not None
                and minimo > maximo):
            raise ErroELiXX(f'Junta "{self.nome}": mínimo > máximo.')
        self.minimo = minimo
        self.maximo = maximo
        tipo_txt = str(tipo).strip() or "pivo"
        if tipo_txt not in TIPOS_JUNTA:
            raise ErroELiXX(f'Junta "{self.nome}": tipo "{tipo_txt}" '
                            f'inválido ({", ".join(TIPOS_JUNTA)}).')
        self.tipo = tipo_txt

    def to_dict(self) -> dict:
        return {"nome": self.nome, "parent": self.parent,
                "child": self.child, "pivot_x": self.pivot_x,
                "pivot_unidade_x": self.pivot_unidade_x,
                "pivot_y": self.pivot_y,
                "pivot_unidade_y": self.pivot_unidade_y,
                "minimo": self.minimo, "maximo": self.maximo,
                "tipo": self.tipo}

    @staticmethod
    def from_dict(dados: dict) -> RigJoint:
        if not isinstance(dados, dict):
            raise ErroELiXX("Junta precisa de dicionário.")
        return RigJoint(
            dados.get("nome", ""), dados.get("parent", ""),
            dados.get("child", ""),
            pivot_x=dados.get("pivot_x", 50.0),
            pivot_unidade_x=dados.get("pivot_unidade_x", "%"),
            pivot_y=dados.get("pivot_y", 50.0),
            pivot_unidade_y=dados.get("pivot_unidade_y", "%"),
            minimo=dados.get("minimo"), maximo=dados.get("maximo"),
            tipo=dados.get("tipo", "pivo"))

    def __repr__(self) -> str:
        return f"RigJoint({self.nome}: {self.parent}→{self.child})"


class RigPart:
    """Parte do rig: bounds local + pivô + junta + camada + máscara."""

    def __init__(self, part_id: str, tipo: str = "desconhecido",
                 bounds: Bounds2D | None = None,
                 parent_id: str | None = None,
                 pivot_x: float = 50.0, pivot_unidade_x: str = "%",
                 pivot_y: float = 50.0, pivot_unidade_y: str = "%",
                 joint: RigJoint | None = None,
                 z: int = 0, mask_id: str | None = None,
                 confianca: float | None = None,
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(part_id)
        self.tipo = str(tipo).strip() or "desconhecido"
        if bounds is None:
            bounds = Bounds2D(0.0, 0.0, 0.0, 0.0)
        self.bounds = _validar_bounds(
            bounds if bounds is not None
            else Bounds2D(0.0, 0.0, 0.0, 0.0),
            f"parte {self.id}")
        self.parent_id = (str(parent_id).strip() or None
                          if parent_id is not None else None)
        if self.parent_id == self.id:
            raise ErroELiXX(f'Parte "{self.id}": pai de si mesma.')
        self.pivot_x = _finito(pivot_x, f"pivô x de {self.id}")
        self.pivot_y = _finito(pivot_y, f"pivô y de {self.id}")
        for unid, eixo in ((pivot_unidade_x, "x"), (pivot_unidade_y, "y")):
            if unid not in ("%", "px"):
                raise ErroELiXX(f'Parte "{self.id}": pivô {eixo} '
                                 "inválido (%, px).")
        self.pivot_unidade_x = pivot_unidade_x
        self.pivot_unidade_y = pivot_unidade_y
        if joint is not None and not isinstance(joint, RigJoint):
            raise ErroELiXX(f'Parte "{self.id}": joint de RigJoint.')
        self.joint = joint
        try:
            self.z = int(z)
        except (TypeError, ValueError):
            raise ErroELiXX(f'Parte "{self.id}": z inteiro.')
        self.mask_id = (str(mask_id).strip() or None
                        if mask_id is not None else None)
        self.confianca = _confianca(confianca)
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Parte "{self.id}": metadata inválida.')
        self.metadata = meta

    def to_dict(self) -> dict:
        dados = {"id": self.id, "tipo": self.tipo,
                 "bounds": _bounds_dict(self.bounds),
                 "parent_id": self.parent_id,
                 "pivot_x": self.pivot_x,
                 "pivot_unidade_x": self.pivot_unidade_x,
                 "pivot_y": self.pivot_y,
                 "pivot_unidade_y": self.pivot_unidade_y,
                 "joint": self.joint.to_dict()
                 if self.joint is not None else None,
                 "z": self.z, "mask_id": self.mask_id,
                 "confianca": self.confianca,
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX(f'Parte "{self.id}" não serializável.')
        return dados

    @staticmethod
    def from_dict(dados: dict) -> RigPart:
        if not isinstance(dados, dict):
            raise ErroELiXX("Parte do rig precisa de dicionário.")
        bruto_joint = dados.get("joint")
        return RigPart(
            dados.get("id", ""), tipo=dados.get("tipo",
                                                "desconhecido"),
            bounds=_bounds_de(dados.get("bounds") or {},
                              dados.get("id", "?")),
            parent_id=dados.get("parent_id"),
            pivot_x=dados.get("pivot_x", 50.0),
            pivot_unidade_x=dados.get("pivot_unidade_x", "%"),
            pivot_y=dados.get("pivot_y", 50.0),
            pivot_unidade_y=dados.get("pivot_unidade_y", "%"),
            joint=(RigJoint.from_dict(bruto_joint)
                   if bruto_joint is not None else None),
            z=dados.get("z", 0), mask_id=dados.get("mask_id"),
            confianca=dados.get("confianca"),
            metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"RigPart({self.tipo} {self.id})"


class RigLayer:
    """Ordem de desenho de uma parte (sem compositor)."""

    def __init__(self, layer_id: str, parte_id: str, ordem: int = 0,
                 asset: str | None = None,
                 visivel: bool = True) -> None:
        self.id = _id_valido(layer_id, "id da camada")
        self.parte_id = _id_valido(parte_id, "parte da camada")
        try:
            self.ordem = int(ordem)
        except (TypeError, ValueError):
            raise ErroELiXX(f'Camada "{self.id}": ordem inteira.')
        self.asset = (str(asset) if asset is not None else None)
        self.visivel = bool(visivel)

    def to_dict(self) -> dict:
        return {"id": self.id, "parte_id": self.parte_id,
                "ordem": self.ordem, "asset": self.asset,
                "visivel": self.visivel}

    @staticmethod
    def from_dict(dados: dict) -> RigLayer:
        if not isinstance(dados, dict):
            raise ErroELiXX("Camada precisa de dicionário.")
        return RigLayer(dados.get("id", ""),
                        dados.get("parte_id", ""),
                        ordem=dados.get("ordem", 0),
                        asset=dados.get("asset"),
                        visivel=dados.get("visivel", True))

    def __repr__(self) -> str:
        return f"RigLayer({self.id}→{self.parte_id} #{self.ordem})"


class RigView:
    """Vista 2D alternativa do mesmo personagem (frente/costas/...)."""

    def __init__(self, nome: str, imagem_ref: str | None = None,
                 partes_visiveis: list | None = None,
                 metadata: dict | None = None) -> None:
        vista = str(nome).strip().lower()
        if vista not in VISTAS:
            raise ErroELiXX(f'Vista "{nome}" inválida '
                            f'({", ".join(VISTAS)}).')
        self.nome = vista
        self.imagem_ref = (str(imagem_ref)
                           if imagem_ref is not None else None)
        self.partes_visiveis = _ordenado(
            str(p).strip() for p in (partes_visiveis or [])
            if str(p).strip())
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Vista "{self.nome}": metadata inválida.')
        self.metadata = meta

    def to_dict(self) -> dict:
        return {"nome": self.nome, "imagem_ref": self.imagem_ref,
                "partes_visiveis": list(self.partes_visiveis),
                "metadata": dict(self.metadata)}

    @staticmethod
    def from_dict(dados: dict) -> RigView:
        if not isinstance(dados, dict):
            raise ErroELiXX("Vista precisa de dicionário.")
        return RigView(dados.get("nome", ""),
                       imagem_ref=dados.get("imagem_ref"),
                       partes_visiveis=dados.get("partes_visiveis")
                       or [],
                       metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"RigView({self.nome})"


class RigExpression:
    """Expressão modular: {parte → {prop → valor}} (combinável)."""

    def __init__(self, nome: str, ajustes: dict | None = None) -> None:
        self.nome = _id_valido(nome, "nome da expressão")
        self.ajustes = _normalizar_ajustes(
            ajustes, f"expressão {self.nome}")

    def combinar(self, outra: RigExpression,
                 nome: str = "") -> RigExpression:
        """Funde ajustes (última vence por parte/prop; documentado)."""
        if not isinstance(outra, RigExpression):
            raise ErroELiXX("combinar espera RigExpression.")
        fundido = {p: dict(v) for p, v in self.ajustes.items()}
        for parte, props in outra.ajustes.items():
            fundido.setdefault(parte, {}).update(props)
        return RigExpression(nome or f"{self.nome}+{outra.nome}",
                             fundido)

    def to_dict(self) -> dict:
        return {"nome": self.nome,
                "ajustes": {p: dict(v)
                            for p, v in self.ajustes.items()}}

    @staticmethod
    def from_dict(dados: dict) -> RigExpression:
        if not isinstance(dados, dict):
            raise ErroELiXX("Expressão precisa de dicionário.")
        return RigExpression(dados.get("nome", ""),
                             dict(dados.get("ajustes") or {}))

    def __repr__(self) -> str:
        return f"RigExpression({self.nome})"


class RigPose:
    """Pose do rig: {parte → {prop → valor}} (+ expressão opcional)."""

    def __init__(self, nome: str, ajustes: dict | None = None,
                 expressao: str | None = None) -> None:
        self.nome = _id_valido(nome, "nome da pose")
        self.ajustes = _normalizar_ajustes(ajustes,
                                           f"pose {self.nome}")
        self.expressao = (str(expressao).strip() or None
                          if expressao is not None else None)

    def to_dict(self) -> dict:
        return {"nome": self.nome,
                "ajustes": {p: dict(v)
                            for p, v in self.ajustes.items()},
                "expressao": self.expressao}

    @staticmethod
    def from_dict(dados: dict) -> RigPose:
        if not isinstance(dados, dict):
            raise ErroELiXX("Pose precisa de dicionário.")
        return RigPose(dados.get("nome", ""),
                       dict(dados.get("ajustes") or {}),
                       expressao=dados.get("expressao"))

    def __repr__(self) -> str:
        return f"RigPose({self.nome})"


# ----- CharacterRig -----

class CharacterRig:
    """Rig 2D: partes + joints + camadas + máscaras + views + poses."""

    def __init__(self, rig_id: str, nome: str = "",
                 avisos: list | None = None,
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(rig_id, "id do rig")
        self.nome = str(nome or "")
        self._partes: dict[str, RigPart] = {}
        self._ordem: list[str] = []
        self._mascaras: dict[str, CharacterMask] = {}
        self._camadas: dict[str, RigLayer] = {}
        self._views: dict[str, RigView] = {}
        self._expressoes: dict[str, RigExpression] = {}
        self._poses: dict[str, RigPose] = {}
        self.avisos = []
        for a in (avisos or []):
            if not isinstance(a, dict) or not _e_dado(a):
                raise ErroELiXX("Aviso precisa de dicionário JSON.")
            self.avisos.append(dict(a))
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX("Metadata do rig inválida.")
        self.metadata = meta

    def __len__(self) -> int:
        return len(self._partes)

    def __contains__(self, part_id: str) -> bool:
        return str(part_id) in self._partes

    # ----- partes -----

    def adicionar_parte(self, parte: RigPart) -> RigPart:
        if not isinstance(parte, RigPart):
            raise ErroELiXX("adicionar_parte espera RigPart.")
        if parte.id in self._partes:
            raise ErroELiXX(f'Parte "{parte.id}" duplicada no rig.')
        if len(self._partes) >= MAX_PARTES:
            raise ErroELiXX(f'Rig além de {MAX_PARTES} partes.')
        if (parte.parent_id is not None
                and parte.parent_id not in self._partes):
            raise ErroELiXX(f'Parte "{parte.id}": pai '
                            f'"{parte.parent_id}" ausente.')
        self._partes[parte.id] = parte
        self._ordem.append(parte.id)
        erro = self._ciclo(parte.id)
        if erro is not None:
            del self._partes[parte.id]
            self._ordem.remove(parte.id)
            raise ErroELiXX(erro)
        return parte

    def obter_parte(self, part_id: str) -> RigPart:
        try:
            return self._partes[str(part_id)]
        except KeyError:
            raise ErroELiXX(f'Parte "{part_id}" ausente no rig.')

    por_id = obter_parte

    def listar_partes(self) -> list[RigPart]:
        return [self._partes[pid] for pid in self._ordem]

    def filhos(self, part_id: str) -> list[RigPart]:
        self.obter_parte(part_id)
        return [self._partes[pid] for pid in self._ordem
                if self._partes[pid].parent_id == str(part_id)]

    def ancestrais(self, part_id: str) -> list[RigPart]:
        atual = self.obter_parte(part_id)
        saida, vistos = [], {atual.id}
        while atual.parent_id is not None:
            pai = self.obter_parte(atual.parent_id)
            if pai.id in vistos:
                raise ErroELiXX(f'Ciclo envolvendo "{pai.id}".')
            vistos.add(pai.id)
            saida.append(pai)
            atual = pai
        return saida

    def _ciclo(self, inicio: str) -> str | None:
        vistos, atual = set(), inicio
        while atual is not None:
            if atual in vistos:
                return (f'Ciclo na hierarquia envolvendo "{atual}" '
                        "(recusado).")
            vistos.add(atual)
            parte = self._partes.get(atual)
            if parte is None:
                return None
            atual = parte.parent_id
            if len(vistos) > MAX_PROFUNDIDADE_RIG + 4:
                return (f'Hierarquia além de {MAX_PROFUNDIDADE_RIG} '
                        "níveis.")
        return None

    # ----- resto do rig -----

    def adicionar_mascara(self, mascara: CharacterMask) -> CharacterMask:
        if not isinstance(mascara, CharacterMask):
            raise ErroELiXX("adicionar_mascara espera CharacterMask.")
        if mascara.id in self._mascaras:
            raise ErroELiXX(f'Máscara "{mascara.id}" duplicada.')
        if mascara.parte_id not in self._partes:
            raise ErroELiXX(f'Máscara "{mascara.id}": parte '
                            f'"{mascara.parte_id}" ausente.')
        self._mascaras[mascara.id] = mascara
        return mascara

    def adicionar_camada(self, camada: RigLayer) -> RigLayer:
        if not isinstance(camada, RigLayer):
            raise ErroELiXX("adicionar_camada espera RigLayer.")
        if camada.id in self._camadas:
            raise ErroELiXX(f'Camada "{camada.id}" duplicada.')
        if camada.parte_id not in self._partes:
            raise ErroELiXX(f'Camada "{camada.id}": parte '
                            f'"{camada.parte_id}" ausente.')
        self._camadas[camada.id] = camada
        return camada

    def adicionar_view(self, view: RigView) -> RigView:
        if not isinstance(view, RigView):
            raise ErroELiXX("adicionar_view espera RigView.")
        if view.nome in self._views:
            raise ErroELiXX(f'Vista "{view.nome}" duplicada.')
        for pid in view.partes_visiveis:
            if pid not in self._partes:
                raise ErroELiXX(f'Vista "{view.nome}": parte "{pid}" '
                                "ausente.")
        self._views[view.nome] = view
        return view

    def adicionar_expressao(self, expr: RigExpression) -> RigExpression:
        if not isinstance(expr, RigExpression):
            raise ErroELiXX("adicionar_expressao espera RigExpression.")
        if expr.nome in self._expressoes:
            raise ErroELiXX(f'Expressão "{expr.nome}" duplicada.')
        for pid in expr.ajustes:
            if pid not in self._partes:
                raise ErroELiXX(f'Expressão "{expr.nome}": parte '
                                f'"{pid}" ausente.')
        self._expressoes[expr.nome] = expr
        return expr

    def adicionar_pose(self, pose: RigPose) -> RigPose:
        if not isinstance(pose, RigPose):
            raise ErroELiXX("adicionar_pose espera RigPose.")
        if pose.nome in self._poses:
            raise ErroELiXX(f'Pose "{pose.nome}" duplicada.')
        for pid in pose.ajustes:
            if pid not in self._partes:
                raise ErroELiXX(f'Pose "{pose.nome}": parte "{pid}" '
                                "ausente.")
        if (pose.expressao is not None
                and pose.expressao not in self._expressoes):
            raise ErroELiXX(f'Pose "{pose.nome}": expressão '
                            f'"{pose.expressao}" ausente.')
        self._poses[pose.nome] = pose
        return pose

    def camadas_ordenadas(self) -> list[RigLayer]:
        pos = {pid: i for i, pid in enumerate(self._ordem)}
        return sorted(self._camadas.values(),
                      key=lambda c: (c.ordem,
                                     pos.get(c.parte_id, 0), c.id))

    # ----- validação / serialização -----

    def validar(self) -> dict:
        for pid in self._ordem:
            parte = self._partes[pid]
            if (parte.parent_id is not None
                    and parte.parent_id not in self._partes):
                return {"valido": False, "codigo": "referencia_invalida",
                        "motivo": f'Parte "{pid}": pai ausente.'}
            erro = self._ciclo(pid)
            if erro is not None:
                return {"valido": False, "codigo": "ciclo",
                        "motivo": erro}
        return {"valido": True, "codigo": "ok",
                "motivo": "Rig válido."}

    def to_dict(self) -> dict:
        dados = {"id": self.id, "nome": self.nome,
                 "partes": [self._partes[pid].to_dict()
                            for pid in self._ordem],
                 "mascaras": [self._mascaras[mid].to_dict()
                              for mid in _ordenado(self._mascaras)],
                 "camadas": [self._camadas[cid].to_dict()
                             for cid in _ordenado(self._camadas)],
                 "views": [self._views[v].to_dict()
                           for v in _ordenado(self._views)],
                 "expressoes": [self._expressoes[e].to_dict()
                                for e in _ordenado(self._expressoes)],
                 "poses": [self._poses[p].to_dict()
                           for p in _ordenado(self._poses)],
                 "avisos": [dict(a) for a in self.avisos],
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX("Rig não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> CharacterRig:
        if not isinstance(dados, dict):
            raise ErroELiXX("Rig precisa de dicionário.")
        rig = CharacterRig(dados.get("id", ""),
                           nome=dados.get("nome", ""),
                           avisos=dados.get("avisos") or [],
                           metadata=dict(dados.get("metadata") or {}))
        for item in (dados.get("partes") or []):
            rig.adicionar_parte(RigPart.from_dict(item))
        for item in (dados.get("mascaras") or []):
            rig.adicionar_mascara(CharacterMask.from_dict(item))
        for item in (dados.get("camadas") or []):
            rig.adicionar_camada(RigLayer.from_dict(item))
        for item in (dados.get("views") or []):
            rig.adicionar_view(RigView.from_dict(item))
        for item in (dados.get("expressoes") or []):
            rig.adicionar_expressao(RigExpression.from_dict(item))
        for item in (dados.get("poses") or []):
            rig.adicionar_pose(RigPose.from_dict(item))
        resultado = rig.validar()
        if not resultado["valido"]:
            raise ErroELiXX(f"Rig inválido: {resultado['motivo']}")
        return rig

    @staticmethod
    def from_json(texto: str) -> CharacterRig:
        if not isinstance(texto, str):
            raise ErroELiXX("Rig JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Rig JSON inválido: {exc}.")
        return CharacterRig.from_dict(dados)

    def __repr__(self) -> str:
        return (f"CharacterRig({self.id}: {len(self)} partes, "
                f"{len(self._poses)} poses)")


# ----- analyzers (provider-based; sem modelo pesado) -----

class CharacterAnalyzer:
    """Contrato: imagem/dados → CharacterAnalysis (sem IA obrigatória)."""

    def __init__(self, nome: str) -> None:
        self.nome = _id_valido(nome, "nome do analyzer")

    def disponivel(self) -> bool:
        return False

    def analisar(self, imagem=None) -> CharacterAnalysis:
        raise ErroELiXX(f'Analyzer "{self.nome}" não implementa '
                        "analisar().")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.nome})"


class NullCharacterAnalyzer(CharacterAnalyzer):
    """Analyzer nulo: análise vazia válida (com aviso honesto)."""

    def __init__(self, nome: str = "nulo") -> None:
        super().__init__(nome)

    def disponivel(self) -> bool:
        return True

    def analisar(self, imagem=None) -> CharacterAnalysis:
        return CharacterAnalysis(
            "vazia", [], origem="nulo",
            avisos=[{"codigo": "sem_deteccoes",
                     "motivo": "Nenhuma parte detectada; informe "
                               "imagem ou dados estruturados."}])

    def __repr__(self) -> str:
        return f"NullCharacterAnalyzer({self.nome})"


class MockCharacterAnalyzer(CharacterAnalyzer):
    """Analyzer de testes: serve detecções pré-estruturadas."""

    def __init__(self, deteccoes: list | None = None,
                 nome: str = "mock") -> None:
        super().__init__(nome)
        self._modelos = []
        for i, bruto in enumerate(deteccoes or []):
            if isinstance(bruto, CharacterPartDetection):
                self._modelos.append(bruto)
                continue
            if not isinstance(bruto, dict):
                raise ErroELiXX("Mock espera dicts ou "
                                "CharacterPartDetection.")
            copia = dict(bruto)
            copia.setdefault("id", f"parte_{i + 1:03d}")
            self._modelos.append(
                CharacterPartDetection.from_dict(copia))

    def disponivel(self) -> bool:
        return True

    def analisar(self, imagem=None) -> CharacterAnalysis:
        _ = imagem  # mock ignora a imagem (determinístico)
        return CharacterAnalysis("mock", list(self._modelos),
                                 origem="mock")

    def __repr__(self) -> str:
        return f"MockCharacterAnalyzer({self.nome})"


class StructuredCharacterAnalyzer(CharacterAnalyzer):
    """Analyzer de dados: dict {parts: [...]} → CharacterAnalysis."""

    def __init__(self, nome: str = "estruturado") -> None:
        super().__init__(nome)

    def disponivel(self) -> bool:
        return True

    def analisar(self, imagem=None) -> CharacterAnalysis:
        if not isinstance(imagem, dict):
            raise ErroELiXX(
                "Structured espera dicionário {parts: [...]} "
                f"(recebido {type(imagem).__name__}).")
        partes = imagem.get("parts")
        if not isinstance(partes, list):
            raise ErroELiXX('Structured espera chave "parts" com '
                            "lista.")
        dets = []
        for i, bruto in enumerate(partes):
            if not isinstance(bruto, dict):
                raise ErroELiXX(f"Parte {i}: dicionário.")
            copia = dict(bruto)
            copia.setdefault("id", f"parte_{i + 1:03d}")
            copia.setdefault("origem", "estruturado")
            b = copia.get("bounds")
            if b is None:
                copia["bounds"] = {
                    "x": copia.pop("x", 0.0), "y": copia.pop("y", 0.0),
                    "largura": copia.pop("largura", 0.0),
                    "altura": copia.pop("altura", 0.0)}
            dets.append(CharacterPartDetection.from_dict(copia))
        return CharacterAnalysis("estruturada", dets,
                                 origem="estruturado",
                                 metadata={"total": len(dets)})

    def __repr__(self) -> str:
        return f"StructuredCharacterAnalyzer({self.nome})"


def analise_de_percepcao(resultado, analysis_id: str = "percebida"):
    """F22 → análise: cada observação vira detecção (opcional).

    Preserva classe/confiança/origem/texto. Sem exigir F22 para o
    resto do fluxo (só conveniência).
    """
    from .percepcao import PerceptionResult

    if not isinstance(resultado, PerceptionResult):
        raise ErroELiXX("analise_de_percepcao espera "
                        "PerceptionResult.")
    dets = []
    for obs in resultado.observacoes:
        b = obs.bounds
        dets.append(CharacterPartDetection(
            obs.id, tipo=obs.classe,
            bounds=Bounds2D(b.x, b.y, b.largura, b.altura),
            confianca=obs.confianca, texto=obs.texto,
            origem=obs.origem,
            metadata={"tipo_percebido": obs.tipo,
                      "track_id": obs.track_id}))
    return CharacterAnalysis(analysis_id, dets, origem="percepcao")


# ----- construir_rig (análise → rig) -----

def construir_rig(analise: CharacterAnalysis, rig_id: str = "rig",
                  nome: str = "") -> CharacterRig:
    """Modo automático/profissional: detecções → hierarquia + pivôs.

    Regras explícitas: `parent_id` da detecção vence; sem pai, a parte
    ancora na raiz auto-criada "corpo" (aviso `hierarquia_inferida` —
    honesto, sem fingir análise real). Pivô padrão: base-central
    (50%, 100%) para membros/cabeça, centro (50%, 50%) no resto.
    Junta padrão: pivo sem limites (limites são dados profissionais).
    """
    if not isinstance(analise, CharacterAnalysis):
        raise ErroELiXX("construir_rig espera CharacterAnalysis.")
    rig = CharacterRig(rig_id, nome=nome or analise.id,
                       avisos=[{"codigo": "fonte_analise",
                                "motivo": f"Rig derivado de "
                                          f'"{analise.id}" '
                                          f"({analise.origem})."}],
                       metadata={"analise": analise.id,
                                 "origem": analise.origem})
    if len(analise) == 0:
        rig.avisos.append({"codigo": "rig_vazio",
                           "motivo": "Análise sem partes; rig vazio."})
        return rig
    ids = {d.id for d in analise.deteccoes}
    precisa_raiz = any(d.parent_id is None or d.parent_id not in ids
                       for d in analise.deteccoes)
    if precisa_raiz:
        rig.adicionar_parte(RigPart(
            "corpo", tipo="corpo",
            bounds=Bounds2D(0.0, 0.0, 0.0, 0.0),
            metadata={"origem": "inferida",
                      "papel": "raiz de ancoragem"}))
        rig.avisos.append(
            {"codigo": "hierarquia_inferida",
             "motivo": "Partes sem pai ancoradas em 'corpo' (raiz "
                       "sintética; informe parent_id para rig "
                       "profissional)."})
    def _pai_de(det) -> str | None:
        if det.parent_id in ids:
            return det.parent_id
        return "corpo" if precisa_raiz else None
    pendentes = sorted(analise.deteccoes, key=lambda d: d.id)
    while pendentes:
        progresso = False
        for det in list(pendentes):
            pai = _pai_de(det)
            if pai is not None and pai not in rig:
                continue  # pai ainda não inserido: adia (ordem
                # alfabética não garante pais antes dos filhos)
            pivo_y = 100.0 if det.tipo in (
                "cabeca", "braco_esquerdo", "braco_direito",
                "antebraco_esquerdo", "antebraco_direito",
                "perna_esquerda", "perna_direita") else 50.0
            rig.adicionar_parte(RigPart(
                det.id, tipo=det.tipo, bounds=det.bounds,
                parent_id=pai, pivot_x=50.0, pivot_unidade_x="%",
                pivot_y=pivo_y, pivot_unidade_y="%",
                joint=(RigJoint(f"j_{det.id}", pai, det.id)
                       if pai is not None else None),
                confianca=det.confianca,
                metadata={"origem": det.origem,
                          "visibilidade": det.visibilidade}))
            for aviso in analise.avisos:
                if det.id in aviso.get("motivo", ""):
                    rig.avisos.append(dict(aviso))
            pendentes.remove(det)
            progresso = True
        if not progresso:
            ciclo = ", ".join(_ordenado(d.id for d in pendentes))
            raise ErroELiXX(
                f"Ciclo de parentesco entre detecções ({ciclo}; "
                "informe hierarquia acíclica).")
    for i, det in enumerate(sorted(analise.deteccoes,
                                   key=lambda d: d.id)):
        rig.adicionar_camada(RigLayer(f"cam_{det.id}", det.id,
                                     ordem=i))
    return rig


# ----- rig → F12 Character -----

def rig_para_personagem(rig: CharacterRig, nome: str) -> object:
    """CharacterRig → Character F12 (sem segundo sistema de puppet).

    Cada RigPart vira CharacterPart com NoVisual próprio (posição =
    origem local, pivô do rig); hierarquia pai/filhos preservada;
    joints viram Joint F12 (limites); RigPose vira Pose, RigExpression
    vira Pose expressiva; RigView.frente/costas/... viram
    representacoes (vista → asset). Pose "neutro" sempre incluída.
    """
    from .cena import NoVisual
    from .personagem import Character, CharacterPart, Joint, Pose

    if not isinstance(rig, CharacterRig):
        raise ErroELiXX("rig_para_personagem espera CharacterRig.")
    nome_txt = _id_valido(nome, "nome do personagem")
    nos: dict[str, object] = {}
    for parte in rig.listar_partes():
        nos[parte.id] = NoVisual(
            tipo="parte", nome=parte.id, x=parte.bounds.x,
            y=parte.bounds.y, largura=parte.bounds.largura,
            altura=parte.bounds.altura, pivo_x=parte.pivot_x,
            pivo_unidade_x=parte.pivot_unidade_x,
            pivo_y=parte.pivot_y,
            pivo_unidade_y=parte.pivot_unidade_y)
    partes: dict[str, CharacterPart] = {}
    for parte in rig.listar_partes():
        junta = None
        if parte.joint is not None:
            junta = Joint(parte.joint.nome, parte.id,
                          minimo=parte.joint.minimo,
                          maximo=parte.joint.maximo)
        partes[parte.id] = CharacterPart(
            parte.id, nos[parte.id], junta=junta,
            variantes={}, vistas={})
    raizes = [p for p in rig.listar_partes() if p.parent_id is None]
    no_raiz = nos[raizes[0].id] if raizes else NoVisual(
        tipo="personagem", nome=nome_txt)
    for parte in rig.listar_partes():
        atual = partes[parte.id]
        if parte.parent_id is not None:
            pai = partes[parte.parent_id]
            atual.pai = pai
            pai.filhos.append(atual)
        atual.raiz = no_raiz
    poses: dict[str, Pose] = {}
    for rp in sorted(rig._poses.values(), key=lambda p: p.nome):
        poses[rp.nome] = Pose(rp.nome, entradas={
            pid: dict(props) for pid, props in rp.ajustes.items()})
    for ex in sorted(rig._expressoes.values(), key=lambda e: e.nome):
        poses[ex.nome] = Pose(ex.nome, entradas={
            pid: dict(props) for pid, props in ex.ajustes.items()},
            expressao=True)
    if "neutro" not in poses:
        poses["neutro"] = Pose("neutro", entradas={})
    representacoes = {v.nome: v.imagem_ref
                      for v in rig._views.values()
                      if v.imagem_ref is not None}
    return Character(nome_txt, no_raiz, partes, poses,
                     representacoes=representacoes)


# ----- animações automáticas (definição estruturada; motor executa) -----

_AUTOMATICAS_DEFS = {
    "respirar": [("tronco", {"escala": (1.0, 1.03)}),
                 ("tronco", {"escala": (1.0, 1.0)})],
    "piscar": [("olhos", {"opacidade": 0.0}),
               ("olhos", {"opacidade": 1.0})],
    "olhar": [("cabeca", {"rotacao": 10.0}),
              ("cabeca", {"rotacao": -10.0}),
              ("cabeca", {"rotacao": 0.0})],
    "falar": [("boca", {"escala": (1.0, 0.6)}),
              ("boca", {"escala": (1.2, 1.0)}),
              ("boca", {"escala": (1.0, 1.0)})],
    "acenar": [("braco_direito", {"rotacao": 45.0}),
               ("braco_direito", {"rotacao": 0.0})],
    "andar": [("perna_esquerda", {"rotacao": 20.0}),
              ("perna_direita", {"rotacao": -20.0}),
              ("perna_esquerda", {"rotacao": 0.0}),
              ("perna_direita", {"rotacao": 0.0})],
    "parar": [],
    "balancar_cabelo": [("cabelo", {"rotacao": 8.0}),
                        ("cabelo", {"rotacao": -8.0}),
                        ("cabelo", {"rotacao": 0.0})],
}
"""Automáticas: [(parte, {prop: valor})] por passo. Só tocam partes
existentes no rig (passo sem alvo vira aviso, nunca erro)."""


def definir_automatica(rig: CharacterRig, nome: str):
    """Rig + nome → Gesture F12 (passos Pose; motor F11 executa).

    "IA prepara, motor executa": aqui só a definição estruturada.
    """
    from .personagem import Gesture, Pose

    if not isinstance(rig, CharacterRig):
        raise ErroELiXX("definir_automatica espera CharacterRig.")
    chave = str(nome).strip().lower()
    if chave not in _AUTOMATICAS_DEFS:
        raise ErroELiXX(f'Automática "{nome}" desconhecida '
                        f'({", ".join(AUTOMATICAS)}).')
    passos, pulados = [], []
    for i, (parte_id, props) in enumerate(_AUTOMATICAS_DEFS[chave]):
        if parte_id not in rig:
            pulados.append(parte_id)
            continue
        passos.append(Pose(f"{chave}_{i:02d}",
                           entradas={parte_id: dict(props)}))
    if pulados:
        rig.avisos.append({"codigo": "automatica_parcial",
                           "motivo": f'"{chave}": partes ausentes '
                                     f"ignoradas ({', '.join(_ordenado(set(pulados)))})."})
    return Gesture(chave, passos=passos, modo="sequencia")


# ----- debug -----

def debug_rigging(rig_ou_analise) -> str:
    """Texto legível: partes, hierarquia, pivôs, views, expressões."""
    if isinstance(rig_ou_analise, CharacterAnalysis):
        ana = rig_ou_analise
        linhas = [f"CharacterAnalysis {ana.id}: {len(ana)} partes "
                   f"(origem {ana.origem}), {len(ana.avisos)} avisos"]
        for d in sorted(ana.deteccoes, key=lambda x: x.id):
            b = d.bounds
            linhas.append(
                f"  {d.id} [{d.tipo}] pos=({b.x:g},{b.y:g}) "
                f"tam={b.largura:g}x{b.altura:g} conf={d.confianca} "
                f"pai={d.parent_id} vis={d.visibilidade}")
        for a in ana.avisos:
            linhas.append(f"  AVISO {a.get('codigo')}: {a.get('motivo')}")
        return "\n".join(linhas)
    rig = rig_ou_analise
    linhas = [f"CharacterRig {rig.id}: {len(rig)} partes, "
               f"{len(rig._poses)} poses, "
               f"{len(rig._expressoes)} expressões, "
               f"{len(rig._views)} vistas, {len(rig.avisos)} avisos"]
    linhas.append("HIERARQUIA:")
    for parte in rig.listar_partes():
        linhas.append(
            f"  {parte.id} [{parte.tipo}] pai={parte.parent_id} "
            f"pivo=({parte.pivot_x:g}{parte.pivot_unidade_x},"
            f"{parte.pivot_y:g}{parte.pivot_unidade_y}) z={parte.z}")
    if rig._views:
        linhas.append("VISTAS: " + ", ".join(
            _ordenado(rig._views)))
    if rig._expressoes:
        linhas.append("EXPRESSOES: " + ", ".join(
            _ordenado(rig._expressoes)))
    return "\n".join(linhas)
