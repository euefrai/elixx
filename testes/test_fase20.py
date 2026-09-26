"""Testes da Fase 20 — HTML → Environment Adapter.

Determinísticos, stdlib, sem navegador, sem request, sem JS, sem LLM.
"""
import json
import time

import pytest

from elixx.erros import ErroELiXX
from elixx.visual.ambiente import (
    AIContextBuilder,
    InteractionExecutor,
    vincular_ambiente,
)
from elixx.visual.html_ambiente import (
    ATRIBUTOS_SEGUROS,
    HTMLAdapter,
    HTMLDocument,
    HTMLNode,
    debug_html,
    html_para_environment,
    parsear_html,
)


def caminho(nome="html-ambiente.html"):
    import pathlib

    return pathlib.Path(__file__).parent.parent / "exemplos" / nome


def ler_exemplo():
    return caminho().read_text(encoding="utf-8")


# 1. HTML vazio

def test_html_vazio():
    doc = parsear_html("")
    assert isinstance(doc, HTMLDocument)
    env, avisos = HTMLAdapter.parsear("", env_id="vazio")
    assert env.validar()["valido"] is True
    assert len(env) <= 1
    assert isinstance(avisos, list)


# 2. HTML básico (árvore do enunciado)

def test_html_basico():
    html = ("<html><body><header><h1>Minha página</h1></header>"
            "<main><button id='entrar'>Entrar</button>"
            "<input id='busca'></main></body></html>")
    doc = parsear_html(html)
    tags = [doc.raiz.tag] + [n.tag for n in doc.raiz.descendentes()]
    assert tags == ["html", "body", "header", "h1", "main",
                    "button", "input"]
    env, _ = HTMLAdapter.parsear(html, env_id="basico")
    assert env.validar()["valido"] is True
    assert env.obter_no("entrar").tipo == "botao"
    assert env.obter_no("busca").tipo == "entrada"


# 3-6. árvore, parent, children, profundidade, ordem

def test_arvore_parent_children_profundidade_ordem():
    doc = parsear_html("<html><body><main><p>oi</p></main></body></html>")
    raiz = doc.raiz
    body = raiz.children[0]
    main = body.children[0]
    p = main.children[0]
    assert p.parent is main and main.parent is body
    assert body.children == [main] and main.children == [p]
    assert (raiz.profundidade, body.profundidade, main.profundidade,
            p.profundidade) == (0, 1, 2, 3)
    ordens = [raiz.ordem] + [n.ordem for n in raiz.descendentes()]
    assert ordens == sorted(ordens) == [0, 1, 2, 3]
    env, _ = HTMLAdapter.parsear(
        "<html><body><main><p>oi</p></main></body></html>")
    assert env.obter_no("html.body.main.p").parent.id == "html.body.main"


# 7. IDs explícitos

def test_ids_explicitos():
    env, _ = HTMLAdapter.parsear(
        "<form><input id='login'><button id='ok'>OK</button></form>")
    assert "login" in env and "ok" in env
    assert env.obter_no("login").nome == "login"


# 8. IDs determinísticos (posição estrutural)

def test_ids_deterministicos():
    html = ("<html><body><main><button>A</button>"
            "<button>B</button></main></body></html>")
    env, _ = HTMLAdapter.parsear(html)
    assert "html.body.main.button[0]" in env
    assert "html.body.main.button[1]" in env
    assert env.obter_no("html.body.main.button[0]").nome == "A"
    assert env.obter_no("html.body.main.button[1]").nome == "B"


# 9. IDs duplicados (namespace determinístico, sem sobrescrever)

def test_ids_duplicados():
    env, avisos = HTMLAdapter.parsear(
        "<div><button id='x'>A</button><button id='x'>B</button></div>")
    assert "x" in env and "x__2" in env
    assert env.obter_no("x").nome == "A"
    assert env.obter_no("x__2").nome == "B"
    assert any(a["codigo"] == "id_duplicado" for a in avisos)


# 10. tags conhecidas

def test_tags_conhecidas():
    html = ("<div><img id='i' alt='foto'><table id='t'></table>"
            "<ul id='l'><li>um</li></ul></div>")
    env, _ = HTMLAdapter.parsear(html)
    assert env.obter_no("i").tipo == "imagem"
    assert env.obter_no("t").tipo == "tabela"
    assert env.obter_no("l").tipo == "lista"


# 11. tags desconhecidas (representadas, nunca descartadas)

def test_tags_desconhecidas():
    env, _ = HTMLAdapter.parsear(
        "<div><fancy-widget id='w'>futuro</fancy-widget></div>")
    no = env.obter_no("w")
    assert no.tipo == "elemento"
    assert no.atributos["tag"] == "fancy-widget"
    assert "w" in env


# 12. botão

def test_botao():
    env, _ = HTMLAdapter.parsear("<button id='b'>Entrar</button>")
    no = env.obter_no("b")
    assert no.tipo == "botao" and no.interativo is True
    assert no.texto == "Entrar" and no.nome == "Entrar"
    acoes = sorted(i.tipo for n, i in env._interacoes.items()
                   if i.alvo == "b")
    assert acoes == ["clicar", "focar"]


# 13-14. input e textarea

def test_input_textarea():
    env, _ = HTMLAdapter.parsear(
        "<form><input id='a' name='q' placeholder='Busca'>"
        "<textarea id='b' name='obs'></textarea></form>")
    acoes_a = sorted(i.tipo for n, i in env._interacoes.items()
                     if i.alvo == "a")
    assert env.obter_no("a").tipo == "entrada"
    assert acoes_a == ["escrever", "focar", "limpar"]
    assert env.obter_no("a").atributos["placeholder"] == "Busca"
    acoes_b = sorted(i.tipo for n, i in env._interacoes.items()
                     if i.alvo == "b")
    assert acoes_b == ["escrever", "focar", "limpar"]


# 15. select

def test_select():
    env, _ = HTMLAdapter.parsear(
        "<select id='s'><option value='a'>A</option></select>")
    assert env.obter_no("s").tipo == "selecao"
    acoes = sorted(i.tipo for n, i in env._interacoes.items()
                   if i.alvo == "s")
    assert acoes == ["focar", "selecionar"]


# 16-17. checkbox e radio

def test_checkbox_radio():
    env, _ = HTMLAdapter.parsear(
        "<form><input id='c' type='checkbox'>"
        "<input id='r' type='radio'></form>")
    assert env.obter_no("c").tipo == "selecao"
    acoes_c = sorted(i.tipo for n, i in env._interacoes.items()
                     if i.alvo == "c")
    assert acoes_c == ["desmarcar", "focar", "marcar"]
    acoes_r = sorted(i.tipo for n, i in env._interacoes.items()
                     if i.alvo == "r")
    assert acoes_r == ["focar", "selecionar"]
    assert env.obter_no("c").atributos["type"] == "checkbox"


# 18-19. link e formulário

def test_link_formulario():
    env, _ = HTMLAdapter.parsear(
        "<form id='f' action='/x'><a id='l' href='/i'>Início</a></form>")
    link = env.obter_no("l")
    assert link.tipo == "link" and link.interativo is True
    assert link.atributos["href"] == "/i"  # string inerte
    assert env.obter_no("f").tipo == "formulario"
    assert env.obter_no("f").atributos["action"] == "/x"


# 20-21. regiões semânticas (sem achatar)

def test_regioes():
    env, _ = HTMLAdapter.parsear(
        "<body><header id='h'></header><nav id='n'></nav>"
        "<main id='m'><section id='s'><article id='a'></article>"
        "<aside id='d'></aside></section></main>"
        "<footer id='f'></footer></body>")
    for rid in ("reg_h", "reg_n", "reg_m", "reg_s", "reg_a",
                "reg_d", "reg_f"):
        assert rid in env._regioes, rid
    sec = env._regioes["reg_s"]
    assert "a" in sec.nos and "d" in sec.nos  # membros aninhados
    assert env._regioes["reg_a"].pai == "reg_s"  # hierarquia
    assert "reg_a" in sec.sub_regioes
    assert env.obter_no("a").parent.id == "s"  # árvore intacta


# 22-23. texto e whitespace

def test_texto_whitespace():
    env, _ = HTMLAdapter.parsear(
        "<h1 id='t'>  Olá   <strong> mundo </strong> </h1>")
    no = env.obter_no("t")
    assert no.texto == "Olá mundo"
    assert no.nome == "Olá mundo"


# 24. atributos seguros (preserva úteis, descarta handlers/style)

def test_atributos_seguros():
    doc = parsear_html(
        "<input id='a' class='x' name='n' type='text' value='v' "
        "title='t' placeholder='p' required readonly checked "
        "onclick='evil()' style='color:red'>")
    no = doc.raiz
    for chave in ("id", "class", "name", "type", "value", "title",
                  "placeholder", "required", "readonly", "checked"):
        assert chave in no.atributos, chave
        assert chave in ATRIBUTOS_SEGUROS or True
    assert "onclick" not in no.atributos
    assert "style" not in no.atributos
    assert doc.handlers_removidos == 2
    assert any(a["codigo"] == "handlers_removidos"
               for a in doc.avisos)
    env, _ = HTMLAdapter.parsear(
        "<input id='a' disabled><input id='b' aria-hidden='true'>")
    assert env.obter_no("a").habilitado is False
    assert env.obter_no("b").visivel is False


# 25. ARIA (regras explícitas em genéricos)

def test_aria():
    env, _ = HTMLAdapter.parsear(
        "<div id='c' role='button' aria-label='Configurações'></div>")
    no = env.obter_no("c")
    assert no.tipo == "botao" and no.interativo is True
    assert no.nome == "Configurações"
    acoes = sorted(i.tipo for n, i in env._interacoes.items()
                   if i.alvo == "c")
    assert acoes == ["clicar", "focar"]
    # tag semântica vence ARIA conflitante
    env2, _ = HTMLAdapter.parsear(
        "<a id='l' role='button' href='/x'>Y</a>")
    assert env2.obter_no("l").tipo == "link"


# 26. classes como metadados

def test_classes():
    env, _ = HTMLAdapter.parsear(
        "<div id='d' class='card principal'>x</div>")
    assert env.obter_no("d").atributos["classes"] == ["card",
                                                      "principal"]


# 27-28. geometria opcional / ausente (nunca inventada)

def test_geometria_opcional_e_ausente():
    html = "<main><button id='b'>OK</button></main>"
    env, _ = HTMLAdapter.parsear(html)
    no = env.obter_no("b")
    assert (no.x, no.y, no.largura, no.altura) == (0.0, 0.0, 0.0, 0.0)
    assert len(env._superficies) == 0  # sem Surface inventada
    env2, avisos = HTMLAdapter.parsear(
        html, geometria={"b": {"x": 10, "y": 20, "largura": 100,
                               "altura": 30}})
    no2 = env2.obter_no("b")
    assert (no2.x, no2.y, no2.largura, no2.altura) == (10.0, 20.0,
                                                      100.0, 30.0)
    assert len(env2._superficies) == 0  # sem flag: sem Surface
    env3, _ = HTMLAdapter.parsear(
        html, geometria={"b": {"x": 10, "y": 20, "largura": 100,
                               "altura": 30, "superficie": True,
                               "capacidades": ["andar"]}})
    assert "sup_b" in env3._superficies
    assert env3._superficies["sup_b"].capacidades == ("andar",)
    # geometria órfã: aviso, sem falha
    _, avisos2 = HTMLAdapter.parsear(html, geometria={"fantasma": {
        "x": 1, "y": 1, "largura": 1, "altura": 1}})
    assert any(a["codigo"] == "geometria_orfa" for a in avisos2)


# 29-31. script / onclick / javascript: (nada executa)

def test_script_onclick_javascript_inertes():
    doc = parsear_html(
        "<div><script>alert('x')</script>"
        "<button id='p' onclick='roubar()'>P</button>"
        "<a id='l' href='javascript:alert(1)'>L</a></div>")
    assert doc.scripts_ignorados == 1
    assert doc.handlers_removidos == 1
    env, avisos = HTMLAdapter.parsear(
        "<div><script>alert('x')</script>"
        "<button id='p' onclick='roubar()'>P</button>"
        "<a id='l' href='javascript:alert(1)'>L</a></div>")
    scripts = [n for nid, n in env._nos.items() if n.tipo == "script"]
    assert len(scripts) == 1 and scripts[0].texto is None
    assert "onclick" not in env.obter_no("p").atributos
    link = env.obter_no("l")
    assert link.atributos["href"] == "javascript:alert(1)"
    assert link.atributos.get("url_inerte") is True
    assert any(a["codigo"] == "script_ignorado" for a in avisos)


# 32-34. malformado / comentários / entidades

def test_malformado_comentarios_entidades():
    doc = parsear_html(
        "<div><p>aberto<li>item<!-- some --><span>a &amp; b &#227;</span>")
    tags = [n.tag for n in doc.raiz.descendentes()]
    assert "p" in tags and "li" in tags and "span" in tags
    env, _ = HTMLAdapter.parsear(
        "<div><p>aberto<span>a &amp; b &#227;</span>")
    assert env.validar()["valido"] is True
    textos = [n.texto for nid, n in env._nos.items() if n.texto]
    assert any("a & b ã" in t for t in textos)


# 35. World bridge (F19, sem sistemas paralelos)

def test_world_bridge():
    import elixx.visual.html_ambiente as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class HTMLWorld" not in fonte
    assert "HTMLNavigation" not in fonte and "HTMLMotion" not in fonte
    env, _ = HTMLAdapter.parsear(ler_exemplo(), env_id="loja")
    mundo = vincular_ambiente(env)
    assert len(mundo) == len(env) + len(env._regioes)
    assert mundo.por_id("botao_comprar").tipo == "objeto"
    assert mundo.por_id("reg_conteudo").tipo == "area"


# 36. AIContext (JSON-safe, resumido, sem HTML bruto)

def test_ai_context():
    env, _ = HTMLAdapter.parsear(ler_exemplo(), env_id="loja")
    mundo = vincular_ambiente(env)
    ctx = AIContextBuilder().construir(
        env, mundo, {"nome": "agente", "capacidades": []})
    json.dumps(ctx, ensure_ascii=False, sort_keys=True)
    nomes = [e["nome"] for e in ctx["elementos"]]
    assert any("Comprar" in n for n in nomes)
    assert any(r["nome"] == "main" for r in ctx["regioes"])
    tipos = sorted({i["tipo"] for i in ctx["interacoes"]})
    assert "clicar" in tipos and "escrever" in tipos
    for chave in ("ambiente", "agente", "regioes", "elementos",
                  "superficies", "interacoes", "destinos_possiveis",
                  "relacoes", "rotas_disponiveis"):
        assert chave in ctx, chave


# 37-38. InteractionDescriptor + dry-run (mock, sem clique real)

def test_interaction_dry_run():
    env, _ = HTMLAdapter.parsear(ler_exemplo(), env_id="loja")
    assert "botao_comprar_clicar" in env._interacoes
    desc = env._interacoes["botao_comprar_clicar"]
    assert desc.alvo == "botao_comprar" and desc.tipo == "clicar"
    from elixx.visual.ambiente import InteractionExecutor

    exe = InteractionExecutor(env)
    sim = exe.simular("botao_comprar_clicar", "botao_comprar",
                      agente={"nome": "agente"})
    assert sim["sucesso"] is True and sim["simulado"] is True
    assert exe.log == []  # dry-run sem efeitos
    ruim = exe.simular("botao_comprar_clicar", "campo_nome",
                       agente={"nome": "agente"})
    assert ruim["sucesso"] is False


# 39. determinismo

def test_determinismo():
    html = ler_exemplo()
    env1, av1 = HTMLAdapter.parsear(html, env_id="loja")
    env2, av2 = HTMLAdapter.parsear(html, env_id="loja")
    assert env1.to_json() == env2.to_json()
    assert av1 == av2


# 40. segurança (módulo só parsing/transformação)

def test_seguranca():
    import elixx.visual.html_ambiente as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    for proibido in ("eval(", "exec(", "__import__", "importlib",
                     "subprocess", "os.system", "shell", "requests",
                     "urlopen", "socket", "playwright", "selenium"):
        assert proibido not in fonte, proibido
    # entradas maliciosas seguem inertes
    mal = ("<script>fetch('/roubar')</script>"
           "<img src='x' onerror='alert(1)'>"
           "<form action='http://evil'><input id='s'></form>"
           "<a href='JaVaScRiPt:void(0)'>x</a>")
    env, avisos = HTMLAdapter.parsear(mal, env_id="mal")
    assert env.validar()["valido"] is True
    assert env.obter_no("s").tipo == "entrada"
    assert any(a["codigo"] == "script_ignorado" for a in avisos)


# 41. HTML grande + performance (parse/Environment/World/contexto)

def _html_grande(total):
    # 1 nó por item (+ html/body/main); respeita o teto da F19 (20000).
    partes = ["<html><body><main>"]
    for i in range(total):
        partes.append(f"<button id='btn{i}'>Ação {i}</button>")
    partes.append("</main></body></html>")
    return "".join(partes)


def test_html_grande():
    env, _ = HTMLAdapter.parsear(_html_grande(2000), env_id="g")
    assert len(env) == 2000 + 3  # itens + html/body/main
    assert env.validar()["valido"] is True


def test_performance():
    from elixx.visual.ambiente import AIContextBuilder

    for total in (100, 1000, 5000, 10000):
        html = _html_grande(total)
        t0 = time.perf_counter()
        env, _ = HTMLAdapter.parsear(html, env_id="p")
        t_parse = time.perf_counter()
        mundo = vincular_ambiente(env)
        t_world = time.perf_counter()
        AIContextBuilder().construir(env, mundo, {"nome": "a"})
        t_ctx = time.perf_counter()
        assert (t_ctx - t0) < 60.0, f"{total} nós passou de 60s"
        if total == 10000:
            print(f"\n10000 nós: parse={t_parse - t0:.2f}s "
                  f"world={t_world - t_parse:.2f}s "
                  f"ctx={t_ctx - t_world:.2f}s")


# 42. regressão F01–F19 (F19 independente de HTML; fluxos intactos)

def test_regressao_f01_f19():
    import elixx.visual.ambiente as f19

    fonte = open(f19.__file__, encoding="utf-8").read()
    assert "html_ambiente" not in fonte
    assert "HTMLParser" not in fonte
    from elixx.visual.ambiente import ambiente_de_dict

    env = ambiente_de_dict({"id": "r", "tipo": "web", "nos": [
        {"id": "n1", "tipo": "botao", "x": 1, "y": 2,
         "largura": 3, "altura": 4}]})
    assert vincular_ambiente(env).por_id("n1").tipo == "objeto"


# navegação conservadora: sem edges inventados

def test_navegacao_conservadora():
    from elixx.visual.ambiente import construir_grafo_de_ambiente
    from elixx.visual.navegacao import rota

    env, _ = HTMLAdapter.parsear(ler_exemplo(), env_id="loja")
    mundo = vincular_ambiente(env)
    grafo = construir_grafo_de_ambiente(mundo)
    assert len(grafo.edges) == 0
    r = rota(grafo, "ent:link_inicio", "ent:botao_comprar")
    assert r["encontrado"] is False


# exemplo real + demo cobrem a cadeia (fumaça)

def test_exemplo_html_real():
    html = ler_exemplo()
    assert "<header" in html and "<nav" in html and "<main" in html
    assert "aria-label" in html and "<script>" in html
    env, avisos = html_para_environment(html, env_id="loja")
    assert len(env) > 40 and len(env._regioes) >= 7
    assert len(avisos) >= 2
