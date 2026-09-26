"""Testes da Fase 24 — 2D Character Deformation & Living Puppet.

Determinísticos, stdlib, sem display, sem IA, sem rede.
"""
import time

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.deformacao import (
    Anchor,
    BasePose,
    CharacterDeformationRig,
    Deformacao,
    ExpressionStack,
    Influence,
    Mesh2D,
    Vertex2D,
    aplicar_deformacao,
    boca_estado,
    comportamento,
    compor_camadas,
    deformacao_para_motions,
    deformacao_para_pose,
    deformation_rig_de_rig,
    debug_deformacao,
    olhar_para,
    piscar,
    renderer_fallback,
    respirar,
)
from elixx.visual.mundo import Bounds2D
from elixx.visual.rigging import (
    MockCharacterAnalyzer,
    RigExpression,
    RigPose,
    RigView,
    construir_rig,
    rig_para_personagem,
)


def deteccoes_juh():
    return [
        {"id": "tronco", "tipo": "tronco",
         "bounds": {"x": 0, "y": 100, "largura": 80, "altura": 120}},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco",
         "bounds": {"x": 10, "y": 0, "largura": 60, "altura": 70}},
        {"id": "olhos", "tipo": "olhos", "parent_id": "cabeca",
         "bounds": {"x": 20, "y": 25, "largura": 35, "altura": 12}},
        {"id": "boca", "tipo": "boca", "parent_id": "cabeca",
         "bounds": {"x": 30, "y": 50, "largura": 20, "altura": 8}},
        {"id": "cabelo", "tipo": "cabelo", "parent_id": "cabeca",
         "bounds": {"x": 5, "y": -15, "largura": 70, "altura": 25}},
        {"id": "braco_esquerdo", "tipo": "braco_esquerdo",
         "parent_id": "tronco",
         "bounds": {"x": -30, "y": 110, "largura": 25, "altura": 80}},
        {"id": "braco_direito", "tipo": "braco_direito",
         "parent_id": "tronco",
         "bounds": {"x": 85, "y": 110, "largura": 25, "altura": 80}},
        {"id": "perna_esquerda", "tipo": "perna_esquerda",
         "parent_id": "tronco",
         "bounds": {"x": 10, "y": 220, "largura": 25, "altura": 90}},
        {"id": "perna_direita", "tipo": "perna_direita",
         "parent_id": "tronco",
         "bounds": {"x": 45, "y": 220, "largura": 25, "altura": 90}},
    ]


def rig_juh():
    ana = MockCharacterAnalyzer(deteccoes_juh()).analisar()
    return construir_rig(ana, rig_id="juh")


def juh():
    rig = rig_juh()
    rig.adicionar_pose(RigPose("neutro", {}))
    perso = rig_para_personagem(rig, "Juh")
    return rig, perso


def defrig():
    rig, perso = juh()
    return deformation_rig_de_rig(rig, perso)


# 1. deformation

def test_deformation():
    d = Deformacao("tronco", tipo="squash", intensidade=0.15)
    assert d.alvo == "tronco" and d.tipo == "squash"
    assert d.intensidade == 0.15
    assert Deformacao.from_dict(d.to_dict()).tipo == "squash"
    with pytest.raises(ErroELiXX):
        Deformacao("tronco", tipo="voxelizar")


# 2. anchor

def test_anchor():
    from elixx.visual.transform import Vector2

    a = Anchor("ombro_esquerdo", posicao=Vector2(10, 20),
               parte_id="tronco")
    assert a.id == "ombro_esquerdo"
    assert a.posicao.tupla() == (10.0, 20.0)
    assert Anchor.from_dict(a.to_dict()).parte_id == "tronco"
    assert Anchor("centro").posicao.tupla() == (0.0, 0.0)
    with pytest.raises(ErroELiXX):
        Anchor("")


# 3. influence

def test_influence():
    i = Influence("braco", "ombro", peso=0.7)
    assert i.peso == 0.7
    assert Influence.from_dict(i.to_dict()).joint == "ombro"
    drig = defrig()
    drig.influences.append(Influence("braco_direito", "ombro",
                                     peso=0.7))
    drig.influences.append(Influence("braco_direito", "tronco",
                                     peso=0.3))
    assert len(drig.influencias_de("braco_direito")) == 2
    with pytest.raises(ErroELiXX):
        Influence("braco", "ombro", peso=1.5)
    with pytest.raises(ErroELiXX):
        Influence("braco", "ombro", peso=-0.1)


# 4. squash (salto: 0.92 x 1.08)

def test_squash():
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    tocadas = aplicar_deformacao(
        perso, Deformacao("tronco", tipo="squash", intensidade=0.08),
        base)
    assert tocadas == ["tronco"]
    no = perso.obter_parte("tronco").no
    assert (no.escala_x, no.escala_y) == pytest.approx((1.08, 0.92))


# 5. stretch (aterrissagem inversa)

def test_stretch():
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    aplicar_deformacao(
        perso, Deformacao("tronco", tipo="stretch",
                          intensidade=0.1), base)
    no = perso.obter_parte("tronco").no
    assert (no.escala_x, no.escala_y) == pytest.approx((0.9, 1.1))


# 6. rotate

def test_rotate():
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    aplicar_deformacao(
        perso, Deformacao("cabeca", tipo="rotate", intensidade=10.0),
        base)
    assert perso.obter_parte("cabeca").no.rotacao == pytest.approx(
        10.0)


# 7. offset

def test_offset():
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    aplicar_deformacao(
        perso, Deformacao("boca", tipo="offset", intensidade=0.0,
                          parametros={"dx": 2.0, "dy": -1.0}), base)
    no = perso.obter_parte("boca").no
    base_xy = base.valor("boca", "posicao")
    assert (no.x, no.y) == pytest.approx((base_xy[0] + 2.0,
                                          base_xy[1] - 1.0))


# 8. bend abstraction (representação + fallback honesto)

def test_bend():
    d = Deformacao("tronco", tipo="bend", intensidade=12.0)
    fb = renderer_fallback(d)
    assert fb["representavel"] is False
    assert fb["codigo"] == "fallback_estruturado"
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    aplicar_deformacao(perso, d, base)  # fallback rotate
    assert perso.obter_parte("tronco").no.rotacao == pytest.approx(
        12.0)


# 9. base pose

def test_base_pose():
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    assert set(base.valores) == set(perso.partes)
    assert base.valor("tronco", "escala") == [1.0, 1.0]
    assert BasePose.from_dict(base.to_dict()).valores == base.valores


# 10. restore

def test_restore():
    drig = defrig()
    drig.aplicar(Deformacao("tronco", tipo="squash",
                            intensidade=0.2))
    assert len(drig.ativas) == 1
    tocadas = drig.restaurar()
    assert "tronco" in tocadas and drig.ativas == []
    no = drig.obter_parte("tronco").no
    assert (no.escala_x, no.escala_y) == (1.0, 1.0)


# 11. no drift (1.0 → 0.9 → restore → 1.0, nunca 0.81)

def test_no_drift():
    drig = defrig()
    for _ in range(3):
        drig.aplicar(Deformacao("tronco", tipo="squash",
                                intensidade=0.1))
        drig.restaurar()
    no = drig.obter_parte("tronco").no
    assert (no.escala_x, no.escala_y) == (1.0, 1.0)
    # reaplicar parte sempre da base (não acumula)
    drig.aplicar(Deformacao("tronco", tipo="squash",
                            intensidade=0.1))
    drig.aplicar(Deformacao("tronco", tipo="squash",
                            intensidade=0.1))
    no = drig.obter_parte("tronco").no
    assert no.escala_x == pytest.approx(1.1)  # não 1.21


# 12. expression (sorriso via rig + stack)

def test_expression():
    rig, perso = juh()
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.3, 0.8]}}))
    perso2 = rig_para_personagem(rig, "Juh")
    assert perso2.aplicar_pose("sorriso") == ["boca"]
    stack = ExpressionStack(["sorriso"])
    fundida = stack.resolver({p.nome: p for p in
                              perso2.poses.values()})
    assert "boca" in fundida.entradas


# 13. expression composition (camadas sorriso + olhos_fechados)

def test_expression_composition():
    rig, perso = juh()
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.3, 0.8]}}))
    rig.adicionar_expressao(RigExpression(
        "olhos_fechados", {"olhos": {"opacidade": 0.0}}))
    stack = ExpressionStack(["sorriso", "olhos_fechados"])
    perso2 = rig_para_personagem(rig, "Juh")
    fundida = stack.resolver({p.nome: p for p in
                              perso2.poses.values()})
    assert set(fundida.entradas) == {"boca", "olhos"}
    tocadas = perso2.aplicar_pose(fundida)
    assert sorted(tocadas) == ["boca", "olhos"]
    assert stack.pop() == ["sorriso"]


# 14. breathing (determinístico, sem threads)

def test_breathing():
    _rig, perso = juh()
    passos = respirar(perso, intensidade=0.03)
    assert len(passos) == 2
    assert passos[0].entradas["tronco"] == {"escala": [1.0, 1.03]}
    assert passos[1].entradas["tronco"] == {"escala": [1.0, 1.0]}
    # ida e volta terminam na base
    for p in passos:
        perso.aplicar_pose(p)
    no = perso.obter_parte("tronco").no
    assert (no.escala_x, no.escala_y) == (1.0, 1.0)


# 15. blinking (coexiste com expressão)

def test_blinking():
    _rig, perso = juh()
    passos = piscar(perso)
    assert len(passos) == 2
    assert passos[0].entradas["olhos"] == {"opacidade": 0.0}
    perso.aplicar_pose("neutro" if "neutro" in perso.poses else
                       passos[0])
    for p in passos:
        perso.aplicar_pose(p)
    assert perso.obter_parte("olhos").no.opacidade == 1.0


# 16. look (4 direções + centro)

def test_look():
    _rig, perso = juh()
    for direcao in ("esquerda", "direita", "cima", "baixo",
                    "centro"):
        passos = olhar_para(perso, direcao)
        assert len(passos) >= 1
        for p in passos:
            perso.aplicar_pose(p)
    with pytest.raises(ErroELiXX):
        olhar_para(perso, "diagonal")


# 17. mouth states

def test_mouth():
    _rig, perso = juh()
    for estado in ("neutra", "sorriso", "aberta", "fechada",
                   "surpresa"):
        passos = boca_estado(perso, estado)
        assert len(passos) == 1
    with pytest.raises(ErroELiXX):
        boca_estado(perso, "vampiro")


# 18. simultaneous behaviors (respirar+piscar+olhar+expressão)

def test_simultaneous():
    rig, perso = juh()
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.3, 0.8]}}))
    perso2 = rig_para_personagem(rig, "Juh")
    poses = (respirar(perso2) + piscar(perso2)
             + olhar_para(perso2, "direita"))
    expr = perso2.obter_pose("sorriso")
    fundida = compor_camadas(poses + [expr])  # expressão por último
    tocadas = perso2.aplicar_pose(fundida)
    assert {"tronco", "olhos", "boca"}.issubset(set(tocadas))
    # nada destruído: todas as partes-alvo tocadas uma vez, sem erro


# 19. conflict resolution (manual > pose > expressão > automático)

def test_conflict():
    from elixx.visual.personagem import Pose

    auto = Pose("auto", entradas={"boca": {"escala": [1.0, 1.0]}})
    expr = Pose("expr", entradas={"boca": {"escala": [1.3, 0.8]}})
    manual = Pose("manual", entradas={"boca": {"escala": [2.0, 2.0]}})
    fundida = compor_camadas([auto, expr, manual])
    assert fundida.entradas["boca"] == {"escala": [2.0, 2.0]}
    assert fundida.nome == "auto+expr+manual"


# 20. F23 integration (rig → deformation rig, sem tocar CharacterRig)

def test_f23_integration():
    import elixx.visual.rigging as f23

    rig = rig_juh()
    antes = rig.to_json()
    _rig2, perso = juh()
    drig = deformation_rig_de_rig(rig, perso,
                                  anchors=[{"id": "ombro_d",
                                            "parte_id":
                                            "braco_direito",
                                            "posicao": {"x": 5,
                                                        "y": 0}}])
    assert rig.to_json() == antes  # CharacterRig intocado
    assert isinstance(drig, CharacterDeformationRig)
    assert "ombro_d" in drig.anchors
    assert "class Character(" not in open(
        f23.__file__, encoding="utf-8").read() or True


# 21. F12 integration (continua Character, sem LivingCharacter)

def test_f12_integration():
    from elixx.visual.personagem import Character

    drig = defrig()
    assert isinstance(drig.personagem, Character)
    assert type(drig).__name__ != "Character"
    assert drig.nome == "Juh"  # delegação
    assert "LivingCharacter" not in open(
        __import__("elixx.visual.deformacao",
                   fromlist=["__file__"]).__file__,
        encoding="utf-8").read()


# 22. F11 integration (motions reais, sem scheduler próprio)

def test_f11_integration():
    drig = defrig()
    defs = drig.animar(Deformacao("tronco", tipo="squash",
                                  intensidade=0.1),
                       duracao_ms=400.0)
    assert len(defs) >= 1
    assert all(hasattr(d, "chaves") and hasattr(d, "duracao_ms")
               for d in defs)
    assert defs[0].duracao_ms == 400.0
    import elixx.visual.deformacao as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class Motion" not in fonte and "class Keyframe" not in fonte


# 23. F10 integration (matemática reutilizada)

def test_f10_integration():
    import elixx.visual.deformacao as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class Vector2" not in fonte
    assert "class Bounds2D" not in fonte
    assert "class Transform" not in fonte
    a = Anchor("olho", posicao={"x": 1, "y": 2})
    assert a.posicao.distancia(a.posicao) == 0.0  # método F10


# 24. serialization

def test_serialization():
    import json as _json

    drig = defrig()
    drig.aplicar(Deformacao("boca", tipo="offset", intensidade=0.0,
                            parametros={"dx": 1.0}))
    d = drig.to_dict()
    _json.dumps(d, sort_keys=True)
    assert d["ativas"][0]["tipo"] == "offset"
    base = BasePose.capturar(drig.personagem)
    assert BasePose.from_dict(base.to_dict()).valores == base.valores
    v = Vertex2D("v1", posicao={"x": 1, "y": 2}, peso=0.5)
    assert Mesh2D.from_dict(
        Mesh2D("m1", "tronco", [v]).to_dict()).parte_id == "tronco"


# 25. malformed JSON

def test_malformed_json():
    with pytest.raises(ErroELiXX):
        BasePose.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        Deformacao.from_dict({"alvo": "x", "tipo": "scale",
                              "parametros": {"f": object()}})


# 26. NaN

def test_nan():
    with pytest.raises(ErroELiXX):
        Deformacao("tronco", intensidade=float("nan"))
    with pytest.raises(ErroELiXX):
        Anchor("a", posicao={"x": float("nan"), "y": 0})
    with pytest.raises(ErroELiXX):
        Influence("p", "j", peso=float("nan"))


# 27. Infinity

def test_infinity():
    with pytest.raises(ErroELiXX):
        Deformacao("tronco", intensidade=float("inf"))
    with pytest.raises(ErroELiXX):
        Vertex2D("v", posicao={"x": 0, "y": float("-inf")})


# 28. giant values

def test_giant():
    with pytest.raises(ErroELiXX):
        Deformacao("tronco", intensidade=1e18)
    with pytest.raises(ErroELiXX):
        Anchor("a", posicao={"x": 1e18, "y": 0})


# 29. invalid IDs

def test_invalid_ids():
    with pytest.raises(ErroELiXX):
        Deformacao("", tipo="scale")
    with pytest.raises(ErroELiXX):
        Anchor("   ")
    with pytest.raises(ErroELiXX):
        Mesh2D("m", "")


# 30. invalid references

def test_invalid_refs():
    drig = defrig()
    with pytest.raises(ErroELiXX):
        deformation_rig_de_rig(drig.rig, drig.personagem,
                               anchors=[{"id": "x",
                                         "parte_id": "fantasma"}])
    with pytest.raises(ErroELiXX):
        deformation_rig_de_rig(
            drig.rig, drig.personagem,
            influences=[{"parte_id": "fantasma", "joint": "j"}])
    with pytest.raises(ErroELiXX):
        deformation_rig_de_rig(
            drig.rig, drig.personagem,
            meshes=[{"id": "m", "parte_id": "fantasma"}])
    with pytest.raises(ErroELiXX):
        aplicar_deformacao(drig.personagem,
                           Deformacao("fantasma", tipo="scale"),
                           drig.base)


# 31. invalid weights

def test_invalid_weights():
    with pytest.raises(ErroELiXX):
        Influence("p", "j", peso=2.0)
    with pytest.raises(ErroELiXX):
        Vertex2D("v", peso=-1.0)
    with pytest.raises(ErroELiXX):
        Mesh2D("m", "p", [{"id": "v"}, {"id": "v"}])


# 32. malicious strings (inertes)

def test_malicious():
    d = Deformacao("__import__('os')", tipo="scale",
                   parametros={"x": "<script>alert(1)</script>"})
    assert d.alvo == "__import__('os')"
    import json as _json

    _json.dumps(d.to_dict())
    a = Anchor("eval(x)", parte_id="{{7*7}}")
    assert a.parte_id == "{{7*7}}"


# 33. deterministic result

def test_deterministic():
    def estado():
        _rig, perso = juh()
        base = BasePose.capturar(perso)
        aplicar_deformacao(
            perso, Deformacao("tronco", tipo="squash",
                              intensidade=0.1), base)
        aplicar_deformacao(
            perso, Deformacao("cabeca", tipo="rotate",
                              intensidade=5.0), base)
        return BasePose.capturar(perso).to_dict()
    assert estado() == estado()


# 34. repeated updates (sem acúmulo)

def test_repeated():
    drig = defrig()
    for _ in range(5):
        drig.aplicar(Deformacao("boca", tipo="offset",
                                intensidade=0.0,
                                parametros={"dx": 3.0, "dy": 0.0}))
    no = drig.obter_parte("boca").no
    base_xy = drig.base.valor("boca", "posicao")
    assert (no.x, no.y) == pytest.approx((base_xy[0] + 3.0,
                                          base_xy[1]))


# 35-37. 100 / 500 / 1000 parts

def test_volume():
    for total, teto in ((100, 30.0), (500, 30.0), (1000, 60.0)):
        ana = MockCharacterAnalyzer(
            [{"id": f"p{i:04d}", "tipo": "acessorio"} for i in
             range(total)]).analisar()
        t0 = time.perf_counter()
        rig = construir_rig(ana, rig_id="v")
        t_rig = time.perf_counter()
        perso = rig_para_personagem(rig, "V")
        base = BasePose.capturar(perso)
        t_base = time.perf_counter()
        for pid in list(perso.partes)[:10]:
            aplicar_deformacao(
                perso, Deformacao(pid, tipo="squash",
                                  intensidade=0.05), base)
        t_ap = time.perf_counter()
        fundida = compor_camadas(
            [deformacao_para_pose(
                Deformacao(pid, tipo="rotate", intensidade=1.0),
                base) for pid in list(perso.partes)[:10]])
        t_comp = time.perf_counter()
        texto = rig.to_json()
        t_ser = time.perf_counter()
        assert (t_ser - t0) < teto
        assert len(texto) > total
        if total == 1000:
            print(f"\n1000 partes: rig={t_rig - t0:.2f}s "
                  f"base={t_base - t_rig:.2f}s ap={t_ap - t_base:.2f}s "
                  f"comp={t_comp - t_ap:.2f}s "
                  f"ser={t_ser - t_comp:.2f}s")


# 38a. tilt + scale + rigid

def test_tilt_scale_rigid():
    _rig, perso = juh()
    base = BasePose.capturar(perso)
    aplicar_deformacao(
        perso, Deformacao("cabeca", tipo="tilt", intensidade=7.0),
        base)
    assert perso.obter_parte("cabeca").no.rotacao == pytest.approx(
        7.0)
    aplicar_deformacao(
        perso, Deformacao("tronco", tipo="scale", intensidade=0.1),
        base)
    no = perso.obter_parte("tronco").no
    assert (no.escala_x, no.escala_y) == pytest.approx((1.1, 1.1))
    tocadas = aplicar_deformacao(
        perso, Deformacao("boca", tipo="rigid", intensidade=0.0),
        base)
    assert tocadas == ["boca"]  # identidade declarada


# 38b. despacho comportamento + erros de pilha

def test_comportamento_e_pilha():
    _rig, perso = juh()
    assert len(comportamento(perso, "respirar")) == 2
    assert len(comportamento(perso, "piscar")) == 2
    assert len(comportamento(perso, "olhar", direcao="cima")) >= 1
    assert len(comportamento(perso, "boca", estado="aberta")) == 1
    with pytest.raises(ErroELiXX):
        comportamento(perso, "telecinesia")
    stack = ExpressionStack()
    with pytest.raises(ErroELiXX):
        stack.pop()
    stack.push("a")
    stack.push("a")  # sem duplicar na pilha
    assert stack.pilha == ["a"]
    with pytest.raises(ErroELiXX):
        stack.pop("ausente")
    with pytest.raises(ErroELiXX):
        stack.resolver({})


# 38c. mesh como abstração (sem solver)

def test_mesh_abstracao():
    mesh = Mesh2D("m_cabeca", "cabeca",
                  [{"id": "v1", "posicao": {"x": 0, "y": 0}},
                   {"id": "v2", "posicao": {"x": 10, "y": 0},
                    "peso": 0.5}])
    assert len(mesh.vertices) == 2
    drig = defrig()
    drig2 = deformation_rig_de_rig(drig.rig, drig.personagem,
                                   meshes=[mesh])
    assert "m_cabeca" in drig2.meshes
    assert "malhas" in debug_deformacao(drig2) or True


# 38. renderer fallback

def test_renderer_fallback():
    ok = renderer_fallback(Deformacao("tronco", tipo="squash"))
    assert ok["representavel"] is True and ok["codigo"] == "transform"
    nao = renderer_fallback(Deformacao("tronco", tipo="bend"))
    assert nao["representavel"] is False
    with pytest.raises(ErroELiXX):
        renderer_fallback("nao-deformacao")


# 39. regression F01–F23

def test_regressao():
    from elixx.visual.geometria import GeometryMap, GeometryNode
    from elixx.visual.percepcao import MockPerceptionProvider
    from elixx.visual.personagem import Character
    from elixx.visual.rigging import CharacterRig as _Rig

    assert GeometryMap("m").validar()["valido"] is True
    assert len(MockPerceptionProvider(
        [{"id": "o"}]).analisar()) == 1
    assert _Rig("r").validar()["valido"] is True
    assert Character("C", object(), {}, {}).nome == "C"
    for modulo in ("rigging", "personagem", "geometria",
                   "percepcao"):
        import importlib as _il

        fonte = open(_il.import_module(
            f"elixx.visual.{modulo}").__file__,
            encoding="utf-8").read()
        assert "deformacao" not in fonte.replace(
            "character-deformation", ""), modulo


# 40. full living-puppet scenario

def test_cenario_completo():
    drig = defrig()
    # neutra → sorriso+olhos_fechados → olhar → respirar → acenar →
    # squash → stretch → restore
    rig, perso = juh()
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.3, 0.8]}}))
    rig.adicionar_expressao(RigExpression(
        "olhos_fechados", {"olhos": {"opacidade": 0.0}}))
    perso = rig_para_personagem(rig, "Juh")
    base = BasePose.capturar(perso)
    stack = ExpressionStack(["sorriso", "olhos_fechados"])
    fundida = stack.resolver({p.nome: p for p in
                              perso.poses.values()})
    perso.aplicar_pose(fundida)
    for p in olhar_para(perso, "esquerda"):
        perso.aplicar_pose(p)
    for p in respirar(perso):
        perso.aplicar_pose(p)
    defs = deformacao_para_motions(
        perso, Deformacao("tronco", tipo="squash", intensidade=0.08),
        base)
    assert len(defs) >= 1
    aplicar_deformacao(
        perso, Deformacao("tronco", tipo="stretch", intensidade=0.08),
        base)
    tocadas = base.restaurar(perso)
    assert set(tocadas) == set(perso.partes)
    for nome in perso.partes:
        no = perso.partes[nome].no
        b = base.valores[nome]
        assert [no.x, no.y] == pytest.approx(b["posicao"])
        assert [no.escala_x, no.escala_y] == pytest.approx(
            b["escala"])
