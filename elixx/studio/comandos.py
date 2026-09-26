"""Comandos do Studio (F25) — operações estruturadas ordenadas.

O futuro Agent emitirá StudioCommand/AgentCommand em vez de clicar na
UI. Stubs AgentProposal/AgentChange/AgentContext preparam esse futuro
(sem agente, sem LLM nesta fase).
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["StudioCommand", "FilaComandos", "AgentCommand",
           "AgentProposal", "AgentChange", "AgentContext"]

COMANDOS = ("abrir_projeto", "salvar", "executar", "parar",
            "abrir_arquivo", "criar_arquivo", "selecionar",
            "alterar_propriedade")
"""Comandos conhecidos (novo comando = dado, nunca código)."""


def _parametros_ok(params: dict) -> bool:
    """JSON raso e finito (sem código, sem objetos)."""

    def _ok(valor, prof: int = 0) -> bool:
        import math

        if prof > 6:
            return False
        if valor is None or isinstance(valor, (bool, int, float)):
            return not (isinstance(valor, float)
                        and not math.isfinite(valor))
        if isinstance(valor, str):
            return True
        if isinstance(valor, list):
            return all(_ok(v, prof + 1) for v in valor)
        if isinstance(valor, dict):
            return all(isinstance(k, str) and _ok(v, prof + 1)
                       for k, v in valor.items())
        return False

    return _ok(params)


class StudioCommand:
    """Comando nomeado + alvo + parâmetros JSON (sem callable)."""

    def __init__(self, nome: str, alvo: str = "",
                 parametros: dict | None = None) -> None:
        cmd = str(nome).strip()
        if not cmd:
            raise ErroELiXX("Comando precisa de nome.")
        self.nome = cmd
        self.alvo = str(alvo)
        params = dict(parametros or {})
        if not _parametros_ok(params):
            raise ErroELiXX(f'Comando "{cmd}": parâmetros inválidos '
                            "(só JSON finito).")
        self.parametros = params
        self.origem = "studio"

    def to_dict(self) -> dict:
        return {"nome": self.nome, "alvo": self.alvo,
                "parametros": dict(self.parametros),
                "origem": self.origem}

    def __repr__(self) -> str:
        return f"StudioCommand({self.nome} {self.alvo})"


class FilaComandos:
    """Fila ordenada e determinística (sem threads)."""

    def __init__(self) -> None:
        self._fila: list[StudioCommand] = []
        self.executados: list[str] = []

    def enfileirar(self, comando: StudioCommand) -> int:
        if not isinstance(comando, StudioCommand):
            raise ErroELiXX("Fila espera StudioCommand.")
        self._fila.append(comando)
        return len(self._fila)

    def pendentes(self) -> list[str]:
        return [c.nome for c in self._fila]

    def executar_proximo(self, app) -> dict:
        """Executa o próximo via StudioApp (ordem de chegada)."""
        if not self._fila:
            raise ErroELiXX("Fila vazia.")
        comando = self._fila.pop(0)
        resultado = app.executar_comando(comando)
        self.executados.append(comando.nome)
        return resultado

    def limpar(self) -> None:
        self._fila.clear()

    def __repr__(self) -> str:
        return f"FilaComandos({len(self._fila)} pendentes)"


class AgentCommand(StudioCommand):
    """Comando futuro do Agent (mesmo contrato, origem marcada)."""

    def __init__(self, nome: str, alvo: str = "",
                 parametros: dict | None = None) -> None:
        super().__init__(nome, alvo, parametros)
        self.origem = "agent"


class AgentProposal:
    """Proposta futura: descrição + mudanças + arquivos + preview."""

    def __init__(self, descricao: str, alteracoes: list | None = None,
                 arquivos: list | None = None,
                 preview: bool = True) -> None:
        if not str(descricao).strip():
            raise ErroELiXX("Proposta precisa de descrição.")
        self.descricao = str(descricao)
        self.alteracoes = [dict(a) for a in (alteracoes or [])]
        self.arquivos = [str(a) for a in (arquivos or [])]
        self.preview = bool(preview)

    def to_dict(self) -> dict:
        return {"descricao": self.descricao,
                "alteracoes": list(self.alteracoes),
                "arquivos": list(self.arquivos),
                "preview": self.preview}

    def __repr__(self) -> str:
        return f"AgentProposal({self.descricao[:40]})"


class AgentChange:
    """Mudança estruturada proposta (arquivo + operação + dados)."""

    def __init__(self, arquivo: str, operacao: str,
                 dados: dict | None = None) -> None:
        if not str(arquivo).strip():
            raise ErroELiXX("Mudança precisa de arquivo.")
        op = str(operacao).strip()
        if op not in ("criar", "editar", "renomear", "excluir"):
            raise ErroELiXX(f'Operação "{op}" inválida.')
        self.arquivo = str(arquivo)
        self.operacao = op
        self.dados = dict(dados or {})

    def to_dict(self) -> dict:
        return {"arquivo": self.arquivo, "operacao": self.operacao,
                "dados": dict(self.dados)}


class AgentContext:
    """Contexto futuro: projeto + seleção + diagnósticos (só dados)."""

    def __init__(self, projeto: str = "",
                 selecao: dict | None = None,
                 diagnosticos: list | None = None) -> None:
        self.projeto = str(projeto)
        self.selecao = dict(selecao or {})
        self.diagnosticos = list(diagnosticos or [])

    def to_dict(self) -> dict:
        return {"projeto": self.projeto,
                "selecao": dict(self.selecao),
                "diagnosticos": list(self.diagnosticos)}
