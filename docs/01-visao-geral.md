# ELiXX — Visão geral

## O que é ELiXX

A ELiXX é uma linguagem de programação independente, em português, criada
para tornar extremamente simples criar coisas **visuais, animadas e
interativas através de código**: janelas, botões, textos, imagens, áudio,
vídeo, animações e eventos.

Ela não é HTML+CSS+JS com outra sintaxe. A proposta é outra abstração: o
programador descreve **o que quer que aconteça**, e a linguagem cuida de
renderização, interpolação e eventos.

## Filosofia

1. Português natural, pouca pontuação, código curto.
2. Abstrações de alto nível (`janela`, `botão`, `quando clicar`).
3. Comportamento previsível e erros que ensinam (sempre em português,
   com linha, trecho e exemplo de correção).
4. A linguagem cresce sem quebrar programas existentes.
5. Independente: funciona 100% sem Fajulto (a integração é uma camada
   futura e opcional).

## Instalação

Pré-requisito: Python 3.10 ou superior.

```bash
cd elixx
pip install -e .
```

## Primeiro programa

Arquivo `programa.elixx`:

```elixx
janela principal {

    titulo: "Minha primeira aplicação"

    tamanho: 800px 600px

    botão teste {

        texto: "Olá ELiXX"

        quando clicar {
            mostrar("Olá, mundo!")
        }
    }
}
```

Execute (Fase 02: abre janela nativa real):

```bash
elixx executar programa.elixx
elixx executar programa.elixx --sem-janela --clicar teste  # modo Fase 01
elixx verificar programa.elixx
elixx compilar programa.elixx
elixx versao
```

Mais exemplos em `exemplos/`. Sintaxe completa em `docs/sintaxe.md`.
