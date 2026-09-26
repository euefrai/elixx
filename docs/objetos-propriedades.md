# ELiXX — Objetos e propriedades

## Modelo de objeto

Todo elemento visual possui:

```text
posição, tamanho, rotação, escala, opacidade,
visibilidade, estilo, eventos e filhos
```

A janela usa tamanho padrão `800x600` quando `tamanho` não é informado;
componentes começam visíveis com opacidade total.

## Propriedades por elemento

Janela: `titulo`, `tamanho`, `posição`, `fundo`, `cor`.

Componentes: `texto`, `tamanho`, `posição`, `cor`, `fundo`, `duração`,
`movimento`, `opacidade`.

Propriedade desconhecida gera erro com sugestão ("você quis dizer..."):

```text
Erro ELiXX na linha 2:
Propriedade desconhecida em janela "p": "tamnaho". Você quis dizer: tamanho?
```

## Unidades

Comprimento: `px`, `%`, `vw`, `vh`. Tempo: `ms`, `s`. Ângulo: `graus`.
Números com unidade nunca viram texto: `800px` é medida `(800, px)`.

## Cores

Nome em português (`vermelho`, `azul`, `verde`...) ou hexadecimal entre
aspas (`"#ff0000"`, `"#f00"`). `#` fora de aspas é comentário — por isso a
forma hexadecimal exige aspas. Erro de digitação sugere o nome certo.
