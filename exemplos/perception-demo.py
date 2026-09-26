"""ELiXX Fase 22 — demo Perception Core (sem YOLO, sem rede).

Simula uma tela 1920x1080 com MockPerceptionProvider (janela, botão,
campo, texto, ícone, personagem) e percorre a cadeia:

    Perception -> Geometry -> Environment -> World

Mostra quantidade, classe, bounds, confiança, origem e relações
geométricas. Percepção observa; nada aqui decide ou executa.
"""
from elixx.visual.ambiente import vincular_ambiente
from elixx.visual.geometria import GeometryMap
from elixx.visual.transform import Vector2
from elixx.visual.percepcao import (
    ImageFrame,
    MockPerceptionProvider,
    NullPerceptionProvider,
    PerceptionRegistry,
    calcular_delta,
    debug_percepcao,
    percepcao_para_environment,
    percepcao_para_geometria,
)


def main() -> None:
    frame = ImageFrame(1920, 1080, formato="rgb", frame_id="f1")
    prov = MockPerceptionProvider([
        {"id": "janela_1", "classe": "janela", "tipo": "interface",
         "x": 0, "y": 0, "largura": 1920, "altura": 1080,
         "confianca": 0.99},
        {"id": "btn_ok", "classe": "botao", "x": 420, "y": 280,
         "largura": 120, "altura": 40, "confianca": 0.91,
         "texto": "Entrar"},
        {"id": "campo_1", "classe": "entrada", "x": 420, "y": 340,
         "largura": 300, "altura": 36, "confianca": 0.87},
        {"id": "txt_1", "classe": "texto", "tipo": "texto",
         "x": 420, "y": 240, "largura": 200, "altura": 24,
         "texto": "Bem-vindo", "confianca": 0.95},
        {"id": "icone_1", "classe": "icone", "x": 60, "y": 60,
         "largura": 32, "altura": 32, "confianca": 0.78},
        {"id": "hero", "classe": "personagem", "tipo": "personagem",
         "x": 900, "y": 500, "largura": 64, "altura": 96,
         "confianca": 0.88, "track_id": "t7"},
    ])
    reg = PerceptionRegistry()
    reg.registrar(prov)
    reg.registrar(NullPerceptionProvider())

    res = reg.obter("mock").analisar(frame)
    print(f"providers: {reg.listar()}")
    print(f"percepcao: {len(res)} observacoes, origem={res.origem}, "
          f"classes={res.classes()}")

    print("--- observacoes ---")
    for o in sorted(res.observacoes, key=lambda x: x.id):
        print(f"  {o.id} [{o.classe}] pos=({o.bounds.x:g},"
              f"{o.bounds.y:g}) tam={o.bounds.largura:g}x"
              f"{o.bounds.altura:g} conf={o.confianca} "
              f"origem={o.origem}")

    mapa = percepcao_para_geometria(res)
    assert isinstance(mapa, GeometryMap)
    rel = mapa.relacao("btn_ok", "campo_1")
    print(f"geometria: {len(mapa)} nos; "
          f"btn_ok->campo_1 dir={rel['direcao']} "
          f"dist={rel['distancia']:.1f}")
    print("  proximos de (480,300):",
          [p["id"] for p in mapa.buscar_proximos(Vector2(480, 300),
                                                 3)])

    env = percepcao_para_environment(res, env_id="tela")
    print(f"environment: {len(env)} nos, "
          f"{len(env._interacoes)} interacoes (zero: sem 'pode clicar')")
    mundo = vincular_ambiente(env)
    print(f"world: {len(mundo)} entidades; "
          f"btn_ok={mundo.por_id('btn_ok').tipo}")

    snap = res.snapshot()
    delta = calcular_delta(res, reg.obter("nulo").analisar(frame))
    print(f"snapshot: {len(snap.ids())} obs; "
          f"delta vs nulo: +{len(delta.adicionados)} "
          f"-{len(delta.removidos)}")
    print("--- debug ---")
    print(debug_percepcao(res).splitlines()[0])


if __name__ == "__main__":
    main()
