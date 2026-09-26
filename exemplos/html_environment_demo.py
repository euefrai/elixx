"""ELiXX Fase 20 — demo HTML → Environment (sem navegador).

1. carrega html-ambiente.html; 2. faz parse; 3. cria Environment;
4. mostra árvore; 5. mostra regiões; 6. mostra interações;
7. converte para World; 8. gera AIContext; 9. serializa JSON;
10. executa dry-run.

Não abre navegador, não faz request, não executa JavaScript.
"""
import json
from pathlib import Path

from elixx.visual.ambiente import (
    AIContextBuilder,
    InteractionExecutor,
    debug_ambiente,
    vincular_ambiente,
)
from elixx.visual.html_ambiente import HTMLAdapter, debug_html, parsear_html


def main() -> None:
    html = Path(__file__).with_name("html-ambiente.html").read_text(
        encoding="utf-8")

    # 1-2. parse (só dados; scripts viram aviso, nada executa)
    doc = parsear_html(html)
    print(f"parse: {doc.total_nos} nós, "
          f"{doc.scripts_ignorados} script(s) ignorado(s), "
          f"{doc.handlers_removidos} handler(s) removido(s)")

    # 3. Environment (+ geometria opcional de fonte separada)
    geometria = {
        "botao_comprar": {"x": 20, "y": 200, "largura": 120,
                          "altura": 36},
        "conteudo": {"x": 0, "y": 120, "largura": 800, "altura": 400,
                     "superficie": True, "capacidades": ["andar"]},
    }
    env, avisos = HTMLAdapter.parsear(html, geometria=geometria,
                                      env_id="loja", nome="Loja ELiXX")
    print(f"environment: {len(env)} nós; "
          f"{len(env._regioes)} regiões; "
          f"{len(env._interacoes)} interações; "
          f"{len(env._superficies)} superfícies; "
          f"{len(avisos)} aviso(s)")

    # 4-6. árvore, regiões, interações
    print("--- árvore ---")
    print(debug_html(doc).splitlines()[0])
    print("--- regiões ---")
    for rid in sorted(env._regioes):
        reg = env._regioes[rid]
        print(f"  {rid} ({reg.nome}): {len(reg.nos)} nós")
    print("--- interações (5 primeiras) ---")
    for nome in sorted(env._interacoes)[:5]:
        inter = env._interacoes[nome]
        print(f"  {inter.tipo} {nome} -> {inter.alvo}")

    # 7. World (ponte F19)
    mundo = vincular_ambiente(env)
    print(f"world: {len(mundo)} entidades; "
          f"botao_comprar={mundo.por_id('botao_comprar').tipo}")

    # 8-9. AIContext JSON-safe
    ctx = AIContextBuilder().construir(
        env, mundo, {"nome": "agente", "capacidades": ["andar"]})
    texto = json.dumps(ctx, ensure_ascii=False, sort_keys=True)
    print(f"contexto: {len(ctx['elementos'])} elementos, "
          f"{len(ctx['regioes'])} regiões, "
          f"{len(ctx['interacoes'])} interações, "
          f"{len(texto)} chars JSON")

    # 10. dry-run (planejado + validado + simulado; nada clicado)
    exe = InteractionExecutor(env)
    planejado = exe.validar("botao_comprar_clicar", "botao_comprar")
    sim = exe.simular("botao_comprar_clicar", "botao_comprar",
                      agente={"nome": "agente"})
    print(f"dry-run: valido={planejado['valido']} "
          f"simulado={sim['simulado']} sucesso={sim['sucesso']}")
    _ = debug_ambiente


if __name__ == "__main__":
    main()
