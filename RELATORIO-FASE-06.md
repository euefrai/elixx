# RELATORIO — ELiXX FASE 06 (dados, HTTP, REST)

## STATUS

Concluída: todos os itens do critério sólidos implementados; limites
honestos documentados (sem suporte fingido). Sem reescrita.

## BASELINE ANTES

147 passed, 0 failed (confirmado por execução antes de alterar).

## BASELINE DEPOIS

174 passed, 0 failed (+27; servidor local, zero internet).

## ARQUITETURA

```text
HTTP/REST → Fonte → estado → Vinculador → Cena → Tk/HTML
```

Camada HTTP sem Tk/Cena/widgets; dados sem renderer; mesma abstração
`FonteDados` para sistema/remota/arquivo; nenhuma reatividade nova
(versões da Fase 05 fazem o resto).

## CLIENTE HTTP

`dados/http.py`: GET/POST/PUT/PATCH/DELETE (urllib), timeout sempre,
headers, params via urlencode, corpo JSON, só http/https. Nunca levanta
para a UI: timeout, DNS, recusada, HTTP NNN, JSON inválido, vazio.

## JSON

Tipos preservados (objeto/lista/string/número/bool/nulo); `formato:
"json"` exibe; UTF-8 com fallback; conteúdo é só dado (testado).

## GET / POST / PUT / PATCH / DELETE

Todos contra servidor local; POST com corpo avaliado do estado
(`nome: estado.nome`); 201 com echo validado.

## TIMEOUT

`tempo_limite` (padrão 10s); teste prova retorno <2.5s contra 3s de
atraso; app nunca congela (thread daemon).

## ERROS

Mapeados em PT; `estado.<nome>.erro`; app continua (validado com
servidor desligado conceitualmente via 500/timeout/DNS).

## CONCORRÊNCIA

`buscar_async` retorna na hora; guarda anti-duplicação; tick livre
(testado); renderer sem threads.

## ESTADO / REATIVIDADE

Resultado cai em `estado.<nome>` (`{valor,carregando,erro,status}`);
bindings existentes reagem (lista mostra Ana/Beto; texto mostra 201).
Leitura profunda `estado.a.b.c` liberada no avaliar e na semântica.

## DADOS LOCAIS

`dados cfg { arquivo }` + espelho com detecção de mudança (sem churn);
relativo à pasta do `.elixx`.

## ATUALIZAÇÃO PERIÓDICA

`atualizar: Ns` (mínimo 1s); um relógio no tick, sem timers extras;
`iniciar_fontes` na abertura; `sincronizar()` manual.

## DASHBOARD

Card "AVISOS (arquivo)" via arquivo→estado→lista; nativo saída 0;
demais dados intactos.

## EXEMPLOS

`dados.elixx`, `lista-api.elixx`, `formulario-api.elixx`,
`servidor_demo.py` (porta 8765), `dados-demo/status.json`. Todos
verificados; lista/form/dados validados em janela real (GET→lista,
POST→201 na tela).

## TESTES

27 novos: cliente (9), remota/arquivo (7), sintaxe/semântica (5),
integração/segurança/concorrência (6). Servidor em
`testes/servidor_teste.py` (9 endpoints). Determinísticos.

## TESTES VISUAIS

lista-api, formulario-api, dados.elixx e dashboard abertos de verdade
com dados reais; M8 no checklist para o usuário.

## LIMITAÇÕES

Sem WebSocket/SQLite/GraphQL; cancelamento best-effort; `compilar`
não busca remoto (prévia estática, documentado); sem cache;
`atualizar` mínimo 1s.

## PRÓXIMA FASE

FASE 07 — multimídia. Parada aqui (regra: não iniciar Fase 07).
