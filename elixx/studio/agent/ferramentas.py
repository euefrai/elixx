"""Ferramentas do Agent (F26) — schema + permissão + execução.

Reutilizam Workspace/Documento/Preview/Editor do Studio (sem duplicar).
Leitura e validação são puras; escrita passa por ChangeSet + aprovação
fora daqui. Ferramentas de personagem operam no Character F12 via
F23/F24 (pose, expressão, gesto, comportamento, transform).
"""
from __future__ import annotations

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["FERRAMENTAS", "PERMISSAO_FERRAMENTA", "AgentTool",
           "ToolRegistry", "executar_ferramenta"]

FERRAMENTAS = ("ler_arquivo", "buscar", "listar_arquivos",
               "analisar_codigo", "obter_simbolo", "criar_arquivo",
               "editar_arquivo", "renomear_arquivo", "mover_arquivo",
               "excluir_arquivo", "validar", "compilar",
               "executar_preview", "obter_diagnosticos",
               "personagem_pose", "personagem_expressao",
               "personagem_gesto", "personagem_comportamento",
               "personagem_transform")
"""Ferramentas conhecidas (desconhecida = erro, nunca execução)."""

PERMISSAO_FERRAMENTA = {
    "ler_arquivo": "READ", "buscar": "READ",
    "listar_arquivos": "READ", "analisar_codigo": "READ",
    "obter_simbolo": "READ", "obter_diagnosticos": "READ",
    "criar_arquivo": "WRITE", "editar_arquivo": "WRITE",
    "renomear_arquivo": "RENAME", "mover_arquivo": "RENAME",
    "excluir_arquivo": "DELETE", "validar": "VALIDATE",
    "compilar": "COMPILE", "executar_preview": "PREVIEW",
    "personagem_pose": "PREVIEW", "personagem_expressao": "PREVIEW",
    "personagem_gesto": "PREVIEW",
    "personagem_comportamento": "PREVIEW",
    "personagem_transform": "PREVIEW",
}
"""Ferramenta → permissão exigida (falha fechada)."""

DESCRICOES = {
    "ler_arquivo": "Lê texto de arquivo contido no workspace.",
    "buscar": "Localiza termo nos arquivos do contexto.",
    "listar_arquivos": "Lista um nível da árvore do projeto.",
    "analisar_codigo": "Símbolos (personagens/poses) via parser.",
    "obter_simbolo": "Detalhe de um símbolo do contexto.",
    "criar_arquivo": "Propõe criação (vira AgentChange).",
    "editar_arquivo": "Propõe edição (vira AgentChange).",
    "renomear_arquivo": "Propõe renomeação (vira AgentChange).",
    "mover_arquivo": "Propõe movimento (vira AgentChange).",
    "excluir_arquivo": "Propõe exclusão (vira AgentChange).",
    "validar": "Diagnósticos do compilador oficial.",
    "compilar": "Parse + semântica (sem executar).",
    "executar_preview": "Pipeline oficial headless.",
    "obter_diagnosticos": "Diagnósticos guardados no contexto.",
    "personagem_pose": "Aplica pose F12 (requer Character).",
    "personagem_expressao": "Aplica expressão F12.",
    "personagem_gesto": "Define gesto F12/F23.",
    "personagem_comportamento": "Comportamento F24 (só definição).",
    "personagem_transform": "Ajuste de transform via pose.",
}
"""Descrição honesta de cada ferramenta (sem prometer IA)."""


class AgentTool:
    """Definição de ferramenta (schema documentado, sem callable)."""

    def __init__(self, nome: str) -> None:
        nome_txt = str(nome).strip()
        if nome_txt not in FERRAMENTAS:
            raise ErroELiXX(f'Agent: ferramenta "{nome}" '
                            "desconhecida.")
        self.nome = nome_txt
        self.descricao = DESCRICOES[nome_txt]
        self.permissao = PERMISSAO_FERRAMENTA[nome_txt]

    def esquema(self) -> dict:
        return {"nome": self.nome, "descricao": self.descricao,
                "permissao": self.permissao}

    def __repr__(self) -> str:
        return f"AgentTool({self.nome}←{self.permissao})"


class ToolRegistry:
    """Registro + despacho com checagem de permissão."""

    def __init__(self, permissoes=None) -> None:
        from .permissao import PermissionSet

        if permissoes is None:
            permissoes = PermissionSet()
        if not isinstance(permissoes, PermissionSet):
            raise ErroELiXX("Agent: registro espera PermissionSet.")
        self.permissoes = permissoes
        self.ferramentas = {nome: AgentTool(nome)
                            for nome in FERRAMENTAS}

    def listar(self) -> list[str]:
        return B.ordenado(self.ferramentas)

    def ferramenta(self, nome: str) -> AgentTool:
        try:
            return self.ferramentas[str(nome)]
        except KeyError:
            raise ErroELiXX(f'Agent: ferramenta "{nome}" '
                            "desconhecida.")

    def pode(self, nome: str) -> bool:
        ferramenta = self.ferramenta(nome)
        return self.permissoes.tem(ferramenta.permissao)


def executar_ferramenta(registro: ToolRegistry, nome: str,
                        argumentos: dict | None = None,
                        ambiente=None) -> dict:
    """Despacha com permissão exigida (falha fechada).

    `ambiente` carrega workspace/documentos/preview/personagens. Escrita
    (criar/editar/renomear/mover/excluir) NÃO toca disco: retorna
    AgentChange proposto (aplicação é do ChangeSet aprovado).

    Aceita o ambiente (com `.registro`) como primeiro argumento por
    conveniência — documentado e determinístico.
    """
    if ambiente is None and hasattr(registro, "registro"):
        ambiente = registro
        registro = ambiente.registro
    if not isinstance(registro, ToolRegistry):
        raise ErroELiXX("Agent: registro de ferramentas inválido.")
    ferramenta = registro.ferramenta(nome)
    registro.permissoes.exigir(ferramenta.permissao, nome)
    args = dict(argumentos or {})
    if not B.e_dado(args):
        raise ErroELiXX(f"Agent: argumentos de {nome} inválidos.")
    if ambiente is None:
        raise ErroELiXX(f"Agent: {nome} exige ambiente Studio.")
    return _IMPLEMENTACOES[nome](ambiente, args)


def _ws(ambiente):
    ws = getattr(ambiente, "workspace", None)
    if ws is None or not ws.aberto:
        raise ErroELiXX("Agent: workspace fechado.")
    return ws


def _texto_alvo(ambiente, args: dict) -> tuple:
    """(texto, caminho): args → contexto (atual/primeiro) → erro.

    Fallback determinístico: caminho explícito vence; depois o
    arquivo atual do contexto; depois o primeiro (ordenado). Sem
    adivinhação fora do contexto.
    """
    if args.get("texto") is not None:
        if not isinstance(args["texto"], str):
            raise ErroELiXX("Agent: texto em string.")
        return args["texto"], str(args.get("caminho", ""))
    if args.get("caminho"):
        ws = _ws(ambiente)
        alvo = ws.resolver(B.id_valido(args["caminho"],
                                       "caminho"))
        if not alvo.is_file():
            raise ErroELiXX("Agent: arquivo ausente.")
        texto = alvo.read_text(encoding="utf-8")
        return texto, args["caminho"]
    ctx = getattr(ambiente, "contexto", None)
    if ctx is not None:
        if ctx.arquivo_atual in ctx.arquivos:
            return (ctx.arquivos[ctx.arquivo_atual],
                    ctx.arquivo_atual)
        for caminho in sorted(ctx.arquivos):
            return ctx.arquivos[caminho], caminho
    raise ErroELiXX("Agent: sem texto nem caminho (informe "
                    '"texto"/"caminho" ou contexto com arquivo).')


def _ler(ambiente, args: dict) -> dict:
    ws = _ws(ambiente)
    if args.get("caminho"):
        alvo = ws.resolver(B.id_valido(args["caminho"],
                                       "caminho"))
        if not alvo.is_file():
            raise ErroELiXX("Agent: arquivo ausente.")
        texto = alvo.read_text(encoding="utf-8")
        return {"caminho": args["caminho"],
                "texto": texto[:100_000],
                "truncado": len(texto) > 100_000}
    texto, caminho = _texto_alvo(ambiente, args)
    return {"caminho": caminho, "texto": texto[:100_000],
            "truncado": len(texto) > 100_000}


def _buscar(ambiente, args: dict) -> dict:
    ws = _ws(ambiente)
    termo = B.id_valido(args.get("termo", ""), "termo")
    ctx = getattr(ambiente, "contexto", None)
    arquivos = (list(ctx.arquivos.items()) if ctx is not None
                else [])
    if not arquivos:
        base = ws.resolver(args.get("raiz", "src"))
        if base.is_dir():
            for item in sorted(base.rglob("*.elixx")):
                try:
                    arquivos.append((str(item), item.read_text(
                        encoding="utf-8")[:100_000]))
                except OSError:
                    continue
    achados = []
    for caminho, texto in arquivos:
        for i, linha in enumerate(str(texto).split("\n"),
                                  start=1):
            if termo in linha:
                achados.append({"arquivo": str(caminho),
                                "linha": i,
                                "trecho": linha.strip()[:200]})
                if len(achados) >= 200:
                    break
    return {"termo": termo, "ocorrencias": achados}


def _listar(ambiente, args: dict) -> dict:
    from ..arquivos import ArvoreArquivos

    ws = _ws(ambiente)
    return {"entradas": ArvoreArquivos(ws).listar(
        args.get("relativo", "."))}


def _analisar(ambiente, args: dict) -> dict:
    texto, _caminho = _texto_alvo(ambiente, args)
    try:
        from ...compilador.componentes import expandir_componentes
        from ...compilador.lexer import tokenizar
        from ...compilador.parser import Parser
        from ...compilador.semantica import validar
        from ...runtime.nucleo import Executor
        from ...visual.cena import ConstrutorCena
        from ...visual.personagem import vincular_personagens

        prog = Parser(tokenizar(texto)).parse()
        expandir_componentes(prog)
        validar(prog)
        cena = ConstrutorCena().de_objetos(
            Executor().executar(prog, []).objetos)
        try:
            personagens = sorted(vincular_personagens(cena))
        except ErroELiXX:
            personagens = []
        return {"valido": True, "personagens": personagens}
    except Exception as exc:
        return {"valido": False,
                "motivo": str(getattr(exc, "mensagem", exc))[:300]}


def _simbolo(ambiente, args: dict) -> dict:
    ctx = getattr(ambiente, "contexto", None)
    nome = B.id_valido(args.get("nome", ""), "símbolo")
    if ctx is not None:
        for s in ctx.simbolos:
            if s.get("nome") == nome:
                return {"simbolo": dict(s)}
    raise ErroELiXX(f'Agent: símbolo "{nome}" fora do contexto.')


def _prop_change(op: str):
    def _f(ambiente, args: dict) -> dict:
        from .mudancas import AgentChange

        caminho = B.id_valido(args.get("caminho", ""), "caminho")
        if op in ("renomear", "mover"):
            destino = B.id_valido(args.get("destino", ""),
                                  "destino")
        else:
            destino = None
        return {"mudanca": AgentChange(
            caminho, op,
            conteudo_novo=args.get("conteudo_novo"),
            destino=destino,
            descricao=args.get("descricao", ""),
            risco=args.get("risco", "baixo")).to_dict()}
    _f.__name__ = op
    return _f


def _validar(ambiente, args: dict) -> dict:
    from ..editor import diagnosticar_texto

    texto, caminho = _texto_alvo(ambiente, args)
    return {"diagnosticos": [
        d.to_dict() for d in diagnosticar_texto(texto, caminho)]}


def _compilar(ambiente, args: dict) -> dict:
    return _analisar(ambiente, args)


def _preview(ambiente, args: dict) -> dict:
    preview = getattr(ambiente, "preview", None)
    if preview is None:
        from ..preview import HeadlessPreview

        preview = HeadlessPreview()
    texto, caminho = _texto_alvo(ambiente, args)
    resultado = preview.executar(texto, caminho or "main.elixx")
    return resultado.to_dict()


def _diagnosticos(ambiente, args: dict) -> dict:
    ctx = getattr(ambiente, "contexto", None)
    if ctx is None:
        return {"diagnosticos": []}
    return {"diagnosticos": list(ctx.diagnosticos)}


def _personagem(ambiente, args: dict):
    """Character vinculado no ambiente (sem duplicar API F12)."""
    personagens = getattr(ambiente, "personagens", None) or {}
    nome = B.id_valido(args.get("personagem", ""), "personagem")
    try:
        return personagens[nome]
    except KeyError:
        raise ErroELiXX(f'Agent: personagem "{nome}" indisponível '
                        "(vincule no ambiente).")


def _pose(ambiente, args: dict) -> dict:
    perso = _personagem(ambiente, args)
    tocadas = perso.aplicar_pose(
        B.id_valido(args.get("pose", ""), "pose"))
    return {"tocadas": tocadas}


def _expressao(ambiente, args: dict) -> dict:
    perso = _personagem(ambiente, args)
    pose = perso.obter_pose(B.id_valido(args.get("expressao", ""),
                                        "expressão"))
    if not pose.expressao:
        raise ErroELiXX("Agent: não é expressão F12.")
    return {"tocadas": perso.aplicar_pose(pose)}


def _gesto(ambiente, args: dict) -> dict:
    from ...visual.rigging import definir_automatica

    rig = getattr(ambiente, "rig", None)
    if rig is None:
        raise ErroELiXX("Agent: rig indisponível no ambiente.")
    gesto = definir_automatica(
        rig, B.id_valido(args.get("gesto", ""), "gesto"))
    return {"gesto": gesto.nome,
            "passos": [p.nome for p in gesto.passos]}


def _comportamento(ambiente, args: dict) -> dict:
    from ...visual.deformacao import comportamento

    perso = _personagem(ambiente, args)
    passos = comportamento(perso, args.get("nome", ""),
                           **{k: v for k, v in args.items()
                              if k not in ("personagem", "nome")})
    for passo in passos:
        perso.aplicar_pose(passo)
    return {"passos": [p.nome for p in passos]}


def _transform(ambiente, args: dict) -> dict:
    from ...visual.personagem import Pose

    perso = _personagem(ambiente, args)
    parte = B.id_valido(args.get("parte", ""), "parte")
    props = dict(args.get("props", {}))
    permitidas = {"posicao", "rotacao", "escala", "opacidade"}
    for prop in props:
        if prop not in permitidas:
            raise ErroELiXX(f'Agent: propriedade "{prop}" inválida.')
    return {"tocadas": perso.aplicar_pose(
        Pose("ajuste_agent", entradas={parte: props}))}


_IMPLEMENTACOES = {
    "ler_arquivo": _ler, "buscar": _buscar,
    "listar_arquivos": _listar, "analisar_codigo": _analisar,
    "obter_simbolo": _simbolo,
    "criar_arquivo": _prop_change("criar"),
    "editar_arquivo": _prop_change("editar"),
    "renomear_arquivo": _prop_change("renomear"),
    "mover_arquivo": _prop_change("mover"),
    "excluir_arquivo": _prop_change("excluir"),
    "validar": _validar, "compilar": _compilar,
    "executar_preview": _preview,
    "obter_diagnosticos": _diagnosticos,
    "personagem_pose": _pose,
    "personagem_expressao": _expressao,
    "personagem_gesto": _gesto,
    "personagem_comportamento": _comportamento,
    "personagem_transform": _transform,
}
