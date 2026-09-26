# ELiXX — Multimídia (Fase 07)

Camada `elixx/multimidia/` sem renderer: recursos (caminhos, bytes,
cache), SVG seguro, ícones embutidos, áudio (winsound), vídeo
(abstração honesta). Tk e HTML consomem daqui.

Matriz honesta (o que é real × onde):

| Recurso | Nativo (Tk) | HTML |
|---|---|---|
| PNG/GIF local | real | `<img>` real |
| JPEG | real com Pillow opcional; erro claro sem ela | `<img>` real |
| SVG arquivo/ícone | real (subconjunto) | ícone: só nativo; SVG: `<img>` se arquivo |
| Imagem remota | real (async + cache + reserva) | `<img src>` real |
| Áudio WAV | real (winsound) | `<audio>` real |
| Vídeo | abstração (placeholder) | `<video>` se arquivo |
| Gráficos 4 tipos | real (Canvas próprio) | placeholder honesto |

Sem Pillow instalada: PNG/GIF funcionam; JPEG explica como instalar.
Nada daqui é dependência obrigatória.
