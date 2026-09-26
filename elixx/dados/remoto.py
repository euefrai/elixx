"""Fontes remotas e locais da ELiXX (Fase 06).

- `FonteRemota`: HTTP/REST via ClienteHttp (stdlib). Estados
  carregando/sucesso/erro; timeout; busca assíncrona em thread daemon
  (a UI nunca bloqueia); cancelamento best-effort (documentado:
  urllib não aborta leitura em curso — a flag impede o efeito).
- `FonteArquivo`: JSON local com releitura por mtime.

Ambas implementam FonteDados (snapshot/obter) e escrevem o resultado no
estado via Executor (ponte mundo→estado→Vinculador→UI). Nada aqui
conhece Tkinter, Cena ou widgets.
"""
from __future__ import annotations

import json
import os
import threading
import time

from .fontes import FonteDados
from .http import ClienteHttp


class FonteRemota(FonteDados):
    """Uma API REST configurada por um bloco `dados nome { ... }`."""

    def __init__(self, *, nome: str, url: str, metodo: str = "GET",
                 cabecalhos: dict | None = None,
                 parametros: dict | None = None,
                 corpo_raw: object = None,
                 timeout_s: float = 10.0,
                 intervalo_s: float | None = None,
                 alvo: str = "") -> None:
        self.nome_fonte = nome
        self.url = url
        self.metodo = metodo
        self.cabecalhos = dict(cabecalhos or {})
        self.parametros = dict(parametros or {})
        self.corpo_raw = corpo_raw
        self.avaliar_corpo = None  # Callable|None, conectado pelo Executor
        self.cliente = ClienteHttp(timeout_s=timeout_s)
        self.intervalo_s = intervalo_s
        self.alvo = alvo or f"estado.{nome}"
        self._estado = {"valor": None, "carregando": False,
                        "erro": None, "status": None}
        self._em_andamento = False
        self._cancelada = False
        self._proxima = 0.0
        self._lock = threading.Lock()
        self.buscas_iniciadas = 0
        self.buscas_concluidas = 0

    # ----- FonteDados (leitura do ÚLTIMO resultado; nunca bloqueia) -----

    def atualizar(self) -> None:
        """Compat: não busca (busca é explícita/periódica)."""

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._estado)

    # ----- busca -----

    def buscar(self) -> dict:
        """Busca SÍNCRONA (testes e --sem-janela; respeita timeout)."""
        with self._lock:
            self._estado = {"valor": None, "carregando": True,
                            "erro": None, "status": None}
        resposta = self._executar()
        with self._lock:
            self._estado = {
                "valor": resposta.valor,
                "carregando": False,
                "erro": resposta.erro,
                "status": resposta.status,
            }
            self.buscas_concluidas += 1
            return dict(self._estado)

    def buscar_async(self, ao_chegar=None) -> bool:
        """Busca em thread daemon. Retorna False se já há uma em curso."""
        with self._lock:
            if self._em_andamento:
                return False
            self._em_andamento = True
            self._estado = {"valor": self._estado.get("valor"),
                            "carregando": True,
                            "erro": None, "status": None}
            self.buscas_iniciadas += 1

        def trabalho():
            resposta = self._executar()
            with self._lock:
                self._em_andamento = False
                cancelada = self._cancelada
                if not cancelada:
                    self._estado = {
                        "valor": resposta.valor,
                        "carregando": False,
                        "erro": resposta.erro,
                        "status": resposta.status,
                    }
                    self.buscas_concluidas += 1
                else:
                    self._estado["carregando"] = False
            if not cancelada and ao_chegar is not None:
                try:
                    ao_chegar(self)
                except Exception:
                    pass

        threading.Thread(target=trabalho, daemon=True,
                         name=f"elixx-{self.nome_fonte}").start()
        return True

    def cancelar(self) -> None:
        """Impede o efeito de uma busca em curso (best-effort)."""
        with self._lock:
            self._cancelada = True
            self._estado["carregando"] = False

    def retomar(self) -> None:
        with self._lock:
            self._cancelada = False

    # ----- periódica (um relógio no tick; sem timers extras) -----

    def deve_buscar(self, agora: float) -> bool:
        return (self.intervalo_s is not None
                and agora >= self._proxima
                and not self._em_andamento
                and not self._cancelada)

    def marcar_agendada(self, agora: float) -> None:
        self._proxima = agora + (self.intervalo_s or 0)

    # ----- interno -----

    def _executar(self):
        corpo = None
        if self.corpo_raw is not None and self.avaliar_corpo is not None:
            try:
                corpo = self.avaliar_corpo()
            except Exception as exc:
                from .http import Resposta

                return Resposta(erro=f"Corpo inválido: {exc}.")
        return self.cliente.requisitar(
            self.metodo, self.url, cabecalhos=self.cabecalhos,
            parametros=self.parametros, corpo=corpo)


class FonteArquivo(FonteDados):
    """JSON local (`dados cfg { arquivo: "dados/x.json" }`)."""

    def __init__(self, *, nome: str, caminho: str,
                 base_dir: str = ".", alvo: str = "") -> None:
        self.nome_fonte = nome
        self.alvo = alvo or f"estado.{nome}"
        if os.path.isabs(caminho):
            self.caminho = caminho
        else:
            self.caminho = os.path.join(base_dir, caminho)
        self._mtime: float | None = -1.0
        self._estado = {"valor": None, "erro": "não carregado"}

    def atualizar(self) -> None:
        self._mtime = -1.0  # força releitura no próximo snapshot

    def snapshot(self) -> dict:
        try:
            mtime = os.path.getmtime(self.caminho)
        except OSError:
            self._estado = {"valor": None,
                            "erro": f"Arquivo não encontrado: {self.caminho}."}
            return dict(self._estado)
        if mtime != self._mtime:
            self._mtime = mtime
            try:
                with open(self.caminho, encoding="utf-8") as arq:
                    self._estado = {"valor": json.load(arq), "erro": None}
            except json.JSONDecodeError:
                self._estado = {"valor": None,
                                "erro": "JSON inválido no arquivo."}
            except (OSError, UnicodeDecodeError) as exc:
                self._estado = {"valor": None, "erro": f"Leitura: {exc}."}
        return dict(self._estado)
