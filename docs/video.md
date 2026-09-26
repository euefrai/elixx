# ELiXX — Vídeo (Fase 07, abstração honesta)

Tkinter + stdlib não decodificam vídeo moderno. Em vez de um player
falso, a linguagem oferece componente, validação e estado hoje, e
reserva o backend para depois:

```elixx
video demo {
    arquivo: "assets/video.mp4"
}
```

`reproduzir("demo")` valida e responde que a reprodução chega com
backend dedicado. O renderer mostra placeholder informativo; o HTML
gera `<video controls>` quando há arquivo.

Avaliação futura (sem escolha nesta fase): porte de lib nativa
(tamanho/licença/Windows/distribuição), invocação de player externo
ou backend opcional por plugin. Critérios na Fase 10 (empacotamento).
