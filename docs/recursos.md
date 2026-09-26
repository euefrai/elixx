# ELiXX — Recursos: arquivos, URLs e cache (Fase 07)

- `arquivo:` ancora na pasta do `.elixx` (previsível; use `/`).
- Remoto só `http(s)`; download em thread daemon com timeout;
  `pronto(bytes)` volta à thread da UI via `programar(0, ...)`.
- `CacheRecursos`: mesma URL/arquivo duas vezes não recarrega
  (estatísticas `hits`/`misses` para testes). Sem persistência ainda.
- Segurança: bytes são dados; SVG passa por parser que ignora script,
  eventos e referências; JSON nunca vira código (Fase 06).
- Erros em português com sugestão; placeholder visual + barra em vez
  de exceção na cara do usuário.
