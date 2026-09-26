"""Testes da Fase 23 — Automatic Character Rigging & 2D Puppet Core.

Determinísticos, stdlib, sem YOLO/SAM/MediaPipe, sem rede, sem display.
"""
import json
import time

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.mundo import Bounds2D
from elixx.visual.rigging import (
    AUTOMATICAS,
    CharacterAnalysis,
    CharacterAnalyzer,
    CharacterMask,
    CharacterPartDetection,
    CharacterRig,
    MockCharacterAnalyzer,
    NullCharacterAnalyzer,
    RigExpression,
    RigJoint,
    RigLayer,
    RigPart,
    RigPose,
    RigView,
    StructuredCharacterAnalyzer,
    analise_de_percepcao,
    construir_rig,
    debug_rigging,
    definir_automatica,
    mesclar_analise,
    rig_para_personagem,
)


def deteccoes_juh():
    return [
        {"id": "tronco", "tipo": "tronco",
         "bounds": {"x": 0, "y": 100, "largura": 80, "altura": 120},
         "confianca": 0.98},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco",
         "bounds": {"x": 10, "y": 0, "largura": 60, "altura": 70},
         "confianca": 0.97},
        {"id": "olho_esquerdo", "tipo": "olho_esquerdo",
         "parent_id": "cabeca",
         "bounds": {"x": 20, "y": 25, "largura": 10, "altura": 12},
         "confianca": 0.9},
        {"id": "olho_direito", "tipo": "olho_direito",
         "parent_id": "cabeca",
         "bounds": {"x": 45, "y": 25, "largura": 10, "altura": 12},
         "confianca": 0.9},
        {"id": "boca", "tipo": "boca", "parent_id": "cabeca",
         "bounds": {"x": 30, "y": 50, "largura": 20, "altura": 8},
         "confianca": 0.88},
        {"id": "braco_esquerdo", "tipo": "braco_esquerdo",
         "parent_id": "tronco",
         "bounds": {"x": -30, "y": 110, "largura": 25, "altura": 80},
         "confianca": 0.91},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco",
         "bounds": {"x": 85, "y": 110, "largura": 25, "altura": 80},
         "confianca": 0.91},
        {"id": "mao_direita", "tipo": "mao_direita",
         "parent_id": "braco_direito",
         "bounds": {"x": 88, "y": 190, "largura": 20, "altura": 20},
         "confianca": 0.85},
    ]


def analise_juh():
    return MockCharacterAnalyzer(deteccoes_juh()).analisar()


def rig_juh():
    return construir_rig(analise_juh(), rig_id="juh", nome="Juh")


# 1. CharacterAnalysis

def test_analysis():
    ana = analise_juh()
    assert isinstance(ana, CharacterAnalysis) and len(ana) == 8
    assert "cabeca" in ana and ana.por_id("boca").tipo == "boca"
    assert ana.origem == "mock"


# 2. part detection

def test_part_detection():
    d = CharacterPartDetection("b1", tipo="braco",
                               bounds=Bounds2D(0, 0, 10, 20),
                               confianca=0.91)
    assert d.id == "b1" and d.confianca == 0.91
    assert d.visibilidade == "visivel"
    assert CharacterPartDetection.from_dict(d.to_dict()).id == "b1"


# 3. masks (bounds / polígono / referência)

def test_masks():
    m1 = CharacterMask("m1", "cabeca",
                       bounds=Bounds2D(0, 0, 10, 10))
    assert m1.kind == "bounds"
    m2 = CharacterMask("m2", "cabeca", kind="poligono",
                       pontos=[{"x": 0, "y": 0}, {"x": 5, "y": 0},
                               {"x": 2, "y": 4}])
    assert len(m2.pontos) == 3
    m3 = CharacterMask("m3", "corpo", kind="referencia",
                       imagem_ref="juh.png")
    assert m3.imagem_ref == "juh.png"
    assert CharacterMask.from_dict(m1.to_dict()).id == "m1"
    rig = rig_juh()
    rig.adicionar_mascara(CharacterMask("mm", "cabeca"))
    assert "mm" in rig._mascaras


# 4. hierarchy

def test_hierarchy():
    rig = rig_juh()
    assert [c.id for c in rig.filhos("tronco")] == [
        "braco_direito", "braco_esquerdo", "cabeca"]
    assert [a.id for a in rig.ancestrais("mao_direita")] == [
        "braco_direito", "tronco", "corpo"]  # raiz de ancoragem
    assert rig.obter_parte("boca").parent_id == "cabeca"


# 5. pivot

def test_pivot():
    rig = rig_juh()
    cabeca = rig.obter_parte("cabeca")
    assert (cabeca.pivot_x, cabeca.pivot_unidade_x) == (50.0, "%")
    assert (cabeca.pivot_y, cabeca.pivot_unidade_y) == (100.0, "%")
    tronco = rig.obter_parte("tronco")
    assert tronco.pivot_y == 50.0
    with pytest.raises(ErroELiXX):
        RigPart("x", pivot_unidade_x="graus")


# 6. joints

def test_joints():
    rig = rig_juh()
    j = rig.obter_parte("braco_esquerdo").joint
    assert isinstance(j, RigJoint)
    assert (j.parent, j.child) == ("tronco", "braco_esquerdo")
    assert j.tipo == "pivo"
    j2 = RigJoint("ombro", "tronco", "braco", minimo=-90.0,
                  maximo=90.0)
    from elixx.visual.personagem import Joint as _J

    f12 = _J("ombro", "braco", minimo=-90.0, maximo=90.0)
    assert f12.aplicar_limite(120.0) == 90.0
    assert j2.to_dict()["maximo"] == 90.0
    with pytest.raises(ErroELiXX):
        RigJoint("j", "a", "a")
    with pytest.raises(ErroELiXX):
        RigJoint("j", "a", "b", minimo=10.0, maximo=-10.0)


# 7. views

def test_views():
    rig = rig_juh()
    rig.adicionar_view(RigView("frente", imagem_ref="juh_frente.png",
                               partes_visiveis=["cabeca", "tronco"]))
    rig.adicionar_view(RigView("costas", imagem_ref="juh_costas.png"))
    assert set(rig._views) == {"costas", "frente"}
    perso = rig_para_personagem(rig, "Juh")
    assert perso.representacoes["frente"] == "juh_frente.png"
    with pytest.raises(ErroELiXX):
        RigView("3d")


# 8. expressions

def test_expressions():
    rig = rig_juh()
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": (1.2, 1.0)}}))
    assert "sorriso" in rig._expressoes
    perso = rig_para_personagem(rig, "Juh")
    assert perso.obter_pose("sorriso").expressao is True
    tocadas = perso.aplicar_pose("sorriso")
    assert tocadas == ["boca"]


# 9. poses

def test_poses():
    rig = rig_juh()
    rig.adicionar_pose(RigPose("neutro", {"cabeca": {"rotacao": 0.0}}))
    rig.adicionar_pose(RigPose("aceno",
                               {"braco_direito": {"rotacao": 45.0}}))
    perso = rig_para_personagem(rig, "Juh")
    assert perso.aplicar_pose("aceno") == ["braco_direito"]
    assert perso.pose_atual == "aceno"


# 10. serialization

def test_serialization():
    rig = rig_juh()
    rig.adicionar_view(RigView("frente"))
    rig.adicionar_expressao(RigExpression("sorriso", {"boca": {}}))
    rig.adicionar_pose(RigPose("neutro"))
    texto = rig.to_json()
    copia = CharacterRig.from_json(texto)
    assert copia.to_json() == texto
    assert len(copia) == len(rig) == 9  # 8 detecções + raiz "corpo"
    ana = analise_juh()
    assert CharacterAnalysis.from_json(ana.to_json()).id == ana.id


# 11. validation (rig válido)

def test_validation():
    rig = rig_juh()
    assert rig.validar()["valido"] is True
    assert CharacterRig("vazio").validar()["valido"] is True


# 12. duplicate IDs

def test_duplicate_ids():
    rig = CharacterRig("r")
    rig.adicionar_parte(RigPart("a"))
    with pytest.raises(ErroELiXX):
        rig.adicionar_parte(RigPart("a"))
    with pytest.raises(ErroELiXX):
        CharacterAnalysis("x", [CharacterPartDetection("d"),
                                CharacterPartDetection("d")])


# 13. invalid parent

def test_invalid_parent():
    rig = CharacterRig("r")
    with pytest.raises(ErroELiXX):
        rig.adicionar_parte(RigPart("filha", parent_id="fantasma"))
    with pytest.raises(ErroELiXX):
        rig.adicionar_camada(RigLayer("c", "fantasma"))


# 14. cycle detection

def test_cycle():
    rig = CharacterRig("r")
    rig.adicionar_parte(RigPart("a"))
    rig.adicionar_parte(RigPart("b", parent_id="a"))
    with pytest.raises(ErroELiXX):
        rig._partes["a"].parent_id = "b"
        erro = rig._ciclo("a")
        assert erro is not None
        raise ErroELiXX(erro)


# 15. depth limit

def test_depth_limit():
    rig = CharacterRig("r")
    rig.adicionar_parte(RigPart("n0"))
    for i in range(1, 33):
        rig.adicionar_parte(RigPart(f"n{i}", parent_id=f"n{i - 1}"))
    assert rig.validar()["valido"] is True
    rig._partes["n0"].parent_id = "n32"  # fecha ciclo fundo
    assert rig.validar()["codigo"] == "ciclo"


# 16. malformed JSON

def test_malformed_json():
    with pytest.raises(ErroELiXX):
        CharacterRig.from_json("{invalido")
    with pytest.raises(ErroELiXX):
        CharacterAnalysis.from_json("[1,2]")
    with pytest.raises(ErroELiXX):
        CharacterRig.from_dict({"id": "r", "partes": "nao-lista"} if False
                               else "nao-dict")


# 17. NaN

def test_nan():
    with pytest.raises(ErroELiXX):
        RigPart("a", bounds=Bounds2D(float("nan"), 0, 1, 1))
    with pytest.raises(ErroELiXX):
        RigJoint("j", "a", "b", minimo=float("nan"))
    with pytest.raises(ErroELiXX):
        CharacterPartDetection("d", confianca=float("nan"))


# 18. Infinity

def test_infinity():
    with pytest.raises(ErroELiXX):
        RigPart("a", pivot_x=float("inf"))
    with pytest.raises(ErroELiXX):
        CharacterMask("m", "p",
                      bounds=Bounds2D(0, 0, float("inf"), 1))


# 19. giant structures

def test_giant():
    with pytest.raises(ErroELiXX):
        RigPart("g", bounds=Bounds2D(1e18, 0, 1, 1))
    with pytest.raises(ErroELiXX):
        CharacterAnalysis("g", [CharacterPartDetection(f"p{i}")
                                for i in range(5001)])
    assert len(CharacterAnalysis(
        "ok", [CharacterPartDetection(f"p{i}")
               for i in range(1000)])) == 1000


# 20. malicious strings (inertes)

def test_malicious_strings():
    rig = CharacterRig("__import__('os')")
    rig.adicionar_parte(RigPart(
        "<script>alert(1)</script>", tipo="{{7*7}}",
        metadata={"x": "../../../etc/passwd"}))
    assert "<script>alert(1)</script>" in rig
    assert rig.to_json()
    ana = MockCharacterAnalyzer([{
        "id": "eval(x)", "tipo": "exec(coisa)"}]).analisar()
    assert "eval(x)" in ana


# 21. NullAnalyzer

def test_null_analyzer():
    ana = NullCharacterAnalyzer().analisar()
    assert len(ana) == 0 and ana.origem == "nulo"
    assert any(a["codigo"] == "sem_deteccoes" for a in ana.avisos)
    rig = construir_rig(ana)
    assert len(rig) == 0
    assert any(a["codigo"] == "rig_vazio" for a in rig.avisos)


# 22. MockAnalyzer

def test_mock_analyzer():
    prov = MockCharacterAnalyzer(deteccoes_juh())
    assert prov.disponivel() is True
    ana = prov.analisar()
    assert len(ana) == 8 and ana.origem == "mock"


# 23. StructuredAnalyzer

def test_structured_analyzer():
    prov = StructuredCharacterAnalyzer()
    assert prov.disponivel() is True
    ana = prov.analisar({"parts": [
        {"id": "cabeca", "tipo": "cabeca",
         "bounds": {"x": 0, "y": 0, "largura": 10, "altura": 10},
         "confianca": 0.98}]})
    assert ana.por_id("cabeca").tipo == "cabeca"
    assert ana.metadata["total"] == 1
    with pytest.raises(ErroELiXX):
        prov.analisar("nao-dict")
    with pytest.raises(ErroELiXX):
        prov.analisar({"parts": "nao-lista"})


# 24. assisted correction (mesclar)

def test_assisted():
    base = analise_juh()
    mesclada = mesclar_analise(base, [
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco",
         "bounds": {"x": 80, "y": 105, "largura": 26, "altura": 82},
         "confianca": 0.99},
        {"id": "olho_extra", "tipo": "olho_extra_custom",
         "bounds": {"x": 1, "y": 1, "largura": 2, "altura": 2}},
    ])
    assert mesclada.origem == "assistido"
    assert mesclada.por_id("braco_direito").confianca == 0.99
    assert "olho_extra" in mesclada  # adicionada, resto preservado
    assert len(mesclada) == len(base) + 1


# 25. professional rig (tudo explícito)

def test_professional():
    rig = CharacterRig("prof", nome="Pro")
    rig.adicionar_parte(RigPart("corpo", tipo="corpo",
                                bounds=Bounds2D(0, 0, 80, 200)))
    rig.adicionar_parte(RigPart(
        "braco", tipo="braco_esquerdo",
        bounds=Bounds2D(-30, 10, 25, 80), parent_id="corpo",
        pivot_x=50.0, pivot_y=0.0,
        joint=RigJoint("ombro", "corpo", "braco",
                       minimo=-90.0, maximo=90.0)))
    rig.adicionar_mascara(CharacterMask("m_braco", "braco"))
    rig.adicionar_camada(RigLayer("cam_braco", "braco", ordem=3))
    rig.adicionar_view(RigView("frente", imagem_ref="pro.png"))
    rig.adicionar_expressao(RigExpression("bravo", {"braco": {}}))
    rig.adicionar_pose(RigPose("neutro", {"braco": {"rotacao": 0.0}},
                               expressao="bravo"))
    assert rig.validar()["valido"] is True
    assert rig.camadas_ordenadas()[0].id == "cam_braco"


# 26. conversion to F12

def test_para_f12():
    from elixx.visual.personagem import Character

    perso = rig_para_personagem(rig_juh(), "Juh")
    assert isinstance(perso, Character)
    assert perso.nome == "Juh"
    assert set(perso.partes) == ({d["id"] for d in deteccoes_juh()}
                                 | {"corpo"})
    assert perso.obter_parte("boca").pai.nome == "cabeca"
    assert "neutro" in perso.poses  # sempre incluída


# 27. Motion Core integration (definições, sem motor)

def test_motion_integration():
    perso = rig_para_personagem(rig_juh(), "Juh")
    rig = rig_juh()
    rig.adicionar_pose(RigPose("aceno",
                               {"braco_direito": {"rotacao": 45.0}}))
    perso2 = rig_para_personagem(rig, "Juh")
    defs = perso2.transicionar_pose("aceno", origem="neutro")
    assert len(defs) >= 1
    assert all(hasattr(d, "chaves") for d in defs)
    # cabeça 0 → 10 → -10 → 0 e braço 0 → 45 → 0 (conceitual)
    rig.adicionar_pose(RigPose("olhar",
                               {"cabeca": {"rotacao": 10.0}}))
    perso3 = rig_para_personagem(rig, "Juh")
    defs2 = perso3.transicionar_pose("olhar", origem="neutro")
    assert any("cabeca" in d.nome for d in defs2)


# 28. expression combination

def test_expression_combination():
    e1 = RigExpression("olhos_fechados",
                       {"olho_esquerdo": {"opacidade": 0.1}})
    e2 = RigExpression("sorriso", {"boca": {"escala": (1.2, 1.0)}})
    fundida = e1.combinar(e2)
    assert fundida.nome == "olhos_fechados+sorriso"
    assert set(fundida.ajustes) == {"olho_esquerdo", "boca"}
    rig = rig_juh()
    rig.adicionar_expressao(fundida)
    perso = rig_para_personagem(rig, "Juh")
    assert perso.aplicar_pose("olhos_fechados+sorriso",
                              []) == ["boca", "olho_esquerdo"]


# 29. multiple views

def test_multiple_views():
    rig = rig_juh()
    for vista in ("frente", "costas", "esquerda", "direita"):
        rig.adicionar_view(RigView(vista,
                                   imagem_ref=f"juh_{vista}.png"))
    assert len(rig._views) == 4
    with pytest.raises(ErroELiXX):
        rig.adicionar_view(RigView("frente"))  # duplicada


# 30. missing views ( honestas: só as declaradas existem)

def test_missing_views():
    rig = rig_juh()
    assert rig._views == {}
    rig.adicionar_view(RigView("frente"))
    assert "costas" not in rig._views  # não fingida


# 31. incomplete body (partes opcionais)

def test_incomplete_body():
    ana = MockCharacterAnalyzer([
        {"id": "cabeca", "tipo": "cabeca"},
        {"id": "tronco", "tipo": "tronco"},
    ]).analisar()
    rig = construir_rig(ana)
    assert "cabeca" in rig and "tronco" in rig
    assert rig.validar()["valido"] is True
    perso = rig_para_personagem(rig, "Parcial")
    assert set(perso.partes) >= {"cabeca", "tronco"}


# 32. hidden parts warnings

def test_hidden_warnings():
    ana = MockCharacterAnalyzer([
        {"id": "braco_d", "tipo": "braco_direito",
         "visibilidade": "parcial"},
        {"id": "perna_e", "tipo": "perna_esquerda",
         "visibilidade": "oculta"},
    ]).analisar()
    codigos = [a["codigo"] for a in ana.avisos]
    assert "parte_parcial" in codigos and "parte_oculta" in codigos
    rig = construir_rig(ana)
    assert any(a["codigo"] in ("parte_parcial", "parte_oculta")
               for a in rig.avisos)


# 33. deterministic output

def test_deterministic():
    a = construir_rig(analise_juh(), rig_id="j").to_json()
    b = construir_rig(analise_juh(), rig_id="j").to_json()
    assert a == b


# 34. repeated analysis (mesma entrada, mesmo rig)

def test_repeated():
    prov = MockCharacterAnalyzer(deteccoes_juh())
    r1 = construir_rig(prov.analisar(), rig_id="x").to_json()
    r2 = construir_rig(prov.analisar(), rig_id="x").to_json()
    assert r1 == r2


# 35-36. 100 / 1000 parts stress + medidas

def test_stress():
    for total, teto in ((100, 30.0), (1000, 30.0)):
        # Hierarquia rasa (teto de 32 níveis testado em
        # test_depth_limit; stress mede volume, não profundidade).
        dets = [{"id": f"p{i:04d}", "tipo": "acessorio",
                 "bounds": {"x": float(i), "y": 0.0,
                            "largura": 1.0, "altura": 1.0}}
                for i in range(total)]
        t0 = time.perf_counter()
        ana = MockCharacterAnalyzer(dets).analisar()
        t_ana = time.perf_counter()
        rig = construir_rig(ana, rig_id="s")
        t_rig = time.perf_counter()
        assert rig.validar()["valido"] is True
        texto = rig.to_json()
        t_ser = time.perf_counter()
        perso = rig_para_personagem(rig, "Stress")
        t_f12 = time.perf_counter()
        assert len(perso.partes) == total + 1  # + raiz "corpo"
        assert (t_f12 - t0) < teto
        if total == 1000:
            print(f"\n1000 partes: ana={t_ana - t0:.2f}s "
                  f"rig={t_rig - t_ana:.2f}s ser={t_ser - t_rig:.2f}s "
                  f"f12={t_f12 - t_ser:.2f}s json={len(texto)} chars")


# 37. invalid masks

def test_invalid_masks():
    with pytest.raises(ErroELiXX):
        CharacterMask("m", "p", kind="voxel")
    with pytest.raises(ErroELiXX):
        CharacterMask("m", "p", kind="poligono",
                      pontos=[{"x": 0, "y": 0}])
    with pytest.raises(ErroELiXX):
        CharacterMask("m", "p", pontos=["nao-ponto"])
    rig = rig_juh()
    with pytest.raises(ErroELiXX):
        rig.adicionar_mascara(CharacterMask("x", "fantasma"))


# 38. invalid pivots

def test_invalid_pivots():
    with pytest.raises(ErroELiXX):
        RigPart("a", pivot_x=float("nan"))
    with pytest.raises(ErroELiXX):
        RigJoint("j", "a", "b", pivot_unidade_y="graus")
    with pytest.raises(ErroELiXX):
        RigPart("a", pivot_y=1e18)


# 39. invalid joints

def test_invalid_joints():
    with pytest.raises(ErroELiXX):
        RigJoint("j", "a", "b", tipo="mola_quantica")
    with pytest.raises(ErroELiXX):
        RigPart("a", joint="nao-joint")


# 40. regression F01–F22 (amostra: F12/F21/F22 intactos)

def test_regressao():
    from elixx.visual.geometria import GeometryMap, GeometryNode
    from elixx.visual.percepcao import MockPerceptionProvider
    from elixx.visual.personagem import Character, Pose

    mapa = GeometryMap("m")
    mapa.adicionar(GeometryNode("n", Bounds2D(1, 2, 3, 4)))
    assert mapa.validar()["valido"] is True
    res = MockPerceptionProvider(
        [{"id": "o", "x": 1, "y": 2, "largura": 3,
          "altura": 4}]).analisar()
    assert len(res) == 1
    assert Pose("p", entradas={}).partes() == []
    import elixx.visual.personagem as f12
    import elixx.visual.percepcao as f22

    assert "rigging" not in open(f12.__file__,
                                 encoding="utf-8").read()
    assert "rigging" not in open(f22.__file__,
                                 encoding="utf-8").read()


# 41. automáticas (definição estruturada; motor executa)

def rig_completo():
    """Rig com todas as partes das automáticas (tronco, olhos, ...)."""
    ana = MockCharacterAnalyzer([
        {"id": p, "tipo": p} for p in
        ("tronco", "olhos", "cabeca", "boca", "braco_direito",
         "perna_esquerda", "perna_direita", "cabelo")] ).analisar()
    return construir_rig(ana, rig_id="full")


def test_automaticas():
    rig = rig_completo()
    for nome in ("respirar", "piscar", "olhar", "falar", "acenar",
                 "andar", "balancar_cabelo"):
        gesto = definir_automatica(rig, nome)
        assert gesto.nome == nome and len(gesto.passos) >= 1
    # rig incompleto: passos sem alvo viram aviso, nunca erro
    parcial_rig = rig_juh()
    parcial = definir_automatica(parcial_rig, "piscar")  # sem "olhos"
    assert parcial.passos == []
    assert any(a["codigo"] == "automatica_parcial"
               for a in parcial_rig.avisos)
    with pytest.raises(ErroELiXX):
        definir_automatica(rig, "teletransportar")
    assert set(AUTOMATICAS) >= {"respirar", "piscar", "olhar",
                                "falar", "andar"}


# 42. F22 → análise (conveniência, sem obrigar F22)

def test_f22_para_analise():
    from elixx.visual.percepcao import MockPerceptionProvider

    res = MockPerceptionProvider(
        [{"id": "cab", "classe": "cabeca", "x": 0, "y": 0,
          "largura": 10, "altura": 10, "confianca": 0.9}]).analisar()
    ana = analise_de_percepcao(res)
    assert ana.por_id("cab").tipo == "cabeca"
    assert ana.origem == "percepcao"
    rig = construir_rig(ana)
    assert "cab" in rig


# 43. sem sistemas paralelos

def test_sem_paralelos():
    import elixx.visual.rigging as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("class Character(", "class Pose",
                     "class Bounds2D", "class Vector2", "torch",
                     "mediapipe", "cv2", "ultralytics", "PIL",
                     "selenium", "playwright"):
        assert proibido not in fonte, proibido


# 44. segurança (sem execução dinâmica)

def test_seguranca():
    import elixx.visual.rigging as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("eval(", "exec(", "compile(", "__import__",
                     "importlib", "subprocess", "os.system",
                     "requests", "urlopen", "socket"):
        assert proibido not in fonte, proibido


# 45. debug legível

def test_debug():
    texto = debug_rigging(rig_juh())
    for trecho in ("CharacterRig juh", "HIERARQUIA:", "cabeca",
                   "pivo=", "tronco"):
        assert trecho in texto, trecho
    assert "CharacterAnalysis" in debug_rigging(analise_juh())
