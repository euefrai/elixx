# ELiXX — Cliente HTTP (Fase 06, só stdlib)

`elixx/dados/http.py`: GET/POST/PUT/PATCH/DELETE via urllib, timeout
sempre (padrão 10s), headers, parâmetros com urlencode (nunca
concatenação manual), corpo JSON. Só `http://` e `https://`
(outros esquemas bloqueados).

Resposta nunca levanta para a UI — todo erro vira texto em português:
timeout ("Tempo esgotado"), DNS, conexão recusada, `HTTP NNN`, JSON
inválido, resposta vazia (2xx vazio = sucesso com `valor` nulo).

JSON é só dados (dict/list/str/float/bool/None do `json` stdlib).
UTF-8 com fallback do charset e `errors="replace"`. Nada remoto é
avaliado como código — testado.
