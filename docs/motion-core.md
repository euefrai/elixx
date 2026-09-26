# ELiXX — Motion Core 2.0 (Fase 11)

Evolução do motor de animação (sem segundo motor): transforma estado
inicial + intenção + tempo + curva/dinâmica em Transform intermediário.
O programador descreve O QUE; o motor calcula COMO ao longo do tempo.

## Conceitos

- EASING = curva temporal `f(t)`, `t ∈ [0,1]` (fechada, sem estado).
- SPRING = dinâmica com estado (rigidez, amortecimento, massa).
- KEYFRAME = estado em um ponto do tempo (`0%`, `50%`, `100%`).
- MOTION = execução de uma transformação ao longo do tempo.
- PROGRESSO = tempo puro (`tempo/duração`); a curva aplica-se depois.

## Curvas (movimento:)

linear, suave (padrão), acelerar, desacelerar, rapido, lento,
deslizar, mola (easing com overshoot), elastico, quicar, expandir,
encolher, sacudir, aparecer, desaparecer — mais aliases entrada
(= desacelerar), saida/saída (= acelerar), entrada_saida (= suave).

API interna aceita `f(t)` própria e `curva_parametrica("mola",
rigidez=, amortecimento=)`.

## Keyframes

```elixx
animação passeio {
    alvo: heroi
    duração: 2s
    movimento: suave
    0% {
        posição: 100px 100px
    }
    50% {
        posição: 300px 200px
    }
    100% {
        posição: 500px 100px
    }
}
```

Quadro guarda estado (sem →). Cada propriedade interpola entre seus
próprios vizinhos; a curva aplica-se por segmento. Mesma propriedade
em chaves e keyframes é erro (disputa explícita).

## Duração, delay, repetição, ping-pong

`duração:`, `atraso:` (progresso 0 durante o delay), `repetir: N` ou
`infinito` (determinístico, sem drift), `modo: ping_pong` (alterna
ida/volta por rodada: `repetir: 2` = ida + volta).

## Sequência e paralelo

`depois:` encadeia (mesmo motor). Animações automáticas distintas
rodam em paralelo; propriedades diferentes coexistem. `MotionGroup`
(paralelo/sequencia) organiza via API interna sobre o mesmo motor.

## Relativo e alvo dinâmico

```elixx
posição: 0px 0px -> 50px 20px
relativo: verdadeiro
```

Destino = atual + (para − de). Sem `de`, o valor é o deslocamento.
Internamente `para` aceita chamável (avaliado no início) — base do
futuro "seguir objeto" (não implementado: destino ainda é número).

## Rotação (menor caminho)

350°→10° passa por 360° (delta +20°). `voltas: 1` soma uma volta no
sentido do movimento (chaves; keyframes ignoram voltas).

## Spring dinâmico (≠ easing mola)

```elixx
fisica: mola
rigidez: 180
amortecimento: 12
massa: 1
```

Integração semi-implícita estável (subpassos 120Hz, sem explosão com
parâmetros comuns). Dura `duração`, depois snap exato. Subamortecida
ultrapassa; crítica assenta sem overshoot.

## Pausa, cancelamento, callbacks

`pausar`/`continuar` (tempo congelado), `cancelar` (para onde está).
`quando começar`, `quando terminar`, `quando cancelar` — 1x cada, em
ordem determinística. Substituição também dispara `quando cancelar`.

## Conflitos (regra explícita)

Mesmo alvo + mesma propriedade ativa: o novo substitui o antigo
(cancelado, marcado `substituida`). Propriedades diferentes coexistem.
`camada` não é animável (ordem estrutural).

## Tempo e snap

Baseado em `dt` real (16/33/50ms equivalentes); fim de rodada = valor
exato (sem `99.999999`); `duracao: 0` conclui de imediato.

## Renderers

Tk e HTML só recebem o estado calculado (sem easing/spring/keyframes
dentro deles). Saída estática sem transformação é idêntica à anterior.

## Segurança

Motion é dado + matemática + estado: sem eval, sem código remoto, sem
threads por Motion (1 dispatcher, N motions).
