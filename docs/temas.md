# ELiXX — Temas (Fase 08)

```elixx
tema escuro {
    cores {
        fundo: "#14161f"
        destaque: "#4ade80"
    }

    tamanhos {
        normal: 14px
    }

    espacos {
        normal: 12px
    }
}

janela principal {
    tema: "escuro"
    fundo: tema.fundo

    texto titulo {
        cor: tema.texto
        fonte: tema.normal
    }
}
```

- `cor:`/`fundo:` aceitam `tema.nome` (seção cores); `fonte:` e medidas
  aceitam `tema.nome` (tamanhos/espacos).
- Herança: componente usa o próprio `tema:`, senão o da janela, senão
  o primeiro definido.
- `usar_tema("claro")` re-resolve a Cena e refresca widgets (sem
  reconstruir). Sem janela, só o estado muda (testável).
- HTML gera variáveis `--elx-*` do tema atual.
