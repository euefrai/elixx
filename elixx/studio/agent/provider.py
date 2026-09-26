"""Providers do Agent (F26) — padrão F18, domínio dev/projeto.

Null: nada gera. Mock: intenções/planos determinísticos (testes).
Structured: entrada estruturada → AgentIntent/AgentPlan. Sem HTTP,
sem OpenAI/Gemini/Ollama, sem modelo local (futuro explícito).
"""
from __future__ import annotations

from ...erros import ErroELiXX
from . import _base as B

__all__ = ["AgentProvider", "NullAgentProvider",
           "MockAgentProvider", "StructuredAgentProvider"]


class AgentProvider:
    """Contrato: nome + disponibilidade + geração (sem efeitos)."""

    def __init__(self, nome: str) -> None:
        self.nome = B.id_valido(nome, "nome do provider")

    def disponivel(self) -> bool:
        return False

    def gerar_intencao(self, contexto, pedido: str = ""):
        raise ErroELiXX(f'Agent: provider "{self.nome}" não gera '
                        "intenção.")

    def gerar_plano(self, intencao, contexto=None):
        raise ErroELiXX(f'Agent: provider "{self.nome}" não gera '
                        "plano.")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.nome})"


class NullAgentProvider(AgentProvider):
    """Nulo: disponível, mas nunca gera (pipeline vazio válido)."""

    def __init__(self, nome: str = "nulo") -> None:
        super().__init__(nome)

    def disponivel(self) -> bool:
        return True


class MockAgentProvider(AgentProvider):
    """Mock determinístico: pedido → intenção/plano tabelados."""

    def __init__(self, nome: str = "mock", roteiro: dict | None = None
                 ) -> None:
        super().__init__(nome)
        self.roteiro = dict(roteiro or {})

    def disponivel(self) -> bool:
        return True

    def gerar_intencao(self, contexto, pedido: str = ""):
        from .intencao import AgentIntent

        chave = str(pedido).strip() or "padrao"
        if chave in self.roteiro:
            return AgentIntent.from_dict(
                self.roteiro[chave].get("intencao", {}))
        texto = chave.lower()
        if "animacao" in texto or "respirar" in texto:
            tipo = "criar_animacao"
        elif "cena" in texto:
            tipo = "criar_cena"
        elif "personagem" in texto or "juh" in texto:
            tipo = "modificar_personagem"
        elif "erro" in texto or "corrig" in texto:
            tipo = "corrigir_erro"
        elif "preview" in texto or "execut" in texto:
            tipo = "executar_preview"
        else:
            tipo = "modificar_interface"
        return AgentIntent(tipo, objetivo=chave, origem="mock")

    def gerar_plano(self, intencao, contexto=None):
        from .plano import AgentPlan, PlanStep

        mapa = {
            "executar_preview": [("validar", "validar", {})],
            "diagnosticar": [("diagnosticar", "validar", {})],
            "modificar_personagem": [
                (" Ler".strip(), "ler_arquivo", {}),
                ("pose", "personagem_pose", {}),
                ("validar", "validar", {}),
                ("preview", "executar_preview", {})],
        }
        passos_txt = mapa.get(intencao.tipo, [
            ("ler", "ler_arquivo", {}),
            ("validar", "validar", {}),
            ("preview", "executar_preview", {})])
        return AgentPlan(intencao, [
            PlanStep(f"passo_{i + 1}", desc, ferramenta=fer,
                     argumentos=args, risco="baixo")
            for i, (desc, fer, args) in enumerate(passos_txt)])


class StructuredAgentProvider(AgentProvider):
    """Estruturado: dict → AgentIntent/AgentPlan (sem adivinhar)."""

    def __init__(self, nome: str = "estruturado") -> None:
        super().__init__(nome)

    def disponivel(self) -> bool:
        return True

    def gerar_intencao(self, contexto, pedido=""):
        from .intencao import AgentIntent

        if not isinstance(pedido, dict):
            raise ErroELiXX("Agent: Structured espera dict com "
                            '"intencao".')
        bruto = pedido.get("intencao")
        if not isinstance(bruto, dict):
            raise ErroELiXX('Agent: Structured exige "intencao" '
                            "dict.")
        return AgentIntent.from_dict(bruto)

    def gerar_plano(self, intencao, contexto=None):
        from .plano import AgentPlan, PlanStep

        bruto = getattr(intencao, "parametros", {}).get("passos")
        if not isinstance(bruto, list):
            raise ErroELiXX("Agent: Structured exige "
                            '"parametros.passos" lista.')
        return AgentPlan(intencao, [PlanStep.from_dict(p)
                                    for p in bruto])
