"""ELiXX Fase 21 — demo Visual Geometry Core (Python puro).

Constrói um pequeno ambiente (janela/cabeçalho/menu/conteúdo/card/
botão/rodapé), cada elemento com GeometryNode, e mostra: bounds,
centros, relações, regiões e consultas espaciais. Sem renderer,
sem navegador, sem rede.
"""
from elixx.visual.geometria import (
    GeometryMap,
    GeometryNode,
    GeometryRegion,
    Point2D,
    debug_geometria,
    environment_para_geometria,
    geometria_para_world,
)
from elixx.visual.mundo import Bounds2D


def main() -> None:
    mapa = GeometryMap("demo")
    mapa.adicionar(GeometryNode("janela", Bounds2D(0, 0, 800, 600)))
    mapa.adicionar(GeometryNode("cabecalho", Bounds2D(0, 0, 800, 60),
                                parent_id="janela"))
    mapa.adicionar(GeometryNode("menu", Bounds2D(0, 60, 150, 480),
                                parent_id="janela"))
    mapa.adicionar(GeometryNode("conteudo", Bounds2D(150, 60, 650, 480),
                                parent_id="janela"))
    mapa.adicionar(GeometryNode("card", Bounds2D(20, 20, 300, 150),
                                parent_id="conteudo"))
    mapa.adicionar(GeometryNode("botao", Bounds2D(30, 90, 120, 40),
                                parent_id="card"))
    mapa.adicionar(GeometryNode("rodape", Bounds2D(0, 540, 800, 60),
                                parent_id="janela"))
    mapa.adicionar_regiao(GeometryRegion("reg_conteudo",
                                         Bounds2D(150, 60, 650, 480)))

    print(f"mapa: {len(mapa)} nós, "
          f"{len(mapa.listar_regioes())} regiões, "
          f"válido={mapa.validar()['valido']}")

    print("--- bounds e centros (globais) ---")
    for nid in ("cabecalho", "menu", "card", "botao"):
        g = mapa.bounds_global(nid)
        c = mapa.centro_global(nid)
        print(f"  {nid}: pos=({g.x:g},{g.y:g}) tam={g.largura:g}x"
              f"{g.altura:g} centro=({c.x:g},{c.y:g})")

    print("--- relações (botao x vizinhos) ---")
    for outro in ("card", "menu", "rodape"):
        rel = mapa.relacao("botao", outro)
        print(f"  botao->{outro}: dir={rel['direcao']} "
              f"dist={rel['distancia']:.1f} dentro={rel['dentro']} "
              f"sobrepoe={rel['sobrepoe']}")

    print("--- regiões ---")
    print("  na reg_conteudo:",
          sorted(n.id for n in mapa.buscar_por_regiao("reg_conteudo")))
    print("  acima do rodape:", mapa.acima_de("rodape"))
    print("  ao sul do cabecalho:",
          sorted(n.id for n in mapa.buscar_direcao("cabecalho", "sul")))

    print("--- consultas espaciais ---")
    print("  ponto (260,190):",
          sorted(n.id for n in mapa.buscar_por_ponto(Point2D(260, 190))))
    print("  próximos de (400,300):",
          [(p["id"], round(p["distancia"], 1))
           for p in mapa.buscar_proximos(Point2D(400, 300), 3)])

    print("--- snapshot ---")
    snap = mapa.snapshot()
    mapa.atualizar("botao", bounds=Bounds2D(0, 0, 1, 1))
    print("  snapshot preservado:",
          snap.bounds_global("botao") == {"x": 200.0, "y": 170.0,
                                          "largura": 120.0,
                                          "altura": 40.0})

    print("--- world (integração opcional) ---")
    mundo = geometria_para_world(mapa, nome="demo_geo")
    print(f"  {len(mundo)} entidades; "
          f"botao={mundo.por_id('botao').tipo}")

    print("--- environment -> geometria (so explicita) ---")
    from elixx.visual.ambiente import Environment, EnvironmentNode

    env = Environment("e", tipo="web")
    env.adicionar_no(EnvironmentNode("com_geo", tipo="botao", x=10,
                                     y=20, largura=30, altura=40))
    env.adicionar_no(EnvironmentNode("sem_geo", tipo="botao"))
    mapa2, ausentes = environment_para_geometria(env)
    print(f"  no mapa: {sorted(n.id for n in mapa2.listar())}; "
          f"ausentes (sem inventar): {ausentes}")

    _ = debug_geometria


if __name__ == "__main__":
    main()
