# ELiXX — Motion Synthesis (Fase 16)

F15 sabe POR ONDE passar. F16 sabe COMO transformar esse caminho em
movimento visual executável. F11 continua sendo o único Motion Core.
F10 continua sendo a única base matemática. F12 continua sendo o
corpo do personagem.

```
TraversalPlan → MotionSynthesizer → MotionPlan → Motion F11
```

## Síntese ≠ execução

`sintetizar()` só descreve (waypoints do F15 preservados, um
MotionStep por etapa). `MotionPlan.executar(motor, cena)` carrega no
motor existente — sem threads, sem loop paralelo, sem física geral,
sem IA. Destino final sempre exato (snap do F11).

## Modos

Cada modo vira Motion(s) F11 com duração determinística:

| modo | síntese | padrão |
|---|---|---|
| andar | deslocamento contínuo | 200 px/s, curva suave |
| correr | deslocamento contínuo | 400 px/s |
| escalar | deslocamento no segmento | 120 px/s |
| descer | deslocamento descendente | 120 px/s |
| voar | deslocamento + orientação | 300 px/s |
| pular | keyframes 0/30/50/70/100% com ápice | altura 60px |
| pairar | desloca + 2 oscilações, fim exato | amplitude 8px |
| teleportar | posição final instantânea | duração 0 |

Duração = distância / velocidade (configurável por modo). Pulo e
pairar usam keyframes absolutos; demais usam chave simples (com
`de=None`, capturando o atual no início — robusto a pequenos desvios).

## Orientação

Direção via `atan2` na convenção ELiXX (horária, Y para baixo):
direita=0°, baixo=90°, esquerda=180°, cima=-90°. Com `orientar=True`
(padrão), a rotação vai junto (`virar_durante`) ou antes
(`virar_antes=True`, step de giro encadeado via `depois` do F11).
`teleportar` não gira. Deslocamento nulo mantém a orientação.

## Personagem

Alvo `Character` move o nó root (partes seguem a hierarquia F12).
`pose_sugerida` vai como metadado (ex. andar → "andar"); F12 decide
se executa. `relativo: True` na etapa converte waypoints em delta
para o recurso relativo do F11 (só chaves simples).

## Requisitos e erros

Requisitos da etapa avaliados contra o holder (`tem_capacidade`):
faltando → plano inviável estruturado (sem exceção). Erros
determinísticos em português para modo não suportado, etapa fora do
grafo, alvo inválido e parâmetros inválidos. Nomes e modos são dados
(sem eval/exec).

## Renderer

Tk aplica a geometria da cena a cada tick (como todo motion F11).
HTML é um instantâneo honesto do estado atual (sem fingir movimento).

## F16 não é planner, IA, física nem comportamento.
