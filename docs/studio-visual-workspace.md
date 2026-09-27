# F38 — Studio Visual Workspace 2.0 + Code Experience

Evolução incremental do Studio F29 (nada reescrito): tokens 2.0,
topbar agrupada, árvore com ícones/indentação/dirty, preview como
viewport, inspector em seções, editor com abas + highlight via lexer
oficial + sync no save, agent com sessão/proposta visível, palette
ampliada, layouts com presets, status global, atalhos completos.

## Arquitetura

```text
UI Tk (opcional) → modelos headless → F25–F37 intactos
```

Novo: `elixx/studio/ux.py` (AbasEditor, SecaoInspector, destaque
semântico, árvore, resumo do agent). Estendido: `tema.py` (novos
tokens), `workspace_ui.py` (visual), `interacao.py` (+10 comandos).

## Tokens 2.0

Somam-se aos F36: `surface_elevated/hover/active`, `danger`,
`ELIXX_GAP`, `ELIXX_FONT_SIZE/LINE_HEIGHT` (espelham fontes),
`ELIXX_PANEL_WIDTH`, `ELIXX_TOOLBAR_HEIGHT`. Accent = ação/seleção/
foco (nunca em tudo).

## Chrome e painéis

Topbar: ELiXX + grupos (Projeto/Ações) + separador + Executar Accent
+ Parar Danger quando ativo + Salvar com ● + Comandos + Layout +
Compacto, todos com tooltips via statusbar. Project: ícones por tipo,
indentação por categoria, atual (→) e dirty (●), duplo-clique abre.
Preview: toolbar (modos visuais + zoom 50–150%/Ajustar honesto +
Executar), viewport com fundo do tema, status, empty centralizado.
Inspector: seções ▾/▸ clicáveis + Ver código (F32 → editor na linha).
Editor: abas por documento, header com ●, highlight PALAVRA/IDENT/
STRING/NUMERO via lexer (fallback lexical), salvar → reparse →
modelo → preview → inspector. Agent: sessão numerada, proposta
visível, chips com rebuild, tools com detalhe. Reasoning intacto +
TOOLS. Status global: projeto, arquivo, sync, erros, Agent x/y,
fase. Empty states curtos em tudo.

## Layouts e teclado

Presets DEFAULT/FOCUS_AGENT/FOCUS_CODE/FOCUS_PREVIEW (proporções do
spec), persistidos; PanedWindow redimensionável com mínimos;
Ctrl+S/F5/Shift+F5/Ctrl+K/Ctrl+1-4/Ctrl+P/Ctrl+Shift+P/Ctrl+Enter/
Esc/Ctrl+F/F/Ctrl+Shift+G/W (sem conflito). Compacto reduz sem
remover função.

## Segurança e limites

Sem `eval/exec/importlib/__import__/pickle/subprocess/os.system/
requests/shell` (scan); traversal, payloads, NaN/Infinity, recursão
e strings inertes; escrita só aprovada; sessão nunca aplica sozinha.
Sem LLM/RAG/3D/plugins/cloud; animações só hover/expansão imediatos.

## Testes

`testes/test_fase38.py`: 143 testes (tokens→regressão F37).
Performance: 100/500/1000 arquivos, editor 100KB, 2000 buscas,
500 abas/docs, 1000 palettes/resumos < 60s. Demo:
`exemplos/studio-visual-workspace-demo.py` (20 passos + `--visual`).
Visual QA: 800x500, 1366x768, 1920x1080 sem corte/sobreposição.
