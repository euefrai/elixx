# F31 — Semantic Actions, Events & Operations

> "SemanticOperation não é uma nova linguagem."

> "A operação semântica descreve uma intenção operacional; a execução
> continua pertencendo às estruturas existentes do ELiXX."

Camada de dados entre `AIIntent` (F18/F30) e execução (F12/F26/F28):
operações tipadas, referências resolvidas no F27, eventos com gatilho
e efeitos, composição ordenada — sem parser novo, sem AST novo, sem
motores novos.

## Arquitetura

```text
pedido → AIIntent → SemanticOperation → F27 resolve
    → runtime (ferramentas F26) ou arquivo (ChangeSet aprovado)
    → reanálise → preview
```

Módulo: `elixx/studio/agent/operacoes.py` (único arquivo novo de
código; `__init__` só ganha exports).

## Operações e categorias

20 tipos em 6 categorias: visual (mostrar/esconder/mover/
transformar), personagem (pose/expressao/gesto/direcao), animacao
(animar/iniciar/parar), evento (adicionar/remover/associar),
projeto (adicionar/remover/alterar/alterar_propriedade) e consulta
(consultar/selecionar — somente leitura, nunca ChangeSet).
Parâmetros tipados com limites (duracao/distancia/valor finitos;
unidade em px/s/ms/deg/%).

## Referências

`SemanticReference(nome, tipo?)` resolve via `resolver_alvo` F28
(reuso, sem duplicar): 0 → erro, 1 → resolvido, N → ambíguo (sem
ChangeSet até desambiguar).

## Eventos e composição

`SemanticEventOperation`: gatilho com evidência no runtime (`quando
<nome>` livre; documentados: clique, pressionar, aparecer, terminar,
comecar, cancelar) + efeitos ordenados + modo sequencia/paralelo
(vocabulário F11) + condição opcional **planejada** (sem execução).
`snippet_evento` gera template `quando … {}`; proposta de evento
mescla no arquivo do alvo e **só vira ChangeSet se o mesclado passar
no parser** — como `quando` não é top-level, a recusa é documentada
em vez de chute (limitação honesta).

## Pontes

`intent_para_operacao` (F30→F31, evento vira operação de evento),
`operacao_para_intent` / `operacao_para_ferramentas` (volta via F30;
`mover` exige base), `operacao_para_proposta` (op de arquivo →
ChangeSet F26 com pré-condições e aprovação; nunca escrita direta),
`explicar_operacao` (frases PT determinísticas).

## Segurança e limites

Sem `eval/exec/importlib/__import__/pickle/subprocess` (scan);
traversal barrado no ChangeSet; NaN/Infinity/gigantes/recursão/
ciclos recusados; strings inertes; tetos (20 params, 10 efeitos).
Consultas não tocam disco; alteração sem aprovação não aplica.

## Limitações honestas

Sem LLM/RAG/shell/internet/3D; condição é representação; sem
scheduler/runtime novo; proposta de evento exige mesclado válido;
sem UI de eventos (só chat textual existente).

## Testes

`testes/test_fase31.py`: 72 testes (operações→regressão F28/F30).
Performance: 5000 ops, 1000 resoluções e 1000 consultas < 30s.
Demo: `exemplos/semantic-actions-demo.py` (18 passos + evento).
