"""HTML → Environment Adapter da ELiXX (Fase 20).

Transforma HTML real em `Environment` (F19), tratando o HTML
exclusivamente como DADO: nenhum JavaScript é executado, nenhum CSS é
interpretado, nenhuma URL é aberta, nenhum request é feito.

    HTML ──→ HTMLParser (stdlib) ──→ HTMLNode ──→ HTMLAdapter
        ──→ Environment ──→ vincular_ambiente (F19) ──→ World

Somente stdlib (`html.parser`). Sem dependências externas, sem
navegador, sem threads, sem relógio em decisões, sem random: dois
parses do mesmo HTML produzem os mesmos IDs e a mesma estrutura.

Princípio honesto: HTML informa ESTRUTURA, nunca posição visual.
Geometria nunca é inventada — só entra via mapa explícito
(`geometria={id: {x, y, largura, altura}}`) de fonte geométrica
separada. Sem geometria, o Environment sai estrutural (válido).
"""

from __future__ import annotations

import math
from html.parser import HTMLParser

from ..erros import ErroELiXX
from .ambiente import (
    MAX_NOS,
    MAX_PROFUNDIDADE,
    Environment,
    EnvironmentNode,
    EnvironmentRegion,
    EnvironmentSurface,
    InteractionDescriptor,
)

__all__ = [
    "ATRIBUTOS_SEGUROS",
    "MAPEAMENTO_TAGS",
    "REGRAS_ARIA",
    "TAGS_REGIAO",
    "TAGS_TEXTO",
    "VOID_ELEMENTS",
    "HTMLNode",
    "HTMLDocument",
    "HTMLAdapter",
    "parsear_html",
    "html_para_environment",
    "debug_html",
]

# ---------------------------------------------------------------------------
# Vocabulário documentado (regras explícitas; nada é adivinhado)
# ---------------------------------------------------------------------------

VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
})
"""Elementos vazios: nunca empilhados, nunca têm filhos/texto."""

ATRIBUTOS_SEGUROS = frozenset({
    "id", "class", "role", "aria-label", "aria-labelledby",
    "aria-describedby", "name", "type", "value", "placeholder",
    "title", "alt", "href", "action", "formaction", "src", "method",
    "disabled", "readonly", "required", "checked", "selected",
})
"""Atributos preservados como dados. `aria-*`/`data-*` genéricos também
são aceitos (sempre inertes). Atributos `on*` (event handlers) e
`style` são descartados e contados em avisos. Nada é executado."""

TAGS_REGIAO = frozenset({
    "header", "nav", "main", "section", "article", "aside", "footer",
})
"""Tags que viram `EnvironmentRegion` (hierarquia preservada)."""

TAGS_TEXTO = frozenset({
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "label",
    "option", "title", "legend", "caption", "a", "button",
    "th", "td",
})
"""Tags cujo `texto` do EnvironmentNode recebe o texto completo da
subárvore (normalizado). Contêineres recebem só o texto direto; demais
nós recebem `None`."""

# tag → (tipo_env, interativo, [interações], é_região)
MAPEAMENTO_TAGS = {
    "button": ("botao", True, ["clicar", "focar"], False),
    "input": ("entrada", True, ["focar", "escrever"], False),
    "textarea": ("entrada", True, ["focar", "escrever", "limpar"], False),
    "select": ("selecao", True, ["focar", "selecionar"], False),
    "a": ("link", True, ["abrir"], False),
    "form": ("formulario", False, [], False),
    "img": ("imagem", False, [], False),
    "table": ("tabela", False, [], False),
    "ul": ("lista", False, [], False),
    "ol": ("lista", False, [], False),
    "li": ("item", False, [], False),
    "option": ("item", False, [], False),
    "div": ("painel", False, [], False),
    "span": ("texto", False, [], False),
    "header": ("regiao", False, [], True),
    "nav": ("regiao", False, [], True),
    "main": ("regiao", False, [], True),
    "section": ("regiao", False, [], True),
    "article": ("regiao", False, [], True),
    "aside": ("regiao", False, [], True),
    "footer": ("regiao", False, [], True),
    "h1": ("texto", False, [], False),
    "h2": ("texto", False, [], False),
    "h3": ("texto", False, [], False),
    "h4": ("texto", False, [], False),
    "h5": ("texto", False, [], False),
    "h6": ("texto", False, [], False),
    "p": ("texto", False, [], False),
    "label": ("texto", False, [], False),
}
"""Mapeamento HTML → Environment. Tags fora daqui viram `elemento`
(genérico, nunca descartado). `input`/`span` têm refinamentos abaixo."""

# role ARIA → (tipo_env, interativo, [interações], é_região).
# Só aplicado a tags genéricas (div/span/elemento); tag semântica vence.
REGRAS_ARIA = {
    "button": ("botao", True, ["clicar", "focar"], False),
    "link": ("link", True, ["abrir"], False),
    "textbox": ("entrada", True, ["focar", "escrever"], False),
    "searchbox": ("entrada", True, ["focar", "escrever"], False),
    "checkbox": ("selecao", True, ["focar", "marcar", "desmarcar"], False),
    "radio": ("selecao", True, ["focar", "selecionar"], False),
    "combobox": ("selecao", True, ["focar", "selecionar"], False),
    "listbox": ("lista", True, ["focar", "selecionar"], False),
    "option": ("item", False, [], False),
    "img": ("imagem", False, [], False),
    "heading": ("texto", False, [], False),
    "navigation": ("regiao", False, [], True),
    "banner": ("regiao", False, [], True),
    "main": ("regiao", False, [], True),
    "contentinfo": ("regiao", False, [], True),
    "complementary": ("regiao", False, [], True),
    "region": ("regiao", False, [], True),
    "form": ("formulario", False, [], False),
}
"""Upgrade ARIA para elementos genéricos. Combinação desconhecida não
muda nada (sem assumir validade ARIA)."""

TIPOS_INPUT_TEXTO = frozenset({
    "text", "password", "search", "email", "number", "url", "tel",
    "", "hidden",
})
"""`type` de input tratado como entrada textual (inclui ausência)."""

MAX_PROFUNDIDADE_HTML = 256
"""Teto do parser (anti-ataque). O adapter trunca em MAX_PROFUNDIDADE
(F19) com aviso em vez de falhar."""

MAX_TEXTO_NOME = 120
"""Teto do `nome` derivado (determinístico; texto completo segue em
`texto` quando for tag de texto)."""


# ---------------------------------------------------------------------------
# HTMLNode — representação intermediária (só dados)
# ---------------------------------------------------------------------------

class HTMLNode:
    """Nó estrutural do HTML parseado. Só dados, sem executáveis."""

    def __init__(self, tag: str, atributos: dict | None = None,
                 ordem: int = 0, profundidade: int = 0) -> None:
        self.tag = str(tag).lower()
        self.atributos = dict(atributos or {})
        self.texto = ""  # texto direto normalizado (preenchido no parse)
        self.parent: HTMLNode | None = None
        self.children: list[HTMLNode] = []
        self.ordem = int(ordem)
        self.profundidade = int(profundidade)
        self._pedacos: list[str] = []  # texto direto bruto (interno)

    def adicionar_filho(self, filho: HTMLNode) -> HTMLNode:
        filho.parent = self
        self.children.append(filho)
        return filho

    def texto_completo(self) -> str:
        """Texto direto + descendentes, em ordem, normalizado."""
        partes = [self.texto]
        for filho in self.children:
            partes.append(filho.texto_completo())
        return _normalizar(" ".join(partes))

    def descendentes(self) -> list[HTMLNode]:
        saida: list[HTMLNode] = []
        for filho in self.children:
            saida.append(filho)
            saida.extend(filho.descendentes())
        return saida

    def __repr__(self) -> str:
        return f"HTMLNode({self.tag} ordem={self.ordem})"


class HTMLDocument:
    """Resultado do parse: raiz + avisos estruturados + estatísticas."""

    def __init__(self, raiz: HTMLNode, avisos: list | None = None,
                 total_nos: int = 0, scripts_ignorados: int = 0,
                 estilos_ignorados: int = 0,
                 handlers_removidos: int = 0) -> None:
        self.raiz = raiz
        self.avisos = list(avisos or [])
        self.total_nos = int(total_nos)
        self.scripts_ignorados = int(scripts_ignorados)
        self.estilos_ignorados = int(estilos_ignorados)
        self.handlers_removidos = int(handlers_removidos)

    def __repr__(self) -> str:
        return (f"HTMLDocument({self.total_nos} nós, "
                f"{len(self.avisos)} avisos)")


def _normalizar(texto: str) -> str:
    """Whitespace colapsado de forma determinística."""
    return " ".join(str(texto or "").split())


# ---------------------------------------------------------------------------
# Parser stdlib (tolerante; documentado em docs/html-environment.md)
# ---------------------------------------------------------------------------

class _ConstrutorArvore(HTMLParser):
    """HTMLParser → árvore HTMLNode. Nunca executa nada."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[HTMLNode] = []
        self.raizes: list[HTMLNode] = []
        self.ordem = 0
        self.scripts_ignorados = 0
        self.estilos_ignorados = 0
        self.handlers_removidos = 0
        self._ignorando: str | None = None  # script/style aberto
        self._profundidade = 0

    # -- construção --

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = str(tag).lower()
        if tag in ("script", "style"):
            if tag == "script":
                self.scripts_ignorados += 1
            else:
                self.estilos_ignorados += 1
            no = self._novo_no(tag, attrs)
            self._ignorando = tag
            return
        no = self._novo_no(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.pilha.append(no)
            self._profundidade += 1

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        tag = str(tag).lower()
        if tag in ("script", "style"):
            if tag == "script":
                self.scripts_ignorados += 1
            else:
                self.estilos_ignorados += 1
            self._novo_no(tag, attrs)
            return
        self._novo_no(tag, attrs)  # autofechada: sem empilhar

    def handle_endtag(self, tag: str) -> None:
        tag = str(tag).lower()
        if self._ignorando is not None:
            if tag == self._ignorando:
                self._ignorando = None
            return
        # Tolerante: desempilha até o par correspondente; sem par, ignora.
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i].tag == tag:
                del self.pilha[i:]
                self._profundidade = len(self.pilha)
                return

    def handle_data(self, dados: str) -> None:
        if self._ignorando is not None:
            return  # conteúdo de script/style: descartado, contado
        if not self.pilha:
            if _normalizar(dados):
                # Texto fora de qualquer elemento: raiz sintética o guarda.
                if not self.raizes or self.raizes[-1].tag != "fragment":
                    frag = HTMLNode("fragment", {}, self.ordem, 0)
                    self.ordem += 1
                    self.raizes.append(frag)
                self.raizes[-1]._pedacos.append(dados)
            return
        self.pilha[-1]._pedacos.append(dados)

    def handle_comment(self, _dados: str) -> None:
        pass  # comentários: ignorados silenciosamente (sem semântica)

    def handle_decl(self, _decl: str) -> None:
        pass  # doctype: ignorado (sem semântica)

    def handle_pi(self, _dados: str) -> None:
        pass  # processing instructions: ignoradas

    # -- interno --

    def _novo_no(self, tag: str, attrs: list) -> HTMLNode:
        if self.ordem >= MAX_NOS:
            raise ErroELiXX(f"HTML com mais de {MAX_NOS} nós "
                            "(estrutura gigante recusada).")
        if self._profundidade >= MAX_PROFUNDIDADE_HTML:
            raise ErroELiXX("HTML profundo demais "
                            f"(>{MAX_PROFUNDIDADE_HTML} níveis).")
        atributos, removidos = _filtrar_atributos(attrs)
        self.handlers_removidos += removidos
        no = HTMLNode(tag, atributos, self.ordem,
                      len(self.pilha))
        self.ordem += 1
        if self.pilha:
            self.pilha[-1].adicionar_filho(no)
        else:
            self.raizes.append(no)
        if tag in ("script", "style"):
            # Registra na árvore (presente, conteúdo ignorado) sem empilhar.
            pass
        return no

    def finalizar(self) -> HTMLNode:
        for no in self._tudo():
            no.texto = _normalizar(" ".join(no._pedacos))
            no._pedacos = []
        if len(self.raizes) == 1:
            return self.raizes[0]
        frag = HTMLNode("fragment", {}, self.ordem, 0)
        self.ordem += 1
        for raiz in self.raizes:
            frag.adicionar_filho(raiz)
        return frag

    def _tudo(self) -> list[HTMLNode]:
        saida: list[HTMLNode] = []
        for raiz in self.raizes:
            saida.append(raiz)
            saida.extend(raiz.descendentes())
        return saida


def _filtrar_atributos(attrs: list) -> tuple[dict, int]:
    """Mantém só o safelist; conta handlers `on*`/`style` removidos."""
    mantidos: dict[str, str] = {}
    removidos = 0
    for nome, valor in (attrs or []):
        chave = str(nome).lower()
        if chave.startswith("on") and len(chave) > 2:
            removidos += 1  # event handler: descartado, contado
            continue
        if chave == "style":
            removidos += 1  # CSS inline: não interpretado, descartado
            continue
        if chave in ATRIBUTOS_SEGUROS or chave.startswith("aria-") \
                or chave.startswith("data-"):
            mantidos[chave] = "" if valor is None else str(valor)
    return mantidos, removidos


def parsear_html(texto: str) -> HTMLDocument:
    """HTML real → HTMLDocument (árvore + avisos; nada executado)."""
    if not isinstance(texto, str):
        raise ErroELiXX("parsear_html espera texto "
                        f"(recebido {type(texto).__name__}).")
    construtor = _ConstrutorArvore()
    try:
        construtor.feed(texto)
        construtor.close()
    except ErroELiXX:
        raise
    except Exception as exc:
        raise ErroELiXX(f"Falha no parse HTML: {exc}.")
    raiz = construtor.finalizar()
    total = 1 + len(raiz.descendentes())
    avisos: list[dict] = []
    if construtor.scripts_ignorados:
        avisos.append({"codigo": "script_ignorado",
                       "motivo": f"{construtor.scripts_ignorados} "
                                 "<script> presente(s); conteúdo ignorado, "
                                 "nada executado."})
    if construtor.estilos_ignorados:
        avisos.append({"codigo": "estilo_ignorado",
                       "motivo": f"{construtor.estilos_ignorados} "
                                 "<style> presente(s); CSS não "
                                 "interpretado."})
    if construtor.handlers_removidos:
        avisos.append({"codigo": "handlers_removidos",
                       "motivo": f"{construtor.handlers_removidos} "
                                 "atributo(s) on*/style descartado(s); "
                                 "nada executado."})
    return HTMLDocument(raiz, avisos, total,
                        construtor.scripts_ignorados,
                        construtor.estilos_ignorados,
                        construtor.handlers_removidos)


# ---------------------------------------------------------------------------
# HTMLAdapter — HTMLNode → Environment (determinístico)
# ---------------------------------------------------------------------------

class HTMLAdapter:
    """Converte HTML parseado em Environment (F19).

    Regras de ID (documentadas): `id="x"` explícito vira `x`; sem id,
    caminho estrutural `html.body.main.button[0]` (`[i]` = posição entre
    irmãos de mesma tag, só quando há mais de um). IDs explícitos
    duplicados ganham sufixo determinístico `__2`, `__3`... em ordem de
    documento + aviso `id_duplicado` (nunca sobrescreve).
    """

    def __init__(self, geometria: dict | None = None) -> None:
        self.geometria = dict(geometria or {})
        self.avisos: list[dict] = []
        self._usados: set[str] = set()
        self._contagem_ids: dict[str, int] = {}
        self._no_por_ordem: dict[int, str] = {}  # ordem HTML → id final

    # -- entrada principal --

    @staticmethod
    def parsear(html: str, geometria: dict | None = None,
                env_id: str = "pagina", nome: str = "") -> tuple:
        """HTML + geometria opcional → (Environment, avisos).

        Nunca inventa coordenadas: sem entrada no mapa, o nó sai com
        0,0,0,0 (estrutural, válido). Nenhuma Surface é criada só por
        existir tag — apenas com `"superficie": true` na geometria.
        """
        return HTMLAdapter(geometria).converter(html, env_id, nome)

    def converter(self, html: str, env_id: str = "pagina",
                  nome: str = "") -> tuple:
        doc = parsear_html(html)
        self.avisos = list(doc.avisos)
        env = Environment(env_id, nome=nome or _titulo(doc.raiz),
                          tipo="web", largura=800.0, altura=600.0,
                          metadados={"fonte": "html",
                                     "total_nos": doc.total_nos})
        if doc.total_nos == 0:
            return env, list(self.avisos)
        self._atribuir_ids(doc.raiz)
        self._converter_subarvore(doc.raiz, env, None, None)
        self._aplicar_geometria(env)
        resultado = env.validar()
        if not resultado["valido"]:
            raise ErroELiXX(f"Environment derivado inválido: "
                            f"{resultado['motivo']}")
        return env, list(self.avisos)

    # -- IDs determinísticos --

    def _atribuir_ids(self, raiz: HTMLNode) -> None:
        """Pré-passe: id final de cada nó (documento em ordem)."""
        todos = [raiz, *raiz.descendentes()]
        for no in todos:
            explicito = _normalizar(no.atributos.get("id", ""))
            if explicito:
                base = explicito
            else:
                base = self._caminho(no)
            final = base
            if final in self._usados:
                self._contagem_ids[base] = self._contagem_ids.get(base, 1) + 1
                final = f"{base}__{self._contagem_ids[base]}"
                self.avisos.append(
                    {"codigo": "id_duplicado",
                     "motivo": f'ID "{base}" repetido; "{final}" usado '
                               "(namespace determinístico)."})
            self._usados.add(final)
            self._no_por_ordem[no.ordem] = final

    @staticmethod
    def _caminho(no: HTMLNode) -> str:
        """`html.body.main.button[0]` a partir da raiz."""
        partes: list[str] = []
        atual: HTMLNode | None = no
        cadeia: list[HTMLNode] = []
        while atual is not None:
            cadeia.append(atual)
            atual = atual.parent
        for item in reversed(cadeia):
            irmaos = ([c for c in item.parent.children
                       if c.tag == item.tag]
                      if item.parent is not None else [item])
            if len(irmaos) > 1:
                indice = irmaos.index(item)
                partes.append(f"{item.tag}[{indice}]")
            else:
                partes.append(item.tag)
        return ".".join(partes)

    # -- conversão --

    def _converter_subarvore(self, no: HTMLNode, env: Environment,
                             pai_id: str | None,
                             regiao_pai: str | None) -> str:
        nid = self._no_por_ordem[no.ordem]
        tipo, interativo, acoes, eh_regiao, refinado = self._classificar(no)
        nome = _derivar_nome(no, nid)
        geo = self._geometria_para(nid)
        habilitado = not ("disabled" in no.atributos
                          or no.atributos.get("aria-disabled") == "true")
        visivel = not (no.atributos.get("aria-hidden") == "true"
                       or "hidden" in no.atributos
                       or (no.tag == "input"
                           and no.atributos.get("type", "").lower()
                           == "hidden"))
        texto = no.texto_completo() or None if no.tag in TAGS_TEXTO else None
        if no.tag in ("script", "style"):
            texto = None
        atributos = _atributos_env(no, tipo)
        env_no = EnvironmentNode(
            nid, nome=nome, tipo=tipo,
            x=geo[0], y=geo[1], largura=geo[2], altura=geo[3],
            visivel=visivel, habilitado=habilitado,
            interativo=interativo, texto=texto,
            role=no.atributos.get("role") or None,
            atributos=atributos)
        if pai_id is not None:
            env.obter_no(pai_id).adicionar_filho(env_no)
        env.adicionar_no(env_no)
        regiao_atual = regiao_pai
        if eh_regiao:
            rid = f"reg_{nid}"
            membros = [nid] + [self._no_por_ordem[d.ordem]
                               for d in no.descendentes()]
            env.adicionar_regiao(EnvironmentRegion(
                rid, nome=no.atributos.get("role") or no.tag,
                nos=membros,
                sub_regioes=[],
                pai=regiao_pai))
            if regiao_pai is not None:
                env._regioes[regiao_pai].sub_regioes.append(rid)
            regiao_atual = rid
        for acao in acoes:
            # Descritores sempre criados (descrição); o executor da F19
            # recusa alvos desabilitados com `alvo_deshabilitado`.
            params = {"texto": "texto"} if acao == "escrever" else {}
            env.adicionar_interacao(InteractionDescriptor(
                f"{nid}_{acao}", tipo=acao, alvo=nid,
                parametros_permitidos=params))
        for filho in no.children:
            if filho.tag in ("script", "style"):
                self._converter_fantasma(filho, env, nid, regiao_atual)
            elif env_no._profundidade() >= MAX_PROFUNDIDADE:
                self._converter_nivelado(filho, env, env_no, regiao_atual)
            else:
                self._converter_subarvore(filho, env, nid, regiao_atual)
        return nid

    def _converter_fantasma(self, no: HTMLNode, env: Environment,
                            pai_id: str, regiao: str | None) -> None:
        """script/style: nó presente (conteúdo ignorado), sem recursão."""
        nid = self._no_por_ordem[no.ordem]
        env_no = EnvironmentNode(nid, nome=no.tag, tipo=no.tag,
                                 atributos={"tag": no.tag,
                                            "conteudo": "ignorado"})
        env.obter_no(pai_id).adicionar_filho(env_no)
        env.adicionar_no(env_no)

    def _converter_nivelado(self, no: HTMLNode, env: Environment,
                            ancestral, regiao: str | None) -> None:
        """Achata além do teto: cada nó vira filho do ancestral."""
        self.avisos.append({"codigo": "profundidade_truncada",
                            "motivo": f'Subárvore de "{no.tag}" além de '
                                      f"{MAX_PROFUNDIDADE} níveis; "
                                      "convertida de forma nivelada."})
        for filho in [no, *no.descendentes()]:
            nid = self._no_por_ordem[filho.ordem]
            tipo, interativo, acoes, eh_regiao, _ = self._classificar(filho)
            env_no = EnvironmentNode(
                nid, nome=_derivar_nome(filho, nid), tipo=tipo,
                interativo=interativo,
                texto=(filho.texto_completo() or None
                       if filho.tag in TAGS_TEXTO else None),
                atributos=_atributos_env(filho, tipo))
            ancestral.adicionar_filho(env_no)
            env.adicionar_no(env_no)
            for acao in acoes:
                env.adicionar_interacao(InteractionDescriptor(
                    f"{nid}_{acao}", tipo=acao, alvo=nid))

    # -- classificação (regras explícitas) --

    def _classificar(self, no: HTMLNode) -> tuple:
        """(tipo, interativo, ações, é_região, {flags}).

        Precedência: tag semântica (button/input/a/...) vence; `role`
        ARIA vence em contêineres genéricos (div/span); tag desconhecida
        consulta ARIA e, sem regra, vira `elemento`.
        """
        tag = no.tag
        if tag in ("script", "style"):
            return tag, False, [], False, {}
        role = _normalizar(no.atributos.get("role", "")).lower()
        if role in REGRAS_ARIA and (tag in ("div", "span")
                                    or tag not in MAPEAMENTO_TAGS):
            tipo, inter, acoes, reg = REGRAS_ARIA[role]
            return tipo, inter, list(acoes), reg, {"via_aria": True}
        if tag in MAPEAMENTO_TAGS:
            tipo, inter, acoes, reg = MAPEAMENTO_TAGS[tag]
            if tag == "input":
                return self._classificar_input(no)
            if tag == "span":
                if any(c.tag not in ("br",) for c in no.children
                       if c.tag not in VOID_ELEMENTS) and no.children:
                    return "caixa", False, [], False, {}
                return tipo, inter, list(acoes), reg, {}
            return tipo, inter, list(acoes), reg, {}
        if role in REGRAS_ARIA:
            tipo, inter, acoes, reg = REGRAS_ARIA[role]
            return tipo, inter, list(acoes), reg, {"via_aria": True}
        return "elemento", False, [], False, {}

    @staticmethod
    def _classificar_input(no: HTMLNode) -> tuple:
        tipo_html = _normalizar(no.atributos.get("type", "")).lower()
        if tipo_html == "checkbox":
            return "selecao", True, ["focar", "marcar", "desmarcar"], \
                False, {"input": "checkbox"}
        if tipo_html == "radio":
            return "selecao", True, ["focar", "selecionar"], False, \
                {"input": "radio"}
        if tipo_html in ("submit", "button", "image"):
            return "botao", True, ["clicar", "focar"], False, \
                {"input": tipo_html}
        if tipo_html in TIPOS_INPUT_TEXTO:
            acoes = ["focar", "escrever"]
            if "readonly" not in no.atributos:
                acoes.append("limpar")
            return "entrada", True, acoes, False, {"input": tipo_html or
                                                   "text"}
        return "entrada", True, ["focar"], False, {"input": tipo_html}

    # -- geometria (só do mapa; nunca inventada) --

    def _geometria_para(self, nid: str) -> tuple:
        bruto = self.geometria.get(nid)
        if bruto is None:
            return (0.0, 0.0, 0.0, 0.0)
        if not isinstance(bruto, dict):
            self.avisos.append({"codigo": "geometria_invalida",
                                "motivo": f'Geometria de "{nid}" não é '
                                          "dicionário; ignorada."})
            return (0.0, 0.0, 0.0, 0.0)
        try:
            x = _numero(bruto.get("x", 0.0), f"x de {nid}")
            y = _numero(bruto.get("y", 0.0), f"y de {nid}")
            larg = _numero(bruto.get("largura", 0.0), f"largura de {nid}")
            alt = _numero(bruto.get("altura", 0.0), f"altura de {nid}")
        except ErroELiXX as exc:
            self.avisos.append({"codigo": "geometria_invalida",
                                "motivo": f'Geometria de "{nid}" ignorada: '
                                          f"{exc}"})
            return (0.0, 0.0, 0.0, 0.0)
        if larg < 0 or alt < 0:
            self.avisos.append({"codigo": "geometria_invalida",
                                "motivo": f'Geometria de "{nid}" com '
                                          "tamanho negativo; ignorada."})
            return (0.0, 0.0, 0.0, 0.0)
        return (x, y, larg, alt)

    def _aplicar_geometria(self, env: Environment) -> None:
        for nid in sorted(self.geometria):
            if nid not in env:
                self.avisos.append({"codigo": "geometria_orfa",
                                    "motivo": f'Geometria para "{nid}" sem '
                                              "nó correspondente; ignorada."})
                continue
            bruto = self.geometria[nid]
            if not isinstance(bruto, dict):
                continue
            if bruto.get("superficie") is True:
                no = env.obter_no(nid)
                if not no.tem_geometria():
                    self.avisos.append(
                        {"codigo": "superficie_sem_geometria",
                         "motivo": f'Superfície de "{nid}" pedida sem '
                                   "geometria; ignorada."})
                    continue
                caps = [str(c) for c in (bruto.get("capacidades") or [])
                        if str(c).strip()]
                orient = str(bruto.get("orientacao", "horizontal"))
                env.adicionar_superficie(EnvironmentSurface(
                    f"sup_{nid}", owner=nid, x=no.x, y=no.y,
                    largura=no.largura, altura=no.altura,
                    orientacao=orient, tipo=orient,
                    capacidades=caps,
                    bloqueada=bool(bruto.get("bloqueada", False))))
        for nid in sorted(env._nos):
            if nid not in self.geometria:
                continue  # nós sem entrada: 0,0,0,0 (estrutural, válido)


def _titulo(raiz: HTMLNode) -> str:
    for d in [raiz, *raiz.descendentes()]:
        if d.tag == "title":
            texto = d.texto_completo()
            if texto:
                return texto[:MAX_TEXTO_NOME]
    return ""


def _derivar_nome(no: HTMLNode, nid: str) -> str:
    rotulo = _normalizar(no.atributos.get("aria-label", ""))
    if rotulo:
        return rotulo[:MAX_TEXTO_NOME]
    if no.tag in TAGS_TEXTO:
        cheio = no.texto_completo()
        if cheio:
            return cheio[:MAX_TEXTO_NOME]
    for chave in ("name", "alt", "title", "placeholder", "value"):
        valor = _normalizar(no.atributos.get(chave, ""))
        if valor:
            return valor[:MAX_TEXTO_NOME]
    explicito = _normalizar(no.atributos.get("id", ""))
    if explicito:
        return explicito
    return nid


def _atributos_env(no: HTMLNode, tipo: str) -> dict:
    """Metadados seguros: tag + classes + atributos úteis (inertes)."""
    attrs: dict = {"tag": no.tag, "tipo_html": tipo}
    classes = _normalizar(no.atributos.get("class", "")).split()
    if classes:
        attrs["classes"] = classes
    for chave in ("name", "type", "value", "placeholder", "title",
                  "alt", "href", "action", "formaction", "src", "method",
                  "role", "aria-label", "aria-labelledby",
                  "aria-describedby", "required", "checked", "selected",
                  "readonly"):
        if chave in no.atributos:
            attrs[chave] = no.atributos[chave]
    for chave, valor in sorted(no.atributos.items()):
        if chave.startswith("data-"):
            attrs[chave] = valor
    href = attrs.get("href", "")
    if isinstance(href, str) and href.lower().lstrip().startswith(
            ("javascript:", "data:")):
        attrs["url_inerte"] = True  # string preservada; nunca aberta
    return attrs


def _numero(valor, o_que: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroELiXX(f'"{o_que}" precisa de número '
                        f"(recebido {type(valor).__name__}).")
    if not math.isfinite(numero):
        raise ErroELiXX(f'"{o_que}" precisa de número finito '
                        "(recebido NaN ou infinito).")
    return numero


# ---------------------------------------------------------------------------
# Conveniências
# ---------------------------------------------------------------------------

def html_para_environment(html: str, geometria: dict | None = None,
                          env_id: str = "pagina",
                          nome: str = "") -> tuple:
    """Alias direto: HTML → (Environment, avisos)."""
    return HTMLAdapter.parsear(html, geometria=geometria, env_id=env_id,
                               nome=nome)


def debug_html(doc_ou_env) -> str:
    """Árvore textual HTML (diagnóstico puro, determinístico)."""
    if isinstance(doc_ou_env, HTMLDocument):
        raiz = doc_ou_env.raiz
        linhas = [f"HTMLDocument: {doc_ou_env.total_nos} nós, "
                   f"{len(doc_ou_env.avisos)} avisos"]
        for no in [raiz, *raiz.descendentes()]:
            linhas.append(f"  {'  ' * min(no.profundidade, 8)}"
                           f"<{no.tag}> id={no.atributos.get('id', '—')} "
                           f"ordem={no.ordem}")
        for aviso in doc_ou_env.avisos:
            linhas.append(f"  AVISO {aviso['codigo']}: {aviso['motivo']}")
        return "\n".join(linhas)
    from .ambiente import debug_ambiente as _dbg
    return _dbg(doc_ou_env)
