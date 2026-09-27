"""UX headless do Studio 2.0 (Fase 38) — modelos sem Tk.

Abas de editor, destaque via lexer oficial, árvore formatada,
resumo do agent, zoom de preview (estado) e seções do inspector.
Tudo testável sem display; Tk só espelha.
"""
from __future__ import annotations

from ..erros import ErroELiXX
from .workspace_ui import destacar_lexico

__all__ = [
    "ZOOM_NIVEIS", "AbasEditor", "SecaoInspector",
    "FocusState", "PropostasTracker",
    "cabecalho_arquivo", "destacar_semantico",
    "formatar_arvore", "resumo_agente",
    "entidade_na_linha",
]


class FocusState:
    """Foco preservando anterior (Esc restaura; sem destruir)."""

    def __init__(self) -> None:
        self.ativo: str | None = None
        self.anterior: list[str] = []

    def entrar(self, layout, paineis: list) -> list[str]:
        from .workspace_ui import Layout as _Layout

        if self.ativo is not None:
            raise ErroELiXX("Foco já ativo (saia antes).")
        if not paineis:
            raise ErroELiXX("Foco precisa de painéis.")
        for painel in paineis:
            if painel not in _Layout().paineis_visiveis() and \
                    painel not in ("project", "editor",
                                   "preview", "inspector",
                                   "console", "timeline",
                                   "diagnosticos", "agent",
                                   "plano", "raciocinio"):
                raise ErroELiXX(f'Painel "{painel}" inválido.')
        self.anterior = list(layout.paineis_visiveis())
        for painel in list(layout.visivel):
            layout.visivel[painel] = painel in paineis
        self.ativo = "+".join(paineis)
        return list(layout.paineis_visiveis())

    def sair(self, layout) -> list[str]:
        if self.ativo is None:
            raise ErroELiXX("Foco inativo.")
        for painel in list(layout.visivel):
            layout.visivel[painel] = painel in self.anterior
        self.ativo = None
        self.anterior = []
        return list(layout.paineis_visiveis())

    def __repr__(self) -> str:
        return f"FocusState({self.ativo})"


class PropostasTracker:
    """Propostas ChangeSet (aprovar/aplicar/desfazer última)."""

    _contador = 0

    def __init__(self) -> None:
        self.propostas: list[dict] = []
        self.aplicadas: list = []

    def adicionar(self, changeset, descricao: str = "") -> str:
        PropostasTracker._contador += 1
        pid = f"prop_{PropostasTracker._contador:03d}"
        self.propostas.append({"id": pid, "descricao": str(
            descricao)[:200], "changeset": changeset,
            "estado": changeset.estado})
        return pid

    def obter(self, pid: str):
        for p in self.propostas:
            if p["id"] == str(pid):
                return p
        raise ErroELiXX(f'Proposta "{pid}" ausente.')

    def aprovar(self, pid: str):
        from .agent import Approval

        proposta = self.obter(pid)
        Approval("manual").aprovar_tudo(proposta["changeset"])
        proposta["estado"] = "aprovado"
        return proposta

    def aplicar(self, pid: str, workspace):
        proposta = self.obter(pid)
        if proposta["estado"] != "aprovado":
            raise ErroELiXX("Proposta exige aprovação.")
        out = proposta["changeset"].aplicar(workspace)
        proposta["estado"] = "aplicado"
        self.aplicadas.append(proposta["changeset"])
        return out

    def desfazer_ultima(self, workspace) -> dict:
        if not self.aplicadas:
            raise ErroELiXX("Nada aplicado para desfazer.")
        cs = self.aplicadas.pop()
        out = cs.desfazer(workspace)
        for p in self.propostas:
            if p["changeset"] is cs:
                p["estado"] = "desfeito"
        return out

    def listar(self) -> list[dict]:
        return [{"id": p["id"], "descricao": p["descricao"],
                 "estado": p["estado"]} for p in self.propostas]


def propor_transformacao(workspace, modelo, ent_id: str,
                         props: dict, snap: int = 0):
    """Gizmo/inspector → ChangeSet proposto (nunca escreve direto).

    Para cada prop: localiza via F32, aplica snap, compõe o texto
    final em memória e valida no parser. Uma única mudança `editar`
    por arquivo. Falha honesta quando impossível.
    """
    from .agent.mudancas import AgentChange, ChangeSet
    from .codigo.gerador import gerar_alteracao, validar_candidato
    from .codigo.localizacao import localizar_propriedade
    from .codigo.sincronizador import SincronizadorCodigo
    from .agent.operacoes import SemanticOperation

    if not isinstance(props, dict) or not props:
        raise ErroELiXX("Proposta precisa de propriedades.")
    ent = next((e for e in modelo.entidades()
                if e.id == str(ent_id)), None)
    if ent is None:
        raise ErroELiXX(f'Entidade "{ent_id}" ausente.')
    sinc = SincronizadorCodigo(workspace, modelo)
    por_arquivo: dict[str, str] = {}
    for prop, valor in props.items():
        op = SemanticOperation(
            "alterar_propriedade", {"nome": ent.nome},
            {"propriedade": prop},
            alteracao={"arquivo": ent.arquivo,
                       "propriedade": prop,
                       "valor_texto": _texto_valor(valor, snap)})
        texto, alvo = sinc._texto_e_entidade(op)
        if alvo.id != ent.id:
            raise ErroELiXX("Proposta: alvo divergiu.")
        alt = gerar_alteracao(op, alvo, texto)
        veredito = validar_candidato(alt, texto, alvo)
        if not veredito["ok"]:
            raise ErroELiXX(f"Proposta: {veredito['codigo']}: "
                            f"{veredito['motivo']}")
        base = por_arquivo.get(ent.arquivo, texto)
        por_arquivo[ent.arquivo] = alt.aplicar_texto(base)
    cs = ChangeSet()
    for arquivo, novo in sorted(por_arquivo.items()):
        atual = workspace.resolver(arquivo).read_text(
            encoding="utf-8")
        from .editor import diagnosticar_texto

        erros = [d for d in diagnosticar_texto(novo, arquivo)
                 if d.severidade == "error"]
        if erros:
            raise ErroELiXX(f"Proposta inválida em {arquivo}: "
                            f"{erros[0].mensagem[:150]}")
        cs.adicionar(AgentChange(
            arquivo, "editar" if workspace.existe(arquivo)
            else "criar", conteudo_novo=novo,
            descricao=f"transformar {ent_id}"))
        _ = atual
    return cs


def _texto_valor(valor, snap: int) -> str:
    if isinstance(valor, bool):
        raise ErroELiXX("Valor precisa ser texto/número.")
    if isinstance(valor, (int, float)):
        import math

        numero = float(valor)
        if not math.isfinite(numero):
            raise ErroELiXX("Valor finito.")
        if snap not in (0, 1, 5, 10):
            raise ErroELiXX("Snap em 0/1/5/10.")
        if snap:
            numero = float(math.floor(numero / snap + 0.5)) * snap
        return str(int(numero)) if numero.is_integer() else str(
            numero)
    texto = str(valor)
    if not texto.strip() or len(texto) > 500:
        raise ErroELiXX("Valor textual curto e não vazio.")
    return texto


def entidade_na_linha(modelo, arquivo: str, linha: int):
    """Entidade do arquivo mais próxima acima da linha (F27+F32).

    Sem invenção: só retorna entidade cuja linha ≤ cursor; None se
    nenhuma. Editor informa; seleção decide.
    """
    candidatas = [e for e in modelo.entidades()
                  if e.arquivo == str(arquivo)
                  and (e.linha or 0) >= 1
                  and e.linha <= int(linha)]
    if not candidatas:
        return None
    candidatas.sort(key=lambda e: (-e.linha, e.id))
    return candidatas[0]

ZOOM_NIVEIS = (50, 75, 100, 125, 150, "Ajustar")
"""Níveis do controle de zoom (estado visual honesto)."""


def destacar_semantico(texto: str) -> list[tuple]:
    """Lexer oficial → [(ini, fim, classe)] (fallback lexical).

    Classes: palavra (PALAVRA), nome (IDENT), string (STRING),
    numero (NUMERO+). Erro léxico = fallback sem exceção.
    """
    if not isinstance(texto, str):
        raise ErroELiXX("Destaque precisa de texto.")
    try:
        from ..compilador.lexer import tokenizar

        tokens = tokenizar(texto)
    except Exception:
        return destacar_lexico(texto)
    linhas = texto.splitlines(keepends=True)
    inicios = [0]
    for linha in linhas:
        inicios.append(inicios[-1] + len(linha))
    marcas = []
    for tok in tokens:
        if tok.tipo == "EOF":
            continue
        classe = {"PALAVRA": "palavra", "STRING": "string",
                  "NUMERO": "numero"}.get(tok.tipo, "nome")
        try:
            base = inicios[tok.linha - 1]
        except IndexError:
            continue
        candidatos = [str(tok.valor)]
        try:
            numero = float(tok.valor)
            if numero.is_integer():
                candidatos.append(str(int(numero)))
        except (TypeError, ValueError):
            pass
        ini = -1
        fatia = ""
        for tentativa in candidatos:
            if texto[base + max(0, tok.coluna - 1):
                     base + max(0, tok.coluna - 1)
                     + len(tentativa)] == tentativa:
                ini = base + max(0, tok.coluna - 1)
                fatia = tentativa
                break
        if ini < 0:
            limite = base + len(linhas[tok.linha - 1]) \
                if tok.linha - 1 < len(linhas) else len(texto)
            for tentativa in candidatos:
                achou = texto.find(tentativa, base, limite)
                if achou >= 0:
                    ini, fatia = achou, tentativa
                    break
        if ini < 0:
            continue
        marcas.append((ini, ini + len(fatia), classe))
    marcas.sort()
    return marcas


def cabecalho_arquivo(caminho: str, dirty: bool) -> str:
    """`main.elixx ●` (● = não salvo) ou `main.elixx`."""
    nome = str(caminho).split("/")[-1].split("\\")[-1]
    if not nome:
        raise ErroELiXX("Cabeçalho precisa de caminho.")
    return f"{nome} ●" if dirty else nome


class AbasEditor:
    """Abas sobre GerenciadorDocumentos (sem duplicar docs)."""

    def __init__(self, gerenciador) -> None:
        from .documento import GerenciadorDocumentos

        if not isinstance(gerenciador, GerenciadorDocumentos):
            raise ErroELiXX("Abas esperam GerenciadorDocumentos.")
        self.gerenciador = gerenciador
        self.ativa: str | None = None

    def abrir(self, caminho: str, texto: str = ""):
        doc = self.gerenciador.abrir(caminho, texto)
        self.ativa = caminho
        return doc

    def trocar(self, caminho: str):
        self.gerenciador.obter(caminho)
        self.ativa = caminho
        return caminho

    def fechar(self, caminho: str):
        self.gerenciador.fechar(caminho)
        if self.ativa == caminho:
            abertos = self.gerenciador.abertos()
            self.ativa = abertos[-1] if abertos else None
        return self.ativa

    def lista(self) -> list[dict]:
        return [{"caminho": c,
                 "cabecalho": cabecalho_arquivo(
                     c, self.gerenciador.obter(c).dirty),
                 "ativa": c == self.ativa}
                for c in self.gerenciador.abertos()]

    def __repr__(self) -> str:
        return f"AbasEditor({len(self.gerenciador.abertos())})"


class SecaoInspector:
    """Seção ▾/▸ com campos reais (estado serializável)."""

    def __init__(self, titulo: str, campos: dict | None = None,
                 aberta: bool = True) -> None:
        if not str(titulo).strip():
            raise ErroELiXX("Seção precisa de título.")
        self.titulo = str(titulo)
        self.campos = dict(campos or {})
        self.aberta = bool(aberta)

    def alternar(self) -> bool:
        self.aberta = not self.aberta
        return self.aberta

    def to_dict(self) -> dict:
        return {"titulo": self.titulo,
                "campos": dict(self.campos),
                "aberta": self.aberta}

    def __repr__(self) -> str:
        marca = "▾" if self.aberta else "▸"
        return f"SecaoInspector({marca} {self.titulo})"


_ICONES_TIPO = {
    "pasta": "▾", "arquivo": "•", "personagem": "◆",
    "cena": "▣", "asset": "▤",
}
"""Ícones textuais por tipo (sem emoji, sem biblioteca)."""


def formatar_arvore(nos: list, atual: str | None = None,
                    sujos: list | None = None) -> list[str]:
    """Nós → linhas `[ícone] nome ●` (indentação por categoria).

    Categorias (arquivo/personagem/cena/asset) viram grupos com
    indentação; arquivo atual e dirty marcados. Só dados de entrada.
    """
    sujos_txt = set(sujos or [])
    grupos: dict[str, list] = {}
    for no in nos or []:
        if not isinstance(no, dict):
            raise ErroELiXX("Árvore: nós em dicts.")
        grupos.setdefault(str(no.get("tipo", "arquivo")),
                          []).append(no)
    ordem = ["arquivo", "cena", "personagem", "asset"]
    extras = sorted(set(grupos) - set(ordem))
    linhas = []
    for tipo in ordem + extras:
        itens = sorted(grupos.get(tipo, []),
                       key=lambda n: str(n.get("nome", "")))
        if not itens:
            continue
        icone = _ICONES_TIPO.get(tipo, "•")
        for item in itens:
            nome = str(item.get("nome", "?"))
            caminho = str(item.get("caminho", nome))
            marcas = ""
            if caminho == (atual or ""):
                marcas += " →"
            if caminho in sujos_txt:
                marcas += " ●"
            linhas.append(f"  {icone} {nome}{marcas}")
    return linhas


def resumo_agente(sessao) -> dict:
    """Header/status/conversa/contexto/tools/plano (só leitura)."""
    provider = getattr(sessao, "provider", None)
    return {
        "header": "ELiXX AGENT",
        "provider": getattr(provider, "nome", "MOCK") +
        " / DETERMINISTIC",
        "status": getattr(sessao, "estado", "IDLE"),
        "mensagens": len(getattr(sessao, "mensagens", [])),
        "tarefa": getattr(sessao, "tarefa", ""),
    }
