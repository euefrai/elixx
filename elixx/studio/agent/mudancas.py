"""ChangeSet (F26) — alterações propostas antes da aplicação.

Operações: criar/editar/excluir/renomear/mover arquivo (+ edição
estruturada futura via `estruturada`). Ciclo: validar → revisar →
aprovar/rejeitar → aplicar → desfazer. Sem aprovação (modo manual),
nada é aplicado. Caminhos sempre relativos e contidos (validados na
aplicação contra o Workspace).
"""
from __future__ import annotations

import json

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["OPERACOES", "RISCOS_MUDANCA", "MAX_MUDANCAS",
           "AgentChange", "ChangeSet"]

OPERACOES = ("criar", "editar", "excluir", "renomear", "mover",
             "estruturada")
"""Operações suportadas (desconhecida = erro, nunca execução)."""

RISCOS_MUDANCA = ("baixo", "medio", "alto")
"""Risco declarado por mudança."""

MAX_MUDANCAS = 1000
"""Teto de mudanças por ChangeSet."""

MAX_BYTES_CONTEUDO = 500_000
"""Teto de conteúdo novo por mudança (sem payloads enormes)."""


def _caminho_seguro(caminho: str, o_que: str = "caminho") -> str:
    texto = B.id_valido(caminho, o_que).replace("\\", "/")
    if texto.startswith("/") or ".." in texto.split("/"):
        raise ErroELiXX(f'Agent: "{o_que}" fora do projeto '
                        "(absoluto ou com ..).")
    return texto


class AgentChange:
    """Uma mudança: caminho + operação + antes/depois (só dados)."""

    def __init__(self, caminho: str, operacao: str,
                 conteudo_anterior: str | None = None,
                 conteudo_novo: str | None = None,
                 destino: str | None = None,
                 descricao: str = "",
                 origem: str = "agent",
                 risco: str = "baixo") -> None:
        self.caminho = _caminho_seguro(caminho)
        op = str(operacao).strip()
        if op not in OPERACOES:
            raise ErroELiXX(f'Agent: operação "{operacao}" inválida '
                            f'({", ".join(OPERACOES)}).')
        self.operacao = op
        for rotulo, valor in (("anterior", conteudo_anterior),
                              ("novo", conteudo_novo)):
            if valor is not None:
                if not isinstance(valor, str):
                    raise ErroELiXX(f"Agent: conteúdo {rotulo} em "
                                    "texto.")
                if len(valor) > MAX_BYTES_CONTEUDO:
                    raise ErroELiXX(f"Agent: conteúdo {rotulo} além "
                                    f"de {MAX_BYTES_CONTEUDO} chars.")
        self.conteudo_anterior = conteudo_anterior
        self.conteudo_novo = conteudo_novo
        self.destino = (_caminho_seguro(destino, "destino")
                        if destino is not None else None)
        if op in ("renomear", "mover") and self.destino is None:
            raise ErroELiXX(f'Agent: "{op}" exige destino.')
        self.descricao = str(descricao)
        self.origem = str(origem).strip() or "agent"
        risco_txt = str(risco).strip() or "baixo"
        if risco_txt not in RISCOS_MUDANCA:
            raise ErroELiXX(f'Agent: risco "{risco}" inválido.')
        self.risco = risco_txt

    def to_dict(self) -> dict:
        return {"caminho": self.caminho, "operacao": self.operacao,
                "conteudo_anterior": self.conteudo_anterior,
                "conteudo_novo": self.conteudo_novo,
                "destino": self.destino,
                "descricao": self.descricao, "origem": self.origem,
                "risco": self.risco}

    @staticmethod
    def from_dict(dados: dict) -> AgentChange:
        if not isinstance(dados, dict):
            raise ErroELiXX("Agent: mudança precisa de dicionário.")
        return AgentChange(
            dados.get("caminho", ""),
            dados.get("operacao", ""),
            conteudo_anterior=dados.get("conteudo_anterior"),
            conteudo_novo=dados.get("conteudo_novo"),
            destino=dados.get("destino"),
            descricao=dados.get("descricao", ""),
            origem=dados.get("origem", "agent"),
            risco=dados.get("risco", "baixo"))

    def __repr__(self) -> str:
        return f"AgentChange({self.operacao} {self.caminho})"


class ChangeSet:
    """Conjunto revisável: validar → aprovar → aplicar → desfazer."""

    def __init__(self, mudancas: list | None = None,
                 estado: str = "proposto") -> None:
        self.mudancas: list[AgentChange] = []
        for m in (mudancas or []):
            self.adicionar(m if isinstance(m, AgentChange)
                           else AgentChange.from_dict(m))
        if estado not in ("proposto", "aprovado", "rejeitado",
                          "aplicado", "desfeito"):
            raise ErroELiXX(f'Agent: estado "{estado}" inválido.')
        self.estado = estado
        self._aplicadas: list[dict] = []  # trilha para desfazer

    def adicionar(self, mudanca: AgentChange) -> AgentChange:
        if not isinstance(mudanca, AgentChange):
            raise ErroELiXX("Agent: ChangeSet espera AgentChange.")
        if len(self.mudancas) >= MAX_MUDANCAS:
            raise ErroELiXX(f"Agent: ChangeSet além de {MAX_MUDANCAS} "
                            "mudanças.")
        vistos = {(m.caminho, m.operacao) for m in self.mudancas}
        if (mudanca.caminho, mudanca.operacao) in vistos:
            raise ErroELiXX(f'Agent: mudança duplicada '
                            f'({mudanca.operacao} '
                            f'{mudanca.caminho}).')
        self.mudancas.append(mudanca)
        return mudanca

    def validar(self) -> dict:
        """Checa coerência interna (sem tocar no disco)."""
        if not self.mudancas:
            return {"valido": False, "codigo": "vazio",
                    "motivo": "ChangeSet sem mudanças."}
        return {"valido": True, "codigo": "ok",
                "motivo": f"{len(self.mudancas)} mudança(s) "
                          "coerentes."}

    def revisar(self) -> list[dict]:
        """Visão legível para aprovação (sem aplicar)."""
        return [{"caminho": m.caminho, "operacao": m.operacao,
                 "descricao": m.descricao, "risco": m.risco,
                 "previa": ((m.conteudo_novo or "")[:200]
                            if m.conteudo_novo else "")}
                for m in self.mudancas]

    def aprovar(self) -> ChangeSet:
        if self.estado != "proposto":
            raise ErroELiXX("Agent: só ChangeSet proposto aprova "
                            f"(atual: {self.estado}).")
        self.estado = "aprovado"
        return self

    def rejeitar(self) -> ChangeSet:
        if self.estado != "proposto":
            raise ErroELiXX("Agent: só ChangeSet proposto rejeita.")
        self.estado = "rejeitado"
        return self

    def aplicar(self, workspace) -> dict:
        """Aplica via Workspace contido (exige estado aprovado)."""
        from ..workspace import Workspace

        if self.estado != "aprovado":
            raise ErroELiXX("Agent: aplicar exige ChangeSet aprovado "
                            "(aprovação falsa recusada).")
        if not isinstance(workspace, Workspace):
            raise ErroELiXX("Agent: aplicar espera Workspace.")
        aplicadas = []
        try:
            for mudanca in self.mudancas:
                aplicadas.append(self._aplicar_uma(workspace,
                                                   mudanca))
        except ErroELiXX:
            # Falha fechada: reverte o que aplicou (rollback parcial
            # honesto) e mantém estado aprovado para inspeção.
            for trilha in reversed(aplicadas):
                self._reverter_uma(workspace, trilha)
            raise
        self._aplicadas = aplicadas
        self.estado = "aplicado"
        return {"aplicadas": len(aplicadas),
                "arquivos": sorted({a["caminho"] for a in
                                    aplicadas})}

    def _aplicar_uma(self, workspace, mudanca: AgentChange) -> dict:
        alvo = workspace.resolver(mudanca.caminho)
        if mudanca.operacao == "criar":
            if alvo.exists():
                raise ErroELiXX(f'Agent: "{mudanca.caminho}" já '
                                "existe.")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(mudanca.conteudo_novo or "",
                            encoding="utf-8")
            return {"caminho": mudanca.caminho, "operacao": "criar",
                    "desfazer": "excluir"}
        if mudanca.operacao == "editar":
            if not alvo.is_file():
                raise ErroELiXX(f'Agent: "{mudanca.caminho}" '
                                "ausente.")
            anterior = alvo.read_text(encoding="utf-8")
            alvo.write_text(mudanca.conteudo_novo or "",
                            encoding="utf-8")
            return {"caminho": mudanca.caminho, "operacao": "editar",
                    "anterior": anterior, "desfazer": "restaurar"}
        if mudanca.operacao == "excluir":
            if not alvo.exists():
                raise ErroELiXX(f'Agent: "{mudanca.caminho}" '
                                "ausente.")
            if alvo.is_dir():
                raise ErroELiXX(f'Agent: "{mudanca.caminho}" é pasta '
                                "(só arquivos).")
            anterior = alvo.read_text(encoding="utf-8")
            alvo.unlink()
            return {"caminho": mudanca.caminho, "operacao": "excluir",
                    "anterior": anterior, "desfazer": "recriar"}
        # renomear / mover / estruturada
        destino = workspace.resolver(mudanca.destino or "")
        if not alvo.exists():
            raise ErroELiXX(f'Agent: "{mudanca.caminho}" ausente.')
        if destino.exists():
            raise ErroELiXX(f'Agent: destino "{mudanca.destino}" '
                            "existe.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        alvo.rename(destino)
        return {"caminho": mudanca.caminho,
                "operacao": mudanca.operacao,
                "destino": mudanca.destino, "desfazer": "voltar"}

    def _reverter_uma(self, workspace, trilha: dict) -> None:
        alvo = workspace.resolver(trilha["caminho"])
        acao = trilha.get("desfazer")
        if acao == "excluir" and alvo.exists():
            alvo.unlink()
        elif acao in ("restaurar", "recriar"):
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(trilha.get("anterior", ""),
                            encoding="utf-8")
        elif acao == "voltar":
            destino = workspace.resolver(trilha.get("destino", ""))
            if destino.exists():
                destino.rename(alvo)

    def desfazer(self, workspace) -> dict:
        """Desfaz aplicação (restaura conteúdos anteriores)."""
        from ..workspace import Workspace

        if self.estado != "aplicado":
            raise ErroELiXX("Agent: só ChangeSet aplicado desfaz "
                            f"(atual: {self.estado}).")
        if not isinstance(workspace, Workspace):
            raise ErroELiXX("Agent: desfazer espera Workspace.")
        for trilha in reversed(self._aplicadas):
            self._reverter_uma(workspace, trilha)
        total = len(self._aplicadas)
        self._aplicadas = []
        self.estado = "desfeito"
        return {"desfeitas": total}

    def to_dict(self) -> dict:
        return {"mudancas": [m.to_dict() for m in self.mudancas],
                "estado": self.estado}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False,
                          sort_keys=True)

    def __repr__(self) -> str:
        return (f"ChangeSet({len(self.mudancas)} mudanças, "
                f"{self.estado})")
