# ELiXX Studio — Visual Polish (F40.5)

Fase visual/UX/composição. Nenhum sistema novo: sem LLM, parser,
modelo, renderer, seleção ou EventBus novos. Tudo reutilizado.

## Design System 3.0 (`elixx/studio/tema.py`)

`ELIXX_COLORS` legado intacto (compat). Novo:

- `ELIXX_DS3`: bg `#0D0D12/#111118`, surfaces
  `#171720/#1D1D27/#242432`, border `#30303D`, textos
  `#F3F3F7/#B8B8C5/#8E8E9E`, accent `#8B5CF6/#9B6CFF/#7446D8`,
  success/warning/danger/info. Sem magenta solto.
- `ELIXX_TYPE`: app_title/section_title/panel_title/subtitle/
  body/secondary/monospace (Segoe UI + Consolas).
- `ELIXX_SPACE`: 2,4,6,8,12,16,20,24,32.
- `ELIXX_RADIUS_V3`: small/medium/large (moderado).
- `paleta()`: DS3 com aliases (fonte única da UI).
- `contraste()` (WCAG) + `validar_ds3()` (hex, contraste ≥ 4.5,
  escala, ordem tipo, ordem raios).
- Regra de cor: 90% neutro; accent só em seleção/ação
  primária/foco/ativo; danger só parar/erro; success só
  concluído/salvo.

## App chrome / toolbar

Menubar real (só comandos existentes): Arquivo (Salvar,
Executar, Parar, Fechar), Visualizar (5 layouts, Compacto,
Foco, sair do foco), Cena (Fit, Grid, Zoom ±), Ajuda
(Palette, Atalhos). Sem menus mortos (Editar/Agent sem ação
real não ganharam menu).

Toolbar do preview em grupos (modos | Grid/Fit | zoom |
status), botões `Toolbar.TButton` com estado ativo real
(`Active.Toolbar.TButton`, fim do "Mover/Mover"), tooltips
via status bar, sem duplicar o Executar do topo.

## Project / Scene / Canvas

Project: tree F27 com ícones por tipo, seleção accent,
arquivo atual e dirty `●` (via `formatar_arvore`).

Canvas protagonista: lista esquemática fina + canvas dark
dominante; grade sutil adaptativa (`ticks_grade`); empty
states reais (sem projeto / erro / sem objetos); auto-fit no
primeiro desenho (respeita zoom/pan do usuário).

Placeholders refinados (`_desenhar_placeholder`): personagem
abstrato (círculo + linhas, sem imagem falsa), janela com
moldura dupla, imagem com `⊞` + status, componente com
rótulo do tipo. `sem asset` discreto; asset ausente/inválido
em warning (não fatal). Seleção: outline accent fino (1px)
+ label `nome · tipo`; handles só onde há operação real.

## Inspector / Agent / Bottom / Status

Inspector em seções `▼/▸` clicáveis, linhas `label valor`
alinhadas, só dados reais, empty elegante, Ver código
secundário.

Agent com cara de chat: `● Ready`, provider em caption,
chips de contexto compactos (`▣ sel · n ent`), histórico,
input + Enviar, ações Consultar/Planejar/Propor. Backend
segue MOCK/determinístico (bug real corrigido: o chat
passava `dict` como ambiente e sempre falhava; agora usa
objeto com atributos).

Bottom: abas com estado ativo (`TabActive.TButton`).
Status bar: resumo + `Sel` + zoom reais. Palette com
categorias `[Scene]/[Editor]/[Agent]/[Projeto]`. Editor com
syntax nas cores DS3 + tag `erro`. Salvar registra `✓`.

## Layouts / Compacto / Foco / Teclado

Presets intactos; SCENE 20/57/23; compacto esconde de
verdade; foco via menu/palette com Esc restaurando.
Atalhos preservados (`F`/`Esc` globais intactos).

## Segurança / Performance / Acessibilidade

Scan sem eval/exec/etc; travessia/absoluto/NaN/payload
cobertos; UI nunca executa código. 100→10k objetos, 1k ops,
500 partes, desenho sem duplicação. Contraste ≥ 4.5 nos
textos; foco/hover visíveis; sem dependência só de cor.

## Limitações

Snap no toolbar do preview não existe (controle vive na
palette F39; documentado). Micro-animações não
implementadas (sem framework). Bottom mantém as 5 abas
reais (CODE/AGENT/etc. como abas novas exigiria sistema
novo). Menus Editar/Agent/Janela omitidos (sem ação real).
