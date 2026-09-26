# RELATORIO — ELiXX FASE 07 (multimídia e gráficos)

## STATUS

Concluída: critério atendido com honestidade total (real onde dá,
abstração + documento onde o backend não alcança). Sem reescrita,
sem sistemas paralelos (Cena, Vinculador, Estado, FonteDados, Motor
de Animação e Renderer abstrato reutilizados).

## BASELINE ANTES

174 passed, 0 failed (confirmado por execução antes de alterar).

## BASELINE DEPOIS

199 passed, 0 failed (+25, determinísticos; áudio toca de verdade).

## IMAGENS

PNG/GIF nativos (PhotoImage), JPEG via Pillow OPCIONAL (erro claro sem
ela), `arquivo:` relativo ao `.elixx`, `ajuste: conter` real
(subsample) e exatos com Pillow, `reserva:` fallback, placeholder +
mensagem em erro. Remotas: download async com cache e reserva.

## SVG

Parser próprio do subconjunto (rect/circle/ellipse/line/polyline/
polygon/path M-L-H-V-Z/text; fill/stroke/opacity; viewBox) em
operações primitivas backend-agnósticas. `<script>`, `on*`, curvas e
desconhecidos ignorados com aviso — nunca executados. Erro PT.

## ÁUDIO

WAV real via winsound (async, validado com `wave`): reproduzir,
pausar, continuar, parar, volume. Limites ditos na saída e nos docs
(pausar para/marca, volume sem efeito, só Windows, só WAV).

## VÍDEO

Abstração honesta, sem player falso: componente, validação, estado,
ações que explicam o backend futuro; placeholder informativo;
`<video>` no HTML quando há arquivo. Avaliação de opções adiada
(documentada, sem escolha).

## GRÁFICOS

`grafico` estendido (não duplicado): `tipo: linha|barras|pizza|area`,
Canvas próprio com paleta, escala pelo máximo. Dois modos: série
(lista substitui, máx. 120) e histórico (número acumula 60, legado
CPU preservado). Reage via Vinculador existente, sem reconstruir.

## HISTÓRICO

`historico` (60, por nó) + `serie` (120) na Cena; exemplo tempo-real
usa a cadência de 1s existente, sem threads extras.

## RECURSOS REMOTOS / CACHE

URLs http(s) com timeout, thread daemon, volta à UI via
`programar(0, …)`; `CacheRecursos` com hits/misses; sem persistência.

## REATIVIDADE / ANIMAÇÃO

Gráficos/imagens participam de posição/tamanho/opacidade/visibilidade
do motor (testado o caminho; sem motor novo). `quando terminar`
funciona com mídia (ação real no callback).

## DASHBOARD

+logo PNG no menu, +ícone embutido, +histórico de CPU ao vivo.
Nativo saída 0; demais dados intactos.

## TESTES

25 novos: SVG (5), ícones (2), recursos (5), áudio (2), vídeo (1),
sintaxe (4), cena/listas (2), gráficos reativos (2), ações (3), HTML
(1). Bugs reais achados e corrigidos: loop infinito em path com curva,
`_pausar` duplicado sombreando mídia, op oval no índice errado,
`botão.icone` descartado por inviabilidade Tk (ícone é componente).

## TESTES VISUAIS

Sondas reais: PNG/SVG/reserva/ícones carregados; som tocado;
4 tipos desenhados e reagindo a clique ([10]→[10,30,25]); áudio com
6 operações; tempo-real e dashboard em janela (saída 0). M9 manual
para o usuário.

## EXEMPLOS

`imagem.elixx`, `audio.elixx`, `grafico.elixx`,
`grafico-tempo-real.elixx`, `multimidia.elixx` (+`assets/`: logo.png,
som.wav, salvar.svg). Todos verificados; 19/19 `.elixx` válidos
(teste de compatibilidade total).

## DOCUMENTAÇÃO

`multimidia.md`, `imagens.md`, `audio.md`, `video.md`, `graficos.md`,
`recursos.md` + sintaxe/manuais/roadmap/README (matriz nativo×HTML).

## DEPENDÊNCIAS

Zero novas obrigatórias. Pillow segue opcional (presente no ambiente,
nunca importada sem try). Critérios da §30 aplicados e registrados.

## LIMITAÇÕES

Vídeo sem reprodução; opacidade/escala de widgets como na Fase 03;
JPEG/esticar exigem Pillow; Bézier fora do SVG; `botão.icone` futuro;
cache só em memória; sem streaming de áudio.

## PRÓXIMA FASE

FASE 08 — interação e janelas. Parada aqui (regra: não iniciar Fase 08).
