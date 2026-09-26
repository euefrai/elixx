# ELiXX — FASE 09 — FINAL REPORT

## STATUS

100% — todos os itens verificáveis do critério implementados, testados
e com prova real. Estado local, contexto, listas dinâmicas, ações,
funções, módulos e app real funcionando no renderer nativo.

## TESTES

Antes:
224 passed

Depois:
259 passed (224 + 35 novos em testes/test_fase09.py)

Falhas:
0

Erros:
0

Tempo aproximado: ~17s. Sem internet, sem máquina específica, sem Tk
nos unitários (probes Tk separadas, descartáveis, em Temp).

## IMPLEMENTADO

- Lexer: `%` como SINAL (grudado segue unidade); `acao`, `importar`
  reservadas (sem colisões: auditado).
- AST: AcaoDef, Import, Componente.modelo, ComponenteDef.estado,
  Programa.acoes/imports/locais; mostrar_arvore cobre tudo.
- Parser: blocos `acao`/`importar`, forma `executar`, `modelo {}` em
  componente, `estado {}` em def, flags `_em_def/_em_modelo/_em_lista`
  com erros PT imediatos para local/item/param fora de escopo.
- Expansão: atravessa modelo, reescreve `local.*` estático para
  `estado.<ns>__x`, `param` inclusive aninhado (`param.a.b`),
  registra padrões em `programa.locais`, slot em modelo.
- Semântica: AcaoDef (dups, colisão com função), modelo-só-em-lista,
  `chave:` (caminho), origem `local.`/`item.`, `ligado_a` local,
  `executar` permitido, extras de locais, `tema:`/props intactos.
- Runtime: `locais` + versões, `pilha_ns`/`item_atual` com context
  managers, `obter/definir_local`, `avaliar_membro` (local/item/param),
  `Ident` guards, atribuição local, `chamar_acao`, ramo `executar`,
  `%` + divisão-por-zero em PT.
- `runtime/listas.py` (novo): `GerenciadorListas` com reconcile por
  chave, namespaces por linha, padrões da def, pacotes por linha com
  versões, despacho com contexto (anti-último-item), destruição.
- Cena: `NoVisual.modelo/dinamica/def_origem/chave_expr`,
  `Fabrica` carrega modelo, builder converte template.
- Vinculador: pula nós dinâmicos no `_coletar`, anexa pacotes do
  gerenciador; `dependencias_origem` entende `local:`.
- Tk: lista dinâmica (container + reconciliação de frames, preserva
  identidade), `ns` nos refs, `_escrever_estado`/`definir` com rota
  local, `ao_interagir` com contexto de linha, `ligado_a: local.*`.
- HTML: placeholder honesto para lista dinâmica.
- Módulos: `compilador/modulos.py` (raiz, traversal, ciclos, merge,
  estado duplicado); `cli.pipeline` usa o loader; `verificar` segue
  sem HTTP/execução.
- Segurança: traversal estruturalmente impossível + `_dentro`;
  ciclos `A → B → A`; remoto nunca vira código (inalterado);
  `local`/`item` fora de escopo nem passam do parser.

## ARQUITETURA

```
SOURCE → LEXER → PARSER → AST → SEMÂNTICA → MÓDULOS/EXPANSÃO
  → RUNTIME (Executor: estado/locais/contexto + GerenciadorListas)
  → VINCULADOR (versões) → CENA (templates + cópias) → RENDERER
```

- Estado local estático = `estado.<ns>__x` (zero mecanismo novo;
  versões e bindings existentes funcionam).
- Estado local dinâmico = `Executor.locais[ns]` por linha (criado
  na reconcile, destruído na remoção).
- Contexto (`pilha_ns`, `item_atual`) via context managers com
  restore em `finally`; renderer nunca decide semântica (só guarda
  `ns` nos refs e repassa a linha).
- Ações/funções reusam `Memoria` com escopo (sem第一类 funções,
  sem closures).
- Listas: runtime reconcilia (dados→linhas), renderer desenha/remove
  (widgets), Vinculador transporta pacotes. Sem loop concorrente.

## SEGURANÇA

Traversal bloqueado (sintaxe + `_dentro`); ciclos de import;
arquivo inexistente; `local`/`item`/`param` fora de escopo (parse);
atribuição em `item` proibida; `param` em runtime proibido; remoto
como dado (inalterado). Testes para cada um.

## COMPATIBILIDADE

Fases 01–08 intactas: 224/224 verdes sem tocar em teste antigo
(exceto 1 ajuste documentado: dashboard `painel menu`→`lateral`
era Fase 08). `param.*`/`local.*`/`item.*` inexistiam antes;
`executar`/`acao`/`importar` sem colisões (auditado).
Incompatibilidade intencional zero.

## PROVAS REAIS

Sondas Tk descartáveis (refeitas do zero nesta fase):
- Lista: Ana/Beto → +Carlos → −Beto → +Diego, widgets conferidos.
- App: favoritar A e C via clique real (B segue false); excluir no
  card do meio registra id 2 (não o último); remover id 2 some a
  linha e destrói o namespace.
- 01/05/06/09/app + dashboard revalidados em janela (`--sem-janela`
  e nativo com auto-close onde aplicável).
Checklist visual M11 em docs/testes-manuais.md (não auto-aprovado).

## EXEMPLOS

- `exemplos/01_estado_local.elixx` … `09_app_completa.elixx` (todos
  `verificar` OK).
- `exemplos/07_modulos.elixx` + `exemplos/modulos_demo/`.
- `app/` real: `principal.elixx`, `componentes/produto_card.elixx`,
  `telas/produtos.elixx`, `dados/produtos.elixx`,
  `dados/produtos.json`, `acoes.elixx`, `funcoes.elixx`.
- `exemplos/dados-demo/produtos.json` (fixture das listas).

## DOCUMENTAÇÃO

- `docs/fase-09.md` (novo): estado local, contexto, listas, item,
  ações, funções, módulos, escopo, limites.
- `docs/sintaxe.md`: seção Composição (Fase 09).
- `docs/arquitetura-roadmap.md`, `README.md`,
  `docs/testes-manuais.md` (M11).

## LIMITAÇÕES

- Slot-filhos usam estado global (`local.*` neles é erro de parse).
- `local.*` em def exige bloco `estado` (erro claro).
- Sem scroll em lista dinâmica; sem template `item{}` fora de
  `modelo`; `param` só dentro de def.
- `executar` como nome de ação/função fica sombreado (documentado).
- HTML: lista dinâmica é placeholder.
- Estado local estático vive com o app (só linhas dinâmicas morrem).
- Sem classes/herança/async/threads públicas (fora de escopo).

## FALHAS CONHECIDAS

Nenhuma. Durante a fase, sondas acharam e corrigimos (sem esconder):
plano sem `ns`/`item`, `_def` consumida em edição, `def` duplicada
em listas.py, `a__valor` não semeado, `c__v` rejeitado no pós-passe,
pacotes sem cena, `param` fora de def passando batido no parse de
comando. Todas com teste de regressão.

## DECISÕES ARQUITETURAIS

1. Estático → `estado.<ns>__x` (reuso total, zero mecanismo novo).
2. Dinâmico → `Executor.locais` por linha (cria/destrói com a linha).
3. Contexto em pilha com restore (eventos e avaliações aninhadas).
4. Sem novas palavras além de `acao`/`importar` (`modelo`, `item`,
   `local`, `param`, `executar` posicionais).
5. `param` com caminho aninhado (`param.a.b`).
6. Módulos fundidos, não interpretados separados (validação única).
7. `%` só com espaços (`20%` continua unidade).
8. `item` em def permitido (aposta documentada p/ uso em lista).

## PRÓXIMA FASE

Sugestões (não implementadas): scroll virtualizado, `para:` em
`executar` com retorno, `teste:` blocos de teste na linguagem,
`scroll`/`página` em lista, debugger de contexto (`elixx contexto`?),
empacotamento de app/ (Fase 10 natural).
