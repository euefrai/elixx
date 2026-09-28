"""Fase 41 (asset runtime) — imagem -> personagem animavel.

Cobre: AssetVisual, CharacterAsset (vistas/aliases/diagnose),
View/Layer/Part/Rig, unidade, respiracao/inclinacao/
deslocamento, renderer existente, integracoes F07/F10/F11/
F12/F16/F17, seguranca, performance. Headless (sem display);
prova visual no demo --visual. Sem Studio.
"""

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.asset_personagem import (
    ALIASES_VISTA,
    EXTENSOES_IMAGEM,
    VISTAS,
    AssetVisual,
    CharacterAsset,
    CharacterLayer,
    CharacterPart,
    CharacterRig,
    CharacterView,
    animacao_deslocamento,
    animacao_inclinacao,
    animacao_respiracao,
    criar_personagem_unidade,
    dimensoes_imagem,
    resolver_vista,
)

BASE = "exemplos"
PASTA = "assets/personagem_teste"
ARQUIVO = f"{PASTA}/personagem.png"


def _png_bytes(larg=8, alt=6):
    import struct
    import zlib

    cab = struct.pack(">IIBBBBB", larg, alt, 8, 6, 0, 0, 0)

    def chunk(tipo, dados):
        c = struct.pack(">I", len(dados)) + tipo + dados
        return c + struct.pack(">I", zlib.crc32(tipo + dados))

    linha = b"\x00" + bytes((1, 2, 3, 255)) * larg
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", cab)
            + chunk(b"IDAT", zlib.compress(linha * alt, 9))
            + chunk(b"IEND", b""))


# ---------- AssetVisual: arquivo ----------


def test_asset_real_existe():
    a = AssetVisual(ARQUIVO, BASE)
    assert a.existe() is True
    assert a.tamanho() > 0


def test_asset_inexistente():
    a = AssetVisual(f"{PASTA}/fantasma.png", BASE)
    assert a.existe() is False
    assert a.to_dict()["existe"] is False
    with pytest.raises(ErroELiXX):
        a.tamanho()


def test_asset_extensao():
    with pytest.raises(ErroELiXX):
        AssetVisual(f"{PASTA}/x.bmp", BASE)
    with pytest.raises(ErroELiXX):
        AssetVisual(f"{PASTA}/x.txt", BASE)


def test_asset_extensoes_suportadas():
    assert set(EXTENSOES_IMAGEM) == {".png", ".gif", ".jpg",
                                     ".jpeg"}


def test_asset_dimensoes_reais():
    a = AssetVisual(ARQUIVO, BASE)
    assert a.dimensoes() == (128, 160)


def test_asset_metadados():
    meta = AssetVisual(ARQUIVO, BASE).metadados()
    assert meta["tipo"] == "png"
    assert meta["largura"] == 128
    assert meta["origem"] == BASE


def test_asset_bytes_lazy():
    a = AssetVisual(ARQUIVO, BASE)
    dados = a.bytes()
    assert dados[:8] == b"\x89PNG\r\n\x1a\n"


def test_asset_repr():
    assert "personagem.png" in repr(
        AssetVisual(ARQUIVO, BASE))


# ---------- dimensoes stdlib ----------


def test_dim_png():
    assert dimensoes_imagem(_png_bytes(8, 6), "png") == (8, 6)


def test_dim_gif():
    dados = (b"GIF89a" + bytes((7, 0, 5, 0)) + bytes(20))
    assert dimensoes_imagem(dados, "gif") == (7, 5)


def test_dim_jpeg():
    import struct

    sof = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(9)
           + b"\xff\xc0\x00\x0b\x08"
           + struct.pack(">HH", 11, 9) + b"\x01\x01\x11\x00")
    assert dimensoes_imagem(sof, "jpg") == (9, 11)


def test_dim_vazio():
    with pytest.raises(ErroELiXX):
        dimensoes_imagem(b"", "png")


def test_dim_formato_invalido():
    with pytest.raises(ErroELiXX):
        dimensoes_imagem(b"xxxx", "bmp")


def test_dim_ilegivel():
    with pytest.raises(ErroELiXX):
        dimensoes_imagem(b"nao-imagem" * 10, "png")


# ---------- seguranca asset ----------


def test_traversal():
    with pytest.raises(ErroELiXX):
        AssetVisual("../../x.png", BASE)
    with pytest.raises(ErroELiXX):
        AssetVisual("a/../b.png", BASE)


def test_absoluto_proibido():
    with pytest.raises(ErroELiXX):
        AssetVisual("C:/x/y.png", BASE)


def test_absoluto_dentro_com_permissao(tmp_path):
    alvo = tmp_path / "i.png"
    alvo.write_bytes(_png_bytes())
    a = AssetVisual("i.png", str(tmp_path))
    assert a.existe() is True


def test_nul_e_controle():
    with pytest.raises(ErroELiXX):
        AssetVisual("a\x00.png", BASE)
    with pytest.raises(ErroELiXX):
        AssetVisual("", BASE)
    with pytest.raises(ErroELiXX):
        AssetVisual("x" * 600, BASE)


def test_scan_modulo():
    from pathlib import Path as _P

    fonte = _P("elixx/visual/asset_personagem.py"
               ).read_text(encoding="utf-8")
    for proibido in ("eval(", "exec(", "__import__",
                     "importlib", "pickle", "subprocess",
                     "os.system", "shell", "requests"):
        assert proibido not in fonte, proibido


def test_strings_maliciosas_inertes():
    for ruim in ("__import__('os')", "eval(1)",
                 "import os\nos.system(1)"):
        with pytest.raises(ErroELiXX):
            AssetVisual(ruim, BASE)


def test_nan_infinito():
    with pytest.raises(ErroELiXX):
        animacao_respiracao("J", float("nan"))
    with pytest.raises(ErroELiXX):
        animacao_inclinacao("J", float("inf"))


# ---------- vistas / aliases ----------


def test_quatro_vistas():
    assert tuple(VISTAS) == ("frente", "tras",
                             "lado_direito",
                             "lado_esquerdo")


def test_aliases():
    assert resolver_vista("direita") == "lado_direito"
    assert resolver_vista("esquerda") == "lado_esquerdo"
    assert resolver_vista("costas") == "tras"
    assert resolver_vista("frente") == "frente"
    assert "lado_direito" in ALIASES_VISTA


def test_vista_desconhecida():
    with pytest.raises(ErroELiXX):
        resolver_vista("lado")
    with pytest.raises(ErroELiXX):
        resolver_vista("cima")


# ---------- CharacterAsset ----------


def test_uma_vista_incompleto():
    c = CharacterAsset("Juh", PASTA, BASE)
    diag = c.diagnosticar()
    assert diag["estado"] == "INCOMPLETO"
    assert diag["vistas"]["frente"] == "AUSENTE"


def test_usar_como_explicito():
    c = CharacterAsset("Juh", PASTA, BASE)
    c.usar_como("frente", "personagem.png")
    diag = c.diagnosticar()
    assert diag["vistas"]["frente"] == "OK"
    assert diag["estado"] == "INCOMPLETO"
    assert diag["experimental"] == ["frente"]


def test_usar_como_ausente():
    c = CharacterAsset("Juh", PASTA, BASE)
    with pytest.raises(ErroELiXX):
        c.usar_como("frente", "nada.png")


def test_quatro_vistas_completo(tmp_path):
    from PIL import Image

    for vista in VISTAS:
        Image.new("RGBA", (4, 4)).save(
            tmp_path / f"{vista}.png")
    c = CharacterAsset("T", ".", str(tmp_path))
    assert c.diagnosticar()["estado"] == "COMPLETO"


def test_vista_asset():
    c = CharacterAsset("Juh", PASTA, BASE)
    c.usar_como("frente", "personagem.png")
    a = c.vista("direita") if False else c.vista("frente")
    assert a.dimensoes() == (128, 160)


def test_vista_ausente_erro():
    c = CharacterAsset("Juh", PASTA, BASE)
    with pytest.raises(ErroELiXX):
        c.vista("tras")


def test_nome_invalido():
    with pytest.raises(ErroELiXX):
        CharacterAsset("", PASTA, BASE)
    with pytest.raises(ErroELiXX):
        CharacterAsset("a/b", PASTA, BASE)


# ---------- View/Layer/Part/Rig ----------


def test_view():
    v = CharacterView("frente",
                      AssetVisual(ARQUIVO, BASE))
    assert v.to_dict()["vista"] == "frente"
    with pytest.raises(ErroELiXX):
        CharacterView("frente", object())


def test_layer():
    camada = CharacterLayer("corpo", 1)
    assert camada.to_dict() == {"layer": "corpo", "ordem": 1}
    with pytest.raises(ErroELiXX):
        CharacterLayer("", 0)


def test_part():
    parte = CharacterPart("braco")
    assert parte.to_dict()["parte"] == "braco"
    with pytest.raises(ErroELiXX):
        CharacterPart("x", vista=object())


def test_rig_unidade():
    from elixx.visual.personagem import Character

    ch = Character("J", None, {}, {})
    rig = CharacterRig(ch)
    assert rig.metodo == "unidade"
    assert rig.to_dict()["personagem"] == "J"


def test_rig_futuro_honesto():
    from elixx.visual.personagem import Character

    with pytest.raises(ErroELiXX):
        CharacterRig(Character("J", None, {}, {}),
                     "bones_ik")


def test_rig_tipo():
    with pytest.raises(ErroELiXX):
        CharacterRig(object())


# ---------- unidade ----------


def test_unidade():
    c = CharacterAsset("Juh", PASTA, BASE)
    c.usar_como("frente", "personagem.png")
    no, ch, rig = criar_personagem_unidade(c, "frente",
                                           10.0, 20.0)
    assert no.tipo == "personagem"
    assert (no.x, no.y) == (10.0, 20.0)
    assert (no.largura, no.altura) == (128.0, 160.0)
    assert no.caminho_recurso.endswith("personagem.png")
    assert ch.direcao == "frente"
    assert rig.metodo == "unidade"


def test_unidade_sem_vista():
    c = CharacterAsset("Juh", PASTA, BASE)
    with pytest.raises(ErroELiXX):
        criar_personagem_unidade(c, "tras")


def test_unidade_direcao():
    c = CharacterAsset("Juh", PASTA, BASE)
    c.usar_como("frente", "personagem.png")
    _, ch, _ = criar_personagem_unidade(c, "frente")
    assert ch.definir_direcao("frente")


def test_unidade_limites():
    assert "braco independente" not in str(
        criar_personagem_unidade.__doc__ or "")


# ---------- animacoes ----------


def test_respiracao_def():
    d = animacao_respiracao("Juh")
    assert d.nome == "respirar" and d.alvo == "Juh"
    assert d.chaves[0].propriedade == "escala"
    assert d.repetir == "infinito" and d.modo == "ping_pong"


def test_respiracao_amplitude():
    with pytest.raises(ErroELiXX):
        animacao_respiracao("J", 0.0)
    with pytest.raises(ErroELiXX):
        animacao_respiracao("J", 0.99)


def test_inclinacao_def():
    d = animacao_inclinacao("Juh", 6.0)
    assert d.chaves[0].propriedade == "rotacao"
    with pytest.raises(ErroELiXX):
        animacao_inclinacao("J", 90.0)


def test_deslocamento_def():
    d = animacao_deslocamento("Juh", (10.0, 20.0), 40.0)
    assert d.chaves[0].propriedade == "posicao"
    assert d.chaves[0].para == (50.0, 20.0)
    with pytest.raises(ErroELiXX):
        animacao_deslocamento("J", "nada")


def test_duracao_limites():
    with pytest.raises(ErroELiXX):
        animacao_respiracao("J", 0.04, 0.0)
    with pytest.raises(ErroELiXX):
        animacao_respiracao("J", 0.04, 99999.0)


# ---------- motor headless ----------


def _cena_unidade():
    from elixx.visual.cena import Cena, NoVisual

    c = CharacterAsset("Juh", PASTA, BASE)
    c.usar_como("frente", "personagem.png")
    no, _, _ = criar_personagem_unidade(c)
    raiz = NoVisual(tipo="janela", nome="palco",
                    largura=800.0, altura=600.0)
    raiz.adicionar(no)
    no.nome = "Juh"
    return Cena(janelas=[raiz]), no


def test_motor_respira():
    from elixx.animacao.motor import MotorAnimacoes

    cena, no = _cena_unidade()
    motor = MotorAnimacoes()
    motor.carregar([animacao_respiracao("Juh")], cena)
    motor.iniciar("respirar")
    for _ in range(12):
        motor.atualizar(100.0)
    assert no.escala > 1.0


def test_motor_inclina():
    from elixx.animacao.motor import MotorAnimacoes

    cena, no = _cena_unidade()
    motor = MotorAnimacoes()
    motor.carregar([animacao_inclinacao("Juh")], cena)
    motor.iniciar("inclinar")
    for _ in range(9):
        motor.atualizar(100.0)
    assert no.rotacao != 0.0


def test_motor_desloca():
    from elixx.animacao.motor import MotorAnimacoes

    cena, no = _cena_unidade()
    motor = MotorAnimacoes()
    motor.carregar([animacao_deslocamento("Juh", (0.0, 0.0))],
                   cena)
    motor.iniciar("deslocar")
    for _ in range(8):
        motor.atualizar(100.0)
    assert no.x > 0.0


def test_motor_stop_cancel_reset():
    from elixx.animacao.motor import MotorAnimacoes

    cena, no = _cena_unidade()
    motor = MotorAnimacoes()
    motor.carregar([animacao_respiracao("Juh")], cena)
    motor.iniciar("respirar")
    motor.pausar("respirar")
    motor.continuar("respirar")
    motor.atualizar(100.0)
    motor.cancelar("respirar")
    assert motor.execucoes["respirar"].estado == "cancelada"


# ---------- integracoes ----------


def test_f07_tipos():
    from elixx.multimidia.recursos import GerenciadorRecursos

    assert GerenciadorRecursos(".") is not None


def test_f10_transform():
    from elixx.visual.transform import Transform, combinar

    t = combinar(Transform(x=5), Transform(y=7))
    assert (t.x, t.y) == (5.0, 7.0)


def test_f11_motor():
    from elixx.animacao.motor import MotorAnimacoes

    assert MotorAnimacoes() is not None


def test_f12_character():
    from elixx.visual.personagem import Character

    assert Character("J", None, {}, {}).direcao == "frente"


def test_f16_sintese():
    from elixx.visual.sintese_movimento import MotionSynthesizer

    assert MotionSynthesizer() is not None


def test_f17_comportamento():
    from elixx.visual.deformacao import respirar
    from elixx.visual.personagem import Character

    assert respirar(Character("J", None, {}, {})) == []
    from elixx.studio.inspetor import fluxo_personagem

    _, ch, _ = fluxo_personagem("J", {"parts": [{"id": "t"}]},
                                analyzer="structured")
    assert respirar(ch, 0.03)


def test_elixx_personagem_imagem():
    from elixx.compilador.lexer import tokenizar
    from elixx.compilador.parser import Parser
    from elixx.compilador.semantica import validar

    src = ('janela p {\n personagem Juh {\n'
           '  imagem: "personagem.png"\n }\n}\n')
    validar(Parser(tokenizar(src)).parse())


def test_elixx_animacao_blocos():
    from elixx.compilador.lexer import tokenizar
    from elixx.compilador.parser import Parser
    from elixx.compilador.semantica import validar

    texto = open("exemplos/character-image-animation.elixx",
                 encoding="utf-8").read()
    validar(Parser(tokenizar(texto)).parse())


def test_cli_verificar():
    from elixx.cli import cmd_verificar

    class _A:
        arquivo = "exemplos/character-image-animation.elixx"

    assert cmd_verificar(_A()) == 0


def test_cli_sem_janela():
    from elixx.cli import cmd_executar

    class _A:
        arquivo = "exemplos/character-image-animation.elixx"
        mostrar_arvore = False
        sem_janela = True
        clicar = None

    assert cmd_executar(_A()) == 0


# ---------- performance ----------


def test_perf_1_imagem():
    import time

    inicio = time.perf_counter()
    AssetVisual(ARQUIVO, BASE).dimensoes()
    assert time.perf_counter() - inicio < 5.0


def test_perf_10_imagens():
    import time

    inicio = time.perf_counter()
    for _ in range(10):
        AssetVisual(ARQUIVO, BASE).dimensoes()
    assert time.perf_counter() - inicio < 10.0


def test_perf_50_100_assets():
    import time

    inicio = time.perf_counter()
    for i in range(100):
        CharacterAsset(f"P{i}", PASTA, BASE).diagnosticar()
    assert time.perf_counter() - inicio < 15.0


def test_sem_copia_gigante():
    a = AssetVisual(ARQUIVO, BASE)
    assert a.tamanho() < 1024 * 1024


def test_usar_como_alias():
    c = CharacterAsset("Juh", PASTA, BASE)
    c.usar_como("direita", "personagem.png")
    assert c.diagnosticar()["vistas"]["lado_direito"] == "OK"
    assert c.vista("direita").existe() is True


def test_mapear_quatro(tmp_path):
    from PIL import Image

    for vista in VISTAS:
        Image.new("RGBA", (4, 4)).save(tmp_path / f"{vista}.png")
    c = CharacterAsset("T", ".", str(tmp_path))
    mapa = c.mapear()
    assert all(mapa[v] == f"{v}.png" for v in VISTAS)


def test_repr_asset():
    assert "CharacterAsset(Juh)" in repr(
        CharacterAsset("Juh", PASTA, BASE))


def test_ext_maiuscula(tmp_path):
    destino = tmp_path / "X.PNG"
    destino.write_bytes(open(
        "exemplos/assets/personagem_teste/personagem.png",
        "rb").read())
    a = AssetVisual("X.PNG", str(tmp_path))
    assert a.dimensoes() == (128, 160)


def test_dimensoes_cache():
    a = AssetVisual(ARQUIVO, BASE)
    assert a.dimensoes() == a.dimensoes()


def test_jpeg_stdlib(tmp_path):
    from PIL import Image

    Image.new("RGB", (9, 11)).save(tmp_path / "j.jpg",
                                   "JPEG")
    a = AssetVisual("j.jpg", str(tmp_path))
    assert a.dimensoes() == (9, 11)
    assert a.metadados()["tipo"] == "jpg"


def test_rig_com_partes():
    from elixx.visual.personagem import Character

    parte = CharacterPart("braco")
    rig = CharacterRig(Character("J", None, {}, {}),
                       partes={"braco": parte},
                       camadas=["base"])
    assert rig.to_dict()["partes"] == ["braco"]


def test_part_completa():
    v = CharacterView("frente", AssetVisual(ARQUIVO, BASE))
    parte = CharacterPart("olho", vista=v,
                          camada=CharacterLayer("c", 0))
    d = parte.to_dict()
    assert d["vista"]["vista"] == "frente"


def test_animacao_modo_invalido():
    from elixx.visual.asset_personagem import _definicao

    with pytest.raises(ErroELiXX):
        _definicao("J", "x", "escala", 1.0, 2.0, 500.0,
                   1, "loop")


def test_deslocamento_dy():
    d = animacao_deslocamento("J", (0.0, 0.0), 0.0, 30.0)
    assert d.chaves[0].para == (0.0, 30.0)


def test_view_dict_asset():
    v = CharacterView("frente", AssetVisual(ARQUIVO, BASE))
    assert v.to_dict()["asset"]["largura"] == 128
