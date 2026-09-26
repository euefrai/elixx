# ELiXX — APIs REST na linguagem (Fase 06)

```elixx
dados usuarios {
    url: "https://api.exemplo.com/usuarios"
    metodo: "GET"
    tempo_limite: 5s
    atualizar: 10s

    cabecalhos {
        "Accept": "application/json"
    }

    parametros {
        pagina: 1
        limite: 20
    }
}

dados novo {
    url: "https://api.exemplo.com/usuarios"
    metodo: "POST"

    corpo {
        nome: estado.nome
    }
}

dados config {
    arquivo: "dados/config.json"
}
```

Regras: `url` XOR `arquivo`; método em GET/POST/PUT/PATCH/DELETE;
`atualizar` mínimo 1s; `para: estado.x` opcional (padrão
`estado.<nome>`, criado sozinho).

Comportamento:

- Nativo: primeira busca assíncrona ao abrir (UI livre) + periódica
  no tick (uma checagem, sem timers extras; sem duplicar em curso).
- `sincronizar()` / `sincronizar("nome")` busca agora.
- `--sem-janela`: uma busca síncrona (respeita timeouts).
- `compilar`/`verificar`: nunca buscam (prévia estática / validação).
- Erro de rede vira `estado.<nome>.erro`; app continua.
- Cancelamento best-effort (urllib não aborta leitura; a flag impede
  o efeito) — documentado, não fingido.

Exemplos: `dados.elixx`, `lista-api.elixx`, `formulario-api.elixx`
(rode `python exemplos/servidor_demo.py` antes dos dois últimos).
Matriz nativo/HTML e segurança em `docs/http.md`.
