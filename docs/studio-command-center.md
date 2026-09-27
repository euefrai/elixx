# F37 — Studio Command Center + Agent Interaction

Command center do Studio: sessão do Agent (mensagens, pipeline real,
sem LLM), Command Palette, seleção global única, layouts, preview com
toolbar, inspector com Ver código, reasoning com TOOLS — sobre F25–F36
sem reescrever nada.

## Arquitetura

```text
input → AgentSession → F30 intent → F34 contexto → F36 tools
    → F31 operação → F33 plano → proposta → ChangeSet aprovado
    → F32 → código → F27 → preview
```

Novo: `elixx/studio/agent/interacao.py` (sessão, mensagens, palette,
seleção). Evoluído: `workspace_ui.py` (agent com sessão, chips com
rebuild, toolbar preview, Ver código, palette Ctrl+K, layouts,
status, tooltips), `app.py` (+4 atalhos).

## Sessão

`AgentSession`: USER→(THINKING→CONTEXT→TOOLS→PLANNING→REVIEW)→DONE/
ERROR/CANCELLED; mensagens com ordem lógica (sem relógio);
`cancelar` e `nova_sessao` nunca tocam arquivos. `CommandPalette`:
20 comandos, busca case/acento-insensível, contextuais por seleção,
execução só de rotas seguras (`executar/parar` via app; resto é
navegação/alvo). `selecao_global`: escreve só em
`app.inspetor.selecao` + evento (sem estado duplicado).

## Layouts e UX

Presets DEFAULT/FOCUS_AGENT/FOCUS_CODE/FOCUS_PREVIEW (+ Ctrl+1–4,
persistidos no layout). Preview com modos visuais + Executar.
Inspector com Ver código (F32 → abre editor na linha). Statusbar com
fase global. Empty states curtos. Tooltips via statusbar. Compacto
preservado. Tk preguiçoso; headless intacto.

## Segurança e limites

Sem `eval/exec/importlib/__import__/pickle/subprocess/os.system/
requests/shell` (scan); traversal, payloads, NaN/Infinity, recursão
e strings inertes; escrita só via ChangeSet aprovado; sessão nunca
aplica sozinha. Sem LLM/RAG/3D/plugins/cloud.

## Testes

`testes/test_fase37.py`: 122 testes (sessão→regressão UI). Demo:
`exemplos/studio-command-center-demo.py` (20 passos + `--visual`).
