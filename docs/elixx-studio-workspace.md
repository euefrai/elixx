# F29 — ELiXX Studio Visual Workspace

> "O Studio é uma interface sobre o projeto ELiXX; ele não mantém uma
> cópia paralela da lógica do projeto."

Evolução incremental do Studio F25 (nada reescrito): layout com
painéis alternáveis, árvore categorizada, editor com destaque e
diagnósticos navegáveis, preview sincronizado com seleção via F27,
inspector estruturado com propostas via ChangeSet, painel Agent (F28
sem LLM), timeline/console/diagnósticos em abas, modo compacto e
geometrias validadas — tudo headless-testável, Tk opcional e preguiçoso.

## Arquitetura

```text
UI (Tk, opcional)
 ↓
StudioWorkspace (headless)
 ↓
F25 (projeto, docs, preview, logs) · F27 (modelo) · F26/F28 (mudanças)
 ↓
arquivo → reanálise → preview atualizado
```

Módulo único novo: `elixx/studio/workspace_ui.py`. Regra de escrita:
**UI → proposta → ChangeSet F26 → aprovação → arquivo → reanálise**;
o Inspector nunca escreve direto.

## Painéis (modelos headless)

- **Layout**: 8 painéis (visibilidade, tamanhos 0.05–0.9, aba
  inferior console/timeline/diagnosticos), modo compacto (oculta
  projeto+agent), geometrias 800x500–3840x2160, serializável.
- **Project** (`ArvoreProjeto`): `.elixx` + assets reais +
  personagens/cenas do F27 (nada inventado); abrir/selecionar/
  atualizar; isolamento e traversal do Workspace.
- **Editor** (`EditorModelo`): dirty, cursor, undo/redo (F25),
  destaque lexical próprio (palavras/strings/números; ELiXX sem
  comentários), diagnósticos ELX001/ELX002 com `ir_para`.
- **Preview** (`PreviewModelo`): `HeadlessPreview` + cartões de
  entidades F27 (lista esquemática rotulada — sem geometria fingida);
  selecionar emite `selecionado` e alimenta o inspector.
- **Inspector** (`InspectorModelo`): seções Tipo/Arquivo/Linha,
  Relações, Personagem (pose, direção, partes, poses) e Transform
  (só campos reais); `propor_alteracao` gera `AgentChange`
  sem tocar disco.
- **Agent** (`PainelAgent`): contexto, consultar, planejar (aceita
  nome ou id), propor (pré-condições + ChangeSet, sem aplicar).
- **Console** (`ConsoleModelo`): INFO/WARNING/ERROR/AGENT/BUILD/
  PREVIEW, filtro por categoria, limpeza, sem traceback bruto.
- **Diagnósticos** (`DiagnosticosModelo`): total/erros/validez e
  navegação (arquivo, linha).
- **Timeline**: `Timeline` F25 + `timeline_de_motions` F11
  (visualização; keyframes futuros).
- **Estado** (`StudioWorkspace.estado`): salvo, pendências,
  executando, erros, analisando, projeto — todos reais.

## Tk (`montar_workspace_ui`)

Toolbar com ações reais (Salvar/Executar/Parar via comandos +
indicador ●), `PanedWindow` redimensionável, editor com números de
linha + destaque + `●` dirty no título, abas inferiores, diagnósticos
clicáveis (via dados), preview por cartões com seleção, inspector em
seções, agent com Consultar/Planejar-Propor, console com filtro.
Tudo `import` preguiçoso; nenhum `import tkinter` em nível superior
(testado).

## Segurança e limites

Traversal, exclusão sem ChangeSet aprovado, propriedades sem tradução
segura, seleções/entidades inexistentes e execução de não-texto
recusados; sem `eval/exec/importlib/__import__/pickle/subprocess`
(scan); strings inertes; diagnósticos sem stack. Sem watcher, polling
ou processos extras.

## Limitações honestas

Sem LLM/chat, geração por IA, keyframes, rig/mesh editors, node graph,
plugins, cloud ou 3D; preview sem geometria real (cartões); edição do
inspector só via proposta (conteúdo exato na aprovação); sincronização
bidirecional total futura.

## Testes

`testes/test_fase29.py`: 64 testes (layout→regressão F25/F28).
Demo: `exemplos/studio-workspace-demo.py` (19 passos headless +
`--visual` 4s com display).
