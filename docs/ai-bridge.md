# ELiXX — AI Bridge (Fase 18)

Ponte segura entre IA/agente externo e ELiXX. A IA declara INTENÇÃO;
o ELiXX valida, planeja com os sistemas existentes e executa apenas
estruturas permitidas. Este módulo NÃO contém inteligência artificial,
LLM, NLP, física ou comportamento autônomo.

```
IA / agente externo
        ↓
AIIntent (só dados)
        ↓
IntentValidator (estrutura + referências, sem executar)
        ↓
AIPlannerBridge
        ↓
Capability check F14 → Navigation F15 → Motion F16 → Behavior F17
        ↓
Character F12 → Transform/Motion F10/F11 → Renderer
```

## Intenção

```python
{"tipo": "mover", "personagem": "Heroi", "destino": "Torre",
 "modo": "andar", "pose": "andar", "expressao": "feliz"}
```

Tipos aceitos: mover, ir, olhar, apontar, interagir, pegar, equipar,
usar. Pipeline completo hoje: mover, ir. Demais tipos válidos retornam
`suportado=False` (honesto, sem fingir). Campos fechados; valores só
JSON puros e finitos; destino texto ou `{"x","y"}`.

## Validação

Estruturada (`valido/codigo/motivo`, sem exceção no normal):
tipo/personagem/destino/modo/pose/expressão verificados contra a
cena. O personagem entra no grafo por caminho explícito (sem origem
inventada).

## Planejamento (dry-run)

`planejar` == `simular`: nunca movimenta. Fluxo mover/ir: capability
do modo (se explícito) → rotas F15 (até 3, com holder) → modo
explícito filtra por presença (sem ranking subjetivo) → 0 rotas:
inviável; >1: `requer_escolha` com resumos (sem escolher
silenciosamente); 1: TraversalPlan → MotionPlan → BehaviorPlan
(pose/expressão via `pose_padrao`/`expressao_padrao`).

## AIPlan e execução

`AIPlan` carrega intent, validação, os três planos, requisitos,
avisos, rotas, flags (viavel/suportado/executavel/requer_escolha) e
log de eventos (criado/validado/rejeitado/iniciada/falhou).
`executar(plano, motor)` só aceita plano aprovado e delega ao
`BehaviorPlan.executar` (F17); `cancelar` usa o motor (restauração
pelos ganchos F17). `debug_aiplan` imprime intenção→capacidades→
rota→motion→behavior→execução sem mover.

## Contexto e fronteiras

`contexto()` devolve snapshot limitado (posição, capacidades,
equipados, próximas num raio, destinos, rotas possíveis, estado);
usa WorldSnapshot onde cabe, sem copiar o mundo. `AIProvider` é a
interface neutra (modelo local, API, JÚLIA, Fajulto — sem acoplamento;
núcleo funciona sem LLM). `texto_para_intencao` existe só como
fronteira explícita não implementada (sem NLP improvisado).

## Segurança

Nomes e parâmetros são dados inertes em todos os caminhos: nenhuma
chamada de avaliação/execução dinâmica, importação programática,
processo externo, código remoto ou execução de texto como código.
