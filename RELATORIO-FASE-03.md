# RELATÓRIO — ELiXX FASE 03 (animação real)

## STATUS

Concluída: implementada, testada (109 passed), documentada,
exemplificada, validada em janela real. Baseline preservado (85 → 109).

## IMPLEMENTADO

- `animacao/easing.py`: 15 movimentos com matemática real e pura
  (linear, suave, acelerar, desacelerar, rapido, lento, mola, elastico,
  quicar, sacudir, deslizar, expandir, encolher, aparecer, desaparecer).
- `animacao/motor.py`: interpolação na Cena (posição, tamanho, escala,
  rotação, opacidade) + duração, atraso, sequência (`depois:`),
  paralelo (automáticas juntas), repetição (N/infinito), pausa,
  retomada, cancelamento, callback (`quando terminar`), snap final.
- Sintaxe `animação nome { }` (AST `AnimacaoDef`, seta `→`/`->`, destino
  único ou `de → para`); semântica valida alvo, movimento, unidades px,
  `início`, `depois`, nomes únicos — tudo em português com sugestão.
- Ações `iniciar/pausar/continuar/cancelar` (via `ctx.motor`, opcional).
- Tk aplica posição/tamanho/alfa da janela a cada tick, só quando muda
  (sem churn); opacidade/escala/rotação de widgets documentadas como
  limitação do backend (valores reais na Cena).

## ARQUITETURA

```text
animação → motor → propriedade abstrata → Cena → renderer
```

Motor sem Tk e sem tempo real (dt injetado); renderer sem regra de
negócio; parser sem detalhe gráfico. `MOVIMENTOS == EASINGS` garantido
por assert (novo movimento = 1 função pura).

## NOVOS ARQUIVOS

`elixx/animacao/easing.py`, `elixx/animacao/motor.py`,
`exemplos/animacao.elixx`, `testes/test_animacao.py` (24 testes),
`RELATORIO-FASE-03.md`. Docs: `docs/animacao.md` (reescrito).

## ARQUIVOS ALTERADOS

`animacao/__init__.py` (15 movimentos, re-export), `ast.py`
(`AnimacaoDef`, `Janela.animacoes`), `lexer.py` (`animação`),
`parser.py` (bloco + keyframes), `semantica.py` (validação),
`acoes.py` (4 ações + `ctx.motor`), `renderizador.py` (`motor`),
`tk.py` (geometria/alfa/motor no tick), `nativo.py` (motor + auto-start),
`dashboard.elixx` (+1 animação de entrada), sintaxe/manuais/roadmap.

## NOVOS RECURSOS

Ver IMPLEMENTADO. Exemplo cobre: auto-suave, manual-quicar com
repetição, sequência, alfa real da janela, desaparecer + callbacks.

## EXEMPLOS

`exemplos/animacao.elixx` (novo, 6 animações) + dashboard ampliado.
Validação real por sonda (10s de janela): cartão 220→40, quique com
volta exata a 300, callbacks, alfa 0.41→1.0 — tudo OK. Um bug real
(manual rodando sozinha) foi achado pela sonda e corrigido com teste.

## TESTES

85 → **109 passed, 0 failed**. Easings (contrato + valores), motor
(interpolação, atraso, repetição, infinito, sequência, pausa,
cancelamento, visibilidade, erros PT), sintaxe e semântica (7 erros),
ações, AST→motor. Generalidade: posição + opacidade + tamanho + escala.

## LIMITAÇÕES

Animação em `px` (erro claro para `%`); opacidade/escala/rotação de
widgets sem efeito visual no Tk (na Cena, sim); sem ping-pong; HTML
ignora animações (prévia estática).

## PRÓXIMA FASE

FASE 04 — layout e componentes.
