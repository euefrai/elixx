"""Localização de código (F32 CP1) — evidência AST, nunca chute.

`LocalizacaoCodigo` marca arquivo + linhas + entidade + como foi
encontrada. `RegiaoCodigo` valida conteúdo atual antes de qualquer
aplicação (mudança externa entre proposta e aprovação = recusa).
Linhas vêm de `linha` real dos nós AST (F01); sem evidência, a
localização é INDISPONÍVEL (erro, não invenção).
"""
from __future__ import annotations

from ...erros import ErroELiXX

__all__ = ["LocalizacaoCodigo", "RegiaoCodigo",
           "localizar_entidade", "localizar_propriedade"]


def _e_dado(valor, prof: int = 0) -> bool:
    import math

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


class LocalizacaoCodigo:
    """Onde uma entidade mora no código (imutável, serializável)."""

    def __init__(self, arquivo: str, inicio_linha: int,
                 fim_linha: int, tipo: str, entidade_id: str,
                 evidencia: str = "ast") -> None:
        if not isinstance(arquivo, str) or not arquivo.strip():
            raise ErroELiXX("Código: arquivo não vazio.")
        for rotulo, valor in (("inicio_linha", inicio_linha),
                              ("fim_linha", fim_linha)):
            if not isinstance(valor, int) or valor < 1:
                raise ErroELiXX(f"Código: {rotulo} ≥ 1.")
        if fim_linha < inicio_linha:
            raise ErroELiXX("Código: fim antes do início.")
        self.arquivo = arquivo.strip()
        self.inicio_linha = inicio_linha
        self.fim_linha = fim_linha
        self.tipo = str(tipo)
        self.entidade_id = str(entidade_id)
        self.evidencia = str(evidencia)

    def to_dict(self) -> dict:
        return {"arquivo": self.arquivo,
                "inicio_linha": self.inicio_linha,
                "fim_linha": self.fim_linha, "tipo": self.tipo,
                "entidade_id": self.entidade_id,
                "evidencia": self.evidencia}

    @staticmethod
    def from_dict(dados: dict) -> LocalizacaoCodigo:
        if not isinstance(dados, dict):
            raise ErroELiXX("Código: localização precisa de dict.")
        return LocalizacaoCodigo(
            dados.get("arquivo", ""),
            dados.get("inicio_linha", 0),
            dados.get("fim_linha", 0),
            dados.get("tipo", ""), dados.get("entidade_id", ""),
            evidencia=dados.get("evidencia", "ast"))

    def __repr__(self) -> str:
        return (f"LocalizacaoCodigo({self.arquivo}:"
                f"{self.inicio_linha}-{self.fim_linha} "
                f"{self.entidade_id})")


class RegiaoCodigo:
    """Região editável + conteúdo esperado (anti-stale)."""

    def __init__(self, arquivo: str, inicio: int, fim: int,
                 conteudo_esperado: str = "") -> None:
        self.local = LocalizacaoCodigo(arquivo, inicio, fim,
                                       "regiao", "")
        if not isinstance(conteudo_esperado, str):
            raise ErroELiXX("Código: conteúdo esperado em texto.")
        self.conteudo_esperado = conteudo_esperado

    def verificar(self, texto_atual: str) -> dict:
        """Conteúdo atual == esperado? (False = rejeitar aplicação)."""
        if not isinstance(texto_atual, str):
            raise ErroELiXX("Código: texto atual em string.")
        linhas = texto_atual.split("\n")
        if self.local.fim_linha > len(linhas):
            if self.local.inicio_linha == len(linhas) + 1 \
                    and not self.conteudo_esperado:
                return {"ok": True, "codigo": "ok",
                        "motivo": "Anexo no fim (append puro)."}
            return {"ok": False,
                    "codigo": "CODIGO_REGIAO_ALTERADA",
                    "motivo": "Região além do fim do arquivo."}
        atual = "\n".join(
            linhas[self.local.inicio_linha - 1:
                   self.local.fim_linha])
        if atual != self.conteudo_esperado:
            return {"ok": False,
                    "codigo": "CODIGO_REGIAO_ALTERADA",
                    "motivo": "Conteúdo mudou desde a proposta."}
        return {"ok": True, "codigo": "ok",
                "motivo": "Região íntegra."}

    def to_dict(self) -> dict:
        return {"arquivo": self.local.arquivo,
                "inicio": self.local.inicio_linha,
                "fim": self.local.fim_linha,
                "conteudo_esperado": self.conteudo_esperado}

    def __repr__(self) -> str:
        return (f"RegiaoCodigo({self.local.arquivo}:"
                f"{self.local.inicio_linha}-{self.local.fim_linha})")


# ----- localização por evidência AST -----

def _programa_de(texto: str):
    from ...compilador.lexer import tokenizar
    from ...compilador.parser import Parser

    return Parser(tokenizar(texto)).parse()


def _nos_janela(janela):
    import elixx.compilador.ast as A

    for membro in getattr(janela, "componentes", []):
        yield membro
        if isinstance(membro, A.Personagem):
            for parte in getattr(membro, "partes", []):
                yield from _nos_parte(parte)


def _nos_parte(parte):
    yield parte
    for sub in getattr(parte, "partes", []):
        yield from _nos_parte(sub)


def _candidatos(programa):
    import elixx.compilador.ast as A

    for janela in list(programa.janelas) + list(programa.telas):
        yield ("janela" if not getattr(janela, "eh_tela", False)
               else "tela", janela)
        yield from (("membro", m) for m in _nos_janela(janela))
    for funcao in programa.funcoes:
        yield ("funcao", funcao)
    for acao in programa.acoes:
        yield ("acao", acao)
    for comp in programa.componentes:
        yield ("componente_def", comp)


def _nome_de(kind: str, no) -> str:
    if kind in ("janela", "tela", "funcao", "acao",
                "componente_def"):
        return str(getattr(no, "nome", ""))
    return str(getattr(no, "nome", getattr(no, "tipo", "")))


def _classe_ok(tipo_entidade: str, no) -> bool:
    """Confere classe AST × tipo F27 (sem casar homônimos errados)."""
    import elixx.compilador.ast as A

    mapa = {"personagem": A.Personagem, "parte": A.Parte,
            "janela": A.Janela, "tela": A.Janela,
            "componente": A.Componente,
            "componente_def": A.ComponenteDef, "funcao": A.Funcao,
            "acao": A.AcaoDef}
    esperada = mapa.get(str(tipo_entidade))
    return esperada is None or isinstance(no, esperada)


def localizar_entidade(entidade, texto: str):
    """Entidade F27 + texto → LocalizacaoCodigo (evidência AST).

    Casa tipo+nome na AST; sem par = CODIGO_LOCALIZACAO_INDISPONIVEL.
    """
    tipo = entidade.tipo if hasattr(entidade, "tipo") \
        else entidade.get("tipo", "")
    nome = entidade.nome if hasattr(entidade, "nome") \
        else entidade.get("nome", "")
    arquivo = entidade.arquivo if hasattr(entidade, "arquivo") \
        else entidade.get("arquivo", "")
    try:
        programa = _programa_de(texto)
    except Exception as exc:
        raise ErroELiXX(f"CODIGO_PARSE_FALHOU: {exc}"[:300])
    for kind, no in _candidatos(programa):
        if _nome_de(kind, no) != nome:
            continue
        if not _classe_ok(tipo, no):
            continue
        linha = int(getattr(no, "linha", 0) or 0)
        if linha < 1:
            continue
        return LocalizacaoCodigo(arquivo, linha, linha, tipo,
                                 getattr(entidade, "id",
                                         f"{tipo}:{nome}"),
                                 evidencia=f"ast:{kind}")
    raise ErroELiXX(f"CODIGO_LOCALIZACAO_INDISPONIVEL: {tipo} "
                    f'"{nome}" sem evidência no AST.')


def localizar_propriedade(entidade, texto: str,
                          propriedade: str):
    """(entidade, prop) → LocalizacaoCodigo da linha da propriedade.

    Caminha até o nó dono (janela/personagem/parte/componente) e casa
    a Propriedade pelo nome. Sem nó ou sem prop = indisponível.
    """
    tipo = entidade.tipo if hasattr(entidade, "tipo") \
        else entidade.get("tipo", "")
    nome = entidade.nome if hasattr(entidade, "nome") \
        else entidade.get("nome", "")
    arquivo = entidade.arquivo if hasattr(entidade, "arquivo") \
        else entidade.get("arquivo", "")
    try:
        programa = _programa_de(texto)
    except Exception as exc:
        raise ErroELiXX(f"CODIGO_PARSE_FALHOU: {exc}"[:300])
    for kind, no in _candidatos(programa):
        if _nome_de(kind, no) != nome:
            continue
        if tipo in ("personagem", "parte", "janela", "tela",
                    "componente", "funcao", "acao") \
                and not _classe_ok(tipo, no):
            continue
        for dono in _donos(no):
            for prop in getattr(dono, "propriedades", []):
                if getattr(prop, "nome", "") == propriedade:
                    linha = int(getattr(prop, "linha", 0) or 0)
                    if linha < 1:
                        continue
                    ent_id = getattr(entidade, "id",
                                     f"{tipo}:{nome}")
                    return LocalizacaoCodigo(
                        arquivo, linha, linha, tipo, ent_id,
                        evidencia="ast:propriedade")
    raise ErroELiXX(f"CODIGO_LOCALIZACAO_INDISPONIVEL: "
                    f'propriedade "{propriedade}" de {tipo} '
                    f'"{nome}".')


def _donos(no):
    import elixx.compilador.ast as A

    yield no
    if isinstance(no, A.Personagem):
        for parte in getattr(no, "partes", []):
            yield from _nos_parte(parte)
