"""Gerador determinístico ELiXX (F32 CP2) — operação → alteração.

Só construções comprováveis pelo parser: SUBSTITUIR linha de
propriedade localizada via AST (indentação preservada), REMOVER a
mesma linha, INSERIR snippet no fim do arquivo. Todo candidato é
parseado e relocalizado antes de virar ChangeSet; sem mapeamento =
GERADOR_NAO_SUPORTADO (sem invenção de sintaxe).
"""
from __future__ import annotations

from ...erros import ErroELiXX
from .localizacao import (LocalizacaoCodigo, RegiaoCodigo,
                          localizar_propriedade)
from .mudanca import AlteracaoCodigo

__all__ = ["gerar_alteracao", "validar_candidato",
           "suportado_pelo_gerador"]


def suportado_pelo_gerador(operacao) -> bool:
    """Tipo tem mapeamento seguro? (sem olhar arquivos)."""
    tipo = operacao.tipo if hasattr(operacao, "tipo") \
        else operacao.get("tipo", "")
    alt = operacao.alteracao if hasattr(operacao, "alteracao") \
        else operacao.get("alteracao", {})
    if tipo == "alterar_propriedade":
        return bool(alt.get("propriedade")
                    and alt.get("valor_texto") is not None)
    if tipo in ("adicionar", "adicionar_evento"):
        return bool(alt.get("snippet"))
    if tipo in ("remover", "remover_evento"):
        return bool(alt.get("propriedade"))
    return False


def _indentacao(linha: str) -> str:
    return linha[:len(linha) - len(linha.lstrip(" \t"))]


def gerar_alteracao(operacao, entidade, texto_atual: str):
    """SemanticOperation (+alteracao) → AlteracaoCodigo.

    `operacao.alteracao` carrega: {arquivo, propriedade?, valor_texto?
    snippet?, remover?}. Cirúrgico: UMA linha de propriedade, ou
    snippet no fim. Fora disso: GERADOR_NAO_SUPORTADO.
    """
    if not suportado_pelo_gerador(operacao):
        tipo = operacao.tipo if hasattr(operacao, "tipo") \
            else operacao.get("tipo", "")
        raise ErroELiXX(f"GERADOR_NAO_SUPORTADO: {tipo} sem "
                        "mapeamento seguro (propriedade/snippet "
                        "explícitos).")
    tipo = operacao.tipo if hasattr(operacao, "tipo") \
        else operacao.get("tipo", "")
    alt = operacao.alteracao if hasattr(operacao, "alteracao") \
        else operacao.get("alteracao", {})
    arquivo = str(alt.get("arquivo", ""))
    if not arquivo:
        raise ErroELiXX("CODIGO_ALVO_NAO_ENCONTRADO: alteração sem "
                        "arquivo.")
    if tipo == "alterar_propriedade" and alt.get("propriedade") \
            and alt.get("valor_texto") is not None:
        return _substituir_propriedade(
            entidade, texto_atual, arquivo,
            str(alt["propriedade"]), str(alt["valor_texto"]),
            tipo)
    if tipo in ("adicionar", "adicionar_evento") and alt.get(
            "snippet"):
        return _inserir_fim(entidade, texto_atual, arquivo,
                            str(alt["snippet"]), tipo)
    if tipo in ("remover", "remover_evento") and alt.get(
            "propriedade"):
        return _remover_propriedade(
            entidade, texto_atual, arquivo,
            str(alt["propriedade"]), tipo)
    raise ErroELiXX(f"GERADOR_NAO_SUPORTADO: {tipo} sem mapeamento "
                    "seguro (propriedade/snippet explícitos).")


def _linha_de(texto: str, numero: int) -> str:
    linhas = texto.split("\n")
    if not 1 <= numero <= len(linhas):
        raise ErroELiXX("CODIGO_REGIAO_ALTERADA: linha fora do "
                        "arquivo.")
    return linhas[numero - 1]


def _substituir_propriedade(entidade, texto: str, arquivo: str,
                            propriedade: str, valor_texto: str,
                            origem: str) -> AlteracaoCodigo:
    loc = localizar_propriedade(entidade, texto, propriedade)
    original = _linha_de(texto, loc.inicio_linha)
    if propriedade not in original:
        raise ErroELiXX("CODIGO_ALTERACAO_INSEGURA: linha sem a "
                        "propriedade (sanidade textual).")
    nova = f"{_indentacao(original)}{propriedade}: {valor_texto}"
    regiao = RegiaoCodigo(arquivo, loc.inicio_linha,
                          loc.fim_linha, original)
    ent_id = entidade.id if hasattr(entidade, "id") \
        else entidade.get("id", "")
    return AlteracaoCodigo(
        arquivo, regiao, tipo="SUBSTITUIR",
        conteudo_anterior=original, conteudo_novo=nova,
        motivo=f"{origem} {propriedade}", entidade_id=ent_id,
        operacao_origem=origem)


def _remover_propriedade(entidade, texto: str, arquivo: str,
                         propriedade: str,
                         origem: str) -> AlteracaoCodigo:
    loc = localizar_propriedade(entidade, texto, propriedade)
    original = _linha_de(texto, loc.inicio_linha)
    if propriedade not in original:
        raise ErroELiXX("CODIGO_ALTERACAO_INSEGURA: linha sem a "
                        "propriedade.")
    regiao = RegiaoCodigo(arquivo, loc.inicio_linha,
                          loc.fim_linha, original)
    ent_id = entidade.id if hasattr(entidade, "id") \
        else entidade.get("id", "")
    return AlteracaoCodigo(
        arquivo, regiao, tipo="REMOVER", conteudo_anterior=original,
        conteudo_novo="", motivo=f"{origem} remover {propriedade}",
        entidade_id=ent_id, operacao_origem=origem)


def _inserir_fim(entidade, texto: str, arquivo: str,
                 snippet: str, origem: str) -> AlteracaoCodigo:
    if not snippet.strip():
        raise ErroELiXX("CODIGO_ALTERACAO_INSEGURA: snippet vazio.")
    if len(snippet) > 100_000:
        raise ErroELiXX("CODIGO_ALTERACAO_INSEGURA: snippet gigante.")
    linhas = texto.split("\n")
    fim = len(linhas) + 1  # append (aplicar_texto insere após fim)
    regiao = RegiaoCodigo(arquivo, fim, fim, "")
    if entidade is None:
        ent_id = ""
    else:
        ent_id = entidade.id if hasattr(entidade, "id") \
            else entidade.get("id", "")
    alt = AlteracaoCodigo(
        arquivo, regiao, tipo="INSERIR", conteudo_anterior="",
        conteudo_novo=snippet.rstrip("\n"),
        motivo=f"{origem} inserir bloco", entidade_id=ent_id,
        operacao_origem=origem)
    # INSERIR fora de região AST: valida o candidato aqui mesmo.
    validar_candidato(alt, texto)
    return alt


def validar_candidato(alteracao: AlteracaoCodigo,
                      texto_atual: str, entidade=None) -> dict:
    """Candidato parseia + entidade relocalizável? (sem aplicar)."""
    from ...compilador.lexer import tokenizar
    from ...compilador.parser import Parser

    try:
        candidato = alteracao.aplicar_texto(texto_atual)
    except ErroELiXX as exc:
        return {"ok": False, "codigo": "CODIGO_REGIAO_ALTERADA",
                "motivo": str(exc)[:200]}
    try:
        Parser(tokenizar(candidato)).parse()
    except Exception as exc:
        detalhe = getattr(exc, "mensagem", None) or str(exc)
        return {"ok": False, "codigo": "CODIGO_RESULTADO_INVALIDO",
                "motivo": str(detalhe)[:200]}
    if entidade is not None:
        from .localizacao import localizar_entidade

        try:
            localizar_entidade(entidade, candidato)
        except ErroELiXX as exc:
            return {"ok": False,
                    "codigo": "CODIGO_ALVO_NAO_ENCONTRADO",
                    "motivo": str(exc)[:200]}
    return {"ok": True, "codigo": "ok",
            "motivo": "Candidato válido.",
            "linhas": len(candidato.split("\n"))}
