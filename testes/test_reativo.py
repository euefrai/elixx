"""Testes da reatividade: Vinculador, formatos, ações de dados e
avaliação de caminhos dados.fonte.campo (tudo com FonteFalsa)."""
import pytest

from elixx.compilador import ast as A
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.dados import FonteFalsa
from elixx.erros import ErroExecucao, ErroSemantico
from elixx.runtime.acoes import Contexto, executar_acao
from elixx.runtime.memoria import Memoria
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.reativo import Vinculador, formatar_valor

FONTE = ('janela p {\n titulo: "T"\n'
         ' texto t_cpu {\n origem: dados.falsa.sistema.cpu\n'
         ' formato: "percentual"\n }\n'
         ' barra b_ram {\n origem: dados.falsa.sistema.ram.percentual\n }\n'
         ' grafico g_cpu {\n origem: dados.falsa.sistema.cpu\n }\n'
         ' lista l_proc {\n origem: dados.falsa.sistema.processos.lista\n }\n'
         '}\n')


def fonte_padrao():
    return FonteFalsa({
        "sistema": {
            "cpu": 32.0,
            "ram": {"percentual": 68.0, "total": 8000000000},
            "processos": {"quantidade": 42, "lista": ["a.exe", "b.exe"]},
            "hora": "12:00:00",
        }
    })


def montar():
    prog = analisar(FONTE)
    validar(prog)
    executor = Executor(fontes={"falsa": fonte_padrao()})
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    return executor, cena, Vinculador(cena, executor.fontes,
                                     intervalo_ms=1000000)


def test_membro_parse_e_caminho():
    prog = analisar(FONTE)
    prop = prog.janelas[0].componentes[0].propriedades[0]
    assert prop.nome == "origem"
    no = prop.valores[0]
    assert isinstance(no, A.Membro)
    assert A.caminho_de_membro(no) == "dados.falsa.sistema.cpu"


def test_origem_invalida_erro_em_portugues():
    with pytest.raises(ErroSemantico) as exc:
        analisar_e_validar_origem("dados.desconhecida.cpu")
    assert "Fonte de dados desconhecida" in str(exc.value)
    with pytest.raises(ErroSemantico):
        analisar_e_validar_origem("dados.sistema")
    with pytest.raises(ErroSemantico):
        analisar_e_validar_origem("texto simples")


def analisar_e_validar_origem(origem_src):
    fonte = ("janela p {\n titulo: \"T\"\n texto t {\n origem: "
             + origem_src + "\n }\n}\n")
    return validar(analisar(fonte))


def membro_caminho(*partes):
    no = A.Ident(nome=partes[0])
    for parte in partes[1:]:
        no = A.Membro(base=no, atributo=parte)
    return no


def test_avaliar_membro_com_fonte_falsa():
    executor, _cena, _v = montar()
    assert executor.avaliar_membro(
        membro_caminho("dados", "falsa", "sistema", "cpu")) == 32.0
    assert executor.avaliar_membro(
        membro_caminho("dados", "falsa", "sistema", "ram",
                       "percentual")) == 68.0
    with pytest.raises(ErroExecucao):  # caminho incompleto p/ fonte
        executor.avaliar_membro(membro_caminho("dados", "falsa"))


def test_dados_sozinho_erro_que_ensina():
    executor, _cena, _v = montar()
    with pytest.raises(ErroExecucao) as exc:
        executor.avaliar(A.Ident(nome="dados"))
    assert "dados.sistema.cpu" in str(exc.value)


def test_vinculador_pacotes_formatados():
    _ex, cena, vinc = montar()
    pacotes = dict((n.nome, p) for n, p in vinc.atualizar(0.0))
    assert pacotes["t_cpu"] == "32%"
    assert pacotes["b_ram"] == 68.0
    assert pacotes["l_proc"] == ["a.exe", "b.exe"]
    assert cena.buscar("g_cpu").historico == [32.0]


def test_vinculador_respeita_intervalo_e_forca():
    _ex, _cena, vinc = montar()
    assert vinc.atualizar(0.0) != []
    assert vinc.atualizar(1.0) == []  # intervalo de 1000s não venceu
    assert vinc.atualizar_agora() != []  # forçado passa


def test_vinculador_automatico_off():
    _ex, _cena, vinc = montar()
    assert vinc.alternar() is False
    vinc._forcar = False
    assert vinc.atualizar(999999.0) == []
    assert vinc.alternar() is True


def test_grafico_historico_limitado():
    _ex, cena, vinc = montar()
    no = cena.buscar("g_cpu")
    for i in range(70):
        vinc._pacote(no, float(i))
    assert len(no.historico) == 60
    assert no.historico[-1] == 69.0


def test_formatos():
    assert formatar_valor(37.0, "percentual") == "37%"
    assert formatar_valor(8000000000, "gb") == "8,0 GB"
    assert formatar_valor(10455289, "mb") == "10,5 MB"
    assert formatar_valor(42.0, "inteiro") == "42"
    assert formatar_valor("indisponível", "percentual") == "indisponível"
    assert formatar_valor("12:00:00", "texto") == "12:00:00"


def test_acoes_exibir_e_sair():
    executor, _cena, _v = montar()
    ctx = Contexto(executor.ctx.objetos, Memoria())
    alvo = executor.ctx.objetos[0].buscar("g_cpu")
    executar_acao("esconder", ["g_cpu"], ctx)
    assert alvo.visivel is False
    executar_acao("exibir", ["g_cpu"], ctx)
    assert alvo.visivel is True
    chamadas = []
    ctx.ao_sair = lambda: chamadas.append("saiu")
    executar_acao("sair", [], ctx)
    assert chamadas == ["saiu"]


def test_acoes_atualizar_e_alternar():
    executor, cena, vinc = montar()
    ctx = Contexto(executor.ctx.objetos, Memoria())
    ctx.vinculador = vinc
    msgs = []
    ctx.ao_mostrar = msgs.append
    executar_acao("atualizar_dados", [], ctx)
    assert "dados atualizados" in ctx.saida[-1]
    executar_acao("alternar_atualizacao", [], ctx)
    assert vinc.automatico is False
    assert "OFF" in msgs[-1]
