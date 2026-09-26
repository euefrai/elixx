"""AI Bridge da ELiXX (Fase 18) — ponte segura IA/agente → ELiXX.

A IA pensa em INTENÇÃO; o ELiXX transforma em PLANO, valida e executa
apenas estruturas permitidas. Este módulo NÃO contém inteligência
artificial, LLM, NLP, física ou comportamento autônomo: é composição
determinística dos sistemas existentes (F14 → F15 → F16 → F17).

    AIIntent → IntentValidator → AIPlannerBridge → AIPlan
        → (dry-run | executar via F17) → resultado estruturado

Segurança: nomes e parâmetros são dados inertes. Nenhuma chamada de
avaliação ou execução dinâmica, nenhuma importação programática, nenhum
processo externo, nenhum código remoto e nenhuma execução de texto como
código — em nenhum caminho deste módulo.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from ..erros import ErroELiXX

__all__ = [
    "TIPOS_INTENCAO",
    "TIPOS_IMPLEMENTADOS",
    "AIIntent",
    "IntentValidator",
    "AIProvider",
    "AIPlan",
    "AIPlannerBridge",
    "debug_ai_plan",
    "texto_para_intencao",
]

TIPOS_INTENCAO = ("mover", "ir", "olhar", "apontar", "interagir", "pegar",
                  "equipar", "usar")
"""Tipos aceitos na gramática da intenção (só dados)."""

TIPOS_IMPLEMENTADOS = ("mover", "ir")
"""Tipos com pipeline completo; demais: suportado=False (honesto)."""

_CAMPOS_INTENT = ("tipo", "agente", "personagem", "destino", "alvo", "modo",
                  "pose", "expressao", "prioridade", "contexto",
                  "parametros")
"""Contrato fechado da intenção (campo fora disso é rejeitado)."""

_PROFUNDIDADE_MAXIMA = 4
"""Limite de aninhamento para contexto/parametros (dados limitados)."""


# ----- utilidades de dados -----

def _e_dado(valor, profundidade=0) -> bool:
    """Apenas tipos JSON puros (sem tupla, sem objeto, sem código)."""
    if profundidade > _PROFUNDIDADE_MAXIMA:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        if isinstance(valor, float) and not math.isfinite(valor):
            return False
        return True
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(item, profundidade + 1) for item in valor)
    if isinstance(valor, dict):
        return all(isinstance(chave, str)
                   and _e_dado(item, profundidade + 1)
                   for chave, item in valor.items())
    return False


def _texto_ou_nulo(valor, campo: str) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ErroELiXX(
            f'Campo "{campo}" da intenção deve ser texto '
            f"(recebido {type(valor).__name__}).")
    texto = valor.strip()
    return texto or None


# ----- AIIntent -----

@dataclass
class AIIntent:
    """Intenção declarada (só dados; nunca executada como código)."""

    tipo: str = ""
    agente: str | None = None
    personagem: str | None = None
    destino: object = None  # str (entidade/nó) ou {"x": n, "y": n}
    alvo: str | None = None
    modo: str | None = None
    pose: str | None = None
    expressao: str | None = None
    prioridade: str = "normal"
    contexto: dict | None = None
    parametros: dict | None = None

    @staticmethod
    def from_dict(dados: object) -> "AIIntent":
        """Valida a estrutura (nunca executa conteúdo)."""
        if not isinstance(dados, dict):
            raise ErroELiXX(
                "Intenção deve ser um dicionário "
                f"(recebido {type(dados).__name__}).")
        desconhecidos = sorted(set(dados) - set(_CAMPOS_INTENT))
        if desconhecidos:
            raise ErroELiXX(
                f'Campo desconhecido na intenção: {", ".join(desconhecidos)}. '
                f'Válidos: {", ".join(_CAMPOS_INTENT)}.')
        for chave, valor in dados.items():
            if not _e_dado(valor):
                raise ErroELiXX(
                    f'Campo "{chave}" da intenção tem valor inválido '
                    "(apenas texto, número finito, lógico, nulo, lista ou "
                    "dicionário).")
        tipo = dados.get("tipo", "")
        if not isinstance(tipo, str) or not tipo.strip():
            raise ErroELiXX('Campo "tipo" da intenção é obrigatório '
                            "(texto não vazio).")
        destino = dados.get("destino")
        if destino is not None and not isinstance(destino, (str, dict)):
            raise ErroELiXX('Campo "destino" deve ser texto ou {"x", "y"}.')
        if isinstance(destino, dict):
            if sorted(destino) != ["x", "y"] or not all(
                    isinstance(destino[eixo], (int, float))
                    and math.isfinite(destino[eixo]) for eixo in ("x", "y")):
                raise ErroELiXX(
                    'Destino coordenado deve ser {"x": número, "y": número} '
                    "com valores finitos.")
        contexto = dados.get("contexto")
        if contexto is not None and not isinstance(contexto, dict):
            raise ErroELiXX('Campo "contexto" deve ser dicionário ou nulo.')
        parametros = dados.get("parametros")
        if parametros is not None and not isinstance(parametros, dict):
            raise ErroELiXX(
                'Campo "parametros" deve ser dicionário ou nulo.')
        return AIIntent(
            tipo=tipo.strip(),
            agente=_texto_ou_nulo(dados.get("agente"), "agente"),
            personagem=_texto_ou_nulo(dados.get("personagem"),
                                      "personagem"),
            destino=(dict(destino) if isinstance(destino, dict)
                     else _texto_ou_nulo(destino, "destino")),
            alvo=_texto_ou_nulo(dados.get("alvo"), "alvo"),
            modo=_texto_ou_nulo(dados.get("modo"), "modo"),
            pose=_texto_ou_nulo(dados.get("pose"), "pose"),
            expressao=_texto_ou_nulo(dados.get("expressao"), "expressao"),
            prioridade=_texto_ou_nulo(dados.get("prioridade"),
                                      "prioridade") or "normal",
            contexto=dict(contexto) if contexto is not None else None,
            parametros=dict(parametros) if parametros is not None else None,
        )

    @staticmethod
    def from_json(texto: str) -> "AIIntent":
        """JSON validado (sem código; só dados)."""
        if not isinstance(texto, str):
            raise ErroELiXX("Intenção JSON deve ser texto.")
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Intenção JSON inválida: {exc}.")
        return AIIntent.from_dict(dados)

    def to_dict(self) -> dict:
        """Representação JSON-segura (só dados)."""
        return {"tipo": self.tipo, "agente": self.agente,
                "personagem": self.personagem, "destino": self.destino,
                "alvo": self.alvo, "modo": self.modo, "pose": self.pose,
                "expressao": self.expressao, "prioridade": self.prioridade,
                "contexto": self.contexto, "parametros": self.parametros}

    def to_json(self) -> str:
        """Serializa (garante só dados antes de serializar)."""
        dados = self.to_dict()
        if not _e_dado(dados):
            raise ErroELiXX("Intenção contém valores não serializáveis.")
        return json.dumps(dados, ensure_ascii=False, sort_keys=True)


# ----- validador -----

class IntentValidator:
    """Valida estrutura e referências (nunca executa conteúdo)."""

    def validar(self, intent: AIIntent, personagens: dict,
                mundos: dict, grafos: dict) -> dict:
        """{"valido", "codigo", "motivo"} — determinístico, sem efeitos."""
        if not isinstance(intent, AIIntent):
            return self._falha("intencao_invalida",
                               "Intenção deve ser AIIntent.")
        if intent.tipo not in TIPOS_INTENCAO:
            return self._falha(
                "tipo_desconhecido",
                f'Tipo de intenção desconhecido: "{intent.tipo}". '
                f'Válidos: {", ".join(TIPOS_INTENCAO)}.')
        if intent.personagem is None:
            return self._falha("personagem_ausente",
                               "Intenção sem personagem (nome obrigatório).")
        if intent.personagem not in personagens:
            return self._falha(
                "personagem_inexistente",
                f'Personagem "{intent.personagem}" não existe.')
        if intent.tipo in ("mover", "ir") and intent.destino is None:
            return self._falha("destino_ausente",
                               "Intenção mover/ir sem destino.")
        if intent.destino is not None:
            resultado = self._validar_destino(intent, mundos, grafos)
            if resultado is not None:
                return resultado
        if intent.modo is not None:
            from .sintese_movimento import MODOS_SINTESE

            if intent.modo not in MODOS_SINTESE:
                return self._falha(
                    "modo_invalido",
                    f'Modo "{intent.modo}" inválido. '
                    f'Válidos: {", ".join(MODOS_SINTESE)}.')
        personagem = personagens[intent.personagem]
        if intent.pose is not None:
            try:
                personagem.obter_pose(intent.pose)
            except ErroELiXX:
                return self._falha(
                    "pose_inexistente",
                    f'Pose "{intent.pose}" não existe no personagem '
                    f'"{intent.personagem}".')
        if intent.expressao is not None:
            try:
                personagem.obter_pose(intent.expressao)
            except ErroELiXX:
                return self._falha(
                    "expressao_inexistente",
                    f'Expressão "{intent.expressao}" não existe no '
                    f'personagem "{intent.personagem}".')
        return {"valido": True, "codigo": "ok",
                "motivo": "Intenção válida."}

    @staticmethod
    def _falha(codigo: str, motivo: str) -> dict:
        return {"valido": False, "codigo": codigo, "motivo": motivo}

    @staticmethod
    def _validar_destino(intent: AIIntent, mundos: dict,
                         grafos: dict) -> dict | None:
        """None = destino existe; senão falha estruturada."""
        destino = intent.destino
        if isinstance(destino, dict):
            return None  # {"x","y"} já validado no from_dict
        texto = str(destino)
        for mundo in mundos.values():
            try:
                mundo.por_id(texto)
                return None
            except ErroELiXX:
                pass
        for grafo in grafos.values():
            if texto in getattr(grafo, "nos", {}):
                return None
            if f"ent:{texto}" in getattr(grafo, "nos", {}):
                return None
        return IntentValidator._falha(
            "destino_inexistente",
            f'Destino "{texto}" não existe (entidade, ponto ou nó).')


# ----- provider neutro (fronteira Fajulto/JÚLIA; sem acoplamento) -----

class AIProvider:
    """Interface neutra de provedor de intenções (sobrescrever)."""

    def __init__(self, nome: str = "externo") -> None:
        self.nome = str(nome)

    def gerar_intencao(self, contexto: dict) -> AIIntent:
        """Produz AIIntent a partir de contexto (implementar fora)."""
        raise NotImplementedError(
            "AIProvider.gerar_intencao deve ser implementado pelo provedor "
            "(modelo local, API, agente externo, JÚLIA, Fajulto).")


def texto_para_intencao(texto: str):
    """Fronteira texto → AIIntent (NÃO implementada: sem NLP improvisado)."""
    _ = texto
    raise ErroELiXX(
        "Conversão texto→intenção não implementada nesta fase "
        "(fronteira reservada para futuro parser/LLM). "
        "Monte AIIntent com dicionário validado.")


# ----- plano -----

@dataclass
class AIPlan:
    """Plano inspecionável (planejar nunca movimenta)."""

    intent: object = None  # AIIntent
    validacao: dict = field(default_factory=dict)
    traversal_plan: object = None
    motion_plan: object = None
    behavior_plan: object = None
    requisitos: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    rotas: list = field(default_factory=list)  # resumos alternativos
    viavel: bool = False
    suportado: bool = True
    executavel: bool = False
    requer_escolha: bool = False
    motivo: str = ""
    eventos: list = field(default_factory=list)  # log declarativo

    def registrar(self, evento: str) -> None:
        """Anexa evento ao log (sem scheduler, sem efeitos)."""
        self.eventos.append({"evento": evento})

    def resumo_rotas(self) -> list[dict]:
        """Alternativas em forma inspecionável (para escolha explícita)."""
        saida = []
        for rota in self.rotas:
            saida.append({"nos": list(rota.get("nos", [])),
                          "modos": list(rota.get("modos", [])),
                          "custo_total": rota.get("custo_total", 0.0),
                          "requisitos": list(rota.get("requisitos", []))})
        return saida


# ----- ponte -----

class AIPlannerBridge:
    """Intenção → validação → F14 → F15 → F16 → F17 (determinístico).

    Composição dos sistemas existentes; nenhuma decisão além de regras
    explícitas e documentadas. Planejar nunca movimenta.
    """

    def __init__(self, cena, personagens: dict, mundos: dict,
                 grafos: dict, itens: dict | None = None) -> None:
        self.cena = cena
        self.personagens = dict(personagens)
        self.mundos = dict(mundos)
        self.grafos = dict(grafos)
        self.itens = itens
        self.validador = IntentValidator()

    # ----- planejamento (dry-run; sem efeitos) -----

    def planejar(self, intent) -> AIPlan:
        """AIIntent|dict → AIPlan inspecionável (nunca movimenta)."""
        if isinstance(intent, dict):
            intent = AIIntent.from_dict(intent)
        plano = AIPlan(intent=intent)
        plano.registrar("ai_plano_criado")
        validacao = self.validador.validar(intent, self.personagens,
                                           self.mundos, self.grafos)
        plano.validacao = validacao
        if not validacao["valido"]:
            plano.registrar("ai_plano_rejeitado")
            plano.motivo = validacao["motivo"]
            return plano
        plano.registrar("ai_plano_validado")
        if intent.tipo not in TIPOS_IMPLEMENTADOS:
            plano.suportado = False
            plano.motivo = (
                f'Intenção "{intent.tipo}" válida, mas ainda não '
                "implementada (honesto: sem fingir suporte).")
            return plano
        return self._planejar_mover(plano, intent)

    simular = planejar
    """Dry-run explícito: planejar nunca movimenta (mesma função)."""

    # ----- execução (só plano aprovado) -----

    def executar(self, plano: AIPlan, motor) -> dict:
        """AIPlan aprovado → BehaviorPlan.executar (reuso F17)."""
        if not isinstance(plano, AIPlan):
            return {"sucesso": False, "codigo": "plano_invalido",
                    "motivo": "Executar espera AIPlan.",
                    "iniciados": []}
        if not plano.viavel or plano.behavior_plan is None:
            plano.registrar("ai_execucao_falhou")
            return {"sucesso": False, "codigo": "plano_inviavel",
                    "motivo": plano.motivo or "Plano inviável.",
                    "iniciados": []}
        personagem = self.personagens[plano.intent.personagem]
        resultado = plano.behavior_plan.executar(motor, self.cena,
                                                 personagem)
        plano.registrar("ai_execucao_iniciada")
        return {"sucesso": True, "codigo": "ok",
                "motivo": resultado.get("motivo", ""),
                "iniciados": list(resultado.get("iniciados", [])),
                "plano": plano}

    def cancelar(self, motor, nomes: list[str]) -> dict:
        """Cancela motions (restauração via ganchos F17)."""
        cancelados: list[str] = []
        for nome in list(nomes or []):
            try:
                motor.cancelar(nome)
                cancelados.append(nome)
            except Exception:
                pass
        return {"sucesso": True, "codigo": "ok",
                "motivo": f"{len(cancelados)} motion(s) cancelada(s).",
                "cancelados": cancelados}

    # ----- contexto e debug (leitura) -----

    def contexto(self, personagem_nome: str, destino=None,
                 raio: float = 400.0) -> dict:
        """Snapshot estruturado para a IA (limitado; sem mundo inteiro)."""
        if personagem_nome not in self.personagens:
            raise ErroELiXX(
                f'Personagem "{personagem_nome}" não existe.')
        personagem = self.personagens[personagem_nome]
        mundo, _grafo = self._mundo_do_personagem(personagem_nome)
        no = getattr(personagem, "no_raiz", None)
        posicao = {"x": float(getattr(no, "x", 0.0)),
                   "y": float(getattr(no, "y", 0.0))} if no is not None \
            else {"x": 0.0, "y": 0.0}
        from .capacidades import capacidades_de, itens_de

        equipados = []
        inventario = getattr(personagem, "inventario", None)
        if inventario is not None:
            for slot in sorted(getattr(inventario, "equipados", {})):
                equipados.append({"slot": slot,
                                  "item": inventario.equipados[slot]})
        proximas: list[dict] = []
        destinos: list[dict] = []
        mundo_nome = mundo.nome if mundo is not None else None
        if mundo is not None:
            for entidade in mundo.proximos(personagem_nome, float(raio)):
                centro = entidade.centro()
                proximas.append({"nome": entidade.nome,
                                 "tipo": entidade.tipo,
                                 "x": centro.x, "y": centro.y,
                                 "dist": posicao and _dist(
                                     posicao, centro)})
            for nome in mundo._ordem:
                entidade = mundo._entidades[nome]
                if entidade.tipo == "ponto":
                    centro = entidade.centro()
                    destinos.append({"nome": nome, "x": centro.x,
                                     "y": centro.y})
        rotas_possiveis: list[dict] = []
        if destino is not None and mundo is not None:
            for rota in self._rotas_para(personagem, mundo, destino):
                rotas_possiveis.append(
                    {"nos": list(rota.get("nos", [])),
                     "modos": list(rota.get("modos", [])),
                     "custo_total": rota.get("custo_total", 0.0),
                     "requisitos": list(rota.get("requisitos", []))})
        estado = {}
        if hasattr(personagem, "estado_resumo"):
            try:
                estado = dict(personagem.estado_resumo())
            except Exception:
                estado = {}
        return {"personagem": personagem_nome, "posicao": posicao,
                "mundo": mundo_nome,
                "capacidades": sorted(capacidades_de(personagem).nomes()),
                "equipados": equipados,
                "entidades_proximas": proximas, "destinos": destinos,
                "rotas_possiveis": rotas_possiveis, "estado": estado}

    def debug_ai_plan(self, plano: AIPlan) -> str:
        """Texto puro: intenção→capacidades→rota→motion→behavior→exec."""
        intent = plano.intent
        linhas = [f"AIPlan ({getattr(intent, 'tipo', '?')}"
                   f"{(':' + intent.personagem) if getattr(intent, 'personagem', None) else ''}"
                   f"{(' → ' + str(intent.destino)) if getattr(intent, 'destino', None) else ''}: "
                   f"viavel={plano.viavel} suportado={plano.suportado} "
                   f"executavel={plano.executavel})"]
        linhas.append(f"INTENÇÃO: {intent.to_dict() if intent else None}")
        linhas.append(f"VALIDAÇÃO: {plano.validacao}")
        linhas.append(f"REQUISITOS: {', '.join(plano.requisitos) or '--'}")
        for rota in plano.resumo_rotas():
            linhas.append(
                f"ROTA nos={rota['nos']} modos={rota['modos']} "
                f"custo={rota['custo_total']:g} req={rota['requisitos']}")
        motion = plano.motion_plan
        linhas.append("MOVIMENTO: " + (
            f"{len(motion.steps)} etapa(s), "
            f"{motion.duracao_total_ms:.0f}ms" if motion is not None
            else "--"))
        behavior = plano.behavior_plan
        linhas.append("COMPORTAMENTO: " + (
            f"{len(behavior.steps)} passo(s)" if behavior is not None
            else "--"))
        linhas.append(f"EXECUTÁVEL: {'sim' if plano.executavel else 'não'}"
                       f" ({plano.motivo})")
        for aviso in plano.avisos:
            linhas.append(f"AVISO: {aviso}")
        return "\n".join(linhas)

    # ----- núcleo mover/ir -----

    def _planejar_mover(self, plano: AIPlan, intent: AIIntent) -> AIPlan:
        from .capacidades import tem_capacidade
        from .navegacao import (plano_travessia, rotas_alternativas)
        from .sintese_comportamento import BehaviorSynthesizer
        from .sintese_movimento import MotionSynthesizer

        personagem = self.personagens[intent.personagem]
        mundo, grafo = self._mundo_e_grafo(intent)
        if mundo is None or grafo is None:
            plano.motivo = (
                f'Personagem "{intent.personagem}" fora de mundo com '
                "navegação.")
            plano.registrar("ai_plano_rejeitado")
            return plano
        origem = intent.personagem
        if intent.modo is not None and not tem_capacidade(personagem,
                                                          intent.modo):
            plano.motivo = (
                f'Capacidade "{intent.modo}" ausente em '
                f'"{intent.personagem}".')
            plano.registrar("ai_plano_rejeitado")
            return plano
        rotas = rotas_alternativas(grafo, origem, intent.destino, k=3,
                                   holder=personagem, mundo=mundo)
        viaveis = [r for r in rotas if r.get("encontrado")]
        plano.rotas = viaveis
        if not viaveis:
            motivo = (rotas[0].get("motivo", "Destino inacessível.")
                      if rotas else "Destino inacessível (sem conexão).")
            plano.motivo = motivo
            if rotas and rotas[0].get("capacidades"):
                plano.requisitos = list(rotas[0]["capacidades"])
            plano.registrar("ai_plano_rejeitado")
            return plano
        if intent.modo is not None:
            viaveis = [r for r in viaveis if intent.modo in r.get("modos",
                                                                  [])]
            if not viaveis:
                plano.motivo = (
                    f'Sem rota no modo "{intent.modo}" até '
                    f'"{_destino_texto(intent.destino)}".')
                plano.registrar("ai_plano_rejeitado")
                return plano
            escolhida = viaveis[0]
            plano.avisos.append(
                f'Modo explícito "{intent.modo}": 1 rota.')
        elif len(viaveis) > 1:
            plano.requer_escolha = True
            plano.viavel = True
            plano.avisos.append(
                f"{len(viaveis)} rotas: escolha explícita "
                "(sem ranking subjetivo).")
            plano.motivo = ("Múltiplas rotas: escolha explícita "
                            "(ver rotas).")
            return plano
        else:
            escolhida = viaveis[0]
        tplan = self._traversal_de_rota(grafo, escolhida, intent,
                                        personagem, mundo)
        motion = MotionSynthesizer().sintetizar(
            tplan, grafo, personagem, personagem, mundo)
        if not motion.viavel:
            plano.motivo = motion.motivo
            plano.registrar("ai_plano_rejeitado")
            return plano
        behavior = BehaviorSynthesizer(
            pose_padrao=intent.pose,
            expressao_padrao=intent.expressao).sintetizar(
            motion, personagem, personagem)
        if not behavior.viavel:
            plano.motivo = behavior.motivo
            plano.requisitos = list(behavior.requisitos)
            plano.registrar("ai_plano_rejeitado")
            return plano
        plano.traversal_plan = tplan
        plano.motion_plan = motion
        plano.behavior_plan = behavior
        plano.requisitos = list(behavior.requisitos)
        plano.viavel = True
        plano.executavel = True
        plano.motivo = "Plano aprovado para execução."
        plano.registrar("ai_plano_validado")
        return plano

    # ----- resolução -----

    def _mundo_do_personagem(self, personagem_nome: str):
        """(mundo, grafo|None) do personagem (primeiro que o contém)."""
        for mundo in self.mundos.values():
            try:
                mundo.por_id(personagem_nome)
            except ErroELiXX:
                continue
            for grafo in self.grafos.values():
                if getattr(grafo, "mundo", None) is mundo:
                    return mundo, grafo
            return mundo, None
        return None, None

    def _mundo_e_grafo(self, intent: AIIntent):
        """Mundo+grafo do personagem da intenção."""
        return self._mundo_do_personagem(intent.personagem)

    def _rotas_para(self, personagem, mundo, destino) -> list[dict]:
        """Até 3 rotas viáveis (para contexto; sem holder filter aqui)."""
        from .navegacao import rotas_alternativas

        for grafo in self.grafos.values():
            if getattr(grafo, "mundo", None) is mundo:
                try:
                    return [r for r in rotas_alternativas(
                        grafo, personagem.nome, destino, k=3,
                        holder=personagem, mundo=mundo)
                        if r.get("encontrado")]
                except ErroELiXX:
                    return []
        return []

    @staticmethod
    def _traversal_de_rota(grafo, rota_dict: dict, intent: AIIntent,
                           personagem, mundo):
        """Rota escolhida → TraversalPlan (etapas do próprio Path)."""
        from .navegacao import Path, TraversalPlan

        nos = list(rota_dict.get("nos", []))
        edges = []
        for no_de, no_para in zip(nos, nos[1:]):
            achados = [e for e in grafo.saidas(no_de)
                       if e.destino == no_para]
            if not achados:
                raise ErroELiXX(
                    f'Sem edge "{no_de}" -> "{no_para}" no grafo.')
            modos = rota_dict.get("modos", [])
            preferidos = [e for e in achados if e.modo in modos]
            edges.append(preferidos[0] if preferidos else achados[0])
        caminho = Path(nos=nos, edges=edges,
                       distancia_total=float(
                           rota_dict.get("distancia_total", 0.0)),
                       custo_total=float(rota_dict.get("custo_total", 0.0)),
                       modos=list(rota_dict.get("modos", [])),
                       requisitos=list(rota_dict.get("requisitos", [])))
        return TraversalPlan(
            origem=str(intent.personagem),
            destino=_destino_texto(intent.destino), path=caminho,
            etapas=caminho.etapas(), modos=list(caminho.modos),
            capacidades_necessarias=list(caminho.requisitos))


def _destino_texto(destino) -> str:
    if isinstance(destino, dict):
        return f"({destino.get('x')},{destino.get('y')})"
    return str(destino)


def _dist(posicao: dict, centro) -> float:
    dx = float(posicao.get("x", 0.0)) - float(centro.x)
    dy = float(posicao.get("y", 0.0)) - float(centro.y)
    return math.hypot(dx, dy)
