"""ELiXX Fase 23 — demo Automatic Character Rigging (sem IA, sem rede).

Usa MockCharacterAnalyzer para construir a personagem "Juh" e mostra:
análise, partes, hierarquia, pivôs, rig, conversão para F12, pose,
expressão e uma pequena animação via Motion Core (definições; sem
display — Tk só se houver tela, e nunca nos testes).
"""
from elixx.visual.rigging import (
    RigExpression,
    RigPose,
    RigView,
    MockCharacterAnalyzer,
    construir_rig,
    debug_rigging,
    definir_automatica,
    rig_para_personagem,
)


def main() -> None:
    deteccoes = [
        {"id": "tronco", "tipo": "tronco",
         "bounds": {"x": 0, "y": 100, "largura": 80, "altura": 120},
         "confianca": 0.98},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco",
         "bounds": {"x": 10, "y": 0, "largura": 60, "altura": 70},
         "confianca": 0.97},
        {"id": "olho_esquerdo", "tipo": "olho_esquerdo",
         "parent_id": "cabeca",
         "bounds": {"x": 20, "y": 25, "largura": 10, "altura": 12}},
        {"id": "olho_direito", "tipo": "olho_direito",
         "parent_id": "cabeca",
         "bounds": {"x": 45, "y": 25, "largura": 10, "altura": 12}},
        {"id": "boca", "tipo": "boca", "parent_id": "cabeca",
         "bounds": {"x": 30, "y": 50, "largura": 20, "altura": 8}},
        {"id": "braco_esquerdo", "tipo": "braco_esquerdo",
         "parent_id": "tronco",
         "bounds": {"x": -30, "y": 110, "largura": 25, "altura": 80}},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco",
         "bounds": {"x": 85, "y": 110, "largura": 25, "altura": 80}},
        {"id": "mao_direita", "tipo": "mao_direita",
         "parent_id": "braco_direito",
         "bounds": {"x": 88, "y": 190, "largura": 20, "altura": 20}},
    ]
    analise = MockCharacterAnalyzer(deteccoes).analisar()
    print(f"1. analise: {len(analise)} partes, origem={analise.origem}")

    print("2. partes detectadas:",
          sorted(d.id for d in analise.deteccoes))

    rig = construir_rig(analise, rig_id="juh", nome="Juh")
    print("3. hierarquia:")
    for parte in rig.listar_partes():
        print(f"   {parte.id} [{parte.tipo}] pai={parte.parent_id}")
    print("4. pivos:")
    for pid in ("cabeca", "braco_direito", "tronco"):
        p = rig.obter_parte(pid)
        print(f"   {pid}: ({p.pivot_x:g}{p.pivot_unidade_x},"
              f"{p.pivot_y:g}{p.pivot_unidade_y})")

    rig.adicionar_view(RigView("frente", imagem_ref="juh.png"))
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.2, 1.0]}}))
    rig.adicionar_pose(RigPose("neutro",
                               {"cabeca": {"rotacao": 0.0}}))
    rig.adicionar_pose(RigPose("aceno", {
        "braco_direito": {"rotacao": 45.0},
        "cabeca": {"rotacao": 5.0}}, expressao="sorriso"))
    print(f"5. rig: {len(rig)} partes, {len(rig._poses)} poses, "
          f"{len(rig._expressoes)} expressoes, "
          f"{len(rig._views)} vistas; valido={rig.validar()}")

    juh = rig_para_personagem(rig, "Juh")
    print(f"6. F12: {juh.nome} com {len(juh.partes)} partes; "
          f"boca filha de {juh.obter_parte('boca').pai.nome}")
    print("7. pose:", juh.aplicar_pose("aceno"))
    print("8. expressao:", juh.aplicar_pose("sorriso"))

    gesto = definir_automatica(rig, "acenar")
    print(f"9. automatica '{gesto.nome}': {len(gesto.passos)} passos; "
          f"motions via transicionar_pose: "
          f"{len(juh.transicionar_pose('aceno', origem='neutro'))} "
          f"definicoes F11")
    _ = debug_rigging


if __name__ == "__main__":
    main()
