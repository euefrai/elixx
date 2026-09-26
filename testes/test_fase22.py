"""Testes da Fase 22 — Visual Perception Core.

Determinísticos, stdlib, sem YOLO real, sem rede, sem renderer.
"""
import json
import time

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.mundo import Bounds2D
from elixx.visual.percepcao import (
    ImageFrame,
    MockPerceptionProvider,
    NullPerceptionProvider,
    OCRProvider,
    PerceptionDelta,
    PerceptionObservation,
    PerceptionProvider,
    PerceptionRegistry,
    PerceptionResult,
    PerceptionSnapshot,
    YOLOProvider,
    calcular_delta,
    debug_percepcao,
    percepcao_para_environment,
    percepcao_para_geometria,
)


def obs_amostra():
    return [
        {"id": "janela_1", "classe": "janela", "tipo": "interface",
         "x": 0, "y": 0, "largura": 1920, "altura": 1080,
         "confianca": 0.99},
        {"id": "btn_ok", "classe": "botao", "tipo": "interface",
         "x": 420, "y": 280, "largura": 120, "altura": 40,
         "confianca": 0.91, "texto": "Entrar"},
        {"id": "campo_1", "classe": "entrada", "x": 420, "y": 340,
         "largura": 300, "altura": 36, "confianca": 0.87},
        {"id": "txt_1", "classe": "texto", "tipo": "texto",
         "x": 420, "y": 240, "largura": 200, "altura": 24,
         "texto": "Bem-vindo", "confianca": 0.95},
        {"id": "icone_1", "classe": "icone", "x": 60, "y": 60,
         "largura": 32, "altura": 32},
        {"id": "hero", "classe": "personagem", "tipo": "personagem",
         "x": 900, "y": 500, "largura": 64, "altura": 96,
         "track_id": "t7"},
    ]


def resultado_amostra():
    prov = MockPerceptionProvider(obs_amostra())
    return prov.analisar()


# 1. Observation básica

def test_observation():
    o = PerceptionObservation("obj_001", classe="botao",
                              bounds=Bounds2D(420, 280, 120, 40),
                              confianca=0.91, origem="detector")
    assert o.id == "obj_001" and o.classe == "botao"
    assert o.confianca == 0.91 and o.texto is None
    assert o.track_id is None


# 2. Observation com texto e track

def test_observation_texto_track():
    o = PerceptionObservation.from_dict(
        {"id": "t1", "classe": "texto", "tipo": "texto",
         "bounds": {"x": 1, "y": 2, "largura": 3, "altura": 4},
         "texto": "Entrar", "track_id": "t1", "origem": "ocr"})
    assert o.texto == "Entrar" and o.track_id == "t1"
    assert o.to_dict()["texto"] == "Entrar"


# 3. Result básico

def test_result():
    res = resultado_amostra()
    assert len(res) == 6 and "btn_ok" in res
    assert res.por_id("btn_ok").classe == "botao"
    assert res.origem == "mock"


# 4. ImageFrame válido

def test_imageframe():
    f = ImageFrame(1920, 1080, formato="rgb", frame_id="f1",
                   dados=b"\x00" * 10)
    assert (f.largura, f.altura) == (1920, 1080)
    assert f.tem_dados is True
    d = f.to_dict()
    assert d["bytes"] == 10 and "dados" not in d
    assert ImageFrame.from_dict(d).frame_id == "f1"


# 5. ImageFrame inválido

def test_imageframe_invalido():
    with pytest.raises(ErroELiXX):
        ImageFrame(0, 1080)
    with pytest.raises(ErroELiXX):
        ImageFrame(1920, -5)
    with pytest.raises(ErroELiXX):
        ImageFrame(1920.5, 1080)
    with pytest.raises(ErroELiXX):
        ImageFrame(10 ** 9, 10 ** 9)
    with pytest.raises(ErroELiXX):
        ImageFrame(640, 480, dados="nao-bytes")


# 6. validação de bounds

def test_bounds_validacao():
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", bounds=Bounds2D(0, 0, -1, 5))
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", bounds="nao-bounds")
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", bounds=Bounds2D(10 ** 9, 0, 1, 1))


# 7. Bounds2D reutilizado

def test_bounds2d_reutilizado():
    import elixx.visual.percepcao as modulo

    assert modulo.Bounds2D is Bounds2D
    assert "class Bounds2D" not in open(modulo.__file__,
                                        encoding="utf-8").read()


# 8. confiança limites

def test_confianca():
    assert PerceptionObservation("a", confianca=0.0).confianca == 0.0
    assert PerceptionObservation("a", confianca=1.0).confianca == 1.0
    assert PerceptionObservation("a").confianca is None
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", confianca=1.5)
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", confianca=-0.1)


# 9. origem preservada

def test_origem():
    res = resultado_amostra()
    assert all(o.origem == "mock" for o in res.observacoes)
    mapa_origens = {"yolo", "ocr", "html", "acessibilidade"}
    for origem in mapa_origens:
        o = PerceptionObservation("x", origem=origem)
        assert o.origem == origem


# 10. texto opcional

def test_texto_opcional():
    assert PerceptionObservation("a").texto is None
    assert PerceptionObservation("a", texto="oi").texto == "oi"


# 11. tipos básicos + desconhecido representado

def test_tipos():
    for tipo in ("objeto", "texto", "regiao", "interface",
                 "personagem", "imagem", "icone", "botao", "entrada",
                 "link", "janela", "cursor", "desconhecido"):
        assert PerceptionObservation("x", tipo=tipo).tipo == tipo
    # tipo novo: representado, nunca descartado
    o = PerceptionObservation("x", tipo="holograma", classe="holograma")
    assert o.tipo == "holograma"
    res = PerceptionResult(100, 100, observacoes=[o])
    assert res.por_id("x").classe == "holograma"


# 12. JSON roundtrip

def test_json():
    res = resultado_amostra()
    texto = res.to_json()
    copia = PerceptionResult.from_json(texto)
    assert copia.to_json() == texto
    assert copia.por_id("txt_1").texto == "Bem-vindo"
    with pytest.raises(ErroELiXX):
        PerceptionResult.from_json("{invalido")
    with pytest.raises(ErroELiXX):
        PerceptionResult.from_dict({"largura_imagem": 1})


# 13. dict roundtrip

def test_dict():
    res = resultado_amostra()
    copia = PerceptionResult.from_dict(res.to_dict())
    assert len(copia) == len(res)
    assert copia.classes() == res.classes()


# 14. snapshot imutável

def test_snapshot():
    res = resultado_amostra()
    snap = res.snapshot()
    assert isinstance(snap, PerceptionSnapshot)
    antes = snap.por_id("btn_ok")
    res.observacoes.append(PerceptionObservation("nova"))
    assert snap.por_id("btn_ok") == antes
    assert "nova" not in snap.ids()
    assert "btn_ok" in debug_percepcao(snap)


# 15. MockProvider

def test_mock_provider():
    prov = MockPerceptionProvider(obs_amostra())
    assert prov.disponivel() is True
    assert prov.capacidades() == ["detectar"]
    res = prov.analisar()
    assert isinstance(res, PerceptionResult) and len(res) == 6
    assert res.por_classe("botao")[0].id == "btn_ok"


# 16. Mock com frame (dimensões do frame vencem)

def test_mock_com_frame():
    prov = MockPerceptionProvider(obs_amostra())
    res = prov.analisar(frame=ImageFrame(800, 600, frame_id="f9"))
    assert (res.largura_imagem, res.altura_imagem) == (800, 600)
    assert res.frame_id == "f9"


# 17. NullProvider

def test_null_provider():
    prov = NullPerceptionProvider()
    assert prov.disponivel() is True
    res = prov.analisar()
    assert len(res) == 0 and res.origem == "nulo"
    assert res.validar_tipos() if hasattr(res, "validar_tipos") else True
    res2 = prov.analisar(frame=ImageFrame(640, 480))
    assert (res2.largura_imagem, res2.altura_imagem) == (640, 480)


# 18. Registry

def test_registry():
    reg = PerceptionRegistry()
    mock = MockPerceptionProvider()
    nulo = NullPerceptionProvider()
    reg.registrar(mock)
    reg.registrar(nulo)
    assert reg.listar() == ["mock", "nulo"]
    assert reg.obter("mock") is mock
    assert "mock" in reg
    reg.remover("nulo")
    assert reg.listar() == ["mock"]
    with pytest.raises(ErroELiXX):
        reg.registrar(mock)  # duplicado
    with pytest.raises(ErroELiXX):
        reg.obter("fantasma")
    with pytest.raises(ErroELiXX):
        reg.registrar("nao-provider")


# 19. provider indisponível (base)

def test_provider_base_indisponivel():
    prov = PerceptionProvider("base")
    assert prov.disponivel() is False
    assert prov.capacidades() == []
    with pytest.raises(ErroELiXX):
        prov.analisar()


# 20. percepção → geometria

def test_para_geometria():
    from elixx.visual.geometria import GeometryMap

    res = resultado_amostra()
    mapa = percepcao_para_geometria(res)
    assert isinstance(mapa, GeometryMap) and len(mapa) == 6
    no = mapa.obter("btn_ok")
    assert (no.bounds.x, no.bounds.y) == (420.0, 280.0)
    assert no.metadata["classe"] == "botao"
    assert no.metadata["confianca"] == 0.91
    assert no.metadata["origem"] == "mock"
    assert len(mapa._superficies if hasattr(mapa, "_superficies")
               else []) == 0


# 21. percepção → environment (sem interações inventadas)

def test_para_environment():
    from elixx.visual.ambiente import Environment

    res = resultado_amostra()
    env = percepcao_para_environment(res, env_id="tela")
    assert isinstance(env, Environment)
    assert env.obter_no("btn_ok").tipo == "botao"
    assert env.obter_no("txt_1").tipo == "texto"
    assert env.obter_no("hero").tipo == "desconhecido"
    assert env.obter_no("hero").atributos["classe"] == "personagem"
    assert len(env._interacoes) == 0  # nada de "pode clicar"
    assert env.validar()["valido"] is True


# 22. duplicatas: ambas mantidas + sobreposição detectável

def test_duplicatas():
    prov = MockPerceptionProvider([
        {"id": "a", "classe": "botao", "x": 0, "y": 0,
         "largura": 100, "altura": 100},
        {"id": "b", "classe": "botao", "x": 50, "y": 50,
         "largura": 100, "altura": 100},
    ])
    res = prov.analisar()
    assert len(res) == 2  # ambas mantidas, sem NMS no núcleo
    pares = res.analisar_sobreposicoes()
    assert {"a": "a", "b": "b", "codigo": "sobreposicao"} in pares


# 23. sobreposição sem falso positivo

def test_sobreposicao_limpa():
    prov = MockPerceptionProvider([
        {"id": "a", "x": 0, "y": 0, "largura": 10, "altura": 10},
        {"id": "b", "x": 500, "y": 500, "largura": 10, "altura": 10},
    ])
    assert prov.analisar().analisar_sobreposicoes() == []


# 24. delta adicionados/removidos

def test_delta_add_rem():
    antes = MockPerceptionProvider([
        {"id": "a", "x": 0, "y": 0, "largura": 10, "altura": 10},
        {"id": "b", "x": 5, "y": 5, "largura": 10, "altura": 10},
    ]).analisar()
    depois = MockPerceptionProvider([
        {"id": "b", "x": 5, "y": 5, "largura": 10, "altura": 10},
        {"id": "c", "x": 9, "y": 9, "largura": 10, "altura": 10},
    ]).analisar()
    delta = calcular_delta(antes, depois)
    assert isinstance(delta, PerceptionDelta)
    assert delta.to_dict() == {"adicionados": ["c"],
                               "removidos": ["a"], "alterados": [],
                               "mantidos": ["b"]}


# 25. delta alterados

def test_delta_alterados():
    antes = MockPerceptionProvider([
        {"id": "a", "classe": "botao", "x": 0, "y": 0,
         "largura": 10, "altura": 10, "confianca": 0.5},
    ]).analisar()
    depois = MockPerceptionProvider([
        {"id": "a", "classe": "botao", "x": 20, "y": 0,
         "largura": 10, "altura": 10, "confianca": 0.5},
    ]).analisar()
    delta = calcular_delta(antes, depois)
    assert delta.alterados == ["a"] and delta.mantidos == []


# 26. frame_id e track_id transportados

def test_frame_track():
    res = MockPerceptionProvider(
        obs_amostra()).analisar(frame=ImageFrame(1920, 1080,
                                                 frame_id="f42"))
    assert res.frame_id == "f42"
    assert res.por_id("hero").track_id == "t7"
    # sem comportamento de tracking: só transporte
    assert res.por_id("btn_ok").track_id is None


# 27. NaN recusado

def test_nan():
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", bounds=Bounds2D(float("nan"), 0,
                                                   1, 1))
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", confianca=float("nan"))
    with pytest.raises(ErroELiXX):
        PerceptionResult(float("nan"), 100)


# 28. Infinity recusado

def test_infinity():
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", bounds=Bounds2D(0, 0, float("inf"),
                                                   1))
    with pytest.raises(ErroELiXX):
        ImageFrame(1920, float("inf"))


# 29. dimensões inválidas

def test_dimensoes_invalidas():
    with pytest.raises(ErroELiXX):
        PerceptionResult(0, 100)
    with pytest.raises(ErroELiXX):
        PerceptionResult(-3, 100)
    with pytest.raises(ErroELiXX):
        PerceptionResult("larga", 100)


# 30. dimensões gigantes

def test_dimensoes_gigantes():
    with pytest.raises(ErroELiXX):
        PerceptionResult(10 ** 9, 10 ** 9)
    with pytest.raises(ErroELiXX):
        PerceptionObservation("g", bounds=Bounds2D(0, 0, 10 ** 9,
                                                   10))


# 31. metadata maliciosa inerte

def test_metadata_maliciosa():
    o = PerceptionObservation(
        "__import__('os')", classe="<script>alert(1)</script>",
        texto="{{7*7}}", origem="javascript:evil",
        metadata={"x": "../../../etc/passwd"})
    assert o.id == "__import__('os')"
    res = PerceptionResult(100, 100, observacoes=[o])
    assert res.to_json()  # serializa, nunca executa
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", metadata={"f": object()})
    profundo: dict = {"h": 1}
    for _ in range(8):
        profundo = {"a": profundo}
    with pytest.raises(ErroELiXX):
        PerceptionObservation("a", metadata={"deep": profundo})


# 32. ids duplicados no resultado

def test_ids_duplicados():
    with pytest.raises(ErroELiXX):
        PerceptionResult(100, 100, observacoes=[
            PerceptionObservation("x"), PerceptionObservation("x")])


# 33. determinismo

def test_determinismo():
    a = resultado_amostra().to_json()
    b = resultado_amostra().to_json()
    assert a == b
    d1 = calcular_delta(resultado_amostra(), resultado_amostra())
    assert d1.to_dict() == {"adicionados": [], "removidos": [],
                            "alterados": [],
                            "mantidos": ["btn_ok", "campo_1", "hero",
                                         "icone_1", "janela_1", "txt_1"]}


# 34. segurança (sem execução dinâmica/rede)

def test_seguranca():
    import elixx.visual.percepcao as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("eval(", "exec(", "__import__", "importlib",
                     "subprocess", "os.system", "shell", "requests",
                     "urlopen", "socket", "compile("):
        assert proibido not in fonte, proibido


# 35. performance (100 → 50k)

def test_performance():
    for total in (100, 1000, 5000, 10000, 50000):
        modelos = [{"id": f"o{i:05d}", "classe": "botao",
                    "x": float(i % 200), "y": float(i // 200),
                    "largura": 4.0, "altura": 4.0,
                    "confianca": 0.9}
                   for i in range(total)]
        t0 = time.perf_counter()
        res = MockPerceptionProvider(modelos).analisar()
        t_cria = time.perf_counter()
        texto = res.to_json()
        t_ser = time.perf_counter()
        mapa = percepcao_para_geometria(res)
        t_geo = time.perf_counter()
        snap = res.snapshot()
        snap.ids()
        t_snap = time.perf_counter()
        antes = MockPerceptionProvider([]).analisar()
        calcular_delta(antes, res)
        t_delta = time.perf_counter()
        debug_percepcao(res)
        t_fim = time.perf_counter()
        assert (t_fim - t0) < 60.0, f"{total} obs passou de 60s"
        assert len(texto) > total
        if total == 50000:
            print(f"\n50000 obs: cria={t_cria - t0:.2f}s "
                  f"json={t_ser - t_cria:.2f}s "
                  f"geo={t_geo - t_ser:.2f}s "
                  f"snap={t_snap - t_geo:.2f}s "
                  f"delta={t_delta - t_snap:.2f}s "
                  f"debug={t_fim - t_delta:.2f}s")


# 36. YOLO: contrato sem quebrar (com ou sem lib instalada)

def test_yolo_contrato():
    prov = YOLOProvider()
    assert isinstance(prov.disponivel(), bool)
    assert prov.nome == "yolo"
    # sem modelo configurado: erro claro, sem download, sem rede
    with pytest.raises(ErroELiXX):
        prov.analisar()
    prov2 = YOLOProvider(modelo="/modelos/yolo.pt")
    assert prov2.modelo == "/modelos/yolo.pt"
    # sem ultralytics real carregado aqui: indisponível OU contrato
    try:
        import ultralytics  # noqa: F401

        tem_lib = True
    except ImportError:
        tem_lib = False
    if not tem_lib:
        assert prov.disponivel() is False
        assert prov.capacidades() == []


# 37. OCR: só contrato

def test_ocr_contrato():
    prov = OCRProvider()
    assert prov.disponivel() is False
    assert prov.capacidades() == []
    with pytest.raises(ErroELiXX):
        prov.analisar()


# 38. debug legível

def test_debug():
    texto = debug_percepcao(resultado_amostra())
    for trecho in ("PerceptionResult", "6 observações", "btn_ok",
                   "botao", "420", "0.91", "Bem-vindo", "mock"):
        assert trecho in texto, trecho


# 39. avisos preservados

def test_avisos():
    res = PerceptionResult(100, 100, origem="yolo",
                           avisos=[{"codigo": "sobreposicao",
                                    "motivo": "a/b"}])
    copia = PerceptionResult.from_json(res.to_json())
    assert copia.avisos == [{"codigo": "sobreposicao",
                             "motivo": "a/b"}]
    with pytest.raises(ErroELiXX):
        PerceptionResult(100, 100, avisos=["nao-dict"])


# 40. confiança preservada nas conversões (sem ranking)

def test_confianca_preservada():
    res = resultado_amostra()
    mapa = percepcao_para_geometria(res)
    assert mapa.obter("btn_ok").metadata["confianca"] == 0.91
    env = percepcao_para_environment(res)
    assert env.obter_no("btn_ok").atributos["confianca"] == 0.91
    # sem "melhor detecção": todas presentes
    assert len(mapa) == len(res) == 6


# 41. geometria usa F21 (sem sistema paralelo)

def test_geometria_f21():
    import elixx.visual.percepcao as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class GeometryMap" not in fonte
    assert "class Bounds2D" not in fonte
    from elixx.visual.geometria import GeometryMap

    assert isinstance(percepcao_para_geometria(resultado_amostra()),
                      GeometryMap)


# 42. cadeia percepção → geometria → environment → world

def test_cadeia_completa():
    from elixx.visual.ambiente import vincular_ambiente

    res = resultado_amostra()
    mapa = percepcao_para_geometria(res)
    assert mapa.validar()["valido"] is True
    env = percepcao_para_environment(res, env_id="tela")
    mundo = vincular_ambiente(env)
    assert mundo.por_id("btn_ok").props["env_tipo"] == "botao"
    assert mundo.por_id("btn_ok").tipo == "objeto"


# 43. sem navegação/motion/IA automáticas

def test_sem_automacao():
    import elixx.visual.percepcao as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("class NavigationGraph", "AIContextBuilder",
                     "AIIntent", "heapq", "playwright", "selenium",
                     "pyautogui", "torch", "cv2", "PIL"):
        assert proibido not in fonte, proibido


# 44. lista gigante recusada

def test_lista_gigante():
    with pytest.raises(ErroELiXX):
        PerceptionResult(100, 100, observacoes=[
            PerceptionObservation(f"o{i}") for i in range(100001)])


# 45. regressão F19/F21 intactas

def test_regressao():
    from elixx.visual.ambiente import Environment, EnvironmentNode
    from elixx.visual.geometria import GeometryMap, GeometryNode

    env = Environment("e", tipo="web")
    env.adicionar_no(EnvironmentNode("n", tipo="botao", x=1, y=2,
                                     largura=3, altura=4))
    assert env.validar()["valido"] is True
    mapa = GeometryMap("m")
    mapa.adicionar(GeometryNode("n", Bounds2D(1, 2, 3, 4)))
    assert mapa.validar()["valido"] is True
    # percepção não tocou nos módulos antigos
    import elixx.visual.ambiente as f19
    import elixx.visual.geometria as f21

    assert "percepcao" not in open(f19.__file__,
                                   encoding="utf-8").read()
    assert "percepcao" not in open(f21.__file__,
                                   encoding="utf-8").read()
