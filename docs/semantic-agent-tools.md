# F36A — Semantic Agent Tool System

> "O Agent recebe ferramentas sem receber acesso arbitrário ao computador."

> "O Studio mostra a ação antes da execução."

Trinta ferramentas semânticas sobre F26/F27/F31/F32/F33/F34 — sem
duplicar o registry F26 (19 tools de runtime intactas), sem escrever
arquivos, sem LLM, sem rede.

## Arquitetura

```text
pedido → tools CONSULTA/ANALISE → proposta OPERACAO/PLANO
    → ChangeSet aprovado (F26/F33) → código → F27 → preview
```

Módulo: `elixx/studio/agent/ferramentas_semanticas.py`. Escrever não
existe aqui: o verbo máximo é PROPOR.

## Peças

- `SemanticTool` (id, nome, descrição, categoria, permissão,
  origem) e `SemanticToolRegistry` (explícito, sem plugins, sem
  import dinâmico; id duplicado = erro).
- `ToolResult` (sucesso, dados, mensagem, diagnóstico, origem,
  avisos, erros; teto de payload; nunca string solta com dados).
- `AgentToolCall` (id, tool, args validados, contexto, estado com
  transições; tetos de args e payload) e `ToolTrace` (ordem,
  `explicar()` em texto, teto 200).
- `SemanticPermissions`: READ/ANALYZE/PROPOSE; **APPLY sempre
  negado** (só Approval F26/F33 aplica).
- `executar_chamada` (permissão → args → impl → envelope) e
  `executar_sequencia` (ordem, para na 1ª falha, profundidade
  1–5; impl nunca chama tools).

## Ferramentas (30)

CONSULTA (12, READ): entidade, relações, tipo, arquivo, personagem
(F12 vinculado ou F27), partes, poses, gestos, animações, assets,
capabilities. ANALISE (4, ANALYZE): contexto, explicar, listar,
comparar. LOCALIZACAO (4, READ): código, região, entidade, diff.
OPERACAO (4, PROPOSE/READ): propor (validada, sem executar),
validar, explicar, listar. PLANO (5, PROPOSE/READ): proposta,
consulta, explicação, validação, simulação (dry-run). CODIGO (1,
READ): trecho. Ausência honesta: gestos/capabilities sem vínculo
retornam vazio + aviso (sem invenção).

## Integrações

F26 (registry e permissões intactos), F27 (única fonte),
F30 (pedido→operação), F31 (operações/explicações), F32
(localização/diff), F33 (planos/dry-run), F34 (contexto),
F35 (estágio TOOLS entre CONTEXT e OPERATIONS + nós TOOL no grafo).

## Segurança e limites

Sem `eval/exec/importlib/__import__/pickle/subprocess/os.system/
requests/shell` (scan); NaN/Infinity/recursão/payloads/traversal/
URLs recusados; strings inertes; tetos (1000 calls, 20 args,
200 resultados, 100KB payload, 200 trace, profundidade 5).
Auditoria sem segredos (args truncados, sem conteúdo sensível).

## Limitações honestas

Sem LLM/RAG/shell/internet/3D; APPLY inexistente aqui; composição
só sequencial curta; gestos exigem rig vinculado.

## Testes

`testes/test_fase36.py` (parte A+B): 133 testes. Performance:
100–10000 entidades e 100–1000 calls < 60s. Demo:
`exemplos/semantic-agent-tools-demo.py` (20 passos + `--visual`).
