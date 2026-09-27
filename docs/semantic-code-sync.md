# F32 — Semantic Code Synchronization

> "IA cria ou edita a intenção; o ELiXX controla a transformação segura em código."

> "O código continua sendo a fonte executável; o modelo semântico é sua representação estruturada."

Infraestrutura determinística código ↔ modelo sobre F26/F27/F28/F31,
sem regex cega, sem parser novo, sem LLM: localização por evidência
AST → alteração cirúrgica → candidato validado no parser → ChangeSet
aprovado → aplicação → reparse → modelo → diff.

## Arquitetura

```text
Código → Parser → AST → F27 → Modelo → F31 Operation
    → F32 Code Generator → ChangeSet → Approval → Apply
    → Parser → F27 → Studio / Agent / Preview
```

Pacote `elixx/studio/codigo/`: `localizacao`, `mudanca`, `gerador`,
`sincronizador` (+ `__init__`).

## Localização (evidência, nunca chute)

`LocalizacaoCodigo` (arquivo, linhas, tipo, entidade, evidência
`ast:*`); `localizar_entidade` casa tipo+nome na AST (classe confere —
homônimos de tipo errado não casam); `localizar_propriedade` desce
até o dono (janela/personagem/parte/componente) e casa a Propriedade.
Sem par = `CODIGO_LOCALIZACAO_INDISPONIVEL`. `RegiaoCodigo` valida
conteúdo atual antes de aplicar (mudança externa = recusa
`CODIGO_REGIAO_ALTERADA`).

## Alteração cirúrgica

`AlteracaoCodigo` (INSERIR/SUBSTITUIR/REMOVER + região + antes/depois
+ motivo + entidade + origem; JSON puro). Uma linha por vez;
indentação preservada; resto do arquivo intocado. Gerador só aceita
propriedade localizada com `valor_texto` explícito, snippet explícito
no fim, ou remoção de linha localizada — fora disso,
`GERADOR_NAO_SUPORTADO`.

## Validação pré/pós e rollback

Pré: região íntegra + candidato parseia + entidade relocalizável.
Sem aprovação: `CODIGO_APROVACAO_NECESSARIA` (ChangeSet proposto de
volta). Pós: reparse + `atualizar_arquivo` + diff; falha crítica =
`desfazer` F26 (`CODIGO_ROLLBACK`). Erros com código (`CODIGO_*`),
nunca traceback cru.

## Bidirecional sem loop

`codigo_para_modelo` (reparse explícito), `operacao_para_codigo`,
`sincronizar` com hash por arquivo (mesma versão não ressincroniza)
+ versão incremental. `diff_textual` (linhas, headless) e diff
semântico via snapshots F27 (entidades adicionadas/removidas/
alteradas).

## Integrações (sem tocar F25–F31)

`sincronizar_workspace` (Studio: modelo + árvore + preview +
diagnósticos), pontes Agent via `operacao_para_codigo` +
`aplicar_com_changeset`. F31 continua gerando propostas de snippet;
F32 cuida da via cirúrgica por propriedade.

## Segurança e limites

Traversal/absolutos, payloads (100KB/mudança), NaN/Infinity,
recursão e strings inertes; sem `eval/exec/importlib/__import__/
pickle/subprocess` (scan); parser só parseia (nunca executa).
Sem LLM/RAG/shell/internet/3D; sem reescrita de arquivos; poses e
construções sem evidência de linha = não suportado (honesto).

## Testes

`testes/test_fase32.py`: 75 testes (localização→diagnóstico Studio).
Performance: 100/500/1000 arquivos, localização/diff/sync e 200
operações < 60s. Demo: `exemplos/code-sync-demo.py` (rotação 0→15
aprovado →30 externo, 20 passos).
