# ELiXX — Layout (Fase 04)

Contêineres que arranjam filhos sem posição manual:

```elixx
coluna pagina {
    posição: 16px 16px
    tamanho: 728px 568px
    espacamento: 12px

    texto titulo {
        conteúdo: "Olá"
    }

    linha botoes {
        espacamento: 10px
        botão um {
            texto: "Um"
            tamanho: 120px 40px
        }
    }
}
```

- `coluna`: empilha vertical. `linha`: lado a lado. `grade`: N colunas
  (`colunas: 2`). `pilha`: todos na mesma origem.
- Filho COM `posição:` é respeitado e ignorado pelo arranjo (válvula).
- Propriedades: `espacamento` (gap), `margem` (fora), `preenchimento`
  (dentro), `alinhamento: "esquerda"|"centro"|"direita"` (coluna/grade)
  e `"topo"|"centro"|"base"` (linha), `largura`/`altura` (refinam cada
  eixo do `tamanho`), `minimo`/`maximo` (ambos os eixos), `colunas`.
- Contêiner sem tamanho cresce até caber nos filhos.
- Redimensionar a janela recalcula `%`/`vw`/`vh` + arranjo (debounce).
- Filhos sem tamanho dentro de layout são medidos após montar.

Ainda não há: ancorar, preencher, centralização plena na janela
(documentados para fase futura). `ancorar`/`preencher` não existem.
