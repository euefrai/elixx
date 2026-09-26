# ELiXX — Estado (Fase 05)

Variáveis reativas do programa, declaradas uma vez, visíveis em toda
janela:

```elixx
estado {
    contador: 0
    nome: "Visitante"
    ativo: verdadeiro
}
```

Valores: texto, número ou verdadeiro/falso. Um bloco por programa.

## Leitura

```elixx
texto contador {
    origem: estado.contador
}
```

Ou em qualquer expressão: `mostrar(estado.contador)`,
`se estado.ativo { ... }`.

## Escrita

```elixx
quando clicar {
    estado.contador = 0
    estado.contador += 1
    estado.contador -= 1
    estado.contador *= 2
    estado.contador /= 2
}
```

`+=` também concatena texto. Divisão por zero e tipos incompatíveis
são erros em português. Dados (`dados.*`) são somente leitura:
atribuir a eles é erro que sugere `estado`.

Atribuir a chave inexistente é erro com sugestão (contra typos).
Contadores usam `incrementar("cliques")` (cria com 0).

## Regras

- Estado inicial existe ANTES de objetos e `aparecer`: componentes com
  origem já nascem com o valor.
- `estado` sozinho não é valor (erro que ensina o caminho).
- Variáveis simples (`x = 1`) vão para a memória (escopo), não p/ estado.
