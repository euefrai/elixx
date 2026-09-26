# RELATÓRIO — ELiXX FASE 04 (layout e componentes)

## STATUS

Concluída: implementada, testada (120 passed), documentada,
exemplificada, validada em janela real. Fase 03 intacta (109 → 120).

## IMPLEMENTADO

- Contêineres `linha`, `coluna`, `grade` (`colunas: N`), `pilha`:
  arranjam filhos sem `posição` (válvula: posição explícita vence).
- Props: `espacamento`, `margem`, `preenchimento`,
  `alinhamento` (esquerda/centro/direita, topo/centro/base),
  `largura`/`altura` (refinam eixos do `tamanho`), `minimo`/`maximo`
  (ambos os eixos, documentado), `colunas`, `opcoes` (1+ textos).
- Motor em `visual/cena.py`: `aplicar_layout` (recursivo, puro),
  `resolver_relativos` (%/vw/vh), `recalcular` (resize).
- Tk: medida pós-montagem de autos em layouts, recálculo com debounce
  no `<Configure>` (sem loop: só reage a mudança real).
- Componentes: `entrada`, `checkbox`, `selecao` (ttk, stdlib),
  `separador`, `indicador` (bool via `origem` → verde/vermelho).
  Interação nativa funciona; leitura programática é Fase 05.

## ARQUITETURA

Layout calculado na Cena (funções puras, testadas sem Tk); renderer só
mede e reposiciona. Parser continua sem detalhe gráfico.

## NOVOS ARQUIVOS

`exemplos/layout.elixx`, `testes/test_layout.py` (11 testes),
`docs/layout.md`, `docs/componentes.md`, `RELATORIO-FASE-04.md`.

## ARQUIVOS ALTERADOS

`lexer.py`, `parser.py` (tipos), `ast.py` (rótulos), `semantica.py`
(props `textos`/`alinhamento`), `cena.py` (layout + `opcoes`),
`reativo.py` (indicador), `tk.py` (5 widgets + remedir + resize),
sintaxe/manuais/roadmap.

## NOVOS RECURSOS / EXEMPLOS

`layout.elixx`: coluna + linha + grade + formulário + indicador vivo.
Sonda real: botões (0/130/260), grade 2 colunas, empilhamento de autos,
resize 760→900 recalculado — OK. Colisão `entrada` × nome de animação
da Fase 03 resolvida renomeando o exemplo/testes (regra documentada:
tipos continuam reservados).

## TESTES

109 → **120 passed, 0 failed**. Layout puro (coluna/linha/grade/pilha,
margem, alinhamentos, explícita-vence, auto-tamanho, relativos,
mínimo/máximo), sintaxe e semântica dos novos tipos/props.

## LIMITAÇÕES

Sem ancorar/preencher/centralização plena; leitura de formulário na
Fase 05; dashboard segue absoluto (estabilidade — migra quando o
layout amadurecer).

## PRÓXIMA FASE

FASE 05 — estado e reatividade (parcialmente preparada: `origem`,
`Vinculador`, refs de widgets já existem).
