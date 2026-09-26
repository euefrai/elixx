# F25 — ELiXX Studio (fundação)

> "O Studio é uma ferramenta de desenvolvimento do ELiXX, não uma
> dependência necessária para executar aplicações ELiXX."

> "Código e visual são representações diferentes do mesmo projeto."

Ambiente oficial de desenvolvimento visual: projeto, arquivos, editor,
preview (Tk + headless), inspetor, assets, timeline, console,
diagnósticos, comandos, eventos e configuração — sobre o MESMO modelo
semântico do compilador/runtime (Fonte → Parser → AST → modelo →
preview; nunca regex-gambiarra, nunca mini-ELiXX paralelo).

## Arquitetura

```text
                ELiXX STUDIO
                     │
       ┌─────────────┼──────────────┐
       ↓             ↓              ↓ (futuro)
    EDITOR        VISUAL          AGENT
       │             │              │
       └─────────────┼──────────────┘
                     ↓
               PROJECT MODEL
                     ↓
                 ELiXX AST
                     ↓
                  RUNTIME
                     ↓
                   OUTPUT
```

Pacote `elixx/studio/`: `app`, `projeto`, `workspace`, `documento`,
`arquivos`, `editor`, `preview`, `inspetor`, `assets`, `cena`,
`comandos`, `estado`, `eventos`, `logs`. Lógica do Studio não vaza
para o runtime.

## Módulos

- **Projeto** (`projeto.py`): `projeto.elixxproj`
  `{nome, versao, entrada, descricao}`; valida tipos, caminhos
  relativos, versão 1 e chaves; carregar nunca executa.
- **Workspace** (`workspace.py`): criar/abrir/fechar/salvar/
  recarregar; contenção anti-traversal em toda operação.
- **Documentos** (`documento.py`): texto, versão, dirty, cursor,
  seleção, undo/redo (teto 100); múltiplos abertos.
- **Arquivos** (`arquivos.py`): listar (pastas primeiro, lazy por
  nível), criar, renomear, excluir **só com confirmação explícita**.
- **Editor** (`editor.py`): inserir, desfazer/refazer, localizar/
  substituir, linhas, cursor; diagnósticos `ELX001` (léxico/sintaxe),
  `ELX002` (semântica), `ELX000` (info/interno) via compilador oficial.
- **Preview** (`preview.py`): `HeadlessPreview` (validar→compilar→
  executar→cena→resumo, sem janela) e `TkPreview` (mesmo pipeline +
  janela; `disponivel()` sem display). Abrir ≠ executar: só
  `executar()` roda, pelo pipeline oficial. Botões: executar, parar,
  recarregar.
- **Inspetor** (`inspetor.py`): `Selecao` (nó/personagem/parte/asset/
  arquivo), props reais de `NoVisual`/`Character` (nada inexistente),
  `InspecaoPersonagem` (pose, expressão, view, transform, partes,
  joints, comportamentos) e `fluxo_personagem` (imagem/dados →
  analyzer Mock/Structured → rig F23 → deformation F24 → Character).
- **Assets** (`assets.py`): varredura por metadados, categorias
  (imagens/sons/vídeos/personagens/outros), tamanho com teto,
  `validar` com `detectar_tipo` da F07 (sem executar nada).
- **Cena/Timeline** (`cena.py`): `ModeloCena` (janelas/nós/
  personagens) e `Timeline` (trilhas por alvo, tempos finitos ≥ 0;
  visualização de motions F11 via `timeline_de_motions`; edição de
  keyframes é futura).
- **Comandos** (`comandos.py`): `StudioCommand` (nome+alvo+params
  JSON, sem callable), `FilaComandos` FIFO, atalhos
  (Ctrl+O/S, F5, Shift+F5, Ctrl+Z/Y/F). `executar_comando` no
  `StudioApp` é a porta única (futuro Agent fala por aqui).
- **Eventos/Logs/Config** (`eventos.py`, `logs.py`, `estado.py`):
  bus síncrono ordenado (10 eventos); console INFO/WARNING/ERROR sem
  traceback bruto; configuração só dados locais (segredos recusados).

## Code ↔ Visual

Base segura implementada: documento → parser → AST → cena/personagem
→ preview/inspetor/timeline. Alteração de propriedade passa por
comando estruturado (`alterar_propriedade`) aplicado via APIs
(`aplicar_pose`, deformation); nada via regex frágil. Sincronização
bidirecional total é futura (o Agent usará `AgentProposal`/
`AgentChange`/`AgentContext`, já esboçados — sem agente nesta fase).

## Segurança

Traversal recusado, exclusão confirmada, paths validados, abrir≠
executar, sem plugins automáticos, sem imports dinâmicos, sem
eval/exec, sem subprocess, sem rede, sem segredos na config, sem
tokens no projeto. Scan por `eval(`/`exec(`/`importlib`/
`__import__` em todo o pacote (testes 34–36).

## Testes e performance

`testes/test_fase25.py`: 56 testes (lista §30 + stubs do Agent,
contrato Tk, atalhos, inspetor de nó, modelo de cena). Performance:
100 assets, 1000 arquivos e 100/1000 partes do fluxo medidos < 30s;
árvore lazy por nível; bytes de assets nunca carregados na varredura.
Demo: `exemplos/studio-demo.py` (10 passos; headless por padrão, UI
opcional com display).
