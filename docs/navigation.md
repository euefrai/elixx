# ELiXX — Navigation + Traversal (Fase 15)

Sabe POR ONDE é possível passar. Não decide, não executa, sem física,
sem IA. Camada derivada do World (sem duplicar entidades/posições).

## Sintaxe

```elixx
navegacao Rotas {
    caminho ChaoA -> ChaoB {
        modo: andar
        custo: 1
    }

    caminho Torre -> Plataforma {
        modo: descer
        requer: descer
    }
}
```

`navegacao` na janela; `caminho Origem -> Destino` (`->` ou `→`)
com `modo:` (descritor, ex. andar/pular/voar/descer), `custo:`
(número ≥ 0; padrão = distância geométrica), `requer:` (capability),
`bloqueado:` (verdadeiro/falso). Origem/destino = entidade do mundo
ou `<entidade>_borda_<lado>` (esquerda/direita/topo/base). Sem forma
simples (`caminho A -> B` sem chaves: modo andar, custo distância).
Mesma origem+destino+modo repetidos = erro (modos distintos OK:
A→B andar + A→B voar).

## Grafo derivado

`NavigationBuilder(mundo)` cria nós para TODAS as entidades
(`ent:<nome>`), superfícies de chão/plataforma/parede (parede: não
navegável, informativa) e bordas de plataforma (esquerda/direita nos
cantos superiores). Links estruturais entidade↔borda (modo andar)
pertencem à superfície (não são invenção). Edges SÓ declarados
(conservador: sem salto automático). Posições sempre ao vivo
(Motion reflete na hora). Obstáculo/parede cruzando o segmento
bloqueia geometricamente (Liang-Barsky interior; borda não conta;
pontas ignoradas) — calculado ao vivo, sem física.

## Consultas

`rota(grafo, origem, destino, holder?, mundo?)` → Dijkstra
determinístico (desempate por inserção): `{encontrado, motivo, nos,
edges, distancia_total, custo_total, modos, requisitos, path}`. Sem
caminho: "sem conexão"; só inacessível: "capacidade ausente" +
faltantes (sem exceção no normal). Origem/destino: entidade, nó ou
Vector2 (nó mais próximo, documentado). `rotas_alternativas(k)`:
melhor + variantes bloqueando 1 edge (determinístico).
`plano_travessia` → `{origem, destino, path, etapas, modos,
capacidades_necessarias}` (descrição; não move). `acessivel(holder,
edge, mundo)` → estruturado (bloqueado/requer via F14).

## Bordas e superfícies

Borda = ponto derivado do bounds ao vivo (esquerda/direita: cantos
superiores; topo/base: meios). Superfície compacta (início/fim/
comprimento; sem pixel-nodes): base do futuro andar contínuo.

## Debug

`debug_navegacao(grafo)`: NODES/EDGES/SURFACES/REQUISITOS (puro).

## F15 calcula caminhos. F15 não executa caminhos.
