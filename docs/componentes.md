# ELiXX — Componentes

Catálogo (Fase 04–07): `janela`, `tela`, `texto`, `botão`, `imagem`,
`vídeo`, `áudio`, `painel`, `cartao`, `linha`, `coluna`, `grade`,
`pilha`, `entrada`, `checkbox`, `selecao`, `separador`, `indicador`,
`barra`, `grafico`, `lista`, `icone`.
Novos (Fase 08): `formulario`, `aba`, `abas`, `menu`, `tabela`,
`modal`, `conteudo` (marcador de slot).

## Reutilizáveis (Fase 08)

Defina uma vez, use várias:

```elixx
componente CartaoUsuario {
    propriedade nome
    propriedade email: "sem email"

    corpo {
        cartao base {
            texto rot {
                conteúdo: param.nome
            }
        }
    }
}

janela principal {
    CartaoUsuario ana {
        nome: "Ana"
    }
}
```

- `propriedade x` (obrigatória) ou `propriedade x: padrao`.
- `param.nome` em qualquer valor/expressão do corpo.
- Nomes internos isolados (`ana__rot`); filhos do slot são públicos.
- Slot: marcador `conteudo` no corpo recebe os filhos do uso.
- Eventos do uso vão para a primeira raiz.
- Sem recursão (erro claro, inclusive indireta A→B→A).
- Expansão entre parse e semântica: o runtime só vê componentes reais.
