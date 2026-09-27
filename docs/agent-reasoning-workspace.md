# F35 — Visual Agent Reasoning Workspace

> "O Agent mostra o que está considerando antes de agir."

> "O grafo representa o contexto; não substitui o modelo semântico."

Sessão visual/operacional do raciocínio do Agent sobre estruturas
reais (F27/F28/F30/F31/F32/F33/F34): workflow em estágios + grafo 2D
de contexto, sem LLM, sem segunda máquina de estados, sem parser novo.

## Arquitetura

```text
pedido → F30 Intent → F34 Contexto → F31 Operations → F33 Plan
    → F32 Changes → Preview, tudo observável em:
WORKFLOW (estágios) + CONTEXT GRAPH (nós/arestas) + Inspector
```

Módulo novo: `elixx/studio/agent/workspace.py` (núcleo headless; Tk
só em `workspace_ui.py`). Reuso: `AgentPlan/PlanStep/AgentTask/
AgentHistory/EventBus` (F26), `resolver_alvo` (F28), `MockIntent/
intent_para_operacao` (F30/F31), `PlanoTarefa/construir_plano`
(F33), `ChangeSet/Approval` (F26), `ContextoResultado` (F34).

## Modelo

`AgentWorkspace`: sessão (id contador, tarefa, origem), 6 estágios
(TASK…PREVIEW com estado/dados/quantidade/erros), nós/arestas,
seleção única, vista (modo, zoom, pan, filtros, busca), sessões.
Estados: IDLE→…→COMPLETED/CANCELLED/FAILED (transições validadas;
falha e cancelamento sempre possíveis). `AgentNode` (tipo do
vocabulário, rótulo, `source_id` real, score, motivos) e `AgentEdge`
(origem, tipo, destino, fonte F27/F34/…).

## Workflow e pipeline

`executar_pedido`: intent Mock → contexto F34 → operações F31 →
estágios marcados; erros viram `FAILED` com mensagem amigável (sem
traceback). `carregar_plano` respeita a ordem topológica F33;
`carregar_changes` aponta arquivo/região sem escrever. Ambiguidade =
estado `AMBIGUOUS` + candidatos (usuário resolve; sem escolha).
Cancelamento seguro (sem escrita, sem aprovação).

## Grafo 2D

Nós de entidades (F34), arquivos, operações, passos (ordem F33) e
mudanças; arestas só com nós existentes (sem invenção; RELATION vive
como aresta, documentado). Layout em camadas BFS determinístico
(mesma entrada, mesmo layout). Viewport: top-100 por score, zoom
0.5–3, pan finito, fit por bbox, filtros por tipo, busca com teto.
Expandir consulta F27 (`possui/contem`); recolher só oculta.
Seleção alimenta o Inspector (entidade/op/passo/change reais) e emite
`node_selected` no bus F25 (9 eventos novos, aditivos).

## UI (aditiva, Tk preguiçoso)

Aba Raciocínio: lista de estágios (○ ◌ ✓ ! × →), canvas com nós/
arestas clicáveis, duplo-clique expande/foca, arrasto = pan,
botões +/−/F, busca, alternância Código/Semântico herdada. Atalhos:
Ctrl+Shift+G (grafo), Ctrl+Shift+W (workflow), Ctrl+F contextual,
F (enquadrar), Esc (cancelar). Statusbar, empty/loading states,
tooltips — sem `import tkinter` no núcleo.

## Segurança e limites

Sem `eval/exec/importlib/__import__/pickle/subprocess/os.system/
requests` (scan); NaN/Infinity/recursão/payloads/traversal recusados;
strings inertes; tetos (10k nós, 20k arestas, 100 visíveis, 50
busca, profundidade 8). Sem LLM/RAG/embeddings/internet/cloud/3D;
Mock declarado como determinístico.

## Testes

`testes/test_fase35.py`: 101 testes (workspace→regressão).
Performance: 100–10000 nós (criação/layout/seleção/busca/filtro) e
serialização < 60s. Demo:
`exemplos/agent-reasoning-workspace-demo.py` (20 passos + `--visual`).
