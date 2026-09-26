"""Testes do dashboard: exemplo válido, compatibilidade dos exemplos
antigos e integração vinculador → renderer (double)."""
from pathlib import Path

from elixx.cli import main
from elixx.compilador.parser import analisar
from elixx.compilador.semantica import validar
from elixx.dados import FonteFalsa
from elixx.runtime.nucleo import Executor
from elixx.visual.cena import ConstrutorCena
from elixx.visual.reativo import Vinculador

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"


def test_dashboard_verificar(capsys):
    assert main(["verificar", str(EXEMPLOS / "dashboard.elixx")]) == 0
    assert "OK" in capsys.readouterr().out


def test_dashboard_headless_executa(capsys):
    assert main(["executar", "--sem-janela",
                 str(EXEMPLOS / "dashboard.elixx")]) == 0
    saida = capsys.readouterr().out
    assert "Monitor iniciado" in saida
    assert "1100x700" in saida


def test_exemplos_antigos_continuam_validos(capsys):
    for nome in ["interface.elixx", "interface-completa.elixx",
                 "programa.elixx", "eventos.elixx", "cores-unidades.elixx",
                 "logica.elixx"]:
        assert main(["verificar", str(EXEMPLOS / nome)]) == 0, nome
        capsys.readouterr()


def test_vinculador_para_renderer_double():
    import test_renderizador
    RenderizadorMemoria = test_renderizador.RenderizadorMemoria

    fonte = ("janela p {\n titulo: \"T\"\n"
             " texto t {\n origem: dados.falsa.sistema.cpu\n"
             " formato: \"percentual\"\n }\n"
             " barra b {\n origem: dados.falsa.sistema.cpu\n }\n}\n")
    prog = analisar(fonte)
    validar(prog)
    executor = Executor(
        fontes={"falsa": FonteFalsa({"sistema": {"cpu": 55.0}})})
    resultado = executor.executar(prog, [])
    cena = ConstrutorCena().de_objetos(resultado.objetos)
    renderer = RenderizadorMemoria(executor)
    renderer.montar(cena)
    vinc = Vinculador(cena, executor.fontes, intervalo_ms=0)
    for no, pacote in vinc.atualizar(0.0):
        renderer.definir_valor(no, pacote)
    assert ("valor", "t", "55%") in renderer.chamadas
    assert ("valor", "b", 55.0) in renderer.chamadas


def test_dashboard_tipos_novos_na_cena():
    prog = analisar((EXEMPLOS / "dashboard.elixx").read_text(
        encoding="utf-8"))
    validar(prog)
    executor = Executor(fontes={"falsa": FonteFalsa({"sistema": {}})})
    cena = ConstrutorCena().de_objetos(
        executor.executar(prog, []).objetos)
    jan = cena.janelas[0]
    tipos = {n.tipo for n in jan.todos()}
    assert {"painel", "cartao", "barra", "grafico", "lista",
            "texto", "botao"} <= tipos
    com_origem = [n for n in jan.todos() if n.origem]
    assert len(com_origem) >= 15
    assert all(o.startswith(("dados.sistema.", "estado."))
               for o in (n.origem for n in com_origem))
    assert any(o.startswith("estado.") for o in
               (n.origem for n in com_origem))
