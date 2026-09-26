# ELiXX — Formulários e validação (Fase 08)

```elixx
formulario cadastro {
    entrada nome {
        ligado_a: estado.nome
        obrigatorio: verdadeiro
        min_caracteres: 3
    }

    entrada email {
        ligado_a: estado.email
        validar: "email"
    }
}

botão enviar {
    quando clicar {
        validar("cadastro")
    }
}
```

Regras: `obrigatorio`, `validar: nenhum|texto|email|numero`,
`min_caracteres`, `max_caracteres`, `min_valor`, `max_valor`.
`validar()` lê o estado, escreve `estado.<form>_valido` (bool) e
`estado.<form>_erros` (lista, pronta para lista/texto).

Envio integrado (Fase 06):

```elixx
quando clicar {
    enviar("cadastro", "usuarios")
}
```

Valida → monta corpo do estado → POST assíncrono → resposta em
`estado.<form>_resposta`. Se inválido, mostra os erros e não envia.
