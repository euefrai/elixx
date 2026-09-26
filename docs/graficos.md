# ELiXX — Gráficos (Fase 07, Canvas próprio)

```elixx
estado {
    vendas: [10, 30, 25]
}

grafico linha_vendas {
    tipo: "linha"   # linha | barras | pizza | area
    texto: "Vendas"
    origem: estado.vendas
    tamanho: 400px 160px
}
```

Dois modos (mesmo componente, sem sistema paralelo):

- **série**: `origem` entrega lista → substitui os dados (máx. 120);
- **histórico**: `origem` entrega número → acumula 60 amostras
  (ex. CPU ao vivo; compatível com a Fase dashboard).

Mudar o estado redesenha só o gráfico (Vinculador + `definir_valor`,
sem reconstruir a janela). Escala automática pelo máximo; pizza com
paleta fixa de 8 cores. Listas literais: `estado.x = [10, 25]`.
