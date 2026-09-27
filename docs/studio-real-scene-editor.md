# ELiXX Studio — Real Scene Canvas (F40)

Cena visual real sobre dados reais. Princípio: Código → Parser →
AST → F27 → Scene/Character/Geometry → Canvas. Sem origem real,
placeholder honesto — nunca posição, tamanho, imagem, personagem,
asset ou animação inventados.

## Scene Canvas (`elixx/studio/scene_canvas.py`)

`cena_de_texto(texto, entrada)`: pipeline oficial (diagnosticar,
parse, expandir, validar, Executor, ConstrutorCena,
vincular_personagens) → `{cena, personagens, diagnosticos}`. O
mesmo que o preview executa; sem segundo renderer/parser.

`SceneCanvas.montar(cena, personagens, modelo, workspace)`:

- **Janelas**: medidas reais (`x/y/largura/altura/camada`).
- **Personagens**: via `vincular_personagens` (F12); sem asset,
  placeholder `PERSONAGEM Juh · sem asset` (sem imagem falsa).
- **Partes**: via `Character` (F12/F23/F24) + `transform_global`
  real; id `parte:Juh.corpo`, `parent_id` no personagem.
- **Textos/componentes/grupos/objetos/imagens**: do `NoVisual`
  real; `ajuste` (`conter/cobrir/original`) preservado.
- **Ordem**: `ordem_visual` F10 (`camada`, `_seq`); nunca
  alfabética.
- **Tamanhos ausentes**: `TAMANHOS_PADRAO` com flag
  `tamanho_derivado` (dado intacto, só apresentação).

## Seleção

Global (`Inspetor` + `selecionado`/`node_selected`): Juh →
`personagem`, cabeça/braço → `parte`, resto → `no`. Tree ↔ Canvas
↔ Inspector ↔ Code pela mesma seleção. `objeto_sob_ponto`
(hit-test do topo). Multi-seleção: `capacidade_multi()` =
não suportado (single oficial, sem segundo sistema).

## Bounding Box / Handles

`bbox_global` compõe a cadeia de pais com `combinar` (F10).
`handles_de`: mover disponível (x/y via proposta); escalar/girar
preparados com motivo. `interpretar_gesto`: botão meio/direito =
pan; esquerdo sobre objeto em Mover = drag; resto = selecionar.

## Visual → Code / Code → Visual

`arrastar_para` → `propor_transformacao` F39 (`posicao`),
ChangeSet proposto, arquivo intacto. `recarregar(texto)`:
diff `{adicionados, removidos, alterados}`; 1 mudança =
`rebuild_parcial` (sem rebuild total). `aplicar_edicao`
(live preview): escreve edição salva → `atualizar_arquivo`
F27 → recarrega canvas.

## Assets

`estado_asset`: `sem_asset | remoto | encontrado | ausente |
invalido | nao_verificado` via `GerenciadorAssets.validar` +
`detectar_tipo` (F07). Remoto nunca baixa. `carregar_imagem`:
PNG/GIF via Tk, JPEG via Pillow, SVG = placeholder; sem display
= `None` (placeholder assume, sem exceção).

## Viewport

`enquadrar` (fit real + centraliza), `centralizar_selecao`,
`zoom_para_selecao`, `ticks_grade` (zoom/pan), `ticks_regua`
(x/y com coordenadas), fundo dark do Design System
(checkerboard reservado a transparência real).

## Debug

`debug` off por padrão; `info_debug` = id/tipo/posição/tamanho/
parent; overlay desenhado só com debug on.

## Inspector

`ficha_objeto`: IDENTIDADE (nome/tipo/arquivo/linha),
TRANSFORM (x/y/width/height/rotation/scale só reais),
RELATIONS (de/para F27), ASSET (status), CHARACTER
(parts/poses/expressions/direção). Seções vazias omitidas.

## Animação / Motion

`AnimationPreview` sobre `MotorAnimacoes` + `Timeline`
(play/pause/stop/tick, sem scheduler novo). `MotionPreview`
sobre `Character`: poses/expressões reais; prévia aplica pose
em memória (arquivos intactos; ida ao código via proposta).

## Agent

`contexto_cena`: `PainelAgent.contexto` + objetos visíveis
(selecionado, sem visão por imagem). Tools/reasoning/plan/
changes F34–F36 inalterados.

## Layouts / Compacto / Palette / Teclado

SCENE = Project 20% + Canvas 57% + Inspector 23%
(`proporcoes_scene`, `aplicar_layout_scene`; frações, sem px
rígido). Compacto via `Layout.definir_compacto` com preview
garantido. Palette F40: 10 comandos (F37/F39 intactas).
Atalhos F40 (Home/F/+/-/0/G/D) contextuais; `F` global segue
`enquadrar` (`conflitos_f40`).

## Tk

`desenhar(canvas_tk, canvas)`: fundo dark, grade, objetos por
camada, placeholders, textos reais, imagens reais, outline
accent + handles na seleção, overlay debug. Aceita stub
duck-typed (testes). `abrir_janela_cena(ws, texto)`: janela
com Fit/Grid/+ e clique→seleção. O preview do Studio monta o
canvas real de forma defensiva (`try/except`).

## Segurança / Performance

Sem eval/exec/importlib/`__import__`/pickle/subprocess/
os.system/shell. Canvas/Inspector/Agent nunca executam código
(arbitrário; a cena usa o pipeline oficial como o preview).
Travessia/absoluto recusados; NaN/Infinity/payload gigante
rejeitados. 100→10k objetos, 1k arquivos, 500 partes, 1k ops;
rebuild parcial em 1 mudança; desenho sem duplicação.

## Limitações

Escalar/girar sem escrita; multi-seleção não suportada;
JPEG exige Pillow+display; SVG sempre placeholder; motion
gestures via API do Character quando definidos.
