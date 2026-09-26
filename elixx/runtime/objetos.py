"""Modelo de objetos da ELiXX.

Todo elemento visual herda o comportamento comum do Objeto:

    posição, tamanho, rotação, escala, opacidade, visibilidade,
    estilo, eventos e filhos.

Isso prepara o terreno para animação: animar é interpolar esses
atributos ao longo do tempo (ver elixx/animacao).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import unicodedata


@dataclass
class Objeto:
    tipo: str  # "janela", "botao", "texto", "imagem", "video", "audio"
    nome: str = ""
    posicao: tuple[float, float] = (0.0, 0.0)
    tamanho: tuple[float, float] = (100.0, 100.0)
    rotacao: float = 0.0  # graus, horário (Fase 10: normalizado [0, 360))
    escala: float = 1.0  # legado uniforme (Fase 10: espelha escala_x/y)
    escala_x: float = 1.0
    escala_y: float = 1.0
    opacidade: float = 1.0
    # Fase 10: pivô (ponto de rotação/escala) e camada visual (z).
    pivo_x: float = 50.0
    pivo_y: float = 50.0
    pivo_unidade_x: str = "%"
    pivo_unidade_y: str = "%"
    camada: float = 0.0
    visivel: bool = True
    estilo: dict = field(default_factory=dict)
    eventos: dict = field(default_factory=dict)  # nome -> Bloco (AST)
    filhos: list[Objeto] = field(default_factory=list)
    modelo: list[Objeto] = field(default_factory=list)  # Fase 09: template
    def_origem: str | None = None  # Fase 09: def que gerou (estado local)
    linha: int = 0
    # Fase 02: valores brutos da AST por propriedade (para a Cena resolver
    # unidades relativas como %/vw/vh). Não altera o comportamento da Fase 01.
    bruto: dict = field(default_factory=dict)  # nome -> list[expr AST]
    # Fase 12: metadados de personagem/parte (None fora de personagens).
    personagem: dict | None = None

    def buscar(self, nome: str) -> Objeto | None:
        """Busca um objeto pelo nome, recursivamente."""
        if self.nome == nome:
            return self
        for filho in self.filhos:
            achado = filho.buscar(nome)
            if achado is not None:
                return achado
        return None

    def todos(self) -> list[Objeto]:
        """Lista este objeto e todos os descendentes (pré-ordem)."""
        lista = [self]
        for filho in self.filhos:
            lista.extend(filho.todos())
        return lista


def sem_acentos(texto: str) -> str:
    """Remove acentos (posição→posicao, título→titulo, conteúdo→conteudo)."""
    normalizado = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _medida_para_numero(valor: object) -> float:
    from ..compilador import ast as A

    if isinstance(valor, A.Medida):
        return float(valor.valor)
    if isinstance(valor, A.NumeroLit):
        return float(valor.valor)
    return 0.0


def _angulo_para_graus(valor: object) -> float:
    """Medida de ângulo (graus/deg/rad) ou número (= graus) → graus."""
    import math

    from ..compilador import ast as A

    if isinstance(valor, A.Medida):
        if valor.unidade == "rad":
            return math.degrees(float(valor.valor))
        return float(valor.valor)  # graus, deg (= graus)
    if isinstance(valor, A.NumeroLit):
        return float(valor.valor)
    return 0.0


def _pivo_para_valor(vals: list) -> tuple[tuple[float, str],
                                         tuple[float, str]]:
    """1-2 valores (px ou %) → ((x, unidade), (y, unidade))."""
    from ..compilador import ast as A

    def um(valor: object) -> tuple[float, str]:
        if isinstance(valor, A.Medida) and valor.unidade in ("%", "px"):
            return (float(valor.valor), valor.unidade)
        return (_medida_para_numero(valor), "px")

    primeiro = um(vals[0])
    segundo = um(vals[1]) if len(vals) == 2 else primeiro
    return primeiro, segundo


class FabricaObjetos:
    """Constrói a árvore de Objetos a partir da AST (sem executar nada)."""

    def de_janela(self, no: object, tipo: str = "janela") -> Objeto:
        from ..compilador import ast as A

        assert isinstance(no, A.Janela)
        obj = Objeto(tipo=tipo, nome=no.nome, tamanho=(800.0, 600.0),
                     linha=no.linha)
        for prop in no.propriedades:
            self.aplicar_propriedade(obj, prop)
        for comp in no.componentes:
            if isinstance(comp, A.ItemDef):
                continue  # Fase 14: itens são semânticos (sem Objeto)
            obj.filhos.append(self.de_no_visual(comp))
        for ev in no.eventos:
            obj.eventos[ev.nome] = ev.bloco
        return obj

    def de_no_visual(self, no: object) -> Objeto:
        """Componente, grupo/objeto ou personagem/parte (Fase 12)."""
        from ..compilador import ast as A

        if isinstance(no, A.Personagem):
            return self.de_personagem(no)
        if isinstance(no, A.Parte):
            return self.de_parte(no)
        return self.de_componente(no)

    def de_personagem(self, no: object) -> Objeto:
        """Personagem = contêiner raiz (usa Transform como grupo)."""
        obj = Objeto(tipo="personagem", nome=no.nome, linha=no.linha)
        for prop in no.propriedades:
            self.aplicar_propriedade(obj, prop)
        obj.personagem = _meta_personagem(no)
        for parte in no.partes:
            obj.filhos.append(self.de_parte(parte))
        for filho in no.filhos:
            obj.filhos.append(self.de_no_visual(filho))
        return obj

    def de_parte(self, no: object) -> Objeto:
        """Parte = nó articulável (subpartes + visuais em filhos)."""
        obj = Objeto(tipo="parte", nome=no.nome, linha=no.linha)
        for prop in no.propriedades:
            self.aplicar_propriedade(obj, prop)
        obj.personagem = _meta_parte(no)
        for sub in no.partes:
            obj.filhos.append(self.de_parte(sub))
        for filho in no.filhos:
            obj.filhos.append(self.de_no_visual(filho))
        return obj

    def de_componente(self, no: object) -> Objeto:
        from ..compilador import ast as A
        from ..erros import ErroExecucao

        if not isinstance(no, A.Componente):
            raise ErroExecucao(
                "Instância não expandida (uso interno: rode "
                "expandir_componentes antes de executar).")
        obj = Objeto(tipo=no.tipo, nome=no.nome, linha=no.linha)
        if no.tipo == "modal":
            obj.visivel = False  # Fase 08: modal nasce escondido
        obj.def_origem = getattr(no, "_def_origem", None)
        for prop in no.propriedades:
            self.aplicar_propriedade(obj, prop)
        for filho in no.filhos:
            obj.filhos.append(self.de_componente(filho))
        for modelo in getattr(no, "modelo", []):
            obj.modelo.append(self.de_componente(modelo))
        for ev in no.eventos:
            obj.eventos[ev.nome] = ev.bloco
        return obj

    def aplicar_propriedade(self, obj: Objeto, prop: object) -> None:
        from ..compilador import ast as A
        from ..visual.transform import (normalizar_graus, validar_fator_escala,
                                        validar_opacidade)

        nome = sem_acentos(prop.nome)
        vals = prop.valores
        obj.bruto[nome] = list(vals)
        if nome == "tamanho" and len(vals) in (1, 2):
            largura = _medida_para_numero(vals[0])
            altura = _medida_para_numero(vals[1]) if len(vals) == 2 else largura
            obj.tamanho = (largura, altura)
        elif nome in ("posicao",) and len(vals) == 2:
            obj.posicao = (_medida_para_numero(vals[0]),
                           _medida_para_numero(vals[1]))
        elif nome == "opacidade" and len(vals) == 1:
            valor = _medida_para_numero(vals[0])
            if isinstance(vals[0], A.Medida) and vals[0].unidade == "%":
                valor = valor / 100.0
            obj.opacidade = validar_opacidade(valor, linha=prop.linha)
        elif nome == "rotacao" and len(vals) == 1:
            obj.rotacao = normalizar_graus(_angulo_para_graus(vals[0]),
                                           linha=prop.linha)
        elif nome == "escala" and len(vals) in (1, 2):
            sx = validar_fator_escala(_medida_para_numero(vals[0]),
                                      eixo="escala x", linha=prop.linha)
            sy = validar_fator_escala(
                _medida_para_numero(vals[1]) if len(vals) == 2 else sx,
                eixo="escala y", linha=prop.linha)
            # legado uniforme espelha só quando uniforme (leitura antiga).
            if sx == sy:
                obj.escala = sx
            obj.escala_x, obj.escala_y = sx, sy
        elif nome == "pivo" and len(vals) in (1, 2):
            (px, ux), (py, uy) = _pivo_para_valor(vals)
            obj.pivo_x, obj.pivo_unidade_x = px, ux
            obj.pivo_y, obj.pivo_unidade_y = py, uy
        elif nome == "camada" and len(vals) == 1:
            obj.camada = validar_fator_escala(
                _medida_para_numero(vals[0]), eixo="camada",
                linha=prop.linha)
        elif nome in ("titulo", "texto", "fundo", "cor", "duracao",
                      "movimento") and vals:
            obj.estilo[nome] = vals[0] if len(vals) == 1 else list(vals)
        else:
            obj.estilo[nome] = vals[0] if len(vals) == 1 else list(vals)


def _texto_prop_valor(prop: object) -> str | None:
    """Valor texto simples de propriedade (imagem/vistas/variantes)."""
    from ..compilador import ast as A

    if prop.valores and isinstance(prop.valores[0], A.TextoLit):
        return prop.valores[0].valor
    return None


def _meta_personagem(no: object) -> dict:
    """Metadados do root: poses/capacidades (AST), posse, direção, etc."""
    from ..compilador import ast as A

    meta: dict = {"kind": "personagem", "poses": list(no.poses),
                  "capacidades": list(no.capacidades),
                  "possui": [], "equipa": [],
                  "direcao": "frente", "vistas": {}, "imagem": None,
                  "variantes": {}}
    for prop in no.propriedades:
        nome = sem_acentos(prop.nome)
        if nome in ("possui", "equipa"):
            meta[nome].extend(
                v.valor for v in prop.valores
                if isinstance(v, A.TextoLit))
            continue
        if nome == "direcao":
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["direcao"] = valor.strip().lower()
        elif nome in ("frente", "costas", "esquerda", "direita", "cima",
                      "baixo"):
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["vistas"][nome] = valor
        elif nome == "imagem":
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["imagem"] = valor
        elif prop.nome.startswith("asset_"):
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["variantes"][prop.nome[len("asset_"):]] = valor
    return meta


def _meta_parte(no: object) -> dict:
    """Metadados da parte: junta, limites, capacidades, vistas, etc."""
    meta: dict = {"kind": "parte", "junta": None, "limite_min": None,
                  "limite_max": None, "vistas": {}, "imagem": None,
                  "variantes": {}, "capacidades": list(no.capacidades)}
    for prop in no.propriedades:
        nome = sem_acentos(prop.nome)
        if nome == "junta":
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["junta"] = valor
        elif nome in ("limite_min", "limite_max"):
            meta[nome] = _angulo_meta(prop)
        elif nome in ("frente", "costas", "esquerda", "direita", "cima",
                      "baixo"):
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["vistas"][nome] = valor
        elif nome == "imagem":
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["imagem"] = valor
        elif prop.nome.startswith("asset_"):
            valor = _texto_prop_valor(prop)
            if valor is not None:
                meta["variantes"][prop.nome[len("asset_"):]] = valor
    return meta


def _angulo_meta(prop: object) -> float | None:
    """Ângulo da prop (graus/deg/rad/número) → graus."""
    import math

    from ..compilador import ast as A

    if not prop.valores:
        return None
    valor = prop.valores[0]
    if isinstance(valor, A.Medida):
        numero = float(valor.valor)
        if valor.unidade == "rad":
            numero = math.degrees(numero)
        return numero
    if isinstance(valor, A.NumeroLit):
        return float(valor.valor)
    return None
