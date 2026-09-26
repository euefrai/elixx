"""ELiXX Fase 24 — demo Living Puppet (headless; sem display).

Juh: pose neutra, sorriso, olhos fechados, olhar, respirar, acenar,
squash, stretch, combinação simultânea e retorno à base. Tk só se
houver tela (opcional); o teste da demo é o modo headless abaixo.
"""
from elixx.visual.deformacao import (
    BasePose,
    Deformacao,
    ExpressionStack,
    aplicar_deformacao,
    comportamento,
    compor_camadas,
    deformacao_para_motions,
    deformation_rig_de_rig,
)
from elixx.visual.rigging import (
    MockCharacterAnalyzer,
    RigExpression,
    RigPose,
    construir_rig,
    definir_automatica,
    rig_para_personagem,
)


def main() -> None:
    deteccoes = [
        {"id": "tronco", "tipo": "tronco",
         "bounds": {"x": 0, "y": 100, "largura": 80, "altura": 120}},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco",
         "bounds": {"x": 10, "y": 0, "largura": 60, "altura": 70}},
        {"id": "cabelo", "tipo": "cabelo", "parent_id": "cabeca",
         "bounds": {"x": 5, "y": -15, "largura": 70, "altura": 25}},
        {"id": "olhos", "tipo": "olhos", "parent_id": "cabeca",
         "bounds": {"x": 20, "y": 25, "largura": 35, "altura": 12}},
        {"id": "boca", "tipo": "boca", "parent_id": "cabeca",
         "bounds": {"x": 30, "y": 50, "largura": 20, "altura": 8}},
        {"id": "braco_esquerdo", "tipo": "braco_esquerdo",
         "parent_id": "tronco",
         "bounds": {"x": -30, "y": 110, "largura": 25, "altura": 80}},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco",
         "bounds": {"x": 85, "y": 110, "largura": 25, "altura": 80}},
    ]
    rig = construir_rig(MockCharacterAnalyzer(deteccoes).analisar(),
                        rig_id="juh", nome="Juh")
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.3, 0.8]}}))
    rig.adicionar_expressao(RigExpression(
        "olhos_fechados", {"olhos": {"opacidade": 0.0}}))
    rig.adicionar_pose(RigPose("neutro", {}))
    juh = rig_para_personagem(rig, "Juh")
    drig = deformation_rig_de_rig(rig, juh)
    base = drig.base

    print("1. neutra:", juh.aplicar_pose("neutro"))
    print("2. sorriso:", juh.aplicar_pose("sorriso"))
    print("3. olhos_fechados:",
          juh.aplicar_pose("olhos_fechados"))
    olhar = comportamento(juh, "olhar", direcao="direita")
    for p in olhar:
        juh.aplicar_pose(p)
    print(f"4. olhar direita: {len(olhar)} passos")
    for p in comportamento(juh, "respirar"):
        juh.aplicar_pose(p)
    print("5. respirar: tronco de volta a",
          juh.obter_parte("tronco").no.escala_y)
    gesto = definir_automatica(rig, "acenar")
    print(f"6. acenar: gesto '{gesto.nome}' com {len(gesto.passos)} "
          "passos F12/F11")
    aplicar_deformacao(juh, Deformacao("tronco", tipo="squash",
                                       intensidade=0.08), base)
    print("7. squash: escala tronco =",
          round(juh.obter_parte("tronco").no.escala_x, 3))
    aplicar_deformacao(juh, Deformacao("tronco", tipo="stretch",
                                       intensidade=0.08), base)
    print("8. stretch: escala tronco =",
          round(juh.obter_parte("tronco").no.escala_x, 3))
    stack = ExpressionStack(["sorriso", "olhos_fechados"])
    fundida = stack.resolver({p.nome: p for p in
                              juh.poses.values()})
    combo = compor_camadas([fundida] + olhar[:1])
    print("9. combo sorriso+olhos+olhar:", sorted(
        combo.entradas))
    print("   motions squash (F11):",
          len(deformacao_para_motions(juh, Deformacao(
              "tronco", tipo="squash", intensidade=0.08), base)))
    print("10. restore:", sorted(base.restaurar(juh)))

    # Visual opcional: só com display real (nunca nos testes).
    try:
        import tkinter as _tk

        raiz = _tk.Tk()
        raiz.withdraw()
        etiqueta = _tk.Label(
            raiz, text="Juh vive (headless OK; feche para sair)")
        etiqueta.pack()
        raiz.after(1500, raiz.destroy)
        raiz.deiconify()
        raiz.mainloop()
        print("tk: janela exibida e fechada")
    except Exception as exc:
        print(f"tk: headless ({type(exc).__name__})")


if __name__ == "__main__":
    main()
