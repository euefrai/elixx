# F28 — Semantic Agent Loop

> "O Agent consulta o Modelo Semântico, mas o Modelo Semântico não
> executa ações."

> "O ChangeSet continua sendo a fronteira entre planejamento e
> alteração do projeto."

Primeira integração funcional F26 ↔ F27, sem LLM e sem rede:

```text
pedido → consulta F27 → contexto → plano → ChangeSet F26
    → aprovação F26 → aplicação → validação → reanálise F27
    → modelo atualizado (+ diff)
```

Módulo único: `elixx/studio/agent/loop.py` (ponte; zero sistemas
novos — F26 executa mudanças, F27 representa estado).

## Peças

- **Consultas** (`consultar_modelo`): id, nome, tipo, arquivo,
  relacoes_de/para, entidade — envelope `{kind, criterio, total,
  resultados}`; delega à `ConsultaSemantica` (sem duplicar).
- **Alvo** (`resolver_alvo`): nome (+tipo) → `unico` | `ambiguo`
  (candidatos id+arquivo, sem escolher) | `nao_encontrado`.
  Ambíguo ou ausente = **sem ChangeSet**.
- **Contexto** (`SemanticContext`): entidades + relações + arquivos
  do alvo e vizinhança, com tetos (200 ent, 500 rel, 200KB);
  determinístico e serializável.
- **Plano** (`PlanoSemantico`): compõe `AgentIntent` + alvo +
  entidades + consultas + `AgentPlan` F26 + pré-condições +
  alterações propostas (conteúdo **explícito**, sem geração mágica).
- **Pré-condições** (`verificar_precondicoes`): alvo único, arquivo
  existe (workspace), operação válida, conteúdo no limite, permissão
  F26 (`criar/editar→WRITE`, `renomear/mover→RENAME`,
  `excluir→DELETE`). Falha = sem ChangeSet.
- **ChangeSet** (`gerar_changeset`): propostas → `ChangeSet` F26
  proposto; aplicação só via `ChangeSet.aplicar` (aprovação manual
  prévia, auto_seguro total ou nada; rollback F26 em falha de
  aplicação → status `aplicacao_falhou`).
- **Reanálise** (`reanalisar_modelo`): arquivos aplicados →
  `atualizar_arquivo` → `comparar_snapshots`; `diff_legivel`
  (`+id`/`-id`/`~id`, só informação).
- **Loop** (`executar_loop`): pipeline com status `concluida` |
  `concluida_com_erros` | `aguardando_aprovacao` | `alvo_ambiguo` |
  `alvo_nao_encontrado` | `precondicao_falhou` |
  `aprovacao_recusada` | `aplicacao_falhou`; registra `AgentTask` +
  `AgentResult` e histórico opcional.

## F26 / F27 / F25

- F26: intenção, plano, permissões, aprovação, ChangeSet, rollback,
  tasks, providers — reutilizados, nenhum modificado.
- F27: modelo, índice, consultas, atualização, snapshot/diff —
  reutilizados, nenhum modificado (1 melhoria honesta no adaptador:
  janela/personagem duplicada entre arquivos não aborta mais os
  membros novos — deduplicação individual preservada).
- F25: nenhuma mudança; Studio consulta via `resumo_para_inspetor`
  existente; Agent funciona sem UI.

## Segurança e limites

Traversal, payloads (500KB/mudança, 100KB entidade), recursão,
ciclos, duplicadas e aprovação falsa bloqueados; escrita sem
aprovação recusada; `NETWORK/PROCESS/SHELL` seguem negados; strings
maliciosas inertes; sem `eval/exec/importlib/__import__/pickle/
subprocess` (scan). Contexto e ChangeSet com tetos (sem cópias
gigantes).

## Limitações honestas

Sem LLM/NLU/visão/RAG/internet/shell; `Mock` não entende pedidos;
conteúdo de alteração é entrada explícita (não geração); sem watcher
(reanálise explícita); sem UI de plano; sem multiagente/3D.

## Testes

`testes/test_fase28.py`: 53 testes (contexto, consultas, ambiguidade,
inexistência, planejamento, pré-condições, ChangeSet, aprovação,
aplicação, validação, rollback, reanálise, segurança, performance
100/1000/5000 entidades e 1000 consultas, determinismo, regressão
F26/F27). Demo: `exemplos/semantic-agent-demo.py` (15 passos).
