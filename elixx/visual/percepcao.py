"""Visual Perception Core da ELiXX (Fase 22) — ver, estruturar, representar.

Transforma entrada visual estruturada em observações semânticas:

    ImageFrame ──→ PerceptionProvider ──→ PerceptionResult
        ──→ Geometry (F21, onde) ──→ Environment (F19, o que)
        ──→ World (F13, contexto)

PERCEPÇÃO NÃO É DECISÃO. O núcleo apenas observa: não clica, não
move, não digita, não planeja, não executa. Não chama modelos de
linguagem, não gera intenções, não alimenta o contexto de IA
sozinho.

O núcleo é INDEPENDENTE do detector: YOLO, OCR, acessibilidade e
HTML são providers (contratos), nunca o Core. Sem provider externo,
tudo funciona com Null/Mock (sem imagens reais nos testes).

Reuso (sem duplicar): Vector2/Point2D/Size2D (F10/F21), Bounds2D
(F13), GeometryMap/GeometryNode (F21), Environment/EnvironmentNode
(F19), World (F13). Sem Navigation/Motion novos, sem rede, sem
downloads de modelos, sem dependências pesadas obrigatórias.
"""
from __future__ import annotations

import json
import math

from ..erros import ErroELiXX
from .mundo import Bounds2D

__all__ = [
    "TIPOS_PERCEPCAO",
    "ORIGENS_PERCEPCAO",
    "MAX_OBSERVACOES",
    "MAX_DIMENSAO",
    "ImageFrame",
    "PerceptionObservation",
    "PerceptionResult",
    "PerceptionDelta",
    "PerceptionSnapshot",
    "PerceptionProvider",
    "NullPerceptionProvider",
    "MockPerceptionProvider",
    "YOLOProvider",
    "OCRProvider",
    "PerceptionRegistry",
    "percepcao_para_geometria",
    "percepcao_para_environment",
    "calcular_delta",
    "debug_percepcao",
]

TIPOS_PERCEPCAO = ("objeto", "texto", "regiao", "interface",
                   "personagem", "imagem", "icone", "botao", "entrada",
                   "link", "janela", "cursor", "desconhecido")
"""Tipos básicos. Extensível como dado: tipo novo segue representado,
nunca descartado (só estes têm mapeamento Environment dedicado)."""

ORIGENS_PERCEPCAO = ("mock", "nulo", "yolo", "ocr", "acessibilidade",
                     "html", "imagem", "detector")
"""Origens conhecidas. Origem nova segue como string opaca (preservada,
nunca apagada nas conversões)."""

MAX_OBSERVACOES = 100000
"""Teto anti-gigante (50000 observações passam; acima: erro claro)."""

MAX_DIMENSAO = 100000
"""Teto de largura/altura de frame e de coordenadas de bounds."""

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


def _confianca_valida(valor, o_que: str = "confiança") -> float | None:
    if valor is None:
        return None
    numero = _finito(valor, o_que)
    if not 0.0 <= numero <= 1.0:
        raise ErroELiXX(f'"{o_que}" precisa de 0..1 '
                        f"(recebido {numero:g}).")
    return numero


# ----- ImageFrame -----

class ImageFrame:
    """Entrada visual segura: metadados + referência; bytes nunca no JSON.

    `dados` (bytes) é opaco e opcional: fica fora de to_dict (só a
    contagem é serializada). Sem Pillow obrigatório: o núcleo aceita
    frames só com metadados ou vindos de providers.
    """

    def __init__(self, largura: int | float, altura: int | float,
                 formato: str = "desconhecido",
                 frame_id: str | None = None,
                 referencia: str | None = None,
                 dados: bytes | None = None) -> None:
        larg = _finito(largura, "largura do frame")
        alt = _finito(altura, "altura do frame")
        if larg <= 0 or alt <= 0:
            raise ErroELiXX("Frame precisa de largura e altura > 0 "
                            f"(recebido {larg:g}x{alt:g}).")
        if larg > MAX_DIMENSAO or alt > MAX_DIMENSAO:
            raise ErroELiXX(f"Frame gigante ({larg:g}x{alt:g}; teto "
                            f"{MAX_DIMENSAO}).")
        # Dimensões inteiras (pixels): fração é erro claro, não silêncio.
        if float(larg) != int(larg) or float(alt) != int(alt):
            raise ErroELiXX("Frame precisa de dimensões inteiras "
                            f"(recebido {larg:g}x{alt:g}).")
        self.largura = int(larg)
        self.altura = int(alt)
        self.formato = str(formato).strip() or "desconhecido"
        self.frame_id = (str(frame_id).strip() or None
                         if frame_id is not None else None)
        self.referencia = (str(referencia) if referencia is not None
                           else None)
        if dados is not None and not isinstance(dados, (bytes, bytearray)):
            raise ErroELiXX("Dados do frame precisam de bytes.")
        self.dados = bytes(dados) if dados is not None else None

    @property
    def tem_dados(self) -> bool:
        return self.dados is not None

    def to_dict(self) -> dict:
        return {"largura": self.largura, "altura": self.altura,
                "formato": self.formato, "frame_id": self.frame_id,
                "referencia": self.referencia,
                "tem_dados": self.tem_dados,
                "bytes": len(self.dados) if self.dados is not None else 0}

    @staticmethod
    def from_dict(dados: dict) -> ImageFrame:
        if not isinstance(dados, dict):
            raise ErroELiXX("Frame precisa de dicionário.")
        return ImageFrame(dados.get("largura", 0),
                          dados.get("altura", 0),
                          formato=dados.get("formato", "desconhecido"),
                          frame_id=dados.get("frame_id"),
                          referencia=dados.get("referencia"))

    def __repr__(self) -> str:
        return (f"ImageFrame({self.largura}x{self.altura} "
                f"{self.formato})")


# ----- PerceptionObservation -----

class PerceptionObservation:
    """Uma observação: classe + bounds + confiança + origem. Só dados."""

    def __init__(self, obs_id: str, classe: str = "desconhecido",
                 bounds: Bounds2D | None = None,
                 tipo: str = "objeto",
                 confianca: float | None = None,
                 texto: str | None = None,
                 origem: str = "detector",
                 track_id: str | None = None,
                 metadata: dict | None = None) -> None:
        self.id = _id_valido(obs_id)
        self.classe = str(classe).strip() or "desconhecido"
        if bounds is None:
            bounds = Bounds2D(0.0, 0.0, 0.0, 0.0)
        if not isinstance(bounds, Bounds2D):
            raise ErroELiXX(f'Observação "{self.id}": bounds precisa de '
                            "Bounds2D.")
        for campo in ("x", "y", "largura", "altura"):
            valor = _finito(getattr(bounds, campo),
                            f"{campo} da observação {self.id}")
            if abs(valor) > MAX_DIMENSAO:
                raise ErroELiXX(f'Observação "{self.id}": {campo} '
                                f"gigante ({valor:g}).")
        if bounds.largura < 0 or bounds.altura < 0:
            raise ErroELiXX(f'Observação "{self.id}": tamanho negativo.')
        self.bounds = bounds
        self.tipo = str(tipo).strip() or "objeto"
        self.confianca = _confianca_valida(confianca)
        self.texto = (str(texto) if texto is not None else None)
        self.origem = str(origem).strip() or "detector"
        self.track_id = (str(track_id).strip() or None
                         if track_id is not None else None)
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX(f'Observação "{self.id}": metadata inválida '
                            "(só JSON finito e raso).")
        self.metadata = meta

    def centro(self):
        return self.bounds.centro()

    def to_dict(self) -> dict:
        dados = {"id": self.id, "tipo": self.tipo,
                 "classe": self.classe,
                 "bounds": {"x": self.bounds.x, "y": self.bounds.y,
                            "largura": self.bounds.largura,
                            "altura": self.bounds.altura},
                 "confianca": self.confianca, "texto": self.texto,
                 "origem": self.origem, "track_id": self.track_id,
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX(f'Observação "{self.id}" não serializável.')
        return dados

    @staticmethod
    def from_dict(dados: dict) -> PerceptionObservation:
        if not isinstance(dados, dict):
            raise ErroELiXX("Observação precisa de dicionário.")
        b = dados.get("bounds") or {}
        if not isinstance(b, dict):
            raise ErroELiXX("Bounds da observação precisa de dicionário.")
        return PerceptionObservation(
            dados.get("id", ""), classe=dados.get("classe",
                                                  "desconhecido"),
            bounds=Bounds2D(b.get("x", 0.0), b.get("y", 0.0),
                            b.get("largura", 0.0),
                            b.get("altura", 0.0)),
            tipo=dados.get("tipo", "objeto"),
            confianca=dados.get("confianca"), texto=dados.get("texto"),
            origem=dados.get("origem", "detector"),
            track_id=dados.get("track_id"),
            metadata=dict(dados.get("metadata") or {}))

    def __repr__(self) -> str:
        return f"PerceptionObservation({self.classe} {self.id})"


# ----- PerceptionResult -----

class PerceptionResult:
    """Resultado de uma análise: observações + contexto do frame."""

    def __init__(self, largura_imagem: int | float,
                 altura_imagem: int | float,
                 origem: str = "detector",
                 observacoes: list | None = None,
                 timestamp: float | None = None,
                 frame_id: str | None = None,
                 avisos: list | None = None,
                 metadata: dict | None = None) -> None:
        larg = _finito(largura_imagem, "largura da imagem")
        alt = _finito(altura_imagem, "altura da imagem")
        if larg <= 0 or alt <= 0:
            raise ErroELiXX("Resultado precisa de dimensões > 0.")
        if larg > MAX_DIMENSAO or alt > MAX_DIMENSAO:
            raise ErroELiXX("Resultado com dimensões gigantes.")
        self.largura_imagem = larg
        self.altura_imagem = alt
        self.origem = str(origem).strip() or "detector"
        obs = list(observacoes or [])
        if len(obs) > MAX_OBSERVACOES:
            raise ErroELiXX(f"Resultado com {len(obs)} observações "
                            f"(teto {MAX_OBSERVACOES}).")
        for o in obs:
            if not isinstance(o, PerceptionObservation):
                raise ErroELiXX("observacoes espera "
                                "PerceptionObservation.")
        vistos = set()
        for o in obs:
            if o.id in vistos:
                raise ErroELiXX(f'Observação "{o.id}" duplicada no '
                                "resultado.")
            vistos.add(o.id)
        self.observacoes = obs
        if timestamp is not None:
            timestamp = _finito(timestamp, "timestamp")
        self.timestamp = timestamp
        self.frame_id = (str(frame_id).strip() or None
                         if frame_id is not None else None)
        self.avisos = []
        for a in (avisos or []):
            if not isinstance(a, dict) or not _e_dado(a):
                raise ErroELiXX("Aviso precisa de dicionário JSON.")
            self.avisos.append(dict(a))
        meta = dict(metadata or {})
        if not _e_dado(meta):
            raise ErroELiXX("Metadata do resultado inválida.")
        self.metadata = meta

    def __len__(self) -> int:
        return len(self.observacoes)

    def __contains__(self, obs_id: str) -> bool:
        return any(o.id == str(obs_id) for o in self.observacoes)

    def por_id(self, obs_id: str) -> PerceptionObservation:
        for o in self.observacoes:
            if o.id == str(obs_id):
                return o
        raise ErroELiXX(f'Observação "{obs_id}" ausente no resultado.')

    def por_classe(self, classe: str) -> list[PerceptionObservation]:
        return [o for o in self.observacoes if o.classe == classe]

    def classes(self) -> list[str]:
        return _ordenado({o.classe for o in self.observacoes})

    def analisar_sobreposicoes(self) -> list[dict]:
        """Pares que se sobrepõem (explícito; O(n²) documentado).

        Não roda sozinho na construção: para 50k observações seria
        inviável. O chamador decide quando vale a pena.
        """
        pares = []
        obs = self.observacoes
        for i in range(len(obs)):
            for j in range(i + 1, len(obs)):
                if obs[i].bounds.sobrepoe(obs[j].bounds):
                    pares.append({"a": obs[i].id, "b": obs[j].id,
                                  "codigo": "sobreposicao"})
        return pares

    def to_dict(self) -> dict:
        dados = {"largura_imagem": self.largura_imagem,
                 "altura_imagem": self.altura_imagem,
                 "origem": self.origem,
                 "observacoes": [o.to_dict() for o in self.observacoes],
                 "timestamp": self.timestamp, "frame_id": self.frame_id,
                 "avisos": [dict(a) for a in self.avisos],
                 "metadata": dict(self.metadata)}
        if not _e_dado(dados):
            raise ErroELiXX("Resultado não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> PerceptionResult:
        if not isinstance(dados, dict):
            raise ErroELiXX("Resultado precisa de dicionário.")
        obs_txt = dados.get("observacoes") or []
        if not isinstance(obs_txt, list):
            raise ErroELiXX("observacoes precisa de lista.")
        return PerceptionResult(
            dados.get("largura_imagem", 0),
            dados.get("altura_imagem", 0),
            origem=dados.get("origem", "detector"),
            observacoes=[PerceptionObservation.from_dict(o)
                         for o in obs_txt],
            timestamp=dados.get("timestamp"),
            frame_id=dados.get("frame_id"),
            avisos=dados.get("avisos") or [],
            metadata=dict(dados.get("metadata") or {}))

    @staticmethod
    def from_json(texto: str) -> PerceptionResult:
        if not isinstance(texto, str):
            raise ErroELiXX("Resultado JSON precisa de texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Resultado JSON inválido: {exc}.")
        return PerceptionResult.from_dict(dados)

    def snapshot(self) -> PerceptionSnapshot:
        return PerceptionSnapshot(self.to_dict())

    def __repr__(self) -> str:
        return (f"PerceptionResult({len(self)} obs, "
                f"{self.origem})")


# ----- PerceptionDelta -----

class PerceptionDelta:
    """Diferença determinística entre dois resultados (por id estável).

    Sem id estável não há identidade persistente inventada: ids
    diferentes = observações diferentes (documentado).
    """

    def __init__(self, adicionados: list, removidos: list,
                 alterados: list, mantidos: list) -> None:
        self.adicionados = _ordenado(str(i) for i in adicionados)
        self.removidos = _ordenado(str(i) for i in removidos)
        self.alterados = _ordenado(str(i) for i in alterados)
        self.mantidos = _ordenado(str(i) for i in mantidos)

    def to_dict(self) -> dict:
        return {"adicionados": list(self.adicionados),
                "removidos": list(self.removidos),
                "alterados": list(self.alterados),
                "mantidos": list(self.mantidos)}

    def __repr__(self) -> str:
        return (f"PerceptionDelta(+{len(self.adicionados)} "
                f"-{len(self.removidos)} ~{len(self.alterados)} "
                f"={len(self.mantidos)})")


def _assinatura(obs: PerceptionObservation) -> tuple:
    b = obs.bounds
    return (obs.classe, obs.tipo, b.x, b.y, b.largura, b.altura,
            obs.confianca, obs.texto)


def calcular_delta(anterior: PerceptionResult,
                   atual: PerceptionResult) -> PerceptionDelta:
    """Compara por id: adicionados/removidos/alterados/mantidos."""
    if not isinstance(anterior, PerceptionResult) or not isinstance(
            atual, PerceptionResult):
        raise ErroELiXX("Delta espera dois PerceptionResult.")
    ids_ant = {o.id for o in anterior.observacoes}
    ids_atu = {o.id for o in atual.observacoes}
    adicionados = ids_atu - ids_ant
    removidos = ids_ant - ids_atu
    alterados, mantidos = [], []
    mapa_ant = {o.id: o for o in anterior.observacoes}
    mapa_atu = {o.id: o for o in atual.observacoes}
    for nid in ids_ant & ids_atu:
        if _assinatura(mapa_ant[nid]) == _assinatura(mapa_atu[nid]):
            mantidos.append(nid)
        else:
            alterados.append(nid)
    return PerceptionDelta(list(adicionados), list(removidos),
                           alterados, mantidos)


# ----- PerceptionSnapshot (imutável) -----

class PerceptionSnapshot:
    """Foto imutável do resultado (congela via JSON)."""

    def __init__(self, dados: dict) -> None:
        if not isinstance(dados, dict) or not _e_dado(dados):
            raise ErroELiXX("Snapshot precisa de dicionário JSON.")
        self._dados = json.loads(json.dumps(dados, sort_keys=True))

    def ids(self) -> list[str]:
        return _ordenado(o["id"] for o in self._dados.get(
            "observacoes", []))

    def por_id(self, obs_id: str) -> dict:
        for o in self._dados.get("observacoes", []):
            if o["id"] == str(obs_id):
                return dict(o)
        raise ErroELiXX(f'Observação "{obs_id}" ausente no snapshot.')

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self._dados, sort_keys=True))

    def __repr__(self) -> str:
        return f"PerceptionSnapshot({len(self.ids())} obs)"


# ----- PerceptionProvider (abstração) -----

class PerceptionProvider:
    """Contrato mínimo: nome + disponibilidade + capacidades + análise."""

    def __init__(self, nome: str) -> None:
        self.nome = _id_valido(nome, "nome do provider")

    def disponivel(self) -> bool:
        """True quando pronto para analisar (sem efeitos)."""
        return False

    def capacidades(self) -> list[str]:
        """Capacidades declaradas (ex. ["detectar", "texto"])."""
        return []

    def analisar(self, frame=None,
                 observacoes: list | None = None) -> PerceptionResult:
        """Analisa e retorna PerceptionResult (nunca executa ações)."""
        raise ErroELiXX(f'Provider "{self.nome}" não implementa '
                        "analisar().")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.nome})"


class NullPerceptionProvider(PerceptionProvider):
    """Provider nulo: observa nada (resultado vazio, válido)."""

    def __init__(self, nome: str = "nulo", largura: int = 1920,
                 altura: int = 1080) -> None:
        super().__init__(nome)
        self._largura = int(largura)
        self._altura = int(altura)

    def disponivel(self) -> bool:
        return True

    def analisar(self, frame=None,
                 observacoes: list | None = None) -> PerceptionResult:
        larg, alt = self._largura, self._altura
        if frame is not None:
            larg, alt = frame.largura, frame.altura
        return PerceptionResult(larg, alt, origem="nulo",
                                frame_id=getattr(frame, "frame_id",
                                                 None))


class MockPerceptionProvider(PerceptionProvider):
    """Provider de testes: serve observações pré-estruturadas."""

    def __init__(self, observacoes: list | None = None,
                 nome: str = "mock", largura: int = 1920,
                 altura: int = 1080,
                 origem: str = "mock") -> None:
        super().__init__(nome)
        self._modelos = []
        for i, bruto in enumerate(observacoes or []):
            if isinstance(bruto, PerceptionObservation):
                self._modelos.append(bruto)
                continue
            if not isinstance(bruto, dict):
                raise ErroELiXX("Mock espera dicts ou "
                                "PerceptionObservation.")
            copia = dict(bruto)
            copia.setdefault("id", f"obj_{i + 1:03d}")
            copia.setdefault("origem", origem)
            b = copia.get("bounds")
            if b is None:
                copia["bounds"] = {
                    "x": copia.pop("x", 0.0), "y": copia.pop("y", 0.0),
                    "largura": copia.pop("largura", 0.0),
                    "altura": copia.pop("altura", 0.0)}
            self._modelos.append(
                PerceptionObservation.from_dict(copia))
        self._largura = int(largura)
        self._altura = int(altura)
        self._origem = str(origem)

    def disponivel(self) -> bool:
        return True

    def capacidades(self) -> list[str]:
        return ["detectar"]

    def analisar(self, frame=None,
                 observacoes: list | None = None) -> PerceptionResult:
        base = (list(observacoes) if observacoes is not None
                else list(self._modelos))
        servidas = []
        for o in base:
            servidas.append(o if isinstance(o, PerceptionObservation)
                            else PerceptionObservation.from_dict(o))
        larg, alt = self._largura, self._altura
        fid = None
        if frame is not None:
            larg, alt = frame.largura, frame.altura
            fid = frame.frame_id
        return PerceptionResult(larg, alt, origem=self._origem,
                                observacoes=servidas, frame_id=fid)


class YOLOProvider(PerceptionProvider):
    """CONTRATO YOLO (opcional): detector pesado, nunca obrigatório.

    - `disponivel()` = True só com biblioteca E modelo local válidos.
    - Nunca instala dependências, nunca baixa modelos, nunca usa rede.
    - Sem ambos: `analisar()` retorna erro claro (não quebra o ELiXX).
    """

    def __init__(self, nome: str = "yolo",
                 modelo: str | None = None) -> None:
        super().__init__(nome)
        self.modelo = (str(modelo) if modelo is not None else None)

    def disponivel(self) -> bool:
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            return False
        return self.modelo is not None

    def capacidades(self) -> list[str]:
        return ["detectar"] if self.disponivel() else []

    def analisar(self, frame=None,
                 observacoes: list | None = None) -> PerceptionResult:
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            raise ErroELiXX(
                'YOLO indisponível: biblioteca "ultralytics" ausente. '
                "O ELiXX continua funcionando com Null/Mock; instale "
                "e informe o modelo local para ativar.")
        if self.modelo is None:
            raise ErroELiXX(
                "YOLO sem modelo local: informe o caminho do arquivo "
                "(.pt) existente. Nada será baixado automaticamente.")
        raise ErroELiXX(
            "YOLOProvider é contrato nesta fase: inferência real "
            "será ligada em fase futura (sem rede, só modelo local).")


class OCRProvider(PerceptionProvider):
    """CONTRATO OCR (não implementado): produzirá tipo=texto futuramente."""

    def __init__(self, nome: str = "ocr") -> None:
        super().__init__(nome)

    def disponivel(self) -> bool:
        return False

    def analisar(self, frame=None,
                 observacoes: list | None = None) -> PerceptionResult:
        raise ErroELiXX(
            "OCR indisponível nesta fase (só contrato). Use Null/Mock.")


# ----- PerceptionRegistry -----

class PerceptionRegistry:
    """Registro explícito de providers (sem imports automáticos)."""

    def __init__(self) -> None:
        self._providers: dict[str, PerceptionProvider] = {}

    def registrar(self, provider: PerceptionProvider) -> PerceptionProvider:
        if not isinstance(provider, PerceptionProvider):
            raise ErroELiXX("registrar espera PerceptionProvider.")
        if provider.nome in self._providers:
            raise ErroELiXX(f'Provider "{provider.nome}" já '
                            "registrado.")
        self._providers[provider.nome] = provider
        return provider

    def obter(self, nome: str) -> PerceptionProvider:
        try:
            return self._providers[str(nome)]
        except KeyError:
            raise ErroELiXX(f'Provider "{nome}" não registrado.')

    def listar(self) -> list[str]:
        return _ordenado(self._providers)

    def remover(self, nome: str) -> PerceptionProvider:
        provider = self.obter(nome)
        del self._providers[provider.nome]
        return provider

    def __contains__(self, nome: str) -> bool:
        return str(nome) in self._providers

    def __repr__(self) -> str:
        return f"PerceptionRegistry({len(self._providers)} providers)"


# ----- integrações (só fatos; sem decisão, sem ação) -----

# classe percebida → tipo Environment (desconhecida segue como dado).
_MAPA_ENVIRONMENT = {
    "botao": "botao", "entrada": "entrada", "link": "link",
    "imagem": "imagem", "icone": "imagem", "texto": "texto",
    "janela": "janela", "regiao": "regiao",
}


def percepcao_para_geometria(resultado: PerceptionResult,
                             nome: str = "percebido"):
    """PerceptionResult → GeometryMap (posição vem da observação).

    Metadata preserva classe/confiança/origem/texto/track_id.
    Nenhuma Surface inventada; nenhuma interação criada.
    """
    from .geometria import GeometryMap, GeometryNode

    if not isinstance(resultado, PerceptionResult):
        raise ErroELiXX("percepcao_para_geometria espera "
                        "PerceptionResult.")
    mapa = GeometryMap(nome)
    for obs in resultado.observacoes:
        b = obs.bounds
        mapa.adicionar(GeometryNode(
            obs.id, Bounds2D(b.x, b.y, b.largura, b.altura),
            metadata={"classe": obs.classe, "tipo_percebido": obs.tipo,
                      "confianca": obs.confianca,
                      "origem": obs.origem, "texto": obs.texto,
                      "track_id": obs.track_id}))
    return mapa


def percepcao_para_environment(resultado: PerceptionResult,
                               env_id: str = "percebido",
                               nome: str = ""):
    """PerceptionResult → Environment (sugestão estrutural).

    Classe vira tipo (desconhecida → "desconhecido", preservada em
    atributos). NENHUMA interação é criada: detectar um botão não
    significa "pode clicar" — só "há algo detectado como botão".
    """
    from .ambiente import Environment, EnvironmentNode

    if not isinstance(resultado, PerceptionResult):
        raise ErroELiXX("percepcao_para_environment espera "
                        "PerceptionResult.")
    env = Environment(env_id, nome=nome, tipo="generico",
                      largura=float(resultado.largura_imagem),
                      altura=float(resultado.altura_imagem),
                      metadados={"fonte": "percepcao",
                                 "origem": resultado.origem,
                                 "frame_id": resultado.frame_id})
    for obs in resultado.observacoes:
        b = obs.bounds
        tipo = _MAPA_ENVIRONMENT.get(obs.classe, "desconhecido")
        env.adicionar_no(EnvironmentNode(
            obs.id, nome=obs.texto or obs.classe, tipo=tipo,
            x=b.x, y=b.y, largura=b.largura, altura=b.altura,
            interativo=False, texto=obs.texto,
            atributos={"classe": obs.classe,
                       "tipo_percebido": obs.tipo,
                       "confianca": obs.confianca,
                       "origem": obs.origem,
                       "track_id": obs.track_id}))
    resultado_validacao = env.validar()
    if not resultado_validacao["valido"]:
        raise ErroELiXX("Environment derivado inválido: "
                        f"{resultado_validacao['motivo']}")
    return env


# ----- debug -----

def debug_percepcao(resultado_ou_snapshot) -> str:
    """Texto legível: origem, provider, classes, bounds, confiança."""
    if isinstance(resultado_ou_snapshot, PerceptionSnapshot):
        dados = resultado_ou_snapshot.to_dict()
        obs_txt = dados.get("observacoes", [])
        linhas = [f"PerceptionSnapshot: {len(obs_txt)} observações "
                   f"(origem {dados.get('origem')})"]
        for o in sorted(obs_txt, key=lambda d: d["id"]):
            b = o["bounds"]
            linhas.append(
                f"  {o['id']} [{o['classe']}/{o['tipo']}] "
                f"pos=({b['x']:g},{b['y']:g}) "
                f"tam={b['largura']:g}x{b['altura']:g} "
                f"conf={o['confianca']} origem={o['origem']}")
        return "\n".join(linhas)
    res = resultado_ou_snapshot
    linhas = [f"PerceptionResult: {len(res)} observações, origem "
               f"{res.origem}, frame {res.largura_imagem:g}x"
               f"{res.altura_imagem:g}, frame_id={res.frame_id}, "
               f"{len(res.avisos)} aviso(s)"]
    for o in sorted(res.observacoes, key=lambda x: x.id):
        linhas.append(
            f"  {o.id} [{o.classe}/{o.tipo}] "
            f"pos=({o.bounds.x:g},{o.bounds.y:g}) "
            f"tam={o.bounds.largura:g}x{o.bounds.altura:g} "
            f"conf={o.confianca} texto={o.texto!r} origem={o.origem}")
    for a in res.avisos:
        linhas.append(f"  AVISO {a.get('codigo')}: {a.get('motivo')}")
    return "\n".join(linhas)
