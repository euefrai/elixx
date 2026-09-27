"""Project Context Intelligence (Fase 34) — visão de contexto do F27.

"IA futura deve receber contexto, não o projeto inteiro."

"O contexto é selecionado pelo significado da tarefa."

`construir_contexto(modelo, tarefa, config)` responde "quais partes do
projeto importam para esta tarefa?" com scores determinísticos e
explicáveis (sem ML, sem embeddings): sinais documentados, soma,
escala max→1.00, desempate estável por id. Só leitura — nunca executa,
nunca escreve.
"""
from __future__ import annotations

import json
import unicodedata

from ...erros import ErroELiXX
from . import _base as B

__all__ = [
    "CATEGORIAS", "MODOS", "PESOS", "ACAO_TIPOS",
    "ContextoConfig", "ContextoTarefa", "ContextoEntidade",
    "ContextoResultado",
    "construir_contexto", "salvar_preferencias",
    "carregar_preferencias", "ids_relevantes",
]


def ids_relevantes(resultado: ContextoResultado,
                   categoria: str | None = None) -> list[str]:
    """IDs ordenados por score (ponte p/ planner/ferramentas)."""
    if not isinstance(resultado, ContextoResultado):
        raise ErroELiXX("Contexto: espera ContextoResultado.")
    ids = [e.id for e in resultado.entidades
           if categoria is None or e.categoria == categoria]
    return ids

CATEGORIAS = ("ALVO", "SUPORTE", "PERSONAGEM", "PARTE", "POSE",
              "EXPRESSAO", "GESTO", "ASSET", "CENA", "ANIMACAO",
              "ARQUIVO", "EVENTO", "DEPENDENCIA")
"""Categorias reutilizáveis (por tipo F27; sem duplicar conceitos)."""

MODOS = ("minimo", "expandido", "completo")
"""minimo: alvo+diretas+arquivo · expandido: +transitivas/recursos ·
completo: respeita orçamento (nunca o projeto inteiro por padrão)."""

PESOS = {
    "alvo_explicito": 1.00,
    "nome_exato": 0.30,
    "tipo_compativel": 0.15,
    "operacao_compativel": 0.15,
    "mesmo_arquivo": 0.10,
    "mesma_cena": 0.08,
    "selecionada": 0.20,
    "relacao_direta": 0.25,
    "relacao_transitiva": 0.10,
    "pai": 0.12,
    "filha": 0.12,
    "recurso": 0.10,
}
"""Sinais de relevância (pesos fixos e documentados; soma + escala)."""

ACAO_TIPOS = {
    "mover": ("personagem", "parte", "cena"),
    "pose": ("personagem", "pose", "parte"),
    "expressao": ("personagem", "expressao", "parte"),
    "gesto": ("personagem", "pose"),
    "animar": ("personagem", "animacao"),
    "mostrar": ("componente", "personagem", "parte", "tela"),
    "esconder": ("componente", "personagem", "parte", "tela"),
    "consultar": (),
    "selecionar": (),
    "adicionar": (), "alterar": (), "remover": (),
    "alterar_propriedade": (), "adicionar_evento": (),
    "associar_acao": ("personagem", "evento", "pose", "expressao"),
}
"""Ação F31 → tipos relevantes (vazio = todos; sem adivinhar além)."""

_TIPO_CATEGORIA = {
    "personagem": "PERSONAGEM", "parte": "PARTE", "pose": "POSE",
    "expressao": "EXPRESSAO", "gesto": "GESTO", "asset": "ASSET",
    "tela": "CENA", "janela": "CENA", "animacao": "ANIMACAO",
    "evento": "EVENTO", "arquivo": "ARQUIVO",
}
"""Tipo F27 → categoria (resto = SUPORTE; ALVO sobrepõe)."""


def _norm(texto: str) -> str:
    base = unicodedata.normalize(
        "NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


class ContextoConfig:
    """Orçamentos e modo (tudo configurável, tudo com teto)."""

    def __init__(self, modo: str = "expandido",
                 max_entidades: int = 50, max_relacoes: int = 100,
                 max_arquivos: int = 5, max_recursos: int = 30,
                 max_profundidade: int = 2, max_bytes: int = 200_000,
                 max_por_categoria: int = 20) -> None:
        modo_txt = str(modo).strip()
        if modo_txt not in MODOS:
            raise ErroELiXX(f'Contexto: modo "{modo}" inválido.')
        self.modo = modo_txt
        limites = {"max_entidades": max_entidades,
                   "max_relacoes": max_relacoes,
                   "max_arquivos": max_arquivos,
                   "max_recursos": max_recursos,
                   "max_profundidade": max_profundidade,
                   "max_bytes": max_bytes,
                   "max_por_categoria": max_por_categoria}
        for nome, valor in limites.items():
            try:
                numero = int(valor)
            except (TypeError, ValueError):
                raise ErroELiXX(f"Contexto: {nome} inteiro.")
            if numero < 0:
                raise ErroELiXX(f"Contexto: {nome} ≥ 0.")
            setattr(self, nome, numero)

    def to_dict(self) -> dict:
        return {"modo": self.modo,
                "max_entidades": self.max_entidades,
                "max_relacoes": self.max_relacoes,
                "max_arquivos": self.max_arquivos,
                "max_recursos": self.max_recursos,
                "max_profundidade": self.max_profundidade,
                "max_bytes": self.max_bytes,
                "max_por_categoria": self.max_por_categoria}

    @staticmethod
    def from_dict(dados: dict) -> ContextoConfig:
        if not isinstance(dados, dict):
            raise ErroELiXX("Contexto: config precisa de dict.")
        padrao = ContextoConfig().to_dict()
        return ContextoConfig(**{
            k: dados.get(k, v) for k, v in padrao.items()})

    def __repr__(self) -> str:
        return f"ContextoConfig({self.modo})"


class ContextoTarefa:
    """O que construir: objetivo, alvo, seleção, limites locais."""

    def __init__(self, objetivo: str = "", alvo: str = "",
                 entidade_selecionada: str = "",
                 arquivo_atual: str = "",
                 operacoes: list | None = None,
                 incluir: list | None = None,
                 excluir: list | None = None,
                 orcamento: dict | None = None,
                 profundidade: int | None = None,
                 restricoes: list | None = None) -> None:
        self.objetivo = str(objetivo)[:2000]
        self.alvo = str(alvo)
        self.entidade_selecionada = str(entidade_selecionada)
        self.arquivo_atual = str(arquivo_atual)
        self.operacoes = [str(o) for o in (operacoes or [])]
        for o in self.operacoes:
            if o not in ACAO_TIPOS:
                raise ErroELiXX(f'Contexto: operação "{o}" '
                                "desconhecida.")
        self.incluir = [str(i) for i in (incluir or [])]
        self.excluir = [str(e) for e in (excluir or [])]
        orc = dict(orcamento or {})
        if not B.e_dado(orc):
            raise ErroELiXX("Contexto: orçamento inválido.")
        self.orcamento = orc
        if profundidade is not None:
            try:
                profundidade = int(profundidade)
            except (TypeError, ValueError):
                raise ErroELiXX("Contexto: profundidade inteira.")
            if profundidade < 0:
                raise ErroELiXX("Contexto: profundidade ≥ 0.")
        self.profundidade = profundidade
        self.restricoes = [str(r) for r in (restricoes or [])]

    def to_dict(self) -> dict:
        return {"objetivo": self.objetivo, "alvo": self.alvo,
                "entidade_selecionada": self.entidade_selecionada,
                "arquivo_atual": self.arquivo_atual,
                "operacoes": list(self.operacoes),
                "incluir": list(self.incluir),
                "excluir": list(self.excluir),
                "orcamento": dict(self.orcamento),
                "profundidade": self.profundidade,
                "restricoes": list(self.restricoes)}

    def __repr__(self) -> str:
        return f"ContextoTarefa({self.objetivo[:40]})"


class ContextoEntidade:
    """Entidade pontuada (score + motivos + categoria + origem)."""

    def __init__(self, ent_id: str, tipo: str = "", nome: str = "",
                 arquivo: str = "", score: float = 0.0,
                 motivos: list | None = None,
                 categoria: str = "SUPORTE",
                 origem: str = "auto") -> None:
        self.id = B.id_valido(ent_id)
        self.tipo = str(tipo)
        self.nome = str(nome)
        self.arquivo = str(arquivo)
        try:
            numero = float(score)
        except (TypeError, ValueError):
            raise ErroELiXX("Contexto: score numérico.")
        import math

        if not math.isfinite(numero):
            raise ErroELiXX("Contexto: score finito.")
        self.score = round(numero, 2)
        self.motivos = [str(m) for m in (motivos or [])]
        if categoria not in CATEGORIAS:
            raise ErroELiXX(f'Contexto: categoria "{categoria}" '
                            "inválida.")
        self.categoria = categoria
        if origem not in ("auto", "manual"):
            raise ErroELiXX("Contexto: origem auto/manual.")
        self.origem = origem

    def to_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo,
                "nome": self.nome, "arquivo": self.arquivo,
                "score": self.score, "motivos": list(self.motivos),
                "categoria": self.categoria, "origem": self.origem}

    def __repr__(self) -> str:
        return f"ContextoEntidade({self.id} {self.score:.2f})"


class ContextoResultado:
    """Resultado: entidades, relações, arquivos, recursos e porquês."""

    def __init__(self, entidades: list | None = None,
                 relacoes: list | None = None,
                 arquivos: list | None = None,
                 recursos: list | None = None,
                 ambiguidade=None,
                 limites: dict | None = None,
                 excluidas: list | None = None,
                 diagnostico: dict | None = None) -> None:
        self.entidades = [e if isinstance(e, ContextoEntidade)
                          else ContextoEntidade(**e)
                          for e in (entidades or [])]
        self.relacoes = [dict(r) for r in (relacoes or [])]
        for r in self.relacoes:
            if not B.e_dado(r):
                raise ErroELiXX("Contexto: relação inválida.")
        self.arquivos = [str(a) for a in (arquivos or [])]
        self.recursos = [dict(r) for r in (recursos or [])]
        self.ambiguidade = dict(ambiguidade or {})
        self.limites = dict(limites or {})
        self.excluidas = [dict(e) for e in (excluidas or [])]
        self.diagnostico = dict(diagnostico or {})

    def por_que(self, ent_id: str) -> list[str]:
        """Motivos de uma entidade (explicabilidade)."""
        for e in self.entidades:
            if e.id == str(ent_id):
                return list(e.motivos)
        raise ErroELiXX(f'Contexto: "{ent_id}" fora do resultado.')

    def to_dict(self) -> dict:
        return {"entidades": [e.to_dict()
                              for e in self.entidades],
                "relacoes": list(self.relacoes),
                "arquivos": list(self.arquivos),
                "recursos": list(self.recursos),
                "ambiguidade": dict(self.ambiguidade),
                "limites": dict(self.limites),
                "excluidas": list(self.excluidas),
                "diagnostico": dict(self.diagnostico)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"ContextoResultado({len(self.entidades)} ent, "
                f"{len(self.relacoes)} rel)")


# ----- engine -----

def construir_contexto(modelo, tarefa, config=None
                       ) -> ContextoResultado:
    """Modelo + tarefa + config → contexto explicável e limitado."""
    from ..modelo.consulta import ConsultaSemantica
    from .loop import resolver_alvo

    if not isinstance(tarefa, ContextoTarefa):
        raise ErroELiXX("Contexto: espera ContextoTarefa.")
    cfg = config if isinstance(config, ContextoConfig) \
        else ContextoConfig()
    for chave, valor in tarefa.orcamento.items():
        if hasattr(cfg, chave):
            try:
                setattr(cfg, chave, int(valor))
            except (TypeError, ValueError):
                raise ErroELiXX("Contexto: orçamento inteiro.")
    profundidade = tarefa.profundidade \
        if tarefa.profundidade is not None \
        else (1 if cfg.modo == "minimo" else cfg.max_profundidade)
    q = ConsultaSemantica(modelo)
    entidades = {e.id: e for e in modelo.entidades()}
    relacoes = modelo.relacoes()

    # -- sementes: alvo, seleção, menções no objetivo --
    sementes: dict[str, list] = {}
    ambiguidade: dict = {}
    if tarefa.alvo:
        alvo = resolver_alvo(modelo, tarefa.alvo)
        if alvo["status"] == "unico":
            sementes[alvo["entidade"]["id"]] = ["alvo explícito"]
        else:
            ambiguidade = {
                "alvo": tarefa.alvo, "status": alvo["status"],
                "candidatos": alvo.get("candidatos", [])}
    if tarefa.entidade_selecionada in entidades:
        sementes.setdefault(tarefa.entidade_selecionada,
                            []).append("entidade selecionada")
    objetivo_norm = _norm(tarefa.objetivo)
    for eid, ent in entidades.items():
        nome_norm = _norm(ent.nome)
        if nome_norm and nome_norm in objetivo_norm:
            sementes.setdefault(eid, []).append(
                "mencionado no objetivo")

    # -- pontua tudo (uma passada O(n)) --
    bruto: dict[str, dict] = {}
    for eid, ent in entidades.items():
        sinais = _sinais(ent, tarefa, sementes, q, entidades)
        bruto[eid] = {"ent": ent, "sinais": sinais,
                      "score": sum(PESOS[s] for s, _ in sinais)}

    # -- expansão por relações até a profundidade --
    alcance: dict[str, int] = {eid: 0 for eid in sementes}
    fronteira = list(sementes)
    for _ in range(max(0, int(profundidade))):
        proxima = []
        for eid in fronteira:
            for rel in q.relacoes_de(eid) + q.relacoes_para(eid):
                for outro in (rel.destino, rel.origem):
                    if outro in entidades and outro not in alcance:
                        alcance[outro] = alcance[eid] + 1
                        proxima.append(outro)
        fronteira = proxima
    for eid, dist in alcance.items():
        if eid not in sementes and dist >= 1:
            chave = "relacao_direta" if dist == 1 else \
                "relacao_transitiva"
            bruto[eid]["sinais"].append((chave,
                                         f"a {dist} passo(s) do alvo"))
            bruto[eid]["score"] += PESOS[chave]

    # -- overrides manuais (prioridade, sem quebrar validade) --
    for eid in tarefa.incluir:
        if eid in bruto:
            bruto[eid]["sinais"].append(
                ("manual", "INCLUIDO_MANUALMENTE"))
            bruto[eid]["score"] += 1.00
            bruto[eid]["manual"] = True
    excluidos_manual = [e for e in tarefa.excluir if e in bruto]

    # -- escala max→1.00, ordena (-score, id), aplica budget --
    pico = max([v["score"] for v in bruto.values()] + [0.0])
    itens = []
    for eid, v in bruto.items():
        score = round(v["score"] / pico, 2) if pico else 0.0
        motivos = sorted({m for _, m in v["sinais"]})
        categoria = _categoria(
            v["ent"], eid in sementes or v.get("manual", False))
        itens.append((eid, score, motivos, categoria,
                      "manual" if v.get("manual") else "auto"))
    itens.sort(key=lambda t: (-t[1], t[0]))
    por_categoria: dict[str, int] = {}
    selecionados, excluidas = [], []
    for eid, score, motivos, categoria, origem in itens:
        if eid in tarefa.excluir:
            excluidas.append({"id": eid,
                              "motivo": "EXCLUIDO_MANUALMENTE"})
            continue
        if len(selecionados) >= cfg.max_entidades:
            excluidas.append({"id": eid,
                              "motivo": "orçamento de entidades"})
            continue
        if por_categoria.get(categoria, 0) >= cfg.max_por_categoria:
            excluidas.append({"id": eid,
                              "motivo": "orçamento da categoria "
                                        + categoria})
            continue
        por_categoria[categoria] = por_categoria.get(categoria,
                                                     0) + 1
        ent = bruto[eid]["ent"]
        selecionados.append(ContextoEntidade(
            eid, ent.tipo, ent.nome, ent.arquivo, score, motivos,
            categoria, origem))
    escolhidos = {e.id for e in selecionados}
    rels = [r.to_dict() for r in relacoes
            if r.origem in escolhidos and r.destino in escolhidos]
    rels_cortadas = rels[:cfg.max_relacoes]
    limites = {"entidades": f"{len(selecionados)}/"
                            f"{cfg.max_entidades}",
               "relacoes": f"{len(rels_cortadas)}/"
                           f"{cfg.max_relacoes}",
               "cortadas_relacoes": len(rels) - len(rels_cortadas)}
    contagem_arq: dict[str, int] = {}
    for e in selecionados:
        if e.arquivo:
            contagem_arq[e.arquivo] = contagem_arq.get(
                e.arquivo, 0) + 1
    arquivos = sorted(contagem_arq,
                      key=lambda a: (-contagem_arq[a], a)
                      )[:cfg.max_arquivos]
    recursos = [{"id": e.id, "tipo": e.tipo, "nome": e.nome}
                for e in selecionados
                if e.tipo in ("pose", "expressao", "animacao",
                              "asset")][:cfg.max_recursos]
    analisadas_rel = sum(1 for _ in relacoes)
    if len(excluidas) > 200:
        excluidas = excluidas[:200] + [
            {"resumo": f"+{len(excluidas) - 200} omitidas"}]
    resultado = ContextoResultado(
        selecionados, rels_cortadas, arquivos, recursos,
        ambiguidade=ambiguidade, limites=limites,
        excluidas=excluidas,
        diagnostico={
            "estado": "pronto" if not ambiguidade
            else ambiguidade.get("status", "ambíguo"),
            "entidades_analisadas": len(entidades),
            "entidades_selecionadas": len(selecionados),
            "relacoes_analisadas": analisadas_rel,
            "relacoes_selecionadas": len(rels_cortadas),
            "overrides": {
                "inclusoes": sum(
                    1 for e in selecionados
                    if e.origem == "manual"),
                "exclusoes": len(excluidos_manual)}})
    if len(resultado.to_json()) > cfg.max_bytes:
        raise ErroELiXX("Contexto: resultado além do orçamento "
                        "de bytes (reduza o escopo).")
    return resultado


def _sinais(ent, tarefa: ContextoTarefa, sementes: dict,
            q, entidades: dict) -> list[tuple]:
    sinais = []
    eid = ent.id
    if eid in sementes:
        for motivo in sementes[eid]:
            if motivo == "alvo explícito":
                sinais.append(("alvo_explicito", motivo))
            elif motivo == "entidade selecionada":
                sinais.append(("selecionada", motivo))
            else:
                sinais.append(("nome_exato", motivo))
    if _norm(ent.nome) and _norm(ent.nome) in _norm(
            tarefa.objetivo) and eid not in sementes:
        sinais.append(("nome_exato", "nome no objetivo"))
    tipos = set()
    for acao in tarefa.operacoes:
        tipos.update(ACAO_TIPOS.get(acao, ()))
    if not tarefa.operacoes:
        sinais.append(("tipo_compativel", "sem filtro de ação"))
    elif not tipos or ent.tipo in tipos:
        sinais.append(("tipo_compativel",
                       f"tipo {ent.tipo or '?'} p/ ação"))
    if tarefa.arquivo_atual and ent.arquivo == tarefa.arquivo_atual:
        sinais.append(("mesmo_arquivo",
                       f"arquivo atual {ent.arquivo}"))
    for sem in sementes:
        outra = entidades.get(sem)
        if outra is not None and outra.arquivo and \
                outra.arquivo == ent.arquivo and eid != sem:
            sinais.append(("mesma_cena",
                           f"mesmo arquivo de {sem}"))
            break
    for ref in q.relacoes_de(eid) + q.relacoes_para(eid):
        outro = ref.destino if ref.origem == eid else ref.origem
        if outro in sementes:
            sinais.append(("relacao_direta",
                           f"{ref.tipo} com {outro}"))
            break
    for rel in q.relacoes_de(eid):
        if rel.destino in entidades and rel.destino != eid:
            sinais.append(("filha",
                           f"possui {rel.destino}"))
            break
    for rel in q.relacoes_para(eid):
        if rel.origem in entidades and rel.origem != eid:
            sinais.append(("pai", f"em {rel.origem}"))
            break
    if ent.tipo in ("pose", "expressao", "animacao", "asset"):
        sinais.append(("recurso", f"recurso {ent.tipo}"))
    return sinais


def _categoria(ent, e_semente: bool) -> str:
    if e_semente:
        return "ALVO"
    return _TIPO_CATEGORIA.get(ent.tipo, "SUPORTE")


# ----- preferências (reusa persistência simples) -----

def salvar_preferencias(workspace, config: ContextoConfig,
                        relativo: str = ".elixx/contexto.json"
                        ) -> str:
    """Só modo/filtros/orçamento (sem segredos, sem conteúdo)."""
    import json

    if not isinstance(config, ContextoConfig):
        raise ErroELiXX("Contexto: espera ContextoConfig.")
    destino = workspace.resolver(relativo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(config.to_dict(),
                                  ensure_ascii=False,
                                  sort_keys=True, indent=2),
                       encoding="utf-8")
    return relativo


def carregar_preferencias(workspace,
                          relativo: str = ".elixx/contexto.json"
                          ) -> ContextoConfig:
    import json

    try:
        destino = workspace.resolver(relativo)
    except ErroELiXX:
        return ContextoConfig()
    if not destino.is_file():
        return ContextoConfig()
    try:
        dados = json.loads(destino.read_text(encoding="utf-8"))
    except ValueError:
        return ContextoConfig()
    try:
        return ContextoConfig.from_dict(dados)
    except ErroELiXX:
        return ContextoConfig()
