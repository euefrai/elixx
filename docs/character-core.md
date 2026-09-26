# ELiXX — Character / Puppet Core (Fase 12)

Personagem 2D articulável como entidade coerente: estrutura + metadados
sobre Scene/Node/Transform/Motion existentes. Sem segundo runtime, sem
segundo motor, sem matemática duplicada.

```
Pose ──→ Motion (F11) ──→ Transform (F10) ──→ Cena ──→ Renderer
```

## Sintaxe

```elixx
personagem Heroi {
    posição: 300px 350px

    parte corpo {
        imagem: "corpo.png"
    }

    parte cabeca {
        posição: 30px 10px
        pivô: 50% 100%
    }

    parte braco {
        posição: 60px 0px
        pivô: 10px 20px
        junta: "ombro"
        limite_min: 0deg
        limite_max: 120deg

        parte antebraco {
            posição: 40px 0px

            parte mao {
                posição: 30px 0px
            }
        }
    }

    pose repouso {
        braco:
            rotação: 0deg
        cabeca:
            rotação: 0deg
    }

    pose acenando {
        braco:
            rotação: 45deg
        antebraco:
            rotação: 60deg
    }

    expressao sorriso {
        cabeca:
            rotação: 5deg
    }
}
```

`personagem`/`parte`/`pose`/`expressao` não são reservadas no lexer
(lookahead, como `grupo`): `imagem objeto {` e `grupo personagem {`
continuam válidos. `parte corpo {` aceita `corpo` como nome.

## Regras

- Hierarquia por aninhamento (árvore; ciclo impossível por construção).
- Nomes de partes globais e únicos (identidade estável, mesmo com a
  pose mudando). Colisão com outra parte/componente/janela = erro.
- Pose referencia parte exata ou erro (`Parte 'x' não encontrada...`).
- Pose é parcial (o resto preserva); `expressao` é pose parcial.
- `imagem: "a.png"` no personagem/parte = visual do nó (mesmo
  carregamento das imagens). Visuais comuns também funcionam como
  filhos (`imagem foto { arquivo: ... }`).
- `junta: "nome"` é metadado; `limite_min/max` (graus) fazem clamp
  previsível na aplicação de pose (motions escrevem direto).
- `direcao: frente|costas|esquerda|direita|cima|baixo` + vistas
  (`frente: "f.png"`...) = representação por estado (2D, sem 3D).
- `asset_<nome>: "a.png"` = variante semântica da parte
  (ex. `asset_fechado` no olho; troca via `definir_variante`).
- Root controla posição/rotação/escala/opacidade globais (opacidade
  multiplica pela hierarquia, F10). Camadas usam `ordem_visual()`.

## API interna (elixx/visual/personagem.py)

`vincular_personagens(cena)`, `Character` (obter_parte/pose,
aplicar_pose, transicionar_pose→DefinicaoAnimacao, executar_gesto,
definir_direcao/variante, obter_transform_global, estado_resumo),
`CharacterPart` (transform_local/global), `Joint` (limites/clamp),
`Pose` (+combinar: última vence), `Gesture` (+MotionGroup),
`ManualAnalyzer`/`CharacterAnalyzer` (fundação assistida; mock honesto,
sem IA externa).

Transição de pose GERA motions (sem interpolação própria); gesto
encadeia poses com origem encadeada (passo 2 parte do fim do passo 1).

## O Character Core NÃO possui

IA, IK, navegação, física, colisão, inventário, capabilities,
comportamento, Studio/editor. Limites valem em poses (motions diretos
não passam pelo clamp — F13 poderá impor ao vivo).
