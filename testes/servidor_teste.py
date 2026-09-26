"""Servidor HTTP local para testes da Fase 06 (stdlib, sem internet).

Endpoints:
  GET  /usuarios    → [{"id":1,"nome":"Ana"},{"id":2,"nome":"Beto"}]
  POST /usuarios    → echo do corpo + {"id": 3}
  PUT  /usuarios/1  → echo do corpo + {"id": 1}
  DELETE /usuarios/1 → {"ok": true}
  GET  /erro        → 500 {"erro": "falha"}
  GET  /atrasado    → dorme 3s, depois JSON (para timeout)
  GET  /invalido    → texto que não é JSON
  GET  /vazio       → 200 vazio
  GET  /eco-utf8    → JSON com acentos/emoji

Uso: with ServidorTeste() as srv: requests para srv.url("/usuarios").
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

USUARIOS = [{"id": 1, "nome": "Ana", "ativo": True},
            {"id": 2, "nome": "Beto", "ativo": False}]


class _Manipulador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _corpo(self):
        tamanho = int(self.headers.get("Content-Length") or 0)
        brutos = self.rfile.read(tamanho) if tamanho else b""
        try:
            return json.loads(brutos.decode("utf-8")) if brutos else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"_invalido": True}

    def _responder(self, codigo: int, objeto) -> None:
        dados = json.dumps(objeto, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type",
                         "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        caminho = self.path.split("?")[0]
        if caminho == "/usuarios":
            self._responder(200, USUARIOS)
        elif caminho == "/erro":
            self._responder(500, {"erro": "falha"})
        elif caminho == "/atrasado":
            time.sleep(3)
            self._responder(200, {"ok": True})
        elif caminho == "/invalido":
            brutos = "isto não é json {".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(brutos)))
            self.end_headers()
            self.wfile.write(brutos)
        elif caminho == "/vazio":
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif caminho == "/eco-utf8":
            self._responder(200, {"msg": "Olá, ELiXX — çãõ ✓"})
        elif caminho == "/bytes":
            brutos = b"0123456789abcdef"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(brutos)))
            self.end_headers()
            self.wfile.write(brutos)
        elif caminho == "/nao-existe":
            self._responder(404, {"erro": "não achado"})
        else:
            self._responder(404, {"erro": "rota desconhecida"})

    def do_POST(self):
        if self.path.split("?")[0] == "/usuarios":
            corpo = self._corpo()
            resposta = dict(corpo) if isinstance(corpo, dict) else {}
            resposta["id"] = 3
            self._responder(201, resposta)
        else:
            self._responder(404, {"erro": "rota desconhecida"})

    def do_PUT(self):
        if self.path.split("?")[0] == "/usuarios/1":
            corpo = self._corpo()
            resposta = dict(corpo) if isinstance(corpo, dict) else {}
            resposta["id"] = 1
            self._responder(200, resposta)
        else:
            self._responder(404, {"erro": "rota desconhecida"})

    def do_PATCH(self):
        self.do_PUT()

    def do_DELETE(self):
        if self.path.split("?")[0] == "/usuarios/1":
            self._responder(200, {"ok": True})
        else:
            self._responder(404, {"erro": "rota desconhecida"})


class ServidorTeste:
    """Sobe o servidor numa thread; `url()` monta endpoints."""

    def __init__(self) -> None:
        self.servidor = HTTPServer(("127.0.0.1", 0), _Manipulador)
        self.porta = self.servidor.server_address[1]
        self.thread = threading.Thread(target=self.servidor.serve_forever,
                                       daemon=True)

    def url(self, caminho: str) -> str:
        return f"http://127.0.0.1:{self.porta}{caminho}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.thread.join(timeout=5)
