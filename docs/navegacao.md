# ELiXX — Navegação, telas, modais, abas, menus, tabelas (Fase 08)

```elixx
tela inicio {
    titulo: "Início"
    botão ir_perfil {
        quando clicar {
            ir("perfil")
        }
    }
}

tela perfil {
    inicial: verdadeiro
    botão voltar_btn {
        quando clicar {
            voltar()
        }
    }
}
```

- Telas de topo (como janelas); sem janela, criam raiz implícita.
- `ir("nome")` empilha, `voltar()` desempilha, `inicio()` volta ao
  começo. Erros amigáveis (pilha vazia, tela inexistente com sugestão).
- Parâmetros via estado (atribua antes de `ir`).
- Ciclo: `quando criar` (uma vez), `mostrar`/`esconder` nas transições.
- `modal nome { ... }` nasce escondido; `abrir`/`fechar` alternam
  (Toplevel real com grab no nativo).
- `abas` com filhas `aba`; `ativa: 0` inicial, `ligado_a` espelha no
  estado; clique alterna.
- `menu` enfileira botões filhos; `tabela` usa `colunas: "a" "b"` +
  `origem:` com lista de dicionários (reativa, ttk.Treeview).
- `lista` com `ligado_a` lê/escreve o índice selecionado.
- `focar("campo")` + `descricao:` (aria no HTML; limitação Tk
  documentada). Evento `mudanca` em entrada/checkbox/seleção/lista.
