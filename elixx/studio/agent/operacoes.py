"""Semantic Actions, Events & Operations (Fase 31) — semântica do Agent.

"SemanticOperation não é uma nova linguagem."

"A operação semântica descreve uma intenção operacional; a execução
continua pertencendo às estruturas existentes do ELiXX."

Camada de dados sobre F18/F26/F27/F28/F30 (nada duplicado, nada
reescrito): `AIIntent` → `SemanticOperation` (+ eventos e composição)
→ F27 resolve → runtime via ferramentas F26/F30 ou arquivo via
ChangeSet F26 aprovado. Consultas nunca geram ChangeSet; arquivo
nunca é escrito direto.
"""
from __future__ import annotations

import json
import math

from ...erros import ErroELiXX
from ...visual.ai_bridge import AIIntent

__all__ = [
    "OPERACOES", "CATEGORIA_OPERACAO", "OPERACOES_CONSULTA",
    "OPERACOES_ARQUIVO", "GATILHOS", "MODOS_COMPOSICAO",
    "MAX_PARAMETROS_OP", "MAX_EFEITOS",
    "SemanticReference", "SemanticOperation",
    "SemanticEventOperation",
    "resolver_referencia",
    "intent_para_operacao", "operacao_para_intent",
    "validar_operacao", "explicar_operacao",
    "operacao_para_ferramentas", "operacao_para_proposta",
    "snippet_evento",
]

OPERACOES = ("mostrar", "esconder", "mover", "transformar",
             "pose", "expressao", "gesto", "direcao",
             "animar", "iniciar", "parar",
             "adicionar_evento", "remover_evento",
             "associar_acao",
             "adicionar", "remover", "alterar",
             "alterar_propriedade",
             "consultar", "selecionar")
"""Vocabulário fechado (pequeno; sem especulação)."""

CATEGORIA_OPERACAO = {
    "mostrar": "visual", "esconder": "visual", "mover": "visual",
    "transformar": "visual",
    "pose": "personagem", "expressao": "personagem",
    "gesto": "personagem", "direcao": "personagem",
    "animar": "animacao", "iniciar": "animacao", "parar": "animacao",
    "adicionar_evento": "evento", "remover_evento": "evento",
    "associar_acao": "evento",
    "adicionar": "projeto", "remover": "projeto", "alterar": "projeto",
    "alterar_propriedade": "projeto",
    "consultar": "consulta", "selecionar": "consulta",
}
"""Operação → categoria (§4; só as implementáveis)."""

OPERACOES_CONSULTA = ("consultar", "selecionar")
"""Somente leitura: nunca geram ChangeSet."""

OPERACOES_ARQUIVO = ("adicionar_evento", "remover_evento",
                     "adicionar", "remover", "alterar",
                     "alterar_propriedade")
"""Podem virar ChangeSet (aprovado; nunca escrita direta)."""

GATILHOS = ("clique", "pressionar", "aparecer", "terminar",
            "comecar", "cancelar")
"""Gatilhos com evidência no runtime (`quando <nome>` é livre; estes
têm exemplo no parser: clicar/pressionar/aparecer e animação
terminar/começar/cancelar)."""

MODOS_COMPOSICAO = ("sequencia", "paralelo")
"""Ordem preservada (sequência) ou conjunta (paralelo, vocabulário
do MotionGroup F11; sem scheduler novo)."""

MAX_PARAMETROS_OP = 20
"""Teto de parâmetros por operação."""

MAX_EFEITOS = 10
"""Teto de efeitos por evento (sem explosão)."""


def _e_dado(valor, prof: int = 0) -> bool:
    if prof > 6:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        return not (isinstance(valor, float)
                    and not math.isfinite(valor))
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(v, prof + 1) for v in valor)
    if isinstance(valor, dict):
        return all(isinstance(k, str) and _e_dado(v, prof + 1)
                   for k, v in valor.items())
    return False


def _id_valido(valor, o_que: str = "id") -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroELiXX(f'Semântica: "{o_que}" não vazio.')
    return valor.strip()


def _ordenado(valores) -> list:
    return sorted(valores)


def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'Semântica: "{o_que}" numérico.')
    if not math.isfinite(numero):
        raise ErroELiXX(f'Semântica: "{o_que}" finito.')
    if abs(numero) > 1.0e9:
        raise ErroELiXX(f'Semântica: "{o_que}" gigante.')
    return numero


# ----- referência (ETAPA 3; resolve via F28, sem duplicar) -----

class SemanticReference:
    """Aponta por nome+tipo (F27 resolve; sem inventar entidade)."""

    def __init__(self, nome: str, tipo: str | None = None,
                 ent_id: str | None = None) -> None:
        self.nome = _id_valido(nome, "nome da referência")
        if tipo is not None and not str(tipo).strip():
            raise ErroELiXX("Semântica: tipo vazio (use None).")
        self.tipo = str(tipo).strip() if tipo else None
        self.ent_id = (str(ent_id).strip() or None
                       if ent_id is not None else None)

    def to_dict(self) -> dict:
        return {"nome": self.nome, "tipo": self.tipo,
                "id": self.ent_id}

    @staticmethod
    def from_dict(dados: dict) -> SemanticReference:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântica: referência precisa de dict.")
        return SemanticReference(dados.get("nome", ""),
                                 tipo=dados.get("tipo"),
                                 ent_id=dados.get("id"))

    def __repr__(self) -> str:
        return f"SemanticReference({self.nome}:{self.tipo})"


def resolver_referencia(modelo, referencia: SemanticReference
                        ) -> dict:
    """F28 `resolver_alvo` (reuso; 0→erro, 1→ok, N→ambíguo)."""
    from .loop import resolver_alvo

    if not isinstance(referencia, SemanticReference):
        raise ErroELiXX("Semântica: espera SemanticReference.")
    return resolver_alvo(modelo, referencia.nome, referencia.tipo)


# ----- operação -----

class SemanticOperation:
    """Operação abstrata: tipo + alvo + parâmetros (só dados)."""

    def __init__(self, tipo: str, alvo=None,
                 parametros: dict | None = None,
                 alteracao: dict | None = None) -> None:
        tipo_txt = str(tipo).strip()
        if tipo_txt not in OPERACOES:
            raise ErroELiXX(f'Semântica: operação "{tipo}" inválida '
                            f'({", ".join(OPERACOES)}).')
        self.tipo = tipo_txt
        if isinstance(alvo, SemanticReference):
            self.alvo = alvo
        elif isinstance(alvo, dict):
            self.alvo = SemanticReference.from_dict(alvo)
        elif isinstance(alvo, str):
            self.alvo = SemanticReference(alvo)
        else:
            raise ErroELiXX("Semântica: alvo (nome, dict ou "
                            "SemanticReference).")
        params = dict(parametros or {})
        if len(params) > MAX_PARAMETROS_OP:
            raise ErroELiXX("Semântica: parâmetros além do teto.")
        if not _e_dado(params):
            raise ErroELiXX("Semântica: parâmetros inválidos "
                            "(NaN/Infinity/recursão).")
        for chave in ("duracao", "distancia", "valor"):
            if chave in params and isinstance(params[chave],
                                              (int, float)):
                _finito(params[chave], chave)
        unidade = params.get("unidade")
        if unidade is not None and unidade not in ("px", "s",
                                                   "ms", "deg",
                                                   "%"):
            raise ErroELiXX(f'Semântica: unidade "{unidade}" '
                            "inválida (px, s, ms, deg, %).")
        self.parametros = params
        alt = dict(alteracao or {})
        if alt and not _e_dado(alt):
            raise ErroELiXX("Semântica: alteração inválida.")
        self.alteracao = alt

    @property
    def categoria(self) -> str:
        return CATEGORIA_OPERACAO[self.tipo]

    @property
    def somente_leitura(self) -> bool:
        return self.tipo in OPERACOES_CONSULTA

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "alvo": self.alvo.to_dict(),
                "parametros": dict(self.parametros),
                "alteracao": dict(self.alteracao)}

    @staticmethod
    def from_dict(dados: dict) -> SemanticOperation:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântica: operação precisa de dict.")
        return SemanticOperation(
            dados.get("tipo", ""), alvo=dados.get("alvo", ""),
            parametros=dict(dados.get("parametros") or {}),
            alteracao=dict(dados.get("alteracao") or {}))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"SemanticOperation({self.tipo} "
                f"{self.alvo.nome})")


def validar_operacao(operacao) -> dict:
    """{valido, codigo, motivo} (referências resolve o F27, não aqui)."""
    if not isinstance(operacao, SemanticOperation):
        return {"valido": False, "codigo": "operacao_invalida",
                "motivo": "Esperava SemanticOperation."}
    if operacao.tipo in OPERACOES_ARQUIVO and not \
            operacao.alteracao:
        return {"valido": False, "codigo": "alteracao_ausente",
                "motivo": f'"{operacao.tipo}" exige bloco '
                          '"alteracao" explícito.'}
    return {"valido": True, "codigo": "ok",
            "motivo": "Operação válida."}


# ----- eventos e composição (ETAPAS 5-6) -----

class SemanticEventOperation:
    """Gatilho + efeitos ordenados (+ condição opcional planejada).

    Condição (`se <fato>`) é representação: o runtime atual pode não
    suportá-la — nesses casos a operação segue planejada, sem
    execução (honestidade documentada).
    """

    def __init__(self, gatilho: str, alvo=None,
                 efeitos: list | None = None,
                 modo: str = "sequencia",
                 condicao: dict | None = None) -> None:
        gatilho_txt = str(gatilho).strip()
        if gatilho_txt not in GATILHOS:
            raise ErroELiXX(f'Semântica: gatilho "{gatilho}" sem '
                            f"evidência ({', '.join(GATILHOS)}).")
        self.gatilho = gatilho_txt
        if isinstance(alvo, SemanticReference):
            self.alvo = alvo
        elif isinstance(alvo, dict):
            self.alvo = SemanticReference.from_dict(alvo)
        else:
            self.alvo = SemanticReference(str(alvo or ""))
        lista = []
        for e in (efeitos or []):
            op = (e if isinstance(e, SemanticOperation)
                  else SemanticOperation.from_dict(e))
            if op.tipo in OPERACOES_CONSULTA:
                raise ErroELiXX("Semântica: efeito não pode ser "
                                "consulta.")
            lista.append(op)
        if len(lista) > MAX_EFEITOS:
            raise ErroELiXX("Semântica: efeitos além do teto.")
        if not lista:
            raise ErroELiXX("Semântica: evento sem efeitos.")
        self.efeitos = lista
        modo_txt = str(modo).strip() or "sequencia"
        if modo_txt not in MODOS_COMPOSICAO:
            raise ErroELiXX(f'Semântica: modo "{modo}" inválido.')
        self.modo = modo_txt
        cond = dict(condicao or {})
        if cond and not _e_dado(cond):
            raise ErroELiXX("Semântica: condição inválida.")
        self.condicao = cond

    def to_dict(self) -> dict:
        return {"gatilho": self.gatilho,
                "alvo": self.alvo.to_dict(),
                "efeitos": [e.to_dict() for e in self.efeitos],
                "modo": self.modo, "condicao": dict(self.condicao)}

    @staticmethod
    def from_dict(dados: dict) -> SemanticEventOperation:
        if not isinstance(dados, dict):
            raise ErroELiXX("Semântica: evento precisa de dict.")
        return SemanticEventOperation(
            dados.get("gatilho", ""), alvo=dados.get("alvo", ""),
            efeitos=dados.get("efeitos") or [],
            modo=dados.get("modo", "sequencia"),
            condicao=dict(dados.get("condicao") or {}))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"SemanticEventOperation({self.gatilho} "
                f"{self.alvo.nome} ×{len(self.efeitos)})")


def snippet_evento(gatilho_elixx: str, efeito: str = "") -> str:
    """Template mínimo `quando <nome> { ... }` (validado depois)."""
    nome = str(gatilho_elixx).strip()
    if not nome:
        raise ErroELiXX("Semântica: nome de evento vazio.")
    corpo = f'    mostrar("{efeito}")\n' if efeito else ""
    return f"quando {nome} {{\n{corpo}}}\n"


# ----- pontes F30/F28 (ETAPAS 7-8; sem duplicar Agent) -----

_TIPO_OPERACAO = {
    "mover": "mover", "mostrar": "mostrar", "esconder": "esconder",
    "animar": "animar", "expressao": "expressao", "pose": "pose",
    "selecionar": "selecionar", "consultar": "consultar",
    "adicionar": "adicionar", "alterar": "alterar",
    "remover": "remover", "associar_evento": "associar_acao",
}
"""AIIntent.tipo F30 → operação F31 (1:1 documentado)."""

_TIPO_F26_OP = {
    "pose": "modificar_personagem",
    "expressao": "modificar_personagem",
    "gesto": "modificar_personagem", "direcao": "modificar_personagem",
    "mover": "modificar_personagem",
    "mostrar": "modificar_interface",
    "esconder": "modificar_interface",
    "animar": "criar_animacao", "iniciar": "modificar_interface",
    "parar": "modificar_interface",
    "adicionar_evento": "modificar_interface",
    "remover_evento": "modificar_interface",
    "associar_acao": "modificar_interface",
    "adicionar": "criar_cena", "remover": "modificar_interface",
    "alterar": "modificar_interface",
    "alterar_propriedade": "modificar_interface",
    "consultar": "diagnosticar", "selecionar": "modificar_interface",
    "transformar": "modificar_personagem",
}
"""Operação F31 → AgentIntent F26 (para PlanoSemantico)."""


def intent_para_operacao(intent: AIIntent):
    """AIIntent → SemanticOperation (+ evento quando houver).

    `associar_evento` vira SemanticEventOperation (gatilho + efeito
    único; composição maior é montada explicitamente, sem chute).
    """
    if not isinstance(intent, AIIntent):
        raise ErroELiXX("Semântica: espera AIIntent.")
    params = dict(intent.parametros or {})
    alvo_nome = intent.personagem or intent.alvo or ""
    if intent.tipo not in _TIPO_OPERACAO:
        raise ErroELiXX(f'Semântica: ação "{intent.tipo}" sem '
                        "operação (sem invenção).")
    if intent.tipo == "associar_evento":
        efeito_nome = params.get("efeito", "acenar")
        efeito = SemanticOperation(
            "pose" if "pose" in str(efeito_nome).lower()
            or str(efeito_nome) in ("acenar",) else "expressao",
            SemanticReference(alvo_nome),
            {"pose": efeito_nome} if "pose" in str(
                efeito_nome).lower() or str(efeito_nome) in
            ("acenar",) else {"expressao": efeito_nome})
        return SemanticEventOperation(
            params.get("evento", "clique"),
            SemanticReference(alvo_nome), [efeito])
    op = SemanticOperation(
        _TIPO_OPERACAO[intent.tipo], SemanticReference(alvo_nome),
        {k: v for k, v in params.items()
         if k not in ("evento", "efeito")})
    return op


def operacao_para_intent(operacao: SemanticOperation) -> AIIntent:
    """Volta honesta op → AIIntent (para ferramentas F30)."""
    if not isinstance(operacao, SemanticOperation):
        raise ErroELiXX("Semântica: espera SemanticOperation.")
    reverso = {v: k for k, v in _TIPO_OPERACAO.items()}
    if operacao.tipo not in reverso:
        raise ErroELiXX(f'Semântica: "{operacao.tipo}" sem '
                        "intenção correspondente.")
    params = dict(operacao.parametros)
    return AIIntent.from_dict({
        "tipo": reverso[operacao.tipo],
        "personagem": operacao.alvo.nome,
        "alvo": operacao.alvo.nome, "parametros": params})


def operacao_para_ferramentas(operacao, base: dict | None = None,
                              personagem: str = "") -> list[dict]:
    """Op → chamadas F26 (via F30; alteração/consulta = via F28)."""
    from .inteligencia import intent_para_ferramentas

    if isinstance(operacao, SemanticEventOperation):
        saidas = []
        for efeito in operacao.efeitos:
            saidas.extend(operacao_para_ferramentas(
                efeito, base, personagem))
        return saidas
    if not isinstance(operacao, SemanticOperation):
        raise ErroELiXX("Semântica: espera operação.")
    if operacao.tipo in OPERACOES_ARQUIVO or \
            operacao.tipo in OPERACOES_CONSULTA:
        return []  # arquivo/consulta: loop F28, sem atalho
    return intent_para_ferramentas(
        operacao_para_intent(operacao),
        personagem or operacao.alvo.nome, base)


def operacao_para_proposta(operacao: SemanticOperation, workspace,
                           modelo, permissoes=None):
    """Op de arquivo → ChangeSet F26 (mesclar+validar antes).

    Conteúdo: explícito em `alteracao.conteudo_novo`, ou snippet
    (só `adicionar_evento` com `snippet` em alteracao) mesclado ao
    final do arquivo do alvo. O MERGIDO precisa passar no parser;
    senão recusa documentada (limitação honesta: `quando` não é
    top-level — ver docs).
    """
    from ..editor import diagnosticar_texto
    from .inteligencia import intent_para_agentintent
    from .loop import (PlanoSemantico, gerar_changeset,
                       resolver_alvo, verificar_precondicoes)

    if not isinstance(operacao, SemanticOperation):
        raise ErroELiXX("Semântica: espera SemanticOperation.")
    if operacao.tipo not in OPERACOES_ARQUIVO:
        raise ErroELiXX(f'Semântica: "{operacao.tipo}" não gera '
                        "ChangeSet (consulta/runtime usam outro "
                        "caminho).")
    if not operacao.alteracao or not operacao.alteracao.get(
            "arquivo"):
        raise ErroELiXX("Semântica: alteração sem arquivo.")
    arquivo = str(operacao.alteracao["arquivo"])
    atual = workspace.resolver(arquivo).read_text(
        encoding="utf-8") if workspace.existe(arquivo) else ""
    if operacao.alteracao.get("conteudo_novo") is not None:
        novo = str(operacao.alteracao["conteudo_novo"])
    elif operacao.alteracao.get("snippet"):
        novo = atual + ("\n" if atual and not atual.endswith(
            "\n") else "") + str(operacao.alteracao["snippet"])
        erros = [d for d in diagnosticar_texto(novo, arquivo)
                 if d.severidade == "error"]
        if erros:
            raise ErroELiXX(
                f"Semântica: mesclado inválido "
                f"({erros[0].mensagem[:150]}). Eventos `quando` "
                "só valem dentro de janela/componente — informe "
                "conteúdo completo ou revise o alvo.")
    else:
        raise ErroELiXX("Semântica: alteração sem "
                        "conteudo_novo/snippet.")
    alvo = resolver_alvo(modelo, operacao.alvo.nome,
                         operacao.alvo.tipo)
    if alvo["status"] != "unico":
        raise ErroELiXX(f"Semântica: alvo {alvo['status']} "
                        "(sem ChangeSet).")
    from .intencao import AgentIntent

    aintent = AgentIntent(
        _TIPO_F26_OP.get(operacao.tipo, "modificar_interface"),
        objetivo=f"{operacao.tipo} {operacao.alvo.nome}",
        parametros={"alvo": operacao.alvo.nome,
                    **operacao.parametros},
        origem="semantica")
    plano = PlanoSemantico(
        aintent, alvo=alvo,
        entidades=[alvo["entidade"]["id"]],
        alteracoes_propostas=[{
            "arquivo": arquivo,
            "operacao": "editar" if workspace.existe(arquivo)
            else "criar",
            "conteudo_novo": novo,
            "descricao": f"{operacao.tipo} {operacao.alvo.nome}",
            "risco": "medio"}])
    pre = verificar_precondicoes(
        plano, workspace, permissoes or _permissoes_leitura())
    if any(not c["ok"] for c in pre):
        raise ErroELiXX("Semântica: pré-condição falhou "
                        f"({[c['nome'] for c in pre if not c['ok']]})")
    return gerar_changeset(plano)


def _permissoes_leitura():
    from .permissao import PermissionSet

    return PermissionSet(["READ"])


# ----- explicação determinística (ETAPA 9; sem LLM) -----

def explicar_operacao(operacao) -> str:
    """Frase PT fixa por forma (depuração futura)."""
    if isinstance(operacao, SemanticEventOperation):
        efeitos = " e ".join(
            f"{e.tipo} '{e.parametros.get('pose') or e.parametros.get('expressao') or ''}'".strip()
            for e in operacao.efeitos)
        base = (f"Entendi que você quer associar o "
                f"{operacao.gatilho} de '{operacao.alvo.nome}' "
                f"a: {efeitos}.")
        if operacao.condicao:
            base += " (com condição planejada, sem execução)."
        if operacao.modo == "paralelo":
            base += " Ações em paralelo."
        return base
    if not isinstance(operacao, SemanticOperation):
        raise ErroELiXX("Semântica: espera operação.")
    nome = operacao.alvo.nome
    prm = operacao.parametros
    frases = {
        "pose": f"aplicar a pose '{prm.get('pose', '')}' à '{nome}'",
        "expressao": f"aplicar a expressão "
                     f"'{prm.get('expressao', '')}' à '{nome}'",
        "mover": f"mover '{nome}' para {prm.get('direcao', '')}",
        "mostrar": f"mostrar '{nome}'",
        "esconder": f"esconder '{nome}'",
        "consultar": f"consultar '{nome}'",
        "selecionar": f"selecionar '{nome}'",
        "animar": f"animar '{nome}'",
        "alterar_propriedade": f"alterar '{nome}'",
        "adicionar_evento": f"adicionar evento a '{nome}'",
        "associar_acao": f"associar ação a '{nome}'",
    }
    acao = frases.get(operacao.tipo, f"atuar em '{nome}'")
    return f"Entendi que você quer {acao}."
