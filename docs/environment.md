# ELiXX — Environment Bridge (Fase 19)

Camada de ambiente estruturado: representa páginas, apps, janelas,
painéis e botões como dados — SEM visão computacional, SEM
screenshots, SEM LLM e SEM executar código do ambiente.

```
Fonte externa (HTML/app/desktop/cena ELiXX/futura visão)
        ↓
Environment Adapter (ambiente_de_dict)
        ↓
Environment (nós/regiões/superfícies/limites/interações)
        ↓
Environment → World Bridge (vincular_ambiente)
        ↓
World (F13) → Navigation (F15, sem pathfinding novo)
        ↓                                    ↓
Interaction (executor mock)          AIContextBuilder → AIProvider
                                     → AIIntent → AIPlannerBridge (F18)
```

## Environment

`Environment(id, nome, tipo, largura, altura, metadados)`. Tipos
fechados: web, aplicativo, desktop, elixx, generico (nada executável).
Guarda nós (ordem de inserção), regiões, superfícies, limites e
interações. `validar()` retorna `valido/codigo/motivo` (refs, ciclos,
tipos, limites). `to_dict/from_dict/to_json/from_json` determinísticos
(chaves ordenadas, só JSON finito).

## Node

`EnvironmentNode(id, nome, tipo, x, y, largura, altura, visivel,
habilitado, interativo, texto, role, atributos)`. Tipos conhecidos:
janela, regiao, painel, caixa, botao, entrada, selecao, lista, item,
imagem, texto, menu, barra, tabela, desconhecido. Tipos novos são
aceitos como dados (`tipo_conhecido=False`), nunca como código.
Geometria deriva `left/right/top/bottom/center/bounds` reutilizando
`Vector2` (F10) e `Bounds2D` (F13). Árvore pai/filho com detecção de
ciclo e teto de profundidade (32).

## Region

`EnvironmentRegion(id, nome, nos, superficies, limites, sub_regioes,
pai)`. Consultas: `regiao_por_id`, `regiao_por_nome`,
`nos_da_regiao`; pai/filhas via `pai`/`sub_regioes`.

## Surface

`EnvironmentSurface(id, owner, x, y, largura, altura, orientacao, tipo,
capacidades, bloqueada)`. Tipos: horizontal, vertical, area,
desconhecida. NÃO assume caminhável: `navegavel()` é só candidata
(não bloqueada + área positiva); a capacidade (andar, escalar...)
vem dos dados ou das regras do chamador, reutilizando os nomes de
capabilities da F14 sem duplicar o registry.

## Boundary

`EnvironmentBoundary(id, owner, lado, x, y, largura, altura)` com
lados topo, base, esquerda, direita, interna, externa.
`derivar_de_node(no, lado)` gera as 5 bordas do bounds (topo/base =
faixas de altura zero; esquerda/direita = faixas de largura zero).
`ponto()` devolve o ponto representativo documentado.

## Interaction

`InteractionDescriptor(nome, tipo, alvo, requisitos, parametros_permitidos)`.
Tipos conhecidos: clicar, focar, escrever, selecionar, limpar, abrir,
navegar, fechar, minimizar, maximizar (extensível só como dado).
`validar_parametros` aceita só chaves permitidas com valores JSON
finitos. `InteractionExecutor(environment)` tem
`validar/simular/executar`: checa alvo existente, interação registrada
e compatível com o alvo, alvo habilitado, parâmetros e capabilities do
agente (via `tem_capacidade` F14 ou lista simples). `simular` é
dry-run (sem efeitos); `executar` é mock seguro com log — NÃO controla
navegador, mouse, teclado ou apps (ver Limitações).

## Capabilities (F14)

Sem duplicar nada: superfícies carregam nomes de capabilities;
o executor e a navegação avaliam contra o holder existente
(`tem_capacidade`, `requer` nos edges). O módulo não define
`Capability`, `CapabilitySet` ou registry.

## Environment → World

`vincular_ambiente(environment, mundo=None, nome_mundo=None)`:
nós com superfície horizontal navegável → `plataforma`; vertical →
`parede`; contentores (janela/regiao/painel/menu/barra/tabela/lista)
→ `area`; demais → `objeto`. Preserva ids, geometria (`base` +
`tamanho_explicito`), hierarquia (`props.pai`), role/texto e
capacidades (`props` + `tags`). Regiões sem entidade própria viram
`area` com bounds = união dos membros. Fonte estrutural → representação
operacional; o World continua dono do espaço.

## Navegação (F15)

`construir_grafo_de_ambiente(mundo, ligacoes=None, nome=None)` cria
nós `ent:*`, superfícies/bordas de plataforma (igual ao
`NavigationBuilder`) e SÓ os edges declarados em `ligacoes`
(`origem/destino/modo/custo/requer/bloqueado`). Sem ligações o grafo
tem zero edges — filosofia conservadora da F15: nada de rotas
automáticas. Pathfinding, `rota`, `rotas_alternativas` e
`plano_travessia` são os existentes (nenhum algoritmo novo aqui).

## AI Context Builder

`AIContextBuilder().construir(environment, mundo, agente, grafo=None,
destino=None, raio=400)` devolve dict com ambiente, agente, posicao,
capacidades, regioes, elementos, superficies, interacoes,
destinos_possiveis, relacoes (filho_de/contem/em_regiao/sub_regiao_de)
e rotas_disponiveis (até 3, só com grafo+destino, via F15).
Determinístico, serializável, JSON-safe: sem objetos, código, funções
ou referências executáveis. O agente pode ser `Character` ou dict
`{nome, x, y, capacidades}`. O contexto alimenta
`AIProvider.gerar_intencao(contexto)` (F18, fronteira externa).

## Estrutura → semântica (regras fixas)

1. `botao` visível+habilitado → interativo + clicar/focar.
2. `entrada` habilitada → focar/escrever/selecionar/limpar.
3. `selecao`/`lista` → selecionar/abrir/navegar.
4. `janela` → fechar/minimizar/maximizar.
5. Nó com geometria → 4 boundaries + externa.
6. `painel`/`caixa`/`barra` ou `atributos.superficie=True` →
   superfície horizontal (orientação/capacidades/bloqueio via
   atributos). Nada além disso; sem IA, sem adivinhação.

## Segurança

Ambiente = dado não confiável: sem `eval/exec/import` dinâmico,
shell ou subprocess em nenhum caminho; IDs/nomes maliciosos seguem
strings inertes (resolução só por igualdade exata); sem travessia
interpretada; ciclos, refs inválidas, tipos desconhecidos, NaN,
infinito, estruturas gigantes (teto 20000 nós) e colisões de ID são
erros claros. Checagem textual no teste (`test_sem_execucao_dinamica`).

## Determinismo

Mesma entrada → mesma saída: ordem de inserção preservada, saídas
ordenadas por id, sem `random`, sem relógio em decisões, sem threads,
sem estado global.

## Limitações (honesto)

- Sem HTML parsing real (o adapter recebe dicts já estruturados).
- Sem controle de navegador/apps/mouse/teclado (executor é mock).
- Sem visão/OCR/física/LLM/NLP (fora do escopo até F20+).
- Superfície nunca afirma caminhabilidade sozinha.

## Exemplos

- `exemplos/environment.elixx` — cena ELiXX espelhando a árvore.
- `exemplos/environment_demo.py` — `python exemplos/environment_demo.py`.
- `exemplos/environment_tk.py` — demo visual (`python ...`, precisa de display).
