"""Servidor demo para os exemplos lista-api/formulario-api (stdlib).

Rode antes dos exemplos, em outro terminal:

    python exemplos/servidor_demo.py

Serve os mesmos endpoints dos testes, na porta fixa 8765.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "testes"))

from servidor_teste import ServidorTeste  # noqa: E402


def main() -> None:
    srv = ServidorTeste()
    porta = 8765
    srv.servidor.server_close()
    from http.server import HTTPServer
    from servidor_teste import _Manipulador

    srv.servidor = HTTPServer(("127.0.0.1", porta), _Manipulador)
    print(f"[ELiXX demo] API local em http://127.0.0.1:{porta}/usuarios")
    print("[ELiXX demo] Ctrl+C para parar.")
    try:
        srv.servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
