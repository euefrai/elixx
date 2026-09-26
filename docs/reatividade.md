# ELiXX — Reatividade (Fase 05)

> Quando um dado muda, só os componentes que dependem dele atualizam.

## Bindings

```elixx
texto cpu {
    origem: dados.sistema.cpu      # fonte externa (Fase dashboard)
}

texto contador {
    origem: estado.contador        # estado (Fase 05)
}

texto total {
    origem: estado.qtd * estado.preco   # expressão derivada
}
```

O Vinculador descobre as dependências (`estado.qtd`, `estado.preco`) e
reavalia quando qualquer uma mudar. `total` não é armazenado: é
recalculado.

## Two-way (`ligado_a`, só com estado)

```elixx
entrada nome {
    ligado_a: estado.nome
}

checkbox ativo {
    ligado_a: estado.ativo
}
```

Fluxo estado → componente (push, sem brigar com digitação em foco) e
componente → estado (ao sair do campo/Enter, ao marcar, ao escolher).
Guardas de igualdade nos dois lados: sem loop infinito. `ligado_a`
com `dados.*` é erro (dados são somente leitura).

## Propriedades reativas

texto, barra, indicador, checkbox, entrada, selecao, lista, grafico.
(Posição/tamanho/opacidade seguem no motor de animação.)

## Eficiência

- Versões por chave: estado intacto nem é re-resolvido.
- Último valor: widget igual não é reescrito.
- Sem reconstrução de janela; sem callbacks encadeados (pull no tick).
- `vinculador.estatisticas` expõe resolucoes/envios/pulados (testes).
- Se o estado tiver `atualizacoes`, ela conta os ciclos (dashboard).

## Ciclos

Polling não recursa: escrever só acontece em evento de widget ou ação,
e cada escrita passa pelos guardas de igualdade. Rajadas convergem
para o último valor (testado com 100 escritas).
