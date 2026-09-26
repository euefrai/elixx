# ELiXX — World Core (Fase 13)

Representação lógica do mundo 2D (o World SABE; não pensa). Cena =
visual; World = significado. Sem segundo Transform/Motion/Cena, sem
loop/thread próprios.

## Sintaxe

```elixx
mundo Principal {
    tamanho: 2000px 1200px

    chão piso {
        posição: 0px 550px
        tamanho: 2000px 50px
    }

    plataforma superior {
        posição: 700px 350px
        tamanho: 300px 30px
    }

    parede esquerda {
        posição: 0px 0px
        tamanho: 40px 600px
    }

    área sala {
        posição: 100px 100px
        tamanho: 500px 400px
    }

    ponto objetivo {
        posição: 900px 300px
    }

    objeto caixa {
        posição: 600px 480px
        categoria: "caixa"
        tag: "interativo"
        visual: caixa_visual
    }

    usar personagem Heroi
}
```

`mundo` vive na janela/tela. Entidades: `chão, parede, plataforma,
obstáculo, objeto, área, ponto` (+ `usar personagem`). Props:
`posição`, `tamanho`, `categoria`, `tag`/`tags`, `visual: nome`
(aspas ou identificador, como `alvo:`), `pai:` (só área, sem ciclos).
`personagem`/`parte`/nomes de entidade não são reservados no lexer.

## Entidades e identidade

`WorldEntity`: nome global único no programa (parte/personagem),
tipo semântico, referência viva (nó ou Character, nunca cópia),
bounds base, categoria, tags, props. Sem visual = válido (spawn);
visual sem entidade = válido (compatibilidade).

## Bounds2D e relações

`Bounds2D` (x, y, largura, altura) com centro, contém-ponto,
interseção (área > 0), toque (só borda), contém, expandir, união,
distância (centros). Relações derivadas sob demanda: acima/abaixo
(bordas), esquerda/direita, perto (raio, padrão 100), contém/dentro,
sobrepõe, toca. Distância e direção (`B − A` entre centros) usam
Vector2 da F10. Bounds globais = origem global (cadeia de pais via
`combinar`) + tamanho (`tamanho:` explícito vence o visual; sem ele,
usa-se o nó; senão ponto).

## Consultas (QUERY, nunca COMMAND)

`por_id/por_nome/por_tipo/por_tag`, `na_area`, `em_regiao` (área não
contém a si), `proximos/vizinhos` (raio, tipo opcional), `sobrepostos`,
`distancia`, `direcao_de`, `visiveis_na_viewport` (cruza a viewport
F10; sem câmera). Ordem determinística (registro). Índices só por id
e tipo (sem quadtree; O(n) simples documentado).

## Regiões e viewport

Área com `pai:` forma subregião (mundo→casa→sala). Entidade pode estar
em várias regiões (sem exclusividade). Mundo tem limites lógicos
(`tamanho:`) e usa a viewport da cena para visibilidade.

## Snapshot e debug

`snapshot()` = tuplas congeladas somente leitura (mutar levanta erro;
mundo posterior não o afeta). `debug_texto()` = diagnóstico puro
(bounds/centros/regiões), opcional e sem tocar no runtime.

## World ↔ Character/Motion

`usar personagem` referencia o Character (posição/pose/direção/motions
via APIs F12). Motion reflete na hora (leitura ao vivo, sem cópia).

## O World NÃO implementa

pathfinding, navegação, capabilities, IA, comportamento, física,
colisão física, câmera. Apenas representação + consultas.
