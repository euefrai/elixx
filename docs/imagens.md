# ELiXX — Imagens e SVG (Fase 07)

```elixx
imagem logo {
    arquivo: "assets/logo.png"
    tamanho: 128px 128px
    ajuste: "conter"
}

imagem avatar {
    url: "https://exemplo.com/a.png"
    reserva: "assets/padrao.png"
}

icone salvar {
    nome: "salvar"
    tamanho: 32px 32px
    cor: "#7aa2ff"
}
```

- `arquivo:` relativo à pasta do `.elixx` (use `/`, nunca `\` —
  a barra invertida é escape na linguagem). Remoto baixa em thread,
  mostra "carregando", usa cache e cai na `reserva:` se falhar.
- `ajuste:` `conter` (padrão, reduz sem distorcer), `esticar`,
  `preencher` (exatos só com Pillow; sem ela, comporta-se como conter).
- SVG: subconjunto seguro (rect/circle/ellipse/line/polyline/polygon,
  path M/L/H/V/Z, text; fill/stroke/opacity). `<script>`, eventos
  `on*`, curvas Bézier e tags desconhecidas são ignorados com aviso —
  nunca executados. SVG inválido é erro em português.
- Ícones embutidos: salvar, editar, excluir, fechar, adicionar, config,
  pesquisar, voltar, avancar, menu. `icone nome { }` usa o próprio nome.
- Erros (ausente, corrompido, formato) viram placeholder + mensagem;
  nunca derrubam a app.
