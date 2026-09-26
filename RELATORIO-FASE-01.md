# ELiXX — FASE 01 — Relatório

## STATUS: 100% (fundação completa e verificada)

## IMPLEMENTADO

- Lexer próprio (PT, medidas como NUMERO+UNIDADE, `#` e `//`, erros em PT)
- Parser próprio recursive descent + AST independente de renderer
- Tipos: Programa, Janela, Componente (botao/texto/imagem/video/audio),
  Propriedade, Evento, Bloco, Acao, Se, Repetir, Retornar, Funcao,
  TextoLit, NumeroLit, Medida, CorLit, Booleano, Ident, Chamada, Binaria
- Modelo de objetos (posição, tamanho, rotação, escala, opacidade,
  visibilidade, estilo, eventos, filhos)
- 4 eventos + 10 ações extensíveis por registro (`@acao`)
- Tipo Cor (nomes PT + hex) e unidades (px % vw vh ms s graus)
- Entidade Animacao + 11 movimentos registrados (interp. na Fase 02)
- Semântica com "você quis dizer" + avisos
- CLI: executar (+--clicar, --mostrar-arvore), verificar, compilar (HTML), versao
- Ponte Fajulto experimental desativada (ELiXX 100% independente)
- 6 docs em PT + 4 exemplos + README

## ARQUITETURA

Python, zero dependências. Parser não conhece eventos/ações (extensão sem
quebrá-lo); semântica valida contra o que o runtime suporta; propriedades
de uma linha (sem separadores). Decisões e bugs encontrados documentados
no histórico (ex.: `texto:` vs componente `texto`, vazamento de valores
entre linhas — ambos corrigidos com testes).

## SINTAXE

Reservado o essencial em PT (janela, botão, quando, clicar...), com
aliases sem acento. Cresce por adição, sem quebrar o existente.

## TESTES: 45 passed, 0 failed

Lexer 11 · Parser 10 · AST 4 · Runtime 13 · CLI 7.

## EXEMPLOS FUNCIONAIS

- `exemplos/programa.elixx` (o da especificação — imprime "Olá, mundo!")
- `exemplos/eventos.elixx`, `cores-unidades.elixx`, `logica.elixx`
  (função dobra 21 → 42, se/senão, repetir)

## LIMITAÇÕES (conhecidas e documentadas)

- Sem janela gráfica nativa: execução simulada + prévia HTML
- `animar` aplica estado final (sem interpolação ainda)
- `repetir` sem número executa 1x com aviso; limite de 1000
- Propriedades de uma linha; integração Fajulto desativada

## PRÓXIMA FASE

Renderer nativo clicável, interpolação de animação, multimídia real,
repetição controlada, especificação formal Fajulto ↔ ELiXX.
