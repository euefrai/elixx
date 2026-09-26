# ELiXX — Visual Core 2D (Fase 10)

Fundação matemática e visual: objetos que existem em um espaço 2D,
com posição, rotação, escala, opacidade, pivô, hierarquia, grupos,
camadas e viewport. Complexidade no motor, simplicidade na linguagem.

## Sistema de coordenadas

- Origem (0, 0) no canto superior esquerdo da área de conteúdo.
- X cresce para a direita, Y cresce para baixo.
- Ângulos em graus, sentido horário na tela (`30deg`, `45graus`,
  `0.5rad` ou número = graus). Unidade interna: graus em [0, 360).
- Opacidade 0% (invisível) .. 100% (visível); interno 0.0..1.0.

Mesmo sistema em runtime, cena, animação e renderers.

## Posição

```elixx
posição: 300px 200px
```

ou em bloco (equivale à forma de uma linha):

```elixx
posição {
    x: 300
    y: 200
}
```

Números nus valem px. `%`/`vw`/`vh` continuam relativos à referência
(como antes). Filhos usam coordenadas locais relativas ao pai.

## Rotação, escala, opacidade, pivô, camada

```elixx
rotação: 30deg
escala: 1.2          # uniforme
escala: 1.2 0.8      # eixos independentes
escala {
    x: 1.2
    y: 0.8
}
opacidade: 80%
pivô: 50% 50%        # padrão = centro
pivô {
    x: 10
    y: 10
}
camada: 10
```

Pivô em `%` (do tamanho do objeto) ou `px` (absoluto). É o ponto ao
redor do qual rotação e escala acontecem (ex. futuro: `braço.pivô` no
ombro). Camada menor = atrás, maior = frente; empate = ordem estável
de criação.

## Grupos e hierarquia

```elixx
grupo personagem {
    posição: 300px 200px
    rotação: 5deg

    imagem tronco {
        arquivo: "corpo.png"
    }

    objeto braco {
        posição: 40px 20px
        rotação: 25deg
    }
}
```

O filho acompanha o pai: move, gira e escala junto (matemática em
`elixx/visual/transform.py`: `combinar`). Opacidade multiplica (filho
nunca mais visível que o pai). `objeto` é um contêiner genérico como
`grupo`. Sem bones/IK/skinning (fases futuras).

## Layout x Transform (precedência)

- LAYOUT organiza a estrutura (linha/coluna/grade/pilha, tamanho).
- TRANSFORM move o visual (posição/rotação/escala/pivô/opacidade).

`posição` explícita vence o empilhamento provisório; resto do layout
inalterado (F01–F09 preservados).

## Cena 2D e viewport

`Cena` = Scene2D (janelas + `viewport` lógica do tamanho da primeira
janela). `NoVisual` = nó com transform local + pai. `cena.globais()`
devolve o transform global de cada nó. Viewport é fundação para futura
câmera (só tamanho/deslocamento/zoom hoje; sem câmera completa).

## Animação (integração mínima, sem Motion Core)

O motor existente continua; agora aceita por propriedade:

- posição/tamanho: px; rotação: graus/deg/rad/número;
- escala: número (uniforme); opacidade: número/%.

Exemplo:

```elixx
animação aceno {
    alvo: braco
    rotacao: 25deg -> 60deg
    duração: 800ms
    movimento: suave
}
```

Animar `escala` define os dois eixos (uniforme).

## Renderers

- Tk: posição real, tamanho × escala real, camadas via `lift()`
  (estável), alfa da janela. Imagem raster com Pillow (opcional, sem
  dependência nova obrigatória) aplica escala + rotação horária;
  SVG aplica escala (sem rotação). Rotação de widgets e opacidade por
  widget NÃO existem no Tk (estado interno preservado, sem fingir).
- HTML: `transform: translate/rotate/scale`, `transform-origin` do
  pivô, `opacity`, `z-index`. Sem transformação → saída idêntica à
  anterior. HTML é prévia; sem reconciliação de listas.

## Validação

Erros claros em português para: opacidade fora de 0..1/0%..100%,
pivô fora de %/px, ângulo com unidade errada, escala não numérica,
NaN/infinito, divisão de vetor por zero, viewport/zoom inválidos,
blocos `posição/pivô/escala` incompletos.
