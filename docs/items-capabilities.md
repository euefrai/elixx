# ELiXX — Items + Capabilities (Fase 14)

Camada semântica: SABE o que pode ser feito. NÃO decide, NÃO executa.
Sem IA, sem comportamento, sem física, sem navegação.

## Sintaxe

```elixx
item BotaFoguete {
    categoria: "equipamento"
    tags: "voo" "propulsao"
    slot: "pes"
    imagem: "assets/bota.png"
    capacidade voar {
        descricao: "voar com propulsão"
        requer_equipado: "BotaFoguete"
    }
    capacidade pairar
}

personagem Heroi {
    possui: "Corda"
    equipa: "BotaFoguete"
    capacidade andar
    capacidade pegar {
        parametro alvo
        requer_proximo: "alvo"
        raio: 250px
    }
}

mundo Mundo {
    usar personagem Heroi
    usar item Corda {
        posição: 250px 420px
    }
    usar item BotaFoguete como botas_hero
}
```

`item`/`capacidade` por lookahead (sem reservar no lexer). `capacidade`
também em parte (pertence ao personagem). `parametro nome` declara
parâmetros esperados (ex. alvo). Requisitos (`requer_*`): equipado,
possuído, presente, próximo (+`raio:`), tag, categoria, tipo, estado,
capacidade. `requer_tag/categoria/tipo` avaliam o ALVO; valor `"alvo"`
aponta para o alvo do `pode()`.

## Itens

`ItemDefinition` (categoria/tags/estado/imagem/visual/vistas/slot/
anexo/capacidades) × `ItemInstance` (identidade + estado próprio).
`usar item X [como Y] [{posição/tamanho}]` instancia e coloca no mundo
(entidade tipo `item`; bounds do override, do visual ou ponto).
Posse/equipamento via API ou declarativo (`possui:`/`equipa:` criam
instâncias). Equipar exige posse (erro claro, sem auto-posse).
`slot:` do item ou informado; `anexo:` = parte padrão (validada contra
o personagem). `ponto_anexo()` = Transform global da parte (segue o
movimento; sem offset nesta fase).

## Capabilities

`Capability` (nome, provider `personagem:X`/`item:Y`, descrição,
parâmetros, requisitos) em `CapabilitySet` (sem duplicar; provedores
unem em ordem). Composição: próprias + itens equipados (ordem
determinística). `tem_capacidade`, `capacidades_de`.

## pode()

```python
pode(heroi, "voar", mundo)
# {"permitido": True, "capacidade": "voar",
#  "motivo": 'Heroi pode "voar".',
#  "requisitos": [{"tipo": "equipado", "alvo": "BotaFoguete",
#                  "ok": True, "detalhe": "BotaFoguete equipada."}]}
```

Capacidades com parâmetros exigem alvo. Espaciais exigem mundo e
âncora (dono fora do mundo = motivo). `estado` avalia o provedor
equipado. Determinístico, sem efeitos, sem execução.

## Integração

World fornece posição/bounds/distância/proximidade/presença; Character
fornece partes/âncoras; Transform/Motion intactos (anexo acompanha via
hierarquia F12). Renderers ignoram capabilities (diagnóstico textual
via `debug_capacidades`).

## F14 não executa capabilities

Não existe `executar_capacidade`. Não há planner/IA/navegação/física/
inventário visual/HUD. Metadados são dados (sem eval/exec).
