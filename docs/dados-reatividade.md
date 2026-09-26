# ELiXX — Dados e reatividade (extensão dashboard)

## Camada de dados (`elixx/dados/`)

```text
ELiXX → FonteDados (interface) → Runtime → Cena → Renderer
```

- `FonteDados`: interface (`atualizar`, `snapshot`, `obter`). Novas
  fontes entram em `REGISTRO_FONTES` sem mexer em semântica ou runtime.
- `FonteSistema`: dados REAIS, só stdlib (ctypes/shutil/platform),
  só leitura. CPU via GetSystemTimes (diferencial entre amostras);
  RAM via GlobalMemoryStatusEx; disco via shutil; processos via
  snapshot Toolhelp32; rede via GetIfTable (critério: operacional OU
  com tráfego, sem loopback); sistema/hora via platform/time. Cada
  campo falha isolado para "indisponível" — nunca derruba a app.
- `FonteFalsa`: valores controlados para testes.

## Sintaxe de acesso

```elixx
origem: dados.sistema.cpu
origem: dados.sistema.ram.percentual
origem: dados.sistema.processos.lista
```

`a.b.c` é o nó `Membro` da AST (também prepara `cor.mais_claro()` no
futuro). A semântica valida forma (`dados.fonte.campo`) e fonte
conhecida, com sugestão em erro.

## Ligação componente ← dado

```elixx
texto val_cpu {
    origem: dados.sistema.cpu
    formato: "percentual"
}

barra bar_cpu {
    origem: dados.sistema.cpu
}

grafico hist_cpu {
    origem: dados.sistema.cpu
    formato: "percentual"
}

lista lista_proc {
    origem: dados.sistema.processos.lista
}
```

Formatos: `texto` (padrão), `percentual`, `inteiro`, `gb`, `mb`.
Decisão: a propriedade chama-se `origem:` (não `valor:`) porque declara
ligação com fonte viva, não conteúdo estático.

## Atualização

O tick do renderer (mesmo loop, sem concorrência) chama
`Vinculador.atualizar(ms)`: releitura a cada 1s, histórico de 60
amostras para gráficos, aplicação via `definir_valor` sem reconstruir
a janela. Ações: `atualizar_dados()`, `alternar_atualizacao()`,
`exibir(nome)` (par de `esconder`), `sair()`.

## Componentes novos

`painel` (contêiner), `cartao` (contêiner com borda), `barra`
(progresso 0-100), `grafico` (linha do histórico), `lista`
(somente-leitura). Filhos de painel usam coordenadas relativas a ele.
