"""Eventos da ELiXX.

Eventos básicos da Fase 01:

    quando clicar { ... }
    quando passar_por_cima { ... }
    quando pressionar { ... }
    quando aparecer { ... }

Novos eventos entram em EVENTOS_SUPORTADOS com nome + descrição — sem
mexer no parser, que aceita qualquer nome e deixa a validação para a
semântica (que consulta este módulo).
"""
from __future__ import annotations

EVENTOS_SUPORTADOS: dict[str, str] = {
    "clicar": "disparado ao clicar no elemento",
    "passar_por_cima": "disparado ao passar o cursor sobre o elemento",
    "pressionar": "disparado ao pressionar tecla com o elemento focado",
    "aparecer": "disparado quando o elemento aparece na tela",
    # Fase 08: ciclo de vida e interação (mesmo dispatcher, sem paralelo).
    "criar": "disparado uma vez ao criar o elemento",
    "mostrar": "disparado quando o elemento fica visível",
    "esconder": "disparado quando o elemento é escondido",
    "mudanca": "disparado quando o valor do campo muda",
}


def validar_evento(nome: str, *, linha: int | None = None) -> None:
    """Levanta ErroExecucao/ErroSemantico se o evento não existir."""
    if nome not in EVENTOS_SUPORTADOS:
        from ..erros import ErroExecucao, sugerir

        parecidos = sugerir(nome, sorted(EVENTOS_SUPORTADOS))
        dica = f" Você quis dizer: {', '.join(parecidos)}?" if parecidos else ""
        raise ErroExecucao(
            f"Evento desconhecido: {nome!r}.{dica} "
            f"Eventos válidos: {', '.join(sorted(EVENTOS_SUPORTADOS))}.",
            linha=linha,
            exemplo="quando clicar {\n    mostrar(\"Olá!\")\n}",
        )
