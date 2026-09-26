"""CLI da ELiXX.

    elixx executar programa.elixx [--clicar nome_botao]
    elixx verificar programa.elixx
    elixx compilar programa.elixx [--saida pagina.html]
    elixx versao
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .compilador import ast as A  # noqa: F401 (uso futuro /utiveis)
from .compilador.ast import mostrar_arvore
from .compilador.lexer import tokenizar
from .compilador.parser import Parser
from .compilador.semantica import validar
from .erros import ErroELiXX
from .runtime.nucleo import Executor
from .visual.html import gerar_html


def ler_fonte(caminho: str) -> str:
    arquivo = Path(caminho)
    if not arquivo.exists():
        raise ErroELiXX(
            f"Arquivo não encontrado: {caminho}.",
            sugestao="Verifique o caminho. Exemplos estão em exemplos/.",
        )
    if arquivo.suffix.lower() != ".elixx":
        raise ErroELiXX(
            f"Extensão inesperada: {arquivo.suffix!r}. Arquivos ELiXX usam .elixx.",
            sugestao="Renomeie para programa.elixx.",
        )
    return arquivo.read_text(encoding="utf-8")


def pipeline(caminho: str):
    """Lexer → parser → imports → componentes → semântica."""
    from .compilador.componentes import expandir_componentes
    from .compilador.modulos import carregar_programa

    programa = carregar_programa(caminho)
    expandir_componentes(programa)
    avisos = validar(programa)
    return programa, avisos


def cmd_executar(args) -> int:
    try:
        programa, avisos = pipeline(args.arquivo)
    except ErroELiXX as e:
        print(e, file=sys.stderr)
        return 1
    if args.mostrar_arvore:
        print(mostrar_arvore(programa))
        print("---")
    for aviso in avisos:
        print(f"Aviso (linha {aviso.linha}): {aviso.mensagem}")
    if args.sem_janela:
        return _executar_simulado(programa, avisos, args,
                                  base=_base_dir(args.arquivo))
    try:
        from .visual.nativo import executar_nativo
        return executar_nativo(programa, avisos, clicar=args.clicar,
                               base_dir=_base_dir(args.arquivo))
    except ErroELiXX as e:
        print(e, file=sys.stderr)
        return 1


def _base_dir(arquivo: str) -> str:
    pai = Path(arquivo).resolve().parent
    return str(pai)


def _executar_simulado(programa, avisos, args, base: str = ".") -> int:
    """Sem janela (testes e CI). Fase 06: busca remota SÍNCRONA única."""
    executor = Executor()
    try:
        resultado = executor.executar(programa, avisos, base_dir=base)
        executor.buscar_fontes_sincrono()
        if args.clicar:
            houve = executor.simular_clique(args.clicar)
            # re-sincroniza saída após o clique simulado
            resultado.saida = list(executor.ctx.saida)
            if not houve:
                print(f"O componente {args.clicar!r} não trata o evento clicar.")
        for linha_saida in resultado.saida:
            print(linha_saida)
        print(f"[ELiXX] {resultado.texto_janelas()}")
        for aviso_extra in executor.avisos:
            print(f"Aviso: {aviso_extra}")
    except ErroELiXX as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cmd_verificar(args) -> int:
    try:
        _programa, avisos = pipeline(args.arquivo)
    except ErroELiXX as e:
        print(e, file=sys.stderr)
        return 1
    if avisos:
        for aviso in avisos:
            print(f"Aviso (linha {aviso.linha}): {aviso.mensagem}")
    print(f"OK: {args.arquivo} válido ({len(avisos)} aviso(s)).")
    return 0


def cmd_compilar(args) -> int:
    try:
        programa, avisos = pipeline(args.arquivo)
    except ErroELiXX as e:
        print(e, file=sys.stderr)
        return 1
    executor = Executor()
    try:
        # HTML é prévia estática: fontes remotas NÃO são buscadas aqui
        # (documentado em docs/http.md). Use executar para dados vivos.
        resultado = executor.executar(
            programa, avisos, base_dir=_base_dir(args.arquivo))
    except ErroELiXX as e:
        print(e, file=sys.stderr)
        return 1
    destino = args.saida or (Path(args.arquivo).stem + ".html")
    Path(destino).write_text(
        gerar_html(resultado.objetos,
                   temas=executor.temas, tema_atual=executor.tema_atual),
        encoding="utf-8")
    print(f"[ELiXX] Página gerada: {destino}")
    return 0


def cmd_versao(_args) -> int:
    print(f"ELiXX {__version__} (Fase 02 — renderer nativo)")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="elixx",
                                description="ELiXX — linguagem visual em português")
    sub = p.add_subparsers(dest="comando", required=True)

    e = sub.add_parser("executar", help="executa um programa .elixx")
    e.add_argument("arquivo")
    e.add_argument("--clicar", default=None,
                   help="simula o clique num componente (ex. --clicar teste)")
    e.add_argument("--sem-janela", action="store_true",
                   help="executa sem abrir janela (modo Fase 01; testes e CI)")
    e.add_argument("--mostrar-arvore", action="store_true",
                   help="imprime a AST antes de executar")
    e.set_defaults(funcao=cmd_executar)

    v = sub.add_parser("verificar", help="valida sem executar")
    v.add_argument("arquivo")
    v.set_defaults(funcao=cmd_verificar)

    c = sub.add_parser("compilar", help="gera página HTML de prévia")
    c.add_argument("arquivo")
    c.add_argument("--saida", default=None)
    c.set_defaults(funcao=cmd_compilar)

    s = sub.add_parser("versao", help="mostra a versão")
    s.set_defaults(funcao=cmd_versao)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = construir_parser().parse_args(argv)
    return args.funcao(args)


def entrada() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrada()
