# F24 — 2D Character Deformation & Living Puppet

> "F24 adiciona comportamento visual ao rig, não inteligência artificial."

> "Deformação não significa reconstrução de pixels ausentes."

A F23 diz quais são as partes e como se conectam; a F24 diz como elas
se deformam e se comportam como um único personagem — via `Transform`
existente, sem segundo motor, sem segundo puppet, sem segunda
matemática.

## Arquitetura

```text
F22 Percepção → F23 Rigging → F24 Deformação → F12 Character
    → F11 Motion Core → F10 Transform → Renderer
```

Módulo único: `elixx/visual/deformacao.py`.

## Deformações

`Deformacao(alvo, tipo, intensidade, parametros?, origem?)`.
Tipos: `rigid/scale/squash/stretch/bend/offset/rotate/tilt`.
Cálculos sempre **a partir da `BasePose`** (referência estável):

- `squash k`: escala `(1+k, 1-k)` — salto (`0.92 x 1.08` com `k=-0.08`).
- `stretch k`: escala `(1-k, 1+k)` — aterrissagem/espichar.
- `scale/rotate/offset/tilt/rigid`: uniforme, graus, `(dx,dy)`,
  inclinação honesta via rotação, identidade declarada.
- `bend`: representação + fallback `rotate` (`renderer_fallback`
  retorna `fallback_estruturado`, nunca finge deformação real).

Transições usam F11: `deformacao_para_motions` → `transicionar_pose`
→ `DefinicaoAnimacao` (ida; volta via `BasePose.restaurar`).

## Anti-drift

`BasePose.capturar(personagem)` lê `{parte → props}` atuais;
`restaurar` reaplica via `aplicar_pose` (público F12). Reaplicar a
mesma deformação parte sempre da base: nunca `1.0 → 0.9 → 0.81`.

## Anchors, influências, mesh

- `Anchor(id, posicao Vector2, parte_id?)` — ombro, olho, boca...
- `Influence(parte_id, joint, peso 0..1)` — multi-joint preparado;
  soma não imposta (misturas parciais honestas); sem skinning real.
- `Mesh2D/Vertex2D` — abstração nominal (vértices + parte dona);
  sem triangulação, GPU ou 3D.

## Expressões em camadas

`ExpressionStack` (base + olhos + boca + ...): `push/pop/resolver`
→ `Pose` fundida determinística. `compor_camadas([Pose...])`
(ordem crescente de prioridade) implementa a política
**manual > pose > expressão > automático** (última vence por
parte/prop — mesma regra de `Pose.combinar`, F12). Expressões F23
(`RigExpression`) viram `Pose` expressivas; bocas: neutra, sorriso,
aberta, fechada, surpresa (sem lip sync).

## Comportamentos vivos

Funções puras retornando passos `Pose` (o motor F11 executa):
`respirar` (tronco/peito, determinístico, sem threads),
`piscar` (coexiste com expressão/olhar/fala),
`olhar_para` (esquerda/direita/cima/baixo/centro; offset + cabeça),
`boca_estado`, `comportamento` (despacho). Movimento corporal
(andar/acenar) reusa `definir_automatica` (F23) e `Gesture` (F12);
compatível com F16/F17 (defs entram em `MotionGroup`).

## CharacterDeformationRig

Adaptação (não segundo Character): guarda rig + personagem + base +
anchors + influências + malhas + ativas; `aplicar` (da base),
`restaurar`, `animar` (motions F11); delega todo o resto ao
`Character` via `__getattr__`. `deformation_rig_de_rig` constrói a
partir de F23+F12 sem modificar o `CharacterRig`.

## Renderer

`renderer_fallback(deformacao)`: tipos Transform → `representavel`;
`bend`/mesh → estado estruturado + warning honesto.

## Segurança e determinismo

Só JSON finito e raso; tetos (10k anchors, ±1e9); NaN/Infinity/
gigantes/ids vazios/referências ausentes/pesos inválidos recusados.
Nenhuma avaliação dinâmica, importação programática, processo ou
rede. Strings maliciosas inertes. Mesma entrada → mesma saída
(testes de repetição e drift).

## Limitações honestas

- Sem YOLO/SAM/MediaPipe/OCR/LLM, física, IK, mesh real, lip sync,
  câmera, editor visual ou 3D.
- `bend` é representação + fallback, não curvatura real.
- Visibilidade é estado F23; deformação não reconstrói o oculto.

## Testes e performance

`testes/test_fase24.py`: 41 testes (lista §29 completa + tilt/scale/
rigid, despacho, mesh). Volumes 100/500/1000 partes < 60s
(construção, base, aplicação, composição, serialização). Demo:
`exemplos/living-puppet-demo.py` (Juh; Tk só com display, headless
nos testes).
