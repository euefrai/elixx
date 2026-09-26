# ELiXX — Áudio (Fase 07)

```elixx
audio musica {
    arquivo: "assets/som.wav"
    volume: 90
}

botão tocar {
    quando clicar {
        reproduzir("musica")
    }
}
```

Ações: `reproduzir`, `pausar`, `continuar`, `parar`,
`volume("musica", 80)`. Mensagens aparecem no console e na barra.

Backend winsound (Windows, stdlib, assíncrono — sem travar a UI):

- formatos: só WAV (validado de verdade; MP3 é erro claro);
- `pausar` para e marca (continuar recomeça — limitação do backend);
- `volume` é guardado mas NÃO tem efeito no winsound (dito na saída);
- fora do Windows: erro claro em vez de silêncio.
