"""Parser da ELiXX: transforma tokens em AST.

Gramática mínima da Fase 01 (documentada em docs/sintaxe.md):

    programa    := (janela | funcao)*
    janela      := 'janela' NOME '{' (propriedade | componente | evento)* '}'
    componente  := TIPO NOME '{' (propriedade | evento | componente)* '}'
    propriedade := NOME ':' valor+
    evento      := 'quando' NOME_EVENTO '{' comando* '}'
    comando     := acao | se | repetir | retornar
    acao        := NOME '(' args? ')' | NOME
    funcao      := ('função' | 'funcao') NOME '(' params? ')' '{' comando* '}'

O parser NÃO valida nomes de eventos/ações (para que novos eventos e ações
possam surgir sem modificar o parser). Essa validação é da semântica.
"""
from __future__ import annotations

from . import ast as A
from ..cores import CORES_NOMEADAS, eh_hex
from ..erros import ErroSintatico
from .lexer import EOF, IDENT, NUMERO, PALAVRA, SINAL, STRING, UNIDADE, Token

TIPOS_COMPONENTE = {
    "botão": "botao", "botao": "botao",
    "texto": "texto",
    "imagem": "imagem",
    "vídeo": "video", "video": "video",
    "áudio": "audio", "audio": "audio",
    "painel": "painel",
    "cartao": "cartao", "cartão": "cartao",
    "barra": "barra",
    "grafico": "grafico", "gráfico": "grafico",
    "lista": "lista",
    "linha": "linha", "coluna": "coluna", "grade": "grade",
    "pilha": "pilha", "entrada": "entrada", "checkbox": "checkbox",
    "selecao": "selecao", "seleção": "selecao",
    "separador": "separador", "indicador": "indicador",
    "icone": "icone", "ícone": "icone",
    "formulario": "formulario", "aba": "aba", "abas": "abas",
    "menu": "menu", "tabela": "tabela", "modal": "modal",
    "conteudo": "conteudo", "conteúdo": "conteudo",
}

# Fase 10: contêineres do Visual Core (grupo/objeto). NÃO são palavras
# reservadas no lexer de propósito: "grupo x {" / "objeto x {" são
# reconhecidos por lookahead aqui (dois nomes + "{"). Assim nomes como
# `imagem objeto {` (objeto como NOME) continuam válidos — parse_nome
# rejeitaria palavra reservada. Built-in vence se houver colisão com
# componente do usuário (documentado).
TIPOS_CONTENEIR_10 = {"grupo": "grupo", "objeto": "objeto"}

# Fase 10: blocos de transformação (`posição { x: 1 y: 2 }`). Viram uma
# Propriedade equivalente à forma de uma linha (`posição: 1 2`) — sem
# nova AST, sem segundo caminho no runtime/semântica.
BLOCOS_TRANSFORM_10 = {"posicao", "pivo", "escala"}


def _sem_acentos_10(texto: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in base if not unicodedata.combining(c))

PRECEDENCIA = {"ou": 1, "e": 2, "==": 3, "!=": 3, ">": 4, "<": 4,
               ">=": 4, "<=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        # Fase 09: contexto p/ validar local./item./param. no parse.
        self._em_def = 0
        self._em_modelo = 0
        self._em_lista = 0
    def _checar_contexto(self, nome: str, tok) -> None:
        """local./item./param. fora do escopo → erro imediato em PT."""
        if nome == "local" and not (self._em_def or self._em_modelo):
            raise self.erro(
                '"local" só existe dentro de componente com estado '
                "ou item de lista.",
                exemplo='origem: local.favorito',
                tok=tok,
            )
        if nome == "item" and not (self._em_modelo or self._em_lista
                                     or self._em_def):
            raise self.erro(
                '"item" só existe dentro de lista (modelo ou chave) '
                "ou componente usado em lista.",
                exemplo='texto: item.nome',
                tok=tok,
            )
        if nome == "param" and not self._em_def:
            raise self.erro(
                '"param" só existe dentro de componente.',
                exemplo='texto: param.titulo',
                tok=tok,
            )

    # ----- navegação -----

    def atual(self) -> Token:
        return self.tokens[self.pos]

    def ver(self, desloc: int = 1) -> Token:
        idx = self.pos + desloc
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def avancar(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def eh_palavra(self, *nomes: str) -> bool:
        t = self.atual()
        return t.tipo == PALAVRA and t.valor in nomes

    def eh_sinal(self, *sinais: str) -> bool:
        t = self.atual()
        return t.tipo == SINAL and t.valor in sinais

    # ----- erros -----

    def erro(self, mensagem: str, exemplo: str | None = None,
             tok: Token | None = None) -> ErroSintatico:
        tok = tok or self.atual()
        if tok.tipo == EOF:
            detalhe = "fim do arquivo"
        else:
            detalhe = f"{tok.valor!r}"
        return ErroSintatico(
            f"{mensagem} Encontrado {detalhe}.",
            linha=tok.linha, coluna=tok.coluna,
            trecho=str(tok.valor), exemplo=exemplo,
        )

    # ----- entrada -----

    def parse(self, exigir_janela: bool = True) -> A.Programa:
        programa = A.Programa()
        while self.atual().tipo != EOF:
            if self.eh_palavra("janela"):
                programa.janelas.append(self.parse_janela())
            elif self.eh_palavra("função", "funcao"):
                programa.funcoes.append(self.parse_funcao())
            elif self.eh_palavra("estado"):
                if programa.estado is not None:
                    tok = self.atual()
                    raise ErroSintatico(
                        "Só um bloco estado por programa. Junte as "
                        "variáveis num único bloco estado { ... }.",
                        linha=tok.linha, coluna=tok.coluna,
                        exemplo='estado {\n    contador: 0\n}',
                    )
                programa.estado = self.parse_estado()
            elif self.eh_palavra("dados"):
                programa.fontes.append(self.parse_fonte())
            elif self.eh_palavra("tema"):
                programa.temas.append(self.parse_tema())
            elif self.eh_palavra("tela"):
                programa.telas.append(self.parse_janela(
                    palavra="tela", eh_tela=True))
            elif self.eh_palavra("componente"):
                programa.componentes.append(self.parse_componente_def())
            elif self.eh_palavra("acao"):
                programa.acoes.append(self.parse_acao_def())
            elif self.eh_palavra("importar"):
                programa.imports.append(self.parse_import())
            else:
                raise self.erro(
                    'Era esperado "janela", "tela", "função", "estado", '
                    '"dados", "tema", "componente", "acao" ou "importar" '
                    'no início de um bloco.',
                    exemplo='janela principal {\n    titulo: "Minha aplicação"\n}',
                )
        if exigir_janela and not programa.janelas and not programa.telas:
            primeiro = self.tokens[0]
            raise ErroSintatico(
                "O programa não possui nenhuma janela nem tela. Todo "
                "programa ELiXX precisa de pelo menos uma janela ou tela.",
                linha=primeiro.linha, coluna=primeiro.coluna,
                exemplo='janela principal {\n    titulo: "Minha aplicação"\n}',
            )
        return programa

    # ----- janela e componentes -----

    def parse_nome(self, o_que: str, exemplo: str) -> Token:
        tok = self.atual()
        if tok.tipo == IDENT:
            return self.avancar()
        if tok.tipo == PALAVRA:
            raise self.erro(
                f"O nome {o_que} não pode ser a palavra reservada {tok.valor!r}. "
                "Escolha outro nome.",
                exemplo=exemplo,
            )
        raise self.erro(
            f"Era esperado o nome {o_que}.",
            exemplo=exemplo,
        )

    def _comeca_propriedade(self) -> bool:
        t = self.atual()
        return (t.tipo in (IDENT, PALAVRA) and self.ver().tipo == SINAL
                and self.ver().valor == ":")

    def parse_janela(self, palavra: str = "janela",
                     eh_tela: bool = False) -> A.Janela:
        tok_janela = self.avancar()  # 'janela' ou 'tela'
        exemplo = (f'{palavra} principal {{\n'
                   f'    titulo: "Minha aplicação"\n}}')
        nome = self.parse_nome("da janela" if not eh_tela else "da tela",
                               exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        janela = A.Janela(nome=str(nome.valor), linha=tok_janela.linha,
                          eh_tela=eh_tela)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A {"tela" if eh_tela else "janela"} não foi fechada '
                    'com "}".',
                    exemplo=exemplo,
                )
            if self.eh_palavra("quando"):
                janela.eventos.append(self.parse_evento())
            elif self.eh_palavra("animação", "animacao"):
                janela.animacoes.append(self.parse_animacao())
            elif self._comeca_propriedade():
                # propriedade ANTES de componente: "texto: ..." é
                # propriedade, "texto nome {" é componente.
                janela.propriedades.append(self.parse_propriedade())
            elif self._comeca_bloco_transform():
                janela.propriedades.append(self.parse_bloco_transform())
            elif self._comeca_mundo():
                janela.mundos.append(self.parse_mundo())
            elif self._comeca_navegacao():
                janela.navegacoes.append(self.parse_navegacao())
            elif self._comeca_item():
                janela.itens.append(self.parse_item())
            elif self._comeca_personagem():
                janela.componentes.append(self.parse_personagem())
            elif self.eh_palavra(*TIPOS_COMPONENTE):
                janela.componentes.append(self.parse_componente())
            elif self._comeca_grupo_objeto():
                janela.componentes.append(self.parse_grupo_objeto())
            elif self._comeca_instancia():
                janela.componentes.append(self.parse_instancia())
            else:
                raise self.erro(
                    "Dentro da janela era esperado propriedade (nome: valor), "
                    "componente (botão, texto, imagem...) ou evento (quando ...).",
                    exemplo='janela principal {\n    titulo: "Oi"\n\n'
                            '    botão ok {\n        texto: "OK"\n    }\n}',
                )
        self.avancar()  # '}'
        return janela

    def _comeca_instancia(self) -> bool:
        """`Nome inst {` onde Nome não é tipo conhecido (Fase 08)."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        # Fase 10/12/14: construções próprias (não instâncias).
        if (t.tipo in (IDENT, PALAVRA)
                and _sem_acentos_10(t.valor) in TIPOS_CONTENEIR_10):
            return False
        if _sem_acentos_10(t.valor) in ("personagem", "parte", "pose",
                                        "expressao", "expressão", "item",
                                        "capacidade", "mundo", "navegacao",
                                        "navegação", "caminho"):
            return False
        segundo = self.ver()
        terceiro = self.ver(2)
        return (segundo.tipo in (IDENT, PALAVRA)
                and terceiro.tipo == SINAL and terceiro.valor == "{")

    def _comeca_grupo_objeto(self) -> bool:
        """Fase 10: `grupo nome {` / `objeto nome {` (contêiner visual)."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(t.valor) not in TIPOS_CONTENEIR_10:
            return False
        segundo = self.ver()
        terceiro = self.ver(2)
        return (segundo.tipo in (IDENT, PALAVRA)
                and terceiro.tipo == SINAL and terceiro.valor == "{")

    # ----- Fase 12: personagem/parte/pose (lookahead; sem reservar) -----

    def _comeca_personagem(self) -> bool:
        return self._comeca_bloco_nomeado(("personagem",))

    def _comeca_parte(self) -> bool:
        return self._comeca_bloco_nomeado(("parte",))

    def _comeca_pose(self) -> bool:
        return self._comeca_bloco_nomeado(("pose", "expressao", "expressão"))

    def _comeca_bloco_nomeado(self, nomes: tuple) -> bool:
        """`palavra Nome {` onde palavra ∈ nomes (não reservada no lexer)."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(t.valor) not in nomes:
            return False
        segundo = self.ver()
        terceiro = self.ver(2)
        return (segundo.tipo in (IDENT, PALAVRA)
                and terceiro.tipo == SINAL and terceiro.valor == "{")

    def _parse_nome_livre(self, o_que: str, exemplo: str) -> Token:
        """Nome de personagem/parte/pose: IDENT ou PALAVRA (ex. `corpo`).

        Sem ambiguidade: aqui já se espera nome + `{` (ou `:` em pose),
        então palavra reservada como nome é segura e natural (`corpo`,
        `cabeça`). Diferente de parse_nome (componentes visuais).
        """
        tok = self.atual()
        if tok.tipo not in (IDENT, PALAVRA):
            raise self.erro(
                f"Era esperado o nome {o_que}.",
                exemplo=exemplo,
            )
        return self.avancar()

    def parse_personagem(self) -> A.Personagem:
        """`personagem Nome { props parte* pose* visuais* }` (Fase 12)."""
        from . import ast as _A

        tok = self.avancar()  # 'personagem'
        exemplo = ('personagem Heroi {\n    parte corpo {\n'
                   '        imagem: "corpo.png"\n    }\n'
                   '    pose repouso {\n        corpo:\n'
                   '            rotação: 0deg\n    }\n}')
        nome = self._parse_nome_livre("do personagem", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        boneco = _A.Personagem(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O personagem {nome.valor!r} não foi fechado com "}}".',
                    exemplo=exemplo,
                )
            if self._comeca_parte():
                boneco.partes.append(self.parse_parte())
            elif self._comeca_pose():
                boneco.poses.append(self.parse_pose())
            elif self._comeca_capacidade():
                boneco.capacidades.append(self.parse_capacidade())
            elif self._comeca_propriedade():
                boneco.propriedades.append(self.parse_propriedade())
            elif self._comeca_bloco_transform():
                boneco.propriedades.append(self.parse_bloco_transform())
            elif self.eh_palavra(*TIPOS_COMPONENTE):
                boneco.filhos.append(self.parse_componente())
            elif self._comeca_grupo_objeto():
                boneco.filhos.append(self.parse_grupo_objeto())
            elif self._comeca_instancia():
                boneco.filhos.append(self.parse_instancia())
            else:
                raise self.erro(
                    "No personagem era esperado propriedade, parte, pose, "
                    "expressão ou componente visual.",
                    exemplo=exemplo,
                )
        self.avancar()  # '}'
        return boneco

    def parse_parte(self) -> A.Parte:
        """`parte nome { props subparte* visuais* }` (recursiva)."""
        from . import ast as _A

        tok = self.avancar()  # 'parte'
        exemplo = ('parte braco {\n    imagem: "braco.png"\n'
                   '    pivo: 10px 20px\n}')
        nome = self._parse_nome_livre("da parte", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        parte = _A.Parte(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A parte {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo,
                )
            if self._comeca_parte():
                parte.partes.append(self.parse_parte())
            elif self._comeca_capacidade():
                parte.capacidades.append(self.parse_capacidade())
            elif self._comeca_propriedade():
                parte.propriedades.append(self.parse_propriedade())
            elif self._comeca_bloco_transform():
                parte.propriedades.append(self.parse_bloco_transform())
            elif self.eh_palavra(*TIPOS_COMPONENTE):
                parte.filhos.append(self.parse_componente())
            elif self._comeca_grupo_objeto():
                parte.filhos.append(self.parse_grupo_objeto())
            elif self._comeca_instancia():
                parte.filhos.append(self.parse_instancia())
            else:
                raise self.erro(
                    "Na parte era esperado propriedade, subparte ou "
                    "componente visual.",
                    exemplo=exemplo,
                )
        self.avancar()  # '}'
        return parte

    def _e_cabecalho_pose(self) -> bool:
        """`Nome:` sem valor na mesma linha = nova entrada de pose."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if not (self.ver().tipo == SINAL and self.ver().valor == ":"):
            return False
        depois = self.ver(2)
        return (depois.tipo == EOF or depois.linha != t.linha
                or (depois.tipo == SINAL and depois.valor == "}"))

    def parse_pose(self) -> A.PoseDef:
        """`pose nome { parte: (props...) }` / `expressao` (parcial)."""
        from . import ast as _A

        tok = self.avancar()  # 'pose' ou 'expressao'
        expressao = _sem_acentos_10(tok.valor) == "expressao"
        exemplo = ('pose acenando {\n    braco:\n'
                   '        rotação: 45deg\n}')
        nome = self._parse_nome_livre("da pose", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        pose = _A.PoseDef(nome=str(nome.valor), expressao=expressao,
                          linha=tok.linha)
        if self.eh_sinal("}"):
            raise self.erro(
                f'A pose {nome.valor!r} está vazia.',
                exemplo=exemplo)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A pose {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo,
                )
            if not self._e_cabecalho_pose():
                raise self.erro(
                    f'Na pose {nome.valor!r} era esperado "parte:" '
                    "(nome da parte seguido de dois-pontos).",
                    exemplo=exemplo,
                )
            tok_parte = self.avancar()
            self.avancar()  # ':'
            entrada = _A.PoseEntrada(parte=str(tok_parte.valor),
                                     linha=tok_parte.linha)
            while not self.eh_sinal("}") and not self._e_cabecalho_pose():
                if self.atual().tipo == EOF:
                    raise self.erro(
                        f'A pose {nome.valor!r} não foi fechada com "}}".',
                        exemplo=exemplo,
                    )
                if not self._comeca_propriedade():
                    raise self.erro(
                        f'Na parte {tok_parte.valor!r} da pose '
                        f'{nome.valor!r} era esperado propriedade '
                        "(posição, rotação, escala, opacidade, pivô).",
                        exemplo=exemplo,
                    )
                entrada.propriedades.append(self.parse_propriedade())
            if not entrada.propriedades:
                raise self.erro(
                    f'A parte {tok_parte.valor!r} da pose {nome.valor!r} '
                    "está vazia.",
                    exemplo=exemplo,
                )
            pose.entradas.append(entrada)
        self.avancar()  # '}'
        return pose

    def _comeca_bloco_transform(self) -> bool:
        """Fase 10: `posição {`, `pivô {`, `escala {` (sem dois-pontos)."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(t.valor) not in BLOCOS_TRANSFORM_10:
            return False
        return self.ver().tipo == SINAL and self.ver().valor == "{"

    def parse_bloco_transform(self) -> A.Propriedade:
        """Bloco `posição/pivô/escala { x: .. y: .. }` → Propriedade.

        Equivale à forma de uma linha. `escala { x: v }` sozinho usa
        y = x (uniforme). Erros em português com a linha do bloco.
        """
        tok = self.avancar()
        base = _sem_acentos_10(tok.valor)
        self.avancar()  # '{'
        vals: dict[str, object] = {}
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O bloco "{tok.valor}" não foi fechado com "}}".',
                    exemplo=f"{tok.valor} {{\n    x: 100\n    y: 200\n}}",
                )
            if not self._comeca_propriedade():
                raise self.erro(
                    f'Dentro de "{tok.valor}" era esperado "x:" ou "y:".',
                    exemplo=f"{tok.valor} {{\n    x: 100\n    y: 200\n}}",
                )
            prop = self.parse_propriedade()
            eixo = _sem_acentos_10(prop.nome)
            if eixo not in ("x", "y"):
                raise self.erro(
                    f'No bloco "{tok.valor}" só existem "x" e "y" '
                    f"(recebido {prop.nome!r}).",
                    exemplo=f"{tok.valor} {{\n    x: 100\n    y: 200\n}}",
                )
            if eixo in vals:
                raise self.erro(
                    f'"{eixo}" repetido no bloco "{tok.valor}".',
                    exemplo=f"{tok.valor} {{\n    x: 100\n    y: 200\n}}",
                )
            if len(prop.valores) != 1:
                raise self.erro(
                    f'"{eixo}" espera um único valor '
                    f"(recebido {len(prop.valores)}).",
                    exemplo=f"{tok.valor} {{\n    x: 100\n    y: 200\n}}",
                )
            vals[eixo] = prop.valores[0]
        self.avancar()  # '}'
        if base == "escala":
            if "x" not in vals:
                raise self.erro(
                    'O bloco "escala" precisa ao menos de "x".',
                    exemplo="escala {\n    x: 1.2\n    y: 0.8\n}",
                )
            vals.setdefault("y", vals["x"])
        elif "x" not in vals or "y" not in vals:
            raise self.erro(
                f'O bloco "{tok.valor}" precisa de "x" e "y".',
                exemplo=f"{tok.valor} {{\n    x: 100\n    y: 200\n}}",
            )
        return A.Propriedade(nome=str(tok.valor),
                             valores=[vals["x"], vals["y"]],
                             linha=tok.linha)

    def parse_instancia(self) -> A.Instancia:
        """Uso de componente reutilizável (expandido depois do parse)."""
        tok_tipo = self.avancar()
        tipo_nome = str(tok_tipo.valor)
        tok_nome = self.atual()
        if tok_nome.tipo not in (IDENT, PALAVRA):
            raise self.erro("Era esperado o nome da instância.",
                            exemplo=f"{tipo_nome} meu_bloco {{ ... }}")
        nome = str(self.avancar().valor)
        self.avancar()  # '{'
        inst = A.Instancia(tipo_nome=tipo_nome, nome=nome,
                           linha=tok_tipo.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A instância {nome!r} não foi fechada com "}}".')
            if self.eh_palavra("quando"):
                inst.eventos.append(self.parse_evento())
            elif self._comeca_propriedade():
                inst.propriedades.append(self.parse_propriedade())
            elif self._comeca_bloco_transform():
                inst.propriedades.append(self.parse_bloco_transform())
            elif self.eh_palavra(*TIPOS_COMPONENTE):
                inst.filhos.append(self.parse_componente())
            elif self._comeca_grupo_objeto():
                inst.filhos.append(self.parse_grupo_objeto())
            elif self._comeca_personagem():
                inst.filhos.append(self.parse_personagem())
            elif self._comeca_instancia():
                inst.filhos.append(self.parse_instancia())
            else:
                raise self.erro(
                    "Na instância era esperado propriedade, evento ou "
                    "componente filho.",
                    exemplo=f"{tipo_nome} {nome} {{\n    texto: \"Oi\"\n}}")
        self.avancar()  # '}'
        return inst

    def parse_componente(self, tipo_forcado: str | None = None) -> A.Componente:
        if tipo_forcado is None:
            tok_tipo = self.avancar()
            tipo = TIPOS_COMPONENTE[str(tok_tipo.valor)]
        else:
            # Fase 10: grupo/objeto (lookahead já validado pelo chamador).
            tok_tipo = self.avancar()
            tipo = tipo_forcado
        exemplo = (f'{tok_tipo.valor} meu_{tipo} {{\n'
                   f'    texto: "Exemplo"\n}}')
        if tipo == "conteudo":
            # marcador de slot: `conteudo { }` ou `conteudo` sozinho.
            if self.eh_sinal("{"):
                self.avancar()
                if not self.eh_sinal("}"):
                    raise self.erro(
                        'O marcador "conteudo" é vazio (só marca o lugar).',
                        exemplo="conteudo")
                self.avancar()
            return A.Componente(tipo=tipo, nome="", linha=tok_tipo.linha)
        else:
            nome = self.parse_nome("do componente", exemplo)
            if not self.eh_sinal("{"):
                raise self.erro(
                    f'Era esperado "{{" depois do nome do componente {nome.valor!r}.',
                    exemplo=exemplo,
                )
            nome = str(nome.valor)
        self.avancar()
        comp = A.Componente(tipo=tipo, nome=nome, linha=tok_tipo.linha)
        if tipo == "lista":
            self._em_lista += 1
        try:
            while not self.eh_sinal("}"):
                if self.atual().tipo == EOF:
                    raise self.erro(
                        f'O componente {nome!r} não foi fechado com "}}".',
                        exemplo=exemplo,
                    )
                if self.eh_palavra("quando"):
                    comp.eventos.append(self.parse_evento())
                elif self._comeca_propriedade():
                    comp.propriedades.append(self.parse_propriedade())
                elif self._comeca_bloco_transform():
                    # Fase 10: posição/pivô/escala em bloco viram propriedade.
                    comp.propriedades.append(self.parse_bloco_transform())
                elif self._comeca_grupo_objeto():
                    comp.filhos.append(self.parse_grupo_objeto())
                elif (self.atual().tipo == IDENT
                        and str(self.atual().valor) == "modelo"
                        and self.ver().tipo == SINAL
                        and self.ver().valor == "{"):
                    # Fase 09: template de lista (só lista usa; semântica checa).
                    self.avancar()  # 'modelo'
                    self.avancar()  # '{'
                    self._em_modelo += 1
                    try:
                        while not self.eh_sinal("}"):
                            if self.atual().tipo == EOF:
                                raise self.erro(
                                    'O modelo não foi fechado com "}".')
                            if self.eh_palavra(*TIPOS_COMPONENTE):
                                comp.modelo.append(self.parse_componente())
                            elif self._comeca_grupo_objeto():
                                comp.modelo.append(self.parse_grupo_objeto())
                            elif self._comeca_instancia():
                                comp.modelo.append(self.parse_instancia())
                            else:
                                raise self.erro(
                                    "No modelo era esperado um componente.",
                                    exemplo='modelo {\n    texto nome {\n'
                                            '        texto: item.nome\n    }\n}',
                                )
                    finally:
                        self._em_modelo -= 1
                    self.avancar()  # '}'
                elif self.eh_palavra(*TIPOS_COMPONENTE):
                    comp.filhos.append(self.parse_componente())
                elif self._comeca_grupo_objeto():
                    comp.filhos.append(self.parse_grupo_objeto())
                elif self._comeca_personagem():
                    comp.filhos.append(self.parse_personagem())
                elif self._comeca_instancia():
                    comp.filhos.append(self.parse_instancia())
                else:
                    raise self.erro(
                        "Dentro do componente era esperado propriedade, "
                        "evento ou subcomponente.",
                        exemplo=exemplo,
                    )
        finally:
            if tipo == "lista":
                self._em_lista -= 1
        self.avancar()
        return comp

    # ----- Fase 13: mundo/entidades (lookahead; sem reservar) -----

    TIPOS_ENTIDADE_13 = ("chao", "chão", "parede", "plataforma",
                         "obstaculo", "obstáculo", "objeto", "area", "área",
                         "ponto")

    def _comeca_mundo(self) -> bool:
        return self._comeca_bloco_nomeado(("mundo",))

    # ----- Fase 15: navegacao/caminho (lookahead; sem reservar) -----

    def _comeca_navegacao(self) -> bool:
        return self._comeca_bloco_nomeado(("navegacao", "navegação"))

    def _comeca_caminho(self) -> bool:
        """`caminho Origem -> Destino { ... }` (seta `->` ou `→`)."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(t.valor) != "caminho":
            return False
        return (self.ver().tipo in (IDENT, PALAVRA)
                and self.ver(2).tipo == SINAL
                and self.ver(2).valor in ("->", "→"))

    def parse_navegacao(self) -> A.Navegacao:
        """`navegacao Nome { caminho A -> B { ... } }` (Fase 15)."""
        tok = self.avancar()  # 'navegacao'
        exemplo = ('navegacao Principal {\n    caminho ChaoA -> ChaoB {\n'
                   '        modo: andar\n        custo: 1\n    }\n}')
        nome = self._parse_nome_livre("da navegação", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        nav = A.Navegacao(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A navegação {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo,
                )
            if not self._comeca_caminho():
                raise self.erro(
                    f'Na navegação {nome.valor!r} era esperado '
                    '"caminho Origem -> Destino".',
                    exemplo=exemplo,
                )
            nav.caminhos.append(self.parse_caminho())
        self.avancar()  # '}'
        return nav

    def parse_caminho(self) -> A.CaminhoNav:
        """`caminho A -> B { modo/custo/requer/bloqueado }`."""
        tok = self.avancar()  # 'caminho'
        exemplo = ('caminho ChaoA -> ChaoB {\n    modo: andar\n    custo: 1\n}')
        tok_origem = self.atual()
        if tok_origem.tipo not in (IDENT, PALAVRA):
            raise self.erro("Era esperado o nome da origem.",
                            exemplo=exemplo)
        origem = str(self.avancar().valor)
        self.avancar()  # '->' ou '→'
        tok_destino = self.atual()
        if tok_destino.tipo not in (IDENT, PALAVRA):
            raise self.erro("Era esperado o nome do destino.",
                            exemplo=exemplo)
        destino = str(self.avancar().valor)
        caminho = A.CaminhoNav(origem=origem, destino=destino,
                               linha=tok.linha)
        if not self.eh_sinal("{"):
            return caminho  # forma simples (padrões: andar, custo 1)
        self.avancar()
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O caminho {origem!r} -> {destino!r} não foi fechado '
                    'com "}".',
                    exemplo=exemplo,
                )
            if not self._comeca_propriedade():
                raise self.erro(
                    f'No caminho {origem!r} -> {destino!r} era esperado '
                    "modo, custo, requer ou bloqueado.",
                    exemplo=exemplo,
                )
            caminho.propriedades.append(self.parse_propriedade())
        self.avancar()  # '}'
        return caminho

    # ----- Fase 14: item/capacidade (lookahead; sem reservar) -----

    def _comeca_item(self) -> bool:
        return self._comeca_bloco_nomeado(("item",))

    def _comeca_capacidade(self) -> bool:
        """`capacidade nome` (bloco `{` ou linha simples)."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(t.valor) != "capacidade":
            return False
        return self.ver().tipo in (IDENT, PALAVRA)

    def parse_item(self) -> A.ItemDef:
        """`item Nome { props capacidade* }` (Fase 14, sem visual)."""
        tok = self.avancar()  # 'item'
        exemplo = ('item BotaFoguete {\n    categoria: "equipamento"\n'
                   '    capacidade voar\n}')
        nome = self._parse_nome_livre("do item", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        item = A.ItemDef(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O item {nome.valor!r} não foi fechado com "}}".',
                    exemplo=exemplo,
                )
            if self._comeca_capacidade():
                item.capacidades.append(self.parse_capacidade())
            elif self._comeca_propriedade():
                item.propriedades.append(self.parse_propriedade())
            else:
                raise self.erro(
                    f'No item {nome.valor!r} era esperado propriedade ou '
                    "capacidade.",
                    exemplo=exemplo,
                )
        self.avancar()  # '}'
        return item

    def parse_capacidade(self) -> A.CapacidadeDef:
        """`capacidade nome` ou bloco (descrição, params, requisitos)."""
        from . import ast as _A

        tok = self.avancar()  # 'capacidade'
        exemplo = ('capacidade voar {\n    descricao: "voar"\n'
                   '    requer_equipado: "BotaFoguete"\n}')
        nome = self._parse_nome_livre("da capacidade", exemplo)
        cap = _A.CapacidadeDef(nome=str(nome.valor), linha=tok.linha)
        if not self.eh_sinal("{"):
            return cap  # forma simples de uma linha
        self.avancar()
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A capacidade {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo,
                )
            t = self.atual()
            if (t.tipo in (IDENT, PALAVRA)
                    and _sem_acentos_10(t.valor) == "parametro"
                    and self.ver().tipo in (IDENT, PALAVRA)):
                self.avancar()
                tok_param = self.avancar()
                cap.parametros.append(_A.ParamCap(
                    nome=str(tok_param.valor), linha=tok_param.linha))
            elif self._comeca_propriedade():
                cap.propriedades.append(self.parse_propriedade())
            else:
                raise self.erro(
                    f'Na capacidade {nome.valor!r} era esperado parametro, '
                    "descricao ou requer_*.",
                    exemplo=exemplo,
                )
        self.avancar()  # '}'
        return cap

    def _comeca_entidade(self) -> bool:
        return self._comeca_bloco_nomeado(
            tuple(_sem_acentos_10(t) for t in self.TIPOS_ENTIDADE_13))

    def _comeca_usar(self) -> bool:
        """`usar personagem Nome` / `usar item X [como Y] [{...}]`."""
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(t.valor) != "usar":
            return False
        segundo = self.ver()
        terceiro = self.ver(2)
        if segundo.tipo not in (IDENT, PALAVRA):
            return False
        if _sem_acentos_10(segundo.valor) not in ("personagem", "item"):
            return False
        return terceiro.tipo in (IDENT, PALAVRA)

    def parse_mundo(self) -> A.Mundo:
        """`mundo Nome { tamanho: .. entidade* usar* }` (Fase 13)."""
        tok = self.avancar()  # 'mundo'
        exemplo = ('mundo Principal {\n    tamanho: 2000px 1200px\n'
                   '    plataforma sup {\n'
                   '        posição: 700px 350px\n'
                   '        tamanho: 300px 30px\n    }\n'
                   '    usar personagem Heroi\n}')
        nome = self._parse_nome_livre("do mundo", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        mundo = A.Mundo(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O mundo {nome.valor!r} não foi fechado com "}}".',
                    exemplo=exemplo,
                )
            if self._comeca_entidade():
                mundo.entidades.append(self.parse_entidade())
            elif self._comeca_usar():
                mundo.entidades.append(self.parse_usar())
            elif self._comeca_propriedade():
                mundo.propriedades.append(self.parse_propriedade())
            else:
                raise self.erro(
                    "No mundo era esperado tamanho, entidade (chão, "
                    "parede, plataforma, obstáculo, objeto, área, ponto) "
                    "ou usar personagem.",
                    exemplo=exemplo,
                )
        self.avancar()  # '}'
        return mundo

    def parse_entidade(self) -> A.EntidadeMundo:
        """`parede esquerda { posição: .. tamanho: .. }` (só props)."""
        from . import ast as _A

        tok = self.avancar()
        tipo = _sem_acentos_10(tok.valor)
        exemplo = (f'{tok.valor} nome {{\n    posição: 0px 0px\n'
                   '    tamanho: 100px 20px\n}')
        nome = self._parse_nome_livre("da entidade", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro(
                f'Era esperado "{{" depois do nome {nome.valor!r}.',
                exemplo=exemplo,
            )
        self.avancar()
        entidade = _A.EntidadeMundo(tipo=tipo, nome=str(nome.valor),
                                    linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A entidade {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo,
                )
            if not self._comeca_propriedade():
                raise self.erro(
                    f'Na entidade {nome.valor!r} era esperado propriedade '
                    "(posição, tamanho, categoria, tag, visual).",
                    exemplo=exemplo,
                )
            entidade.propriedades.append(self.parse_propriedade())
        self.avancar()  # '}'
        return entidade

    def parse_usar(self) -> A.EntidadeMundo:
        """`usar personagem Nome` ou `usar item X [como Y] [{...}]`.

        Item vira entidade tipo "item" (instância); `ref` guarda a
        definição; `como` dá apelido à instância; chaves aceitam só
        posição/tamanho (override de bounds).
        """
        from . import ast as _A

        tok = self.avancar()  # 'usar'
        tok_kind = self.avancar()  # 'personagem' ou 'item'
        kind = _sem_acentos_10(tok_kind.valor)
        nome = self._parse_nome_livre(
            "do personagem" if kind == "personagem" else "do item",
            "usar personagem Heroi")
        if kind == "personagem":
            return _A.EntidadeMundo(tipo="personagem", nome=str(nome.valor),
                                    ref=str(nome.valor), linha=tok.linha)
        # usar item X [como Apelido] [{ posição/tamanho }]
        apelido = str(nome.valor)
        if (self.atual().tipo in (IDENT, PALAVRA)
                and _sem_acentos_10(self.atual().valor) == "como"):
            self.avancar()
            tok_apelido = self.atual()
            if tok_apelido.tipo not in (IDENT, PALAVRA):
                raise self.erro(
                    'Depois de "como" era esperado o nome da instância.',
                    exemplo="usar item Corda como corda_01")
            apelido = str(self.avancar().valor)
        entidade = _A.EntidadeMundo(tipo="item", nome=apelido,
                                    ref=str(nome.valor), linha=tok.linha)
        if self.eh_sinal("{"):
            self.avancar()
            while not self.eh_sinal("}"):
                if self.atual().tipo == EOF:
                    raise self.erro(
                        f'O item {apelido!r} não foi fechado com "}}".',
                        exemplo="usar item Corda {\n    posição: 0px 0px\n}")
                if not self._comeca_propriedade():
                    raise self.erro(
                        f'No item {apelido!r} era esperado posição ou '
                        "tamanho.",
                        exemplo="usar item Corda {\n    posição: 0px 0px\n}")
                entidade.propriedades.append(self.parse_propriedade())
            self.avancar()  # '}'
        return entidade

    def parse_grupo_objeto(self) -> A.Componente:
        """Fase 10: `grupo nome { ... }` / `objeto nome { ... }`.

        Contêiner visual com transformação própria; filhos em coordenadas
        locais. Corpo idêntico ao de componente (propriedades, blocos de
        transformação, eventos, filhos, grupo/objeto aninhados).
        """
        tok = self.atual()
        tipo = TIPOS_CONTENEIR_10[_sem_acentos_10(tok.valor)]
        return self.parse_componente(tipo_forcado=tipo)

    # ----- propriedades -----

    def parse_propriedade(self) -> A.Propriedade:
        tok_nome = self.avancar()
        nome = str(tok_nome.valor)
        self.avancar()  # ':'
        exemplo = f"{nome}: ..."
        valores = []
        # Fase 01: propriedades ocupam uma única linha. Isso dispensa
        # separadores e evita que valores "vazem" para o próximo bloco.
        while self.atual().linha == tok_nome.linha:
            t = self.atual()
            if t.tipo == EOF or self.eh_sinal("}", "{"):
                break
            if self.eh_palavra("quando"):
                break
            valores.append(self.parse_expressao())
        if not valores:
            raise self.erro(
                f'Era esperado um valor depois de "{nome}".',
                exemplo=f'{nome}: ...\n\nExemplo:\ntamanho: 800px 600px',
                tok=tok_nome,
            )
        _ = exemplo
        return A.Propriedade(nome=nome, valores=valores, linha=tok_nome.linha)

    # ----- eventos -----

    def parse_evento(self) -> A.Evento:
        tok = self.avancar()  # 'quando'
        t = self.atual()
        if t.tipo not in (IDENT, PALAVRA):
            raise self.erro(
                'Era esperado o nome do evento depois de "quando" '
                "(ex. clicar, pressionar, aparecer).",
                exemplo='quando clicar {\n    mostrar("Olá!")\n}',
            )
        nome = str(self.avancar().valor)
        if not self.eh_sinal("{"):
            raise self.erro(
                'Era esperado "{" depois do nome do evento.',
                exemplo=f'quando {nome} {{\n    mostrar("Olá!")\n}}',
            )
        self.avancar()
        bloco = self.parse_bloco_comandos(f"quando {nome}")
        return A.Evento(nome=nome, bloco=bloco, linha=tok.linha)

    # ----- blocos e comandos -----

    def parse_bloco_comandos(self, contexto: str) -> A.Bloco:
        tok = self.atual()
        bloco = A.Bloco(linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O bloco de "{contexto}" não foi fechado com "}}".',
                    exemplo='quando clicar {\n    mostrar("Olá!")\n}',
                )
            bloco.comandos.append(self.parse_comando())
        self.avancar()  # '}'
        return bloco

    def parse_comando(self) -> object:
        if self.eh_palavra("se"):
            return self.parse_se()
        if self.eh_palavra("repetir"):
            return self.parse_repetir()
        if self.eh_palavra("retornar"):
            return self.parse_retornar()
        t = self.atual()
        if t.tipo in (IDENT, PALAVRA):
            primeiro = self.avancar()
            nome = str(primeiro.valor)
            # Fase 09: executar acao / executar acao(args).
            if nome == "executar":
                alvo = self.atual()
                if alvo.tipo not in (IDENT, PALAVRA):
                    raise self.erro(
                        'Era esperado o nome da ação após "executar".',
                        exemplo='executar incrementar',
                    )
                nome_acao = str(self.avancar().valor)
                args_exec: list = []
                if self.eh_sinal("("):
                    self.avancar()
                    while not self.eh_sinal(")"):
                        if self.atual().tipo == EOF:
                            raise self.erro(
                                f'A execução "{nome_acao}" não teve o ")" '
                                "de fechamento.",
                                exemplo=f'executar {nome_acao}(...)',
                            )
                        args_exec.append(self.parse_expressao())
                        if self.eh_sinal(","):
                            self.avancar()
                    self.avancar()  # ')'
                return A.Acao(nome="executar",
                              args=[A.Chamada(nome=nome_acao,
                                              args=args_exec,
                                              linha=alvo.linha)],
                              linha=t.linha)
            args: list = []
            if self.eh_sinal("("):
                self.avancar()
                while not self.eh_sinal(")"):
                    if self.atual().tipo == EOF:
                        raise self.erro(
                            f'A ação "{nome}" não teve o ")" de fechamento.',
                            exemplo=f'{nome}("exemplo")',
                        )
                    args.append(self.parse_expressao())
                    if self.eh_sinal(","):
                        self.avancar()
                self.avancar()  # ')'
                return A.Acao(nome=nome, args=args, linha=t.linha)
            # Fase 05: caminho com pontos (estado.contador) e atribuição.
            if nome in ("local", "item", "param"):
                self._checar_contexto(nome, t)
            no: object = A.Ident(nome=nome, linha=t.linha)
            while self.eh_sinal("."):
                self.avancar()  # '.'
                u = self.atual()
                if u.tipo not in (IDENT, PALAVRA):
                    raise self.erro(
                        'Era esperado um nome depois do ponto.',
                        exemplo='estado.contador = 1',
                    )
                no = A.Membro(base=no, atributo=str(self.avancar().valor),
                              linha=u.linha)
            if self.eh_sinal("=", "+=", "-=", "*=", "/="):
                op = str(self.avancar().valor)
                if isinstance(no, A.Ident) and primeiro.tipo == PALAVRA:
                    raise self.erro(
                        f'Não dá para atribuir à palavra reservada "{nome}".',
                        exemplo='estado.contador = 1',
                    )
                valor = self.parse_expressao()
                return A.Atribuicao(alvo=no, op=op, valor=valor,
                                    linha=t.linha)
            if isinstance(no, A.Ident):
                return A.Acao(nome=nome, args=args, linha=t.linha)
            raise self.erro(
                f'"{A.caminho_de_membro(no)}" sozinho não é um comando. '
                "Use mostrar(...) para exibir ou = para atribuir.",
                exemplo='mostrar(estado.contador)',
            )
        raise self.erro(
            "Era esperado uma ação (ex. mostrar(...)), 'se', 'repetir' ou 'retornar'.",
            exemplo='mostrar("Olá, mundo!")',
        )

    def parse_se(self) -> A.Se:
        tok = self.avancar()  # 'se'
        cond = self.parse_expressao()
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" depois da condição do "se".',
                            exemplo='se visivel == verdadeiro {\n    mostrar("Oi")\n}')
        self.avancar()
        entao = self.parse_bloco_comandos("se")
        senao = None
        if self.eh_palavra("senão", "senao"):
            self.avancar()
            if not self.eh_sinal("{"):
                raise self.erro('Era esperado "{" depois de "senão".',
                                exemplo='senão {\n    esconder()\n}')
            self.avancar()
            senao = self.parse_bloco_comandos("senão")
        return A.Se(condicao=cond, entao=entao, senao=senao, linha=tok.linha)

    def parse_repetir(self) -> A.Repetir:
        tok = self.avancar()  # 'repetir'
        vezes = None
        if self.atual().tipo == NUMERO:
            vezes = A.NumeroLit(valor=float(self.avancar().valor), linha=tok.linha)
            if self.eh_palavra("vezes"):
                self.avancar()
        if not self.eh_sinal("{"):
            raise self.erro(
                'Era esperado "{" no "repetir" (ex. repetir 3 vezes { ... }).',
                exemplo="repetir 3 vezes {\n    mostrar(\"Oi\")\n}",
            )
        self.avancar()
        bloco = self.parse_bloco_comandos("repetir")
        return A.Repetir(vezes=vezes, bloco=bloco, linha=tok.linha)

    def parse_retornar(self) -> A.Retornar:
        tok = self.avancar()
        valor = None
        if not self.eh_sinal("}"):
            valor = self.parse_expressao()
        return A.Retornar(valor=valor, linha=tok.linha)

    def parse_funcao(self) -> A.Funcao:
        tok = self.avancar()  # 'função'
        nome = self.parse_nome(
            "da função",
            exemplo='função dobrar(valor) {\n    retornar valor * 2\n}',
        )
        if not self.eh_sinal("("):
            raise self.erro('Era esperado "(" depois do nome da função.',
                            exemplo="função dobrar(valor) {\n}")
        self.avancar()
        params: list[str] = []
        while not self.eh_sinal(")"):
            if self.atual().tipo == EOF:
                raise self.erro("A lista de parâmetros não foi fechada com \")\".")
            t = self.atual()
            if t.tipo != IDENT:
                raise self.erro("O parâmetro da função precisa ser um nome simples.",
                                exemplo="função somar(a, b) {\n}")
            params.append(str(self.avancar().valor))
            if self.eh_sinal(","):
                self.avancar()
        self.avancar()  # ')'
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" para começar o corpo da função.')
        self.avancar()
        bloco = self.parse_bloco_comandos(f"função {nome.valor}")
        return A.Funcao(nome=str(nome.valor), params=params,
                        bloco=bloco, linha=tok.linha)

    def _parse_params_chamada(self, exemplo: str) -> list[str]:
        """(a, b) — compartilhado por função e ação (Fase 09)."""
        self.avancar()  # '('
        params: list[str] = []
        while not self.eh_sinal(")"):
            if self.atual().tipo == EOF:
                raise self.erro("A lista de parâmetros não foi fechada com \")\".")
            t = self.atual()
            if t.tipo != IDENT:
                raise self.erro("O parâmetro precisa ser um nome simples.",
                                exemplo=exemplo)
            params.append(str(self.avancar().valor))
            if self.eh_sinal(","):
                self.avancar()
        self.avancar()  # ')'
        return params

    def parse_acao_def(self) -> A.AcaoDef:
        """`acao nome [(params)] { comandos }` (Fase 09)."""
        tok = self.avancar()  # 'acao'
        exemplo = 'acao incrementar {\n    estado.contador += 1\n}'
        nome = self.parse_nome("da ação", exemplo)
        params: list[str] = []
        if self.eh_sinal("("):
            params = self._parse_params_chamada(
                "acao selecionar(id) {\n}")
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" para começar a ação.',
                            exemplo=exemplo)
        self.avancar()
        bloco = self.parse_bloco_comandos(f"ação {nome.valor}")
        return A.AcaoDef(nome=str(nome.valor), params=params,
                         bloco=bloco, linha=tok.linha)

    def parse_import(self) -> A.Import:
        """`importar a.b.c` (Fase 09; loader resolve e valida)."""
        tok = self.avancar()  # 'importar'
        exemplo = 'importar componentes.card'
        partes: list[str] = []
        while True:
            t = self.atual()
            if t.tipo not in (IDENT, PALAVRA):
                raise self.erro(
                    'Era esperado um caminho como "componentes.card".',
                    exemplo=exemplo)
            partes.append(str(self.avancar().valor))
            if self.eh_sinal("."):
                self.avancar()
                continue
            break
        if not partes:
            raise self.erro('Era esperado um caminho após "importar".',
                            exemplo=exemplo)
        return A.Import(caminho=".".join(partes), linha=tok.linha)

    def parse_estado(self) -> A.EstadoDef:
        """Bloco `estado { nome: valor ... }` (Fase 05, escopo global)."""
        tok = self.avancar()  # 'estado'
        exemplo = 'estado {\n    contador: 0\n    nome: "Maria"\n}'
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" depois de "estado".',
                            exemplo=exemplo)
        self.avancar()
        bloco = A.EstadoDef(linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    'O bloco estado não foi fechado com "}".',
                    exemplo=exemplo,
                )
            if self._comeca_propriedade():
                bloco.propriedades.append(self.parse_propriedade())
            else:
                raise self.erro(
                    "No bloco estado era esperado nome: valor "
                    '(ex. contador: 0).',
                    exemplo=exemplo,
                )
        self.avancar()  # '}'
        return bloco

    def parse_fonte(self) -> A.FonteDef:
        """Bloco `dados nome { url/metodo/... }` (Fase 06)."""
        tok = self.avancar()  # 'dados'
        exemplo = ('dados usuarios {\n    url: "https://api.exemplo.com/u"\n'
                   '    metodo: "GET"\n}')
        nome = self.parse_nome("da fonte", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" depois do nome da fonte.',
                            exemplo=exemplo)
        self.avancar()
        fonte = A.FonteDef(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A fonte {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo)
            t = self.atual()
            if (t.tipo in (IDENT, PALAVRA)
                    and str(t.valor).lower() in (
                        "cabecalhos", "cabeçalhos", "parametros",
                        "parâmetros", "corpo")
                    and self.ver().tipo == SINAL
                    and self.ver().valor == "{"):
                fonte.blocos.append(self.parse_bloco_dados())
            elif self._comeca_propriedade():
                fonte.propriedades.append(self.parse_propriedade())
            else:
                raise self.erro(
                    "Na fonte era esperado propriedade (url, metodo, "
                    "tempo_limite, atualizar, arquivo, para) ou bloco "
                    "(cabecalhos, parametros, corpo).",
                    exemplo=exemplo)
        self.avancar()  # '}'
        return fonte

    def parse_bloco_dados(self) -> A.BlocoDados:
        """Sub-bloco com chaves livres (até texto com hífen, entre aspas)."""
        import unicodedata

        tok = self.avancar()
        base = unicodedata.normalize("NFKD", str(tok.valor).lower())
        nome = "".join(c for c in base if not unicodedata.combining(c))
        self.avancar()  # '{'
        bloco = A.BlocoDados(nome=nome, linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O bloco "{nome}" não foi fechado com "}}".')
            t = self.atual()
            if t.tipo == STRING:
                chave = str(self.avancar().valor)
                if not self.eh_sinal(":"):
                    raise self.erro('Era esperado ":" depois do nome.',
                                    exemplo='"Content-Type": "x"')
                self.avancar()
                valores = [self.parse_expressao()]
                bloco.propriedades.append(
                    A.Propriedade(nome=chave, valores=valores,
                                  linha=t.linha))
            elif self._comeca_propriedade():
                bloco.propriedades.append(self.parse_propriedade())
            else:
                raise self.erro(
                    "No bloco era esperado nome: valor.",
                    exemplo='pagina: 1\n"Content-Type": "application/json"')
        self.avancar()  # '}'
        return bloco

    def parse_tema(self) -> A.TemaDef:
        """Bloco `tema nome { cores/tamanhos/espacos {..} }` (Fase 08)."""
        tok = self.avancar()  # 'tema'
        exemplo = ('tema escuro {\n    cores {\n        fundo: "#14161f"\n'
                   '    }\n}')
        nome = self.parse_nome("do tema", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" depois do nome do tema.',
                            exemplo=exemplo)
        self.avancar()
        tema = A.TemaDef(nome=str(nome.valor), linha=tok.linha)
        vistos: set[str] = set()
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O tema {nome.valor!r} não foi fechado com "}}".',
                    exemplo=exemplo)
            t = self.atual()
            if (t.tipo in (IDENT, PALAVRA)
                    and self.ver().tipo == SINAL
                    and self.ver().valor == "{"):
                secao = str(self.avancar().valor).lower()
                if secao not in ("cores", "tamanhos", "espacos", "espaços"):
                    raise self.erro(
                        'No tema só existem "cores", "tamanhos" e "espacos".',
                        exemplo=exemplo)
                secao = {"espaços": "espacos"}.get(secao, secao)
                if secao in vistos:
                    raise self.erro(
                        f'Seção "{secao}" repetida no tema.',
                        exemplo=exemplo)
                vistos.add(secao)
                self.avancar()  # '{'
                while not self.eh_sinal("}"):
                    if self.atual().tipo == EOF:
                        raise self.erro(
                            f'A seção "{secao}" não foi fechada com "}}".')
                    if self._comeca_propriedade():
                        getattr(tema, secao).append(self.parse_propriedade())
                    else:
                        raise self.erro(
                            "Na seção era esperado nome: valor.",
                            exemplo='fundo: "#14161f"')
                self.avancar()  # '}'
            else:
                raise self.erro(
                    "No tema era esperado bloco cores, tamanhos ou espacos.",
                    exemplo=exemplo)
        self.avancar()  # '}'
        return tema

    def parse_componente_def(self) -> A.ComponenteDef:
        """`componente Nome { propriedade x [: padrao] corpo {..} }`."""
        tok = self.avancar()  # 'componente'
        exemplo = ('componente Cartao {\n    propriedade titulo\n'
                   '    corpo {\n        texto t {\n'
                   '            texto: param.titulo\n        }\n    }\n}')
        nome = self.parse_nome("do componente", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" depois do nome do componente.',
                            exemplo=exemplo)
        self.avancar()
        definicao = A.ComponenteDef(nome=str(nome.valor), linha=tok.linha)
        viu_corpo = False
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O componente {nome.valor!r} não foi fechado com "}}".',
                    exemplo=exemplo)
            if self.eh_palavra("propriedade"):
                self.avancar()
                t = self.atual()
                if t.tipo not in (IDENT, PALAVRA):
                    raise self.erro("Era esperado o nome da propriedade.",
                                    exemplo="propriedade titulo")
                param = A.ParamComponente(nome=str(self.avancar().valor),
                                          linha=t.linha)
                if self.eh_sinal(":"):
                    self.avancar()
                    param.padrao = self.parse_expressao()
                definicao.params.append(param)
            elif self.eh_palavra("corpo"):
                if viu_corpo:
                    raise self.erro("Só um bloco corpo por componente.",
                                    exemplo=exemplo)
                viu_corpo = True
                self.avancar()
                if not self.eh_sinal("{"):
                    raise self.erro('Era esperado "{" depois de "corpo".',
                                    exemplo=exemplo)
                self.avancar()
                self._em_def += 1
                try:
                    while not self.eh_sinal("}"):
                        if self.atual().tipo == EOF:
                            raise self.erro(
                                'O corpo não foi fechado com "}".')
                        if self.eh_palavra(*TIPOS_COMPONENTE):
                            definicao.corpo.append(self.parse_componente())
                        elif self._comeca_grupo_objeto():
                            definicao.corpo.append(self.parse_grupo_objeto())
                        elif self._comeca_personagem():
                            definicao.corpo.append(self.parse_personagem())
                        elif self._comeca_instancia():
                            definicao.corpo.append(self.parse_instancia())
                        else:
                            raise self.erro(
                                "No corpo era esperado um componente.",
                                exemplo=exemplo)
                finally:
                    self._em_def -= 1
                self.avancar()  # '}' do corpo
            elif self.eh_palavra("estado"):
                # Fase 09: padrões do estado local da instância.
                if definicao.estado is not None:
                    raise self.erro("Só um bloco estado por componente.",
                                    exemplo=exemplo)
                definicao.estado = self.parse_estado()
            else:
                raise self.erro(
                    "No componente era esperado propriedade, estado ou corpo.",
                    exemplo=exemplo)
        self.avancar()  # '}'
        return definicao

    # ----- expressões (precedência de operadores) -----

    def parse_expressao(self, nivel: int = 1) -> object:
        esquerda = self.parse_unaria()
        while True:
            t = self.atual()
            if t.tipo == SINAL:
                op = str(t.valor)
            elif t.tipo == PALAVRA and str(t.valor) in ("e", "ou"):
                op = str(t.valor)
            else:
                return esquerda
            prec = PRECEDENCIA.get(op)
            if prec is None or prec < nivel:
                return esquerda
            self.avancar()
            direita = self.parse_expressao(prec + 1)
            esquerda = A.Binaria(op=op, esquerda=esquerda,
                                 direita=direita, linha=t.linha)

    def parse_unaria(self) -> object:
        t = self.atual()
        if t.tipo == SINAL and t.valor == "-":
            self.avancar()
            base = self.parse_unaria()
            if isinstance(base, A.NumeroLit):
                return A.NumeroLit(valor=-base.valor, linha=t.linha)
            if isinstance(base, A.Medida):
                return A.Medida(valor=-base.valor, unidade=base.unidade,
                                linha=t.linha)
            return A.Binaria(op="*", esquerda=A.NumeroLit(valor=-1.0),
                             direita=base, linha=t.linha)
        if t.tipo == PALAVRA and str(t.valor) in ("não", "nao"):
            self.avancar()
            base = self.parse_unaria()
            return A.Binaria(op="nao", esquerda=A.Booleano(valor=True),
                             direita=base, linha=t.linha)
        return self.parse_primaria()

    def parse_primaria(self) -> object:
        t = self.atual()
        if t.tipo == STRING:
            self.avancar()
            texto = str(t.valor)
            if eh_hex(texto):
                return A.CorLit(formato="hex", valor=texto, linha=t.linha)
            return A.TextoLit(valor=texto, linha=t.linha)
        if t.tipo == NUMERO:
            self.avancar()
            if self.atual().tipo == UNIDADE:
                u = self.avancar()
                return A.Medida(valor=float(t.valor), unidade=str(u.valor),
                                linha=t.linha)
            return A.NumeroLit(valor=float(t.valor), linha=t.linha)
        if t.tipo == IDENT:
            self.avancar()
            nome = str(t.valor)
            if nome in ("local", "item", "param"):
                self._checar_contexto(nome, t)
            if nome.lower() in CORES_NOMEADAS:
                return A.CorLit(formato="nomeada", valor=nome.lower(),
                                linha=t.linha)
            if self.eh_sinal("("):
                no = self.parse_chamada_resto(nome, t.linha)
            else:
                no = A.Ident(nome=nome, linha=t.linha)
            return self.parse_membros(no)
        if t.tipo == PALAVRA:
            if str(t.valor) in ("verdadeiro", "falso"):
                self.avancar()
                return A.Booleano(valor=str(t.valor) == "verdadeiro",
                                  linha=t.linha)
            # palavra reservada usada como valor/nome (ex. extensão futura)
            self.avancar()
            if self.eh_sinal("("):
                return self.parse_chamada_resto(str(t.valor), t.linha)
            return self.parse_membros(A.Ident(nome=str(t.valor),
                                              linha=t.linha))
        if self.eh_sinal("("):
            self.avancar()
            expr = self.parse_expressao()
            if not self.eh_sinal(")"):
                raise self.erro('Era esperado ")" para fechar a expressão.',
                                exemplo="(1 + 2) * 3")
            self.avancar()
            return expr
        if self.eh_sinal("["):
            self.avancar()
            itens: list = []
            while not self.eh_sinal("]"):
                if self.atual().tipo == EOF:
                    raise self.erro(
                        'A lista não foi fechada com "]".',
                        exemplo="[10, 25, 35]")
                itens.append(self.parse_expressao())
                if self.eh_sinal(","):
                    self.avancar()
            self.avancar()  # ']'
            return A.ListaLit(itens=itens, linha=t.linha)
        raise self.erro(
            "Era esperado um valor (texto, número, cor ou nome).",
            exemplo='texto: "Olá"\ntamanho: 800px 600px\ncor: vermelho',
        )

    def parse_membros(self, no: object) -> object:
        """Encadeia acesso por pontos: dados.sistema.cpu (+ chamada futura)."""
        while self.eh_sinal("."):
            self.avancar()  # '.'
            t = self.atual()
            if t.tipo not in (IDENT, PALAVRA):
                raise self.erro(
                    'Era esperado um nome depois do ponto (ex. dados.sistema.cpu).',
                    exemplo="origem: dados.sistema.cpu",
                )
            atributo = str(self.avancar().valor)
            if self.eh_sinal("("):
                base_nome = A.caminho_de_membro(no) + "." + atributo
                no = self.parse_chamada_resto(base_nome, t.linha)
            else:
                no = A.Membro(base=no, atributo=atributo, linha=t.linha)
        return no

    # ----- animação (Fase 03) -----

    def parse_animacao(self) -> A.AnimacaoDef:
        import unicodedata

        def norm(s: str) -> str:
            base = unicodedata.normalize("NFKD", s.lower())
            return "".join(c for c in base if not unicodedata.combining(c))

        tok = self.avancar()  # 'animação'
        exemplo = ('animação entrada {\n    alvo: cartao\n'
                   '    posição: 0px 90px → 0px 40px\n'
                   '    duração: 600ms\n    movimento: suave\n}')
        nome = self.parse_nome("da animação", exemplo)
        if not self.eh_sinal("{"):
            raise self.erro('Era esperado "{" depois do nome da animação.',
                            exemplo=exemplo)
        self.avancar()
        anim = A.AnimacaoDef(nome=str(nome.valor), linha=tok.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A animação {nome.valor!r} não foi fechada com "}}".',
                    exemplo=exemplo)
            if self.eh_palavra("quando"):
                self.avancar()
                ev = self.atual()
                if (ev.tipo not in (IDENT, PALAVRA)
                        or norm(str(ev.valor)) not in (
                            "terminar", "comecar", "cancelar")):
                    raise self.erro(
                        'Em animação, os eventos são "quando terminar", '
                        '"quando começar" e "quando cancelar".',
                        exemplo='quando terminar {\n    mostrar("pronto!")\n}')
                qual = norm(str(ev.valor))
                self.avancar()
                if not self.eh_sinal("{"):
                    raise self.erro(
                        f'Era esperado "{{" depois de "quando {ev.valor}".')
                self.avancar()
                bloco = self.parse_bloco_comandos(
                    f"animação {nome.valor} {ev.valor}")
                if qual == "terminar":
                    anim.ao_terminar = bloco
                elif qual == "comecar":
                    anim.ao_comecar = bloco
                else:
                    anim.ao_cancelar = bloco
                continue
            if self._comeca_keyframe():
                anim.keyframes.append(self._parse_keyframe(norm, exemplo))
                continue
            if not self._comeca_propriedade():
                raise self.erro(
                    "Na animação era esperado alvo, propriedade animada "
                    "(posição, tamanho, opacidade...), duração, movimento, "
                    "modo, keyframe (0% { ... }) ou quando terminar.",
                    exemplo=exemplo)
            prop = self.avancar()
            self.avancar()  # ':'
            chave = norm(str(prop.valor))
            if chave in ("alvo", "depois", "movimento", "inicio"):
                anim_val = self._parse_anim_texto(chave, prop)
                setattr(anim, {"inicio": "inicio"}.get(chave, chave), anim_val)
            elif chave == "modo":
                anim.modo = self._parse_anim_modo(prop)
            elif chave == "fisica":
                anim.fisica = self._parse_anim_fisica(prop)
            elif chave in ("duracao", "atraso"):
                anim_val = self._parse_anim_tempo(chave, prop)
                setattr(anim, {"duracao": "duracao_ms",
                               "atraso": "atraso_ms"}[chave], anim_val)
            elif chave in ("rigidez", "amortecimento", "massa"):
                setattr(anim, chave, self._parse_anim_numero(
                    chave, prop, minimo=0.0, permite_zero=False))
            elif chave == "voltas":
                anim.voltas = self._parse_anim_numero(
                    chave, prop, minimo=0.0, permite_zero=True,
                    inteiro=True)
            elif chave == "relativo":
                anim.relativo = self._parse_anim_booleano(prop)
            elif chave == "repetir":
                anim.repetir = self._parse_anim_repetir(prop)
            elif chave in ("posicao", "tamanho", "escala", "rotacao",
                           "opacidade"):
                anim.chaves.append(self._parse_anim_chave(chave, prop))
            else:
                raise self.erro(
                    f'Propriedade de animação desconhecida: "{prop.valor}". '
                    "Válidas: alvo, posição, tamanho, escala, rotação, "
                    "opacidade, duração, atraso, movimento, modo, relativo, "
                    "voltas, fisica, rigidez, amortecimento, massa, "
                    "repetir, início, depois.",
                    exemplo=exemplo)
        self.avancar()  # '}'
        return anim

    def _comeca_keyframe(self) -> bool:
        """Fase 11: `40% { ... }` dentro de animação (quadro temporal)."""
        t = self.atual()
        return (t.tipo == NUMERO and self.ver().tipo == UNIDADE
                and self.ver().valor == "%"
                and self.ver(2).tipo == SINAL
                and self.ver(2).valor == "{")

    def _parse_keyframe(self, norm, exemplo: str) -> A.KeyframeAST:
        """Quadro `P% { prop: valor ... }` (P em 0..100)."""
        from . import ast as _A

        tok_num = self.avancar()  # número
        self.avancar()  # '%'
        self.avancar()  # '{'
        percent = float(tok_num.valor)
        quadro = _A.KeyframeAST(percent=percent, linha=tok_num.linha)
        while not self.eh_sinal("}"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'O quadro {percent:g}% não foi fechado com "}}".',
                    exemplo="40% {\n    posição: 300px 200px\n}")
            if not self._comeca_propriedade():
                raise self.erro(
                    f'No quadro {percent:g}% era esperado propriedade '
                    "animada (posição, tamanho, escala, rotação, "
                    "opacidade).",
                    exemplo="40% {\n    posição: 300px 200px\n}")
            prop = self.avancar()
            self.avancar()  # ':'
            chave = norm(str(prop.valor))
            if chave not in ("posicao", "tamanho", "escala", "rotacao",
                             "opacidade"):
                raise self.erro(
                    f'No quadro {percent:g}%, "{prop.valor}" não é '
                    "animável.",
                    exemplo="40% {\n    posição: 300px 200px\n}")
            if any(c.propriedade == chave for c in quadro.chaves):
                raise self.erro(
                    f'"{prop.valor}" repetida no quadro {percent:g}%.',
                    exemplo="40% {\n    posição: 300px 200px\n}")
            quadro.chaves.append(self._parse_anim_chave(chave, prop))
        self.avancar()  # '}'
        return quadro

    def _parse_anim_modo(self, prop: Token) -> str:
        t = self.atual()
        if t.tipo in (IDENT, PALAVRA, STRING):
            valor = str(t.valor).lower().replace("-", "_")
            self.avancar()
            if valor in ("normal",):
                return "normal"
            if valor in ("ping_pong", "pingpong", "ida_volta", "vai_volta"):
                return "ping_pong"
            # Desconhecido passa adiante: a semântica lista os válidos.
            return valor
        raise self.erro(
            '"modo" espera "normal" ou "ping_pong".',
            exemplo="modo: ping_pong")

    def _parse_anim_fisica(self, prop: Token) -> str:
        t = self.atual()
        if t.tipo in (IDENT, PALAVRA, STRING):
            valor = str(t.valor)
            self.avancar()
            # "mola" ou outro texto: a semântica valida contra FISICAS.
            return valor
        raise self.erro('"fisica" espera "mola" (dinâmica com rigidez).',
                        exemplo="fisica: mola")

    def _parse_anim_numero(self, chave: str, prop: Token, *,
                           minimo: float, permite_zero: bool,
                           inteiro: bool = False) -> float:
        from . import ast as _A

        expr = self.parse_expressao()
        if not isinstance(expr, _A.NumeroLit):
            raise self.erro(f'"{prop.valor}" espera número.',
                            exemplo=f"{prop.valor}: 180")
        numero = float(expr.valor)
        if not (numero > minimo or (permite_zero and numero == minimo)):
            raise self.erro(
                f'"{prop.valor}" precisa ser maior que {minimo:g}.',
                exemplo=f"{prop.valor}: 180")
        return int(numero) if inteiro else numero

    def _parse_anim_booleano(self, prop: Token) -> bool:
        from . import ast as _A

        expr = self.parse_expressao()
        if not isinstance(expr, _A.Booleano):
            raise self.erro(f'"{prop.valor}" espera verdadeiro ou falso.',
                            exemplo=f"{prop.valor}: verdadeiro")
        return bool(expr.valor)

    def _parse_anim_texto(self, chave: str, prop: Token) -> str:
        t = self.atual()
        if t.tipo == STRING:
            self.avancar()
            return str(t.valor)
        if t.tipo in (IDENT, PALAVRA):
            self.avancar()
            return str(t.valor)
        raise self.erro(f'Era esperado um nome/texto depois de "{prop.valor}".',
                        exemplo=f"{prop.valor}: exemplo")

    def _parse_anim_tempo(self, chave: str, prop: Token) -> float:
        from ..unidades import tempo_para_ms

        expr = self.parse_expressao()
        from . import ast as _A

        if isinstance(expr, _A.Medida):
            from ..unidades import categoria

            if categoria(expr.unidade) != "tempo":
                raise self.erro(
                    f'"{prop.valor}" espera tempo (ms ou s).',
                    exemplo=f"{prop.valor}: 500ms")
            return tempo_para_ms(expr.valor, expr.unidade)
        raise self.erro(f'"{prop.valor}" espera tempo (ms ou s).',
                        exemplo=f"{prop.valor}: 500ms")

    def _parse_anim_repetir(self, prop: Token) -> object:
        from . import ast as _A

        expr = self.parse_expressao()
        if isinstance(expr, _A.NumeroLit):
            if expr.valor < 1:
                raise self.erro('"repetir" precisa de ao menos 1 vez.',
                                exemplo="repetir: 3")
            return int(expr.valor)
        if isinstance(expr, (_A.Ident,)) and str(expr.nome).lower() == "infinito":
            return "infinito"
        raise self.erro('"repetir" espera número ou "infinito".',
                        exemplo="repetir: 3")

    def _parse_anim_chave(self, chave: str, prop: Token) -> A.ChaveAnimacaoAST:
        from . import ast as _A

        def numero(expr) -> tuple:
            if isinstance(expr, _A.Medida):
                return (expr.unidade, float(expr.valor))
            if isinstance(expr, _A.NumeroLit):
                return ("px", float(expr.valor))
            raise self.erro(
                f'"{prop.valor}" espera número ou medida em pixels.',
                exemplo=f"{prop.valor}: 0px → 100px")

        def grupo() -> list:
            vals = []
            while (self.atual().tipo != EOF and not self.eh_sinal("}", "→", "->")
                   and self.atual().linha == prop.linha
                   and not self.eh_palavra("quando")):
                vals.append(numero(self.parse_expressao()))
            return vals

        antes = grupo()
        if self.eh_sinal("→", "->"):
            self.avancar()
            depois = grupo()
            if not antes or not depois:
                raise self.erro(
                    f'"{prop.valor}" precisa de valor antes e depois da seta.',
                    exemplo=f"{prop.valor}: 0px → 100px")
            return A.ChaveAnimacaoAST(propriedade=chave,
                                      de=self._forma_valor(chave, antes, prop),
                                      para=self._forma_valor(chave, depois, prop),
                                      linha=prop.linha)
        if not antes:
            raise self.erro(f'Era esperado um valor depois de "{prop.valor}".',
                            exemplo=f"{prop.valor}: 0px → 100px")
        return A.ChaveAnimacaoAST(propriedade=chave, de=None,
                                  para=self._forma_valor(chave, antes, prop),
                                  linha=prop.linha)

    @staticmethod
    def _forma_valor(chave: str, vals: list, prop: Token) -> object:
        # Preserva unidades: a semântica exige pixels em animação (Fase 03).
        if chave in ("posicao", "tamanho"):
            if len(vals) not in (1, 2):
                raise ErroSintatico(
                    f'"{prop.valor}" espera 1 ou 2 valores '
                    f"(recebido {len(vals)}).",
                    linha=prop.linha,
                    exemplo=f"{prop.valor}: 0px 0px → 100px 50px")
            return tuple(vals) if len(vals) == 2 else vals[0]
        if len(vals) != 1:
            raise ErroSintatico(
                f'"{prop.valor}" espera 1 valor (recebido {len(vals)}).',
                linha=prop.linha, exemplo=f"{prop.valor}: 0 → 1")
        return vals[0]

    def parse_chamada_resto(self, nome: str, linha: int) -> A.Chamada:
        self.avancar()  # '('
        args: list = []
        while not self.eh_sinal(")"):
            if self.atual().tipo == EOF:
                raise self.erro(
                    f'A chamada "{nome}" não teve o ")" de fechamento.',
                    exemplo=f'{nome}("exemplo")',
                )
            args.append(self.parse_expressao())
            if self.eh_sinal(","):
                self.avancar()
        self.avancar()  # ')'
        return A.Chamada(nome=nome, args=args, linha=linha)


def analisar(fonte: str, nome_arquivo: str = "<memória>") -> A.Programa:
    """Pipeline do compilador: tokenizar + analisar (sem executar)."""
    from .lexer import tokenizar

    return Parser(tokenizar(fonte, nome_arquivo)).parse()
