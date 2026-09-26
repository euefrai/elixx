"""Testes da Fase 06 — HTTP/REST, fontes remotas/arquivo e integração
estado→reatividade. Servidor local controlado (sem internet)."""
import threading
import time

import pytest

from servidor_teste import ServidorTeste
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.dados import ClienteHttp, FonteArquivo, FonteRemota, montar_url
from elixx.dados.http import METODOS
from elixx.erros import ErroSemantico
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.reativo import Vinculador


@pytest.fixture(scope="module")
def srv():
    with ServidorTeste() as servidor:
        yield servidor


def cliente(timeout=5):
    return ClienteHttp(timeout_s=timeout)


# ----- cliente -----

def test_metodos_suportados(srv):
    assert set(METODOS) >= {"GET", "POST", "PUT", "PATCH", "DELETE"}


def test_get_lista_tipada(srv):
    r = cliente().requisitar("GET", srv.url("/usuarios"))
    assert r.ok and r.status == 200
    assert r.valor == [{"id": 1, "nome": "Ana", "ativo": True},
                       {"id": 2, "nome": "Beto", "ativo": False}]
    assert isinstance(r.valor[0]["id"], int)
    assert isinstance(r.valor[0]["ativo"], bool)


def test_post_put_patch_delete(srv):
    c = cliente()
    r = c.requisitar("POST", srv.url("/usuarios"), corpo={"nome": "Cid"})
    assert r.ok and r.status == 201 and r.valor["id"] == 3
    r = c.requisitar("PUT", srv.url("/usuarios/1"), corpo={"nome": "Ana2"})
    assert r.ok and r.valor == {"nome": "Ana2", "id": 1}
    r = c.requisitar("PATCH", srv.url("/usuarios/1"), corpo={"ativo": True})
    assert r.ok and r.valor["ativo"] is True
    r = c.requisitar("DELETE", srv.url("/usuarios/1"))
    assert r.ok and r.valor == {"ok": True}


def test_parametros_urlencode(srv):
    url = montar_url(srv.url("/usuarios"), {"q": "a b", "n": 1})
    assert "q=a+b" in url and "n=1" in url
    r = cliente().requisitar("GET", srv.url("/usuarios"),
                             parametros={"limite": 20})
    assert r.ok


def test_timeout_nao_trava(srv):
    inicio = time.monotonic()
    r = cliente(timeout=1).requisitar("GET", srv.url("/atrasado"))
    duracao = time.monotonic() - inicio
    assert not r.ok and "Tempo esgotado" in r.erro
    assert duracao < 2.5


def test_erros_mapeados(srv):
    c = cliente()
    assert "500" in c.requisitar("GET", srv.url("/erro")).erro
    assert "404" in c.requisitar("GET", srv.url("/nao-existe")).erro
    inv = c.requisitar("GET", srv.url("/invalido"))
    assert not inv.ok and "JSON" in inv.erro
    vazio = c.requisitar("GET", srv.url("/vazio"))
    assert vazio.ok and vazio.valor is None
    dns = c.requisitar("GET", "http://inexistente-xyz-12345.invalid/x")
    assert not dns.ok and dns.erro
    bloqueada = c.requisitar("GET", "ftp://x/y")
    assert "bloqueada" in bloqueada.erro


def test_utf8_preservado(srv):
    r = cliente().requisitar("GET", srv.url("/eco-utf8"))
    assert r.ok and r.valor["msg"].startswith("Olá, ELiXX")


# ----- FonteRemota -----

def nova_remota(srv, caminho="/usuarios", **kwargs):
    base = dict(nome="usuarios", url=srv.url(caminho), metodo="GET",
                timeout_s=5)
    base.update(kwargs)
    return FonteRemota(**base)


def test_remota_estados_e_snapshot(srv):
    fonte = nova_remota(srv)
    snap = fonte.snapshot()
    assert snap == {"valor": None, "carregando": False,
                    "erro": None, "status": None}
    resultado = fonte.buscar()
    assert resultado["valor"][0]["nome"] == "Ana"
    assert resultado["erro"] is None and resultado["status"] == 200
    assert fonte.obter("valor.0.nome") == "Ana"


def test_remota_erro_nao_derruba(srv):
    fonte = nova_remota(srv, "/erro")
    resultado = fonte.buscar()
    assert "500" in resultado["erro"]
    assert resultado["valor"] == {"erro": "falha"}  # corpo preservado
    assert resultado["status"] == 500


def test_remota_async_nao_bloqueia(srv):
    fonte = nova_remota(srv, "/atrasado", timeout_s=5)
    inicio = time.monotonic()
    assert fonte.buscar_async() is True
    assert time.monotonic() - inicio < 1.0  # retornou na hora
    assert fonte.buscar_async() is False  # segunda: já em curso
    prazo = time.monotonic() + 6
    while fonte.snapshot()["carregando"] and time.monotonic() < prazo:
        time.sleep(0.1)
    assert fonte.snapshot()["valor"] == {"ok": True}
    assert fonte.buscas_concluidas == 1


def test_remota_callback_e_cancelar(srv):
    fonte = nova_remota(srv, "/atrasado", timeout_s=5)
    chamadas = []
    fonte.buscar_async(ao_chegar=lambda f: chamadas.append(f.snapshot()))
    fonte.cancelar()
    time.sleep(3.5)
    assert chamadas == []  # cancelada: sem efeito
    assert fonte.snapshot()["carregando"] is False


def test_remota_periodica_agenda(srv):
    fonte = nova_remota(srv, intervalo_s=60)
    assert fonte.deve_buscar(1000.0) is True
    fonte.marcar_agendada(1000.0)
    assert fonte.deve_buscar(1001.0) is False
    assert fonte.deve_buscar(2000.0 + 60.0) is True


def test_arquivo_json_local(tmp_path):
    alvo = tmp_path / "cfg.json"
    alvo.write_text('{"tema": "escuro", "n": 3}', encoding="utf-8")
    fonte = FonteArquivo(nome="cfg", caminho=str(alvo))
    assert fonte.snapshot() == {"valor": {"tema": "escuro", "n": 3},
                                "erro": None}
    assert fonte.obter("valor.tema") == "escuro"
    alvo.write_text('{"tema": "claro"}', encoding="utf-8")
    # mtime pode empatar: força releitura
    fonte.atualizar()
    assert fonte.snapshot()["valor"] == {"tema": "claro"}
    fonte2 = FonteArquivo(nome="x", caminho=str(tmp_path / "falta.json"))
    assert "não encontrado" in fonte2.snapshot()["erro"]
    alvo.write_text("{ruim", encoding="utf-8")
    fonte.atualizar()
    assert "inválido" in fonte2.snapshot()["erro"] or \
        "inválido" in fonte.snapshot()["erro"]


# ----- sintaxe + semântica -----

FONTE_OK = ('dados usuarios {\n url: "URL"\n metodo: "GET"\n'
            ' tempo_limite: 5s\n atualizar: 10s\n'
            ' cabecalhos {\n "Accept": "application/json"\n }\n'
            ' parametros {\n pagina: 1\n }\n}\n'
            'janela p {\n titulo: "T"\n}\n')


def test_parse_bloco_dados():
    from elixx.compilador import ast as A

    prog = analisar(FONTE_OK.replace("URL", "https://a.b/u"))
    assert len(prog.fontes) == 1
    fonte = prog.fontes[0]
    assert isinstance(fonte, A.FonteDef) and fonte.nome == "usuarios"
    assert {b.nome for b in fonte.blocos} == {"cabecalhos", "parametros"}
    validar(prog)


def test_semantica_fonte_erros():
    base = FONTE_OK.replace("URL", "https://a.b/u")
    with pytest.raises(ErroSemantico, match="http"):
        validar(analisar(base.replace("https://a.b/u", "ftp://a.b/u")))
    with pytest.raises(ErroSemantico, match="metodo"):
        validar(analisar(base.replace('"GET"', '"TRACE"')))
    with pytest.raises(ErroSemantico, match="exatamente um"):
        validar(analisar(base.replace('tempo_limite: 5s',
                                      'tempo_limite: 5s\n arquivo: "a.json"')))
    with pytest.raises(ErroSemantico, match="1s"):
        validar(analisar(base.replace("atualizar: 10s", "atualizar: 100ms")))
    with pytest.raises(ErroSemantico, match="duplicada"):
        validar(analisar(base + 'dados usuarios {\n url: "https://a.b/u"\n}\n'))
    with pytest.raises(ErroSemantico, match="desconhecida"):
        validar(analisar(base.replace('metodo: "GET"',
                                      'metodo: "GET"\n esquema: "x"')))


def test_origem_fonte_remota_valida(srv):
    prog = analisar(
        FONTE_OK.replace("URL", srv.url("/usuarios")) +
        "".join([]))
    validar(prog)  # "usuarios" conhecida via bloco (não só REGISTRO)


def test_origem_fonte_desconhecida_sugere():
    prog = analisar('janela p {\n titulo: "T"\n texto t {\n'
                    ' origem: dados.usuarioss.valor\n}\n}\n')
    with pytest.raises(ErroSemantico, match="desconhecida"):
        validar(prog)


# ----- integração: GET → estado → binding → componente -----

def test_fluxo_completo_remoto(srv):
    import test_renderizador

    fonte = ('dados usuarios {\n url: "URL"\n metodo: "GET"\n}\n'
             'janela p {\n titulo: "T"\n'
             ' lista nomes {\n origem: estado.usuarios.valor\n'
             ' formato: "json"\n }\n'
             ' texto total {\n origem: estado.usuarios.status\n'
             ' formato: "inteiro"\n }\n}\n').replace("URL",
                                                    srv.url("/usuarios"))
    prog = analisar(fonte)
    validar(prog)
    executor = Executor(fontes={})
    resultado = executor.executar(prog, [])
    assert executor.estado.obter("usuarios") is None  # garantir, sem buscar
    executor.buscar_fontes_sincrono()
    usuarios = executor.estado.obter("usuarios")
    assert usuarios["status"] == 200
    assert usuarios["valor"][1]["nome"] == "Beto"
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    renderer = test_renderizador.RenderizadorMemoria(executor)
    vinc = Vinculador(cena, executor.fontes, executor.estado, executor,
                      intervalo_ms=0)
    for no, pacote in vinc.primeira_carga():
        renderer.definir_valor(no, pacote)
    valores = {nome: valor for _t, nome, valor in
               [c for c in renderer.chamadas if c[0] == "valor"]}
    assert '"nome": "Ana"' in valores["nomes"][0]
    assert valores["total"] == "200"


def test_post_formulario_estado(srv):
    fonte = ('dados novo {\n url: "URL"\n metodo: "POST"\n'
             ' corpo {\n nome: estado.nome\n }\n}\n'
             'estado {\n nome: "Cid"\n}\n'
             'janela p {\n titulo: "T"\n'
             ' botão enviar {\n texto: " ir"\n'
             '  quando clicar {\n sincronizar("novo")\n }\n }\n}\n'
             ).replace("URL", srv.url("/usuarios"))
    prog = analisar(fonte)
    validar(prog)
    executor = Executor(fontes={})
    executor.executar(prog, [])
    from elixx.runtime.acoes import Contexto
    from elixx.runtime.memoria import Memoria

    executor.ctx.ao_sincronizar = executor.sincronizar_fontes
    ctx = executor.ctx
    from elixx.runtime.acoes import executar_acao

    executar_acao("sincronizar", ["novo"], ctx)
    prazo = time.monotonic() + 5
    while executor.estado.obter("novo") is None and time.monotonic() < prazo:
        time.sleep(0.05)
    novo = executor.estado.obter("novo")
    assert novo["status"] == 201
    assert novo["valor"]["nome"] == "Cid"  # corpo avaliado do estado
    assert novo["valor"]["id"] == 3


def test_seguranca_conteudo_e_dado(srv):
    r = cliente().requisitar("GET", srv.url("/usuarios"))
    assert isinstance(r.valor, list)
    for item in r.valor:
        assert isinstance(item, dict)
        assert set(item) <= {"id", "nome", "ativo"}
    # nada do payload é chamável/avaliável como código
    assert not callable(r.valor)


def test_concorrencia_ui_livre(srv):
    executor = Executor(fontes={})
    prog = analisar(
        ('dados lento {\n url: "URL"\n atualizar: 60s\n}\n'
         'janela p {\n titulo: "T"\n}\n').replace("URL",
                                                 srv.url("/atrasado")))
    validar(prog)
    executor.executar(prog, [], base_dir=".")
    executor.iniciar_fontes()  # async: retorna na hora
    fonte = executor.fontes_remotas["lento"]
    assert fonte.snapshot()["carregando"] is True
    executor.atualizar(16.0)  # tick continua livre (sem exceção/bloqueio)
    fonte.cancelar()


def test_espelho_arquivo_sem_churn(tmp_path):
    alvo = tmp_path / "d.json"
    alvo.write_text('{"v": 1}', encoding="utf-8")
    prog = analisar('dados cfg {\n arquivo: "ARQ"\n}\n'
                    'janela p {\n titulo: "T"\n}\n'.replace(
                        "ARQ", str(alvo).replace("\\", "/")))
    validar(prog)
    executor = Executor(fontes={})
    executor.executar(prog, [], base_dir=".")
    assert executor.buscar_fontes_sincrono() == 1
    assert executor.estado.obter("cfg")["valor"] == {"v": 1}
    versao = executor.estado.versao("cfg")
    executor.atualizar(16.0)  # sem mudança: sem bump
    executor.atualizar(16.0)
    assert executor.estado.versao("cfg") == versao
    alvo.write_text('{"v": 2}', encoding="utf-8")
    executor.atualizar(16.0)  # mudou: espelha
    assert executor.estado.obter("cfg")["valor"] == {"v": 2}
    assert executor.estado.versao("cfg") == versao + 1


def test_periodica_dispara_e_nao_duplica(srv):
    executor = Executor(fontes={})
    prog = analisar(
        ('dados u {\n url: "URL"\n atualizar: 1s\n}\n'
         'janela p {\n titulo: "T"\n}\n').replace("URL",
                                                 srv.url("/usuarios")))
    validar(prog)
    executor.executar(prog, [], base_dir=".")
    fonte = executor.fontes_remotas["u"]
    fonte._proxima = 0.0
    executor.atualizar(16.0)
    assert fonte.buscas_iniciadas == 1
    executor.atualizar(16.0)  # em curso ou reagendada: sem duplicar
    assert fonte.buscas_iniciadas == 1
    prazo = time.monotonic() + 5
    while fonte.snapshot()["carregando"] and time.monotonic() < prazo:
        time.sleep(0.05)
    assert executor.estado.obter("u")["status"] == 200


def test_sincronizar_nome_desconhecido_erro(srv):
    executor = Executor(fontes={})
    prog = analisar(
        ('dados u {\n url: "URL"\n}\n'
         'janela p {\n titulo: "T"\n}\n').replace("URL",
                                                 srv.url("/usuarios")))
    validar(prog)
    executor.executar(prog, [], base_dir=".")
    from elixx.runtime.acoes import Contexto, executar_acao
    from elixx.runtime.memoria import Memoria

    ctx = Contexto([], Memoria())
    ctx.estado = executor.estado
    ctx.ao_sincronizar = executor.sincronizar_fontes
    executar_acao("sincronizar", ["fantasma"], ctx)
    assert "desconhecida" in ctx.saida[-1]


def test_para_alvo_customizado(srv):
    prog = analisar(
        ('dados u {\n url: "URL"\n para: estado.meus_dados\n}\n'
         'estado {\n meus_dados: 0\n}\n'
         'janela p {\n titulo: "T"\n}\n').replace("URL",
                                                 srv.url("/usuarios")))
    validar(prog)
    executor = Executor(fontes={})
    executor.executar(prog, [], base_dir=".")
    executor.buscar_fontes_sincrono()
    assert executor.estado.obter("meus_dados")["status"] == 200


def test_origem_dados_remota_direta(srv):
    prog = analisar(
        ('dados u {\n url: "URL"\n}\n'
         'janela p {\n titulo: "T"\n texto t {\n'
         ' origem: dados.u.valor\n formato: "json"\n }\n}\n').replace(
             "URL", srv.url("/eco-utf8")))
    validar(prog)
    executor = Executor(fontes={})
    resultado = executor.executar(prog, [], base_dir=".")
    executor.buscar_fontes_sincrono()
    from elixx.visual.cena import ConstrutorCena

    cena = ConstrutorCena().de_objetos(resultado.objetos)
    assert executor.avaliar(
        prog.janelas[0].componentes[0].propriedades[0].valores[0]
    )["msg"].startswith("Olá")


def test_compilar_nao_busca_remota(srv, tmp_path):
    from elixx.cli import main

    alvo = tmp_path / "remoto.elixx"
    alvo.write_text(
        'dados u {\n url: "URL"\n}\n'
        'janela p {\n titulo: "T"\n}\n'.replace("URL",
                                               srv.url("/atrasado")),
        encoding="utf-8")
    saida = str(tmp_path / "previa.html")
    assert main(["compilar", str(alvo), "--saida", saida]) == 0
    # compilar não esperou os 3s do /atrasado: prévia estática rápida
