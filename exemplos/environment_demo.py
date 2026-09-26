"""ELiXX Fase 19 — exemplo programático (sem LLM, sem visão).

Constrói o Environment da especificação (Janela/Barra/Menu/Conteúdo/
Painel/Botão) e percorre a cadeia completa:

    Environment → World → Navigation → AI Context → AIIntent → plano
"""
from elixx.visual.ai_bridge import AIIntent, AIPlannerBridge, AIProvider
from elixx.visual.ambiente import (
    AIContextBuilder,
    Environment,
    EnvironmentNode,
    EnvironmentRegion,
    construir_grafo_de_ambiente,
    gerar_boundaries,
    gerar_surface,
    inferir_interacoes,
    vincular_ambiente,
)
from elixx.visual.navegacao import rota


def construir() -> Environment:
    env = Environment("env_demo", nome="Demo", tipo="web",
                      largura=800.0, altura=600.0)
    nos = [
        ("janela", "Janela", "janela", 0, 0, 800, 600, {}),
        ("barra", "Barra superior", "barra", 0, 0, 800, 40, {}),
        ("menu", "Menu lateral", "menu", 0, 40, 150, 560, {}),
        ("inicio", "Início", "botao", 10, 50, 130, 30, {}),
        ("config", "Configurações", "botao", 10, 90, 130, 30, {}),
        ("perfil", "Perfil", "botao", 10, 130, 130, 30, {}),
        ("conteudo", "Conteúdo", "regiao", 150, 40, 650, 560, {}),
        ("painel", "Painel", "painel", 170, 60, 300, 150,
         {"superficie": True, "capacidades": ["andar"]}),
        ("botao_ok", "Botão", "botao", 180, 70, 100, 30, {}),
    ]
    for nid, nome, tipo, x, y, larg, alt, attrs in nos:
        env.adicionar_no(EnvironmentNode(
            nid, nome=nome, tipo=tipo, x=x, y=y, largura=larg,
            altura=alt,
            interativo=(tipo == "botao"), atributos=dict(attrs)))
    for pai, filhos in (("janela", ("barra", "menu", "conteudo")),
                        ("menu", ("inicio", "config", "perfil")),
                        ("conteudo", ("painel",)),
                        ("painel", ("botao_ok",))):
        for filho in filhos:
            env.obter_no(pai).adicionar_filho(env.obter_no(filho))
    env.adicionar_regiao(EnvironmentRegion(
        "reg_menu", nome="menu",
        nos=["menu", "inicio", "config", "perfil"]))
    env.adicionar_regiao(EnvironmentRegion(
        "reg_conteudo", nome="conteúdo",
        nos=["conteudo", "painel", "botao_ok"]))
    env.adicionar_superficie(gerar_surface(env.obter_no("painel")))
    for limite in gerar_boundaries(env.obter_no("painel")):
        env.adicionar_limite(limite)
    for alvo in ("inicio", "config", "perfil", "botao_ok"):
        for inter in inferir_interacoes(env.obter_no(alvo)):
            env.adicionar_interacao(inter)
    print(env.validar()["motivo"])
    return env


class ProvedorDemo(AIProvider):
    """Fronteira externa: contexto → intenção (aqui: regra fixa)."""

    def gerar_intencao(self, contexto: dict) -> AIIntent:
        agente = contexto.get("agente", "agente")
        return AIIntent.from_dict({"tipo": "mover", "personagem": agente,
                                   "destino": "botao_ok",
                                   "modo": "andar"})


def main() -> None:
    env = construir()
    mundo = vincular_ambiente(env)
    grafo = construir_grafo_de_ambiente(
        mundo, ligacoes=[{"origem": "menu", "destino": "conteudo",
                           "modo": "andar"},
                         {"origem": "conteudo", "destino": "painel",
                           "modo": "andar"},
                         {"origem": "painel", "destino": "botao_ok",
                           "modo": "andar"}],
        nome="RotasEnv")
    print(f"World: {len(mundo)} entidades; "
          f"grafo: {len(grafo.nos)} nós, {len(grafo.edges)} edges")
    print(rota(grafo, "menu", "botao_ok")["nos"])
    ctx = AIContextBuilder().construir(
        env, mundo, {"nome": "agente", "x": 75.0, "y": 65.0,
                     "capacidades": ["andar"]})
    intent = ProvedorDemo("demo").gerar_intencao(ctx)
    print(f"intenção: {intent.to_dict()}")
    print(f"destinos: {len(ctx['destinos_possiveis'])}; "
          f"relações: {len(ctx['relacoes'])}")


if __name__ == "__main__":
    main()
