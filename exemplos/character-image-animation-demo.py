"""Experimento F41 — imagem real -> personagem animavel.

1-12. localizar, validar, carregar, personagem, transform, motion,
renderizar, respiracao, inclinacao, deslocamento, cancelar,
finalizar. Sem Studio. --visual abre janela real; --sem-janela
prova o ciclo no motor (headless).
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PASTA = "assets/personagem_teste"
ARQUIVO = f"{PASTA}/personagem.png"

from elixx.visual.asset_personagem import (  # noqa: E402
    CharacterAsset,
    animacao_deslocamento,
    animacao_inclinacao,
    animacao_respiracao,
    criar_personagem_unidade,
)


def montar_motor():
    from elixx.animacao.motor import MotorAnimacoes
    from elixx.visual.cena import Cena

    asset = CharacterAsset("Juh", PASTA, str(BASE))
    print(f"1. localizar: {PASTA}/")
    print(f"2. validar: {asset.diagnosticar()}")
    asset.usar_como("frente", "personagem.png")
    vis = asset.vista("frente")
    print(f"3. carregar: {vis.metadados()}")
    no, character, rig = criar_personagem_unidade(asset)
    print(f"4. personagem: {character.nome} "
          f"({rig.metodo})")
    print(f"5. transform: x={no.x} y={no.y} "
          f"escala={no.escala}")
    cena = Cena(janelas=[])
    from elixx.visual.cena import NoVisual

    raiz = NoVisual(tipo="janela", nome="palco",
                    largura=800.0, altura=600.0)
    raiz.adicionar(no)
    cena.janelas.append(raiz)
    motor = MotorAnimacoes()
    motor.carregar([animacao_respiracao("Juh"),
                    animacao_inclinacao("Juh"),
                    animacao_deslocamento("Juh", (no.x,
                                                  no.y))],
                   cena)
    print("6. motion: respirar+inclinar+deslocar")
    return cena, motor, no


def sem_janela() -> None:
    cena, motor, no = montar_motor()
    print("7. renderizar: cena pronta "
          f"({len(cena.janelas)} janela)")
    motor.iniciar("respirar")
    antes = no.escala
    for _ in range(12):
        motor.atualizar(100.0)
    print(f"8. respiracao: escala {antes} -> {no.escala}")
    assert no.escala != antes
    motor.iniciar("inclinar")
    for _ in range(9):
        motor.atualizar(100.0)
    print(f"9. inclinacao: rotacao={no.rotacao}")
    assert no.rotacao != 0.0
    motor.iniciar("deslocar")
    x0 = no.x
    for _ in range(8):
        motor.atualizar(100.0)
    print(f"10. deslocamento: x {x0} -> {no.x}")
    assert no.x != x0
    motor.cancelar("respirar")
    motor.cancelar("inclinar")
    motor.cancelar("deslocar")
    print("11. cancelar: execucoes paradas")
    print("12. finalizar: UMA IMAGEM = unidade animavel "
          "(sem bracos/olhos independentes)")


def visual() -> None:
    from elixx.visual.asset_personagem import abrir_palco

    cena, motor, no = montar_motor()
    print("7. renderizar: abrindo janela real")
    renderer = abrir_palco(cena, str(BASE), motor)
    for nome in ("respirar", "inclinar", "deslocar"):
        motor.iniciar(nome)
    print("8-10. respiracao+inclinacao+deslocamento: "
          "observe a janela (fecha em 8s)")
    renderer.programar(8000, renderer.fechar)
    renderer.executar_loop()
    print("11-12. finalizar: janela fechada")


if __name__ == "__main__":
    if "--visual" in sys.argv:
        visual()
    else:
        sem_janela()
