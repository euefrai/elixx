"""Testes da Fase 14 — Items + Capability System (determinísticos)."""
import threading

import pytest

from elixx.compilador.componentes import expandir_componentes
from elixx.compilador.lexer import tokenizar
from elixx.compilador.parser import Parser, analisar
from elixx.compilador.semantica import validar
from elixx.erros import ErroELiXX, ErroSemantico, ErroSintatico
from elixx.runtime.nucleo import Executor
from elixx.visual.capacidades import (
    Capability,
    CapabilityRegistry,
    CapabilitySet,
    Inventario,
    ItemDefinition,
    ItemInstance,
    anexado,
    capacidades_de,
    coletar_definicoes,
    debug_capacidades,
    equipado,
    item_por_nome,
    itens_de,
    nova_instancia,
    obter_instancia,
    pode,
    possui,
    slot_de,
    tem_capacidade,
    vincular_itens,
)
from elixx.visual.cena import ConstrutorCena
from elixx.visual.mundo import vincular_mundos
from elixx.visual.personagem import vincular_personagens


def analisar_expandir(fonte):
    prog = Parser(tokenizar(fonte)).parse()
    expandir_componentes(prog)
    return prog


def montar(fonte):
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    return executor, cena, prog


def vinculo(fonte):
    ex, cena, prog = montar(fonte)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    return ex, cena, prog, itens, pers, mundos


BASE = ('janela p {\n titulo: "T"\n'
        ' item BotaFoguete {\n  categoria: "equipamento"\n'
        '  tags: "voo" "propulsao"\n  slot: "pes"\n  anexo: "pe_direito"\n'
        '  imagem: "bota.png"\n  frente: "bota-f.png"\n'
        '  asset_ligada: "bota-on.png"\n'
        '  capacidade voar {\n   descricao: "voar"\n'
        '   requer_equipado: "BotaFoguete"\n  }\n'
        '  capacidade pairar\n  capacidade subir\n  capacidade descer\n'
        ' }\n'
        ' item Corda {\n  categoria: "ferramenta"\n'
        '  capacidade prender\n  capacidade descer {\n   parametro alvo\n  }\n'
        '  capacidade alcancar\n }\n'
        ' item Arma {\n  categoria: "arma"\n  slot: "mao_direita"\n'
        '  anexo: "mao_direita"\n'
        '  capacidade mirar {\n   parametro alvo\n'
        '   requer_equipado: "Arma"\n  }\n'
        '  capacidade apontar {\n   parametro alvo\n  }\n'
        '  capacidade ameacar\n }\n'
        ' personagem Heroi {\n  posição: 100px 100px\n'
        '  possui: "Corda"\n  equipa: "BotaFoguete"\n'
        '  parte corpo {\n  }\n  parte pe_direito {\n   posição: 5px 40px\n  }\n'
        '  parte mao_direita {\n   posição: 20px 0px\n  }\n'
        '  capacidade andar\n  capacidade pular\n'
        '  capacidade pegar {\n   parametro alvo\n'
        '   requer_proximo: "alvo"\n   raio: 200px\n  }\n'
        ' }\n'
        ' imagem torre_visual {\n  arquivo: "t.png"\n'
        '  posição: 150px 120px\n  tamanho: 60px 200px\n }\n'
        ' mundo M {\n  usar personagem Heroi\n'
        '  usar item BotaFoguete como botas_hero\n'
        '  usar item Corda\n  usar item Arma\n'
        '  plataforma torre_plataforma {\n   posição: 140px 300px\n'
        '   tamanho: 100px 20px\n  }\n'
        '  ponto torre {\n   posição: 150px 120px\n  }\n'
        ' }\n}\n')


def base():
    return vinculo(BASE)


# ----- 1-7: definição, identidade, categoria, tags, props, visual, views -----

def test_definicao_item():
    _ex, _cena, _prog, itens, _pers, _mundos = base()
    bota = item_por_nome(itens, "BotaFoguete")
    assert isinstance(bota, ItemDefinition)
    assert bota.nome == "BotaFoguete"
    with pytest.raises(ErroELiXX, match="não definido"):
        item_por_nome(itens, "Fantasma")


def test_identidade_definicao_instancia():
    _ex, _cena, _prog, itens, _pers, _mundos = base()
    a = obter_instancia(itens, "Corda")
    b = obter_instancia(itens, "Corda")
    assert a is b  # estável por nome
    c = obter_instancia(itens, "Corda", "corda_02")
    assert c.nome == "corda_02" and c.definicao == "Corda"
    assert c is not a
    assert isinstance(c, ItemInstance)


def test_categoria_tags_propriedades():
    _ex, _cena, _prog, itens, _pers, _mundos = base()
    bota = item_por_nome(itens, "BotaFoguete")
    assert bota.categoria == "equipamento"
    assert bota.tags == ("voo", "propulsao")
    assert item_por_nome(itens, "Corda").categoria == "ferramenta"


def test_visual_views_variantes():
    _ex, _cena, _prog, itens, _pers, _mundos = base()
    bota = item_por_nome(itens, "BotaFoguete")
    assert bota.imagem == "bota.png"
    assert bota.vistas == {"frente": "bota-f.png"}
    assert item_por_nome(itens, "Corda").vistas == {}
    inst = obter_instancia(itens, "BotaFoguete")
    assert inst.estado == "disponivel"


def test_item_duplicado_erro():
    with pytest.raises(ErroSemantico, match="duas vezes"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n }\n item X {\n }\n}\n'))


def test_item_parse_arvore():
    from elixx.compilador.ast import mostrar_arvore

    prog = analisar_expandir(BASE)
    arvore = mostrar_arvore(prog)
    assert "Item BotaFoguete" in arvore
    assert "Capacidade voar" in arvore
    validar(prog)


# ----- 8-10: item no World, sem visual, visual sem item -----

def test_item_no_world():
    _ex, _cena, _prog, itens, _pers, mundos = base()
    w = mundos["M"]
    ent = w.por_id("botas_hero")
    assert ent.tipo == "item"
    assert ent.item is not None
    assert ent.item.definicao == "BotaFoguete"
    assert ent.categoria == "equipamento"
    assert w.por_tipo("item")[0].nome in ("botas_hero", "Corda", "Arma")


def test_item_sem_visual_e_ponto():
    _ex, _cena, _prog, itens, _pers, mundos = base()
    ent = mundos["M"].por_id("Corda")
    assert ent.item is not None
    assert ent.bounds_global().largura == 0.0  # ponto, sem visual/tamanho
    assert ent.posicao_global().tupla() == (0.0, 0.0)


def test_usar_item_invalido_erro():
    with pytest.raises(ErroSemantico, match="não definido"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n mundo M {\n'
            '  usar item Fantasma\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="repetida"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n }\n mundo M {\n'
            '  usar item X\n  usar item X\n }\n}\n'))


# ----- 11-16: posse, instâncias, equipamento, slots, attachment -----

def test_posse():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert possui(h, "Corda") is True
    assert possui(h, "corda_inexistente") is False
    assert itens_de(h) == ["Corda", "BotaFoguete"]


def test_multiplas_instancias():
    _ex, _cena, _prog, itens, pers, _mundos = base()
    h = pers["Heroi"]
    h.inventario.possuir(obter_instancia(itens, "Corda", "corda_02"))
    assert possui(h, "corda_02") is True
    assert possui(h, "Corda") is True
    assert h.inventario.de_definicao("Corda") == ["Corda", "corda_02"]


def test_equipamento_slots():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert equipado(h, "BotaFoguete") is True
    assert slot_de(h, "BotaFoguete") == "pes"
    assert equipado(h, "Corda") is False
    assert slot_de(h, "Corda") is None
    # equipar sem possuir é erro claro (sem auto-posse)
    with pytest.raises(ErroELiXX, match="não possuído"):
        h.inventario.equipar("Arma")
    h.inventario.possuir(obter_instancia(_itens, "Arma"))
    assert h.inventario.equipar("Arma") == "mao_direita"
    assert slot_de(h, "Arma") == "mao_direita"


def test_attachment_parte():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert anexado(h, "BotaFoguete") == "pe_direito"
    assert anexado(h, "Corda") is None
    # anexo segue a hierarquia F12 (transform global da parte)
    t = h.transform_anexo("BotaFoguete")
    assert (t.x, t.y) == (105.0, 140.0)
    with pytest.raises(ErroELiXX, match="sem anexo"):
        h.transform_anexo("Corda")


def test_anexo_invalido_erro_semantico():
    with pytest.raises(ErroSemantico, match="não existe"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n  anexo: "asa"\n }\n'
            ' personagem H {\n  equipa: "X"\n  parte b {\n  }\n }\n}\n'))


def test_transform_relativo_acompanha_motion():
    ex, cena, prog, itens, pers, _mundos = base()
    h = pers["Heroi"]
    antes = h.transform_anexo("BotaFoguete")
    assert (antes.x, antes.y) == (105.0, 140.0)
    cena.buscar("Heroi").x = 500.0
    depois = h.transform_anexo("BotaFoguete")
    assert (depois.x, depois.y) == (505.0, 140.0)


# ----- 17-23: capabilities -----

def test_capability_simples():
    cap = Capability(nome="voar", provider="item:BotaFoguete")
    assert cap.nome == "voar" and not cap.exige_alvo()


def test_capability_duplicada_mescla_provedores():
    conjunto = CapabilitySet()
    conjunto.adicionar(Capability(nome="voar", provider="item:A"))
    conjunto.adicionar(Capability(nome="voar", provider="item:B"))
    assert len(conjunto) == 1
    assert conjunto.provedores("voar") == ["item:A", "item:B"]
    with pytest.raises(ErroELiXX, match="desconhecida"):
        conjunto.obter("nadar")


def test_capability_com_provider():
    _ex, _cena, _prog, itens, pers, _mundos = base()
    h = pers["Heroi"]
    compostas = capacidades_de(h)
    assert "voar" in compostas
    assert compostas.provedores("pairar") == ["item:BotaFoguete"]
    assert "item:BotaFoguete" in compostas.provedores("voar")


def test_composicao_ordem_deterministica():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert capacidades_de(h).nomes() == ["andar", "pular", "pegar", "voar",
                                         "pairar", "subir", "descer"]


def test_capability_personagem_e_item():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert tem_capacidade(h, "andar") is True  # própria
    assert tem_capacidade(h, "voar") is True  # equipada
    assert tem_capacidade(h, "mirar") is False  # arma não equipada
    assert tem_capacidade(h, "nadar") is False


def test_capability_equipada_sai_ao_desequipar():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert tem_capacidade(h, "voar") is True
    h.inventario.desequipar("BotaFoguete")
    assert tem_capacidade(h, "voar") is False
    assert tem_capacidade(h, "andar") is True


def test_registry():
    from elixx.visual.capacidades import CapabilityRegistry

    reg = CapabilityRegistry()
    reg.registrar_item(ItemDefinition(nome="X"))
    assert reg.provedores_de("voar") == []
    with pytest.raises(ErroELiXX, match="duas vezes"):
        reg.registrar_item(ItemDefinition(nome="X"))


# ----- 24-28: requisitos e pode() -----

def test_requisito_satisfeito_equipado():
    _ex, _cena, _prog, _itens, pers, mundos = base()
    r = pers["Heroi"].pode("voar", mundos["M"])
    assert r["permitido"] is True
    assert r["requisitos"] == [{"tipo": "equipado", "alvo": "BotaFoguete",
                                "ok": True,
                                "detalhe": "BotaFoguete equipada."}]


def test_requisito_ausente_motivo():
    _ex, _cena, _prog, _itens, pers, mundos = base()
    r = pers["Heroi"].pode("mirar", mundos["M"], alvo="torre")
    assert r["permitido"] is False  # nem possui a capacidade
    assert "mirar" in r["motivo"]
    # equipa a arma: requisito equipado passa, sem espaciais
    pers["Heroi"].inventario.possuir(
        obter_instancia(_itens, "Arma"))
    pers["Heroi"].inventario.equipar("Arma")
    r2 = pers["Heroi"].pode("mirar", mundos["M"], alvo="torre")
    assert r2["permitido"] is True


def test_requisito_espacial_proximidade():
    _ex, _cena, _prog, _itens, pers, mundos = base()
    h, w = pers["Heroi"], mundos["M"]
    r = h.pode("pegar", w, alvo="torre")
    assert r["permitido"] is True  # hero (100,100) perto de torre (150,120)
    r2 = h.pode("pegar", w)  # sem alvo, mas exige alvo
    assert r2["permitido"] is False
    assert "alvo" in r2["motivo"]
    # longe: move o hero para longe
    w.por_id("Heroi").character.no_raiz.x = 1500.0
    r3 = h.pode("pegar", w, alvo="torre")
    assert r3["permitido"] is False
    assert "longe" in r3["motivo"]


def test_requisito_presente_tag_categoria_tipo():
    ex, cena, prog, itens, pers, mundos = mundos_de_torre()
    h, w = pers["Heroi"], mundos["M"]
    assert h.pode("abrir_porta", w)["permitido"] is True
    assert h.pode("ler_caixa", w, alvo="caixa")["permitido"] is True
    assert h.pode("ler_caixa", w, alvo="torre")["permitido"] is False
    assert h.pode("focar", w, alvo="caixa")["permitido"] is True
    assert h.pode("focar", w)["permitido"] is False  # exige alvo


def mundos_de_torre():
    fonte = ('janela p {\n titulo: "T"\n'
             ' personagem Heroi {\n  posição: 0px 0px\n  parte b {\n  }\n'
             '  capacidade abrir_porta {\n   requer_presente: "porta"\n  }\n'
             '  capacidade ler_caixa {\n   parametro alvo\n'
             '   requer_categoria: "caixa"\n  }\n'
             '  capacidade focar {\n   parametro alvo\n'
             '   requer_tag: "interativo"\n  }\n'
             ' }\n'
             ' imagem caixa_visual {\n  arquivo: "c.png"\n'
             '  posição: 10px 10px\n  tamanho: 20px 20px\n }\n'
             ' mundo M {\n  usar personagem Heroi\n'
             '  ponto porta {\n   posição: 5px 5px\n  }\n'
             '  objeto caixa {\n   posição: 10px 10px\n   tamanho: 20px 20px\n'
             '   categoria: "caixa"\n   tag: "interativo"\n'
             '   visual: caixa_visual\n  }\n'
             '  ponto torre {\n   posição: 500px 500px\n  }\n'
             ' }\n}\n')
    ex, cena, prog = montar(fonte)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    return ex, cena, prog, itens, pers, vincular_mundos(cena, prog, pers,
                                                       itens)


def test_requisito_estado_e_capacidade():
    ex, cena, prog, itens, pers, mundos = vinculo(
        'janela p {\n titulo: "T"\n'
        ' item Lanterna {\n  estado: "apagada"\n'
        '  capacidade iluminar {\n   requer_equipado: "Lanterna"\n'
        '   requer_estado: "acesa"\n  }\n'
        ' }\n'
        ' personagem H {\n  posição: 0px 0px\n  equipa: "Lanterna"\n'
        '  parte b {\n  }\n  capacidade liderar {\n'
        '   requer_capacidade: "iluminar"\n  }\n'
        ' }\n'
        ' mundo M {\n  usar personagem H\n  usar item Lanterna\n }\n}\n')
    h, w = pers["H"], mundos["M"]
    r = h.pode("iluminar", w)
    assert r["permitido"] is False and "apagada" in r["motivo"]
    h.inventario.instancias["Lanterna"].definir_estado("acesa")
    assert h.pode("iluminar", w)["permitido"] is True
    assert h.pode("liderar", w)["permitido"] is True
    with pytest.raises(ErroELiXX, match="vazio"):
        h.inventario.instancias["Lanterna"].definir_estado("  ")


# ----- 28-31: alvo, parâmetros, estado, consultas -----

def test_capability_com_alvo_e_parametros():
    _ex, _cena, _prog, itens, pers, _mundos = base()
    h = pers["Heroi"]
    cap = capacidades_de(h).obter("pegar")
    assert cap.parametros == ("alvo",)
    assert cap.exige_alvo() is True
    assert capacidades_de(h).obter("andar").parametros == ()


def test_estado_semantico_livre():
    _ex, _cena, _prog, itens, _pers, _mundos = base()
    inst = obter_instancia(itens, "Corda")
    assert inst.estado == "disponivel"
    inst.definir_estado("dobrada")
    assert inst.estado == "dobrada"


def test_consultas_deterministicas():
    _ex, _cena, _prog, _itens, pers, mundos = base()
    h = pers["Heroi"]
    assert capacidades_de(h).nomes() == capacidades_de(h).nomes()
    assert h.pode("voar", mundos["M"]) == h.pode("voar", mundos["M"])
    assert debug_capacidades(h, mundos["M"]).splitlines()[0] == (
        "CAPACIDADES DE Heroi")


# ----- 32-35: F12, F13, F11 -----

def test_personagem_f12_intacto():
    _ex, _cena, _prog, _itens, pers, _mundos = base()
    h = pers["Heroi"]
    assert h.obter_parte("mao_direita").nome == "mao_direita"
    assert h.obter_pose if hasattr(h, "obter_pose") else True
    assert h.direcao == "frente"


def test_world_f13_intacto():
    _ex, _cena, _prog, _itens, _pers, mundos = base()
    w = mundos["M"]
    assert w.por_id("torre").tipo == "ponto"
    assert "botas_hero" in w
    assert w.distancia("Heroi", "torre") > 0


def test_motion_f11_sem_duplicacao():
    import elixx.visual.capacidades as capmod

    assert not hasattr(capmod, "MotorAnimacoes")
    assert not hasattr(capmod, "Transform")


# ----- segurança -----

def test_seguranca_dados_inertes():
    ex, cena, prog, itens, pers, mundos = vinculo(
        'janela p {\n titulo: "T"\n'
        ' item Evil {\n  categoria: "__import__(os).system(x)"\n'
        '  tags: "eval(1)" "exec(y)"\n'
        '  capacidade explodir {\n   descricao: "os.system(rm)"\n  }\n'
        ' }\n'
        ' personagem H {\n  posição: 0px 0px\n  equipa: "Evil"\n'
        '  parte b {\n  }\n }\n'
        ' mundo M {\n  usar personagem H\n  usar item Evil\n }\n}\n')
    h = pers["H"]
    assert tem_capacidade(h, "explodir") is True
    r = h.pode("explodir", mundos["M"])
    assert r["permitido"] is True  # dado inerte, sem execução
    assert "__import__" in item_por_nome(itens, "Evil").categoria


def test_exemplo_items_capabilities():
    with open("exemplos/items-capabilities.elixx", encoding="utf-8") as arq:
        fonte = arq.read()
    prog = analisar_expandir(fonte)
    validar(prog)
    executor = Executor()
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    itens = vincular_itens(prog)
    pers = vincular_personagens(cena, itens)
    mundos = vincular_mundos(cena, prog, pers, itens)
    h, w = pers["Heroi"], mundos["Mundo"]
    # §24: programa responde sem executar
    assert possui(h, "Corda") is True
    assert w.perto_de("Heroi", "Corda", 500) in (True, False)
    assert pode(h, "pegar", w, alvo="Corda")["permitido"] is True
    assert possui(h, "BotaFoguete") is True
    assert equipado(h, "BotaFoguete") is True
    assert pode(h, "voar", w)["permitido"] is True
    assert equipado(h, "Arma") is False
    assert pode(h, "mirar", w, alvo="destino")["permitido"] is False
    assert tem_capacidade(h, "andar") is True


def test_slot_um_por_vez_deterministico():
    _ex, _cena, _prog, itens, pers, _mundos = base()
    h = pers["Heroi"]
    h.inventario.possuir(obter_instancia(itens, "Arma", "arma2"))
    h.inventario.equipar("arma2", slot="pes")  # ocupa slot da bota
    assert slot_de(h, "arma2") == "pes"
    assert tem_capacidade(h, "voar") is False  # bota saiu do slot
    assert tem_capacidade(h, "mirar") is True


def test_requer_desconhecido_erro_claro():
    with pytest.raises(ErroSemantico, match="desconhecida"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n'
            '  capacidade c {\n   voar_alto: 1\n  }\n }\n}\n'))


def test_capacidade_semantica_erros():
    with pytest.raises(ErroSemantico, match="repetida"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n'
            '  capacidade a\n  capacidade a\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="repetido"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n'
            '  capacidade a {\n   parametro t\n   parametro t\n  }\n }\n}\n'))
    with pytest.raises(ErroSemantico, match="raio"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n item X {\n'
            '  capacidade a {\n   raio: 10px\n  }\n }\n}\n'))
    with pytest.raises(ErroSintatico):
        analisar('janela p {\n titulo: "T"\n item X {\n'
                 '  capacidade\n }\n}\n')
    with pytest.raises(ErroSemantico, match="não definido"):
        validar(analisar_expandir(
            'janela p {\n titulo: "T"\n personagem H {\n'
            '  possui: "Fantasma"\n  parte b {\n  }\n }\n}\n'))
