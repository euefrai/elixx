"""AST da ELiXX — tipos claros, independentes de qualquer renderizador.

O parsing nunca renderiza nada: ele só constrói estes nós. O runtime
interpreta a AST depois, e o gerador HTML a converte em página.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------- expressões ----------

@dataclass
class TextoLit:
    valor: str
    linha: int = 0


@dataclass
class NumeroLit:
    valor: float
    linha: int = 0


@dataclass
class Medida:
    """Número com unidade (ex. 800px, 20%, 500ms)."""

    valor: float
    unidade: str
    linha: int = 0


@dataclass
class CorLit:
    formato: str  # "hex" ou "nomeada"
    valor: str
    linha: int = 0


@dataclass
class Booleano:
    valor: bool
    linha: int = 0


@dataclass
class ListaLit:
    """Literal de lista: [10, 25, 35] (Fase 07, séries para gráficos)."""

    itens: list = field(default_factory=list)
    linha: int = 0


@dataclass
class Ident:
    nome: str
    linha: int = 0


@dataclass
class Chamada:
    nome: str
    args: list = field(default_factory=list)
    linha: int = 0


@dataclass
class Membro:
    """Acesso por pontos: dados.sistema.cpu (base.atributo, encadeável)."""

    base: object
    atributo: str
    linha: int = 0


@dataclass
class Binaria:
    op: str
    esquerda: object
    direita: object
    linha: int = 0


# ---------- comandos ----------

@dataclass
class Acao:
    nome: str
    args: list = field(default_factory=list)
    linha: int = 0


@dataclass
class Se:
    condicao: object
    entao: object
    senao: object | None = None
    linha: int = 0


@dataclass
class Repetir:
    vezes: object | None  # None = sem número (runtime executa 1x + aviso)
    bloco: object = None
    linha: int = 0


@dataclass
class Retornar:
    valor: object | None = None
    linha: int = 0


@dataclass
class Atribuicao:
    """Escrita de estado/variável: estado.x = 1, estado.n += 2 (Fase 05)."""

    alvo: object  # Membro
    op: str = "="  # = += -= *= /=
    valor: object = None
    linha: int = 0


@dataclass
class Bloco:
    comandos: list = field(default_factory=list)
    linha: int = 0


@dataclass
class Funcao:
    nome: str
    params: list[str] = field(default_factory=list)
    bloco: Bloco = field(default_factory=Bloco)
    linha: int = 0


# ---------- estrutura visual ----------

@dataclass
class Propriedade:
    nome: str
    valores: list = field(default_factory=list)
    linha: int = 0


@dataclass
class Evento:
    nome: str
    bloco: Bloco = field(default_factory=Bloco)
    linha: int = 0


@dataclass
class ChaveAnimacaoAST:
    """Uma linha animada: propriedade, de (ou None) e para."""

    propriedade: str
    de: object = None
    para: object = None
    linha: int = 0


@dataclass
class KeyframeAST:
    """Quadro do Motion Core 2.0: `40% { posição: ... }` (tempo 0..100)."""

    percent: float = 0.0
    chaves: list = field(default_factory=list)  # ChaveAnimacaoAST
    linha: int = 0


@dataclass
class AnimacaoDef:
    """Bloco `animação nome { ... }` (Fase 03; Motion Core na Fase 11)."""

    nome: str = ""
    alvo: str = ""
    chaves: list = field(default_factory=list)
    duracao_ms: float = 500.0
    atraso_ms: float = 0.0
    movimento: str = "suave"
    repetir: object = None  # None = 1x; int; "infinito"
    depois: str | None = None
    inicio: str = "automatico"
    ao_terminar: Bloco | None = None
    linha: int = 0
    # Fase 11: composição e dinâmica (padrões = comportamento Fase 03).
    modo: str = "normal"  # normal | ping_pong
    relativo: bool = False  # para = deslocamento a partir do atual
    voltas: int = 0  # voltas completas extras na rotação
    fisica: str | None = None  # None | "mola" (dinâmica, ≠ easing)
    rigidez: float = 180.0
    amortecimento: float = 12.0
    massa: float = 1.0
    keyframes: list = field(default_factory=list)  # KeyframeAST
    ao_comecar: Bloco | None = None
    ao_cancelar: Bloco | None = None


@dataclass
class PoseEntrada:
    """Uma parte numa pose: `braço:` + props de transformação."""

    parte: str
    propriedades: list = field(default_factory=list)  # Propriedade
    linha: int = 0


@dataclass
class PoseDef:
    """`pose nome { parte: (props...) }` (ou `expressao`, parcial)."""

    nome: str = ""
    entradas: list = field(default_factory=list)  # PoseEntrada
    expressao: bool = False
    linha: int = 0


@dataclass
class Parte:
    """`parte nome { ... }` — nó articulável (subpartes + visuais)."""

    nome: str = ""
    propriedades: list = field(default_factory=list)  # Propriedade
    partes: list = field(default_factory=list)  # Parte (subpartes)
    filhos: list = field(default_factory=list)  # Componente|Instancia|grupo
    capacidades: list = field(default_factory=list)  # CapacidadeDef (F14)
    linha: int = 0


@dataclass
class Personagem:
    """`personagem Nome { parte* pose* }` — entidade visual coerente."""

    nome: str = ""
    propriedades: list = field(default_factory=list)  # Propriedade (root)
    partes: list = field(default_factory=list)  # Parte
    poses: list = field(default_factory=list)  # PoseDef
    capacidades: list = field(default_factory=list)  # CapacidadeDef (F14)
    filhos: list = field(default_factory=list)  # visuais soltos (acessório)
    linha: int = 0


@dataclass
class Componente:
    tipo: str  # "botao", "texto", "imagem", "video", "audio"
    nome: str = ""
    propriedades: list[Propriedade] = field(default_factory=list)
    eventos: list[Evento] = field(default_factory=list)
    filhos: list = field(default_factory=list)  # Componente|Instancia
    modelo: list = field(default_factory=list)  # Fase 09: template de lista
    linha: int = 0


@dataclass
class ParamCap:
    """Parâmetro declarado de capability (`parametro alvo`)."""

    nome: str
    linha: int = 0


@dataclass
class CapacidadeDef:
    """`capacidade nome` ou bloco (descrição, params, requisitos)."""

    nome: str = ""
    parametros: list = field(default_factory=list)  # ParamCap
    propriedades: list = field(default_factory=list)  # Propriedade
    linha: int = 0


@dataclass
class ItemDef:
    """`item Nome { ... }` — definição semântica (Fase 14, sem visual)."""

    nome: str = ""
    propriedades: list = field(default_factory=list)  # Propriedade
    capacidades: list = field(default_factory=list)  # CapacidadeDef
    linha: int = 0


@dataclass
class EntidadeMundo:
    """Entidade semântica do World (Fase 13): tipo + nome + propriedades.

    Tipos: chao, parede, plataforma, obstaculo, objeto, area, ponto,
    personagem (via `usar personagem Nome`), item (via `usar item`).
    `ref` guarda a definição referenciada (personagem/item).
    """

    tipo: str = ""
    nome: str = ""
    propriedades: list = field(default_factory=list)  # Propriedade
    ref: str = ""
    linha: int = 0


@dataclass
class Mundo:
    """`mundo Nome { ... }` — camada semântica sobre a cena (Fase 13)."""

    nome: str = ""
    propriedades: list = field(default_factory=list)  # Propriedade
    entidades: list = field(default_factory=list)  # EntidadeMundo
    linha: int = 0


@dataclass
class CaminhoNav:
    """`caminho A -> B { modo/custo/requer/bloqueado }` (Fase 15)."""

    origem: str = ""
    destino: str = ""
    propriedades: list = field(default_factory=list)  # Propriedade
    linha: int = 0


@dataclass
class Navegacao:
    """`navegacao Nome { caminho* }` — grafo explícito (Fase 15)."""

    nome: str = ""
    caminhos: list = field(default_factory=list)  # CaminhoNav
    linha: int = 0


@dataclass
class Janela:
    nome: str = ""
    propriedades: list = field(default_factory=list)
    componentes: list = field(default_factory=list)  # Componente|Instancia
    eventos: list = field(default_factory=list)
    animacoes: list = field(default_factory=list)
    mundos: list = field(default_factory=list)  # Mundo (Fase 13)
    itens: list = field(default_factory=list)  # ItemDef (Fase 14)
    navegacoes: list = field(default_factory=list)  # Navegacao (Fase 15)
    eh_tela: bool = False  # Fase 08: bloco `tela` (navegação)
    linha: int = 0


@dataclass
class EstadoDef:
    """Bloco `estado { ... }` de programa (Fase 05, escopo global)."""

    propriedades: list[Propriedade] = field(default_factory=list)
    linha: int = 0


@dataclass
class TemaDef:
    """Bloco `tema nome { cores/tamanhos/espacos }` (Fase 08)."""

    nome: str = ""
    cores: list = field(default_factory=list)  # Propriedade (CorLit)
    tamanhos: list = field(default_factory=list)  # Propriedade (Medida)
    espacos: list = field(default_factory=list)  # Propriedade (Medida)
    linha: int = 0


@dataclass
class ParamComponente:
    """`propriedade nome [: padrao]` de componente reutilizável."""

    nome: str = ""
    padrao: object = None
    linha: int = 0


@dataclass
class ComponenteDef:
    """`componente Nome { propriedade.. [estado {}] corpo {..} }`."""

    nome: str = ""
    params: list = field(default_factory=list)  # ParamComponente
    estado: object = None  # EstadoDef|None (Fase 09: padrões locais)
    corpo: list = field(default_factory=list)  # Componente
    linha: int = 0


@dataclass
class Instancia:
    """Uso `Nome inst { props, filhos, eventos }` (expandido p/ Fase 08)."""

    tipo_nome: str = ""
    nome: str = ""
    propriedades: list[Propriedade] = field(default_factory=list)
    filhos: list = field(default_factory=list)  # Componente (slot)
    eventos: list[Evento] = field(default_factory=list)
    linha: int = 0


@dataclass
class BlocoDados:
    """Sub-bloco de fonte: cabecalhos/parametros/corpo (Fase 06)."""

    nome: str = ""
    propriedades: list[Propriedade] = field(default_factory=list)
    linha: int = 0


@dataclass
class FonteDef:
    """Bloco `dados nome { url/metodo/... }` (Fase 06)."""

    nome: str = ""
    propriedades: list[Propriedade] = field(default_factory=list)
    blocos: list = field(default_factory=list)  # BlocoDados
    linha: int = 0


@dataclass
class AcaoDef:
    """`acao nome [(params)] { comandos }` (Fase 09, reutilizável)."""

    nome: str = ""
    params: list[str] = field(default_factory=list)
    bloco: Bloco = field(default_factory=Bloco)
    linha: int = 0


@dataclass
class Import:
    """`importar a.b.c` (Fase 09, resolvido pelo carregador)."""

    caminho: str = ""
    linha: int = 0


@dataclass
class Programa:
    janelas: list[Janela] = field(default_factory=list)
    telas: list[Janela] = field(default_factory=list)  # Fase 08
    funcoes: list[Funcao] = field(default_factory=list)
    acoes: list = field(default_factory=list)  # AcaoDef (Fase 09)
    imports: list = field(default_factory=list)  # Import (Fase 09)
    estado: EstadoDef | None = None
    fontes: list = field(default_factory=list)  # FonteDef (Fase 06)
    temas: list = field(default_factory=list)  # TemaDef (Fase 08)
    componentes: list = field(default_factory=list)  # ComponenteDef
    locais: dict = field(default_factory=dict)  # Fase 09: ns -> {chave: valor}


# ---------- utilidade ----------

def mostrar_arvore(no: object, nivel: int = 0) -> str:
    """Representação em árvore da AST (usada na CLI e nos testes)."""
    ind = "  " * nivel
    if isinstance(no, Programa):
        linhas = ["Programa"]
        if no.estado is not None:
            linhas.append(mostrar_arvore(no.estado, nivel + 1))
        for imp in no.imports:
            linhas.append(mostrar_arvore(imp, nivel + 1))
        for fonte in no.fontes:
            linhas.append(mostrar_arvore(fonte, nivel + 1))
        for tema in no.temas:
            linhas.append(mostrar_arvore(tema, nivel + 1))
        for cd in no.componentes:
            linhas.append(mostrar_arvore(cd, nivel + 1))
        for f in no.funcoes:
            linhas.append(mostrar_arvore(f, nivel + 1))
        for a in no.acoes:
            linhas.append(mostrar_arvore(a, nivel + 1))
        for j in no.janelas:
            linhas.append(mostrar_arvore(j, nivel + 1))
        for t in no.telas:
            linhas.append(mostrar_arvore(t, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, TemaDef):
        return f"{ind}Tema {no.nome}"
    if isinstance(no, ComponenteDef):
        return (f"{ind}Componente {no.nome}("
                f"{', '.join(p.nome for p in no.params)})")
    if isinstance(no, Instancia):
        return f"{ind}Usa {no.tipo_nome} {no.nome}"
    if isinstance(no, FonteDef):
        linhas = [f"{ind}Fonte {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for bloco in no.blocos:
            linhas.append(f"{ind}  Bloco {bloco.nome}")
            for p in bloco.propriedades:
                linhas.append(mostrar_arvore(p, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, EstadoDef):
        linhas = [f"{ind}Estado"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, Funcao):
        return f"{ind}Função {no.nome}({', '.join(no.params)})"
    if isinstance(no, AcaoDef):
        return f"{ind}Ação {no.nome}({', '.join(no.params)})"
    if isinstance(no, Import):
        return f"{ind}Importar {no.caminho}"
    if isinstance(no, Janela):
        linhas = [f"{ind}{'Tela' if no.eh_tela else 'Janela'} {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for c in no.componentes:
            linhas.append(mostrar_arvore(c, nivel + 1))
        for m in no.mundos:
            linhas.append(mostrar_arvore(m, nivel + 1))
        for i in no.itens:
            linhas.append(mostrar_arvore(i, nivel + 1))
        for n in no.navegacoes:
            linhas.append(mostrar_arvore(n, nivel + 1))
        for e in no.eventos:
            linhas.append(mostrar_arvore(e, nivel + 1))
        for a in no.animacoes:
            linhas.append(mostrar_arvore(a, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, Navegacao):
        linhas = [f"{ind}Navegacao {no.nome}"]
        for c in no.caminhos:
            linhas.append(mostrar_arvore(c, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, CaminhoNav):
        linhas = [f"{ind}Caminho {no.origem} -> {no.destino}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, ItemDef):
        linhas = [f"{ind}Item {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for cap in no.capacidades:
            linhas.append(mostrar_arvore(cap, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, CapacidadeDef):
        linhas = [f"{ind}Capacidade {no.nome}"]
        for param in no.parametros:
            linhas.append(f"{ind}  Parametro {param.nome}")
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, Componente):
        rotulo = {"botao": "Botão", "texto": "Texto", "imagem": "Imagem",
                  "video": "Vídeo", "audio": "Áudio", "painel": "Painel",
                  "cartao": "Cartão", "barra": "Barra",
                  "grafico": "Gráfico", "lista": "Lista",
                  "linha": "Linha", "coluna": "Coluna", "grade": "Grade",
                  "pilha": "Pilha", "entrada": "Entrada",
                  "checkbox": "Checkbox", "selecao": "Seleção",
                  "separador": "Separador",
                  "indicador": "Indicador",
                   "icone": "Ícone", "formulario": "Formulário",
                   "aba": "Aba", "abas": "Abas", "menu": "Menu",
                   "tabela": "Tabela", "modal": "Modal",
                   "conteudo": "Conteúdo",
                   "grupo": "Grupo", "objeto": "Objeto"}.get(
                       no.tipo, no.tipo)
        linhas = [f"{ind}{rotulo} {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for e in no.eventos:
            linhas.append(mostrar_arvore(e, nivel + 1))
        for f in no.filhos:
            linhas.append(mostrar_arvore(f, nivel + 1))
        if no.modelo:
            linhas.append(f"{ind}Modelo")
            for m in no.modelo:
                linhas.append(mostrar_arvore(m, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, Personagem):
        linhas = [f"{ind}Personagem {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for parte in no.partes:
            linhas.append(mostrar_arvore(parte, nivel + 1))
        for pose in no.poses:
            linhas.append(mostrar_arvore(pose, nivel + 1))
        for cap in no.capacidades:
            linhas.append(mostrar_arvore(cap, nivel + 1))
        for f in no.filhos:
            linhas.append(mostrar_arvore(f, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, Parte):
        linhas = [f"{ind}Parte {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for sub in no.partes:
            linhas.append(mostrar_arvore(sub, nivel + 1))
        for cap in no.capacidades:
            linhas.append(mostrar_arvore(cap, nivel + 1))
        for f in no.filhos:
            linhas.append(mostrar_arvore(f, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, PoseDef):
        rotulo = "Expressão" if no.expressao else "Pose"
        linhas = [f"{ind}{rotulo} {no.nome}"]
        for entrada in no.entradas:
            linhas.append(f"{ind}  {entrada.parte}:")
            for p in entrada.propriedades:
                linhas.append(mostrar_arvore(p, nivel + 2))
        return "\n".join(linhas)
    if isinstance(no, Mundo):
        linhas = [f"{ind}Mundo {no.nome}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        for e in no.entidades:
            linhas.append(mostrar_arvore(e, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, EntidadeMundo):
        rotulo = f"Entidade {no.tipo} {no.nome}"
        if no.ref and no.ref != no.nome:
            rotulo += f" (de {no.ref})"
        linhas = [f"{ind}{rotulo}"]
        for p in no.propriedades:
            linhas.append(mostrar_arvore(p, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, Propriedade):
        return f"{ind}Propriedade {no.nome} = {valores_para_texto(no.valores)}"
    if isinstance(no, Evento):
        linhas = [f"{ind}Evento quando {no.nome}"]
        for c in no.bloco.comandos:
            linhas.append(mostrar_arvore(c, nivel + 1))
        return "\n".join(linhas)
    if isinstance(no, AnimacaoDef):
        linhas = [f"{ind}Animação {no.nome} → {no.alvo} "
                   f"({no.movimento}, {no.duracao_ms:g}ms)"]
        for chave in no.chaves:
            linhas.append(f"{ind}  Chave {chave.propriedade} = "
                           f"{valores_para_texto([chave.para])}")
        for quadro in no.keyframes:
            linhas.append(f"{ind}  Quadro {quadro.percent:g}%")
        if no.ao_terminar is not None:
            linhas.append(f"{ind}  quando terminar")
        if no.ao_comecar is not None:
            linhas.append(f"{ind}  quando começar")
        if no.ao_cancelar is not None:
            linhas.append(f"{ind}  quando cancelar")
        return "\n".join(linhas)
    if isinstance(no, Acao):
        return f"{ind}Ação {no.nome}({valores_para_texto(no.args)})"
    if isinstance(no, Se):
        return f"{ind}Se ..."
    if isinstance(no, Repetir):
        return f"{ind}Repetir ..."
    if isinstance(no, Retornar):
        return f"{ind}Retornar ..."
    if isinstance(no, Atribuicao):
        return (f"{ind}Atribuir {caminho_de_membro(no.alvo)} {no.op} "
                f"{valores_para_texto([no.valor])}")
    return f"{ind}{no!r}"


def valores_para_texto(valores: list) -> str:
    partes = []
    for v in valores:
        if isinstance(v, TextoLit):
            partes.append(f'"{v.valor}"')
        elif isinstance(v, NumeroLit):
            partes.append(str(v.valor))
        elif isinstance(v, Medida):
            partes.append(f"{v.valor:g}{v.unidade}")
        elif isinstance(v, CorLit):
            partes.append(v.valor)
        elif isinstance(v, Ident):
            partes.append(v.nome)
        elif isinstance(v, Chamada):
            partes.append(f"{v.nome}(...)")
        elif isinstance(v, Membro):
            partes.append(caminho_de_membro(v))
        elif isinstance(v, Binaria):
            partes.append(f"({valores_para_texto([v.esquerda])} "
                           f"{v.op} {valores_para_texto([v.direita])})")
        elif isinstance(v, Booleano):
            partes.append("verdadeiro" if v.valor else "falso")
        elif isinstance(v, ListaLit):
            partes.append("[" + ", ".join(
                valores_para_texto([item]) for item in v.itens) + "]")
        else:
            partes.append(str(v))
    return " ".join(partes)


def caminho_de_membro(no: object) -> str:
    """'dados.sistema.cpu' a partir de um Membro encadeado."""
    partes = []
    atual = no
    while isinstance(atual, Membro):
        partes.append(atual.atributo)
        atual = atual.base
    if isinstance(atual, Ident):
        partes.append(atual.nome)
    elif isinstance(atual, Chamada):
        partes.append(atual.nome)
    return ".".join(reversed(partes))
