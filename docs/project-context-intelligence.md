# F34 — Project Context Intelligence

> "IA futura deve receber contexto, não o projeto inteiro."

> "O contexto é selecionado pelo significado da tarefa."

Camada determinística entre intenção/tarefa e operações: dado o
modelo F27 + tarefa, responde "quais partes do projeto importam?" com
scores explicáveis — sem ML, sem embeddings, sem rede. Só leitura:
nunca executa, nunca escreve.

## Arquitetura

```text
F30 Intent → F34 Context Engine → Task Context → F31 Operations
    → F33 Planner → F32 → ChangeSet → código → F27 → preview
```

Módulo novo: `elixx/studio/agent/contexto_tarefa.py` (+ exports).
F26 `agent/contexto.py` (AgentContext) intacto — nomes separados de
propósito (`ContextoTarefa` vs execução).

## Engine

`construir_contexto(modelo, tarefa, config)`:
1. sementes (alvo resolvido, seleção, menções no objetivo);
2. pontua tudo em uma passada O(n);
3. expande por relações até a profundidade (BFS com visitados);
4. overrides manuais (prioridade sem quebrar validade);
5. escala max→1.00, ordena (-score, id), aplica budget.

## Sinais e scores

Pesos fixos (`PESOS`): alvo_explicito 1.00, nome_exato 0.30,
selecionada 0.20, tipo/operacao_compativel 0.15, relacao_direta 0.25,
transitiva 0.10, pai/filha 0.12, mesmo_arquivo 0.10, mesma_cena 0.08,
recurso 0.10. Ação→tipos (`ACAO_TIPOS`) direciona à tarefa (mover→
corpo/cena; pose→poses...). Cada motivo é registrado; `por_que(id)`
responde "por que estou no contexto?".

## Categorias, modos e budget

13 categorias (ALVO, PERSONAGEM, PARTE, POSE, ..., SUPORTE).
Modos minimo/expandido/completo (completo ainda com teto — nunca o
projeto inteiro por padrão). Orçamentos configuráveis (entidades,
relações, arquivos, recursos, profundidade, bytes, por categoria);
ao atingir: sem quebrar, motivo registrado (`orçamento ...`),
determinístico. Excluídas listadas (amostra + resumo além de 200).

## Overrides e ambiguidade

`incluir`/`excluir` manuais viram origem `manual` com motivos
`INCLUIDO/EXCLUIDO_MANUALMENTE`. Ambiguidade do alvo é registrada
(com candidatos), sem escolha silenciosa (reuso `resolver_alvo`).

## Integrações (sem tocar F25–F33)

F27 (única fonte, sem duplicar), F30 (intenção→tarefa), F31
(operações indicam tipos), F33 (`ids_relevantes` para o planner),
F32 (arquivos guiam reanálise). Studio: seção CONTEXTO DA TAREFA
(resumo + Ver contexto com filtro/categorias, incluir/excluir,
detalhe de motivos). Preferências em `.elixx/contexto.json` (só
modo/filtros/orçamento).

## Segurança e limites

Sem `eval/exec/importlib/__import__/pickle/subprocess/os.system/
requests` (scan); NaN/Infinity/recursão/payloads/traversal
recusados; strings inertes; scores finitos. Sem LLM/RAG/embeddings/
internet/shell/3D/plugins.

## Testes

`testes/test_fase34.py`: 80 testes (criação→regressão F27/agent).
Performance: 100/500/1000/5000/10000 entidades < 60s. Demo:
`exemplos/context-intelligence-demo.py` (17 passos + `--visual`).
