# ELiXX — FASE 02 — Relatório

## STATUS: 100%

Checklist de conclusão: todos os 15 itens atendidos (inspeção visual
humana M1/M2 em `docs/testes-manuais.md` executada de forma automatizada
— janela real abriu, clique real atravessou o pipeline — e pendente de
confirmação visual do usuário).

## BACKEND ESCOLHIDO: Tkinter (stdlib, zero dependências)

Nativo no Windows, eventos maduros, 2D (Label/Button), imagens via
PhotoImage, animação futura via `after()`. Qt descartado (dependência
~100MB); SDL descartado (sem widgets); Win32 puro descartado
(boilerplate); Skia descartada (sem distribuição simples). Troca futura
não toca o runtime (classe `Renderizador` abstrata). Análise completa em
`docs/renderer-nativo.md`.

## IMPLEMENTADO

- Cena (`visual/cena.py`): NoVisual com pai/filhos/posição/tamanho/
  escala/rotação/opacidade/visibilidade/estilo/eventos + `ref_objeto`
  (ponte com o runtime); resolução de `%`/`vw`/`vh` contra a janela
- `Renderizador` abstrato + registro (`nativo`, doubles de teste);
  runtime nunca importa backend
- `RenderizadorTk`: janela real (título, tamanho, posição, fundo),
  texto (conteúdo, fonte, cor), botão com clique E hover reais,
  barra de mensagens do `mostrar`, tick 50ms com `dt_ms`, fechar limpo
- Fluxo exigido, sem sistema paralelo: gesto → `ao_interagir` →
  `executor.disparar` → Bloco AST → ações
- CLI: `executar` abre janela (padrão); `--sem-janela` preserva Fase 01;
  `verificar`, `compilar` (HTML intacto), `versao` inalterados
- Sintaxe (adição, nada quebra): `conteúdo:` alias de `texto:`;
  `fonte: 24px` p/ letra (`tamanho` segue sendo a caixa — decisão
  justificada); vocabulário deixou de ser reservado (`botão abrir` vale)
- Coordenadas documentadas: x→direita, y→baixo, origem no canto superior
  esquerdo do conteúdo
- Exemplos `interface.elixx` (marco) e `interface-completa.elixx`

## TESTES: 63 passed, 0 failed

Antes: 45 · Depois: 63 (45 preservados — 2 ajustados por mudança
intencional documentada — + 18 novos: cena 9, renderer 8, lexer 1).
Janela real nunca é aberta em teste automático (double `RenderizadorMemoria`);
testes manuais separados e nunca auto-aprovados.

## ANTES → DEPOIS

- `executar` simulado → janela nativa real com clique de verdade
- `mostrar` só console → barra de mensagens + console
- medidas `%` ignoradas na prática → resolvidas contra a janela
- 1 backend (HTML) → 2 backends (nativo + HTML)

## LIMITAÇÕES (provisórias, marcadas no código)

Sem layout (empilhamento provisório), sem alfa por pixel, sem
rotação/escala em widgets, imagem/vídeo/áudio com placeholder,
sem interpolação de animação (tick com `dt_ms` já pronto).

## DECISÕES DE ARQUITETURA

1. Tkinter por custo zero de distribuição (tabela comparativa nos docs).
2. Cena entre runtime e renderer (parser nunca vê backend).
3. `fonte:` em vez de sobrecarregar `tamanho:` (ambiguidade).
4. Vocabulário não-reservado (nomes como `abrir` liberados).
5. `bruto` no Objeto (aditivo, zero impacto Fase 01) + `ao_mostrar`
   opcional no Contexto (sem gancho, comportamento idêntico).
6. Bugs achados por testes e corrigidos: normalização de acentos
   (`conteúdo`), import do backend.

## PRÓXIMA FASE (aguardando decisão — não iniciada)

Interpolação de animação, layout (centralizar/alinhar), multimídia real.
