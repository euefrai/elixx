# ELiXX — Fontes de dados (Fase 06)

```text
mundo externo → Fonte → estado → Vinculador → Cena → renderer
```

Três tipos, mesma interface (`snapshot`/`obter`):

| Fonte | Origem | Exemplos |
|---|---|---|
| `sistema` | máquina (ctypes/shutil) | `dados.sistema.cpu` |
| remota (`dados nome { url }`) | HTTP/REST JSON | `dados.usuarios.valor` |
| arquivo (`dados cfg { arquivo }`) | JSON local | `dados.cfg.valor` |

Toda fonte remota/arquivo escreve seu snapshot em `estado.<nome>`
(ou `para: estado.x`):

```text
{valor, carregando, erro, status}
```

Bindings usam `estado.usuarios.valor`, `...status`, `...erro`,
`...carregando`. Sem segundo sistema de reatividade: versões do
estado fazem o resto.

Novas fontes globais entram em `REGISTRO_FONTES`; fontes de programa
vêm dos blocos `dados` (validadas contra o programa, não globais).
