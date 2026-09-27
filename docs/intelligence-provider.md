# F30 — Intelligence Provider & Natural Intent

> "O Provider interpreta pedidos; ele não executa ações."

> "A Intent é uma descrição de intenção, não código executável."

Camada desacoplada texto→`AIIntent` sobre F18 (sem segundo sistema de
intenção): providers futuros (local, remoto, multimodal) herdam
`IntelligenceProvider` sem tocar Agent, modelo ou ChangeSet.

## Arquitetura

```text
pedido → IntelligenceProvider → AIIntent (F18) → Agent F26
    → F27 → loop F28 → plano → ChangeSet → aprovação → preview
```

Módulo: `elixx/studio/agent/inteligencia.py` (+ chat no Studio F29).

## Reuso F18 (decisão)

`AIIntent` (tipo/personagem/alvo/destino/modo/pose/expressao/
prioridade/contexto/parametros + `from_dict` forte) e `AIProvider`
(nome + `gerar_intencao`) são reutilizados. F18 valida ações runtime
(mover/ir/olhar…); F30 valida ações studio (`validar_intent`) —
domínios separados, primitivas compartilhadas. `texto_para_intencao`
F18 continua reservado (não implementado lá); o Mock F30 ocupa a
fronteira com vocabulário documentado.

## Ações e Mock

12 ações (`mover/mostrar/esconder/animar/expressao/pose/selecionar/
consultar/adicionar/alterar/remover/associar_evento`); alteração só
via F28. `MockIntentProvider`: PT normalizado (caixa de nomes
preservada para o F27), p. ex. "faça a Juh acenar" → pose/Juh/acenar;
fora do vocabulário = `INTENT_NAO_SUPORTADA` (erro, sem invenção);
ambíguo sem nome = alvo ausente (F28 resolve ou pede esclarecimento).

## Contexto e validação

`IntentContext`: projeto, arquivo, selecionado, entidades (só
id/tipo/nome/arquivo/partes/poses — segredos cortados) e ações;
`contexto_de_intencao` constrói sem vazar nada. `validar_intent` →
`{valido, codigo, motivo}` (ação, alvo, parâmetros, direção,
finitude, payload 20 params / 2000 chars pedido).

## Pontes F26/F28

`intent_para_agentintent` (ação→tipo F26 documentado),
`intent_para_ferramentas` (pose/expressão/gesto/comportamento/
transform; `mover` exige base `{posicao}` — deslocamento relativo,
nunca chute; alteração/consulta retornam `[]` = via loop).
`explicar` devolve o rastro pedido→intenção→consulta→plano→ChangeSet.

## Studio

`AgentChat` headless (turno = intent + validação + resolução F27 +
histórico; mostra `mock: true`) e painel ELiXX AGENT no Studio
(entrada + histórico + plano/proposta, aditivo na UI F29).

## Segurança e limites

Sem `eval/exec/importlib/__import__/subprocess/pickle/requests`
(scan); traversal/URLs/shell/injection inertes; NaN/Infinity/
recursão/gigantes recusados; provider registry explícito (sem
plugins/import dinâmico); pedido e parâmetros com teto.

## Limitações honestas

Sem LLM/OpenAI/Gemini/Ollama/modelos/embeddings/RAG/internet/API
keys/visão/shell/multiagentes/3D; sem streaming (síncrono); Mock
cobre só o vocabulário documentado.

## Testes

`testes/test_fase30.py`: 63 testes (provider→regressão F18/F26/F28).
Performance: 1000 intents e 100/1000/5000 entidades < 30s. Demo:
`exemplos/intelligence-provider-demo.py` (16 passos headless).
