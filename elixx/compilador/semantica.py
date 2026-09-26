"""Semântica da ELiXX — validação de significado (após o parser).

Verifica: janela existente, propriedades conhecidas com tipos corretos,
eventos válidos (consulta runtime/eventos.py) e ações válidas (consulta
runtime/acoes.py). Devolve avisos; erros levantam ErroSemantico em PT.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..cores import CORES_NOMEADAS, eh_hex
from ..erros import ErroSemantico, sugerir
from ..unidades import categoria
from ..runtime.acoes import REGISTRO as ACOES
from ..runtime.eventos import EVENTOS_SUPORTADOS
from . import ast as A


@dataclass
class Aviso:
    mensagem: str
    linha: int = 0


# propriedades conhecidas por categoria de elemento (+ exemplo de uso)
PROPS_JANELA = {
    "titulo": ("texto", 'titulo: "Minha aplicação"'),
    "título": ("texto", 'titulo: "Minha aplicação"'),
    "tamanho": ("medidas_1_2", "tamanho: 800px 600px"),
    "posicao": ("medidas_2", "posição: 100px 100px"),
    "posição": ("medidas_2", "posição: 100px 100px"),
    "fundo": ("cor", 'fundo: azul'),
    "cor": ("cor", "cor: vermelho"),
    "tema": ("texto", 'tema: "escuro"'),
    "inicial": ("booleano", "inicial: verdadeiro"),
}
PROPS_COMPONENTE = {
    "texto": ("texto", 'texto: "Olá ELiXX"'),
    "titulo": ("texto", 'titulo: "Título"'),
    # Fase 02: "conteúdo" é alias de "texto" (a sintaxe da Fase 01 continua
    # valendo; nada existente quebra).
    "conteudo": ("texto", 'conteúdo: "Olá ELiXX"'),
    "conteúdo": ("texto", 'conteúdo: "Olá ELiXX"'),
    # Fase 02: "fonte" é o tamanho da letra. Decisão documentada: "tamanho"
    # continua significando dimensões da caixa (Fase 01), por isso a letra
    # ganha propriedade própria em vez de sobrecarregar "tamanho: 24px".
    "fonte": ("medida_1", "fonte: 24px"),
    "tamanho": ("medidas_1_2", "tamanho: 200px 50px"),
    "posicao": ("medidas_2", "posição: 10px 20px"),
    "posição": ("medidas_2", "posição: 10px 20px"),
    "cor": ("cor", "cor: vermelho"),
    "fundo": ("cor", "fundo: azul"),
    "duracao": ("tempo", "duração: 500ms"),
    "duração": ("tempo", "duração: 500ms"),
    "movimento": ("texto", "movimento: suave"),
    "opacidade": ("opacidade", "opacidade: 80%"),
    # Fase 10: Visual Core 2D (transformação; layout continua separado).
    # Precedência documentada: layout organiza a estrutura; transform
    # (posição/rotação/escala/pivô/opacidade/camada) move o visual.
    "rotacao": ("angulo", "rotação: 30deg"),
    "rotação": ("angulo", "rotação: 30deg"),
    "escala": ("numero_1_2", "escala: 1.2"),
    "pivo": ("pivo", "pivô: 50% 50%"),
    "pivô": ("pivo", "pivô: 50% 50%"),
    "camada": ("numero", "camada: 10"),
    # Reatividade (extensão dashboard): liga o componente a um dado vivo.
    # Decisão: "origem:" (fonte do vínculo) em vez de "valor:" — "valor"
    # sugeriria conteúdo estático, enquanto "origem" declara ligação.
    "origem": ("origem_dados", "origem: dados.sistema.cpu"),
    "formato": ("texto", 'formato: "percentual"'),
    # Fase 05: two-way binding (só estado; dados é somente leitura).
    "ligado_a": ("ligado_estado", "ligado_a: estado.nome"),
    # Fase 04: layout (aditivas; nada existente muda).
    "espacamento": ("medida_1", "espaçamento: 12px"),
    "espaçamento": ("medida_1", "espaçamento: 12px"),
    "margem": ("medidas_1_2", "margem: 16px"),
    "preenchimento": ("medidas_1_2", "preenchimento: 12px"),
    "alinhamento": ("alinhamento", 'alinhamento: "centro"'),
    "largura": ("medida_1", "largura: 200px"),
    "altura": ("medida_1", "altura: 40px"),
    "minimo": ("medida_1", "mínimo: 100px"),
    "mínimo": ("medida_1", "mínimo: 100px"),
    "maximo": ("medida_1", "máximo: 400px"),
    "máximo": ("medida_1", "máximo: 400px"),
    "colunas": ("numero", "colunas: 3"),
    "opcoes": ("textos", 'opções: "a" "b" "c"'),
    "opções": ("textos", 'opções: "a" "b" "c"'),
    # Fase 07: multimídia (aditivas; props continuam vocabulário livre).
    "arquivo": ("texto", 'arquivo: "assets/logo.png"'),
    "url": ("texto", 'url: "https://exemplo.com/a.png"'),
    "reserva": ("texto", 'reserva: "assets/padrao.png"'),
    "ajuste": ("ajuste", 'ajuste: "conter"'),
    "tipo": ("tipo_grafico", 'tipo: "barras"'),
    "nome": ("texto", 'nome: "salvar"'),
    "volume": ("volume", "volume: 80"),
    "repetir": ("booleano", "repetir: verdadeiro"),
    # Fase 08: aplicação (aditivas).
    "tema": ("texto", 'tema: "escuro"'),    "inicial": ("booleano", "inicial: verdadeiro"),
    "ativa": ("indice_ativo", 'ativa: 0'),
    "obrigatorio": ("booleano", "obrigatório: verdadeiro"),
    "obrigatório": ("booleano", "obrigatório: verdadeiro"),
    "validar": ("validacao", 'validar: "email"'),
    "min_caracteres": ("numero", "min_caracteres: 3"),
    "max_caracteres": ("numero", "max_caracteres: 40"),
    "min_valor": ("numero", "min_valor: 0"),
    "max_valor": ("numero", "max_valor: 100"),
    "descricao": ("texto", 'descrição: "Salvar alterações"'),
    "descrição": ("texto", 'descrição: "Salvar alterações"'),
    "destino": ("texto", 'destino: "usuarios"'),
    "colunas": ("numero_ou_textos", "colunas: 3"),
    # Fase 09: chave de identidade da linha (ex. chave: item.id).
    "chave": ("caminho", 'chave: item.id'),
}

# Fase 12: Character/Puppet Core (propriedades extras de personagem/parte).
# Direção visual (estado 2D multi-representação, sem 3D).
DIRECOES_PERSONAGEM = ("frente", "costas", "esquerda", "direita", "cima",
                       "baixo")

PROPS_PERSONAGEM = dict(
    PROPS_COMPONENTE,
    **{
        "imagem": ("texto", 'imagem: "corpo.png"'),
        "direcao": ("direcao", 'direcao: "direita"'),
        "direção": ("direcao", 'direcao: "direita"'),
        "frente": ("texto", 'frente: "frente.png"'),
        "costas": ("texto", 'costas: "costas.png"'),
        "esquerda": ("texto", 'esquerda: "esq.png"'),
        "direita": ("texto", 'direita: "dir.png"'),
        "cima": ("texto", 'cima: "cima.png"'),
        "baixo": ("texto", 'baixo: "baixo.png"'),
        # Fase 14: posse/equipamento declarativos (nomes de definições).
        "possui": ("textos", 'possui: "Corda"'),
        "equipa": ("textos", 'equipa: "BotaFoguete"'),
    },
)

PROPS_PARTE = dict(
    PROPS_PERSONAGEM,
    **{
        "junta": ("texto", 'junta: "ombro"'),
        "limite_min": ("angulo", "limite_min: 0deg"),
        "limite_max": ("angulo", "limite_max: 145deg"),
    },
)

POSE_PROPS = {
    "posicao": ("medidas_2", "posição: 100px 100px"),
    "posição": ("medidas_2", "posição: 100px 100px"),
    "rotacao": ("angulo", "rotação: 30deg"),
    "rotação": ("angulo", "rotação: 30deg"),
    "escala": ("numero_1_2", "escala: 1.2"),
    "opacidade": ("opacidade", "opacidade: 80%"),
    "pivo": ("pivo", "pivô: 50% 50%"),
    "pivô": ("pivo", "pivô: 50% 50%"),
}

# Fase 13: World & Scene Intelligence (camada semântica, sem visual).
PROPS_MUNDO = {
    "tamanho": ("medidas_1_2", "tamanho: 2000px 1200px"),
}

# Fase 14: Items + Capability System (dados declarativos, sem execução).
PROPS_ITEM = {
    "categoria": ("texto", 'categoria: "equipamento"'),
    "tags": ("textos", 'tags: "voo" "propulsao"'),
    "estado": ("texto", 'estado: "disponivel"'),
    "imagem": ("texto", 'imagem: "bota.png"'),
    "visual": ("referencia", 'visual: "bota_visual"'),
    "slot": ("texto", 'slot: "pes"'),
    "anexo": ("texto", 'anexo: "mao_direita"'),
    "frente": ("texto", 'frente: "frente.png"'),
    "costas": ("texto", 'costas: "costas.png"'),
    "esquerda": ("texto", 'esquerda: "esq.png"'),
    "direita": ("texto", 'direita: "dir.png"'),
    "cima": ("texto", 'cima: "cima.png"'),
    "baixo": ("texto", 'baixo: "baixo.png"'),
}

PROPS_CAPACIDADE = {
    "descricao": ("texto", 'descricao: "voar com propulsão"'),
    "descrição": ("texto", 'descricao: "voar com propulsão"'),
    "requer_equipado": ("texto", 'requer_equipado: "BotaFoguete"'),
    "requer_possuido": ("texto", 'requer_possuido: "Corda"'),
    "requer_presente": ("texto", 'requer_presente: "torre"'),
    "requer_proximo": ("texto", 'requer_proximo: "torre"'),
    "requer_tag": ("texto", 'requer_tag: "interativo"'),
    "requer_categoria": ("texto", 'requer_categoria: "caixa"'),
    "requer_tipo": ("texto", 'requer_tipo: "objeto"'),
    "requer_estado": ("texto", 'requer_estado: "ligado"'),
    "requer_capacidade": ("texto", 'requer_capacidade: "equilibrio"'),
}

PROPS_USAR_ITEM = {
    "posicao": ("medidas_2", "posição: 100px 100px"),
    "posição": ("medidas_2", "posição: 100px 100px"),
    "tamanho": ("medidas_1_2", "tamanho: 40px 40px"),
}

# Fase 15: Navigation + Traversal (descritivo; sem execução).
PROPS_CAMINHO = {
    "modo": ("descritor", 'modo: "andar"'),
    "custo": ("numero", "custo: 1"),
    "requer": ("descritor", 'requer: "voar"'),
    "bloqueado": ("booleano", "bloqueado: verdadeiro"),
}

LADOS_BORDA_15 = ("esquerda", "direita", "topo", "base")

PROPS_ENTIDADE = {
    "posicao": ("medidas_2", "posição: 100px 100px"),
    "posição": ("medidas_2", "posição: 100px 100px"),
    "tamanho": ("medidas_1_2", "tamanho: 300px 30px"),
    "categoria": ("texto", 'categoria: "caixa"'),
    "tag": ("texto", 'tag: "interativo"'),
    "tags": ("textos", 'tags: "a" "b"'),
    "visual": ("referencia", 'visual: "caixa_visual"'),
    "pai": ("referencia", 'pai: "sala"'),
}

TIPOS_ENTIDADE_13 = ("chao", "parede", "plataforma", "obstaculo", "objeto",
                     "area", "ponto", "personagem", "item")


def _eh_texto(v: object) -> bool:
    return isinstance(v, A.TextoLit)


def _eh_ref_tema(v: object) -> bool:
    """Membro `tema.nome` (resolvido na Cena; checado no pós-passe)."""
    if not isinstance(v, A.Membro):
        return False
    partes = A.caminho_de_membro(v).split(".")
    return len(partes) == 2 and partes[0] == "tema"


def _eh_ref_estado(v: object) -> bool:
    if not isinstance(v, A.Membro):
        return False
    partes = A.caminho_de_membro(v).split(".")
    return len(partes) == 2 and partes[0] == "estado"


def _eh_medida(v: object, cat: str) -> bool:
    return isinstance(v, A.Medida) and categoria(v.unidade) == cat


def validar_valor(especificacao: str, valores: list, nome_prop: str,
                   linha: int, fontes_remotas=frozenset()) -> None:
    def erro(esperado: str, exemplo: str) -> ErroSemantico:
        return ErroSemantico(
            f'Propriedade "{nome_prop}" espera {esperado}.',
            linha=linha, exemplo=f"{nome_prop}: {exemplo}",
        )

    if especificacao == "texto":
        if len(valores) != 1 or not _eh_texto(valores[0]):
            raise erro("um texto entre aspas", '"exemplo"')
    elif especificacao == "angulo":
        # Fase 10: graus/deg/rad ou número (= graus). Finitude exigida.
        import math

        if len(valores) != 1:
            raise erro("um ângulo (ex. 30deg ou 0.5rad)", "30deg")
        valor = valores[0]
        if isinstance(valor, A.Medida):
            from ..unidades import categoria

            if categoria(valor.unidade) != "angulo":
                raise erro("um ângulo (ex. 30deg ou 0.5rad)", "30deg")
            numero = float(valor.valor)
        elif isinstance(valor, A.NumeroLit):
            numero = float(valor.valor)
        else:
            raise erro("um ângulo (ex. 30deg ou 0.5rad)", "30deg")
        if not math.isfinite(numero):
            raise erro("um ângulo finito", "30deg")
    elif especificacao == "numero_1_2":
        # Fase 10: escala — 1 ou 2 números sem unidade (finitos).
        import math

        if not (1 <= len(valores) <= 2) or not all(
                isinstance(v, A.NumeroLit) for v in valores):
            raise erro("um ou dois números (ex. escala: 1.2)",
                       "1.2")
        if not all(math.isfinite(float(v.valor)) for v in valores):
            raise erro("um número finito", "1.2")
    elif especificacao == "opacidade":
        # Fase 10: 0..1 sem unidade ou 0%..100% (nunca silencioso).
        import math

        if len(valores) != 1:
            raise erro("opacidade 0..1 ou 0%..100%", "80%")
        valor = valores[0]
        if isinstance(valor, A.Medida):
            if valor.unidade != "%":
                raise erro("opacidade 0..1 ou 0%..100%", "80%")
            numero = float(valor.valor)
            if not math.isfinite(numero) or not 0 <= numero <= 100:
                raise erro("opacidade 0%..100%", "80%")
        elif isinstance(valor, A.NumeroLit):
            numero = float(valor.valor)
            if not math.isfinite(numero) or not 0 <= numero <= 1:
                raise erro("opacidade 0..1 ou 0%..100%", "80%")
        else:
            raise erro("opacidade 0..1 ou 0%..100%", "80%")
    elif especificacao == "pivo":
        # Fase 10: pivô — 1 ou 2 valores em px (ou número) ou %.
        import math

        if not (1 <= len(valores) <= 2):
            raise erro("pivô em % ou px (ex. 50% 50%)", "50% 50%")
        for valor in valores:
            if isinstance(valor, A.Medida):
                if valor.unidade not in ("px", "%"):
                    raise erro("pivô em % ou px (ex. 50% 50%)",
                               "50% 50%")
                numero = float(valor.valor)
            elif isinstance(valor, A.NumeroLit):
                numero = float(valor.valor)
            else:
                raise erro("pivô em % ou px (ex. 50% 50%)", "50% 50%")
            if not math.isfinite(numero):
                raise erro("um pivô finito", "50% 50%")
    elif especificacao == "medidas_1_2":
        # Fase 10: número nu vale px (ex. posição { x: 100 y: 200 }).
        if not (1 <= len(valores) <= 2) or not all(
                _eh_medida(v, "comprimento") or isinstance(v, A.NumeroLit)
                for v in valores):
            raise erro("uma ou duas medidas de tamanho",
                       "800px 600px")
    elif especificacao == "medidas_2":
        if len(valores) != 2 or not all(
                _eh_medida(v, "comprimento") or isinstance(v, A.NumeroLit)
                for v in valores):
            raise erro("duas medidas (ex. posição x e y)",
                       "100px 100px")
    elif especificacao == "cor":
        if len(valores) != 1 or not (
                isinstance(valores[0], A.CorLit)
                or _eh_ref_tema(valores[0])):
            raise erro("uma cor, nome, hexadecimal ou tema.nome",
                       'vermelho, "#ff0000" ou tema.destaque')
    elif especificacao == "tempo":
        if len(valores) != 1 or not _eh_medida(valores[0], "tempo"):
            raise erro("uma duração (ex. 500ms ou 2s)", "500ms")
    elif especificacao == "origem_estado":
        if len(valores) != 1 or not isinstance(valores[0], A.Membro):
            raise erro("um caminho estado.nome (ex. para: estado.usuarios)",
                       "estado.usuarios")
        caminho = A.caminho_de_membro(valores[0])
        partes = caminho.split(".")
        if len(partes) != 2 or partes[0] != "estado":
            raise erro("um caminho estado.nome (ex. para: estado.usuarios)",
                       "estado.usuarios")
    elif especificacao == "numero":
        if len(valores) != 1 or not isinstance(
                valores[0], (A.NumeroLit, A.Medida)):
            raise erro("um número", "50%")
    elif especificacao == "booleano":
        if (len(valores) != 1 or not isinstance(valores[0], A.Booleano)):
            raise erro("verdadeiro ou falso", "verdadeiro")
    elif especificacao == "volume":
        if (len(valores) != 1 or not isinstance(valores[0], A.NumeroLit)
                or not 0 <= valores[0].valor <= 100):
            raise erro("um número de 0 a 100", "80")
    elif especificacao == "ajuste":
        validos = {"conter", "preencher", "esticar"}
        if (len(valores) != 1 or not _eh_texto(valores[0])
                or valores[0].valor.lower() not in validos):
            raise erro('conter, preencher ou esticar', '"conter"')
    elif especificacao == "tipo_grafico":
        validos = {"linha", "barras", "pizza", "area"}
        if (len(valores) != 1 or not _eh_texto(valores[0])
                or valores[0].valor.lower() not in validos):
            raise erro('linha, barras, pizza ou area', '"barras"')
    elif especificacao == "textos":
        if not valores or not all(_eh_texto(v) for v in valores):
            raise erro('um ou mais textos entre aspas', '"a" "b"')
    elif especificacao == "alinhamento":
        validos = {"esquerda", "direita", "centro", "topo", "base"}
        if (len(valores) != 1 or not _eh_texto(valores[0])
                or valores[0].valor.lower() not in validos):
            raise erro(
                f'um alinhamento ({", ".join(sorted(validos))})',
                '"centro"')
    elif especificacao == "medida_1":
        if len(valores) != 1 or not (
                _eh_medida(valores[0], "comprimento")
                or _eh_ref_tema(valores[0])):
            raise erro("uma medida ou tema.nome", "24px")
    elif especificacao == "validacao":
        validos = {"nenhum", "texto", "email", "numero"}
        if (len(valores) != 1 or not _eh_texto(valores[0])
                or valores[0].valor.lower() not in validos):
            raise erro("nenhum, texto, email ou numero", '"email"')
    elif especificacao == "indice_ativo":
        if len(valores) != 1 or not (
                isinstance(valores[0], A.NumeroLit)
                or _eh_ref_estado(valores[0])):
            raise erro("um número ou estado.nome", "0")
    elif especificacao == "referencia":
        # Fase 13: nome entre aspas ou identificador (como alvo: nome).
        if len(valores) != 1 or not isinstance(
                valores[0], (A.TextoLit, A.Ident)):
            raise erro('um nome entre aspas ou identificador (ex. visual: "x" '
                       "ou visual: x)",
                       '"caixa_visual"')
    elif especificacao == "descritor":
        # Fase 15: descritor semântico (texto ou identificador, sem vazio).
        if len(valores) != 1:
            raise erro("um descritor (ex. modo: andar)", '"andar"')
        valor = valores[0]
        if isinstance(valor, A.TextoLit):
            texto = valor.valor.strip()
        elif isinstance(valor, A.Ident):
            texto = valor.nome.strip()
        else:
            texto = ""
        if not texto:
            raise erro("um descritor não vazio (ex. modo: andar)", '"andar"')
    elif especificacao == "direcao":
        # Fase 12: orientação visual 2D (frente/costas/lados/cima/baixo).
        if (len(valores) != 1 or not _eh_texto(valores[0])
                or valores[0].valor.strip().lower()
                not in DIRECOES_PERSONAGEM):
            raise erro(
                f'uma direção ({", ".join(DIRECOES_PERSONAGEM)})',
                '"direita"')
    elif especificacao == "numero_ou_textos":
        if not valores or not (
                all(isinstance(v, (A.NumeroLit, A.Medida)) for v in valores)
                or all(_eh_texto(v) for v in valores)):
            raise erro("um número ou textos", '3 ou "a" "b"')
    elif especificacao == "caminho":
        # Fase 09: um caminho com pontos (ex. chave: item.id).
        if len(valores) != 1 or not isinstance(valores[0], A.Membro):
            raise erro("um caminho com pontos (ex. item.id)",
                       "item.id")
    elif especificacao == "origem_dados":
        # Fase 05: origem geral — caminho (dados.|estado.) ou expressão
        # derivada (Binaria) ou literal estático. Chaves de estado são
        # checadas no pós-passe de validar() (precisa do programa).
        if len(valores) != 1:
            raise erro("uma origem (ex. dados.sistema.cpu)",
                       "dados.sistema.cpu")
        _validar_origem(valores[0], erro, fontes_remotas)
    elif especificacao == "ligado_estado":
        # Fase 05: two-way binding com estado; Fase 09: também local.*
        # (ligação da linha/instância, resolvida com contexto).
        if (len(valores) != 1 or not isinstance(valores[0], A.Membro)):
            raise erro("um caminho estado.nome ou local.nome "
                       "(ex. ligado_a: estado.nome)",
                       "estado.nome")
        caminho = A.caminho_de_membro(valores[0])
        partes = caminho.split(".")
        if len(partes) != 2 or partes[0] not in ("estado", "local"):
            raise erro("um caminho estado.nome ou local.nome "
                       "(dados é somente leitura)",
                       "estado.nome")
    elif especificacao == "caminho":
        # Fase 09: um caminho com pontos (ex. chave: item.id).
        if len(valores) != 1 or not isinstance(valores[0], A.Membro):
            raise erro("um caminho com pontos (ex. item.id)",
                       "item.id")


def _validar_origem(expr: object, erro, fontes_remotas=frozenset()) -> None:
    """Forma da origem: Membro dados.|estado., Binaria derivada ou literal."""
    if isinstance(expr, A.Binaria):
        if expr.op == "nao":
            _validar_origem(expr.direita, erro, fontes_remotas)
            return
        _validar_origem(expr.esquerda, erro, fontes_remotas)
        _validar_origem(expr.direita, erro, fontes_remotas)
        return
    if isinstance(expr, (A.TextoLit, A.NumeroLit, A.Booleano)):
        return
    if isinstance(expr, A.Ident) and expr.nome == "item":
        # Fase 09: linha inteira (só faz sentido em modelo; parser checou).
        return
    if isinstance(expr, A.ListaLit):
        for item in expr.itens:
            _validar_origem(item, erro, fontes_remotas)
        return
    if isinstance(expr, A.Chamada):
        # Fase 09: funções em origem (ex. total(estado.preco, 2)).
        for arg in expr.args:
            _validar_origem(arg, erro, fontes_remotas)
        return
    if not isinstance(expr, A.Membro):
        raise erro("um caminho (dados.fonte.campo, estado.nome) ou "
                   "expressão com eles", "dados.sistema.cpu")
    caminho = A.caminho_de_membro(expr)
    partes = caminho.split(".")
    if partes[0] == "dados":
        if len(partes) < 3:
            raise erro("um caminho dados.fonte.campo "
                       "(ex. dados.sistema.cpu)", "dados.sistema.cpu")
        from ..dados import REGISTRO_FONTES

        conhecidas = set(REGISTRO_FONTES) | set(fontes_remotas)
        if partes[1] not in conhecidas:
            parecidas = sugerir(partes[1], sorted(conhecidas))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'Fonte de dados desconhecida: "{partes[1]}".{dica} '
                f"Fontes válidas: {', '.join(sorted(conhecidas))}.",
                linha=expr.linha,
                exemplo="origem: dados.sistema.cpu",
            )
    elif partes[0] == "estado":
        if len(partes) < 2:
            raise erro("um caminho estado.nome (ex. estado.contador)",
                       "estado.contador")
    elif partes[0] in ("local", "item"):
        # Fase 09: contexto dinâmico (parser já garantiu o escopo).
        if len(partes) < 2:
            raise erro("um caminho local.nome ou item.campo",
                       "local.favorito")
    else:
        raise erro("um caminho dados.fonte.campo ou estado.nome",
                   "dados.sistema.cpu")


def validar_propriedade(prop: A.Propriedade, tabela: dict,
                         onde: str, fontes_remotas=frozenset()) -> None:
    if prop.nome not in tabela:
        parecidas = sugerir(prop.nome, sorted(tabela))
        dica = f" Você quis dizer: {', '.join(parecidas)}?" if parecidas else ""
        raise ErroSemantico(
            f'Propriedade desconhecida em {onde}: "{prop.nome}".{dica} '
            f'Propriedades válidas: {", ".join(sorted(tabela))}.',
            linha=prop.linha,
            exemplo=f"{sorted(tabela)[0]}: ...",
        )
    especificacao, exemplo = tabela[prop.nome]
    validar_valor(especificacao, prop.valores, prop.nome, prop.linha,
                  fontes_remotas)


def validar_evento_no(ev: A.Evento, onde: str) -> None:
    if ev.nome not in EVENTOS_SUPORTADOS:
        parecidos = sugerir(ev.nome, sorted(EVENTOS_SUPORTADOS))
        dica = f" Você quis dizer: {', '.join(parecidos)}?" if parecidos else ""
        raise ErroSemantico(
            f'Evento desconhecido em {onde}: "{ev.nome}".{dica} '
            f"Eventos válidos: {', '.join(sorted(EVENTOS_SUPORTADOS))}.",
            linha=ev.linha,
            exemplo="quando clicar {\n    mostrar(\"Olá!\")\n}",
        )
    validar_bloco(ev.bloco)


def validar_comando(cmd: object) -> None:
    if isinstance(cmd, A.Acao):
        # Fase 09: "executar" é o despachante de ações/funções do usuário.
        if cmd.nome == "executar":
            return
        if cmd.nome not in ACOES:
            parecidas = sugerir(cmd.nome, sorted(ACOES))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'Ação desconhecida: "{cmd.nome}".{dica} '
                f"Ações válidas: {', '.join(sorted(ACOES))}.",
                linha=cmd.linha,
                exemplo='mostrar("Olá, mundo!")',
            )
    elif isinstance(cmd, A.Se):
        validar_bloco(cmd.entao)
        if cmd.senao is not None:
            validar_bloco(cmd.senao)
    elif isinstance(cmd, A.Repetir):
        validar_bloco(cmd.bloco)
    elif isinstance(cmd, A.Retornar):
        pass
    elif isinstance(cmd, A.Atribuicao):
        # Forma checada aqui; chaves de estado no pós-passe (validar()).
        alvo = cmd.alvo
        if isinstance(alvo, A.Ident):
            return
        caminho = A.caminho_de_membro(alvo)
        partes = caminho.split(".")
        if partes[0] not in ("estado", "dados"):
            raise ErroSemantico(
                f'Atribuição inválida: "{caminho}". Use estado.nome.',
                linha=cmd.linha,
                exemplo="estado.contador = 1",
            )
        if partes[0] == "dados":
            raise ErroSemantico(
                "Dados são somente leitura: atribua a estado.",
                linha=cmd.linha,
                exemplo="estado.copia = dados.sistema.cpu",
            )


def validar_bloco(bloco: A.Bloco) -> None:
    for cmd in bloco.comandos:
        validar_comando(cmd)


def validar_componente(comp, nomes_funcoes: set[str],
                        fontes_remotas=frozenset(),
                        itens: dict | None = None) -> None:
    if isinstance(comp, A.Instancia):
        raise ErroSemantico(
            f'Instância "{comp.nome}" não expandida (uso interno: rode '
            "expandir_componentes antes de validar).",
            linha=comp.linha,
        )
    if isinstance(comp, A.Personagem):
        # Fase 12: personagem em janela/grupo/instância.
        validar_personagem(comp, nomes_funcoes, fontes_remotas, itens)
        return
    onde = f'{comp.tipo} "{comp.nome}"'
    for prop in comp.propriedades:
        validar_propriedade(prop, PROPS_COMPONENTE, onde, fontes_remotas)
    for ev in comp.eventos:
        validar_evento_no(ev, onde)
    for filho in comp.filhos:
        validar_componente(filho, nomes_funcoes, fontes_remotas, itens)
    modelo = getattr(comp, "modelo", [])
    if modelo and comp.tipo != "lista":
        raise ErroSemantico(
            f'{onde}: bloco "modelo" só existe dentro de lista.',
            linha=comp.linha,
            exemplo='lista itens {\n    origem: estado.itens\n'
                     '    modelo {\n        texto nome {\n'
                     '            texto: item.nome\n        }\n    }\n}',
        )
    for item in modelo:
        validar_componente(item, nomes_funcoes, fontes_remotas, itens)
    modelo = getattr(comp, "modelo", [])
    if modelo and comp.tipo != "lista":
        raise ErroSemantico(
            f'{onde}: bloco "modelo" só existe dentro de lista.',
            linha=comp.linha,
            exemplo='lista itens {\n    origem: estado.itens\n'
                     '    modelo {\n        texto nome {\n'
                     '            texto: item.nome\n        }\n    }\n}',
        )
    for item in modelo:
        validar_componente(item, nomes_funcoes, fontes_remotas, itens)


def _validar_prop_personagem(prop, tabela: dict, onde: str,
                             fontes_remotas=frozenset()) -> None:
    """Propriedade de personagem/parte (+ `asset_<nome>`: variante)."""
    if prop.nome.startswith("asset_"):
        resto = prop.nome[len("asset_"):]
        if not resto:
            raise ErroSemantico(
                f'Variante sem nome em {onde}: "{prop.nome}".',
                linha=prop.linha,
                exemplo='asset_fechado: "olho-fechado.png"',
            )
        especificacao, exemplo = ("texto",
                                  f'{prop.nome}: "arquivo.png"')
        validar_valor(especificacao, prop.valores, prop.nome, prop.linha,
                      fontes_remotas)
        return
    validar_propriedade(prop, tabela, onde, fontes_remotas)


def _partes_nomes(boneco) -> dict[str, object]:
    """Todas as partes (aninhadas): nome → Parte."""
    achadas: dict[str, object] = {}

    def visitar(parte) -> None:
        achadas[parte.nome] = parte
        for sub in parte.partes:
            visitar(sub)

    for parte in boneco.partes:
        visitar(parte)
    return achadas


def validar_personagem(boneco, nomes_funcoes: set[str],
                        fontes_remotas=frozenset(),
                        itens: dict | None = None) -> None:
    """Fase 12: root, partes, juntas, limites, poses e referências."""
    onde = f'personagem "{boneco.nome}"'
    for prop in boneco.propriedades:
        _validar_prop_personagem(prop, PROPS_PERSONAGEM, onde,
                                 fontes_remotas)
    _validar_posse_equip(boneco, onde, itens)
    for cap in boneco.capacidades:
        _validar_capacidade(cap, f'capacidade de {onde}', itens)
    vistos: set[str] = set()
    for parte in boneco.partes:
        if parte.nome in vistos:
            parecidas = sugerir(parte.nome, sorted(vistos))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'Parte "{parte.nome}" repetida em {onde}.{dica}',
                linha=parte.linha,
            )
        vistos.add(parte.nome)
        _validar_parte(parte, onde, vistos, nomes_funcoes, fontes_remotas,
                       itens)
    nomes_partes = _partes_nomes(boneco)
    vistos_poses: set[str] = set()
    for pose in boneco.poses:
        rotulo = "expressão" if pose.expressao else "pose"
        if pose.nome in vistos_poses:
            raise ErroSemantico(
                f'{rotulo} "{pose.nome}" repetida em {onde}.',
                linha=pose.linha,
            )
        vistos_poses.add(pose.nome)
        _validar_pose(pose, boneco.nome, nomes_partes)
    for filho in boneco.filhos:
        validar_componente(filho, nomes_funcoes, fontes_remotas, itens)


def _validar_parte(parte, onde_personagem: str, vistos: set[str],
                   nomes_funcoes: set[str], fontes_remotas=frozenset(),
                   itens: dict | None = None) -> None:
    onde = f'parte "{parte.nome}" de {onde_personagem}'
    for prop in parte.propriedades:
        _validar_prop_personagem(prop, PROPS_PARTE, onde, fontes_remotas)
    for cap in parte.capacidades:
        _validar_capacidade(cap, f'capacidade de {onde}', itens)
    limites = {}
    for prop in parte.propriedades:
        if prop.nome in ("limite_min", "limite_max"):
            limites[prop.nome] = prop.valores[0]
    if "limite_min" in limites and "limite_max" in limites:
        minimo = _angulo_para_graus_sem(limites["limite_min"])
        maximo = _angulo_para_graus_sem(limites["limite_max"])
        if minimo > maximo:
            raise ErroSemantico(
                f'{onde}: limite_min ({minimo:g}°) maior que limite_max '
                f"({maximo:g}°).",
                linha=parte.linha,
                exemplo="limite_min: 0deg\nlimite_max: 145deg",
            )
    for sub in parte.partes:
        if sub.nome in vistos:
            raise ErroSemantico(
                f'Parte "{sub.nome}" repetida em {onde_personagem} '
                "(nomes de partes são únicos no personagem).",
                linha=sub.linha,
            )
        vistos.add(sub.nome)
        _validar_parte(sub, onde_personagem, vistos, nomes_funcoes,
                       fontes_remotas, itens)
    for filho in parte.filhos:
        validar_componente(filho, nomes_funcoes, fontes_remotas, itens)


def _angulo_para_graus_sem(valor: object) -> float:
    """Medida de ângulo validada → graus (só graus/deg/rad/número)."""
    import math

    if isinstance(valor, A.Medida):
        numero = float(valor.valor)
        if valor.unidade == "rad":
            numero = math.degrees(numero)
    elif isinstance(valor, A.NumeroLit):
        numero = float(valor.valor)
    else:
        numero = 0.0
    return numero


# ----- Fase 14: Items + Capability System (declarativo, sem execução) -----

REQUERIMENTOS_CAPACIDADE = ("requer_equipado", "requer_possuido",
                            "requer_presente", "requer_proximo",
                            "requer_tag", "requer_categoria", "requer_tipo",
                            "requer_estado", "requer_capacidade")


def _texto_valor(prop) -> str | None:
    if prop.valores and isinstance(prop.valores[0], A.TextoLit):
        return prop.valores[0].valor
    return None


def _validar_item(item, tipos_janela: dict[str, str]) -> None:
    """Fase 14: item semântico (props, vistas, capacidades)."""
    onde = f'item "{item.nome}"'
    for prop in item.propriedades:
        _validar_prop_personagem(prop, PROPS_ITEM, onde)
    visual = None
    for prop in item.propriedades:
        if prop.nome == "visual":
            visual = _texto_valor(prop) or (
                prop.valores[0].nome
                if prop.valores and isinstance(prop.valores[0], A.Ident)
                else None)
    if visual is not None and visual not in tipos_janela:
        parecidas = sugerir(visual, sorted(tipos_janela))
        dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                if parecidas else "")
        raise ErroSemantico(
            f'Visual "{visual}" não encontrado em {onde}.{dica}',
            linha=item.linha,
        )
    vistos: set[str] = set()
    for cap in item.capacidades:
        if cap.nome in vistos:
            raise ErroSemantico(
                f'Capacidade "{cap.nome}" repetida em {onde}.',
                linha=cap.linha,
            )
        vistos.add(cap.nome)
        _validar_capacidade(cap, f'capacidade de {onde}', None)


def _validar_capacidade(cap, onde: str, itens: dict | None) -> None:
    """Fase 14: params únicos, props válidas, refs de item existentes."""
    vistos_param: set[str] = set()
    for param in cap.parametros:
        if param.nome in vistos_param:
            raise ErroSemantico(
                f'Parâmetro "{param.nome}" repetido na capacidade '
                f'"{cap.nome}" de {onde}.',
                linha=param.linha,
            )
        vistos_param.add(param.nome)
    raio_visto = False
    for prop in cap.propriedades:
        if prop.nome == "raio":
            raio_visto = True
            _validar_raio(prop, onde, cap.nome)
            continue
        validar_propriedade(prop, PROPS_CAPACIDADE, onde)
    if raio_visto and not any(
            p.nome == "requer_proximo" for p in cap.propriedades):
        raise ErroSemantico(
            f'Capacidade "{cap.nome}" de {onde} tem "raio" sem '
            '"requer_proximo".',
            linha=cap.linha,
        )
    if itens is not None:
        for prop in cap.propriedades:
            if prop.nome in ("requer_equipado", "requer_possuido"):
                ref = _texto_valor(prop)
                if ref is not None and ref not in itens:
                    parecidas = sugerir(ref, sorted(itens))
                    dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                            if parecidas else "")
                    raise ErroSemantico(
                        f'Item "{ref}" não definido ({prop.nome} na '
                        f'capacidade "{cap.nome}" de {onde}).{dica}',
                        linha=prop.linha,
                    )


def _validar_raio(prop, onde: str, nome_cap: str) -> None:
    """Raio: número positivo ou medida px (sem dropdown de unidades)."""
    if not prop.valores:
        raise ErroSemantico(
            f'Capacidade "{nome_cap}" de {onde}: "raio" espera valor.',
            linha=prop.linha,
            exemplo="raio: 200px",
        )
    valor = prop.valores[0]
    if isinstance(valor, A.NumeroLit):
        numero = float(valor.valor)
    elif isinstance(valor, A.Medida) and valor.unidade == "px":
        numero = float(valor.valor)
    else:
        raise ErroSemantico(
            f'Capacidade "{nome_cap}" de {onde}: "raio" espera número '
            "positivo ou px.",
            linha=prop.linha,
            exemplo="raio: 200px",
        )
    import math

    if not math.isfinite(numero) or numero <= 0:
        raise ErroSemantico(
            f'Capacidade "{nome_cap}" de {onde}: "raio" precisa ser '
            "positivo.",
            linha=prop.linha,
            exemplo="raio: 200px",
        )


def _nomes_textos(prop) -> list[str]:
    """Valores texto de possui/equipa (TextoLit)."""
    return [v.valor for v in prop.valores if isinstance(v, A.TextoLit)]


def _validar_posse_equip(boneco, onde: str,
                         itens: dict | None) -> None:
    """Fase 14: possui/equipa referenciam definições; anexo existe."""
    if itens is None:
        return
    for prop in boneco.propriedades:
        if prop.nome not in ("possui", "equipa"):
            continue
        for ref in _nomes_textos(prop):
            if ref not in itens:
                parecidas = sugerir(ref, sorted(itens))
                dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                        if parecidas else "")
                raise ErroSemantico(
                    f'Item "{ref}" não definido ({prop.nome} em {onde}).'
                    f'{dica}',
                    linha=prop.linha,
                )
    partes = _partes_nomes(boneco)
    for prop in boneco.propriedades:
        if prop.nome != "equipa":
            continue
        for ref in _nomes_textos(prop):
            item = itens.get(ref)
            if item is None:
                continue
            anexo = None
            for prop_item in item.propriedades:
                if prop_item.nome == "anexo":
                    anexo = _texto_valor(prop_item)
            if anexo is not None and anexo not in partes:
                parecidas = sugerir(anexo, sorted(partes))
                dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                        if parecidas else "")
                raise ErroSemantico(
                    f'Parte "{anexo}" não existe em {onde} (anexo do item '
                    f'"{ref}").{dica}',
                    linha=prop.linha,
                )


def _validar_pose(pose, nome_personagem: str,
                  nomes_partes: dict[str, object]) -> None:
    rotulo = "expressão" if pose.expressao else "pose"
    onde = f'{rotulo} "{pose.nome}" do personagem "{nome_personagem}"'
    for entrada in pose.entradas:
        if entrada.parte not in nomes_partes:
            parecidas = sugerir(entrada.parte, sorted(nomes_partes))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f"Parte '{entrada.parte}' não encontrada em {onde}.{dica}",
                linha=entrada.linha,
            )
        vistos: set[str] = set()
        for prop in entrada.propriedades:
            if prop.nome in vistos:
                raise ErroSemantico(
                    f'"{prop.nome}" repetido para "{entrada.parte}" '
                    f"em {onde}.",
                    linha=prop.linha,
                )
            vistos.add(prop.nome)
            validar_propriedade(prop, POSE_PROPS, onde)


def _nomes_da_janela(janela: A.Janela) -> set[str]:
    nomes = {janela.nome}
    pilha = list(janela.componentes)
    while pilha:
        comp = pilha.pop()
        if isinstance(comp, A.ItemDef):
            continue  # Fase 14: itens não são alvos visuais
        if isinstance(comp, A.Personagem):
            # Fase 12: personagem/partes são alvos de animação e pose.
            nomes.add(comp.nome)
            pilha.extend(comp.filhos)
            pilha.extend(comp.partes)
            continue
        if isinstance(comp, A.Parte):
            nomes.add(comp.nome)
            pilha.extend(comp.filhos)
            pilha.extend(comp.partes)
            continue
        nomes.add(comp.nome)
        pilha.extend(comp.filhos)
        pilha.extend(getattr(comp, "modelo", []))
    return nomes


def _todas_partes(boneco) -> list:
    """Todas as partes aninhadas (para nomes e validação)."""
    saida: list = []

    def visitar(parte) -> None:
        saida.append(parte)
        for sub in parte.partes:
            visitar(sub)

    for parte in boneco.partes:
        visitar(parte)
    return saida


def _unidades_de_valor_anim(valor: object) -> list:
    """Unidades de um lado (de/para) de chave de animação."""
    if isinstance(valor, tuple) and valor and isinstance(valor[0], tuple):
        return [u for u, _ in valor]  # par ((u,v),(u,v))
    return [valor[0]]  # escalar (u, v)


def _permitidas_anim(prop: str) -> set:
    # Fase 10: cada propriedade aceita suas unidades (posição/tamanho
    # em px; rotação em graus/deg/rad/número; escala sem unidade;
    # opacidade em número/%). "px" vindo de número nu é o curinga.
    return {"posicao": {"px"}, "tamanho": {"px"},
            "rotacao": {"px", "graus", "deg", "rad"},
            "escala": {"px"}, "opacidade": {"px", "%"}}[prop]


def _erro_unidade_anim(onde: str, prop: str, unidade: str,
                       linha: int) -> ErroSemantico:
    if prop in ("posicao", "tamanho"):
        return ErroSemantico(
            f'{onde}: animação de "{prop}" usa pixels '
            f"(recebido {unidade!r}).",
            linha=linha,
            exemplo="posição: 0px 0px → 100px 50px",
        )
    return ErroSemantico(
        f'{onde}: "{prop}" não aceita {unidade!r} em animação.',
        linha=linha,
        exemplo="posição: 0px 0px → 100px 50px",
    )


def _validar_anim_chaves(anim, onde: str) -> None:
    from ..animacao.motor import PROPS_ANIMAVEIS

    for chave in anim.chaves:
        if chave.propriedade not in PROPS_ANIMAVEIS:
            raise ErroSemantico(
                f'{onde}: "{chave.propriedade}" não é animável. '
                f"Válidas: {', '.join(PROPS_ANIMAVEIS)}.",
                linha=chave.linha,
            )
        permitidas = _permitidas_anim(chave.propriedade)
        for lado in ("de", "para"):
            valor = getattr(chave, lado)
            if valor is None:
                continue
            for unidade in _unidades_de_valor_anim(valor):
                if unidade not in permitidas:
                    raise _erro_unidade_anim(onde, chave.propriedade,
                                             unidade, chave.linha)


def _validar_anim_keyframes(anim, onde: str) -> None:
    from ..animacao.motor import PROPS_ANIMAVEIS

    if not anim.keyframes:
        return
    vistos: set[float] = set()
    for quadro in sorted(anim.keyframes, key=lambda k: k.percent):
        if not 0.0 <= quadro.percent <= 100.0:
            raise ErroSemantico(
                f"{onde}: quadro {quadro.percent:g}% fora de 0%..100%.",
                linha=quadro.linha,
                exemplo="50% {\n    posição: 300px 200px\n}",
            )
        if quadro.percent in vistos:
            raise ErroSemantico(
                f"{onde}: quadro {quadro.percent:g}% repetido.",
                linha=quadro.linha,
            )
        vistos.add(quadro.percent)
        if not quadro.chaves:
            raise ErroSemantico(
                f"{onde}: quadro {quadro.percent:g}% vazio (sem chaves).",
                linha=quadro.linha,
                exemplo="50% {\n    posição: 300px 200px\n}",
            )
        for chave in quadro.chaves:
            if chave.propriedade not in PROPS_ANIMAVEIS:
                raise ErroSemantico(
                    f"{onde}: \"{chave.propriedade}\" não é animável. "
                    f"Válidas: {', '.join(PROPS_ANIMAVEIS)}.",
                    linha=chave.linha,
                )
            permitidas = _permitidas_anim(chave.propriedade)
            for lado in ("de", "para"):
                valor = getattr(chave, lado)
                if valor is None:
                    continue
                for unidade in _unidades_de_valor_anim(valor):
                    if unidade not in permitidas:
                        raise _erro_unidade_anim(onde, chave.propriedade,
                                                 unidade, chave.linha)
    if len(anim.keyframes) < 2:
        raise ErroSemantico(
            f"{onde}: keyframes precisam de ao menos 2 quadros "
            "(ex. 0% e 100%).",
            linha=anim.linha,
            exemplo="0% {\n    posição: 100px 100px\n}\n"
                    "100% {\n    posição: 500px 100px\n}",
        )
    das_chaves = {c.propriedade for c in anim.chaves}
    dos_quadros = {c.propriedade for q in anim.keyframes for c in q.chaves}
    ambos = sorted(das_chaves & dos_quadros)
    if ambos:
        raise ErroSemantico(
            f"{onde}: {', '.join(ambos)} em chaves e keyframes ao mesmo "
            "tempo (disputa). Use um dos dois.",
            linha=anim.linha,
        )
    for quadro in anim.keyframes:
        for chave in quadro.chaves:
            if chave.de is not None:
                raise ErroSemantico(
                    f"{onde}: quadro {quadro.percent:g}% guarda estado, "
                    "não transição (sem →).",
                    linha=chave.linha,
                    exemplo="50% {\n    posição: 300px 200px\n}",
                )
    if anim.relativo and anim.keyframes:
        raise ErroSemantico(
            f"{onde}: relativo vale para chaves (deslocamento); "
            "keyframes guardam posições absolutas.",
            linha=anim.linha,
        )
    if anim.fisica is not None and anim.keyframes:
        raise ErroSemantico(
            f"{onde}: fisica (dinâmica) usa chaves de/para; "
            "keyframes usam curva.",
            linha=anim.linha,
        )


def validar_animacao(anim: A.AnimacaoDef, nomes: set[str],
                     nomes_anims: set[str]) -> None:
    from ..animacao import MOVIMENTOS
    from ..animacao.motor import PROPS_ANIMAVEIS

    onde = f'animação "{anim.nome}"'
    if not anim.alvo:
        raise ErroSemantico(
            f'{onde} precisa de alvo (ex. alvo: nome_do_componente).',
            linha=anim.linha,
            exemplo=f'{onde} {{\n    alvo: ...\n}}',
        )
    if anim.alvo not in nomes:
        parecidos = sugerir(anim.alvo, sorted(nomes))
        dica = (f" Você quis dizer: {', '.join(parecidos)}?"
                if parecidos else "")
        raise ErroSemantico(
            f'{onde}: alvo {anim.alvo!r} não existe na janela.{dica}',
            linha=anim.linha,
        )
    if not anim.chaves and not anim.keyframes and anim.movimento not in (
            "aparecer", "desaparecer"):
        raise ErroSemantico(
            f'{onde} não anima nada. Adicione ao menos uma propriedade '
            "(posição, tamanho, escala, rotação, opacidade) ou keyframes "
            "(0% { ... }).",
            linha=anim.linha,
            exemplo="posição: 0px 0px → 100px 50px",
        )
    _validar_anim_chaves(anim, onde)
    _validar_anim_keyframes(anim, onde)
    if anim.movimento not in MOVIMENTOS:
        parecidos = sugerir(anim.movimento, sorted(MOVIMENTOS))
        dica = (f" Você quis dizer: {', '.join(parecidos)}?"
                if parecidos else "")
        raise ErroSemantico(
            f"{onde}: movimento desconhecido: {anim.movimento!r}.{dica} "
            f"Válidos: {', '.join(sorted(MOVIMENTOS))}.",
            linha=anim.linha,
        )
    if anim.inicio not in ("automatico", "manual"):
        raise ErroSemantico(
            f'{onde}: início deve ser "automatico" ou "manual".',
            linha=anim.linha,
        )
    if anim.depois is not None and anim.depois not in nomes_anims:
        raise ErroSemantico(
            f'{onde}: "depois" aponta para animação inexistente '
            f"{anim.depois!r}.",
            linha=anim.linha,
        )
    # Fase 11: composição e dinâmica do Motion Core.
    from ..animacao.motion import FISICAS_MOTION, MODOS_MOTION

    if anim.modo not in MODOS_MOTION:
        raise ErroSemantico(
            f'{onde}: modo inválido: {anim.modo!r}. '
            f'Válidos: {", ".join(MODOS_MOTION)}.',
            linha=anim.linha,
            exemplo="modo: ping_pong",
        )
    if not isinstance(anim.voltas, int) or anim.voltas < 0:
        raise ErroSemantico(
            f'{onde}: "voltas" precisa de inteiro ≥ 0.',
            linha=anim.linha,
            exemplo="voltas: 1",
        )
    if not isinstance(anim.relativo, bool):
        raise ErroSemantico(
            f'{onde}: "relativo" espera verdadeiro ou falso.',
            linha=anim.linha,
            exemplo="relativo: verdadeiro",
        )
    if anim.fisica is not None:
        if anim.fisica not in FISICAS_MOTION:
            raise ErroSemantico(
                f'{onde}: fisica inválida: {anim.fisica!r}. '
                f'Válidas: {", ".join(FISICAS_MOTION)}.',
                linha=anim.linha,
                exemplo="fisica: mola",
            )
        import math

        for campo in ("rigidez", "amortecimento", "massa"):
            numero = float(getattr(anim, campo))
            if not math.isfinite(numero) or numero <= 0:
                raise ErroSemantico(
                    f'{onde}: "{campo}" precisa de número positivo.',
                    linha=anim.linha,
                )
    if anim.ao_terminar is not None:
        validar_bloco(anim.ao_terminar)
    if anim.ao_comecar is not None:
        validar_bloco(anim.ao_comecar)
    if anim.ao_cancelar is not None:
        validar_bloco(anim.ao_cancelar)


def validar_estado(bloco) -> set[str]:
    """Valida o bloco estado; retorna as chaves declaradas."""
    vistos: set[str] = set()
    for prop in bloco.propriedades:
        if prop.nome in vistos:
            raise ErroSemantico(
                f'Estado "{prop.nome}" declarado duas vezes.',
                linha=prop.linha,
            )
        vistos.add(prop.nome)
        if len(prop.valores) != 1 or not _eh_literal_estado(prop.valores[0]):
            raise ErroSemantico(
                f'Estado "{prop.nome}" precisa de um valor simples '
                "(texto, número, verdadeiro/falso ou lista deles).",
                linha=prop.linha,
                exemplo=f"{prop.nome}: 0",
            )
    return vistos


def _eh_literal_estado(valor: object) -> bool:
    if isinstance(valor, (A.TextoLit, A.NumeroLit, A.Booleano)):
        return True
    if isinstance(valor, A.ListaLit):
        return all(isinstance(item, (A.TextoLit, A.NumeroLit, A.Booleano))
                   for item in valor.itens)
    return False


def _iterar_blocos(programa: A.Programa):
    """Todos os blocos de comandos (eventos, animações, funções, ações)."""

    def de_componente(comp):
        if isinstance(comp, A.ItemDef):
            return  # Fase 14: itens não têm blocos de comandos
        if isinstance(comp, A.Personagem):
            # Fase 12: visuais soltos do personagem (sem eventos próprios).
            for filho in comp.filhos:
                yield from de_componente(filho)
            return
        if isinstance(comp, A.Parte):
            for filho in comp.filhos:
                yield from de_componente(filho)
            return
        for ev in comp.eventos:
            yield ev.bloco
        for filho in comp.filhos:
            yield from de_componente(filho)
        for modelo in getattr(comp, "modelo", []):
            yield from de_componente(modelo)

    for janela in list(programa.janelas) + list(programa.telas):
        for ev in janela.eventos:
            yield ev.bloco
        for comp in janela.componentes:
            yield from de_componente(comp)
        for anim in janela.animacoes:
            if anim.ao_terminar is not None:
                yield anim.ao_terminar
            if anim.ao_comecar is not None:
                yield anim.ao_comecar
            if anim.ao_cancelar is not None:
                yield anim.ao_cancelar
    for funcao in programa.funcoes:
        yield funcao.bloco
    for acao in programa.acoes:
        yield acao.bloco


def _iterar_propriedades_origem(programa: A.Programa):
    def de_parte(parte):
        for prop in parte.propriedades:
            if prop.nome in ("origem", "ligado_a"):
                yield prop
        for sub in parte.partes:
            yield from de_parte(sub)
        for filho in parte.filhos:
            yield from de_componente(filho)

    def de_componente(comp):
        if isinstance(comp, A.ItemDef):
            return  # Fase 14: itens não têm origem/ligado_a
        if isinstance(comp, A.Personagem):
            # Fase 12: origem/ligado_a no root, partes e visuais.
            for prop in comp.propriedades:
                if prop.nome in ("origem", "ligado_a"):
                    yield prop
            for parte in comp.partes:
                yield from de_parte(parte)
            for filho in comp.filhos:
                yield from de_componente(filho)
            return
        for prop in comp.propriedades:
            if prop.nome in ("origem", "ligado_a"):
                yield prop
        for filho in comp.filhos:
            yield from de_componente(filho)
        for modelo in getattr(comp, "modelo", []):
            yield from de_componente(modelo)

    for janela in list(programa.janelas) + list(programa.telas):
        for comp in janela.componentes:
            yield from de_componente(comp)


def _chaves_estado_em(expr: object) -> set[str]:
    """Chaves estado.* usadas numa expressão (para o pós-passe)."""
    if isinstance(expr, A.Membro):
        caminho = A.caminho_de_membro(expr)
        partes = caminho.split(".")
        if partes[0] == "estado" and len(partes) >= 2:
            return {partes[1]}
        achadas: set[str] = set()
        return achadas | _chaves_estado_em(expr.base)
    if isinstance(expr, A.Binaria):
        return (_chaves_estado_em(expr.esquerda)
                | _chaves_estado_em(expr.direita))
    if isinstance(expr, A.ListaLit):
        achadas: set[str] = set()
        for item in expr.itens:
            achadas |= _chaves_estado_em(item)
        return achadas
    if isinstance(expr, A.Chamada):
        achadas = set()
        for arg in expr.args:
            achadas |= _chaves_estado_em(arg)
        return achadas
    return set()


def validar_chaves_estado(programa: A.Programa, chaves: set[str],
                           extras: set[str] | None = None) -> None:
    """Pós-passe: toda chave estado.* usada precisa estar declarada.

    extras: chaves implícitas (alvos de fontes remotas/arquivo, criadas
    pelo runtime via garantir).
    """
    declaradas = set(chaves) | set(extras or ())

    def conferir(nome: str, linha: int, onde: str) -> None:
        if nome not in declaradas:
            parecidas = sugerir(nome, sorted(declaradas))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'{onde}: estado "{nome}" não declarado.{dica} '
                "Declare no bloco estado { ... }.",
                linha=linha,
                exemplo=f"estado {{\n    {nome}: 0\n}}",
            )

    def de_comando(cmd) -> None:
        if isinstance(cmd, A.Atribuicao):
            for chave in _chaves_estado_em(cmd.alvo):
                conferir(chave, cmd.linha, "Atribuição")
            for chave in _chaves_estado_em(cmd.valor):
                conferir(chave, cmd.linha, "Atribuição")
        elif isinstance(cmd, A.Se):
            for chave in _chaves_estado_em(cmd.condicao):
                conferir(chave, cmd.linha, "Condição")
            for sub in cmd.entao.comandos:
                de_comando(sub)
            if cmd.senao is not None:
                for sub in cmd.senao.comandos:
                    de_comando(sub)
        elif isinstance(cmd, A.Repetir):
            for sub in cmd.bloco.comandos:
                de_comando(sub)
        elif isinstance(cmd, A.Acao):
            for arg in cmd.args:
                for chave in _chaves_estado_em(arg):
                    conferir(chave, cmd.linha, "Ação")

    for prop in _iterar_propriedades_origem(programa):
        for valor in prop.valores:
            for chave in _chaves_estado_em(valor):
                conferir(chave, prop.linha,
                         f'Propriedade "{prop.nome}"')
    for fonte in programa.fontes:
        for bloco in fonte.blocos:
            if bloco.nome != "corpo":
                continue
            for prop in bloco.propriedades:
                for valor in prop.valores:
                    for chave in _chaves_estado_em(valor):
                        conferir(chave, prop.linha,
                                 f'Corpo da fonte "{fonte.nome}"')
    for bloco in _iterar_blocos(programa):
        for cmd in bloco.comandos:
            de_comando(cmd)


PROPS_FONTE = {
    "url": ("texto", 'url: "https://api.exemplo.com/usuarios"'),
    "metodo": ("texto", 'metodo: "GET"'),
    "método": ("texto", 'metodo: "GET"'),
    "tempo_limite": ("tempo", "tempo_limite: 5s"),
    "atualizar": ("tempo", "atualizar: 10s"),
    "arquivo": ("texto", 'arquivo: "dados/config.json"'),
    "para": ("origem_estado", "para: estado.usuarios"),
}

METODOS_HTTP = ("GET", "POST", "PUT", "PATCH", "DELETE")


def validar_fonte(fonte: A.FonteDef) -> dict:
    """Valida um bloco dados; retorna config resolvida para o runtime."""
    onde = f'fonte "{fonte.nome}"'
    props: dict[str, object] = {}
    for prop in fonte.propriedades:
        if prop.nome not in PROPS_FONTE:
            parecidas = sugerir(prop.nome, sorted(PROPS_FONTE))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'Propriedade desconhecida em {onde}: "{prop.nome}".{dica} '
                f'Válidas: {", ".join(sorted(PROPS_FONTE))}.',
                linha=prop.linha,
            )
        especificacao, _exemplo = PROPS_FONTE[prop.nome]
        validar_valor(especificacao, prop.valores, prop.nome, prop.linha)
        props[prop.nome] = prop.valores[0]
    blocos: dict[str, list] = {}
    for bloco in fonte.blocos:
        if bloco.nome not in ("cabecalhos", "parametros", "corpo"):
            raise ErroSemantico(
                f'Bloco desconhecido em {onde}: "{bloco.nome}". Válidos: '
                "cabecalhos, parametros, corpo.",
                linha=bloco.linha,
            )
        if bloco.nome in blocos:
            raise ErroSemantico(
                f'Bloco "{bloco.nome}" repetido em {onde}.',
                linha=bloco.linha,
            )
        for prop in bloco.propriedades:
            for valor in prop.valores:
                if not isinstance(valor, (A.TextoLit, A.NumeroLit,
                                          A.Booleano, A.Membro)):
                    raise ErroSemantico(
                        f'Valor inválido em {onde}/{bloco.nome}: use '
                        "texto, número, verdadeiro/falso ou estado.*.",
                        linha=prop.linha,
                    )
        blocos[bloco.nome] = bloco.propriedades
    tem_url = "url" in props
    tem_arquivo = "arquivo" in props
    if tem_url == tem_arquivo:
        raise ErroSemantico(
            f'{onde} precisa de exatamente um: url (remota) ou arquivo '
            "(JSON local).",
            linha=fonte.linha,
            exemplo='url: "https://api.exemplo.com/usuarios"',
        )
    if tem_url:
        url = props["url"].valor
        esquema = url.split("://")[0].lower() if "://" in url else ""
        if esquema not in ("http", "https"):
            raise ErroSemantico(
                f'{onde}: url deve começar com http:// ou https://.',
                linha=fonte.linha,
            )
        metodo = "GET"
        if "metodo" in props or "método" in props:
            metodo = (props.get("metodo", props.get("método"))).valor.upper()
            if metodo not in METODOS_HTTP:
                raise ErroSemantico(
                    f"{onde}: metodo deve ser um de "
                    f'{", ".join(METODOS_HTTP)}.',
                    linha=fonte.linha,
                )
        props["metodo"] = metodo
        if "atualizar" in props:
            from ..unidades import tempo_para_ms

            intervalo = props["atualizar"]
            if tempo_para_ms(intervalo.valor, intervalo.unidade) < 1000:
                raise ErroSemantico(
                    f"{onde}: atualizar mínimo de 1s (evita "
                    "sobrecarregar a API).",
                    linha=fonte.linha,
                )
    return {"props": props, "blocos": blocos}


def validar_tema(tema: A.TemaDef) -> None:
    """Valida seções cores (CorLit) e tamanhos/espacos (Medida)."""
    for prop in tema.cores:
        if (len(prop.valores) != 1
                or not isinstance(prop.valores[0], A.CorLit)):
            raise ErroSemantico(
                f'Cor "{prop.nome}" no tema precisa de cor '
                "(nome ou hexadecimal).",
                linha=prop.linha,
                exemplo=f'{prop.nome}: "#ffffff"',
            )
    for secao_nome, lista in (("tamanhos", tema.tamanhos),
                              ("espacos", tema.espacos)):
        for prop in lista:
            if (len(prop.valores) != 1
                    or not _eh_medida(prop.valores[0], "comprimento")):
                raise ErroSemantico(
                    f'"{prop.nome}" em {secao_nome} precisa de medida '
                    "(ex. 16px).",
                    linha=prop.linha,
                )


def validar_componente_def(defn: A.ComponenteDef) -> None:
    """Valida definição: params únicos, corpo com componentes válidos."""
    vistos: set[str] = set()
    for param in defn.params:
        if param.nome in vistos:
            raise ErroSemantico(
                f'Propriedade "{param.nome}" repetida em "{defn.nome}".',
                linha=param.linha,
            )
        vistos.add(param.nome)
    if not defn.corpo:
        raise ErroSemantico(
            f'Componente "{defn.nome}" precisa de corpo com ao menos '
            "um componente.",
            linha=defn.linha,
            exemplo="corpo {\n    texto t {\n    }\n}",
        )
    if getattr(defn, "estado", None) is not None:
        validar_estado(defn.estado)
    elif _usa_local(defn.corpo):
        raise ErroSemantico(
            f'Componente "{defn.nome}" usa local.* mas não declara '
            "estado. Adicione um bloco estado { ... }.",
            linha=defn.linha,
            exemplo="estado {\n    valor: 0\n}",
        )


def _usa_local(corpo: list) -> bool:
    """True se alguma expressão usa raiz local.*."""

    def em_expr(expr) -> bool:
        if isinstance(expr, A.Membro):
            partes = A.caminho_de_membro(expr).split(".")
            if partes[0] == "local":
                return True
            return em_expr(expr.base)
        if isinstance(expr, A.Binaria):
            return em_expr(expr.esquerda) or em_expr(expr.direita)
        if isinstance(expr, A.ListaLit):
            return any(em_expr(i) for i in expr.itens)
        if isinstance(expr, A.Chamada):
            return any(em_expr(a) for a in expr.args)
        return False

    def em_comandos(bloco) -> bool:
        for cmd in bloco.comandos:
            if isinstance(cmd, A.Acao):
                if any(em_expr(a) for a in cmd.args):
                    return True
            elif isinstance(cmd, A.Atribuicao):
                if em_expr(cmd.valor):
                    return True
            elif isinstance(cmd, A.Se):
                if em_expr(cmd.condicao) or em_comandos(cmd.entao):
                    return True
                if cmd.senao is not None and em_comandos(cmd.senao):
                    return True
            elif isinstance(cmd, A.Repetir):
                if em_comandos(cmd.bloco):
                    return True
            elif isinstance(cmd, A.Retornar) and cmd.valor is not None:
                if em_expr(cmd.valor):
                    return True
        return False

    pilha = list(corpo)
    while pilha:
        no = pilha.pop()
        if isinstance(no, A.Personagem):
            # Fase 12: local.* dentro de personagem/parte também conta.
            for prop in no.propriedades:
                if any(em_expr(v) for v in prop.valores):
                    return True
            for parte in _todas_partes(no):
                for prop in parte.propriedades:
                    if any(em_expr(v) for v in prop.valores):
                        return True
            pilha.extend(no.filhos)
            continue
        if not isinstance(no, A.Componente):
            continue
        for prop in no.propriedades:
            if any(em_expr(v) for v in prop.valores):
                return True
        for ev in no.eventos:
            if em_comandos(ev.bloco):
                return True
        pilha.extend(no.filhos)
        pilha.extend(getattr(no, "modelo", []))
    return False


def validar_refs_tema(programa: A.Programa, temas: dict) -> None:
    """Pós-passe: `tema.x` existe no tema; `tema:` aponta p/ tema válido."""

    def conferir_tema(nome: str, linha: int) -> None:
        if nome not in temas:
            parecidas = sugerir(nome, sorted(temas))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'Tema "{nome}" não definido.{dica} Crie com '
                "tema nome { ... }.",
                linha=linha,
            )

    def conferir_chave(tema_nome: str, secao: str, chave: str,
                       linha: int) -> None:
        chaves = set(temas[tema_nome].get(secao, {}))
        if chave not in chaves:
            raise ErroSemantico(
                f'Tema "{tema_nome}" não tem "{chave}" em {secao}. '
                f"Disponíveis: {', '.join(sorted(chaves)) or 'nenhuma'}.",
                linha=linha,
            )

    def de_props(props: list, onde: str) -> None:
        for prop in props:
            if prop.nome == "tema" and prop.valores:
                valor = prop.valores[0]
                if isinstance(valor, A.TextoLit):
                    conferir_tema(valor.valor, prop.linha)
                continue
            for valor in prop.valores:
                if not isinstance(valor, A.Membro):
                    continue
                caminho = A.caminho_de_membro(valor)
                partes = caminho.split(".")
                if len(partes) != 2 or partes[0] != "tema":
                    continue
                # tema atual desconhecido aqui: checa em TODOS os temas
                achados = [t for t, secs in temas.items()
                           if partes[1] in secs.get("cores", {})
                           or partes[1] in secs.get("tamanhos", {})
                           or partes[1] in secs.get("espacos", {})]
                if not achados:
                    todos = sorted({c for secs in temas.values()
                                    for s in ("cores", "tamanhos", "espacos")
                                    for c in secs.get(s, {})})
                    parecidas = sugerir(partes[1], todos)
                    dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                            if parecidas else "")
                    raise ErroSemantico(
                        f'{onde}: "{caminho}" não existe em nenhum tema.'
                        f"{dica}",
                        linha=prop.linha,
                    )

    def de_comp(comp) -> None:
        if isinstance(comp, A.Personagem):
            # Fase 12: refs de tema no root, partes e visuais do personagem.
            de_props(comp.propriedades,
                     f'personagem "{comp.nome}"')
            for parte in _todas_partes(comp):
                de_props(parte.propriedades,
                         f'parte "{parte.nome}"')
            for filho in comp.filhos:
                if isinstance(filho, A.Componente):
                    de_comp(filho)
            return
        de_props(comp.propriedades, f'{comp.tipo} "{comp.nome}"')
        for filho in comp.filhos:
            if isinstance(filho, (A.Componente, A.Personagem)):
                de_comp(filho)

    for janela in list(programa.janelas) + list(programa.telas):
        de_props(janela.propriedades, f'janela "{janela.nome}"')
        for comp in janela.componentes:
            if isinstance(comp, (A.Componente, A.Personagem)):
                de_comp(comp)


def validar(programa: A.Programa) -> list[Aviso]:
    """Valida o programa. Retorna avisos; erros levantam ErroSemantico."""
    avisos: list[Aviso] = []
    if not programa.janelas and not programa.telas:
        raise ErroSemantico(
            "O programa não possui nenhuma janela nem tela.",
            exemplo='janela principal {\n    titulo: "Minha aplicação"\n}',
        )
    chaves_estado = (validar_estado(programa.estado)
                     if programa.estado is not None else set())
    nomes_fontes: set[str] = set()
    for fonte in programa.fontes:
        if fonte.nome in nomes_fontes:
            raise ErroSemantico(
                f'Fonte duplicada: "{fonte.nome}". Cada bloco dados '
                "precisa de um nome único.",
                linha=fonte.linha,
            )
        nomes_fontes.add(fonte.nome)
        validar_fonte(fonte)
    # Fase 08: temas e componentes reutilizáveis.
    vistos_temas: set[str] = set()
    temas: dict = {}
    for tema in programa.temas:
        if tema.nome in vistos_temas:
            raise ErroSemantico(
                f'Tema "{tema.nome}" definido duas vezes.',
                linha=tema.linha,
            )
        vistos_temas.add(tema.nome)
        validar_tema(tema)
        temas[tema.nome] = {
            "cores": {p.nome for p in tema.cores},
            "tamanhos": {p.nome for p in tema.tamanhos},
            "espacos": {p.nome for p in tema.espacos},
        }
    vistos_comp: set[str] = set()
    for definicao in programa.componentes:
        if definicao.nome in vistos_comp:
            raise ErroSemantico(
                f'Componente "{definicao.nome}" definido duas vezes.',
                linha=definicao.linha,
            )
        vistos_comp.add(definicao.nome)
        validar_componente_def(definicao)
    validar_refs_tema(programa, temas)
    # Alvos de fontes (estado.<nome> por padrão) existem via garantir().
    extras = set(nomes_fontes)
    for fonte in programa.fontes:
        for prop in fonte.propriedades:
            if prop.nome == "para" and prop.valores:
                caminho = A.caminho_de_membro(prop.valores[0])
                extras.add(caminho.split(".")[1])
    # Fase 08: chaves de formulário (<form>_valido/_erros/_resposta).
    def _forms(comp):
        if not isinstance(comp, A.Componente):
            return
        if comp.tipo == "formulario" and comp.nome:
            extras.update({f"{comp.nome}_valido", f"{comp.nome}_erros",
                            f"{comp.nome}_resposta"})
        for filho in comp.filhos:
            if isinstance(filho, A.Componente):
                _forms(filho)

    for janela in list(programa.janelas) + list(programa.telas):
        for comp in janela.componentes:
            if isinstance(comp, A.Componente):
                _forms(comp)
    # Fase 09: chaves de estado local estático (programa.locais).
    for ns, chaves in (programa.locais or {}).items():
        extras.update(f"{ns}__{chave}" for chave in chaves)
    validar_chaves_estado(programa, chaves_estado, extras)
    nomes_funcoes = {f.nome for f in programa.funcoes}
    # Fase 09: ações reutilizáveis (sem colidir com funções).
    vistos_acoes: set[str] = set()
    for acao in programa.acoes:
        if acao.nome in vistos_acoes:
            raise ErroSemantico(
                f'Ação "{acao.nome}" definida duas vezes.',
                linha=acao.linha,
            )
        vistos_acoes.add(acao.nome)
        if acao.nome in nomes_funcoes:
            raise ErroSemantico(
                f'"{acao.nome}" já é função. Ação e função não podem '
                "ter o mesmo nome.",
                linha=acao.linha,
            )
        vistos_params: set[str] = set()
        for param in acao.params:
            if param in vistos_params:
                raise ErroSemantico(
                    f'Parâmetro "{param}" repetido na ação "{acao.nome}".',
                    linha=acao.linha,
                )
            vistos_params.add(param)
        validar_bloco(acao.bloco)
    vistos_janelas: set[str] = set()
    # Fase 14: registro global de definições de item (todas as janelas).
    itens_def: dict[str, object] = {}
    for janela in list(programa.janelas) + list(programa.telas):
        for item in janela.itens:
            if item.nome in itens_def:
                raise ErroSemantico(
                    f'Item "{item.nome}" definido duas vezes no programa.',
                    linha=item.linha,
                )
            itens_def[item.nome] = item
    for janela in list(programa.janelas) + list(programa.telas):
        rotulo = "Tela" if janela.eh_tela else "Janela"
        if janela.nome in vistos_janelas:
            raise ErroSemantico(
                f'{rotulo} duplicada: "{janela.nome}". Cada uma precisa '
                "de um nome único.",
                linha=janela.linha,
            )
        vistos_janelas.add(janela.nome)
        for prop in janela.propriedades:
            validar_propriedade(prop, PROPS_JANELA,
                                f'{rotulo.lower()} "{janela.nome}"',
                                nomes_fontes)
        if not any(p.nome in ("titulo", "título")
                   for p in janela.propriedades):
            avisos.append(Aviso(
                f'Janela "{janela.nome}" sem título. '
                'Adicione titulo: "Nome da aplicação".',
                linha=janela.linha))
        for ev in janela.eventos:
            validar_evento_no(ev, f'janela "{janela.nome}"')
        for item in janela.itens:
            _validar_item(item, _tipos_da_janela(janela))
        for comp in janela.componentes:
            validar_componente(comp, nomes_funcoes, nomes_fontes,
                               itens_def)
        nomes_anims = {a.nome for a in janela.animacoes}
        if len(nomes_anims) != len(janela.animacoes):
            raise ErroSemantico(
                f'Janela "{janela.nome}" tem animações com nome repetido. '
                "Cada animação precisa de um nome único.",
                linha=janela.linha,
            )
        nomes = _nomes_da_janela(janela)
        for anim in janela.animacoes:
            validar_animacao(anim, nomes, nomes_anims)
        _ = nomes_funcoes
        _validar_mundos(janela, nomes, itens_def)
        _validar_navegacoes(janela)
    _validar_identidade_partes(programa)
    return avisos


def _bordas_de_entidade(nome_entidade: str) -> list[str]:
    """Ids de borda derivados: `<ent>_borda_<lado>` (Fase 15)."""
    return [f"{nome_entidade}_borda_{lado}" for lado in LADOS_BORDA_15]


def _nos_navegaveis(janela: A.Janela) -> set[str]:
    """Nomes referenciáveis em caminho: entidades + bordas derivadas."""
    nomes: set[str] = set()
    for mundo in janela.mundos:
        for entidade in mundo.entidades:
            nomes.add(entidade.nome)
            nomes.update(_bordas_de_entidade(entidade.nome))
    return nomes


def _validar_navegacoes(janela: A.Janela) -> None:
    """Fase 15: navegações da janela (refs, custos, duplicatas)."""
    rotulo = "Tela" if janela.eh_tela else "Janela"
    vistos_nav: set[str] = set()
    referenciaveis = _nos_navegaveis(janela)
    for nav in janela.navegacoes:
        onde_nav = (f'navegação "{nav.nome}" '
                    f'({rotulo.lower()} "{janela.nome}")')
        if nav.nome in vistos_nav:
            raise ErroSemantico(
                f'Navegação "{nav.nome}" repetida em {rotulo.lower()} '
                f'"{janela.nome}".',
                linha=nav.linha,
            )
        vistos_nav.add(nav.nome)
        vistos_cam: set[tuple] = set()
        for caminho in nav.caminhos:
            for ponta, rotulo_ponta in ((caminho.origem, "origem"),
                                        (caminho.destino, "destino")):
                if ponta not in referenciaveis:
                    parecidas = sugerir(ponta, sorted(referenciaveis))
                    dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                            if parecidas else "")
                    raise ErroSemantico(
                        f'{rotulo_ponta} "{ponta}" do caminho '
                        f"{caminho.origem!r} -> {caminho.destino!r} não "
                        f"existe em {onde_nav}.{dica} Use entidade do mundo "
                        "ou <entidade>_borda_<lado>.",
                        linha=caminho.linha,
                    )
            for prop in caminho.propriedades:
                validar_propriedade(prop, PROPS_CAMINHO,
                                    f'caminho "{caminho.origem}" -> '
                                    f'"{caminho.destino}"')
            modo = "andar"
            for prop in caminho.propriedades:
                if prop.nome == "modo" and prop.valores:
                    valor = prop.valores[0]
                    if isinstance(valor, A.TextoLit):
                        modo = valor.valor.strip() or "andar"
                    elif isinstance(valor, A.Ident):
                        modo = valor.nome.strip() or "andar"
            chave = (caminho.origem, caminho.destino, modo)
            if chave in vistos_cam:
                raise ErroSemantico(
                    f'Caminho "{caminho.origem}" -> "{caminho.destino}" '
                    f'(modo "{modo}") repetido em {onde_nav}.',
                    linha=caminho.linha,
                )
            vistos_cam.add(chave)
            for prop in caminho.propriedades:
                if prop.nome == "custo" and prop.valores:
                    valor = prop.valores[0]
                    numero = (float(valor.valor)
                              if isinstance(valor, A.NumeroLit) else None)
                    if numero is None or numero < 0:
                        raise ErroSemantico(
                            f'Caminho "{caminho.origem}" -> '
                            f'"{caminho.destino}" de {onde_nav}: "custo" '
                            "precisa de número ≥ 0.",
                            linha=prop.linha,
                            exemplo="custo: 1",
                        )


def _tipos_da_janela(janela: A.Janela) -> dict[str, str]:
    """Nome → kind (personagem vs visual) para refs `usar/visual`."""
    tipos: dict[str, str] = {}

    def visitar(no, kind: str) -> None:
        if getattr(no, "nome", ""):
            tipos.setdefault(no.nome, kind)
        for filho in getattr(no, "filhos", []):
            visitar(filho, kind)
        for modelo in getattr(no, "modelo", []):
            visitar(modelo, kind)

    for comp in janela.componentes:
        if isinstance(comp, A.ItemDef):
            continue  # Fase 14: itens não são nós visuais
        if isinstance(comp, A.Personagem):
            tipos.setdefault(comp.nome, "personagem")
            for parte in _todas_partes(comp):
                tipos.setdefault(parte.nome, "parte")
                for filho in parte.filhos:
                    visitar(filho, "visual")
            for filho in comp.filhos:
                visitar(filho, "visual")
        else:
            visitar(comp, "visual")
    return tipos


def _validar_mundos(janela: A.Janela, nomes: set[str],
                     itens: dict | None = None) -> None:
    """Fase 13: mundos da janela (nomes, entidades, refs, áreas)."""
    rotulo = "Tela" if janela.eh_tela else "Janela"
    vistos_mundos: set[str] = set()
    tipos = _tipos_da_janela(janela)
    for mundo in janela.mundos:
        onde_mundo = (f'mundo "{mundo.nome}" '
                      f'({rotulo.lower()} "{janela.nome}")')
        if mundo.nome in vistos_mundos:
            raise ErroSemantico(
                f'Mundo "{mundo.nome}" repetido em {rotulo.lower()} '
                f'"{janela.nome}".',
                linha=mundo.linha,
            )
        vistos_mundos.add(mundo.nome)
        for prop in mundo.propriedades:
            validar_propriedade(prop, PROPS_MUNDO, onde_mundo)
        vistos_ent: set[str] = set()
        for entidade in mundo.entidades:
            if entidade.tipo not in TIPOS_ENTIDADE_13:
                raise ErroSemantico(
                    f'Tipo de entidade inválido em {onde_mundo}: '
                    f'"{entidade.tipo}".',
                    linha=entidade.linha,
                )
            if entidade.nome in vistos_ent:
                parecidas = sugerir(entidade.nome, sorted(vistos_ent))
                dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                        if parecidas else "")
                raise ErroSemantico(
                    f'Entidade "{entidade.nome}" repetida em '
                    f'{onde_mundo}.{dica}',
                    linha=entidade.linha,
                )
            vistos_ent.add(entidade.nome)
            _validar_entidade(entidade, onde_mundo, tipos, itens)
        _validar_areas(mundo, onde_mundo)


def _validar_entidade(entidade, onde_mundo: str,
                      tipos: dict[str, str],
                      itens: dict | None = None) -> None:
    onde = f'{entidade.tipo} "{entidade.nome}" de {onde_mundo}'
    if entidade.tipo == "personagem":
        # `usar personagem Nome`: só referência (sem propriedades).
        if entidade.propriedades:
            raise ErroSemantico(
                f"{onde} é referência (usar personagem); não aceita "
                "propriedades.",
                linha=entidade.linha,
                exemplo="usar personagem Heroi",
            )
        kind = tipos.get(entidade.nome)
        if kind is None:
            raise ErroSemantico(
                f"Personagem '{entidade.nome}' não encontrado em {onde_mundo}. "
                "Declare com personagem Nome { ... }.",
                linha=entidade.linha,
            )
        if kind != "personagem":
            raise ErroSemantico(
                f"'{entidade.nome}' em {onde_mundo} não é personagem "
                f"(é {kind}).",
                linha=entidade.linha,
            )
        return
    if entidade.tipo == "item":
        # Fase 14: `usar item Def [como Apelido] [{posição/tamanho}]`.
        ref = entidade.ref or entidade.nome
        if itens is None or ref not in itens:
            parecidas = sugerir(ref, sorted(itens or {}))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'Item "{ref}" não definido em {onde}.{dica} '
                "Declare com item Nome { ... }.",
                linha=entidade.linha,
            )
        for prop in entidade.propriedades:
            validar_propriedade(prop, PROPS_USAR_ITEM, onde)
        return
    for prop in entidade.propriedades:
        validar_propriedade(prop, PROPS_ENTIDADE, onde)
    for prop in entidade.propriedades:
        if prop.nome == "visual" and prop.valores:
            valor = prop.valores[0]
            from ..compilador import ast as _A

            if isinstance(valor, _A.TextoLit):
                ref = valor.valor
            elif isinstance(valor, _A.Ident):
                ref = valor.nome  # como `alvo: nome` em animação
            else:
                continue
            if ref not in tipos:
                parecidas = sugerir(ref, sorted(tipos))
                dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                        if parecidas else "")
                raise ErroSemantico(
                    f'Visual "{ref}" não encontrado em {onde}.{dica}',
                    linha=prop.linha,
                )


def _validar_areas(mundo, onde_mundo: str) -> None:
    """`pai:` de área referencia outra área (sem ciclos)."""
    from ..compilador import ast as _A

    areas = {e.nome: e for e in mundo.entidades if e.tipo == "area"}

    def _nome_pai(valor):
        from ..compilador import ast as _A

        if isinstance(valor, _A.TextoLit):
            return valor.valor
        if isinstance(valor, _A.Ident):
            return valor.nome
        return None

    for entidade in mundo.entidades:
        for prop in entidade.propriedades:
            if prop.nome != "pai" or not prop.valores:
                continue
            pai = _nome_pai(prop.valores[0])
            if pai is None:
                continue
            if entidade.tipo != "area":
                raise ErroSemantico(
                    f'Só área aceita "pai" em {onde_mundo} '
                    f'(recebido em {entidade.tipo} "{entidade.nome}").',
                    linha=prop.linha,
                )
            if pai not in areas:
                parecidas = sugerir(pai, sorted(areas))
                dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                        if parecidas else "")
                raise ErroSemantico(
                    f'Área "{pai}" não encontrada em {onde_mundo}.{dica}',
                    linha=prop.linha,
                )
            # ciclo: sobe a cadeia (mundo é pequeno; O(n²) aceitável).
            visitado = {entidade.nome}
            atual = pai
            while atual in areas:
                if atual in visitado:
                    raise ErroSemantico(
                        f"Ciclo de áreas em {onde_mundo}: "
                        f'"{entidade.nome}" → ... → "{atual}".',
                        linha=prop.linha,
                    )
                visitado.add(atual)
                proximo = None
                for prop2 in areas[atual].propriedades:
                    if prop2.nome == "pai" and prop2.valores:
                        proximo = _nome_pai(prop2.valores[0])
                atual = proximo


def _validar_identidade_partes(programa) -> None:
    """Fase 12: nomes de partes são globais e únicos (identidade estável).

    Só atua quando há personagens (fora isso, nada muda). Parte não pode
    repetir nem colidir com outro nome (componente, janela, personagem).
    """
    partes: list[tuple[str, str, int]] = []  # (nome, personagem, linha)
    outros: dict[str, str] = {}  # nome -> descrição

    def visitar_parte(parte, nome_personagem: str) -> None:
        partes.append((parte.nome, nome_personagem, parte.linha))
        for sub in parte.partes:
            visitar_parte(sub, nome_personagem)

    def visitar_comp(comp) -> None:
        if isinstance(comp, A.ItemDef):
            return  # Fase 14: itens têm namespace próprio
        if isinstance(comp, A.Personagem):
            outros.setdefault(comp.nome,
                              f'personagem "{comp.nome}"')
            for filho in comp.filhos:
                if isinstance(filho, (A.Componente, A.Personagem)):
                    visitar_comp(filho)
            for parte in comp.partes:
                visitar_parte(parte, comp.nome)
            return
        if isinstance(comp, A.Instancia):
            outros.setdefault(comp.nome, f'instância "{comp.nome}"')
            return
        outros.setdefault(comp.nome,
                          f'{comp.tipo} "{comp.nome}"')
        for filho in comp.filhos:
            if isinstance(filho, (A.Componente, A.Personagem)):
                visitar_comp(filho)
        for modelo in getattr(comp, "modelo", []):
            visitar_comp(modelo)

    for janela in list(programa.janelas) + list(programa.telas):
        outros.setdefault(janela.nome, f'janela "{janela.nome}"')
        for comp in janela.componentes:
            visitar_comp(comp)
    if not partes:
        return
    contagem: dict[str, int] = {}
    for nome, _personagem, _linha in partes:
        contagem[nome] = contagem.get(nome, 0) + 1
    for nome, nome_personagem, linha in partes:
        if contagem[nome] > 1:
            raise ErroSemantico(
                f'Parte "{nome}" do personagem "{nome_personagem}" '
                "colide com outra parte (nomes de partes são globais "
                "e únicos).",
                linha=linha,
            )
        dono = outros.get(nome)
        if dono is not None:
            raise ErroSemantico(
                f'Parte "{nome}" do personagem "{nome_personagem}" '
                f"colide com {dono} (nomes de partes são globais "
                "e únicos).",
                linha=linha,
            )
