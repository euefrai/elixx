# ELiXX — Eventos e ações

## Eventos (Fase 01)

| Evento            | Quando dispara                        |
|-------------------|---------------------------------------|
| `clicar`          | ao clicar no elemento                 |
| `passar_por_cima` | ao passar o cursor sobre o elemento   |
| `pressionar`      | ao pressionar tecla com foco nele     |
| `aparecer`        | quando o elemento aparece (automático)|

Novos eventos são registrados em `elixx/runtime/eventos.py`, sem mexer
no parser. Nome errado gera erro com sugestão.

## Ações (Fase 01)

`mostrar`, `esconder`, `abrir`, `fechar`, `mover`, `redimensionar`,
`alterar`, `reproduzir`, `parar`, `animar` (simplificada na Fase 01).

Novas ações via decorador, sem modificar o núcleo:

```python
from elixx.runtime.acoes import acao

@acao("girar")
def girar(ctx, graus):
    ...
```

## Simulação na CLI

Sem interface gráfica nativa na Fase 01, eventos são simulados:

```bash
elixx executar programa.elixx --clicar teste
```

`aparecer` dispara automaticamente para todos os objetos.
