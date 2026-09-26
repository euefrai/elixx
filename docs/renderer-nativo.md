# ELiXX — Renderer nativo (Fase 02)

## Backend escolhido: Tkinter (stdlib)

Análise técnica das opções:

| Backend   | Distribuição | Windows | Eventos | 2D | Imagem | Animação | GPU/3D futuro | Veredito |
|-----------|--------------|---------|---------|----|--------|----------|---------------|----------|
| Tkinter   | zero (stdlib)| nativo  | maduros | Canvas/Label/Button | PhotoImage (+Pillow) | `after()` | via troca de backend | **escolhido** |
| PySide/Qt | pesada (~100MB+) | sim | ótimos | ótimo | sim | sim | sim | descartado: viola "sem dependências pesadas" |
| SDL/pygame| DLLs extras | sim | baixo nível | manual | sim | loop próprio | parcial | descartado: botão teria que ser reinventado |
| Win32 puro| zero | nativo | manual | GDI manual | manual | manual | sim | descartado: boilerplate excessivo p/ Fase 02 |
| Skia      | sem binding leve oficial | — | — | ótimo | sim | sim | sim | descartado: sem distribuição simples |

Troca futura de backend não toca o runtime: basta outra subclasse de
`Renderizador`. Backends convivem: `nativo` (janela real) e `html`
(`elixx compilar`, prévia).

## Pipeline

```text
Código → Lexer → Parser → AST → Semântica → Objetos → Cena → Renderer
```

A Cena (`elixx/visual/cena.py`) é a representação intermediária: o
renderer recebe dados já processados (pixels, hex, textos).

## Coordenadas (decisão)

- x cresce para a direita, y cresce para baixo;
- origem (0, 0) = canto superior esquerdo da área de conteúdo da janela;
- `posição` da janela = posição na tela (gerenciador do SO);
- `posição` de componente = relativa à área de conteúdo;
- `%` = fração da janela; `vw`/`vh` = fração da janela (base do layout futuro).

## Fluxo de eventos (sem sistema paralelo)

```text
clique físico → Tk Button → ao_interagir(no, "clicar")
→ executor.disparar(objeto, "clicar") → Bloco AST → ações
```

`mostrar(...)` aparece na barra de mensagens da janela e no console.

## Loop

`mainloop` do Tk + tick de 50ms chamando `atualizar(dt_ms)` (sincroniza
visibilidade runtime → tela; `dt_ms` prepara animação da Fase 03).

## Sintaxe nova (adição, sem quebrar a Fase 01)

- `conteúdo:` = alias de `texto:` (a forma da Fase 01 continua valendo);
- `fonte: 24px` = tamanho da letra. Justificativa: `tamanho` na Fase 01
  significa dimensões da caixa (`tamanho: 200px 50px`); sobrecarregá-lo
  com `tamanho: 24px` seria ambíguo e imprevisível;
- vocabulário (ações/eventos/propriedades) deixou de ser palavra
  reservada: `botão abrir` (marco da fase) agora vale. Só palavras
  estruturais (`janela`, `quando`, `se`, `função`...) e tipos
  (`botão`, `texto`...) continuam reservadas.

## Limitações assumidas (provisórias, marcadas no código)

- Filhos sem `posição` são empilhados (layout real na Fase 03);
- sem alfa por pixel (hex de 8 dígitos reduzido a 6);
- rotação/escala guardadas na Cena, ainda não aplicadas a widgets;
- `imagem`/`vídeo`/`áudio` mostram placeholder (Fase 03).
