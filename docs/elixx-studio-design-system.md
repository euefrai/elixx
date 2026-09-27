# ELiXX Studio Design System (F36B)

Origem honesta: os projetos-irmãos locais **não possuem tokens
extraíveis** (Fajulto: icon theme + gramática VSCode, sem cores; sem
pastas Juh/Kulia/principal_completo). Esta paleta é **derivada** das
convenções dark-editor com identidade própria ELiXX (acento violeta)
— escolha F36 documentada, não medição. Nada copiado (só stdlib/Tk).

## Cores (`ELIXX_COLORS`)

background `#16161d` · surface `#1e1e26` · surface_alt `#252532` ·
panel `#1b1b22` · panel_hover `#2a2a38` · border `#343442` ·
text `#e8e8f0` · text_muted `#9a9ab0` · accent `#7c6cf0` ·
accent_hover `#9388f5` · success `#58c98a` · warning `#e0b45c` ·
error `#e06c6c` · info `#6cb8e0` · selection `#37335c`.

## Tipografia (`ELIXX_FONTS`)

titulo 13 bold · section 10 bold · label/body 9 · code Consolas 9 ·
caption 8 (família Segoe UI; fallback nativo, sem downloads).

## Espaço/densidade (`ELIXX_SPACING`, `ELIXX_DENSITY`)

xs 2 · sm 4 · md 8 · lg 12 · xl 16; compacto reduz padx/pady.
Raios simulados (`ELIXX_RADIUS`: 3/6/10 — Tk sem radius nativo).
Bordas finas (`ELIXX_BORDERS`: 1/2/0; separadores sutis, sem caixas
pesadas). Métricas (`ELIXX_METRICS`): toolbar 32, lateral 220,
editor mín 120, console 110.

## Componentes

Botões: normal/hover/pressed/disabled + Accent (executar/aprovar) e
Danger (cancelar). Inputs com fundo/borda/focus/erro. Abas com mesmo
design (Notebook estilizado). Scrollbars nativas via tema clam.
Cards: header/content com padding e hover. Ícones: símbolos e Canvas
(sem emoji, sem biblioteca). Estados: normal/hover/selected/focused/
disabled/error/success/warning (nunca só cor: texto e posição
reforçam). Animações: só hover/expansão/seleção (sem bloqueio).

## Layout e responsividade

Toolbar agrupada com tooltips via statusbar; painéis redimensionáveis
(PanedWindow); compacto alternável; 800x500–3840x2160 testados, com
prioridade Agent/Preview/Inspector em telas menores. Persistência
reusa `.elixx/layout.json` (tema/layout/aba; sem segredos).

## Acessibilidade

Foco por teclado (Ctrl+P/Palette/Enter/Esc/F), seleção visível,
contraste texto/fundo ≥ legível, labels em tudo, mensagens sem
traceback. `validar_tokens()` garante hex/fontes/espaços sem display;
`aplicar_tema()` é idempotente e opcional.
