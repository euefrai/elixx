# RELATORIO — ELiXX FASE 08 (aplicações completas)

## STATUS

Concluída: aplicação real em ELiXX (tema, telas, form, tabela, modal,
abas, dados, gráfico, CRUD) sem reescrita e sem sistemas paralelos.

## BASELINE ANTES

199 passed, 0 failed (confirmado por execução antes de alterar).

## BASELINE DEPOIS

224 passed, 0 failed (+25, determinísticos).

## COMPONENTES

`componente Nome { propriedade x [: padrao] corpo {..} }` + uso
`Nome inst { ... }` + slot `conteudo`. Expansão entre parse e
semântica (substitução, nomes `inst__x`, eventos na 1ª raiz, sem
recursão). Runtime só vê componentes reais.

## PROPRIEDADES

`tema:`, `inicial:`, `ativa:` (número), `obrigatorio:`,
`validar:`, `min/max_caracteres`, `min/max_valor`, `descricao:`,
`destino:`, `colunas:` (número ou textos), `titulo:` em componentes.

## ESTADO LOCAL

NÃO implementado (decisão): só global. Nomes de slot são públicos.
Documentado para Fase 09.

## TEMAS

Blocos `tema` (cores/tamanhos/espacos); `cor/fundo: tema.x`,
`fonte: tema.x`; herança componente→janela→primeiro; `usar_tema`
re-resolve + refresca widgets sem reconstruir; claro/escuro no exemplo.

## TEMA CLARO/ESCURO

Suporte total + troca ao vivo validada em janela (`#1a1d29` ↔
`#ffffff` no widget).

## FORMULÁRIOS

Tipo `formulario`; regras por campo; `validar()` escreve
`estado.<f>_valido/_erros`; mensagens via bindings existentes.

## VALIDAÇÃO

`validacao.py` puro: obrigatório, email, número, mínimos/máximos.
Mensagens PT. Cobertura total de ramos.

## HTTP + FORMULÁRIOS

`enviar("form", "fonte")` valida → corpo do estado → POST async →
`estado.<form>_resposta`. Reusa Fase 06 (sem segundo cliente).

## NAVEGAÇÃO

`Navegador`: ir/voltar/inicio com pilha; telas top-level (ou raiz
implícita); `inicial:`; eventos criar/mostrar/esconder; parâmetros
via estado (documentado, sem sintaxe nova).

## TELAS

Render: frames em tela cheia (janela) ou raiz implícita. Visibilidade
no Objeto (tick sincroniza). Headless testável.

## MODAIS

Toplevel real com grab; nasce escondido; `abrir`/`fechar` estendidos;
X dispara `fechar`. Validado abrir→fechar em janela.

## ABAS

Botões + conteúdo alternado; `ativa:` inicial; `ligado_a` espelha no
estado (ida e volta); sem reconstrução.

## MENUS

`menu` enfileira botões filhos (medidos de verdade). Suspenso adiado
(seleção cobre; documentado).

## LISTAS

`ligado_a` = índice selecionado (lê/escreve); dicts formatados;
evento `mudanca`. Template `item{}` adiado (documentado).

## TABELAS

`colunas: "a" "b"` + `origem:` lista de dicts → ttk.Treeview reativa
(só linhas mudadas). Sem ordenação/paginação (documentado).

## RESPONSIVIDADE

% + containers + recálculo no resize (Fases 04, testado). Sem
breakpoints-CSS (documentado como modelo próprio futuro).

## CICLO DE VIDA

`criar` (uma vez, antes de aparecer), `mostrar`/`esconder` em
navegação/modais, `mudanca` em campos. `destruir` adiado.

## EVENTOS

Mesmo dispatcher + 4 nomes (`EVENTOS_SUPORTADOS`). Sem paralelo.

## FOCO/TECLADO

`focar("campo")`; Enter/Escape/Tab globais adiados (documentado).

## ACESSIBILIDADE

`descricao:` → aria no HTML; limitação Tk documentada.

## ANIMAÇÃO

Tudo existente reutilizado (alvos expandidos reescritos; sem motor
novo). Transições de modal/abas via visibilidade (documentado).

## HTML

Tabela, abas (details), modal, menu, form, aria, CSS vars do tema.
Gráficos/imagem dinâmica: placeholder honesto.

## TESTES

25 novos (test_aplicacao.py): temas (5), componentes (5), telas/nav
(3), ciclo (1), validação (3), abas/menu/tabela/modal/foco (5),
literais/HTML/seleção (3). Regressão: 199 intactos.

## REGRESSÃO

199 → 224, zero falhas. Migração única: `painel menu` → `painel
lateral` (nome virou tipo; documentada). Bugs achados: `fonte`
colidindo (→`destino`), slot sem prefixo (público, documentado),
"corpo vazio" mascarando recursão, `_pausar` duplicado, `grade`/`criar`/
`nao` como nomes (erro claro, exemplos renomeados).

## TESTES VISUAIS

Sondas reais: 2 cartões isolados + clique; tema troca widget de
verdade; pilha [config,perfil] com voltar certo; modal/abas/tabela
(3 linhas)/navegação; form inválido (2 erros) → válido; CRUD
GET→tabela, POST→201 na tela. M10 no checklist (visual do usuário).

## EXEMPLOS

`componentes`, `temas`, `formulario`, `navegacao`,
`aplicacao-completa` (tema+telas+form+tabela+modal+abas+dados+gráfico),
`crud` (demo local). 25/25 `.elixx` válidos (compat total).

## DOCUMENTAÇÃO

`componentes.md` (mesclado com catálogo), `temas.md`,
`formularios.md`, `navegacao.md`, `aplicacoes.md` + sintaxe (Fase 08),
manuais (M10), roadmap, README.

## DEPENDÊNCIAS

Zero novas (stdlib + Tk/ttk). Pillow segue opcional.

## LIMITAÇÕES

Sem estado local/componente; sem wrapper `aplicação`; sem template
`item{}`; sem ordenação/paginação; sem breakpoints; sem destruir;
sem atalhos globais; sem `botão.icone`; vídeo como na Fase 07.
Tudo documentado com motivo.

## PRÓXIMA FASE

FASE 09 — empacotamento/debugger/estado local (a definir). Parada
aqui: Fase 09 NÃO iniciada.
