"""Testes da camada de dados: interface, fonte falsa (determinística)
e fumaça da fonte real (chaves e formatos, nunca valores)."""
import re

import pytest

from elixx.dados import (
    REGISTRO_FONTES,
    FonteFalsa,
    FonteSistema,
    registrar_fonte,
)
from elixx.erros import ErroExecucao


def test_registro_contem_fontes_conhecidas():
    assert set(REGISTRO_FONTES) >= {"sistema", "falsa"}


def test_registrar_nova_fonte_sem_mexer_em_nada():
    class MinhaFonte(FonteFalsa):
        nome = "minha"

    registrar_fonte("minha_teste", MinhaFonte)
    assert REGISTRO_FONTES["minha_teste"] is MinhaFonte
    del REGISTRO_FONTES["minha_teste"]


def test_falsa_obter_caminho():
    fonte = FonteFalsa({"sistema": {"cpu": 42.0,
                                    "ram": {"percentual": 68.0}}})
    assert fonte.obter("sistema.cpu") == 42.0
    assert fonte.obter("sistema.ram.percentual") == 68.0
    assert fonte.atualizar() is None
    assert fonte.atualizacoes == 1


def test_falsa_caminho_desconhecido_erro_em_portugues():
    fonte = FonteFalsa({"sistema": {}})
    with pytest.raises(ErroExecucao) as exc:
        fonte.obter("sistema.nao_existe")
    assert "desconhecido" in str(exc.value).lower()


def test_real_snapshot_tem_todas_as_chaves():
    dados = FonteSistema().snapshot()
    assert set(dados) >= {"cpu", "ram", "disco", "sistema",
                          "processos", "rede", "hora"}
    assert set(dados["ram"]) >= {"total", "disponivel", "usada",
                                 "percentual"}
    assert set(dados["disco"]) >= {"total", "livre", "usado", "percentual"}
    assert set(dados["sistema"]) >= {"so", "versao", "arquitetura",
                                     "computador", "python"}
    assert set(dados["processos"]) >= {"quantidade", "lista"}
    assert set(dados["rede"]) >= {"online", "interface", "enviados",
                                  "recebidos"}


def test_real_tipos_saudaveis_sem_valores_fixos():
    dados = FonteSistema().snapshot()
    assert isinstance(dados["cpu"], (int, float, str))
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", str(dados["hora"]))
    qtd = dados["processos"]["quantidade"]
    assert isinstance(qtd, int) and qtd >= 0
    assert isinstance(dados["processos"]["lista"], list)
    assert isinstance(dados["ram"]["total"], int)  # bytes reais
    assert dados["ram"]["total"] > 0
