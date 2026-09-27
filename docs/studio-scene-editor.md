# ELiXX Studio — Scene Editor + Adaptive Workspace (F39)

Camada de interação sobre o Preview e o modelo semântico. Não é um
segundo renderer, parser, modelo, seleção, EventBus, Planner, Context
Engine ou Tool Registry: tudo é reutilizado de F10–F38.

## Scene Editor (`elixx/studio/scene_editor.py`)

`SceneEditor(inspetor, eventos)`:

- **Modos** (`MODOS_F39`, reuso de `cena.MODOS_CENA`): Selecionar,
  Mover, Escalar, Girar, Ajustar. Só **Mover** possui transformação
  real (propriedade ELiXX `posicao` via proposta); Escalar/Girar ficam
  "preparados" com motivo honesto (`gizmo_status`).
- **Seleção**: usa a seleção global (`Inspetor` + evento
  `selecionado`/`node_selected`). Bidirecional: Scene Tree ↔ Preview
  (`PreviewModelo.selecionar`) ↔ Inspector ↔ Code.
- **Destaque**: `destaque()` devolve `{node_id, estilo: outline}`
  discreto, só para o nó real selecionado.
- **BoundingBox**: `bbox_entidade` lê dados reais quando existem;
  caso contrário os campos são `None` (sem invenção).

## Viewport

`ViewportState` (F25, `elixx/studio/cena.py`): zoom, `offset_x`,
`offset_y`, modo — tudo serializável (`to_dict`/`from_dict`).

- **Zoom** (`ZOOM_F39` = 25/50/75/100/125/150/200/Ajustar): valor
  real aplicado em `para_tela`/`da_tela`; `zoom_mais`/`zoom_menos`.
- **Pan**: `pan(dx, dy)`; não bloqueia a seleção.
- **Fit/center**: `fit(larg, alt, conteudo_w, conteudo_h)` escolhe o
  maior nível que cabe; `centralizar()` zera offsets; `ajustar()`
  volta a "Ajustar".
- **Grid**: on/off; respeita zoom/pan; não interfere na seleção;
  usa cores do Design System.
- **Snap**: 0 (livre) / 1 / 5 / 10, via `snap_valor`; só aplicado
  quando há transformação real (`propor_mover`).

## Scene Toolbar

`SceneToolbar(editor)`: 10 itens em 3 grupos (modo | zoom | vista),
cada um com `tooltip`. `acionar(id)` executa a ação real. O snap
cicla 0→1→5→10.

## Scene Tree

`SceneTree.construir(modelo)` (F25): janelas → personagens/
componentes → partes, usando **apenas** relações `contem`/`possui`
de F27. Sem relação real, sem filho (sem invenção). `linhas()`
renderiza `▾/▸/├/└`; `alternar()` recolhe/expande; `visiveis()`
respeita recolhidos.

## Inspector visual

`InspectorModelo.inspecionar` mostra seções reais (inclui Transform
quando o nó possui os campos). `propor_alteracao` / `propor_mover` /
`propor_transformar` **nunca escrevem**: devolvem `ChangeSet`.

Fluxo: Inspector → `SemanticOperation` (F31) → Planner (F33) →
`ChangeSet` → `Approval` → `Code Sync` (F32). `PropostasTracker`
(`elixx/studio/ux.py`): adicionar → aprovar → aplicar → desfazer
última. Propostas pendentes não entram no histórico do projeto.

## Visual ↔ Code

- `ir_para_codigo(editor_modelo, modelo, ent_id)`: F27+F32
  (`localizar_entidade` → `ir_para`); sem região, erro honesto.
- `entidade_do_cursor(modelo, arquivo, linha)`: entidade com maior
  linha ≤ cursor (`entidade_na_linha`); `None` sem correspondência.

## Adaptive Workspace

`WorkspaceModes`: DEFAULT (Project+Scene+Inspector), CODE
(Project+Code), SCENE (Scene dominante), AGENT (Agent dominante),
REVIEW (Code+Diff+Changes). Só visibilidade — nenhum estado de
painel é destruído. Os presets também estão em `LAYOUTS`
(CODE/SCENE/AGENT/REVIEW, aditivos aos F37).

## Focus Mode

`FocusState` (`ux.py`): `entrar(layout, paineis)` guarda o anterior;
`sair(layout)` restaura. `Esc` volta ao layout anterior.

## Bottom Workspace

`BottomWorkspace`: abas CODE/AGENT/REASONING/PLAN/CHANGES/CONSOLE;
uma (ou poucas) abertas por vez; `ABA_PARA_PAINEL` mapeia para
painéis/abas existentes (`editor`, `agent`, `raciocinio`, `plano`,
`console`).

## Console / Status

`ConsoleModelo` com INFO/SUCCESS/WARNING/ERROR (+AGENT/BUILD/
PREVIEW); mensagens truncadas, sem traceback (`erro_amigavel`).
`StatusBar` + `montar_status()`: `P | 3 entities | 2 changes |
main.elixx | Unsaved | Agent ready`.

## Agent (MOCK/determinístico)

Nada muda na inteligência. A entidade selecionada alimenta
`PainelAgent.contexto/consultar/planejar/propor`; Tools F36
consultam dados; F31→F33→F32 preparam a alteração; nada aplica sem
aprovação. `ToolTrace.explicar()` compacto; Reasoning mantém
TASK→CONTEXT→TOOLS→OPERATIONS→PLAN→CHANGES→PREVIEW.

## Command Palette / Atalhos

F39 tem lista própria (`COMANDOS_F39`, 13 comandos; `COMANDOS_PALETTE`
F37 intacto com 30). Atalhos contextuais `ATALHOS_F39`
(V/G/S/R/F, Ctrl+Shift+F, Esc) **não** substituem o mapa global:
`conflitos_f39()` documenta que `F` global segue `enquadrar` e `Esc`
global segue `cancelar`. Novo global: `Ctrl+Shift+F` → `foco_atual`.

## Segurança

Scene/Inspector/Agent nunca executam código: só dados. Validação de
finitude (NaN/Infinity), textos curtos sem controle, travessia e
caminho absoluto recusados pelo `Workspace`, ChangeSet validado no
parser antes de aplicar.

## Performance

SceneTree sobre 10k entidades, 1k arquivos (entidades `arquivo`),
500 partes, 1k operações — sem O(n²) (relações via índice; sem
rebuild desnecessário).

## Limitações

- Escalar/Girar/Ajustar: modos preparados, sem escrita geométrica.
- BBox: só com dados reais do nó/modelo.
- Sem 3D, física, IK, LLM, RAG, rede, plugins.
