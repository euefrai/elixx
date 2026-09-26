# ELiXX — Behavior Synthesis (Fase 17)

F16 sabe COMO SE MOVIMENTAR. F17 sabe COMO O PERSONAGEM DEVE SE
COMPORTAR DURANTE ESSE MOVIMENTO. Não decide objetivos, rotas ou
ações: não é IA, planner, física ou comportamento autônomo.

```
TraversalPlan
      ↓
MotionSynthesizer F16
      ↓
MotionPlan
      ↓
BehaviorSynthesizer F17
      ↓
BehaviorPlan
  ├── Motion F11
  ├── Pose F12
  ├── Gesture F12
  ├── Expression F12
  └── sincronização
          ↓
    Character F12 → Transform F10 → Renderer
```

## Síntese ≠ execução

`BehaviorSynthesizer(...).sintetizar(motion_plan, character)` só
descreve: cada MotionStep F16 vira um BehaviorStep com pose, gesto,
expressão, eventos e requisitos. `BehaviorPlan.executar(motor, cena,
character)` clona os motions (o MotionPlan segue reutilizável),
pendura ganchos, carrega no motor existente e dispara — sem threads,
sem loop paralelo, sem scheduler novo.

## Camadas por step

Ordem determinística `emergencia > gesto > comportamento > padrao`;
expressão é camada separada e nunca sobrescreve pose corporal (partes
ocupadas são puladas e registradas em `expressao_pulada`). Pose pode
vir do modo (`andar` → "andar", `pular` → "pulo", `voar` → "voando"),
de mapa explícito ou de `pose_padrao`; ausente = sem pose, sem erro.
Gestos usam `Gesture`/MotionGroup do F12 (nomes via
`registro_gestos`); expressões são poses F12 (`expressao=True`).

## Sincronização (só F11)

- início do motion → snapshot + pose + gesto + expressão
  (gancho `ao_comecar`; callbacks anteriores preservados e executados
  primeiro);
- meio → `BehaviorEvent(quando="ao_meio")` via marcador: motion vazio
  com atraso = metade da duração (reuso de `atraso` + `ao_comecar`);
- fim → encerra gestos do step, restaura snapshot (se `restaurar`) e
  aplica `pose_fim` (se dada);
- cancelamento → encerra gestos, restaura, sem prender pose/gesto;
  permanente do personagem nunca é apagado.

## Requisitos e estados

Requisitos do step validados contra o holder (`tem_capacidade`):
faltando → plano inviável estruturado (`viavel=False`, motivo, sem
exceção). Estados corporais (`parado`, `andando`, …) são dados por
modo, personalizáveis. Erros de programação (modo/gesto/pose
inexistente, personagem inválido) são determinísticos em português.

## Tracks e debug

Todo plano monta as 4 tracks (`movimento`, `pose`, `gesto`,
`expressao`) com `(step, carga)` por passo.
`debug_comportamento(plano)` imprime estado/motion/pose/gesto/
expressão/etapa sem mover nada (puro). HTML compila normalmente
(instantâneo honesto, sem fingir animação).

## F17 NÃO é IA, planner, física ou comportamento autônomo.
