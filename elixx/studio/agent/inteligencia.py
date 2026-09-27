"""Intelligence Provider (Fase 30) — texto natural vira AIIntent.

"O Provider interpreta pedidos; ele não executa ações."

"A Intent é uma descrição de intenção, não código executável."

Camada desacoplada sobre F18 (`AIIntent`/`AIProvider` reutilizados,
sem segundo sistema de intenção): `IntelligenceProvider` adiciona
`pedido` explícito + origem; `MockIntentProvider` reconhece comandos
PT documentados e determinísticos; desconhecido = INTENT_NAO_SUPORTADA
(erro estruturado, sem invenção). Ações de alteração nunca executam:
viram proposta via F28/ChangeSet.

Sem LLM, sem rede, sem modelo, sem API keys — offline, stdlib.
"""
from __future__ import annotations

import json
import math
import re

from ...erros import ErroELiXX
from ...visual.ai_bridge import AIIntent, AIProvider

__all__ = [
    "ACOES_INTENT",
    "ACOES_ALTERACAO",
    "DIRECOES",
    "MAX_PEDIDO_CHARS",
    "MAX_PARAMETROS",
    "IntelligenceProvider",
    "MockIntentProvider",
    "IntentContext",
    "ProviderRegistry",
    "AgentChat",
    "contexto_de_intencao",
    "validar_intent",
    "intent_para_agentintent",
    "intent_para_ferramentas",
    "explicar",
]

ACOES_INTENT = ("mover", "mostrar", "esconder", "animar",
                "expressao", "pose", "selecionar", "consultar",
                "adicionar", "alterar", "remover",
                "associar_evento")
"""Ações studio suportadas (alteração só via F28/ChangeSet)."""

ACOES_ALTERACAO = ("adicionar", "alterar", "remover")
"""Ações que exigem ChangeSet aprovado (nunca diretas)."""

DIRECOES = ("direita", "esquerda", "cima", "baixo", "centro")
"""Direções do mover/olhar (vocabulário fechado)."""

MAX_PEDIDO_CHARS = 2000
"""Teto do pedido (sem payload gigante)."""

MAX_PARAMETROS = 20
"""Teto de parâmetros por intenção."""


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


def _finito(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'Intent: "{o_que}" numérico.')
    if not math.isfinite(numero):
        raise ErroELiXX(f'Intent: "{o_que}" finito.')
    if abs(numero) > 1.0e9:
        raise ErroELiXX(f'Intent: "{o_que}" gigante.')
    return numero


# ----- provider (ETAPA 2; estende AIProvider F18) -----

class IntelligenceProvider(AIProvider):
    """Fronteira texto→AIIntent (pedido explícito; sem filesystem).

    Futuro: LocalProvider/RemotoProvider/Multimodal herdam daqui sem
    tocar o Agent (mesmo `gerar_intencao`, mesmos validadores).
    """

    def __init__(self, nome: str = "inteligencia") -> None:
        super().__init__(nome)
        self.origem = "intelligence"

    def gerar_intencao(self, contexto=None, pedido: str = ""):
        """Contexto + pedido → AIIntent (implementar na subclasse)."""
        raise ErroELiXX(
            f'Provider "{self.nome}": geração não implementada '
            "(use MockIntentProvider nesta fase).")

    def indisponivel(self, motivo: str = "") -> ErroELiXX:
        """Erro estruturado padrão (sem traceback cru na UI)."""
        return ErroELiXX(
            f"PROVIDER_INDISPONIVEL: {self.nome} "
            f"({motivo or 'sem motivo'}).")


# ----- contexto controlado (sem segredos, sem objetos) -----

class IntentContext:
    """Snapshot controlado para o provider (só dados permitidos)."""

    def __init__(self, projeto: str = "", arquivo: str = "",
                 selecionado: dict | None = None,
                 entidades: list | None = None,
                 acoes: list | None = None) -> None:
        self.projeto = str(projeto)
        self.arquivo = str(arquivo)
        sel = dict(selecionado or {})
        if not _e_dado(sel):
            raise ErroELiXX("Intent: selecionado inválido.")
        self.selecionado = sel
        self.entidades = []
        for e in (entidades or []):
            if not isinstance(e, dict) or not _e_dado(e):
                raise ErroELiXX("Intent: entidade inválida.")
            self.entidades.append({k: e[k] for k in
                                   ("id", "tipo", "nome",
                                    "arquivo", "partes", "poses")
                                   if k in e})
        self.acoes = [str(a) for a in (acoes or [])]
        for a in self.acoes:
            if a not in ACOES_INTENT:
                raise ErroELiXX(f'Intent: ação "{a}" indisponível.')

    def to_dict(self) -> dict:
        return {"projeto": self.projeto, "arquivo": self.arquivo,
                "selecionado": dict(self.selecionado),
                "entidades": list(self.entidades),
                "acoes": list(self.acoes)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"IntentContext({self.projeto}: "
                f"{len(self.entidades)} ent)")


def contexto_de_intencao(projeto: str = "", arquivo: str = "",
                         selecionado: dict | None = None,
                         entidades: list | None = None) -> dict:
    """Construtor honesto: só os campos permitidos (sem segredos)."""
    return IntentContext(
        projeto, arquivo, selecionado, entidades,
        acoes=list(ACOES_INTENT)).to_dict()


# ----- mock determinístico em PT (ETAPA 4) -----

def _norm(pedido: str) -> str:
    import unicodedata

    texto = unicodedata.normalize("NFKD", str(pedido or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(
        c)).lower()
    return re.sub(r"\s+", " ", texto).strip()


class MockIntentProvider(IntelligenceProvider):
    """Reconhece comandos PT documentados (100% determinístico).

    Padrões (normalizados sem acento, minúsculos):
    - "mova X para <direcao>" → mover/X/direcao
    - "faca X sorrir" → expressao/X/sorrindo
    - "faca X acenar" → pose/X/acenar
    - "mostre X" → mostrar/X · "esconda X" → esconder/X
    - "selecione X" → selecionar/X
    - "o que e X?" / "mostre ..." → consultar
    - "quando clicar em X, faca ... acenar" → associar_evento
    Fora disso: INTENT_NAO_SUPORTADA (sem invenção).
    """

    def __init__(self, nome: str = "mock") -> None:
        super().__init__(nome)

    def gerar_intencao(self, contexto=None, pedido: str = ""):
        if not isinstance(pedido, str) or not pedido.strip():
            raise ErroELiXX("INTENCAO_INVALIDA: pedido vazio.")
        if len(pedido) > MAX_PEDIDO_CHARS:
            raise ErroELiXX("INTENCAO_INVALIDA: pedido além de "
                            f"{MAX_PEDIDO_CHARS} chars.")
        texto = _norm(pedido)
        achado = self._casar(texto, pedido)
        if achado is None:
            raise ErroELiXX(
                "INTENT_NAO_SUPORTADA: comando fora do vocabulário "
                "documentado (sem invenção).")
        tipo, alvo, params = achado
        return AIIntent.from_dict({
            "tipo": tipo, "personagem": alvo, "alvo": alvo,
            "parametros": params,
            "contexto": {"pedido": pedido[:500],
                         "provider": self.nome}})

    @staticmethod
    def _nome_original(original: str, indice: int):
        """Token do pedido original (preserva caixa: Juh ≠ juh)."""
        palavras = str(original).strip().split()
        if not 0 <= indice < len(palavras):
            return None
        token = palavras[indice].strip("?!,.:;")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", token):
            return token
        return None

    @classmethod
    def _casar(cls, texto: str, original: str):
        w = texto.split()
        # "mova [a|o] N para [[a|o] D]": nome no índice 2.
        if len(w) >= 5 and w[0] == "mova" and w[1] in ("a", "o"):
            resto_mover = list(w[3:])
            if resto_mover[:1] == ["para"]:
                resto_mover = resto_mover[1:]
            if resto_mover[:1] in (["a"], ["o"]):
                resto_mover = resto_mover[1:]
            if len(resto_mover) == 1 and resto_mover[0] in DIRECOES:
                nome = cls._nome_original(original, 2)
                if nome:
                    return ("mover", nome,
                            {"direcao": resto_mover[0]})
        if w[:1] == ["faca"] and w[-1:] == ["sorrir"] \
                and len(w) in (3, 4) and (len(w) == 3
                                          or w[1] in ("a", "o")):
            nome = cls._nome_original(original, len(w) - 2)
            if nome:
                return ("expressao", nome,
                        {"expressao": "sorrindo"})
        if w[:1] == ["faca"] and w[-1:] == ["acenar"] \
                and len(w) in (3, 4) and (len(w) == 3
                                          or w[1] in ("a", "o")):
            nome = cls._nome_original(original, len(w) - 2)
            if nome:
                return ("pose", nome, {"pose": "acenar"})
        if len(w) == 3 and w[0] in ("mostre", "esconda",
                                    "selecione") \
                and w[1] in ("a", "o"):
            nome = cls._nome_original(original, 2)
            if nome:
                acao = {"mostre": "mostrar",
                        "esconda": "esconder",
                        "selecione": "selecionar"}[w[0]]
                return (acao, nome, {})
        if len(w) >= 7 and w[0] == "quando" and w[1] == "clicar" \
                and w[2] in ("em", "na", "no") \
                and "acenar" in w[-2:]:
            nome = cls._nome_original(original, 3)
            if nome:
                return ("associar_evento", nome,
                        {"evento": "clique", "efeito": "acenar"})
        resto: list[str] = []
        if w[:3] == ["o", "que", "e"]:
            resto = list(w[3:])
        elif w[:2] == ["quem", "e"]:
            resto = list(w[2:])
        elif w[:1] == ["descreva"]:
            resto = list(w[1:])
        if resto and resto[0] in ("a", "o"):
            resto = resto[1:]
        if len(resto) == 1:
            alvo = resto[0].rstrip("?")
            idx = next((i for i, t in enumerate(w)
                        if t.rstrip("?") == alvo), -1)
            if idx >= 0:
                nome = cls._nome_original(original, idx)
                if nome:
                    return ("consultar", nome, {})
        return None


# ----- validação forte (ETAPA 5) -----

def validar_intent(intent) -> dict:
    """AIIntent → {valido, codigo, motivo} (estilo F18, domínio PT).

    Códigos: ok, intencao_invalida, acao_desconhecida, alvo_ausente,
    parametros_invalidos, payload_excedido.
    """
    if not isinstance(intent, AIIntent):
        return {"valido": False, "codigo": "intencao_invalida",
                "motivo": "Intenção deve ser AIIntent."}
    if intent.tipo not in ACOES_INTENT:
        return {"valido": False, "codigo": "acao_desconhecida",
                "motivo": f'Ação "{intent.tipo}" fora de '
                          f'({", ".join(ACOES_INTENT)}).'}
    alvo = intent.personagem or intent.alvo
    if not alvo:
        return {"valido": False, "codigo": "alvo_ausente",
                "motivo": f'Ação "{intent.tipo}" sem alvo.'}
    params = intent.parametros or {}
    if not isinstance(params, dict):
        return {"valido": False, "codigo": "parametros_invalidos",
                "motivo": "Parâmetros em dicionário."}
    if len(params) > MAX_PARAMETROS:
        return {"valido": False, "codigo": "payload_excedido",
                "motivo": f"Máximo {MAX_PARAMETROS} parâmetros."}
    if not _e_dado(params):
        return {"valido": False, "codigo": "parametros_invalidos",
                "motivo": "Parâmetros com NaN/Infinity/recursão."}
    for chave, valor in params.items():
        if chave == "direcao" and valor not in DIRECOES:
            return {"valido": False,
                    "codigo": "parametros_invalidos",
                    "motivo": f'Direção "{valor}" inválida.'}
        if chave in ("duracao", "valor") and isinstance(
                valor, (int, float)):
            try:
                _finito(valor, chave)
            except ErroELiXX as exc:
                return {"valido": False,
                        "codigo": "parametros_invalidos",
                        "motivo": str(exc)[:200]}
    return {"valido": True, "codigo": "ok",
            "motivo": "Intenção válida."}


# ----- pontes F26/F28 (ETAPA 6; sem duplicar Agent) -----

_TIPO_F26 = {
    "mover": "modificar_personagem",
    "mostrar": "modificar_interface",
    "esconder": "modificar_interface",
    "animar": "criar_animacao",
    "expressao": "modificar_personagem",
    "pose": "modificar_personagem",
    "selecionar": "modificar_interface",
    "consultar": "diagnosticar",
    "adicionar": "criar_cena",
    "alterar": "modificar_interface",
    "remover": "modificar_interface",
    "associar_evento": "modificar_interface",
}
"""AIIntent.tipo → AgentIntent F26 (documentado; sem adivinhar)."""


def intent_para_agentintent(intent: AIIntent):
    """AIIntent F18 → AgentIntent F26 (só dados, sem executar)."""
    from .intencao import AgentIntent

    valido = validar_intent(intent)
    if not valido["valido"]:
        raise ErroELiXX(f"INTENCAO_INVALIDA: {valido['motivo']}")
    alvo = intent.personagem or intent.alvo
    params = dict(intent.parametros or {})
    params.setdefault("alvo", alvo)
    return AgentIntent(
        _TIPO_F26[intent.tipo],
        objetivo=f"{intent.tipo} {alvo}",
        parametros=params, origem="intelligence")


_FERRAMENTA_ACAO = {
    "pose": "personagem_pose",
    "expressao": "personagem_expressao",
    "mover": "personagem_transform",
    "mostrar": "personagem_transform",
    "esconder": "personagem_transform",
    "selecionar": "personagem_transform",
    "animar": "personagem_gesto",
    "associar_evento": "personagem_gesto",
}
"""Ação → ferramenta F26 (consultar/adicionar/alterar/remover vão
pelo loop semântico, não por ferramenta direta)."""


def intent_para_ferramentas(intent: AIIntent, personagem: str = "",
                            base: dict | None = None
                            ) -> list[dict]:
    """AIIntent → chamadas de ferramenta F26 (dados, sem executar).

    Ações de alteração (adicionar/alterar/remover) e consultar NÃO
    geram ferramenta direta: usam F28 (resolver_alvo + ChangeSet).
    `mover` exige `base` {"posicao": [x, y]} (posição atual lida do
    personagem): deslocamento sempre relativo, nunca chute absoluto.
    """
    valido = validar_intent(intent)
    if not valido["valido"]:
        raise ErroELiXX(f"INTENCAO_INVALIDA: {valido['motivo']}")
    if intent.tipo in ACOES_ALTERACAO or intent.tipo == "consultar":
        return []  # via loop semântico F28 (sem atalho)
    ferramenta = _FERRAMENTA_ACAO.get(intent.tipo)
    if ferramenta is None:
        raise ErroELiXX(f"INTENCAO_INVALIDA: sem ferramenta para "
                        f'"{intent.tipo}".')
    alvo = personagem or intent.personagem or intent.alvo or ""
    params = dict(intent.parametros or {})
    if intent.tipo == "pose" and "pose" in params:
        args = {"personagem": alvo, "pose": params["pose"]}
    elif intent.tipo == "expressao" and "expressao" in params:
        args = {"personagem": alvo, "expressao": params["expressao"]}
    elif intent.tipo == "mover":
        d = params.get("direcao", "centro")
        mapa = {"direita": (30.0, 0.0), "esquerda": (-30.0, 0.0),
                "cima": (0.0, -30.0), "baixo": (0.0, 30.0),
                "centro": (0.0, 0.0)}
        dx, dy = mapa.get(d, (0.0, 0.0))
        if not isinstance(base, dict) or "posicao" not in base:
            raise ErroELiXX("INTENCAO_INVALIDA: mover exige base "
                            '{"posicao": [x, y]} (sem chute).')
        bx, by = base["posicao"]
        args = {"personagem": alvo, "parte": params.get(
            "parte", "corpo"),
            "props": {"posicao": [float(bx) + dx,
                                  float(by) + dy]}}
    elif intent.tipo in ("mostrar", "esconder", "selecionar"):
        args = {"personagem": alvo, "parte": params.get(
            "parte", "corpo"),
            "props": {"opacidade":
                      1.0 if intent.tipo != "esconder" else 0.0}}
    else:
        args = {"personagem": alvo}
        args.update({k: v for k, v in params.items()
                     if k in ("gesto", "nome", "pose",
                              "expressao")})
    return [{"ferramenta": ferramenta, "argumentos": args}]


def explicar(pedido: str, intent: AIIntent,
             resolucao: dict | None = None,
             plano: dict | None = None,
             changeset: dict | None = None) -> dict:
    """Rastro Pedido→Intenção→Consulta→Plano→ChangeSet (depuração)."""
    valido = validar_intent(intent)
    return {
        "pedido": str(pedido)[:500],
        "intencao": {"acao": intent.tipo,
                     "alvo": intent.personagem or intent.alvo,
                     "parametros": intent.parametros or {},
                     "valida": valido["valido"],
                     "codigo": valido["codigo"]},
        "consulta": dict(resolucao or {}),
        "plano": dict(plano or {}),
        "changeset": dict(changeset or {}),
        "nota": "Provider Mock/determinístico (sem LLM).",
    }


# ----- registry (sem import dinâmico, sem plugins) -----

class ProviderRegistry:
    """Nome → provider instanciado (registro explícito)."""

    def __init__(self) -> None:
        self._providers: dict = {}

    def registrar(self, provider: IntelligenceProvider
                  ) -> IntelligenceProvider:
        if not isinstance(provider, IntelligenceProvider):
            raise ErroELiXX("Registry espera IntelligenceProvider.")
        if provider.nome in self._providers:
            raise ErroELiXX(f'Provider "{provider.nome}" duplicado.')
        self._providers[provider.nome] = provider
        return provider

    def obter(self, nome: str) -> IntelligenceProvider:
        try:
            return self._providers[str(nome)]
        except KeyError:
            raise ErroELiXX(f'Provider "{nome}" desconhecido '
                            "(mock/local/remoto registrados "
                            "explicitamente).")

    def listar(self) -> list[str]:
        return sorted(self._providers)

    def __repr__(self) -> str:
        return f"ProviderRegistry({self.listar()})"


# ----- chat headless do Studio (ETAPA 7) -----

class AgentChat:
    """Conversa estruturada: pedido → intent → resolução → proposta.

    Sem LLM: mostra a intent + consulta F27 + plano F28; alteração só
    via ChangeSet aprovado fora daqui. Deixa claro que o provider é
    Mock/determinístico.
    """

    def __init__(self, provider=None) -> None:
        self.provider = provider or MockIntentProvider()
        if not isinstance(self.provider, IntelligenceProvider):
            raise ErroELiXX("Chat espera IntelligenceProvider.")
        self.historico: list[dict] = []

    def enviar(self, pedido: str, modelo=None,
               contexto: dict | None = None) -> dict:
        """Um turno: intent validada + resolução opcional (sem atos)."""
        try:
            intent = self.provider.gerar_intencao(contexto,
                                                  pedido)
        except ErroELiXX as exc:
            resposta = {"ok": False, "codigo": "INTENT_FALHOU",
                        "motivo": str(exc)[:300],
                        "provider": self.provider.nome}
            self.historico.append({"pedido": str(pedido)[:500],
                                   "resposta": resposta})
            return resposta
        valido = validar_intent(intent)
        resolucao: dict = {}
        if modelo is not None and valido["valido"]:
            from .loop import resolver_alvo

            alvo = intent.personagem or intent.alvo or ""
            resolucao = resolver_alvo(modelo, alvo) if alvo \
                else {"status": "nao_encontrado"}
        resposta = {
            "ok": valido["valido"], "provider": self.provider.nome,
            "mock": isinstance(self.provider, MockIntentProvider),
            "intencao": {"acao": intent.tipo,
                         "alvo": intent.personagem or intent.alvo,
                         "parametros": intent.parametros or {}},
            "validacao": valido, "resolucao": resolucao,
            "explicacao": explicar(pedido, intent, resolucao),
        }
        self.historico.append({"pedido": str(pedido)[:500],
                               "resposta": resposta})
        return resposta

    def __repr__(self) -> str:
        return (f"AgentChat({self.provider.nome}, "
                f"{len(self.historico)} turnos)")
