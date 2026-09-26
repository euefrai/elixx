# F21 — Visual Geometry Core

Núcleo independente de geometria visual: representa **onde algo está**.
Não decide o que fazer, qual caminho escolher ou qual botão clicar —
essas decisões pertencem às camadas superiores (Navigation, Motion,
Behavior, AI Bridge). A geometria fornece apenas fatos estruturados.

## O que a F21 NÃO implementa

- F21 NÃO implementa CSS.
- F21 NÃO implementa visão computacional.
- F21 NÃO implementa YOLO.
- F21 NÃO implementa OCR.
- F21 NÃO implementa navegador.
- F21 NÃO implementa IA.
- F21 NÃO implementa física, pathfinding, planner ou execução de ações.

## Arquitetura

```text
Environment (F19, o que existe)
    ↓  só geometria explícita; nunca inventada
GeometryMap (onde existe)
    ↓  fonte espacial; sem duplicar entidades
World (F13, fonte semântica)
```

Módulo único: `elixx/visual/geometria.py` (stdlib + F10/F13/F19).

## Reuso (sem duplicação)

- `Vector2` — reutilizado da F10 (`transform.py`).
- `Bounds2D` — reutilizado da F13 (`mundo.py`).
- Novos: `Point2D` (subclasse de `Vector2`) e `Size2D` (largura/altura).
- `Transform`/`Scene` continuam donos de movimento; o `GeometryNode`
  guarda bounds **local** e o mapa deriva o global por soma de origens
  (sem rotação/escala — limitação documentada).

## API

- `GeometryNode(id, bounds, parent_id?, visible, enabled, z_index,
  metadata)` — bounds local; consultas `contem_ponto`, `intersecta`,
  `sobrepoe`, `toca`, `distancia_para` (centros), `expandido`,
  `transladado`; acessores `esquerda/direita/topo/baixo/tamanho`.
- `GeometryMap(nome)` — `adicionar/atualizar/remover/obter/listar`,
  `filhos/ancestrais/descendentes`, `ordenar_z` (por `z_index`,
  inserção), `bounds_global/centro_global`,
  `local_para_global/global_para_local`.
- Relações (fatos globais): `relacao(a, b)` →
  `acima/abaixo/esquerda/direita/dentro/contem/sobrepoe/toca/
  distancia/direcao`; atalhos `acima_de/abaixo_de/a_esquerda_de/
  a_direita_de`.
- Direção (`direcao_entre`): 8 vias + `centro` a partir dos centros;
  `dy` positivo = sul (Y desce, convenção F10); diagonal quando o eixo
  secundário tem ao menos metade do dominante.
- Regiões: `GeometryRegion(id, bounds, parent_id?, tipo, metadata)`;
  `entidades_na_regiao/regioes_sobrepostas/regioes_com_ponto`.
- Consultas: `buscar_por_ponto/por_area/por_regiao/proximos
  (centro, empate por id)/direcao/intersecoes` — determinísticas,
  sem ranking por importância.
- Snapshot: `mapa.snapshot()` → `GeometrySnapshot` imutável
  (congela via JSON; alterações posteriores não a afetam).
- Debug: `debug_geometria(mapa|snapshot)` — texto puro, sem renderer.
- Serialização: `to_dict/from_dict/to_json/from_json` (só JSON finito).

## Coordenadas

`bounds` é **local ao pai** (pai ausente = já global).
Exemplo: pai `(100,100)` + filho `(20,30)` → global `(120,130)`.
Ciclos (`A→B→C→A`) e pai ausente geram erro estruturado.
Hierarquia além de 32 níveis é recusada.

## Mapa explícito

`parsear_mapa_explicito({id: {x, y, largura, altura, parent_id?,
visible?, enabled?, z_index?, metadata?}})` — aceita só números
finitos ≤ ±1e9, strings, booleanos e estruturas rasas; rejeita NaN,
Infinity, gigantes, recursão profunda e chaves desconhecidas.

## Integração Environment (opcional, sem ciclo)

`environment_para_geometria(env, geometria=None)` → `(mapa, ausentes)`.
Entra no mapa quem tem geometria **real** (`tem_geometria()`) ou
entrada explícita (que vence). Sem nenhum dos dois, o id vai para
`ausentes` — sem posição falsa, sem ordem DOM como coordenada,
sem layout fictício. Regiões F19 sem geometria real ficam de fora.
A F20 **não** depende da F21.

## Integração World (opcional, sem duplicar)

- `geometria_para_world(mapa, nome)` — World novo, uma entidade por nó
  **visível** (`objeto`; regiões viram `area`), `props = {geo_id, ...}`.
- `vincular_geometria_world(mundo, mapa)` — atualiza `base` das
  entidades existentes pelo global do mapa; retorna
  `{atualizadas, ausentes}`; nunca cria nem remove entidades.

## Segurança

Entrada externa é dado: validação de finitude, teto ±1e9, teto de
20000 nós, metadados só JSON raso. Nenhuma avaliação dinâmica,
nenhuma importação programática, nenhum processo externo, nenhuma
rede. Strings maliciosas seguem inertes como ids/metadata.

## Limitações honestas

- Sem rotação/escala na derivação global (soma de translações).
- `distancia` = distância entre centros (mesma regra do World).
- `sobrepoe` exige área > 0; encosto de borda é `toca`, não sobreposição.
- Visibilidade é só estado (`visible`), sem composição visual.
- `z_index` só ordena; sem compositor.

## Testes e performance

`testes/test_fase21.py`: 45 testes (primitivas, relações, hierarquia,
coordenadas, regiões, consultas, integrações, JSON, NaN/Infinity/
gigantes/inválidas, determinismo, segurança, performance
100/1000/5000/10000 nós < 60s). Demo: `exemplos/geometry-demo.py`.
