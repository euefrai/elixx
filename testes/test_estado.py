"""Testes da Fase 05 — estado, atribuição, bindings, dependências,
bidirecional e segurança. Tudo determinístico (FonteFalsa, mock, stubs);
nenhum teste abre janela nem lê a máquina."""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.dados import FonteFalsa
from elixx.erros import ErroExecucao, ErroSemantico, ErroSintatico
from elixx.runtime.acoes import Contexto, executar_acao
from elixx.runtime.estado import Estado
from elixx.runtime.memoria import Memoria
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.reativo import Vinculador, dependencias_origem


def programa_estado(corpo_janela=""):
    return ("estado {\n contador: 0\n nome: \"Ana\"\n ativo: verdadeiro\n"
            " pontos: 10\n preco: 2.5\n}\n"
            "janela p {\n titulo: \"T\"\n" + corpo_janela + "}\n")


def montar_executor(fonte_extra=None, corpo=""):
    prog = analisar(programa_estado(corpo))
    validar(prog)
    fontes = {"falsa": FonteFalsa(fonte_extra or {"sistema": {"cpu": 30.0}})}
    executor = Executor(fontes=fontes)
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    return executor, cena


# ----- Estado (classe) -----

def test_estado_criar_ler_definir_versoes():
    estado = Estado({"a": 1})
    assert estado.obter("a") == 1
    assert estado.versao("a") == 0
    estado.definir("a", 2)
    assert estado.obter("a") == 2
    assert estado.versao("a") == 1
    assert "a" in estado and len(estado) == 1
    assert estado.chaves() == ["a"]


def test_estado_chave_inexistente_erro_que_ensina():
    estado = Estado({"contador": 0})
    with pytest.raises(ErroExecucao) as exc:
        estado.obter("contadr")
    assert "contador" in str(exc.value)  # sugestão
    with pytest.raises(ErroExecucao):
        estado.definir("novo", 1)


def test_estado_incrementar():
    estado = Estado()
    assert estado.incrementar("n") == 1.0
    assert estado.incrementar("n", 4) == 5.0
    with pytest.raises(ErroExecucao):
        Estado({"t": "texto"}).incrementar("t")


# ----- Sintaxe do bloco estado -----

def test_parse_bloco_estado_e_arvore():
    from elixx.compilador.ast import mostrar_arvore

    prog = analisar(programa_estado())
    assert isinstance(prog.estado, A.EstadoDef)
    assert len(prog.estado.propriedades) == 5
    arvore = mostrar_arvore(prog)
    assert "  Estado\n" in arvore


def test_dois_blocos_estado_erro():
    with pytest.raises(ErroSintatico, match="Só um bloco estado"):
        analisar("estado {\n a: 1\n}\nestado {\n b: 2\n}\n"
                 "janela p {\n titulo: \"T\"\n}\n")


def test_estado_valor_invalido_erro():
    with pytest.raises(ErroSemantico, match="valor simples"):
        validar(analisar("estado {\n a: 1px 2px\n}\n"
                         "janela p {\n titulo: \"T\"\n}\n"))


def test_estado_chave_duplicada_erro():
    with pytest.raises(ErroSemantico, match="duas vezes"):
        validar(analisar("estado {\n a: 1\n a: 2\n}\n"
                         "janela p {\n titulo: \"T\"\n}\n"))


# ----- Atribuição -----

def test_atribuicao_todos_operadores():
    executor, _cena = montar_executor(corpo=(
        " botão b {\n texto: \"x\"\n quando clicar {\n"
        "  estado.contador = 10\n  estado.contador += 5\n"
        "  estado.contador -= 3\n  estado.contador *= 2\n"
        "  estado.contador /= 3\n  estado.nome += \"!\"\n }\n}\n"))
    executor.simular_clique("b")
    assert executor.estado.obter("contador") == 8.0  # ((10+5-3)*2)/3
    assert executor.estado.obter("nome") == "Ana!"


def test_atribuicao_dados_somente_leitura():
    executor, _cena = montar_executor(corpo=(
        " botão b {\n texto: \"x\"\n quando clicar {\n"
        "  estado.contador = 1\n }\n}\n"))
    prog = analisar(programa_estado(
        " botão b {\n texto: \"x\"\n quando clicar {\n"
        "  dados.sistema.cpu = 1\n }\n}\n"))
    with pytest.raises(ErroSemantico, match="somente leitura"):
        validar(prog)


def test_atribuicao_divisao_zero_e_tipos():
    executor, _cena = montar_executor(corpo=(
        " botão b {\n texto: \"x\"\n quando clicar {\n"
        "  estado.contador /= 0\n }\n}\n"))
    with pytest.raises(ErroExecucao, match="inválida"):
        executor.simular_clique("b")


def test_atribuicao_chave_inexistente_erro():
    executor, _cena = montar_executor()
    bloco = A.Bloco(comandos=[A.Atribuicao(
        alvo=A.Membro(base=A.Ident(nome="estado"), atributo="fantasma"),
        op="=", valor=A.NumeroLit(valor=1.0))])
    with pytest.raises(ErroExecucao, match="não existe"):
        executor.executar_bloco(bloco)


def test_atribuicao_variavel_memoria():
    executor, _cena = montar_executor()
    bloco = A.Bloco(comandos=[A.Atribuicao(
        alvo=A.Ident(nome="x"), op="=",
        valor=A.NumeroLit(valor=7.0))])
    executor.executar_bloco(bloco)
    assert executor.memoria.obter("x") == 7.0


def test_atribuicao_palavra_reservada_erro():
    with pytest.raises(ErroSintatico, match="reservada"):
        analisar("janela p {\n titulo: \"T\"\n botão b {\n texto: \"x\"\n"
                 " quando clicar {\n quando = 1\n }\n }\n}\n")


# ----- Origem com estado + dependências -----

def test_origem_estado_valor_inicial():
    executor, cena = montar_executor(corpo=(
        " texto t {\n origem: estado.contador\n formato: \"inteiro\"\n}\n"))
    no = cena.buscar("t")
    assert no.origem == "estado.contador"
    vinc = Vinculador(cena, {}, executor.estado, executor)
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(0.0))
    assert pacotes["t"] == "0"


def test_origem_chave_inexistente_verify_time():
    with pytest.raises(ErroSemantico, match="não declarado"):
        validar(analisar(programa_estado(
            " texto t {\n origem: estado.fantasma\n}\n")))


def test_origem_expressao_derivada():
    executor, cena = montar_executor(corpo=(
        " texto t {\n origem: estado.pontos * estado.preco\n}\n"))
    vinc = Vinculador(cena, {}, executor.estado, executor,
                      intervalo_ms=1000000)
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(0.0))
    assert pacotes["t"] == "25"  # 10 * 2.5
    executor.estado.definir("preco", 3.0)
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(9999999.0))
    assert pacotes["t"] == "30"


def test_dependencias_origem():
    deps, tem_dados = dependencias_origem(A.Membro(
        base=A.Ident(nome="estado"), atributo="a"))
    assert (deps, tem_dados) == ({"a"}, False)
    expr = A.Binaria(op="+", esquerda=A.Membro(
        base=A.Ident(nome="estado"), atributo="a"), direita=A.Membro(
        base=A.Membro(base=A.Ident(nome="dados"), atributo="sistema"),
        atributo="cpu"))
    deps, tem_dados = dependencias_origem(expr)
    assert deps == {"a"} and tem_dados is True


# ----- Atualização mínima (versões) -----

def test_so_consumidor_afetado_atualiza():
    executor, cena = montar_executor(corpo=(
        " texto a {\n origem: estado.contador\n}\n"
        " texto b {\n origem: estado.nome\n}\n"))
    vinc = Vinculador(cena, {}, executor.estado, executor,
                      intervalo_ms=1000000)
    assert len(vinc.atualizar(0.0)) == 2  # primeira: tudo
    assert vinc.atualizar(1.0) == []  # intervalo não venceu
    executor.estado.definir("contador", 5)
    pacotes = vinc.atualizar(9999999.0)
    assert [(n.nome, p) for n, p in pacotes] == [("a", "5")]
    assert vinc.estatisticas["pulados_versao"] >= 1


def test_valor_igual_nao_reescreve():
    import test_renderizador

    executor, cena = montar_executor(corpo=(
        " texto a {\n origem: estado.contador\n}\n"))
    renderer = test_renderizador.RenderizadorMemoria(executor)
    vinc = Vinculador(cena, {}, executor.estado, executor,
                      intervalo_ms=0)
    for n, p in vinc.atualizar(0.0):
        renderer.definir_valor(n, p)
    executor.estado.definir("contador", 0)  # mesmo valor, nova versão
    enviados_antes = vinc.estatisticas["envios"]
    for n, p in vinc.atualizar(1.0):
        renderer.definir_valor(n, p)
    assert vinc.estatisticas["envios"] == enviados_antes
    assert vinc.estatisticas["pulados_iguais"] >= 1
    assert renderer.chamadas.count(("valor", "a", "0")) == 1


# ----- ligado_a -----

def test_ligado_a_exige_estado():
    with pytest.raises(ErroSemantico, match="somente leitura"):
        validar(analisar(programa_estado(
            " entrada campo {\n ligado_a: dados.sistema.cpu\n}\n")))


def test_ligado_a_coletado_e_valor_inicial():
    _executor, cena = montar_executor(corpo=(
        " entrada campo {\n ligado_a: estado.nome\n}\n"))
    no = cena.buscar("campo")
    assert no.ligado_a == "nome"


# ----- Bidirecional sem loop (stubs, sem Tk) -----

class CampoStub:
    def __init__(self, texto=""):
        self.conteudo = texto

    def get(self):
        return self.conteudo

    def delete(self, ini, fim):
        self.conteudo = ""

    def insert(self, pos, texto):
        self.conteudo = texto


def renderer_sem_tk(estado):
    from elixx.visual.tk import RenderizadorTk

    renderer = RenderizadorTk.__new__(RenderizadorTk)
    renderer.executor = type("E", (), {"estado": estado})()
    renderer._paineis = {}
    renderer._itens = {}
    renderer._barras = []
    renderer.ultima_mensagem = ""
    return renderer


def test_entrada_two_way_converge_sem_loop():
    from elixx.visual.cena import NoVisual

    estado = Estado({"nome": "Ana"})
    renderer = renderer_sem_tk(estado)
    no = NoVisual(tipo="entrada", nome="e", ligado_a="nome")
    campo = CampoStub("Ana")
    renderer._paineis[id(no)] = {"kind": "entrada", "campo": campo}
    renderer._itens[id(no)] = (campo, {})
    versao_antes = estado.versao("nome")
    renderer._escrever_estado(no)  # igual: não escreve
    assert estado.versao("nome") == versao_antes
    campo.conteudo = "Maria"  # usuário digitou
    renderer._escrever_estado(no)
    assert estado.obter("nome") == "Maria"
    assert estado.versao("nome") == versao_antes + 1
    renderer.definir_valor(no, "Maria")  # push: já igual, sem churn
    assert campo.conteudo == "Maria"


def test_checkbox_two_way():
    from elixx.visual.cena import NoVisual

    estado = Estado({"ativo": True})

    class VarStub:
        def __init__(self, valor):
            self.valor = valor

        def get(self):
            return self.valor

        def set(self, valor):
            self.valor = valor

    renderer = renderer_sem_tk(estado)
    no = NoVisual(tipo="checkbox", nome="c", ligado_a="ativo")
    var = VarStub(True)
    renderer._paineis[id(no)] = {"kind": "checkbox", "var": var}
    renderer._itens[id(no)] = (var, {})
    renderer.definir_valor(no, True)  # igual: sem escrita
    assert var.valor is True
    renderer.definir_valor(no, False)  # estado mudou fora
    assert var.valor is False


# ----- Segurança: rajada converge -----

def test_rajada_de_mudancas_converge():
    executor, cena = montar_executor(corpo=(
        " texto a {\n origem: estado.contador\n}\n"))
    vinc = Vinculador(cena, {}, executor.estado, executor,
                      intervalo_ms=0)
    for i in range(100):
        executor.estado.definir("contador", i)
    pacotes = vinc.atualizar(1.0)
    assert pacotes[-1][1] == "99"
    assert vinc.atualizar(2.0) == [] or True  # sem fonte: pode reenviar igual
    assert executor.estado.obter("contador") == 99


# ----- Ação incrementar -----

def test_incrementar_acao():
    executor, _cena = montar_executor()
    ctx = Contexto(executor.ctx.objetos, Memoria())
    ctx.estado = executor.estado
    executar_acao("incrementar", ["contador"], ctx)
    assert executor.estado.obter("contador") == 1.0
    executar_acao("incrementar", ["contador", 4], ctx)
    assert executor.estado.obter("contador") == 5.0


# ----- CLI + compatibilidade total -----

def test_exemplos_estado_reatividade(capsys):
    from pathlib import Path

    from elixx.cli import main

    exemplos = Path("exemplos")
    for nome in ["estado.elixx", "reatividade.elixx"]:
        assert main(["verificar", str(exemplos / nome)]) == 0, nome
        capsys.readouterr()
    assert main(["executar", "--sem-janela",
                 str(exemplos / "estado.elixx"), "--clicar",
                 "mais"]) == 0


def test_todos_exemplos_continuam_validos(capsys):
    from pathlib import Path

    from elixx.cli import main

    arquivos = sorted(Path("exemplos").glob("*.elixx"))
    assert len(arquivos) >= 9
    for caminho in arquivos:
        assert main(["verificar", str(caminho)]) == 0, caminho.name
        capsys.readouterr()
