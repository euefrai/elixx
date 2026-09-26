# ELiXX — Sintaxe (Fase 01)

## Programa

Um programa tem uma ou mais janelas e (opcional) funções:

```elixx
função dobrar(valor) {
    retornar valor * 2
}

janela principal {
    titulo: "App"
}
```

## Janela

```elixx
janela principal {
    titulo: "Minha aplicação"
    tamanho: 800px 600px
}
```

## Componentes

`botão`, `texto`, `imagem`, `vídeo`, `áudio` — com nome próprio e bloco:

```elixx
botão confirmar {
    texto: "OK"
}
```

Contêineres e dados (extensão dashboard): `painel`, `cartao`,
`barra`, `grafico`, `lista`.

Layout e formulário (Fase 04): `linha`, `coluna`, `grade`, `pilha`,
`entrada`, `checkbox`, `selecao`, `separador`, `indicador`.
Detalhes em `docs/layout.md` e `docs/componentes.md`.

```elixx
painel lateral {
    texto titulo {
        conteúdo: "Título"
    }
    barra uso {
        origem: dados.sistema.cpu
    }
}
```

Componentes podem ser aninhados. Formas sem acento valem (`botao`,
`video`, `audio`, `posicao`, `titulo`, `duracao`, `funcao`, `senao`,
`cartao`, `grafico`).

## Propriedades

Uma por linha, formato `nome: valores`:

```elixx
titulo: "Nome"
tamanho: 800px 600px
posição: 100px 100px
fundo: azul
cor: "#ff0000"
duração: 500ms
```

Valores: texto entre aspas, número, medida (`800px`, `20%`, `2s`),
cor (nome ou hexadecimal entre aspas), expressões (`valor * 2`).

Texto de um componente: `texto:` (Fase 01) ou `conteúdo:` (alias, Fase 02).
Tamanho da letra: `fonte: 24px` (Fase 02; `tamanho` continua sendo a
caixa, ex. `tamanho: 200px 50px`).

Comentários: `#` ou `//` até o fim da linha.

## Dados vivos (reatividade)

```elixx
texto cpu {
    origem: dados.sistema.cpu
    formato: "percentual"
}
```

Caminhos: `dados.sistema.cpu`, `.ram.percentual`, `.disco.*`,
`.rede.*`, `.processos.*`, `.sistema.*`, `.hora`. Formatos: `texto`,
`percentual`, `inteiro`, `gb`, `mb`. Detalhes em
`docs/dados-reatividade.md`.

## Estado e reatividade (Fase 05)

```elixx
estado {
    contador: 0
}

texto contador {
    origem: estado.contador
}

botão mais {
    quando clicar {
        estado.contador += 1
    }
}

entrada nome {
    ligado_a: estado.nome
}
```

Atribuição: `= += -= *= /=`. Origem aceita expressões
(`estado.qtd * estado.preco`). Detalhes em `docs/estado.md` e
`docs/reatividade.md`.

## Fontes de dados (Fase 06)

```elixx
dados usuarios {
    url: "https://api.exemplo.com/usuarios"
    metodo: "GET"
    tempo_limite: 5s
    atualizar: 10s
}
```

Detalhes em `docs/dados.md`, `docs/http.md` e `docs/apis.md`.

## Multimídia (Fase 07)

```elixx
imagem logo {
    arquivo: "assets/logo.png"
}

icone salvar {
    nome: "salvar"
}

audio musica {
    arquivo: "assets/som.wav"
}

grafico vendas {
    tipo: "barras"
    origem: estado.vendas
}
```

Listas: `estado.nums = [10, 25, 35]`. Detalhes em `docs/multimidia.md`,
`docs/imagens.md`, `docs/audio.md`, `docs/video.md`,
`docs/graficos.md`, `docs/recursos.md`.

## Aplicações (Fase 08)

```elixx
tema escuro {
    cores {
        fundo: "#14161f"
    }
}

tela inicio {
    botão ir_perfil {
        quando clicar {
            ir("perfil")
        }
    }
}

componente Cartao {
    propriedade titulo
    corpo {
        texto rot {
            conteúdo: param.titulo
        }
    }
}
```

Detalhes em `docs/componentes.md`, `docs/temas.md`,
`docs/formularios.md`, `docs/navegacao.md`, `docs/aplicacoes.md`.

## Composição (Fase 09)

```elixx
componente Contador {
    estado {
        valor: 0
    }

    corpo {
        texto rot {
            origem: local.valor
        }
    }
}

lista usuarios {
    origem: estado.usuarios
    chave: item.id

    modelo {
        texto nome {
            origem: item.nome
        }
    }
}

acao selecionar(id) {
    estado.selecionado = id
}

funcao total(preco, quantidade) {
    retornar preco * quantidade
}

importar componentes.card
```

Comandos: `executar nome` / `executar nome(args)`. Operadores:
`+ - * / %`, comparações, `e`/`ou`/`não`. Detalhes em
`docs/fase-09.md`.

## Animação (Fase 03)

```elixx
animação entrada {
    alvo: cartao
    posição: 0px 90px → 0px 40px
    duração: 600ms
    movimento: suave
    quando terminar {
        mostrar("pronto!")
    }
}
```

Detalhes em `docs/animacao.md`.

## Eventos

```elixx
quando clicar {
    mostrar("Clicou!")
}
```

Eventos: `clicar`, `passar_por_cima`, `pressionar`, `aparecer`.

## Comandos (dentro de eventos e funções)

```elixx
mostrar("Olá")                 # ação
se 2 > 1 {                     # condicional
    mostrar("maior")
}
senão {
    mostrar("menor")
}
repetir 3 vezes {              # repetição
    mostrar("oi")
}
retornar valor * 2             # só em funções
```

Operadores: `+ - * /`, `== != > < >= <=`, `e`, `ou`, `não`.
