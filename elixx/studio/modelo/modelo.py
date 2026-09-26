"""Modelo semântico (F27 CP1) — entidades, relações e o modelo.

Camada de LEITURA e INDEXAÇÃO sobre o AST existente: nunca executa,
nunca substitui parser/componentes/personagens. IDs únicos; conflito
= erro determinístico (sem substituição silenciosa).
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX

__all__ = ["TIPOS_ENTIDADE", "TIPOS_RELACAO", "EntidadeSemantica",
           "RelacaoSemantica", "ModeloSemantico",
           "MutacaoSemantica"]

TIPOS_ENTIDADE = ("projeto", "arquivo", "tela", "janela",
                  "componente", "componente_def", "personagem",
                  "parte", "pose", "expressao", "gesto",
                  "animacao", "funcao", "acao", "evento", "estado",
                  "fonte", "asset", "import", "simbolo")
"""Tipos conhecidos. Tipo novo = erro claro (vocabulário fechado e
documentado; nada adivinhado)."""

TIPOS_RELACAO = ("contem", "possui", "usa_asset", "atua_em",
                 "responde", "depende_de", "define", "referencia")
"""Relações descritivas (nunca executadas)."""

_PROF_DADOS = 6
"""Aninhamento máximo de dados/tags (só JSON raso)."""

MAX_DADOS_CHARS = 100_000
"""Teto serializado de dados+tags por entidade (anti payload)."""


def _e_dado(valor, profundidade: int = 0) -> bool:
    import math

    if profundidade > _PROF_DADOS:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, float) and not math.isfinite(valor):
            return False
        return True
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(v, profundidade + 1) for v in valor)
    if isinstance(valor, dict):
        return all(isinstance(k, str) and _e_dado(v, profundidade + 1)
                   for k, v in valor.items())
    return False


def _id_valido(valor, o_que: str = "id") -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'Semântico: "{o_que}" não vazio.')
    return valor.strip()


def _ordenado(valores) -> list:
    return sorted(valores)


class EntidadeSemantica:
    """Um significado do projeto (id, tipo, nome, arquivo, local)."""

    def __init__(self, ent_id: str, tipo: str, nome: str = "",
                 arquivo: str = "", linha: int | None = None,
                 dados: dict | None = None,
                 tags: list | None = None) -> None:
        self.id = _id_valido(ent_id)
        tipo_txt = str(tipo).strip()
        if tipo_txt not in TIPOS_ENTIDADE:
            raise ErroELiXX(f'Semântico: tipo "{tipo}" inválido '
                            f'({", ".join(TIPOS_ENTIDADE)}).')
        self.tipo = tipo_txt
        self.nome = str(nome)
        self.arquivo = str(arquivo)
        if linha is not None:
            try:
                linha = int(linha)
            except (TypeError, ValueError):
                raise ErroELiXX("Semântico: linha inteira.")
            if linha < 0:
                raise ErroELiXX("Semântico: linha ≥ 0.")
        self.linha = linha
        conteudo = dict(dados or {})
        if not _e_dado(conteudo):
            raise ErroELiXX(f'Semântico: dados de "{self.id}" '
                            "inválidos (JSON finito).")
        lista_tags = [str(t) for t in (tags or [])]
        if not _e_dado(lista_tags):
            raise ErroELiXX(f'Semântico: tags de "{self.id}" '
                            "inválidas.")
        if len(json.dumps(conteudo, sort_keys=True)) + sum(
                len(t) for t in lista_tags) > MAX_DADOS_CHARS:
            raise ErroELiXX(f'Semântico: dados de "{self.id}" '
                            f"além de {MAX_DADOS_CHARS} chars.")
        self.dados = conteudo
        self.tags = lista_tags

    def to_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo, "nome": self.nome,
                "arquivo": self.arquivo, "linha": self.linha,
                "dados": dict(self.dados), "tags": list(self.tags)}

    @staticmethod
    def from_dict(dados: dict) -> EntidadeSemantica:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântico: entidade precisa de dict.")
        return EntidadeSemantica(
            dados.get("id", ""), dados.get("tipo", ""),
            nome=dados.get("nome", ""),
            arquivo=dados.get("arquivo", ""),
            linha=dados.get("linha"),
            dados=dict(dados.get("dados") or {}),
            tags=list(dados.get("tags") or []))

    def __repr__(self) -> str:
        return f"EntidadeSemantica({self.tipo} {self.id})"


class RelacaoSemantica:
    """Fato descritivo: origem —tipo→ destino (só entre entidades)."""

    def __init__(self, origem: str, tipo: str, destino: str) -> None:
        self.origem = _id_valido(origem, "origem")
        tipo_txt = str(tipo).strip()
        if tipo_txt not in TIPOS_RELACAO:
            raise ErroELiXX(f'Semântico: relação "{tipo}" inválida.')
        self.tipo = tipo_txt
        self.destino = _id_valido(destino, "destino")

    def to_dict(self) -> dict:
        return {"origem": self.origem, "tipo": self.tipo,
                "destino": self.destino}

    @staticmethod
    def from_dict(dados: dict) -> RelacaoSemantica:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântico: relação precisa de dict.")
        return RelacaoSemantica(dados.get("origem", ""),
                                dados.get("tipo", ""),
                                dados.get("destino", ""))

    def __repr__(self) -> str:
        return (f"RelacaoSemantica({self.origem} —{self.tipo}→ "
                f"{self.destino})")


class ModeloSemantico:
    """Contêiner: entidades + relações + arquivos + diagnósticos."""

    def __init__(self, nome: str = "modelo") -> None:
        self.nome = str(nome or "modelo")
        self._entidades: dict[str, EntidadeSemantica] = {}
        self._relacoes: list[RelacaoSemantica] = []
        self._arquivos: dict[str, dict] = {}
        self._diagnosticos: list[dict] = []

    def __len__(self) -> int:
        return len(self._entidades)

    def __contains__(self, ent_id: str) -> bool:
        return str(ent_id) in self._entidades

    # ----- entidades -----

    def adicionar_entidade(self, entidade: EntidadeSemantica
                           ) -> EntidadeSemantica:
        if not isinstance(entidade, EntidadeSemantica):
            raise ErroELiXX("Semântico: espera EntidadeSemantica.")
        if entidade.id in self._entidades:
            raise ErroELiXX(f'Semântico: entidade "{entidade.id}" '
                            "duplicada (sem substituição).")
        self._entidades[entidade.id] = entidade
        return entidade

    def obter_entidade(self, ent_id: str) -> EntidadeSemantica:
        try:
            return self._entidades[str(ent_id)]
        except KeyError:
            raise ErroELiXX(f'Semântico: entidade "{ent_id}" '
                            "ausente.")

    def remover_entidade(self, ent_id: str) -> EntidadeSemantica:
        entidade = self.obter_entidade(ent_id)
        del self._entidades[entidade.id]
        self._relacoes = [r for r in self._relacoes
                          if r.origem != entidade.id
                          and r.destino != entidade.id]
        return entidade

    def entidades(self) -> list[EntidadeSemantica]:
        return [self._entidades[k] for k in _ordenado(
            self._entidades)]

    # ----- relações -----

    def adicionar_relacao(self, relacao: RelacaoSemantica
                          ) -> RelacaoSemantica:
        if not isinstance(relacao, RelacaoSemantica):
            raise ErroELiXX("Semântico: espera RelacaoSemantica.")
        if relacao.origem not in self._entidades:
            raise ErroELiXX(f'Semântico: origem "{relacao.origem}" '
                            "ausente.")
        if relacao.destino not in self._entidades:
            raise ErroELiXX(f'Semântico: destino "{relacao.destino}" '
                            "ausente.")
        chave = (relacao.origem, relacao.tipo, relacao.destino)
        if any((r.origem, r.tipo, r.destino) == chave
               for r in self._relacoes):
            raise ErroELiXX("Semântico: relação duplicada.")
        self._relacoes.append(relacao)
        return relacao

    def remover_relacao(self, origem: str, tipo: str,
                        destino: str) -> None:
        antes = len(self._relacoes)
        self._relacoes = [
            r for r in self._relacoes
            if not (r.origem == origem and r.tipo == tipo
                    and r.destino == destino)]
        if len(self._relacoes) == antes:
            raise ErroELiXX("Semântico: relação ausente.")

    def relacoes(self) -> list[RelacaoSemantica]:
        return sorted(self._relacoes,
                      key=lambda r: (r.origem, r.tipo, r.destino))

    # ----- arquivos / diagnósticos -----

    def registrar_arquivo(self, relativo: str, tipo: str = "elixx",
                          status: str = "ok",
                          conteudo_hash: str | None = None
                          ) -> dict:
        caminho = _id_valido(relativo, "arquivo").replace("\\", "/")
        if caminho.startswith("/") or ".." in caminho.split("/"):
            raise ErroELiXX("Semântico: arquivo fora do projeto.")
        registro = {"caminho": caminho, "tipo": str(tipo),
                    "status": str(status),
                    "hash": conteudo_hash}
        if not _e_dado(registro):
            raise ErroELiXX("Semântico: registro inválido.")
        self._arquivos[caminho] = registro
        return registro

    def arquivos(self) -> list[dict]:
        return [self._arquivos[k] for k in _ordenado(self._arquivos)]

    def remover_arquivo_registro(self, relativo: str) -> None:
        caminho = str(relativo).replace("\\", "/")
        self._arquivos.pop(caminho, None)

    def adicionar_diagnostico(self, diagnostico: dict) -> None:
        if not isinstance(diagnostico, dict) or not _e_dado(
                diagnostico):
            raise ErroELiXX("Semântico: diagnóstico inválido.")
        self._diagnosticos.append(dict(diagnostico))

    def diagnosticos(self) -> list[dict]:
        return [dict(d) for d in self._diagnosticos]

    # ----- serialização -----

    def to_dict(self) -> dict:
        dados = {"nome": self.nome,
                 "entidades": [e.to_dict()
                               for e in self.entidades()],
                 "relacoes": [r.to_dict() for r in self.relacoes()],
                 "arquivos": self.arquivos(),
                 "diagnosticos": self.diagnosticos()}
        if not _e_dado(dados):
            raise ErroELiXX("Semântico: modelo não serializável.")
        return dados

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    @staticmethod
    def from_dict(dados: dict) -> ModeloSemantico:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântico: modelo precisa de dict.")
        modelo = ModeloSemantico(str(dados.get("nome", "modelo")))
        for item in (dados.get("entidades") or []):
            modelo.adicionar_entidade(
                EntidadeSemantica.from_dict(item))
        for item in (dados.get("relacoes") or []):
            modelo.adicionar_relacao(
                RelacaoSemantica.from_dict(item))
        for item in (dados.get("arquivos") or []):
            if not isinstance(item, dict):
                raise ErroELiXX("Semântico: arquivo inválido.")
            modelo.registrar_arquivo(
                item.get("caminho", ""),
                tipo=item.get("tipo", "elixx"),
                status=item.get("status", "ok"),
                conteudo_hash=item.get("hash"))
        for item in (dados.get("diagnosticos") or []):
            modelo.adicionar_diagnostico(item)
        return modelo

    def __repr__(self) -> str:
        return (f"ModeloSemantico({self.nome}: {len(self)} "
                f"entidades, {len(self._relacoes)} relações)")


class MutacaoSemantica:
    """Intenção de mudança (alvo + propriedade + valor). NÃO aplica.

    A ponte `mutacao_para_changeset` (adaptador.py) converte para
    ChangeSet F26 proposto — aplicação continua exigindo aprovação.
    """

    def __init__(self, alvo: str, propriedade: str,
                 valor=None) -> None:
        self.alvo = _id_valido(alvo, "alvo")
        self.propriedade = _id_valido(propriedade, "propriedade")
        if not _e_dado(valor):
            raise ErroELiXX("Semântico: valor inválido (JSON).")
        self.valor = valor

    def to_dict(self) -> dict:
        return {"alvo": self.alvo, "propriedade": self.propriedade,
                "valor": self.valor}

    @staticmethod
    def from_dict(dados: dict) -> MutacaoSemantica:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântico: mutação precisa de dict.")
        return MutacaoSemantica(dados.get("alvo", ""),
                                dados.get("propriedade", ""),
                                valor=dados.get("valor"))

    def __repr__(self) -> str:
        return (f"MutacaoSemantica({self.alvo}.{self.propriedade})")
