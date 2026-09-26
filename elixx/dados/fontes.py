"""Fontes de dados da ELiXX.

Arquitetura:

    ELiXX → FonteDados (interface) → Runtime → Cena → Renderer

O renderer nunca sabe de onde veio o dado. `FonteSistema` lê dados REAIS
da máquina usando apenas a biblioteca padrão (ctypes/shutil/platform no
Windows). `FonteFalsa` é a fonte controlada usada nos testes — nenhum
teste depende de valores da máquina.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
import time
from abc import ABC, abstractmethod


class FonteDados(ABC):
    """Interface que toda fonte de dados ELiXX implementa."""
    nome = "base"

    @abstractmethod
    def atualizar(self) -> None:
        """Força uma nova leitura (próximo snapshot sai fresco)."""

    @abstractmethod
    def snapshot(self) -> dict:
        """Retorna os dados atuais como dicionário aninhado."""

    def obter(self, caminho: str):
        """Lê subcaminho: 'sistema.cpu', 'usuarios.valor.0.nome'.

        Partes numéricas indexam listas (JSON). Erro em português se
        não existir."""
        from ..erros import ErroExecucao

        atual: object = self.snapshot()
        for parte in caminho.split("."):
            if isinstance(atual, dict) and parte in atual:
                atual = atual[parte]
            elif isinstance(atual, (list, tuple)) and parte.lstrip(
                    "-").isdigit() and -len(atual) <= int(parte) < len(atual):
                atual = atual[int(parte)]
            else:
                raise ErroExecucao(
                    f"Caminho de dados desconhecido: {caminho!r}.",
                    sugestao="Exemplos: sistema.cpu, ram.percentual, "
                             "disco.livre, processos.quantidade, "
                             "usuarios.valor.0.nome.",
                )
        return atual


REGISTRO_FONTES: dict[str, type] = {}
"""Novas fontes entram aqui sem mexer na semântica nem no runtime."""


def registrar_fonte(nome: str, classe: type) -> None:
    REGISTRO_FONTES[nome] = classe


class FonteFalsa(FonteDados):
    """Fonte controlada para testes (valores definidos pelo teste)."""

    nome = "falsa"

    def __init__(self, valores: dict | None = None) -> None:
        self.valores = valores or {}
        self.atualizacoes = 0

    def atualizar(self) -> None:
        self.atualizacoes += 1

    def snapshot(self) -> dict:
        return {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in self.valores.items()}


class FonteSistema(FonteDados):
    """Dados REAIS da máquina (Windows via ctypes; outros SO: parcial).

    Cada campo é lido com proteção individual: se uma API falhar, aquele
    campo vira "indisponível" em vez de derrubar a aplicação. Somente
    leitura — nenhum comando administrativo, nenhuma alteração no sistema.
    """

    nome = "sistema"

    def __init__(self) -> None:
        self._cpu_amostra: tuple | None = None  # (ocioso, total)
        self._rede_base: tuple | None = None  # (enviados, recebidos)
        self._cache: dict = {}
        self._cache_hora: float = 0.0

    # ----- interface -----

    def atualizar(self) -> None:
        self._cache = {}
        self._cache_hora = 0.0

    def snapshot(self) -> dict:
        agora = time.monotonic()
        if self._cache and agora - self._cache_hora < 0.25:
            return self._cache
        dados = {
            "cpu": self._ler_cpu(),
            "ram": self._ler_ram(),
            "disco": self._ler_disco(),
            "sistema": self._ler_sistema(),
            "processos": self._ler_processos(),
            "rede": self._ler_rede(),
            "hora": time.strftime("%H:%M:%S"),
        }
        self._cache = dados
        self._cache_hora = agora
        return dados

    # ----- CPU (GetSystemTimes; % entre duas amostras) -----

    def _ler_cpu(self) -> float:
        try:
            import ctypes

            if os.name != "nt":
                return "indisponível"
            idle, kernel, user = self._tempos_sistema(ctypes)
            total = kernel + user
            amostra = (idle, total)
            anterior = self._cpu_amostra
            self._cpu_amostra = amostra
            if anterior is None:
                return 0.0
            ocioso_d = idle - anterior[0]
            total_d = total - anterior[1]
            if total_d <= 0:
                return 0.0
            return round(max(0.0, min(100.0,
                                     (1.0 - ocioso_d / total_d) * 100.0)), 1)
        except Exception:
            return "indisponível"

    @staticmethod
    def _tempos_sistema(ctypes) -> tuple[int, int, int]:
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("baixo", wintypes.DWORD),
                        ("alto", wintypes.DWORD)]

        kernel32 = ctypes.windll.kernel32
        ocioso, nucleo, usuario = FILETIME(), FILETIME(), FILETIME()
        if not kernel32.GetSystemTimes(ctypes.byref(ocioso),
                                       ctypes.byref(nucleo),
                                       ctypes.byref(usuario)):
            raise OSError("GetSystemTimes falhou")

        def inteiro(ft: FILETIME) -> int:
            return (ft.alto << 32) | ft.baixo

        return inteiro(ocioso), inteiro(nucleo), inteiro(usuario)

    # ----- RAM (GlobalMemoryStatusEx) -----

    def _ler_ram(self) -> dict:
        try:
            import ctypes
            from ctypes import wintypes

            if os.name != "nt":
                return {"total": "indisponível", "disponivel": "indisponível",
                        "usada": "indisponível", "percentual": "indisponível"}

            class ESTADO(ctypes.Structure):
                _fields_ = [
                    ("tamanho", wintypes.DWORD),
                    ("carga", wintypes.DWORD),
                    ("total_fis", ctypes.c_ulonglong),
                    ("disp_fis", ctypes.c_ulonglong),
                    ("total_pag", ctypes.c_ulonglong),
                    ("disp_pag", ctypes.c_ulonglong),
                    ("total_virt", ctypes.c_ulonglong),
                    ("disp_virt", ctypes.c_ulonglong),
                    ("disp_ext", ctypes.c_ulonglong),
                ]

            estado = ESTADO()
            estado.tamanho = ctypes.sizeof(ESTADO)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(
                    ctypes.byref(estado)):
                raise OSError("GlobalMemoryStatusEx falhou")
            total = int(estado.total_fis)
            disp = int(estado.disp_fis)
            usada = total - disp
            return {"total": total, "disponivel": disp, "usada": usada,
                    "percentual": round(usada / total * 100.0, 1)
                    if total else 0.0}
        except Exception:
            return {"total": "indisponível", "disponivel": "indisponível",
                    "usada": "indisponível", "percentual": "indisponível"}

    # ----- Disco (shutil, stdlib multiplataforma) -----

    def _ler_disco(self) -> dict:
        try:
            alvo = os.environ.get("SystemDrive", "C:") + os.sep
            uso = shutil.disk_usage(alvo)
            usado = uso.total - uso.free
            return {"total": uso.total, "livre": uso.free, "usado": usado,
                    "percentual": round(usado / uso.total * 100.0, 1)
                    if uso.total else 0.0}
        except Exception:
            return {"total": "indisponível", "livre": "indisponível",
                    "usado": "indisponível", "percentual": "indisponível"}

    # ----- Sistema (platform/os/sys) -----

    def _ler_sistema(self) -> dict:
        try:
            return {
                "so": platform.system() or "indisponível",
                "versao": platform.version() or "indisponível",
                "arquitetura": platform.machine() or "indisponível",
                "computador": (os.environ.get("COMPUTERNAME")
                               or platform.node() or "indisponível"),
                "python": platform.python_version(),
            }
        except Exception:
            return {"so": "indisponível", "versao": "indisponível",
                    "arquitetura": "indisponível",
                    "computador": "indisponível", "python": "indisponível"}

    # ----- Processos (Toolhelp32 snapshot; conta + nomes) -----

    def _ler_processos(self) -> dict:
        try:
            import ctypes
            from ctypes import wintypes

            if os.name != "nt":
                return {"quantidade": "indisponível", "lista": []}
            TH32CS_SNAPPROCESS = 0x00000002

            class ENTRADA(ctypes.Structure):
                _fields_ = [
                    ("tamanho", wintypes.DWORD),
                    ("uso", wintypes.DWORD),
                    ("pid", wintypes.DWORD),
                    # ULONG_PTR: 8 bytes no 64-bit (c_ulong tem 4 e quebra
                    # a estrutura com ERROR_BAD_LENGTH).
                    ("heap", ctypes.c_void_p),
                    ("modulo", wintypes.DWORD),
                    ("threads", wintypes.DWORD),
                    ("ppid", wintypes.DWORD),
                    ("prioridade", wintypes.LONG),
                    ("flags", wintypes.DWORD),
                    ("nome", wintypes.WCHAR * 260),
                ]

            kernel32 = ctypes.windll.kernel32
            foto = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if foto == wintypes.HANDLE(-1).value:
                raise OSError("Snapshot de processos falhou")
            try:
                entrada = ENTRADA()
                entrada.tamanho = ctypes.sizeof(ENTRADA)
                nomes: list[str] = []
                ok = kernel32.Process32FirstW(foto, ctypes.byref(entrada))
                while ok:
                    nomes.append(entrada.nome)
                    ok = kernel32.Process32NextW(foto, ctypes.byref(entrada))
            finally:
                kernel32.CloseHandle(foto)
            return {"quantidade": len(nomes),
                    "lista": sorted(set(nomes))[:12]}
        except Exception:
            return {"quantidade": "indisponível", "lista": []}

    # ----- Rede (GetIfTable; soma interfaces operacionais) -----

    def _ler_rede(self) -> dict:
        try:
            import ctypes
            from ctypes import wintypes

            if os.name != "nt":
                return {"online": "indisponível", "interface": "indisponível",
                        "enviados": "indisponível",
                        "recebidos": "indisponível"}
            iphlp = ctypes.windll.iphlpapi
            tamanho = wintypes.DWORD(0)
            iphlp.GetIfTable(None, ctypes.byref(tamanho), 0)
            bruto = ctypes.create_string_buffer(tamanho.value)
            if iphlp.GetIfTable(bruto, ctypes.byref(tamanho), 0) != 0:
                raise OSError("GetIfTable falhou")
            num = wintypes.DWORD.from_buffer(bruto).value

            class LINHA(ctypes.Structure):
                # MIB_IFROW COMPLETA: o passo entre linhas precisa ser o
                # tamanho real da estrutura (parar no meio desalinhava tudo).
                _fields_ = [
                    ("nome", wintypes.WCHAR * 256),
                    ("indice", wintypes.DWORD),
                    ("tipo", wintypes.DWORD),
                    ("mtu", wintypes.DWORD),
                    ("velocidade", wintypes.DWORD),
                    ("fis_len", wintypes.DWORD),
                    ("fis", wintypes.BYTE * 8),
                    ("admin", wintypes.DWORD),
                    ("oper", wintypes.DWORD),
                    ("mudanca", wintypes.DWORD),
                    ("entra_oct", wintypes.DWORD),
                    ("sai_oct", wintypes.DWORD),
                    ("entra_ucast", wintypes.DWORD),
                    ("entra_nucast", wintypes.DWORD),
                    ("entra_desc", wintypes.DWORD),
                    ("entra_err", wintypes.DWORD),
                    ("entra_desc_proto", wintypes.DWORD),
                    ("sai_ucast", wintypes.DWORD),
                    ("sai_nucast", wintypes.DWORD),
                    ("sai_desc", wintypes.DWORD),
                    ("sai_err", wintypes.DWORD),
                    ("sai_fila", wintypes.DWORD),
                    ("descr_len", wintypes.DWORD),
                    ("descr", wintypes.BYTE * 256),
                ]

            base = ctypes.addressof(bruto) + ctypes.sizeof(wintypes.DWORD)
            passo = ctypes.sizeof(LINHA)
            entra = sai = 0
            ativas = 0
            for i in range(num):
                linha = LINHA.from_address(base + i * passo)
                if linha.tipo == 24:  # 24 = loopback, sempre ignorado
                    continue
                # Critério documentado: operacional (1) OU com tráfego real.
                # Interfaces virtuais/VPN costumam ficar "dormentes" (5)
                # mesmo trafegando — só o oper==1 as excluiria de verdade.
                com_trafego = (linha.entra_oct + linha.sai_oct) > 0
                if linha.oper == 1 or com_trafego:
                    entra += linha.entra_oct
                    sai += linha.sai_oct
                    ativas += 1
            return {"online": ativas > 0,
                    "interface": f"{ativas} ativa(s)" if ativas else "nenhuma",
                    "enviados": sai, "recebidos": entra}
        except Exception:
            return {"online": "indisponível", "interface": "indisponível",
                    "enviados": "indisponível", "recebidos": "indisponível"}


registrar_fonte("sistema", FonteSistema)
registrar_fonte("falsa", FonteFalsa)
