"""Character / Puppet Core da ELiXX (Fase 12).

Um personagem é ESTRUTURA + METADADOS sobre Scene/Node/Transform/Motion
existentes — sem segundo runtime, sem segundo motor, sem matemática
duplicada:

    Pose ──→ Motion (F11) ──→ Transform (F10) ──→ Cena ──→ Renderer
      ↑            (transicionar_pose gera DefinicaoAnimacao)
    Character (partes, juntas, limites, direção, representações)

Nomes de partes são globais e únicos (identidade estável, validada na
semântica). Limites fazem clamp previsível na aplicação de pose
(motions escrevem direto, como no resto da linguagem).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..erros import ErroELiXX
from .transform import Transform, combinar, transform_de_no

__all__ = [
    "DIRECOES", "POSE_PROPS_INTERNAS",
    "Joint", "Pose", "Gesture", "CharacterPart", "Character",
    "AnaliseResultado", "CharacterAnalyzer", "ManualAnalyzer",
    "vincular_personagens",
]

DIRECOES = ("frente", "costas", "esquerda", "direita", "cima", "baixo")
"""Orientação visual 2D (estado; sem câmera 3D)."""

POSE_PROPS_INTERNAS = ("posicao", "rotacao", "escala", "opacidade", "pivo")
"""Propriedades que uma pose pode carregar (transform parcial)."""


# ----- Joint -----

@dataclass
class Joint:
    """Articulação: junta nomeada entre parte e subparte, com limites.

    Limites em graus (None = livre). Pivô vive no Transform da F10.
    """

    nome: str
    parte: str  # parte dona da junta
    minimo: float | None = None
    maximo: float | None = None
    linha: int = 0

    def dentro_limites(self, rotacao_graus: float) -> bool:
        """True se a rotação respeita os limites (ou se não há limites)."""
        valor = float(rotacao_graus)
        if self.minimo is not None and valor < self.minimo:
            return False
        if self.maximo is not None and valor > self.maximo:
            return False
        return True

    def aplicar_limite(self, rotacao_graus: float) -> float:
        """Clamp previsível da rotação aos limites."""
        valor = float(rotacao_graus)
        if self.minimo is not None:
            valor = max(self.minimo, valor)
        if self.maximo is not None:
            valor = min(self.maximo, valor)
        return valor


# ----- Pose -----

@dataclass
class Pose:
    """Pose = {parte → transform parcial} (dado, sem motor próprio)."""

    nome: str
    entradas: dict = field(default_factory=dict)  # parte -> {prop: valor}
    expressao: bool = False
    linha: int = 0

    def partes(self) -> list[str]:
        return sorted(self.entradas)

    def combinar(self, outra: Pose, nome: str = "") -> Pose:
        """Compõe poses: última vence por (parte, prop) — sem conflito
        silencioso dentro de uma pose (já validado), prioridade por
        ordem entre poses (documentado)."""
        fundida: dict = {}
        for parte, props in self.entradas.items():
            fundida[parte] = dict(props)
        for parte, props in outra.entradas.items():
            fundida.setdefault(parte, {}).update(props)
        return Pose(nome=nome or f"{self.nome}+{outra.nome}",
                    entradas=fundida,
                    expressao=self.expressao and outra.expressao)


# ----- Gesture -----

@dataclass
class Gesture:
    """Gesto = composição Pose/Motion sobre MotionGroup (sem motor novo)."""

    nome: str
    passos: list = field(default_factory=list)  # Pose | dict(motion) | str
    modo: str = "sequencia"  # sequencia | paralelo
    repetir: object = None
    linha: int = 0


# ----- CharacterPart -----

@dataclass
class CharacterPart:
    """Parte articulável: envolve um Node visual (sem duplicar Transform)."""

    nome: str
    no: object  # NoVisual da parte
    junta: Joint | None = None
    variantes: dict = field(default_factory=dict)  # estado -> asset
    vistas: dict = field(default_factory=dict)  # vista -> asset
    filhos: list[CharacterPart] = field(default_factory=list)
    pai: CharacterPart | None = None
    raiz: object = None  # NoVisual do root (composto por último)

    def transform_local(self) -> Transform:
        return transform_de_no(self.no)

    def transform_global(self) -> Transform:
        """Global: root + cadeia de pais (reusa combinar da F10).

        Dobra de dentro para fora: antebraço∘mão, depois braço∘...,
        depois root∘... (ordem importa por causa dos pivôs).
        """
        atual = self.transform_local()
        ancestral = self.pai
        cadeia = []
        while ancestral is not None:
            cadeia.append(transform_de_no(ancestral.no))
            ancestral = ancestral.pai
        for transform_pai in cadeia:  # pai direto primeiro
            atual = combinar(transform_pai, atual)
        if self.raiz is not None:
            atual = combinar(transform_de_no(self.raiz), atual)
        return atual

    def variante_atual(self) -> str | None:
        return getattr(self.no, "_variante", None)


# ----- Character -----

class Character:
    """Personagem como entidade coerente (root + partes + poses)."""

    def __init__(self, nome: str, no_raiz, partes: dict[str, CharacterPart],
                 poses: dict[str, Pose], direcao: str = "frente",
                 representacoes: dict | None = None) -> None:
        from .capacidades import CapabilitySet, Inventario

        self.nome = nome
        self.no_raiz = no_raiz
        self.partes = dict(partes)
        self.poses = dict(poses)
        self.direcao = direcao
        self.representacoes = dict(representacoes or {})
        self.pose_atual: str | None = None
        self.gesto_atual: str | None = None
        self.motions_ativos: list[str] = []
        # Fase 14: capacidades próprias + inventário (posse/equip/anexo).
        self.capacidades = CapabilitySet()
        self.inventario = Inventario(dono=nome)

    # ----- Fase 14: atalhos delegados (sem duplicar lógica) -----

    def capacidades_compostas(self):
        """Próprias + itens equipados (ordem determinística)."""
        from .capacidades import capacidades_de

        return capacidades_de(self)

    def tem_capacidade(self, capacidade: str) -> bool:
        from .capacidades import tem_capacidade

        return tem_capacidade(self, capacidade)

    def pode(self, capacidade: str, mundo=None,
             alvo: str | None = None) -> dict:
        """Consulta determinística (nunca executa)."""
        from .capacidades import pode

        return pode(self, capacidade, mundo, alvo)

    def possui(self, nome: str) -> bool:
        from .capacidades import possui

        return possui(self, nome)

    def equipado(self, nome: str) -> bool:
        from .capacidades import equipado

        return equipado(self, nome)

    def transform_anexo(self, item_nome: str):
        """Transform global do ponto de encaixe (segue a parte)."""
        parte_nome = self.inventario.anexado(item_nome)
        if parte_nome is None:
            raise ErroELiXX(
                f'Item "{item_nome}" sem anexo em "{self.nome}". '
                "Equipe com anexo a uma parte.")
        return self.obter_transform_global(parte_nome)

    # ----- identidade -----

    def obter_parte(self, nome: str) -> CharacterPart:
        """Parte exata ou erro claro (sem fallback silencioso)."""
        try:
            return self.partes[nome]
        except KeyError:
            from ..erros import sugerir

            parecidas = sugerir(nome, sorted(self.partes))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroELiXX(
                f"Parte '{nome}' não encontrada no personagem "
                f"'{self.nome}'.{dica}",
                sugestao="Confira as partes declaradas no personagem.")

    def obter_transform_global(self, nome: str) -> Transform:
        """Transform global de uma parte (local + cadeia de pais)."""
        return self.obter_parte(nome).transform_global()

    # ----- poses -----

    def obter_pose(self, nome: str) -> Pose:
        """Pose exata ou erro claro (poses e expressões no mesmo índice)."""
        try:
            return self.poses[nome]
        except KeyError:
            from ..erros import sugerir

            parecidas = sugerir(nome, sorted(self.poses))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroELiXX(
                f'Pose "{nome}" não encontrada no personagem '
                f"'{self.nome}'.{dica}")

    def aplicar_pose(self, nome_ou_pose, poses_extras=()) -> list[str]:
        """Aplica pose ( + overlays ): localiza, valida, clampa, escreve.

        Retorna as partes tocadas. Parcial por construção (o resto fica).
        Composição: última pose vence por (parte, prop).
        """
        base = (self.obter_pose(nome_ou_pose) if isinstance(nome_ou_pose, str)
                else nome_ou_pose)
        fundida = base
        for extra in poses_extras:
            outra = (self.obter_pose(extra) if isinstance(extra, str)
                     else extra)
            fundida = fundida.combinar(outra)
        tocadas: list[str] = []
        for parte_nome, props in fundida.entradas.items():
            parte = self.obter_parte(parte_nome)
            self._aplicar_props(parte, props)
            tocadas.append(parte_nome)
        self.pose_atual = fundida.nome
        return sorted(tocadas)

    def _aplicar_props(self, parte: CharacterPart, props: dict) -> None:
        no = parte.no
        for prop, valor in props.items():
            if prop == "posicao":
                no.x, no.y = float(valor[0]), float(valor[1])
            elif prop == "rotacao":
                rot = float(valor)
                if parte.junta is not None:
                    rot = parte.junta.aplicar_limite(rot)
                from .transform import normalizar_graus

                no.rotacao = normalizar_graus(rot)
            elif prop == "escala":
                if isinstance(valor, (tuple, list)):
                    no.escala_x, no.escala_y = (float(valor[0]),
                                                float(valor[1]))
                else:
                    no.escala = no.escala_x = no.escala_y = float(valor)
            elif prop == "opacidade":
                no.opacidade = max(0.0, min(1.0, float(valor)))
            elif prop == "pivo":
                (px, ux), (py, uy) = valor
                no.pivo_x, no.pivo_unidade_x = float(px), ux
                no.pivo_y, no.pivo_unidade_y = float(py), uy
            else:
                raise ErroELiXX(
                    f'Propriedade de pose desconhecida: "{prop}". '
                    f"Válidas: {', '.join(POSE_PROPS_INTERNAS)}.")

    # ----- transição via Motion Core (obrigatório: sem interpolação própria)
    # -----

    def transicionar_pose(self, destino, origem=None, duracao_ms: float = 500.0,
                          movimento: str = "suave") -> list:
        """Pose A → B como Motions (um por parte+prop diferente).

        Gera DefinicaoAnimacao prontas para MotorAnimacoes.carregar
        (alvo = nome do nó = nome da parte, identidade global única).
        """
        from ..animacao.motor import ChaveAnimacao, DefinicaoAnimacao

        pose_fim = (self.obter_pose(destino) if isinstance(destino, str)
                    else destino)
        inicio = self._estado_atual(pose_fim)
        if origem is not None:
            pose_ini = (self.obter_pose(origem) if isinstance(origem, str)
                        else origem)
            inicio = {p: dict(v) for p, v in pose_ini.entradas.items()}
        definicoes = []
        for parte_nome in sorted(pose_fim.entradas):
            parte = self.obter_parte(parte_nome)
            for prop in sorted(pose_fim.entradas[parte_nome]):
                valor_fim = self._normalizar_prop(
                    parte, prop, pose_fim.entradas[parte_nome][prop])
                atual = inicio.get(parte_nome, {}).get(prop)
                if atual is None:
                    atual = self._ler_no(parte.no, prop)
                if atual == valor_fim:
                    continue
                definicoes.append(DefinicaoAnimacao(
                    nome=f"{self.nome}_{pose_fim.nome}_{parte_nome}_{prop}",
                    alvo=parte.no.nome or parte_nome,
                    chaves=[ChaveAnimacao(prop, atual, valor_fim)],
                    duracao_ms=float(duracao_ms), movimento=movimento))
        return definicoes

    def _estado_atual(self, pose: Pose) -> dict:
        """Valores atuais das props que a pose destino toca."""
        saida = {}
        for parte_nome, props in pose.entradas.items():
            parte = self.obter_parte(parte_nome)
            saida[parte_nome] = {p: self._ler_no(parte.no, p) for p in props}
        return saida

    @staticmethod
    def _ler_no(no, prop: str) -> object:
        if prop == "posicao":
            return (float(no.x), float(no.y))
        if prop == "rotacao":
            return float(no.rotacao)
        if prop == "escala":
            return (float(getattr(no, "escala_x", 1.0)),
                    float(getattr(no, "escala_y", 1.0)))
        if prop == "opacidade":
            return float(no.opacidade)
        if prop == "pivo":
            return ((float(no.pivo_x), no.pivo_unidade_x),
                    (float(no.pivo_y), no.pivo_unidade_y))
        raise ErroELiXX(f'Propriedade de pose desconhecida: "{prop}".')

    def _normalizar_prop(self, parte: CharacterPart, prop: str,
                         valor: object) -> object:
        """Valor da pose com limites da junta (clamp previsível)."""
        if prop == "rotacao" and parte.junta is not None:
            return parte.junta.aplicar_limite(float(valor))
        if prop == "escala" and not isinstance(valor, (tuple, list)):
            return (float(valor), float(valor))
        return valor

    # ----- gestos (composição sobre MotionGroup) -----

    def executar_gesto(self, gesto: Gesture, motor) -> object:
        """Monta e dispara o gesto (sequencial/paralelo/repetido).

        Passos: str (pose do personagem), Pose, Gesture (aninhado) ou
        dict de motion pronto. Retorna o MotionGroup.
        """
        from ..animacao.motion import MotionGroup

        nomes_defs: list[str] = []
        anterior = None  # última pose (origem encadeada do próximo passo)
        ultima_pose = None
        for idx, passo in enumerate(gesto.passos):
            if isinstance(passo, Gesture):
                sub = self.executar_gesto(passo, motor)
                nomes_defs.extend(sub.membros)
                continue
            if isinstance(passo, str):
                defs = self.transicionar_pose(passo, origem=anterior)
                anterior = self.obter_pose(passo)
                ultima_pose = passo
            elif isinstance(passo, Pose):
                defs = self.transicionar_pose(passo, origem=anterior)
                anterior = passo
                ultima_pose = passo.nome
            elif isinstance(passo, dict):
                from ..animacao.motor import DefinicaoAnimacao as _D

                defs = [_D(**passo)]
            else:
                raise ErroELiXX(
                    f'Passo de gesto inválido no gesto "{gesto.nome}". '
                    "Use nome de pose, Pose ou motion.")
            for definicao in defs:
                definicao.nome = f"{gesto.nome}_{idx}_{definicao.nome}"
                if gesto.repetir is not None:
                    definicao.repetir = gesto.repetir
            cena = getattr(motor, "_cena", None)
            if cena is None:
                raise ErroELiXX(
                    f'Gesto "{gesto.nome}": motor sem cena carregada. '
                    "Carregue ao menos um motion antes.")
            motor.carregar(defs, cena)
            nomes_defs.extend(d.nome for d in defs)
        grupo = MotionGroup(gesto.nome, motor, nomes_defs,
                            modo=("sequencia" if gesto.modo == "sequencia"
                                  else "paralelo"))
        grupo.preparar()
        grupo.iniciar()
        self.gesto_atual = gesto.nome
        self.motions_ativos = list(nomes_defs)
        if ultima_pose is not None:
            # Intenção declarada (os motions animam até ela no tempo).
            self.pose_atual = ultima_pose
        return grupo

    # ----- direção / representação / variantes -----

    def definir_direcao(self, direcao: str) -> str:
        """Troca a orientação (frente/costas/lados); devolve o asset."""
        vista = str(direcao).strip().lower()
        if vista not in DIRECOES:
            raise ErroELiXX(
                f'Direção inválida: "{direcao}". '
                f'Válidas: {", ".join(DIRECOES)}.')
        self.direcao = vista
        return self.representacoes.get(vista)

    def definir_variante(self, parte_nome: str, variante: str) -> str:
        """Troca estado visual da parte (ex. olho → fechado): semântico."""
        parte = self.obter_parte(parte_nome)
        try:
            asset = parte.variantes[variante]
        except KeyError:
            raise ErroELiXX(
                f'Variante "{variante}" inexistente na parte '
                f"'{parte_nome}'. Válidas: "
                f"{', '.join(sorted(parte.variantes)) or 'nenhuma'}.")
        parte.no._variante = variante
        return asset

    def estado_resumo(self) -> dict:
        """Estado mínimo: pose, direção, gesto, motions (sem IA/comport.)."""
        return {"personagem": self.nome, "pose_atual": self.pose_atual,
                "direcao": self.direcao, "gesto_atual": self.gesto_atual,
                "motions_ativos": list(self.motions_ativos)}


# ----- análise (fundações assistida/automática; mock honesto) -----

@dataclass
class AnaliseResultado:
    """Resultado estruturado: partes detectadas/declaradas."""

    partes: list = field(default_factory=list)  # [{nome, pai, pivo}]
    fonte: str = "manual"


class CharacterAnalyzer:
    """Interface do futuro analisador (imagem → partes)."""

    def analisar(self, imagem: str) -> AnaliseResultado:
        raise NotImplementedError


class ManualAnalyzer(CharacterAnalyzer):
    """Implementação manual/mock: declara partes (sem IA externa)."""

    def __init__(self, partes: list | None = None) -> None:
        self._partes = list(partes or [])

    def analisar(self, imagem: str) -> AnaliseResultado:
        return AnaliseResultado(partes=[dict(p) for p in self._partes],
                                fonte="manual")


# ----- vínculo cena → personagens -----

def _converter_pose(pose_ast) -> Pose:
    """PoseDef AST → Pose (valores convertidos p/ o motor)."""
    from ..animacao.motor import converter_valor_anim

    entradas = {}
    for entrada in pose_ast.entradas:
        props = {}
        for prop in entrada.propriedades:
            nome = _normalizar_prop_pose(prop.nome)
            if nome == "posicao":
                valor = tuple(converter_valor_anim(_tupla(v), "posicao")
                              for v in prop.valores)
            elif nome == "escala":
                if len(prop.valores) == 2:
                    valor = tuple(converter_valor_anim(_tupla(v), "escala")
                                  for v in prop.valores)
                else:
                    valor = converter_valor_anim(
                        _tupla(prop.valores[0]), "escala")
            elif nome == "pivo":
                valor = _converter_pivo(prop.valores)
            else:
                valor = converter_valor_anim(_tupla(prop.valores[0]), nome)
            props[nome] = valor
        entradas[entrada.parte] = props
    return Pose(nome=pose_ast.nome, entradas=entradas,
                expressao=bool(pose_ast.expressao), linha=pose_ast.linha)


def _tupla(valor: object) -> tuple:
    """Nó AST (Medida/NumeroLit) → tupla (unidade, número) do motor."""
    from ..compilador import ast as _A

    if isinstance(valor, _A.Medida):
        return (valor.unidade, float(valor.valor))
    if isinstance(valor, _A.NumeroLit):
        return ("px", float(valor.valor))
    return ("px", 0.0)


def _normalizar_prop_pose(nome: str) -> str:
    base = {"posição": "posicao", "rotação": "rotacao",
            "pivô": "pivo"}.get(nome, nome)
    try:
        return {"posicao": "posicao", "rotacao": "rotacao",
                "escala": "escala", "opacidade": "opacidade",
                "pivo": "pivo"}[base]
    except KeyError:
        raise ErroELiXX(
            f'Propriedade de pose desconhecida: "{nome}". '
            f"Válidas: {', '.join(POSE_PROPS_INTERNAS)}.")


def _converter_pivo(valores: list) -> tuple:
    """[x, y] AST (Medida/Numero) → ((x, unid), (y, unid))."""
    from ..compilador import ast as _A

    def um(valor):
        if isinstance(valor, _A.Medida) and valor.unidade in ("%", "px"):
            return (float(valor.valor), valor.unidade)
        if isinstance(valor, _A.NumeroLit):
            return (float(valor.valor), "px")
        return (0.0, "px")

    primeiro = um(valores[0])
    segundo = um(valores[1]) if len(valores) == 2 else primeiro
    return (primeiro, segundo)


def vincular_personagens(cena, itens: dict | None = None
                         ) -> dict[str, Character]:
    """Percorre a cena e monta Characters (root + partes + poses).

    Parte = nó `parte` descendente do root; subparte = `parte` filha.
    Erro claro se a meta AST sumiu (uso interno fora do pipeline).
    Com `itens` (vincular_itens), liga capacidades próprias, posse e
    equipamento declarativos.
    """
    personagens: dict[str, Character] = {}
    for janela in getattr(cena, "janelas", []):
        for no in janela.todos():
            if getattr(no, "tipo", "") != "personagem":
                continue
            personagens[no.nome] = _vincular_um(no, itens)
    return personagens


def _vincular_um(no_raiz, itens: dict | None = None) -> Character:
    meta = getattr(no_raiz, "personagem_meta", None) or {}
    if meta.get("kind") != "personagem":
        raise ErroELiXX(
            f'Personagem "{no_raiz.nome}" sem metadados (fora do pipeline '
            "ELiXX?).")
    partes: dict[str, CharacterPart] = {}

    def visitar(no_parte, pai: CharacterPart | None) -> CharacterPart:
        meta_parte = getattr(no_parte, "personagem_meta", None) or {}
        junta = None
        if meta_parte.get("junta") or meta_parte.get("limite_min") is not None \
                or meta_parte.get("limite_max") is not None:
            junta = Joint(nome=meta_parte.get("junta") or no_parte.nome,
                          parte=no_parte.nome,
                          minimo=meta_parte.get("limite_min"),
                          maximo=meta_parte.get("limite_max"),
                          linha=getattr(no_parte, "linha", 0))
        parte = CharacterPart(nome=no_parte.nome, no=no_parte, junta=junta,
                              variantes=dict(meta_parte.get("variantes",
                                                            {})),
                              vistas=dict(meta_parte.get("vistas", {})),
                              pai=pai, raiz=no_raiz)
        partes[parte.nome] = parte
        for filho in getattr(no_parte, "filhos", []):
            if getattr(filho, "tipo", "") == "parte":
                parte.filhos.append(visitar(filho, parte))
        return parte

    for filho in getattr(no_raiz, "filhos", []):
        if getattr(filho, "tipo", "") == "parte":
            visitar(filho, None)
    poses = {}
    for pose_ast in meta.get("poses", []):
        poses[pose_ast.nome] = _converter_pose(pose_ast)
    boneco = Character(nome=no_raiz.nome, no_raiz=no_raiz, partes=partes,
                       poses=poses,
                       direcao=meta.get("direcao", "frente"),
                       representacoes=dict(meta.get("vistas", {})))
    if itens is not None:
        _vincular_inventario(boneco, meta, partes, itens)
    return boneco


def _vincular_inventario(boneco: Character, meta: dict,
                         partes: dict, itens: dict) -> None:
    """Fase 14: capacidades próprias + possui/equipa declarativos."""
    from .capacidades import (CapabilitySet, _cap_de_ast, obter_instancia)

    conjunto = CapabilitySet()
    for cap_ast in meta.get("capacidades", []):
        conjunto.adicionar(_cap_de_ast(
            cap_ast, f"personagem:{boneco.nome}"))
    for no_parte_nome, parte in partes.items():
        meta_parte = getattr(parte.no, "personagem_meta", None) or {}
        for cap_ast in meta_parte.get("capacidades", []):
            conjunto.adicionar(_cap_de_ast(
                cap_ast, f"personagem:{boneco.nome}"))
    boneco.capacidades = conjunto
    boneco.inventario._defs_ref = itens.get("defs", {})
    for nome in meta.get("possui", []):
        boneco.inventario.possuir(obter_instancia(itens, nome))
    for nome in meta.get("equipa", []):
        instancia = obter_instancia(itens, nome)
        boneco.inventario.possuir(instancia)
        parte_nome = (instancia.anexo_padrao
                      or _defs_anexo(itens, instancia.definicao))
        if parte_nome is not None and parte_nome not in partes:
            raise ErroELiXX(
                f'Parte "{parte_nome}" não existe no personagem '
                f'"{boneco.nome}" (anexo do item "{nome}").')
        boneco.inventario.equipar(instancia.nome,
                                  anexo=parte_nome)


def _defs_anexo(itens: dict, definicao_nome: str) -> str | None:
    definicao = itens.get("defs", {}).get(definicao_nome)
    return getattr(definicao, "anexo", None)
