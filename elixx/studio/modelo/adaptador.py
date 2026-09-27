"""Adaptador AST → Modelo (F27 CP3) — o coração honesto da fase.

NÃO cria parser. Caminha o `Programa` com `isinstance` e extrai SÓ o
que o AST realmente fornece (nomes, tipos, linhas, alvos, imports,
propriedades de asset). Sem adivinhação: alvo de animação vira
relação só se a entidade existir; asset só de prop conhecida com
texto e extensão conhecida.

IDs determinísticos e únicos por projeto:
arquivo, tela/janela, componente (caminho de contenção),
personagem, parte (qualificada pelo ancestral), pose/expressão,
animacao, funcao/acao/evento/estado/fonte/import, asset.
"""
from __future__ import annotations

import hashlib

from ...erros import ErroELiXX
from .modelo import (EntidadeSemantica, ModeloSemantico,
                     RelacaoSemantica)

__all__ = ["PROPS_ASSET", "EXTENSOES_ASSET", "AdaptadorAST",
           "analisar_texto", "analisar_projeto", "atualizar_arquivo",
           "modelo_para_contexto", "resumo_para_inspetor",
           "mutacao_para_changeset"]

PROPS_ASSET = ("imagem", "src", "som", "video", "icone", "fonte",
               "audio")
"""Propriedades que referenciam asset (resto ignorado, sem chute)."""

EXTENSOES_ASSET = (".png", ".jpg", ".jpeg", ".svg", ".wav", ".mp3",
                   ".mp4", ".webm", ".ttf", ".otf")
"""Extensões reconhecidas (fora daqui = dado, não asset)."""


def _texto_valor(valor) -> str | None:
    """Texto literal do AST (None se não for texto simples)."""
    if type(valor).__name__ == "TextoLit":
        texto = getattr(valor, "valor", None)
        return texto if isinstance(texto, str) else None
    return None


class AdaptadorAST:
    """Programa AST → entidades e relações (leitura pura)."""

    def __init__(self, modelo: ModeloSemantico,
                 arquivo: str = "") -> None:
        if not isinstance(modelo, ModeloSemantico):
            raise ErroELiXX("Semântico: adaptador espera modelo.")
        self.modelo = modelo
        self.arquivo = str(arquivo)

    # ----- entrada -----

    def adaptar_programa(self, programa) -> dict:
        """Extrai tudo que o AST oferece; retorna contagem honesta."""
        import elixx.compilador.ast as A

        if not isinstance(programa, A.Programa):
            raise ErroELiXX("Semântico: espera Programa AST.")
        conta = {"entidades": 0, "relacoes": 0, "ignorados": 0}
        for janela in list(programa.janelas) + list(
                programa.telas):
            self._janela(janela, conta)
        for comp in programa.componentes:
            self._componente_def(comp, conta)
        for funcao in programa.funcoes:
            self._entidade(f"funcao:{funcao.nome}", "funcao",
                            funcao.nome, getattr(funcao, "linha",
                                                 None), {}, conta)
        for acao in programa.acoes:
            nome = getattr(acao, "nome", "")
            self._entidade(f"acao:{nome}", "acao", nome,
                            getattr(acao, "linha", None), {}, conta)
        for imp in programa.imports:
            caminho = getattr(imp, "caminho", "")
            self._entidade(f"import:{caminho}", "import", caminho,
                            getattr(imp, "linha", None),
                            {"caminho": caminho}, conta)
        if programa.estado is not None:
            self._entidade(f"estado:{self.arquivo}", "estado",
                            "estado",
                            getattr(programa.estado, "linha", None),
                            {}, conta)
        for fonte in programa.fontes:
            nome = getattr(fonte, "nome", "")
            self._entidade(f"fonte:{nome}", "fonte", nome,
                            getattr(fonte, "linha", None), {}, conta)
        return conta

    # ----- peças -----

    def _entidade(self, ent_id: str, tipo: str, nome: str,
                  linha, dados: dict, conta: dict
                  ) -> EntidadeSemantica | None:
        try:
            ent = EntidadeSemantica(ent_id, tipo, nome,
                                    self.arquivo, linha, dados)
            self.modelo.adicionar_entidade(ent)
            conta["entidades"] += 1
            return ent
        except ErroELiXX:
            conta["ignorados"] += 1  # duplicata entre arquivos: pula
            return None

    def _relacao(self, origem: str, tipo: str, destino: str,
                 conta: dict) -> None:
        if destino not in self.modelo:
            conta["ignorados"] += 1  # alvo inexistente: sem chute
            return
        try:
            self.modelo.adicionar_relacao(
                RelacaoSemantica(origem, tipo, destino))
            conta["relacoes"] += 1
        except ErroELiXX:
            conta["ignorados"] += 1

    def _janela(self, janela, conta: dict) -> None:
        tipo = "tela" if getattr(janela, "eh_tela", False) else \
            "janela"
        jid = f"{tipo}:{janela.nome}"
        self._entidade(jid, tipo, janela.nome,
                       getattr(janela, "linha", None), {}, conta)
        # Sem retorno antecipado: janela duplicada entre arquivos
        # ainda pode conter membros novos (deduplicação individual
        # abaixo + relações sem duplicata).
        for comp in getattr(janela, "componentes", []):
            self._membro(comp, jid, conta)
        for evento in getattr(janela, "eventos", []):
            self._evento(evento, jid, conta)
        for anim in getattr(janela, "animacoes", []):
            self._animacao(anim, jid, conta)

    def _membro(self, no, dono_id: str, conta: dict) -> None:
        import elixx.compilador.ast as A

        if isinstance(no, A.Personagem):
            self._personagem(no, dono_id, conta)
        elif isinstance(no, A.Componente):
            cid = f"componente:{dono_id.split(':', 1)[1]}." \
                  f"{no.nome or no.tipo}"
            if self._entidade(cid, "componente",
                              no.nome or no.tipo,
                              getattr(no, "linha", None),
                              {"tipo_componente": no.tipo},
                              conta) is None:
                return
            self._relacao(dono_id, "contem", cid, conta)
            for evento in getattr(no, "eventos", []):
                self._evento(evento, cid, conta)
            for filho in getattr(no, "filhos", []):
                self._membro(filho, cid, conta)
            self._assets_de(getattr(no, "propriedades", []), cid,
                            conta)
        else:
            conta["ignorados"] += 1  # Instancia etc.: sem modelo novo

    def _personagem(self, no, dono_id: str, conta: dict) -> None:
        pid = f"personagem:{no.nome}"
        self._entidade(pid, "personagem", no.nome,
                       getattr(no, "linha", None), {}, conta)
        self._relacao(dono_id, "contem", pid, conta)
        for parte in getattr(no, "partes", []):
            self._parte(parte, pid, pid, conta)
        for pose in getattr(no, "poses", []):
            kind = "expressao" if getattr(pose, "expressao",
                                          False) else "pose"
            eid = f"{kind}:{no.nome}.{pose.nome}"
            if self._entidade(eid, kind, pose.nome,
                              getattr(pose, "linha", None),
                              {"personagem": no.nome},
                              conta) is None:
                continue
            self._relacao(pid, "possui", eid, conta)
        self._assets_de(getattr(no, "propriedades", []), pid,
                        conta)

    def _parte(self, parte, pid: str, ancestral_id: str,
               conta: dict) -> None:
        nome = getattr(parte, "nome", "")
        eid = f"parte:{pid.split(':', 1)[1]}.{nome}"
        if self._entidade(eid, "parte", nome,
                          getattr(parte, "linha", None),
                          {"personagem": pid.split(":", 1)[1]},
                          conta) is None:
            return
        self._relacao(ancestral_id, "possui", eid, conta)
        for sub in getattr(parte, "partes", []):
            self._parte(sub, pid, eid, conta)
        self._assets_de(getattr(parte, "propriedades", []), eid,
                        conta)

    def _evento(self, evento, dono_id: str, conta: dict) -> None:
        nome = getattr(evento, "nome", "")
        eid = f"evento:{dono_id.split(':', 1)[1]}.{nome}"
        if self._entidade(eid, "evento", nome,
                          getattr(evento, "linha", None), {},
                          conta) is None:
            return
        self._relacao(dono_id, "possui", eid, conta)

    def _animacao(self, anim, dono_id: str, conta: dict) -> None:
        nome = getattr(anim, "nome", "")
        alvo = getattr(anim, "alvo", "")
        aid = f"animacao:{nome}"
        if self._entidade(aid, "animacao", nome,
                          getattr(anim, "linha", None),
                          {"alvo": alvo,
                           "duracao_ms": getattr(
                               anim, "duracao_ms", 500.0)},
                          conta) is None:
            return
        self._relacao(dono_id, "define", aid, conta)
        # atua_em só com alvo resolvido (sem adivinhar nomes)
        for eid in self._alvos_por_nome(alvo):
            self._relacao(aid, "atua_em", eid, conta)

    def _alvos_por_nome(self, alvo: str) -> list:
        if not alvo:
            return []
        base = alvo.split(".")[-1]
        return [e.id for e in self.modelo.entidades()
                if e.nome == base and e.tipo in (
                    "parte", "componente", "personagem")]

    def _assets_de(self, propriedades, dono_id: str,
                   conta: dict) -> None:
        for prop in propriedades or []:
            nome = getattr(prop, "nome", "")
            if nome not in PROPS_ASSET:
                continue
            for valor in getattr(prop, "valores", []):
                texto = _texto_valor(valor)
                if texto is None:
                    continue
                base = texto.split("/")[-1]
                if not base.lower().endswith(EXTENSOES_ASSET):
                    continue
                aid = f"asset:{base}"
                if aid not in self.modelo:
                    if self._entidade(aid, "asset", base, None,
                                      {"caminho": texto},
                                      conta) is None:
                        continue
                self._relacao(dono_id, "usa_asset", aid, conta)


# ----- operações de projeto (CP4) -----

def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def analisar_texto(modelo: ModeloSemantico, texto: str,
                   arquivo: str) -> dict:
    """Texto .elixx → entidades (parse oficial; sem executar)."""
    if not isinstance(texto, str):
        raise ErroELiXX("Semântico: texto em string.")
    from ...compilador.lexer import tokenizar
    from ...compilador.parser import Parser

    try:
        programa = Parser(tokenizar(texto)).parse()
    except Exception as exc:
        modelo.adicionar_diagnostico(
            {"codigo": "parse", "arquivo": arquivo,
             "motivo": str(getattr(exc, "mensagem", exc))[:200]})
        modelo.registrar_arquivo(arquivo, status="erro_parse")
        return {"entidades": 0, "relacoes": 0, "ignorados": 0,
                "erro": True}
    modelo.registrar_arquivo(arquivo, status="ok",
                             conteudo_hash=_hash(texto))
    return AdaptadorAST(modelo, arquivo).adaptar_programa(programa)


def analisar_projeto(modelo: ModeloSemantico, raiz) -> dict:
    """Workspace → .elixx → parser → modelo (sem executar nada)."""
    from pathlib import Path

    if not isinstance(modelo, ModeloSemantico):
        raise ErroELiXX("Semântico: espera modelo.")
    base = Path(raiz).resolve()
    if not base.is_dir():
        raise ErroELiXX("Semântico: raiz ausente.")
    total = {"arquivos": 0, "entidades": 0, "relacoes": 0,
             "ignorados": 0, "erros": 0}
    for item in sorted(base.rglob("*.elixx"),
                       key=lambda p: str(p)):
        try:
            rel = str(item.resolve().relative_to(base)).replace(
                "\\", "/")
        except ValueError:
            continue
        try:
            texto = item.read_text(encoding="utf-8")
        except OSError:
            continue
        parte = analisar_texto(modelo, texto, rel)
        total["arquivos"] += 1
        total["entidades"] += parte["entidades"]
        total["relacoes"] += parte["relacoes"]
        total["ignorados"] += parte["ignorados"]
        total["erros"] += 1 if parte.get("erro") else 0
    return total


def atualizar_arquivo(modelo: ModeloSemantico, relativo: str,
                      texto: str) -> dict:
    """Remove entidades do arquivo e re-analisa (sem watcher)."""
    if not isinstance(modelo, ModeloSemantico):
        raise ErroELiXX("Semântico: espera modelo.")
    caminho = str(relativo).replace("\\", "/")
    if caminho.startswith("/") or ".." in caminho.split("/"):
        raise ErroELiXX("Semântico: arquivo fora do projeto.")
    for ent in [e for e in modelo.entidades()
                if e.arquivo == caminho]:
        modelo.remover_entidade(ent.id)
    modelo.remover_arquivo_registro(caminho)
    return analisar_texto(modelo, texto, caminho)


# ----- pontes opcionais (CP6; sem tocar F25/F26) -----

def resumo_para_inspetor(modelo: ModeloSemantico,
                         ent_id: str) -> dict:
    """Studio: entidade + origem + tipo + relações (só leitura)."""
    from .consulta import ConsultaSemantica

    return ConsultaSemantica(modelo).vizinhanca(ent_id)


def modelo_para_contexto(contexto, modelo: ModeloSemantico,
                         max_entidades: int = 50):
    """Agent: entidades como símbolos (opcional; Agent intacto)."""
    n = 0
    for ent in modelo.entidades():
        if n >= max_entidades:
            break
        contexto.adicionar_simbolo(
            {"nome": ent.id, "tipo": f"semantico:{ent.tipo}",
             "arquivo": ent.arquivo})
        n += 1
    return contexto


def mutacao_para_changeset(mutacao, modelo: ModeloSemantico):
    """Mutação → ChangeSet F26 PROPOSTO (sem aplicar, sem disco)."""
    from ..agent.mudancas import AgentChange, ChangeSet
    from .modelo import MutacaoSemantica

    if not isinstance(mutacao, MutacaoSemantica):
        raise ErroELiXX("Semântico: espera MutacaoSemantica.")
    if mutacao.alvo not in modelo:
        raise ErroELiXX(f'Semântico: alvo "{mutacao.alvo}" '
                        "ausente.")
    return ChangeSet([AgentChange(
        "__proposta__.md", "criar",
        conteudo_novo=f"mutacao: {mutacao.alvo}."
                       f"{mutacao.propriedade} = "
                       f"{mutacao.valor!r}\n",
        descricao=f"Aplicar {mutacao.alvo}."
                  f"{mutacao.propriedade} (revisão humana; o "
                  "modelo não escreve código sozinho).")])
