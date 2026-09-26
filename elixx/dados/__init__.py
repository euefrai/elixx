"""ELiXX — camada de dados (fontes desacopladas do renderer)."""
from .fontes import (
    REGISTRO_FONTES,
    FonteDados,
    FonteFalsa,
    FonteSistema,
    registrar_fonte,
)
from .http import METODOS, ClienteHttp, Resposta, montar_url
from .remoto import FonteArquivo, FonteRemota

__all__ = ["FonteDados", "FonteFalsa", "FonteSistema",
           "REGISTRO_FONTES", "registrar_fonte",
           "ClienteHttp", "Resposta", "METODOS", "montar_url",
           "FonteRemota", "FonteArquivo"]
