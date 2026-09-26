# ELiXX — Fase 09: composição, estado local, listas e módulos

Crescer sem monólito: componentes com estado próprio, listas que
viram N itens, ações/funções reutilizáveis e arquivos importados.

## Estado local

```elixx
componente Contador {
    estado {
        valor: 0
    }

    corpo {
        texto rot {
            origem: local.valor
        }

        botão mais {
            quando clicar {
                local.valor += 1
            }
        }
    }
}
```

Fora de `modelo`, a expansão reescreve `local.x` para
`estado.<inst>__x` (isolado por instância, com padrões semeados, sem
contexto em runtime). Dentro de `modelo`, `local.*` é dinâmico
(namespace da linha, destruído com ela). Def sem bloco `estado`
usando `local.*` é erro claro. Leitura inexistente é erro;
escrita cria.

## Contexto

- `estado.*` global; `local.*` instância/linha; `param.*` só em def
  (expansão substitui, inclusive `param.a.b`); `item.*` + `item.indice`
  só em `modelo` (parser barra fora com erro PT imediato);
  `dados.*` como antes.
- `param`/`item`/`local` nus têm erro dedicado; atribuir em `item`
  é erro (somente leitura).

## Listas dinâmicas

```elixx
lista usuarios {
    origem: estado.usuarios
    chave: item.id

    modelo {
        texto nome {
            origem: item.nome
        }
    }
}
```

`origem` lista substitui a série; número mantém histórico. `chave:`
preserva identidade (sem chave: posicional, documentado). Reconcilia
por chave: cria/atualiza/destrói linhas e namespaces. Bindings por
linha reavaliados com item+ns no contexto; versões evitam retrabalho.

## Ações e funções

```elixx
acao selecionar(id) {
    estado.selecionado = id
}

funcao total(preco, quantidade) {
    retornar preco * quantidade
}
```

`executar nome` / `executar nome(args)`; retorno de ação descartado;
params com escopo (Memoria, sem vazamento); aridade com erro PT.
Operadores: `+ - * / %`, comparações, `e`/`ou`/`não`, precedência
(`2 + 3 * 4` = 14); divisão por zero em PT.

## Módulos

```elixx
importar componentes.card
```

Caminhos com pontos a partir da raiz (pasta do entry); `..`,
absolutos e fuga da raiz bloqueados; ciclos `A → B → A` detectados;
cada arquivo uma vez; tudo fundido (estado duplicado é erro).
`verificar` continua sem HTTP/execução.

## Projeto

```text
app/
    principal.elixx
    componentes/
    telas/
    dados/
```

Um `app.elixx` sozinho continua válido. Ver `app/` de exemplo.

## Limites honestos

Sem `param` fora de def; sem `item` fora de modelo/lista; sem
`local` fora de def/modelo; scroll em lista dinâmica não existe;
HTML renderiza lista dinâmica como placeholder.
