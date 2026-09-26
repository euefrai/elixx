"""ELiXX Fase 19 — demo visual Tk (estrutura externa vira espaço).

Desenha regiões (menu/conteúdo), painel (superfície), agente e caminho
até o destino usando apenas Tk + stdlib. Sem controlar apps reais.
Uso: python exemplos/environment_tk.py
"""
import sys

sys.path.insert(0, ".")

from elixx.visual.ambiente import (
    Environment,
    EnvironmentNode,
    EnvironmentRegion,
    construir_grafo_de_ambiente,
    gerar_surface,
    vincular_ambiente,
)
from elixx.visual.navegacao import rota


def construir() -> Environment:
    env = Environment("env_tk", nome="Demo Tk", tipo="desktop",
                      largura=800.0, altura=600.0)
    for nid, nome, tipo, x, y, larg, alt in [
            ("janela", "Janela", "janela", 0, 0, 800, 600),
            ("menu", "Menu", "menu", 0, 40, 150, 560),
            ("conteudo", "Conteúdo", "regiao", 150, 40, 650, 560),
            ("painel", "Painel", "painel", 170, 60, 300, 150),
            ("botao_ok", "Botão", "botao", 180, 70, 100, 30)]:
        env.adicionar_no(EnvironmentNode(
            nid, nome=nome, tipo=tipo, x=x, y=y, largura=larg,
            altura=alt,
            interativo=(tipo == "botao"),
            atributos={"superficie": True} if nid == "painel" else {}))
    env.obter_no("janela").adicionar_filho(env.obter_no("menu"))
    env.obter_no("janela").adicionar_filho(env.obter_no("conteudo"))
    env.obter_no("conteudo").adicionar_filho(env.obter_no("painel"))
    env.obter_no("painel").adicionar_filho(env.obter_no("botao_ok"))
    env.adicionar_regiao(EnvironmentRegion("reg_menu", nome="menu",
                                           nos=["menu"]))
    env.adicionar_regiao(EnvironmentRegion(
        "reg_conteudo", nome="conteúdo",
        nos=["conteudo", "painel", "botao_ok"]))
    env.adicionar_superficie(gerar_surface(env.obter_no("painel")))
    return env


def main() -> None:
    import tkinter as tk

    env = construir()
    mundo = vincular_ambiente(env)
    grafo = construir_grafo_de_ambiente(
        mundo, ligacoes=[{"origem": "menu", "destino": "conteudo",
                           "modo": "andar"},
                         {"origem": "conteudo", "destino": "painel",
                           "modo": "andar"},
                         {"origem": "painel", "destino": "botao_ok",
                           "modo": "andar"}])
    resultado = rota(grafo, "menu", "botao_ok")
    print("rota:", resultado["nos"])

    raiz = tk.Tk()
    raiz.title("ELiXX F19 — Environment → World")
    tela = tk.Canvas(raiz, width=800, height=600, bg="#10131c")
    tela.pack()
    cores = {"menu": "#1d2b45", "conteudo": "#14251c",
             "painel": "#2b4a35", "botao_ok": "#c98a2b"}
    for nid, cor in cores.items():
        no = env.obter_no(nid)
        tela.create_rectangle(no.x, no.y, no.right, no.bottom,
                              fill=cor, outline="#5b6b8c")
        tela.create_text(no.x + 6, no.y + 10, text=no.nome,
                         anchor="w", fill="white",
                         font=("Arial", 10))
    # agente + destino + caminho (centros das entidades do World)
    pontos = []
    for no_id in resultado["nos"]:
        nome = no_id.replace("ent:", "")
        centro = mundo.por_id(nome).centro()
        pontos.extend([centro.x, centro.y])
    if pontos:
        tela.create_line(*pontos, fill="#7dd3fc", width=3)
        tela.create_oval(pontos[0] - 7, pontos[1] - 7, pontos[0] + 7,
                         pontos[1] + 7, fill="#7dd3fc",
                         outline="white")
        tela.create_oval(pontos[-2] - 7, pontos[-1] - 7, pontos[-2] + 7,
                         pontos[-1] + 7, fill="#c98a2b",
                         outline="white")
    tela.create_text(400, 585, text="menu → conteúdo → painel → botão",
                     fill="#9fb3d1", font=("Arial", 11))
    raiz.mainloop()


if __name__ == "__main__":
    main()
