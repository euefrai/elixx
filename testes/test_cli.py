"""Testes da CLI: execução, validação, compilação, versão e erros."""
from pathlib import Path

from elixx.cli import main

PROGRAMA = ('janela principal {\n titulo: "App"\n tamanho: 800px 600px\n'
            ' botão teste {\n texto: "Olá"\n'
            ' quando clicar {\n mostrar("Olá, mundo!")\n }\n }\n}')


def escrever(tmp_path: Path, nome: str = 'programa.elixx') -> str:
    alvo = tmp_path / nome
    alvo.write_text(PROGRAMA, encoding='utf-8')
    return str(alvo)


def test_executar_ok(tmp_path, capsys):
    # Fase 02: executar abre janela por padrão; --sem-janela preserva o
    # comportamento Fase 01 (usado aqui para o teste ser headless).
    assert main(['executar', '--sem-janela', escrever(tmp_path)]) == 0
    assert 'principal' in capsys.readouterr().out


def test_executar_com_clique(tmp_path, capsys):
    assert main(['executar', '--sem-janela', escrever(tmp_path),
                 '--clicar', 'teste']) == 0
    assert 'Olá, mundo!' in capsys.readouterr().out


def test_verificar_ok(tmp_path, capsys):
    assert main(['verificar', escrever(tmp_path)]) == 0
    assert 'OK' in capsys.readouterr().out


def test_verificar_erro_retorna_1(tmp_path, capsys):
    ruim = tmp_path / 'ruim.elixx'
    ruim.write_text('janela a {\n titulo: "x"\n', encoding='utf-8')
    assert main(['verificar', str(ruim)]) == 1
    assert 'Erro ELiXX' in capsys.readouterr().err


def test_compilar_gera_html(tmp_path):
    saida = str(tmp_path / 'previa.html')
    assert main(['compilar', escrever(tmp_path), '--saida', saida]) == 0
    conteudo = Path(saida).read_text(encoding='utf-8')
    assert '<button' in conteudo and 'Olá, mundo!' in conteudo


def test_versao(capsys):
    assert main(['versao']) == 0
    assert 'ELiXX' in capsys.readouterr().out


def test_arquivo_inexistente_erro_pt(tmp_path, capsys):
    assert main(['verificar', str(tmp_path / 'falta.elixx')]) == 1
    assert 'não encontrado' in capsys.readouterr().err.lower()
