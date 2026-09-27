# F33 — Semantic Task Planner + Studio UX

> "Uma tarefa complexa é decomposta em operações semânticas verificáveis antes de tocar no código."

> "O Planner decide a ordem das operações; a F32 continua responsável pela transformação segura em código."

Planejador determinístico de tarefas multi-etapa sobre F26/F28/F31/F32
(sem LLM, sem scheduler novo, sem segunda máquina de estados) +
evolução incremental do Studio F29 (painel de plano, diff duplo,
aprovação contextual, statusbar, atalhos, empty states).

## Arquitetura

```text
Usuário → F30 Intent → F31 Operation → F33 Planner → DAG
    → validação → aprovação → F32 → ChangeSet → código
    → parser → F27 → reanálise → preview/Studio/Agent
```

Módulo novo: `elixx/studio/agent/planejamento.py`. Reuso total:
`AgentPlan/PlanStep/AgentTask/AgentHistory` (F26),
`SemanticOperation` (F31), `resolver_alvo`/ChangeSet/Approval (F28),
`AlteracaoCodigo`/aplicação (F32). Rollback = evento + `desfazer`
F26 (estado `falhou`; sem duplicar estados).

## Planner

- `PlanoTarefa`: objetivo + operações + dependências explícitas +
  pré/pós-condições + `AgentPlan` + `AgentTask`. IDs de passo
  `passo_N` determinísticos (contador, sem hash).
- `construir_plano`: valida referências, soma auto-cadeia por arquivo
  (operações no mesmo arquivo viram sequência — anti-conflito de
  região), ordena via DAG F26 (ciclos falham cedo), gera condições.
- Pré: alvo único, arquivo existe; pós: entidade existe, valor
  esperado relido do código (anti-drift honesto).
- `dry_run`: passos/arquivos/entidades/riscos **sem escrever**.
- `preparar_execucao` (ChangeSets sem aplicar) → aprovação externa →
  `executar_plano` (revalida anti-stale, compara com o preparado,
  aplica, verifica pós, rollback reverso em falha, histórico).
- `explicar_plano`: texto PT fixo (nº etapas, lista, arquivos,
  entidades, aviso de aprovação).
- `PainelPlano` (headless): passos com estados, seleção, diff por
  passo, aprovar/recusar/cancelar, progresso real (concluídos/total),
  resumo.

## Diff duplo

Por passo: código (trocas F32, compacto) e semântico
(`parte:Juh.corpo.rotacao: rotacao: 0 -> rotacao: 15`). Alternância
Código/Semântico no painel.

## Studio UX (aditivo, sem reescrever F29)

Aba inferior `plano` (passos com ícones ○ ▶ ✓ ✗ — ❌; detalhe com
diff), botões Revisar/Aprovar/Cancelar, statusbar (projeto | arquivo |
sincronizado | erros | Agent x/y), tooltips via statusbar, atalhos
Ctrl+P (busca), Ctrl+Shift+P (comandos), Ctrl+Enter (aprovar),
Esc (cancelar), empty states, layout persistido em
`.elixx/layout.json` (só dados locais), tema clam compacto.
Tk continua preguiçoso; testes 100% headless.

## Segurança e limites

Traversal, payloads (5000 passos), recursão, ciclos, NaN/Infinity e
strings inertes; escrita só com ChangeSet aprovado; auto-seguro
recusa risco médio; sem `eval/exec/importlib/__import__/pickle/
subprocess` (scan). Sem LLM/RAG/shell/internet/paralelismo real/3D;
condições F31 seguem planejadas.

## Testes

`testes/test_fase33.py`: 82 testes (task→regressão F32). Performance:
100/500/1000 operações, 100/500/1000 arquivos e dry-run de 100
passos < 60s. Demo: `exemplos/task-planner-demo.py` (18 passos +
`--visual` 4s).
