# F26 — ELiXX Studio Agent (fundação)

> "A Fase 26 implementa a infraestrutura do Agent, não um LLM."

> "O Agent trabalha sobre o modelo estruturado do ELiXX, não sobre
> cliques arbitrários na interface."

Infraestrutura segura para o futuro assistente de desenvolvimento:
contexto, intenção, plano, ChangeSet, permissões, ferramentas,
providers, tarefas, pipeline, aprovação, diagnósticos, resultado e
histórico — tudo sem LLM, sem rede, sem modelos (providers
Null/Mock/Structured; HTTP/OpenAI/Gemini/Ollama ficam para o futuro).

## Pipeline

```text
pedido → contexto → intenção → plano → aprovação → changeset
    → aplicação → validação → preview → diagnóstico → resultado
```

`executar_tarefa` (em `agent/tarefa.py`) encadeia etapas isoladas e
testáveis: `etapa_intencao/plano/ferramentas/aprovacao/
validar_preview`. Falha em qualquer ponto = estado `falhou` + evento.

## Módulos (`elixx/studio/agent/`)

- **contexto**: incremental (projeto + arquivo atual; resto por
  adição explícita), tetos (50 arquivos, 100KB/arquivo, 200 itens),
  serializável.
- **intencao**: 12 tipos (`criar_interface`…`explicar_projeto`);
  objetivo, parâmetros, contexto necessário, origem, confiança 0..1.
- **plano**: passos com dependências (ciclos recusados), ordem
  topológica determinística, risco por passo, transições validadas
  (`pendente→executando→concluido/falhou…`). Não executa sozinho.
- **mudancas**: `AgentChange` (criar/editar/excluir/renomear/mover/
  estruturada) + `ChangeSet` (validar→revisar→aprovar/rejeitar→
  aplicar→desfazer, com rollback parcial honesto). Caminhos relativos
  contidos; payloads com teto.
- **permissao**: `READ/WRITE/RENAME/DELETE/VALIDATE/COMPILE/PREVIEW`
  (negação padrão); `NETWORK/PROCESS/SHELL` reservados e sempre
  negados. Falha fechada e explícita.
- **ferramentas**: 19 declaradas (leitura, busca, análise via parser,
  validação, preview, personagem) com permissão exigida; escrita NÃO
  toca disco — retorna `AgentChange` proposto. Reusam Workspace,
  Editor, Preview e F12/F23/F24 (sem duplicar).
- **provider**: `Null` (nada gera), `Mock` (roteiro determinístico),
  `Structured` (dict → intenção/plano). Mesmo padrão do `AIProvider`
  F18, outro domínio (ver abaixo).
- **tarefa**: 12 estados, progresso, eventos, saídas, resultado.
- **aprovacao**: `manual` (propõe→humano aprova→aplica),
  `automatico_seguro` (só risco baixo em criar/editar; resto bloqueia)
  e `bloqueado` (nada aplica). Aprovação falsa = erro.
- **diagnostico/resultado**: espelham o Studio (código, arquivo,
  linha, severidade, sugestão); sem traceback bruto; `AgentResult`
  com sucesso, mudanças, arquivos, preview.
- **historico**: em memória (teto 500) + JSON opcional; desfazer de
  ChangeSet aplicado restaura conteúdos.

## Integração Studio

`elixx/studio/integracao_agent.py` (`AgentStudioBridge`): enviar
tarefa, executar pipeline, estado, plano, mudanças, aprovação,
resultado, diagnósticos. Studio funciona com o Agent desativado
(ponte ausente = F25 intacta; sem import reverso no `app.py`).

## Personagem (demonstração semântica)

Ferramentas `personagem_pose/expressao/gesto/comportamento/
transform`: "Juh levantar o braço" vira intenção → ferramenta →
`Character`/`Pose`/`Gesture`/comportamento F24 → motion F11. Sem LLM.

## F18: decisão de reuso

`AIIntent`/`AIPlan`/`AIPlannerBridge` são runtime/ação (mover,
rotas) — incompatíveis com o domínio dev/projeto. Mantidos
separados: **AI Bridge = runtime/ação; Studio Agent =
desenvolvimento/projeto**. Compartilham só primitivas (padrão
provider, `ErroELiXX`, JSON determinístico).

## Segurança

Traversal recusado (Workspace + ChangeSet), comandos fora do
vocabulário recusados, escrita sem aprovação recusada, permissões
negadas por padrão, payloads/recursão com teto, ciclos de plano
recusados, mudanças duplicadas recusadas, rollback testado, strings
maliciosas inertes, sem `eval`/`exec`/`importlib` (scan no pacote —
estendido ao `agent/`).

## Limitações honestas

Sem LLM, NLU, visão, OCR, geração por IA, planejamento autônomo
real, aprendizado, cloud, plugins, shell, internet, keyframes. O
`Mock` não entende pedidos — classifica por palavras-chave
determinísticas (documentado nos testes).

## Testes e performance

`testes/test_fase26.py`: 85 testes (contexto→histórico, pipeline
manual/bloqueado/aprovado/escrita, personagem, segurança, rollback,
determinismo, regressão F25). Performance: contexto nos tetos e
ChangeSets de 100/1000 mudanças < 60s. Demo:
`exemplos/studio-agent-demo.py` (14 passos + Juh, headless).
