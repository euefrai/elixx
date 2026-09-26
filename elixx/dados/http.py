"""Cliente HTTP da ELiXX — só biblioteca padrão (urllib/json).

Não conhece Tkinter, Cena nem widgets: recebe método/URL/opções e devolve
Resposta. Nunca levanta para a UI — todo erro vira Resposta.erro em
português. JSON é tratado exclusivamente como DADOS (só dict/list/str/
float/bool/None do json stdlib; nada é avaliado como código).
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE")


@dataclass
class Resposta:
    """Resultado de uma requisição (sucesso ou erro mapeado)."""

    ok: bool = False
    status: int | None = None
    valor: object = None  # JSON decodificado ou texto
    texto: str = ""
    erro: str | None = None
    cabecalhos_resp: dict = field(default_factory=dict)


def montar_url(base: str, parametros: dict | None) -> str:
    """Junta URL + query com urlencode (nunca concatena na mão)."""
    if not parametros:
        return base
    partes = urllib.parse.urlparse(base)
    query = dict(urllib.parse.parse_qsl(partes.query))
    for chave, valor in (parametros or {}).items():
        query[str(chave)] = valor if isinstance(valor, (str, int, float,
                                                         bool)) else json.dumps(
            valor, ensure_ascii=False)
    nova = partes._replace(
        query=urllib.parse.urlencode(query, doseq=True))
    return urllib.parse.urlunparse(nova)


class ClienteHttp:
    """GET/POST/PUT/PATCH/DELETE síncronos com timeout (stdlib)."""

    def __init__(self, timeout_s: float = 10.0) -> None:
        self.timeout_s = max(0.5, float(timeout_s))

    def requisitar(self, metodo: str, url: str, *,
                   cabecalhos: dict | None = None,
                   parametros: dict | None = None,
                   corpo: object = None) -> Resposta:
        metodo = str(metodo).upper()
        if metodo not in METODOS:
            return Resposta(erro=f"Método inválido: {metodo}.")
        esquema = urllib.parse.urlparse(url).scheme.lower()
        if esquema not in ("http", "https"):
            return Resposta(
                erro=f"URL bloqueada (só http/https): {esquema or '?'}.")
        final = montar_url(url, parametros)
        dados = None
        heads = {"Accept": "application/json",
                 "User-Agent": "ELiXX/0.2"}
        for chave, valor in (cabecalhos or {}).items():
            heads[str(chave)] = str(valor)
        if corpo is not None and metodo in ("POST", "PUT", "PATCH"):
            dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            heads["Content-Type"] = "application/json; charset=utf-8"
        req = urllib.request.Request(final, data=dados, headers=heads,
                                     method=metodo)
        try:
            with urllib.request.urlopen(req,
                                        timeout=self.timeout_s) as resp:
                return self._ler(resp, None)
        except urllib.error.HTTPError as exc:
            try:
                return self._ler(exc, None)
            except Exception:
                return Resposta(status=exc.code,
                                erro=f"HTTP {exc.code}.")
        except urllib.error.URLError as exc:
            motivo = getattr(exc.reason, "strerror", None) or str(exc.reason)
            texto = str(motivo).lower()
            if "name or service not known" in texto or "nodename" in texto \
                    or "getaddrinfo" in texto:
                return Resposta(erro="DNS: endereço não encontrado.")
            if "refused" in texto or "recus" in texto:
                return Resposta(erro="Conexão recusada pelo servidor.")
            return Resposta(erro=f"Rede: {motivo}.")
        except (socket.timeout, TimeoutError):
            return Resposta(erro="Tempo esgotado (timeout).")
        except (ConnectionError, OSError) as exc:
            return Resposta(erro=f"Conexão: {exc}.")
        except Exception as exc:
            return Resposta(erro=f"Falha: {exc}.")

    @staticmethod
    def _ler(resp, _ignorado) -> Resposta:
        status = getattr(resp, "status", None)
        if status is None:
            try:
                status = resp.getcode()
            except Exception:
                status = None
        brutos = resp.read()
        charset = "utf-8"
        try:
            content_type = resp.headers.get("Content-Type", "")
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[
                    0].strip() or "utf-8"
        except Exception:
            pass
        texto = brutos.decode(charset, errors="replace")
        if not texto.strip():
            return Resposta(ok=status is not None and 200 <= status < 300,
                            status=status, valor=None, texto=texto,
                            erro=None if status is not None and 200 <= status < 300
                            else f"HTTP {status} (resposta vazia).")
        try:
            valor = json.loads(texto)
        except json.JSONDecodeError:
            return Resposta(ok=False, status=status, valor=None,
                            texto=texto, erro="Resposta não é JSON válido.")
        ok = status is not None and 200 <= status < 300
        return Resposta(ok=ok, status=status, valor=valor, texto=texto,
                        erro=None if ok else f"HTTP {status}.")
