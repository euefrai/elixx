# F22 — Visual Perception Core

Núcleo de percepção visual: transforma entrada visual estruturada em
observações semânticas. **Percepção observa. Não decide nem executa.**

```text
ImageFrame -> PerceptionProvider -> PerceptionResult
    -> Geometry (F21, onde) -> Environment (F19, o que) -> World (F13)
```

## YOLO é um provider, não o Perception Core

O núcleo nunca sabe como o provider detectou algo. Futuros providers
(YOLO, OCR, acessibilidade, HTML, visão clássica, multimodais) falam
o mesmo contrato: `PerceptionProvider -> PerceptionResult`.

## API

- `ImageFrame(largura, altura, formato?, frame_id?, referencia?,
  dados?)` — dimensões inteiras > 0 (teto 100000); `dados` (bytes)
  é opaco e **fora** do JSON (só a contagem serializa). Sem Pillow
  obrigatório.
- `PerceptionObservation(id, classe?, bounds?, tipo?, confianca?,
  texto?, origem?, track_id?, metadata?)` — confiança `None` ou
  `0..1` (dado do detector, sem ranking); origem preservada como
  string opaca; tipos novos seguem representados, nunca descartados.
- `PerceptionResult(largura_imagem, altura_imagem, origem?,
  observacoes?, timestamp?, frame_id?, avisos?, metadata?)` —
  `to_dict/from_dict/to_json/from_json`; `por_id/por_classe/classes`;
  ids duplicados = erro; `analisar_sobreposicoes()` é **explícito**
  (O(n²) documentado — não roda sozinho na construção).
- `PerceptionProvider` — `nome/disponivel()/capacidades()/analisar()`.
- `NullPerceptionProvider` — resultado vazio válido (sempre
  disponível). `MockPerceptionProvider` — serve observações
  pré-estruturadas (dicts `{x, y, largura, altura, ...}` ou objetos).
- `YOLOProvider` — **só contrato**: `disponivel()` = biblioteca +
  modelo local presentes; nunca instala, nunca baixa, nunca usa rede;
  sem ambos, `analisar()` retorna erro claro. `OCRProvider` — só
  contrato (`disponivel()` = False nesta fase).
- `PerceptionRegistry` — `registrar/obter/listar/remover`; registro
  explícito, sem imports automáticos.
- `PerceptionDelta` / `calcular_delta(antes, depois)` —
  adicionados/removidos/alterados/mantidos por **id estável**; sem id
  estável não se inventa identidade persistente.
- `PerceptionSnapshot` — imutável (congela via JSON).
- `debug_percepcao(result|snapshot)` — texto puro, sem renderer.

## Integrações (só fatos)

- `percepcao_para_geometria(result)` → `GeometryMap` (posição vem da
  observação; metadata preserva classe/confiança/origem/texto/
  track_id; nenhuma Surface inventada).
- `percepcao_para_environment(result, env_id)` → `Environment`
  (classe vira tipo; desconhecida → `desconhecido` com classe em
  atributos; **zero interações** — detectar um botão não significa
  "pode clicar").
- Sem navegação automática (F15 intacta), sem motion, sem IA
  (nada alimenta contexto/intenção sozinho).

## Origem e confiança

Ambas viajam juntas até Geometry/Environment/World sem serem
apagadas. O núcleo não escolhe "melhor" detecção e não implementa
NMS (cada provider filtra internamente se precisar). Duplicatas na
mesma região são mantidas; sobreposição vira dado consultável.

## Segurança

Só números finitos, strings, booleanos e JSON raso; tetos (100k
observações, dimensões ≤ 100000); NaN/Infinity/gigantes/recursão/
chaves estranhas recusados com erro claro. Nenhuma avaliação
dinâmica, nenhum processo externo, nenhuma rede, nenhum download de
modelo, nenhum JavaScript. Strings maliciosas seguem inertes.

## Limitações honestas

- `tracking`: só transporte de `track_id`/`frame_id`, sem rastreio.
- Sobreposição pairwise é O(n²) e opt-in (50k observações não a
  disparam sozinhas).
- `YOLOProvider` com biblioteca+modelo presentes ainda retorna erro
  de contrato (inferência real em fase futura, só modelo local).
- Sem Pillow obrigatório; frame pode ser só metadados.

## Testes e performance

`testes/test_fase22.py`: 45 testes. Performance 100/1k/5k/10k/50k
observações < 60s (criação, JSON, geometria, snapshot, delta, debug).
Demo: `exemplos/perception-demo.py` (Mock, 1920x1080, sem YOLO).
