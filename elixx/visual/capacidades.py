"""Items + Capability System da ELiXX (Fase 14).

Camada semântica: SABE o que pode ser feito, NÃO decide o que fazer.
Sem execução, sem IA, sem comportamento, sem física.

    ItemDefinition (o que é) ──→ ItemInstance (qual, com estado)
    Capability (o que pode) ──→ provider (personagem ou item)
    Inventario (possui/equipa/anexa) ──→ composição
    pode() (consulta determinística com requisitos)

Reutiliza: Vector2/Transform (posições), World (espacial), Character
(partes/anexos), Cena/Node (visuais por referência). Nenhum eval/exec:
nomes e tags são dados inertes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..erros import ErroELiXX

__all__ = [
    "TIPOS_REQUISITO", "SLOTS_PADRAO",
    "Requisito", "Capability", "CapabilitySet", "CapabilityRegistry",
    "ItemDefinition", "ItemInstance", "Inventario",
    "coletar_definicoes", "vincular_itens",
    "capacidades_de", "tem_capacidade", "pode",
    "item_por_nome", "itens_de", "possui", "equipado", "slot_de",
    "anexado", "ponto_anexo", "debug_capacidades",
]

TIPOS_REQUISITO = ("equipado", "possuido", "presente", "proximo", "tag",
                   "categoria", "tipo", "estado", "capacidade")
"""Kinds de `requer_*` (texto após o prefixo)."""

SLOTS_PADRAO = ("geral",)
"""Slot fallback quando o item não declara `slot:`."""


# ----- Requisito / Capability -----

@dataclass(frozen=True)
class Requisito:
    """Pré-condição declarativa: kind + alvo (+ raio para próximo)."""

    kind: str  # sem prefixo: "equipado", "proximo", ...
    alvo: str = ""  # nome de item/entidade/tag/... ou "alvo"
    raio: float = 100.0
    linha: int = 0


@dataclass
class Capability:
    """Descritor semântico: nome, provider, params, requisitos."""

    nome: str
    provider: str = ""  # "personagem:Heroi" | "item:BotaFoguete"
    descricao: str = ""
    parametros: tuple = ()
    requisitos: tuple = ()  # Requisito
    tags: tuple = ()
    linha: int = 0

    def exige_alvo(self) -> bool:
        """True se declara parâmetros (alvo necessário em pode())."""
        return len(self.parametros) > 0


class CapabilitySet:
    """Conjunto ordenado sem duplicação (primeiro vence valores)."""

    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}
        self._provedores: dict[str, list[str]] = {}

    def adicionar(self, cap: Capability) -> None:
        """Soma sem duplicar: provedores unem em ordem determinística."""
        if cap.nome in self._caps:
            if cap.provider not in self._provedores[cap.nome]:
                self._provedores[cap.nome].append(cap.provider)
            return
        self._caps[cap.nome] = cap
        self._provedores[cap.nome] = [cap.provider] if cap.provider else []

    def unir(self, outro: CapabilitySet) -> None:
        for nome in outro.nomes():
            self.adicionar(outro._caps[nome])

    def nomes(self) -> list[str]:
        return list(self._caps)

    def obter(self, nome: str) -> Capability:
        try:
            return self._caps[nome]
        except KeyError:
            from ..erros import sugerir

            parecidas = sugerir(nome, self.nomes())
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroELiXX(
                f'Capacidade "{nome}" desconhecida neste conjunto.{dica}')

    def provedores(self, nome: str) -> list[str]:
        return list(self._provedores.get(nome, []))

    def __len__(self) -> int:
        return len(self._caps)

    def __contains__(self, nome: str) -> bool:
        return nome in self._caps


class CapabilityRegistry:
    """Índice programa: definições de item + capacidades por nome."""

    def __init__(self) -> None:
        self.itens: dict[str, ItemDefinition] = {}
        self.por_capacidade: dict[str, list[str]] = {}
        # capacidade -> ["item:X", "personagem:Y", ...] (ordem de registro)

    def registrar_item(self, definicao: ItemDefinition) -> None:
        if definicao.nome in self.itens:
            raise ErroELiXX(
                f'Item "{definicao.nome}" definido duas vezes.',
                linha=definicao.linha)
        self.itens[definicao.nome] = definicao
        for cap in definicao.capacidades.nomes():
            self.por_capacidade.setdefault(cap, []).append(
                f"item:{definicao.nome}")

    def provedores_de(self, capacidade: str) -> list[str]:
        return list(self.por_capacidade.get(capacidade, []))


# ----- Item -----

@dataclass
class ItemDefinition:
    """Definição semântica (categoria/tags/estado/views/capacidades)."""

    nome: str
    categoria: str = ""
    tags: tuple = ()
    estado: str = "disponivel"
    imagem: str | None = None
    visual: str | None = None  # nó da cena (referência, sem cópia)
    slot: str = "geral"
    anexo: str | None = None  # parte padrão de encaixe
    vistas: dict = field(default_factory=dict)
    variantes: dict = field(default_factory=dict)
    capacidades: CapabilitySet = field(default_factory=CapabilitySet)
    linha: int = 0


@dataclass
class ItemInstance:
    """Instância com identidade estável e estado próprio."""

    nome: str
    definicao: str  # nome da definição
    categoria: str = ""
    tags: tuple = ()
    estado: str = "disponivel"
    slot: str = "geral"
    linha: int = 0

    def definir_estado(self, estado: str) -> None:
        """Troca semântica (texto livre; vazio é erro claro)."""
        texto = str(estado).strip()
        if not texto:
            raise ErroELiXX(
                f'Estado vazio no item "{self.nome}". Use um nome como '
                '"ligado" ou "disponivel".')
        self.estado = texto


# ----- Inventario (posse + equipamento + anexo) -----

class Inventario:
    """Relações possui/equipa/anexa de UM dono (sem UI, sem valores)."""

    def __init__(self, dono: str = "", defs: dict | None = None) -> None:
        self.dono = dono
        self.instancias: dict[str, ItemInstance] = {}
        self.equipados: dict[str, str] = {}  # slot -> nome da instância
        self.anexos: dict[str, str] = {}  # instância -> parte
        self._defs_ref: dict = defs or {}

    def listar(self) -> list[str]:
        """Instâncias possuídas (ordem de posse; determinístico)."""
        return list(self.instancias)

    def possui(self, nome: str) -> bool:
        return nome in self.instancias

    def possuir(self, instancia: ItemInstance) -> ItemInstance:
        """Registra posse (idempotente por nome)."""
        self.instancias.setdefault(instancia.nome, instancia)
        return self.instancias[instancia.nome]

    def equipar(self, nome: str, slot: str | None = None,
                anexo: str | None = None) -> str:
        """Equipa possuído (slot do item ou informado; sem auto-posse)."""
        if nome not in self.instancias:
            raise ErroELiXX(
                f'Item "{nome}" não possuído por "{self.dono or "?"}". '
                "Possua antes de equipar.")
        instancia = self.instancias[nome]
        destino = slot or instancia.slot or "geral"
        self.equipados[destino] = nome
        if anexo is not None:
            self.anexos[nome] = anexo
        elif instancia.nome not in self.anexos and _anexo_def(instancia):
            self.anexos[nome] = _anexo_def(instancia)
        return destino

    def desequipar(self, nome: str) -> None:
        """Remove dos slots/anexos (mantém a posse)."""
        for slot, equipado in list(self.equipados.items()):
            if equipado == nome:
                del self.equipados[slot]
        self.anexos.pop(nome, None)

    def equipado(self, nome: str) -> bool:
        return nome in self.equipados.values()

    def slot_de(self, nome: str) -> str | None:
        for slot, equipado in self.equipados.items():
            if equipado == nome:
                return slot
        return None

    def anexado(self, nome: str) -> str | None:
        return self.anexos.get(nome)

    def equipados_lista(self) -> list[str]:
        """Instâncias equipadas (ordem de slot; determinístico)."""
        return [self.equipados[slot] for slot in sorted(self.equipados)]

    def de_definicao(self, definicao: str) -> list[str]:
        """Instâncias desta definição (possuídas)."""
        return [nome for nome, inst in self.instancias.items()
                if inst.definicao == definicao]


def _anexo_def(instancia: ItemInstance) -> str | None:
    return getattr(instancia, "anexo_padrao", None)


# ----- vínculo AST → definições/instâncias -----

def _texto(prop) -> str | None:
    from ..compilador import ast as _A

    if prop.valores and isinstance(prop.valores[0], _A.TextoLit):
        return prop.valores[0].valor
    return None


def _cap_de_ast(cap_ast, provider: str) -> Capability:
    requisitos = []
    descricao = ""
    for prop in cap_ast.propriedades:
        if prop.nome in ("descricao", "descrição"):
            descricao = _texto(prop) or ""
            continue
        if prop.nome == "raio":
            continue  # acoplado ao requer_proximo abaixo
        if prop.nome.startswith("requer_"):
            kind = prop.nome[len("requer_"):]
            if kind not in TIPOS_REQUISITO:
                continue  # semântica já barrou; defesa em profundidade
            alvo = _texto(prop) or ""
            raio = 100.0
            for prop2 in cap_ast.propriedades:
                if prop2.nome == "raio":
                    raio = _raio_num(prop2)
            requisitos.append(Requisito(kind=kind, alvo=alvo, raio=raio,
                                        linha=prop.linha))
    return Capability(nome=cap_ast.nome, provider=provider,
                      descricao=descricao,
                      parametros=tuple(p.nome for p in cap_ast.parametros),
                      requisitos=tuple(requisitos),
                      linha=cap_ast.linha)


def _raio_num(prop) -> float:
    from ..compilador import ast as _A

    if not prop.valores:
        return 100.0
    valor = prop.valores[0]
    if isinstance(valor, _A.NumeroLit):
        return float(valor.valor)
    if isinstance(valor, _A.Medida):
        return float(valor.valor)
    return 100.0


def _itemdef_de_ast(item_ast) -> ItemDefinition:
    categoria = ""
    tags: list[str] = []
    estado = "disponivel"
    imagem = visual = slot = anexo = None
    vistas: dict = {}
    variantes: dict = {}
    for prop in item_ast.propriedades:
        if prop.nome == "categoria":
            categoria = _texto(prop) or ""
        elif prop.nome == "tags":
            from ..compilador import ast as _A

            tags.extend(v.valor for v in prop.valores
                        if isinstance(v, _A.TextoLit))
        elif prop.nome == "estado":
            estado = _texto(prop) or "disponivel"
        elif prop.nome == "imagem":
            imagem = _texto(prop)
        elif prop.nome == "visual":
            visual = _texto(prop) or _ident(prop)
        elif prop.nome == "slot":
            slot = _texto(prop) or "geral"
        elif prop.nome == "anexo":
            anexo = _texto(prop)
        elif prop.nome in ("frente", "costas", "esquerda", "direita",
                           "cima", "baixo"):
            valor = _texto(prop)
            if valor is not None:
                vistas[prop.nome] = valor
        elif prop.nome.startswith("asset_"):
            valor = _texto(prop)
            if valor is not None:
                variantes[prop.nome[len("asset_"):]] = valor
    conjunto = CapabilitySet()
    for cap_ast in item_ast.capacidades:
        conjunto.adicionar(_cap_de_ast(cap_ast, f"item:{item_ast.nome}"))
    definicao = ItemDefinition(
        nome=item_ast.nome, categoria=categoria, tags=tuple(tags),
        estado=estado, imagem=imagem, visual=visual, slot=slot or "geral",
        anexo=anexo, vistas=vistas, variantes=variantes,
        capacidades=conjunto, linha=item_ast.linha)
    return definicao


def _ident(prop) -> str | None:
    from ..compilador import ast as _A

    if prop.valores and isinstance(prop.valores[0], _A.Ident):
        return prop.valores[0].nome
    return None


def coletar_definicoes(programa) -> dict[str, ItemDefinition]:
    """Todas as definições de item do programa (nomes únicos)."""
    definicoes: dict[str, ItemDefinition] = {}
    for janela in list(programa.janelas) + list(programa.telas):
        for item_ast in janela.itens:
            if item_ast.nome in definicoes:
                raise ErroELiXX(
                    f'Item "{item_ast.nome}" definido duas vezes.',
                    linha=item_ast.linha)
            definicoes[item_ast.nome] = _itemdef_de_ast(item_ast)
    return definicoes


def nova_instancia(definicao: ItemDefinition, nome: str) -> ItemInstance:
    """Instância com identidade própria a partir da definição."""
    instancia = ItemInstance(
        nome=nome, definicao=definicao.nome, categoria=definicao.categoria,
        tags=tuple(definicao.tags), estado=definicao.estado,
        slot=definicao.slot or "geral", linha=definicao.linha)
    instancia.anexo_padrao = definicao.anexo
    return instancia


def vincular_itens(programa) -> dict:
    """Defs + registry + instâncias (compartilhado; sem visuals)."""
    definicoes = coletar_definicoes(programa)
    registro = CapabilityRegistry()
    for definicao in definicoes.values():
        registro.registrar_item(definicao)
    return {"defs": definicoes, "registro": registro, "instances": {}}


def obter_instancia(itens: dict, definicao_nome: str,
                    nome: str | None = None) -> ItemInstance:
    """Instância existente ou nova (identidade estável por nome)."""
    definicao = itens["defs"].get(definicao_nome)
    if definicao is None:
        from ..erros import sugerir

        parecidas = sugerir(definicao_nome, sorted(itens["defs"]))
        dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                if parecidas else "")
        raise ErroELiXX(
            f'Item "{definicao_nome}" não definido.{dica} '
            "Declare com item Nome { ... }.")
    chave = nome or definicao_nome
    instancias = itens["instances"]
    if chave in instancias:
        existente = instancias[chave]
        if existente.definicao != definicao_nome:
            raise ErroELiXX(
                f'Instância "{chave}" já existe de '
                f'"{existente.definicao}" (não de "{definicao_nome}"). '
                "Use outro apelido (como).")
        return existente
    instancias[chave] = nova_instancia(definicao, chave)
    return instancias[chave]


# ----- consultas (§22; determinísticas, sem efeitos) -----

def item_por_nome(itens: dict, nome: str) -> ItemDefinition:
    """Definição exata ou erro claro."""
    try:
        return itens["defs"][nome]
    except KeyError:
        from ..erros import sugerir

        parecidas = sugerir(nome, sorted(itens["defs"]))
        dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                if parecidas else "")
        raise ErroELiXX(f'Item "{nome}" não definido.{dica}')


def itens_de(character) -> list[str]:
    """Instâncias possuídas pelo personagem (ordem de posse)."""
    return character.inventario.listar()


def possui(character, nome: str) -> bool:
    """Relações possui(personagem, item): por instância ou definição."""
    inventario = character.inventario
    if inventario.possui(nome):
        return True
    return len(inventario.de_definicao(nome)) > 0


def equipado(character, nome: str) -> bool:
    """Item equipado (por instância ou definição)."""
    inventario = character.inventario
    if inventario.equipado(nome):
        return True
    return any(inventario.equipado(inst)
               for inst in inventario.de_definicao(nome))


def slot_de(character, nome: str) -> str | None:
    """Slot do equipamento (None se não equipado)."""
    inventario = character.inventario
    direto = inventario.slot_de(nome)
    if direto is not None:
        return direto
    for inst in inventario.de_definicao(nome):
        slot = inventario.slot_de(inst)
        if slot is not None:
            return slot
    return None


def anexado(character, nome: str) -> str | None:
    """Parte de encaixe do item (None se solto)."""
    inventario = character.inventario
    direto = inventario.anexado(nome)
    if direto is not None:
        return direto
    for inst in inventario.de_definicao(nome):
        parte = inventario.anexado(inst)
        if parte is not None:
            return parte
    return None


def capacidades_de(character) -> CapabilitySet:
    """Próprias + itens equipados (ordem determinística, sem duplicar)."""
    conjunto = CapabilitySet()
    conjunto.unir(character.capacidades)
    for inst_nome in character.inventario.equipados_lista():
        instancia = character.inventario.instancias[inst_nome]
        definicao = character.inventario._defs_ref.get(instancia.definicao)
        if definicao is not None:
            conjunto.unir(definicao.capacidades)
    return conjunto


def tem_capacidade(character, capacidade: str) -> bool:
    """Acesso semântico (própria ou via equipamento)."""
    return capacidade in capacidades_de(character)


# ----- pode(): consulta determinística com requisitos -----

def _holder_anchor(character, mundo):
    """Entidade do mundo que representa o dono (ou None)."""
    if mundo is None:
        return None
    for nome in mundo._ordem:
        entidade = mundo._entidades[nome]
        if entidade.character is character:
            return entidade
    return None


def pode(character, capacidade: str, mundo=None, alvo: str | None = None,
         itens: dict | None = None) -> dict:
    """Responde se pode (nunca executa). Estruturado e determinístico.

    {
      permitido: bool, capacidade: str, motivo: str,
      requisitos: [{tipo, alvo, ok, detalhe}],
    }
    """
    conjunto = capacidades_de(character)
    if capacidade not in conjunto:
        return {"permitido": False, "capacidade": capacidade,
                "motivo": f'{character.nome} não possui capacidade '
                          f'"{capacidade}".',
                "requisitos": []}
    cap = conjunto.obter(capacidade)
    avaliados: list[dict] = []
    if cap.exige_alvo() and alvo is None:
        return {"permitido": False, "capacidade": capacidade,
                "motivo": f'Capacidade "{capacidade}" exige alvo '
                          f'(parâmetros: {", ".join(cap.parametros)}).',
                "requisitos": []}
    for req in cap.requisitos:
        ok, detalhe = _avaliar_requisito(character, cap, req, mundo, alvo,
                                         itens)
        avaliados.append({"tipo": req.kind, "alvo": req.alvo, "ok": ok,
                          "detalhe": detalhe})
        if not ok:
            return {"permitido": False, "capacidade": capacidade,
                    "motivo": detalhe, "requisitos": avaliados}
    return {"permitido": True, "capacidade": capacidade,
            "motivo": f'{character.nome} pode "{capacidade}".',
            "requisitos": avaliados}


def _resolver_alvo(req_alvo: str, alvo: str | None) -> str | None:
    if req_alvo == "alvo":
        return alvo
    return req_alvo


def _avaliar_requisito(character, cap: Capability, req: Requisito,
                       mundo, alvo: str | None,
                       itens: dict | None) -> tuple[bool, str]:
    inventario = character.inventario
    nome_alvo = _resolver_alvo(req.alvo, alvo)
    if req.kind == "equipado":
        if any(inventario.equipado(n)
               for n in _instancias_de(inventario, req.alvo)):
            return True, f"{req.alvo} equipada."
        return False, f"{req.alvo} não equipada por {character.nome}."
    if req.kind == "possuido":
        if any(inventario.possui(n)
               for n in _instancias_de(inventario, req.alvo)):
            return True, f"{req.alvo} possuída."
        return False, f"{req.alvo} não possuída por {character.nome}."
    if req.kind == "presente":
        if mundo is None:
            return False, "Sem mundo para verificar presença."
        if nome_alvo is None or nome_alvo not in mundo:
            return False, f'"{req.alvo}" ausente do mundo.'
        return True, f'"{nome_alvo}" presente.'
    if req.kind == "proximo":
        if mundo is None:
            return False, "Sem mundo para verificar proximidade."
        ancora = _holder_anchor(character, mundo)
        if ancora is None:
            return False, f"{character.nome} fora do mundo."
        if nome_alvo is None or nome_alvo not in mundo:
            return False, f'"{req.alvo}" ausente do mundo.'
        if mundo.perto_de(ancora.nome, nome_alvo, req.raio):
            return True, f"{nome_alvo} a até {req.raio:g}."
        return False, f"{nome_alvo} longe (raio {req.raio:g})."
    if req.kind in ("tag", "categoria", "tipo"):
        # Fase 14: req.alvo é o VALOR esperado; a entidade é o alvo.
        if mundo is None:
            return False, "Sem mundo para verificar alvo."
        if alvo is None or alvo not in mundo:
            return False, (f'Capacidade "{cap.nome}" exige alvo '
                           f"({req.kind}={req.alvo}).")
        entidade = mundo.por_id(alvo)
        if req.kind == "tag":
            ok = req.alvo in entidade.tags
        elif req.kind == "categoria":
            ok = entidade.categoria == req.alvo
        else:
            ok = entidade.tipo == req.alvo
        if ok:
            return True, f"{alvo} satisfaz {req.kind}={req.alvo}."
        return False, f"{alvo} não satisfaz {req.kind}={req.alvo}."
    if req.kind == "estado":
        provedor = _provedor_equipado(character, cap)
        if provedor is None:
            return False, (f'Capacidade "{cap.nome}" sem provedor com '
                            f'estado "{req.alvo}".')
        if provedor.estado == req.alvo:
            return True, f"{provedor.nome} está {req.alvo}."
        return False, (f"{provedor.nome} está {provedor.estado} "
                       f"(requer {req.alvo}).")
    if req.kind == "capacidade":
        if tem_capacidade(character, req.alvo):
            return True, f"Tem {req.alvo}."
        return False, f"Requer capacidade {req.alvo}."
    return False, f"Requisito desconhecido: {req.kind}."


def _instancias_de(inventario: Inventario, definicao: str) -> list[str]:
    """Nomes (instância direta + instâncias da definição)."""
    nomes = []
    if inventario.possui(definicao):
        nomes.append(definicao)
    nomes.extend(inventario.de_definicao(definicao))
    vistos: list[str] = []
    for nome in nomes:
        if nome not in vistos:
            vistos.append(nome)
    return vistos


def _provedor_equipado(character, cap: Capability):
    """Instância equipada que fornece a capability (ou None)."""
    inventario = character.inventario
    for inst_nome in inventario.equipados_lista():
        instancia = inventario.instancias[inst_nome]
        definicao = inventario._defs_ref.get(instancia.definicao)
        if definicao is not None and cap.nome in definicao.capacidades:
            return instancia
    return None


# ----- diagnóstico (painel textual; sem UI oficial) -----

def debug_capacidades(character, mundo=None) -> str:
    """Painel diagnóstico: próprias, compostas, posse, equipamento."""
    linhas = [f"CAPACIDADES DE {character.nome}"]
    proprias = character.capacidades.nomes()
    linhas.append(f"  próprias: {', '.join(proprias) or '—'}")
    compostas = capacidades_de(character).nomes()
    linhas.append(f"  compostas: {', '.join(compostas) or '—'}")
    linhas.append(f"  possui: {', '.join(itens_de(character)) or '—'}")
    equipados = character.inventario.equipados_lista()
    detalhe = ", ".join(
        f"{n} ({character.inventario.slot_de(n)})" for n in equipados)
    linhas.append(f"  equipados: {detalhe or '—'}")
    if mundo is not None:
        ancora = _holder_anchor(character, mundo)
        linhas.append(f"  no mundo: {ancora.nome if ancora else 'fora'}")
    return "\n".join(linhas)
