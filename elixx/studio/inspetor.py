"""Inspetor do Studio (F25) — seleção → propriedades reais.

Inspetor lê Transform/Character/pose via APIs oficiais (nunca mostra
propriedade inexistente). Selecao simples (por id; sem pixel-perfect).
fluxo_personagem integra F23/F24: imagem → analyzer → rig → deformation
→ Character (Mock/Structured nos testes; sem IA real).
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = ["Selecao", "Inspetor", "InspecaoPersonagem",
           "fluxo_personagem"]


class Selecao:
    """Elemento selecionado (tipo + id + origem opcional)."""

    def __init__(self, tipo: str, ref_id: str,
                 origem: str = "preview") -> None:
        tipo_txt = str(tipo).strip()
        if tipo_txt not in ("no", "personagem", "parte", "asset",
                            "arquivo", "nenhum"):
            raise ErroELiXX(f'Seleção: tipo "{tipo}" inválido.')
        if not isinstance(ref_id, str):
            raise ErroELiXX("Seleção precisa de id em texto.")
        self.tipo = tipo_txt
        self.ref_id = ref_id
        self.origem = str(origem)

    def vazia(self) -> bool:
        return self.tipo == "nenhum"

    @staticmethod
    def vazia_sel() -> Selecao:
        return Selecao("nenhum", "")

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "ref_id": self.ref_id,
                "origem": self.origem}

    def __repr__(self) -> str:
        return f"Selecao({self.tipo} {self.ref_id})"


class Inspetor:
    """Propriedades da seleção (somente o que existe de verdade)."""

    def __init__(self) -> None:
        self.selecao = Selecao.vazia_sel()

    def selecionar(self, selecao: Selecao) -> Selecao:
        if not isinstance(selecao, Selecao):
            raise ErroELiXX("selecionar espera Selecao.")
        self.selecao = selecao
        return selecao

    def limpar(self) -> None:
        self.selecao = Selecao.vazia_sel()

    def inspecionar_no(self, no) -> dict:
        """NoVisual/cena: transform + identidade (reusa F10)."""
        props: dict = {"tipo": getattr(no, "tipo", "?"),
                       "nome": getattr(no, "nome", "")}
        for campo in ("x", "y", "rotacao", "escala_x", "escala_y",
                      "opacidade", "pivo_x", "pivo_y",
                      "pivo_unidade_x", "pivo_unidade_y",
                      "camada", "visivel"):
            if hasattr(no, campo):
                props[campo] = getattr(no, campo)
        pai = getattr(no, "pai", None)
        props["pai"] = getattr(pai, "nome", None) if pai else None
        props["filhos"] = [getattr(f, "nome", "?") for f in
                           getattr(no, "filhos", [])]
        return props

    def inspecionar_personagem(self, personagem) -> dict:
        """Character F12: pose/expressão/view/partes (via API)."""
        return {"nome": personagem.nome,
                "pose_atual": personagem.pose_atual,
                "direcao": personagem.direcao,
                "gesto_atual": personagem.gesto_atual,
                "partes": sorted(personagem.partes),
                "poses": sorted(personagem.poses)}

    def __repr__(self) -> str:
        return f"Inspetor({self.selecao})"


class InspecaoPersonagem:
    """Workflow do personagem selecionado (F23/F24 via APIs)."""

    def __init__(self, personagem, deformation_rig=None) -> None:
        from ..visual.personagem import Character

        if not isinstance(personagem, Character):
            raise ErroELiXX("InspecaoPersonagem espera Character.")
        self.personagem = personagem
        self.deformation_rig = deformation_rig

    def resumo(self) -> dict:
        p = self.personagem
        return {"nome": p.nome, "pose_atual": p.pose_atual,
                "direcao": p.direcao,
                "partes": sorted(p.partes),
                "poses": sorted(p.poses)}

    def trocar_pose(self, nome: str) -> list[str]:
        return self.personagem.aplicar_pose(nome)

    def trocar_expressao(self, nome: str) -> list[str]:
        pose = self.personagem.obter_pose(nome)
        if not pose.expressao:
            raise ErroELiXX(f'"{nome}" não é expressão '
                            "(pose comum, não expressiva).")
        return self.personagem.aplicar_pose(nome)

    def alterar_transform(self, parte: str, **props) -> list[str]:
        from ..visual.personagem import Pose

        permitidas = {"posicao", "rotacao", "escala", "opacidade",
                      "pivo"}
        for prop in props:
            if prop not in permitidas:
                raise ErroELiXX(f'Propriedade "{prop}" inválida '
                                "(posicao, rotacao, escala, "
                                "opacidade, pivo).")
        return self.personagem.aplicar_pose(
            Pose("ajuste_inspetor", entradas={parte: dict(props)}))

    def trocar_view(self, vista: str) -> str:
        return self.personagem.definir_direcao(vista)

    def executar_comportamento(self, nome: str, **kwargs) -> list:
        from ..visual.deformacao import comportamento

        passos = comportamento(self.personagem, nome, **kwargs)
        for passo in passos:
            self.personagem.aplicar_pose(passo)
        return passos

    def __repr__(self) -> str:
        return f"InspecaoPersonagem({self.personagem.nome})"


def fluxo_personagem(nome: str, deteccoes: list,
                     analyzer: str = "mock"):
    """Imagem/dados → analyzer → rig → deformation → Character.

    Retorna (rig, personagem, deformation_rig). Sem IA real: mock ou
    structured (dict {parts: [...]}) nesta fase.
    """
    from ..visual.deformacao import deformation_rig_de_rig
    from ..visual.rigging import (
        MockCharacterAnalyzer,
        StructuredCharacterAnalyzer,
        construir_rig,
        rig_para_personagem,
    )

    if analyzer == "mock":
        prov = MockCharacterAnalyzer(deteccoes)
        analise = prov.analisar()
    elif analyzer == "structured":
        if isinstance(deteccoes, dict):
            dados = deteccoes
        else:
            dados = {"parts": list(deteccoes)}
        analise = StructuredCharacterAnalyzer().analisar(dados)
    else:
        raise ErroELiXX(f'Analyzer "{analyzer}" inválido '
                        "(mock, structured).")
    rig = construir_rig(analise, rig_id=nome.lower())
    personagem = rig_para_personagem(rig, nome)
    return rig, personagem, deformation_rig_de_rig(rig, personagem)
