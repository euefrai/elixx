# ELiXX — Animação real (Fase 03)

O motor interpola propriedades na Cena; cada renderer aplica o que
consegue. Nada de animação é calculado dentro do Tkinter.

## Sintaxe

```elixx
animação entrada {
    alvo: cartao
    posição: 0px 90px → 0px 40px
    duração: 600ms
    movimento: suave
    atraso: 200ms
    repetir: 2
    início: automatico
    depois: outra_animacao
    quando terminar {
        mostrar("pronto!")
    }
}
```

- `alvo:` nome do componente ou da janela (validado, com sugestão).
- Chaves: `posição` (1-2 valores), `tamanho` (1-2), `escala`,
  `rotação`, `opacidade` (1 valor). Forma `de → para` (seta `→` ou
  `->`) ou só destino (parte do valor atual).
- `duração:`/`atraso:` em `ms`/`s`. `repetir:` número ou `infinito`.
- `início:` `automatico` (padrão, roda ao abrir) ou `manual`
  (só via `iniciar("nome")`).
- `depois:` encadeia sequência (roda quando a outra concluir).
- `quando terminar:` callback em ELiXX.
- Ações: `iniciar`, `pausar`, `continuar`, `cancelar`.

## Movimentos (15, matemática real em `animacao/easing.py`)

suave (padrão), linear, acelerar, desacelerar, rapido, lento, mola,
elastico, quicar, sacudir, deslizar, expandir, encolher, aparecer,
desaparecer. `aparecer` liga visibilidade no início; `desaparecer`
desliga no fim.

## O que é visível de verdade (honesto)

- Posição e tamanho: sim, em qualquer widget.
- Opacidade da janela: sim (alfa real do SO).
- Opacidade de widgets: **não no Tk** (limitação do backend; o valor
  existe e interpola na Cena para backends futuros).
- Escala/rotação: interpolam na Cena; widgets Tk não aplicam.

## Regras do motor

Valores `de` ausentes capturam o atual ao iniciar. Ao concluir, o valor
final é exato (snap). `depois` nunca dispara antes da antecessora.
Animações em `px` (Fase 03); `%` em chave é erro claro em português.
