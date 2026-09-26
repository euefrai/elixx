# RELATORIO — ELiXX FASE 05 (estado e reatividade)

## STATUS

Concluída: todos os 9 itens do critério (§27) atendidos. Nenhuma
regressão; nada do sistema anterior foi recriado.

## BASELINE ANTES

120 passed, 0 failed (confirmado por execução antes de alterar).

## BASELINE DEPOIS

147 passed, 0 failed (+27, todos determinísticos, sem janela/máquina).

## ARQUITETURA

```text
fonte de dados ─┐
                ├→ Vinculador (versões + último valor) → Cena → renderer
estado (versões)┘
```

Reaproveitado sem recriar: `origem`, `Vinculador`, `formato`,
`definir_valor`, `_paineis`, `Memoria`, `FonteDados`. Novo: bloco
`estado`, classe `Estado`, `Atribuicao`, `ligado_a`, expressões em
origem, primeira carga síncrona. Renderer sem lógica de estado (só
`definir_valor` + escrita guardada); Tk não decide o que mudou.

## ESTADO

Bloco `estado { }` (único, global); classe com versão por chave;
inicial avaliado antes de objetos/aparecer; leitura em qualquer
expressão; escrita `= += -= *= /=` (+ concatena texto); `incrementar`;
erros PT com sugestão; chave inexistente é erro (typo-safe).

## BINDINGS

`origem:` unidirecional (dados/estado/expressão/literal);
`ligado_a:` bidirecional (só estado; `dados` rejeitado). Push pula
foco em edição; escrita só quando diferente.

## REATIVIDADE

Dependências extraídas (`dependencias_origem`); versões evitam
re-resolver; igualdade evita reescrever; sem reconstrução;
`estatisticas` comprovam (ex. 8 pulados_versao); `atualizacoes` conta
ciclos quando declarada.

## DEPENDÊNCIAS

`estado.qtd * estado.preco` reavalia se qualquer parte mudar;
múltiplos consumidores da mesma chave atualizam juntos; outros pulam.

## BIDIRECIONAL

entrada (FocusOut/Return), checkbox (trace), selecao (evento).
Convergência testada com stubs (1 escrita por mudança, sem loop).

## COMPONENTES

texto, barra, indicador, checkbox, entrada, selecao, lista, grafico.
Leitura programática de formulário: pronta (estado recebe ao interagir).

## ARQUIVOS CRIADOS

`elixx/runtime/estado.py`, `exemplos/estado.elixx`,
`exemplos/reatividade.elixx`, `testes/test_estado.py` (27 testes),
`docs/estado.md`, `docs/reatividade.md`, `RELATORIO-FASE-05.md`.

## ARQUIVOS ALTERADOS

`ast.py` (EstadoDef, Atribuicao), `lexer.py` (`estado`, += -= *= /=),
`parser.py` (bloco, atribuição, membros em PALAVRA), `semantica.py`
(origem geral, `ligado_a`, pós-passe de chaves), `nucleo.py` (estado,
atribuição, leitura), `acoes.py` (`incrementar`, `ctx.estado`),
`cena.py` (`origem_expr`, `ligado_a`), `reativo.py` (Vinculador v2),
`tk.py` (definir entrada/checkbox/selecao, escrita two-way),
`nativo.py` (fiação + primeira carga), `dashboard.elixx` (estado,
ciclos, cliques, modo), sintaxe/manuais/roadmap.

## TESTES

147 passed. Estado (6), sintaxe (4), atribuição (6), origem/deps (4),
mínimo (2), ligado_a (2), two-way stubs (2), rajada (1), incrementar
(1), CLI+compat total (2). Auditoria achou e corrigiu: PALAVRA sem
membros, `atualizar_agora` × pacotes, pintura inicial vazia.

## TESTES VISUAIS

Sonda real `estado.elixx` (janela, 3s): iniciais 0/Visitante/50;
cliques → 2/55; digitação real → eco; toggle real → bolinha vermelha;
stats com pulados — OK. `reatividade.elixx`: 10/10/25 iniciais,
15/15/35 após +5, seletivo (12 pulados) — OK. Dashboard nativo com
estado — OK, saída 0. M7 manual pendente do usuário (checklist).

## EXEMPLOS

`estado.elixx` (contador, nome two-way, ativo, derivado),
`reatividade.elixx` (multi-consumo, seletividade), dashboard com
ciclos/cliques/modo. Todos os 11 `.elixx` verificados (teste automático).

## LIMITAÇÕES

Sem HTTP/REST (Fase 06); `ligado_a` só entrada/checkbox/selecao;
posição/tamanho/opacidade seguem no motor de animação; espelho
automático dados→estado não existe (ponte documentada p/ Fase 06:
fontes implementam a interface que o estado consome).

## PRÓXIMA FASE

FASE 06 — dados e APIs. Parado aqui, sem avançar (regra §29).
