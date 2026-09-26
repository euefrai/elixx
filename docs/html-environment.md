# HTML → Environment (Fase 20)

Adapter real de HTML para `Environment` (F19). HTML externo é tratado
exclusivamente como **dado**: nenhum JavaScript é executado, nenhum CSS
é interpretado, nenhuma URL é aberta, nenhum request é feito.

```text
HTML
 ↓  html.parser (stdlib)
HTMLNode (árvore + avisos)
 ↓  HTMLAdapter
Environment (F19)
 ↓  vincular_ambiente (F19)
World → Navigation → … → AIContextBuilder → AIProvider (F18)
```

Só stdlib, sem dependências externas, sem navegador, sem threads. Dois
parses do mesmo HTML produzem os mesmos IDs e a mesma estrutura.

## Parser (`parsear_html`)

`html.parser.HTMLParser` com `convert_charrefs=True` (entidades como
`&amp;`, `&#227;` decodificadas). Comportamento com HTML malformado
(tolerante, sem virar navegador):

- tags não fechadas: adotadas pelo ancestral aberto (ex. `<p>aberto`
  vira parágrafo com o texto seguinte);
- end tag sem par: ignorada;
- elementos vazios (`br`, `img`, `input`, `meta`, …): nunca empilhados;
- comentários, doctype e processing instructions: ignorados;
- texto fora de qualquer elemento: guardado numa raiz `fragment`;
- sem `<html>`: usa o único elemento raiz, ou `fragment` se houver
  vários;
- teto: 20000 nós e 256 níveis (acima disso, `ErroELiXX` claro).

Scripts e estilos: `<script>`/`<style>` entram na árvore como nós
presentes (`tipo` `script`/`estilo`, conteúdo descartado) e geram
avisos `script_ignorado` / `estilo_ignorado`. Conteúdo nunca avaliado.

## HTMLNode

`tag` (minúscula), `atributos` (só safelist, inertes), `texto` (direto,
normalizado), `parent`, `children`, `ordem` (documento), `profundidade`.
`texto_completo()` = direto + descendentes, com whitespace colapsado
(`"  Olá   mundo "` → `"Olá mundo"`).

## HTMLAdapter (`HTMLAdapter.parsear(html, geometria=None, …)`)

Retorna `(Environment, avisos)`. Avisos são dicts
`{codigo, motivo}`: `script_ignorado`, `estilo_ignorado`,
`handlers_removidos`, `id_duplicado`, `geometria_orfa`,
`geometria_invalida`, `superficie_sem_geometria`,
`profundidade_truncada`.

### IDs (regra documentada)

Explícito vence: `id="login"` → `login`. Sem id: caminho estrutural
`html.body.main.button[0]` (`[i]` = posição entre irmãos de mesma tag,
só quando há mais de um). Duplicado explícito: sufixo determinístico
em ordem de documento (`x`, `x__2`, …) + aviso — nunca sobrescreve.

### Mapeamento HTML → Environment

| HTML | tipo | interativo | interações |
|---|---|---|---|
| `button`, `input submit/button/image` | `botao` | sim | clicar, focar |
| `input` texto/busca/… | `entrada` | sim | focar, escrever (+limpar se editável) |
| `input checkbox` | `selecao` | sim | focar, marcar, desmarcar |
| `input radio` | `selecao` | sim | focar, selecionar |
| `textarea` | `entrada` | sim | focar, escrever, limpar |
| `select` | `selecao` | sim | focar, selecionar |
| `a` | `link` | sim | abrir |
| `form` | `formulario` | não | — |
| `header/nav/main/section/article/aside/footer` | `regiao` | não | — (+`EnvironmentRegion`) |
| `div` | `painel` | não | — |
| `span` (só texto) / `h1–h6` / `p` / `label` | `texto` | não | — |
| `span` (com filhos) | `caixa` | não | — |
| `img` | `imagem` | não | — |
| `table` / `ul,ol` / `li,option` | `tabela` / `lista` / `item` | não | — |
| demais | `elemento` | não | — (nunca descartada) |

Precedência: tag semântica vence; `role` ARIA vence em `div`/`span`
genéricos; tag desconhecida consulta ARIA e, sem regra, vira
`elemento`. `div role="button" aria-label="Configurações"` →
`botao` interativo com clicar/focar. `aria-label` vira `nome`;
`aria-hidden="true"`/`hidden`/`input hidden` → `visivel=False`;
`disabled`/`aria-disabled` → `habilitado=False` (o executor F19 recusa
com `alvo_deshabilitado`).

### Atributos

Preservados (inertes): `id class role aria-* name type value
placeholder title alt href action formaction src method disabled
readonly required checked selected` + `data-*`. `class="card principal"`
vira `["card", "principal"]`. Atributos sem valor valem `""` (presença
= verdadeiro). `on*` e `style` descartados e contados. `href`/
`action`/`src` com `javascript:`/`data:` seguem strings com flag
`url_inerte` — nunca abertas.

### Texto e nome

Tags de texto recebem o texto completo da subárvore; contêineres, só o
direto; `script`/`style`, nada. `nome` = `aria-label` → texto →
`name`/`alt`/`title`/`placeholder`/`value` → `id` → caminho (teto 120).

### Regiões

Cada tag de região vira `EnvironmentRegion` (`reg_<id>`) com o próprio
nó + todos os descendentes como membros; regiões aninhadas ligam
`pai`/`sub_regioes`. A árvore nunca é achatada (exceto além de 32
níveis, com aviso `profundidade_truncada`).

### Geometria opcional (nunca inventada)

`geometria={id: {x, y, largura, altura}}` de fonte externa. Sem entrada:
`0,0,0,0` (estrutural, válido). Valores não-finitos/negativos e ids
órfãos geram aviso e são ignorados. **Nenhuma `Surface` nasce de tag**:
só com `"superficie": true` (+`capacidades`, `orientacao`,
`bloqueada` opcionais) na entrada de geometria. Sem bordas automáticas
(o chamador pode usar `gerar_boundaries` da F19). CSS não é lido:
nem `style`, nem seletores, nem layout — classes seguem metadados.

## Segurança

`eval/exec/__import__/importlib/subprocess/socket/requests` e
automação (playwright/selenium) ausentes por construção (teste
automatizado varre o fonte). Entradas maliciosas (`<script>`,
`onerror`, `javascript:`, `form action` externa) permanecem inertes.

## Integração F19/F18

`vincular_ambiente(env)` → `World` (link→objeto, regiões→áreas, sem
`HTMLWorld` paralelo). `construir_grafo_de_ambiente(mundo)` sem
ligações tem zero edges (F15 conservadora: sem geometria/rotas, sem
caminho inventado). `AIContextBuilder` gera contexto JSON-safe
(regiões, elementos, interações clicar/escrever, sem HTML bruto) para
`AIProvider.gerar_intencao`. `InteractionExecutor.simular/executar`
segue mock (dry-run sem efeitos).

## Limitações (honesto)

Sem parsing de CSS, sem layout/engine visual, sem JS/DOM dinâmico,
sem fetch de sub-recursos, sem shadow DOM, sem acessibilidade
computada além das regras ARIA acima, sem controle de navegador
(`executar` continua mock). Profundidade >32 é nivelada, não perdida.

## Exemplos

`exemplos/html-ambiente.html` (loja: header/nav/main/form/tabela/ARIA/
tag desconhecida/script de teste) e `exemplos/html_environment_demo.py`
(10 passos, sem navegador/request/JS).
