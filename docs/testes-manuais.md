# ELiXX — Testes manuais (Fase 02)

Estes testes exigem olho humano numa janela real. Eles NUNCA são marcados
como automaticamente aprovados: rode, observe e marque à mão.

## M11 — Composição Fase 09 (validado por sonda automática; confirme visual)

```bash
elixx executar exemplos/01_estado_local.elixx
elixx executar exemplos/03_lista_dinamica.elixx
elixx executar exemplos/05_acoes.elixx
elixx executar app/principal.elixx
```

- [ ] dois contadores independentes (+1 em um não mexe no outro)
- [ ] lista mostra Ana/Beto; "Adicionar Carlos" insere terceira linha
- [ ] ações +1 / Escolher 7 / Zerar atualizam os textos
- [ ] app: 3 cards; favoritar A e C (B segue desmarcado); excluir no
      card do meio registra o id certo; remover item some a linha

## M1 — Janela do marco

```bash
elixx executar exemplos/interface.elixx
```

- [ ] abre janela intitulada "Minha primeira aplicação ELiXX"
- [ ] janela tem ~800x500
- [ ] botão "Abrir" visível
- [ ] clicar no botão mostra "Olá, ELiXX!" na barra inferior
- [ ] fechar a janela (X) encerra sem erro no console

## M2 — Interface completa

```bash
elixx executar exemplos/interface-completa.elixx
```

- [ ] texto "Olá, ELiXX" grande e azul em (100, 60)
- [ ] passar o cursor no "Abrir" mostra mensagem de hover
- [ ] clicar "Abrir" mostra "Olá, ELiXX!"
- [ ] clicar "Fechar" esconde o próprio botão e mostra mensagem
- [ ] fundo da janela branco

## M10 — Aplicações (validado automaticamente nesta sessão; confirme visual)

```bash
elixx executar exemplos/componentes.elixx
elixx executar exemplos/temas.elixx
elixx executar exemplos/formulario.elixx
elixx executar exemplos/navegacao.elixx
elixx executar exemplos/aplicacao-completa.elixx
```

- [ ] dois cartões independentes (Ana com email, Beto com padrão)
- [ ] temas trocam cores/fontes sem reconstruir
- [ ] formulário inválido mostra erros; válido libera
- [ ] telas alternam, voltar respeita a pilha, modal abre/fecha
- [ ] abas, tabela com 3 linhas, menu clicável
- [ ] `python exemplos/servidor_demo.py` + `elixx executar exemplos/crud.elixx`: lista, criar, editar, excluir com modal

## M9 — Multimídia (validado automaticamente nesta sessão; confirme visual)

```bash
elixx executar exemplos/imagem.elixx
elixx executar exemplos/audio.elixx
elixx executar exemplos/grafico.elixx
elixx executar exemplos/grafico-tempo-real.elixx
elixx executar exemplos/multimidia.elixx
```

- [ ] logo PNG + SVG + 2 ícones; quebrada mostra a reserva
- [ ] Tocar/Pausar/Continuar/Parar com som real; volume mostra aviso honesto
- [ ] 4 gráficos mudam juntos ao clicar nas semanas
- [ ] tempo-real: linha da CPU cresce sozinha
- [ ] galeria: tudo acima + vídeo com placeholder futuro

## M8 — APIs (validado automaticamente nesta sessão; confirme visual)

```bash
python exemplos/servidor_demo.py
elixx executar exemplos/lista-api.elixx
elixx executar exemplos/formulario-api.elixx
elixx executar exemplos/dados.elixx
```

- [ ] lista mostra Ana/Beto vindos da API; Recarregar rebusca
- [ ] formulário: preencher, Enviar, resposta com id 3
- [ ] dados: avisos do JSON local na lista
- [ ] com servidor desligado: erro em texto, app continua aberta

## M7 — Estado (validado automaticamente nesta sessão; confirme visual)

```bash
elixx executar exemplos/estado.elixx
elixx executar exemplos/reatividade.elixx
```

- [ ] contador nasce em 0; +1/-1/x2/zerar atualizam na hora
- [ ] digitar no campo reflete no texto azul; checkbox alterna a bolinha
- [ ] total (pontos × preço) recalcula ao somar ponto
- [ ] reatividade: +5 move os dois textos, a barra e o derivado juntos
- [ ] sem travamento após cliques rápidos

## M6 — Layout (validado automaticamente nesta sessão; confirme visual)

```bash
elixx executar exemplos/layout.elixx
```

- [ ] coluna empilha sem posição manual; linha alinha 3 botões
- [ ] grade monta 2 colunas de cartões
- [ ] entrada/checkbox/seleção interativos; indicador mostra a rede
- [ ] redimensionar a janela rearranja sem quebrar

## M5 — Animação (validada automaticamente nesta sessão; confirme visual)

```bash
elixx executar exemplos/animacao.elixx
```

- [ ] cartão desliza sozinho de baixo para cima (suave)
- [ ] clicar "Quicar" quica o botão 2x e ele volta (sequência + "quicou!")
- [ ] "Sumir" esconde o texto com "sumiu!"
- [ ] "Fantasma" deixa a JANELA translúcida; "Restaurar" volta ao normal

## M4 — Dashboard (validado automaticamente nesta sessão; confirme visual)

```bash
elixx executar exemplos/dashboard.elixx
```

- [ ] janela escura "ELiXX System Dashboard" 1100x700 com sidebar
- [ ] CPU/RAM/SSD com % reais e barras preenchidas; gráfico com linha
- [ ] relógio atualizando a cada segundo; processos/rede com valores
- [ ] sidebar alterna as 4 páginas; Sair fecha
- [ ] Atualizar força leitura; Auto ON/OFF pausa/retoma

## M3 — Regressão Headless/HTML

```bash
elixx verificar exemplos/programa.elixx
elixx executar exemplos/programa.elixx --sem-janela --clicar teste
elixx compilar exemplos/interface.elixx
```

- [ ] verificar diz OK
- [ ] simulado imprime "Olá, mundo!"
- [ ] HTML gerado contém o botão com alert
