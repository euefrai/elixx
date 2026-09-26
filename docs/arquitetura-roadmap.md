# ELiXX — Arquitetura e roadmap

## Arquitetura (Fase 01)

```text
elixx/
  elixx/
    ...
    dados/            # FonteDados, FonteSistema (real, stdlib), FonteFalsa
    visual/reativo.py # Vinculador (tick único, sem loop concorrente)
    animacao/         # Fase 03: easing.py (matemática pura) + motor.py
                      # (interpolação na Cena; renderer aplica)
    visual/reativo.py # Vinculador v2: estado+versões+expressões
    runtime/estado.py # Fase 05: Estado reativo com versão por chave
    dados/http.py     # Fase 06: ClienteHttp (stdlib, sem exceção p/ UI)
    dados/remoto.py   # Fase 06: FonteRemota/Arquivo (thread, estados)
    multimidia/       # Fase 07: recursos, SVG, icones, audio, video
    runtime/temas.py  # Fase 08: temas resolvidos (hex/px)
    runtime/navegacao.py  # Fase 08: pilha de telas
    runtime/validacao.py  # Fase 08: regras puras de formulário
    compilador/componentes.py  # Fase 08: expansão (parse→semântica)
    runtime/listas.py   # Fase 09: reconciliação de linhas (runtime)
    compilador/modulos.py  # Fase 09: imports com raiz/traversal/ciclos
  ...
  testes/               # 259 testes (+ assets em exemplos/assets/)
  exemplos/             # + 01–09 didáticos; app/ multimódulo real
```

Decisões: Python (mesma stack do Fajulto, zero dependências); parser não
conhece eventos/ações (extensão sem quebrá-lo); semântica consulta o
runtime; propriedades de uma linha (dispensa separadores); sem pastas
vazias (multimídia real é roadmap, tipos já existem na AST).

## Roadmap

- Fase 02 (concluída): renderer nativo Tkinter atrás de `Renderizador`
  abstrato; Cena intermediária; `conteúdo`/`fonte`; 63 testes.
- Fases 03–08: animação, layout, estado, dados/HTTP, multimídia,
  aplicações (ver RELATORIO-FASE-0X.md).
- Fase 09 (atual): composição — estado local, listas dinâmicas, ações,
  funções, módulos/import.
- Futuro: 3D, editor visual, IA, voz; integração Fajulto ↔ ELiXX.
