"""Cena da ELiXX — representação intermediária entre runtime e renderer.

Fluxo (o parser nunca encosta aqui):

    AST → runtime Objetos → Cena (NoVisual) → Renderizador → tela

Coordenadas (decisão documentada em docs/renderer-nativo.md):
x cresce para a direita, y cresce para baixo; a origem (0, 0) é o canto
superior esquerdo da área de conteúdo da janela.

Unidades relativas: `px` é absoluto; `%` é fração da referência (largura
da janela para x/largura, altura para y/altura); `vw`/`vh` são fração da
janela. A resolução acontece aqui, não no parser nem no backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..compilador import ast as A
from ..cores import para_cor

TIPOS_VISUAIS = ("janela", "botao", "texto", "imagem", "video", "audio",
                 "grupo", "objeto")
"""Tipos que participam da cena (Fase 10: grupo/objeto agrupam)."""

FONTE_PADRAO_PX = 12.0


@dataclass
class NoVisual:
    """Um nó da árvore visual (espelho de um Objeto do runtime)."""

    tipo: str
    nome: str = ""
    x: float = 0.0
    y: float = 0.0
    largura: float | None = None  # None = tamanho automático do backend
    altura: float | None = None
    escala: float = 1.0  # legado uniforme (Fase 10: espelha escala_x/y)
    escala_x: float = 1.0
    escala_y: float = 1.0
    rotacao: float = 0.0  # graus, horário (Fase 10: [0, 360))
    opacidade: float = 1.0
    # Fase 10: pivô (ponto de rotação/escala; % do tamanho ou px) e
    # camada visual (menor atrás, maior na frente; empate = criação).
    pivo_x: float = 50.0
    pivo_y: float = 50.0
    pivo_unidade_x: str = "%"
    pivo_unidade_y: str = "%"
    camada: float = 0.0
    _seq: int = 0  # ordem de criação (desempate estável de camada)
    visivel: bool = True
    # estilo resolvido em valores simples
    titulo: str = ""
    texto: str = ""
    fonte_px: float = FONTE_PADRAO_PX
    fundo_hex: str | None = None
    cor_hex: str | None = None
    eventos: dict = field(default_factory=dict)  # nome -> Bloco (AST)
    pai: NoVisual | None = None
    filhos: list[NoVisual] = field(default_factory=list)
    ref_objeto: object = None  # Objeto do runtime (ponte para eventos)
    linha: int = 0
    # Reatividade (extensão dashboard): caminho "dados.fonte.campo",
    # formato de exibição ("texto", "percentual", "gb", "mb", "inteiro")
    # e histórico de amostras numéricas (para gráficos).
    origem: str | None = None
    formato: str = "texto"
    historico: list[float] = field(default_factory=list)
    # Fase 05: expressão de origem (Membro, Binaria derivada ou literal)
    # e two-way binding (ligado_a → chave de estado).
    origem_expr: object = None
    ligado_a: str | None = None
    # Fase 04: layout resolvido (números) + medidas relativas originais
    # (para recalcular no resize sem perder a referência).
    layout: dict = field(default_factory=dict)
    medidas: dict = field(default_factory=dict)
    # Fase 04: opções de seleção (lista de textos).
    opcoes: list[str] = field(default_factory=list)
    # Fase 07: multimídia (recursos, gráficos, áudio).
    fonte_recurso: str | None = None  # arquivo | url | None
    caminho_recurso: str = ""
    reserva: str | None = None
    ajuste: str = "conter"
    tipo_grafico: str = "linha"
    serie: list[float] = field(default_factory=list)
    nome_icone: str | None = None
    volume: int = 100
    repetir_audio: bool = False
    # Fase 08: temas (refs p/ troca sem reconstruir) e aplicação.
    tema_usado: str | None = None
    tema_refs: dict = field(default_factory=dict)  # prop -> chave
    colunas_nomes: list[str] = field(default_factory=list)
    ativa_index: int | None = None  # aba inicial (binding via ligado_a)
    # Fase 09: template de lista dinâmica + def de origem (estado local).
    modelo: list = field(default_factory=list)  # NoVisual template
    dinamica: bool = False  # lista com modelo (GerenciadorListas manda)
    def_origem: str | None = None
    chave_expr: object = None  # prop chave: (Membro, ex. item.id)
    # Fase 12: metadados de personagem/parte (None fora de personagens).
    personagem_meta: dict | None = None

    def adicionar(self, filho: NoVisual) -> None:
        filho.pai = self
        self.filhos.append(filho)

    def buscar(self, nome: str) -> NoVisual | None:
        if self.nome == nome:
            return self
        for filho in self.filhos:
            achado = filho.buscar(nome)
            if achado is not None:
                return achado
        return None

    def todos(self) -> list[NoVisual]:
        lista = [self]
        for filho in self.filhos:
            lista.extend(filho.todos())
        return lista


@dataclass
class Cena:
    """Conjunto de janelas prontas para renderizar (Scene2D).

    `viewport` é a fundação da futura câmera (Fase 10: só tamanho lógico;
    sem seguir/zoom animado). O renderer apenas interpreta a cena.
    """

    janelas: list[NoVisual] = field(default_factory=list)
    viewport: object = None  # Viewport (transform.py; None = 800x600)

    def buscar(self, nome: str) -> NoVisual | None:
        for janela in self.janelas:
            achado = janela.buscar(nome)
            if achado is not None:
                return achado
        return None

    def globais(self) -> dict[int, object]:
        """Transform global de cada nó (ver transform.globais_da_cena)."""
        from .transform import globais_da_cena

        return globais_da_cena(self)


LAYOUTS = ("linha", "coluna", "grade", "pilha")
"""Contêineres que arranjam filhos sem posição explícita."""


def resolver_medida(expr: object, referencia: float) -> float | None:
    """Resolve uma expressão de medida para pixels (ou None se inválida)."""
    if isinstance(expr, A.Medida):
        if expr.unidade == "px":
            return float(expr.valor)
        if expr.unidade == "%":
            return float(expr.valor) / 100.0 * referencia
        if expr.unidade in ("vw", "vh"):
            return float(expr.valor) / 100.0 * referencia
        return None
    if isinstance(expr, A.NumeroLit):
        return float(expr.valor)
    return None


def _texto_de(valor: object) -> str:
    if isinstance(valor, A.TextoLit):
        return valor.valor
    if isinstance(valor, str):
        return valor
    return ""


def _cor_hex_de(valor: object, linha: int = 0) -> str | None:
    if isinstance(valor, A.CorLit):
        return para_cor(valor.valor, linha=linha).hexadecimal
    if isinstance(valor, str):
        try:
            return para_cor(valor, linha=linha).hexadecimal
        except Exception:
            return None
    return None


class ConstrutorCena:
    """Monta a Cena a partir dos Objetos do runtime (pós-execução)."""

    def __init__(self) -> None:
        self.temas: dict = {}
        self.tema_padrao: str | None = None
        self._seq: int = 0  # Fase 10: ordem de criação (desempate camada)

    def _proximo_seq(self) -> int:
        valor = self._seq
        self._seq += 1
        return valor

    def de_objetos(self, objetos: list, temas: dict | None = None,
                   tema_padrao: str | None = None) -> Cena:
        self.temas = temas or {}
        self.tema_padrao = tema_padrao or (next(iter(self.temas), None))
        cena = Cena()
        for obj in objetos:
            if obj.tipo in ("janela", "tela"):
                cena.janelas.append(self.de_janela(obj))
        # Fase 10: viewport lógica = primeira janela (fundação câmera).
        from .transform import Viewport

        if cena.janelas:
            primeira = cena.janelas[0]
            cena.viewport = Viewport(
                largura=float(primeira.largura or 800.0),
                altura=float(primeira.altura or 600.0))
        else:
            cena.viewport = Viewport()
        return cena

    def _tema_de(self, obj) -> str | None:
        tema = obj.estilo.get("tema")
        if isinstance(tema, A.TextoLit) and tema.valor in self.temas:
            return tema.valor
        return self.tema_padrao

    @staticmethod
    def _tem_posicao_explicita(obj) -> bool:
        return bool(obj.bruto.get("posicao"))

    def _resolver_cor(self, no, obj, chave: str, tema: str | None) -> None:
        valor = obj.estilo.get(chave)
        if isinstance(valor, A.Membro) and tema:
            partes = A.caminho_de_membro(valor).split(".")
            if len(partes) == 2 and partes[0] == "tema":
                hexa = (self.temas.get(tema, {}).get("cores", {})
                        .get(partes[1]))
                if hexa is not None:
                    if chave == "fundo":
                        no.fundo_hex = hexa
                    else:
                        no.cor_hex = hexa
                    no.tema_refs[chave] = partes[1]
                    return
        if chave == "fundo":
            resultado = _cor_hex_de(valor, obj.linha)
            if resultado is not None:
                no.fundo_hex = resultado
        else:
            resultado = _cor_hex_de(valor, obj.linha)
            if resultado is not None:
                no.cor_hex = resultado

    def _resolver_fonte(self, bruto: dict,
                        tema: str | None) -> tuple[float, str | None]:
        """(px, chave_tema|None) — registra refs quem chama."""
        fonte = bruto.get("fonte", [])
        if fonte and isinstance(fonte[0], A.Membro) and tema:
            partes = A.caminho_de_membro(fonte[0]).split(".")
            if len(partes) == 2 and partes[0] == "tema":
                for secao in ("tamanhos", "espacos"):
                    valor = self.temas.get(tema, {}).get(secao, {}).get(
                        partes[1])
                    if valor is not None:
                        return float(valor), partes[1]
        if fonte:
            resolvida = resolver_medida(fonte[0], 16.0)
            if resolvida is not None:
                return resolvida, None
        return FONTE_PADRAO_PX, None

    def de_janela(self, obj) -> NoVisual:
        largura = obj.tamanho[0] or 800.0
        altura = obj.tamanho[1] or 600.0
        tema = self._tema_de(obj)
        no = NoVisual(
            tipo=obj.tipo, nome=obj.nome,
            x=obj.posicao[0], y=obj.posicao[1],
            largura=largura, altura=altura,
            escala=obj.escala, escala_x=obj.escala_x, escala_y=obj.escala_y,
            rotacao=obj.rotacao,
            opacidade=obj.opacidade, visivel=obj.visivel,
            pivo_x=obj.pivo_x, pivo_y=obj.pivo_y,
            pivo_unidade_x=obj.pivo_unidade_x,
            pivo_unidade_y=obj.pivo_unidade_y,
            camada=obj.camada, _seq=self._proximo_seq(),
            eventos=dict(obj.eventos), ref_objeto=obj, linha=obj.linha,
        )
        no.tema_usado = tema
        no.titulo = _texto_de(obj.estilo.get("titulo", obj.nome))
        self._resolver_cor(no, obj, "fundo", tema)
        if no.fundo_hex is None:
            no.fundo_hex = _cor_hex_de(obj.estilo.get("fundo"), obj.linha)
        # PROVISÓRIO (Fase 02): filhos sem posição explícita são empilhados
        # verticalmente. Layout real (centralizar/alinhar) é Fase 03.
        cursor_y = 20.0
        for filho in obj.filhos:
            no_filho = self.de_componente(filho, largura, altura, tema)
            if not self._tem_posicao_explicita(filho):
                no_filho.x = 20.0
                no_filho.y = cursor_y
                cursor_y += (no_filho.altura or 40.0) + 12.0
            no.adicionar(no_filho)
        # Fase 04: contêineres de layout rearranjam os filhos sem posição.
        aplicar_layout(no)
        return no

    def de_componente(self, obj, ref_larg: float, ref_alt: float,
                      tema_atual: str | None = None) -> NoVisual:
        bruto = obj.bruto
        # Fase 08: tema próprio vence; senão herda; senão padrão.
        tema_prop = obj.estilo.get("tema")
        if (isinstance(tema_prop, A.TextoLit)
                and tema_prop.valor in self.temas):
            tema = tema_prop.valor
        else:
            tema = tema_atual or self.tema_padrao
        bruto = obj.bruto
        x, y = obj.posicao
        pos = bruto.get("posicao", [])
        medidas: dict = {}
        if len(pos) >= 1:
            if (isinstance(pos[0], A.Medida)
                    and pos[0].unidade not in ("px",)):
                medidas["x"] = (pos[0].valor, pos[0].unidade)
            resolvido = resolver_medida(pos[0], ref_larg)
            x = resolvido if resolvido is not None else x
        if len(pos) >= 2:
            if (isinstance(pos[1], A.Medida)
                    and pos[1].unidade not in ("px",)):
                medidas["y"] = (pos[1].valor, pos[1].unidade)
            resolvido = resolver_medida(pos[1], ref_alt)
            y = resolvido if resolvido is not None else y
        largura, altura = None, None
        tam = bruto.get("tamanho", [])
        if len(tam) >= 1:
            largura = resolver_medida(tam[0], ref_larg)
        if len(tam) >= 2:
            altura = resolver_medida(tam[1], ref_alt)
        # Fase 04: largura/altura refinam cada eixo do tamanho.
        for chave, ref in (("largura", ref_larg), ("altura", ref_alt)):
            vals = bruto.get(chave, [])
            if vals:
                resolvido = resolver_medida(vals[0], ref)
                if resolvido is not None:
                    if chave == "largura":
                        largura = resolvido
                    else:
                        altura = resolvido
                if (isinstance(vals[0], A.Medida)
                        and vals[0].unidade not in ("px",)):
                    medidas[chave] = (vals[0].valor, vals[0].unidade)
        minimo = _numero_ou_nulo(bruto.get("minimo", []))
        maximo = _numero_ou_nulo(bruto.get("maximo", []))
        if largura is not None:
            largura = _limita(largura, minimo, maximo)
        if altura is not None:
            altura = _limita(altura, minimo, maximo)
        fonte_px, fonte_ref = self._resolver_fonte(bruto, tema)
        no = NoVisual(
            tipo=obj.tipo, nome=obj.nome, x=x, y=y,
            largura=largura, altura=altura,
            escala=obj.escala, escala_x=obj.escala_x, escala_y=obj.escala_y,
            rotacao=obj.rotacao,
            opacidade=obj.opacidade, visivel=obj.visivel,
            pivo_x=obj.pivo_x, pivo_y=obj.pivo_y,
            pivo_unidade_x=obj.pivo_unidade_x,
            pivo_unidade_y=obj.pivo_unidade_y,
            camada=obj.camada, _seq=self._proximo_seq(),
            eventos=dict(obj.eventos), ref_objeto=obj, linha=obj.linha,
        )
        no.tema_usado = tema
        if fonte_ref is not None:
            no.tema_refs["fonte"] = fonte_ref
        no.texto = _texto_de(obj.estilo.get("texto",
                             obj.estilo.get("conteudo", obj.nome)))
        no.fonte_px = fonte_px
        self._resolver_cor(no, obj, "fundo", tema)
        self._resolver_cor(no, obj, "cor", tema)
        no.medidas = medidas
        no.layout = _resolver_layout(bruto, ref_larg)
        opcoes = obj.estilo.get("opcoes")
        if isinstance(opcoes, list):
            no.opcoes = [o.valor for o in opcoes
                         if isinstance(o, A.TextoLit)]
        elif isinstance(opcoes, A.TextoLit):
            no.opcoes = [opcoes.valor]
        origem = obj.estilo.get("origem")
        if isinstance(origem, A.Membro):
            no.origem = A.caminho_de_membro(origem)
            no.origem_expr = origem
        elif isinstance(origem, (A.Binaria, A.TextoLit, A.NumeroLit,
                                 A.Booleano)):
            # Fase 05: expressão derivada ou literal estático.
            no.origem_expr = origem
        elif isinstance(origem, A.Ident) and origem.nome == "item":
            # Fase 09: linha inteira como texto.
            no.origem_expr = origem
        ligado = obj.estilo.get("ligado_a")
        if isinstance(ligado, A.Membro):
            partes = A.caminho_de_membro(ligado).split(".")
            if len(partes) == 2 and partes[0] == "estado":
                no.ligado_a = partes[1]
            elif len(partes) == 2 and partes[0] == "local":
                # Fase 09: two-way da linha (namespace vem do contexto).
                no.ligado_a = "local." + partes[1]
        formato = obj.estilo.get("formato")
        if isinstance(formato, A.TextoLit):
            no.formato = formato.valor.strip().lower() or "texto"
        # Fase 07: multimídia (valores já validados na semântica).
        arquivo = obj.estilo.get("arquivo")
        if isinstance(arquivo, A.TextoLit):
            no.fonte_recurso = "arquivo"
            no.caminho_recurso = arquivo.valor
        url = obj.estilo.get("url")
        if isinstance(url, A.TextoLit):
            no.fonte_recurso = "url"
            no.caminho_recurso = url.valor
        reserva = obj.estilo.get("reserva")
        if isinstance(reserva, A.TextoLit):
            no.reserva = reserva.valor
        ajuste = obj.estilo.get("ajuste")
        if isinstance(ajuste, A.TextoLit):
            no.ajuste = ajuste.valor.strip().lower()
        tipo = obj.estilo.get("tipo")
        if isinstance(tipo, A.TextoLit):
            no.tipo_grafico = tipo.valor.strip().lower()
        nome = obj.estilo.get("nome")
        if isinstance(nome, A.TextoLit):
            no.nome_icone = nome.valor.strip()
        elif no.tipo == "icone" and not no.fonte_recurso:
            no.nome_icone = obj.nome  # icone salvar { } usa o próprio nome
        volume = obj.estilo.get("volume")
        if isinstance(volume, A.NumeroLit):
            no.volume = max(0, min(100, int(volume.valor)))
        repetir = obj.estilo.get("repetir")
        if isinstance(repetir, A.Booleano):
            no.repetir_audio = bool(repetir.valor)
        # Fase 08: colunas da tabela (textos) e aba ativa.
        colunas = obj.estilo.get("colunas")
        if isinstance(colunas, list):
            no.colunas_nomes = [c.valor for c in colunas
                                if isinstance(c, A.TextoLit)]
        # Fase 09: chave de identidade da linha (item.id ou índice).
        chave = obj.estilo.get("chave")
        if isinstance(chave, A.Membro):
            no.chave_expr = chave
        ativa = obj.estilo.get("ativa")
        if isinstance(ativa, A.NumeroLit):
            no.ativa_index = int(ativa.valor)
        no.def_origem = getattr(obj, "def_origem", None)
        # Fase 12: personagem/parte carregam metadados; `imagem:` vira o
        # visual do nó (mesmo caminho de arquivo das imagens).
        no.personagem_meta = getattr(obj, "personagem", None)
        if obj.tipo in ("personagem", "parte"):
            imagem = (no.personagem_meta or {}).get("imagem")
            if imagem:
                no.fonte_recurso = "arquivo"
                no.caminho_recurso = imagem
        for neto in obj.filhos:
            no.adicionar(self.de_componente(neto, ref_larg, ref_alt, tema))
        # Fase 09: template do modelo (sem layout/posicionamento aqui;
        # o GerenciadorListas instancia por linha em runtime).
        for modelo in getattr(obj, "modelo", []):
            no.modelo.append(self.de_componente(modelo, ref_larg, ref_alt,
                                                tema))
        no.dinamica = bool(no.modelo)
        return no

def aplicar_tema(cena: Cena, temas: dict, nome: str) -> None:
    """Re-resolve cores/fonte de refs tema.* (troca sem reconstruir)."""
    from ..runtime.temas import cor_do_tema, medida_do_tema

    for janela in cena.janelas:
        for no in janela.todos():
            if not no.tema_refs:
                continue
            for prop, chave in no.tema_refs.items():
                if prop in ("fundo", "cor"):
                    hexa = cor_do_tema(temas, nome, chave)
                    if hexa is not None:
                        if prop == "fundo":
                            no.fundo_hex = hexa
                        else:
                            no.cor_hex = hexa
                elif prop == "fonte":
                    px = medida_do_tema(temas, nome, chave)
                    if px is not None:
                        no.fonte_px = float(px)
            no.tema_usado = nome


def _numero_ou_nulo(vals: list) -> float | None:
    if not vals:
        return None
    v = vals[0]
    if isinstance(v, A.Medida):
        return float(v.valor)
    if isinstance(v, A.NumeroLit):
        return float(v.valor)
    return None


def _limita(valor: float, minimo: float | None,
            maximo: float | None) -> float:
    if minimo is not None:
        valor = max(minimo, valor)
    if maximo is not None:
        valor = min(maximo, valor)
    return valor


def _par_medidas(vals: list, ref: float, padrao: float) -> tuple[float, float]:
    if not vals:
        return (padrao, padrao)
    primeiro = resolver_medida(vals[0], ref)
    if len(vals) == 1:
        v = primeiro if primeiro is not None else padrao
        return (v, v)
    segundo = resolver_medida(vals[1], ref)
    return ((primeiro if primeiro is not None else padrao),
            (segundo if segundo is not None else padrao))


def _resolver_layout(bruto: dict, ref: float) -> dict:
    """Propriedades de layout em números (fase 04)."""
    espac = bruto.get("espacamento", [])
    margem = bruto.get("margem", [])
    preench = bruto.get("preenchimento", [])
    colunas = bruto.get("colunas", [])
    return {
        "espacamento": _par_medidas(espac, ref, 8.0)[0],
        "margem": _par_medidas(margem, ref, 0.0),
        "preenchimento": _par_medidas(preench, ref, 0.0),
        "colunas": int(colunas[0].valor) if colunas and isinstance(
            colunas[0], A.NumeroLit) else 2,
    }


def aplicar_layout(no: NoVisual) -> None:
    """Arranjo backend-agnóstico, recursivo (filhos primeiro)."""
    for filho in no.filhos:
        aplicar_layout(filho)
    if no.tipo not in LAYOUTS:
        return
    livres = [f for f in no.filhos if not _no_tem_posicao(f)]
    if not livres:
        return
    larg = no.largura or 0.0
    esp = no.layout.get("espacamento", 8.0)
    mg_x, mg_y = no.layout.get("margem", (0.0, 0.0))
    pd_x, pd_y = no.layout.get("preenchimento", (0.0, 0.0))
    ox, oy = mg_x + pd_x, mg_y + pd_y
    util = max(0.0, larg - (mg_x + pd_x) * 2)
    alinh = _alinhamento_de(no)
    if no.tipo == "coluna":
        cursor = oy
        for f in livres:
            f.x = ox + _desloca(alinh, util, f.largura or 0.0)
            f.y = cursor
            cursor += (f.altura or 0.0) + esp
        _auto_tamanho(no, livres, ox, oy, esp)
    elif no.tipo == "linha":
        cursor = ox
        altura_max = max([(f.altura or 0.0) for f in livres] + [0.0])
        for f in livres:
            f.x = cursor
            f.y = oy + _desloca_vertical(alinh, altura_max,
                                         f.altura or 0.0)
            cursor += (f.largura or 0.0) + esp
        _auto_tamanho(no, livres, ox, oy, esp)
    elif no.tipo == "pilha":
        for f in livres:
            f.x, f.y = ox, oy
        _auto_tamanho(no, livres, ox, oy, esp)
    elif no.tipo == "grade":
        ncols = max(1, no.layout.get("colunas", 2))
        cw = util / ncols if ncols else util
        cursor_y = oy
        linha_atual: list = []
        for f in livres:
            linha_atual.append(f)
            if len(linha_atual) == ncols:
                cursor_y = _arranja_linha_grade(
                    linha_atual, cw, cursor_y, ox, esp, alinh)
                linha_atual = []
        if linha_atual:
            _arranja_linha_grade(linha_atual, cw, cursor_y, ox, esp, alinh)
        _auto_tamanho(no, livres, ox, oy, esp)


def _no_tem_posicao(no: NoVisual) -> bool:
    obj = no.ref_objeto
    if obj is None:
        return False
    return bool(obj.bruto.get("posicao"))


def _alinhamento_de(no: NoVisual) -> str:
    obj = no.ref_objeto
    if obj is None:
        return ""
    vals = obj.bruto.get("alinhamento", [])
    if vals and isinstance(vals[0], A.TextoLit):
        return vals[0].valor.strip().lower()
    return ""


def _desloca(alinh: str, util: float, larg_filho: float) -> float:
    if alinh == "centro":
        return max(0.0, (util - larg_filho) / 2.0)
    if alinh == "direita":
        return max(0.0, util - larg_filho)
    return 0.0


def _desloca_vertical(alinh: str, altura_max: float,
                      altura_filho: float) -> float:
    if alinh == "centro":
        return max(0.0, (altura_max - altura_filho) / 2.0)
    if alinh == "base":
        return max(0.0, altura_max - altura_filho)
    return 0.0


def _arranja_linha_grade(linha_atual: list, cw: float, cursor_y: float,
                         ox: float, esp: float, alinh: str) -> float:
    altura_max = max((f.altura or 0.0) for f in linha_atual)
    for i, f in enumerate(linha_atual):
        f.x = ox + i * cw + _desloca(alinh, cw, f.largura or 0.0)
        f.y = cursor_y
    return cursor_y + altura_max + esp


def _auto_tamanho(no: NoVisual, livres: list, ox: float, oy: float,
                  esp: float) -> None:
    if not livres:
        return
    direita = max(f.x + (f.largura or 0.0) for f in livres)
    base = max(f.y + (f.altura or 0.0) for f in livres)
    if no.largura is None:
        no.largura = direita + ox
    if no.altura is None:
        no.altura = base + oy


def resolver_relativos(cena: Cena) -> None:
    """Re-resolve %/vw/vh contra o tamanho atual das janelas (resize)."""
    for jan in cena.janelas:
        ref_larg = jan.largura or 800.0
        ref_alt = jan.altura or 600.0
        for no in jan.todos()[1:]:
            for chave, (valor, unidade) in no.medidas.items():
                ref = ref_larg if chave in ("x", "largura") else ref_alt
                resolvido = resolver_medida(
                    A.Medida(valor=valor, unidade=unidade), ref)
                if resolvido is None:
                    continue
                if chave == "x":
                    no.x = resolvido
                elif chave == "y":
                    no.y = resolvido
                elif chave == "largura":
                    no.largura = resolvido
                elif chave == "altura":
                    no.altura = resolvido


def recalcular(cena: Cena) -> None:
    """Pós-medida/resize: relativos + layout (backend-agnóstico)."""
    resolver_relativos(cena)
    for jan in cena.janelas:
        aplicar_layout(jan)
