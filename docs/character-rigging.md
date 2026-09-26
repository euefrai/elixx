# F23 — Automatic Character Rigging & 2D Puppet Core

> "IA prepara. O motor executa."

> "Uma imagem não contém informação visual que não esteja presente nela."

Núcleo que transforma análise visual estruturada em personagem 2D
animável, sem exigir montagem manual do rig. Runtime sem LLM, sem
rede, sem dependências pesadas: a inteligência de análise é
provider-based (Mock/Structured/Null nesta fase; real no futuro).

## Arquitetura

```text
Imagem / PerceptionResult (F22, opcional)
    ↓
CharacterAnalyzer (Null/Mock/Structured)
    ↓
CharacterAnalysis (detecções + avisos honestos)
    ↓  construir_rig (modos automático/profissional)
CharacterRig (partes, joints, camadas, máscaras, views, poses)
    ↓  rig_para_personagem
Character (F12, sem segundo puppet)
    ↓  transicionar_pose / Gesture
Motion Core (F11, sem segundo motor)
    ↓
Transform (F10) → Renderer
```

Módulo único: `elixx/visual/rigging.py`.

## Modos

- **Automático**: analyzer entrega detecções; `construir_rig` monta
  hierarquia + pivôs + joints + camadas. Sem `parent_id`, partes
  ancoram na raiz sintética `corpo` (aviso `hierarquia_inferida`).
- **Assistido**: `mesclar_analise(base, correcoes)` — mesmo id
  substitui, id novo adiciona; resto preservado; origem `assistido`.
- **Profissional**: tudo explícito — `RigPart` (bounds local, pivô,
  joint, z, máscara), `RigJoint` (pai, filho, pivô, limites, tipo),
  `RigLayer`, `CharacterMask`, `RigView`, `RigExpression`, `RigPose`.

## Entidades

- `CharacterPartDetection` — id, tipo (vocabulário `PARTES_CONHECIDAS`
  como dica; custom preservado + aviso), bounds, confiança,
  `parent_id`, visibilidade (`visivel/parcial/oculta` → avisos
  `parte_parcial/parte_oculta`).
- `CharacterMask` — `bounds` (retângulo), `poligono` (≥3 pontos) ou
  `referencia` (asset externo, só string). Sem bitmap pesado.
- `RigJoint` — pai, filho, pivô, limites mín/máx, tipo
  (`pivo/deslizante/fixa`); sem solver, sem IK.
- `RigView` — frente/costas/esquerda/direita/cima/baixo (reusa
  `DIRECOES` da F12); vistas são alternativas 2D, não 3D; ausentes
  não são fingidas.
- `RigExpression` — `{parte → {prop → valor}}`, combinável via
  `combinar` (última vence por parte/prop).
- `RigPose` — ajustes + expressão opcional; viram `Pose` F12
  (expressões com `expressao=True`); pose `neutro` sempre incluída.
- `CharacterRig` — CRUD validado (pais existentes, sem ciclos, teto
  32 níveis / 5000 partes), camadas ordenadas, JSON determinístico.

## Pivôs e joints

Pivô no formato F12 `(valor, unidade)` por eixo (`%` ou `px`).
Padrão do construtor: base-central (50%, 100%) para cabeça e membros,
centro (50%, 50%) no resto. Joints viram `Joint` F12 (limites com
clamp na aplicação de pose). Sem física.

## Animações automáticas

`definir_automatica(rig, nome)` → `Gesture` F12 (passos `Pose`;
o motor F11 executa). Disponíveis: respirar, piscar, olhar, falar,
acenar, andar, parar, balancar_cabelo. Passos sem parte no rig viram
aviso `automatica_parcial` (nunca erro, nunca invenção).

## Conversão F12

`rig_para_personagem(rig, nome)` cria `NoVisual` por parte (posição
local, pivô do rig), monta pai/filhos, joints, poses, expressões e
`representacoes` (vista → asset). Sem duplicar Character/Pose/Joint.

## Integrações

- **F22**: `analise_de_percepcao(result)` (observação → detecção,
  preservando classe/confiança/origem); F23 funciona sem F22.
- **F11**: `transicionar_pose` gera `DefinicaoAnimacao` (cabeça
  0°→10°→-10°→0°, braço 0°→45°→0°); nenhum motor novo.
- **F10**: pivôs e `Vector2`/`Bounds2D` reutilizados.

## Segurança e determinismo

Só JSON finito e raso; tetos (5000 partes, 32 níveis, ±1e9); NaN/
Infinity/gigantes/recursão/ids duplicados/pais ausentes/ciclos
recusados. Nenhuma avaliação dinâmica, nenhuma importação
programática, nenhum processo, nenhuma rede, nenhum download.
Strings maliciosas seguem inertes. Mesma análise → mesmo rig
(diversos testes de repetição).

## Limitações honestas

- Sem YOLO/SAM/MediaPipe/OCR/LLM (só contratos via analyzers).
- Sem IK solver, física, mesh/morph, lip sync real, inpainting ou 3D.
- Sem editor visual; sem câmera; testes nunca exigem display.
- Vista não fornecida não existe no rig (não reconstruída).

## Testes e performance

`testes/test_fase23.py`: 44 testes (análise, detecção, máscaras,
hierarquia, pivôs, joints, views, expressões, poses, serialização,
validação, ciclos, JSON malformado, NaN/Infinity/gigantes, strings
maliciosas, 3 analyzers, assistido, profissional, F12, Motion,
combinação, vistas, corpo incompleto, avisos, determinismo, stress
100/1000 partes, regressão). Demo:
`exemplos/character-rigging-demo.py` (Juh, Mock, sem display).
