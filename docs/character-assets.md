# ELiXX — Character Assets (F41 asset runtime)

Runtime puro (sem Studio): imagem → asset → personagem
animável → animação → renderização. Prova real com janela e
pixels que mudam; headless via motor + CLI `--sem-janela`.

## Módulo

`elixx/visual/asset_personagem.py` (novo; resto reutilizado:
F07 tipos, F10 Transform, F11 motor, F12 Character, F16/F17
sintese, F21 Bounds2D, renderer Tk, CLI).

## AssetVisual

`AssetVisual(caminho, base_dir)` — caminho relativo contido
na base (traversal e absoluto externo recusados), extensões
png/gif/jpg/jpeg, teto 20MB, dimensões via stdlib (PNG IHDR,
GIF header, JPEG SOF) com Pillow só de reserva, leitura
tardia (`bytes()` só quando necessário). Nenhum asset executa
código: só `struct` sobre bytes.

## Personagem por pasta

`personagens/<nome>/` com `frente|tras|lado_direito|
lado_esquerdo.png`. `CharacterAsset.mapear()` (só arquivos
reais), aliases (`direita/esquerda/costas`), `diagnosticar()`
(`OK/AUSENTE` por vista, `COMPLETO/INCOMPLETO`).

Uma animação completa requer as 4 vistas. Incompleta carrega
para experimentos limitados. `usar_como(vista, arquivo)` é o
mapeamento experimental **explícito** (ex.: 1 imagem como
frente) — registrado em `experimental`, nunca fingido.

## Unidade visual

`criar_personagem_unidade` → `(NoVisual, Character F12,
CharacterRig metodo "unidade")`. UMA IMAGEM = unidade
animável: sem braços/olhos/pernas/boca independentes, sem
troca de perspectiva (declarado). Rig futuro (`bones_ik`)
recusado honestamente.

## Animações (F11 puro)

`animacao_respiracao` (escala 1→1.04, ping_pong infinito),
`animacao_inclinacao` (rotação ±45°), `animacao_deslocamento`
(posição). Sem scheduler novo: `MotorAnimacoes`.

Na linguagem (sem mudar o parser — já existia):

```elixx
personagem Juh {
 imagem: "assets/personagem_teste/personagem.png"
}
animacao respirar {
 alvo: Juh
 escala: 1 -> 1.05
 duracao: 1200ms
 movimento: suave
}
```

## Renderer (adaptador mínimo)

`abrir_palco(cena, base_dir, motor)`: RenderizadorTk com
recursos na pasta do projeto. Mudança F41 em `tk.py`: o tick
move o widget, mas escala/rotação exigem regenerar a foto —
agora `_aplicar_geometria` detecta mudança de transform e
regenera via `_foto_raster` existente (bytes em cache, sem
releitura; primeira aplicação não recarrega). Posição segue
sem reload.

## Executar

```
elixx executar exemplos/character-image-animation.elixx
elixx executar exemplos/character-image-animation.elixx --sem-janela
python exemplos/character-image-animation-demo.py --visual
python exemplos/character-image-animation-demo.py --sem-janela
```

Sem Studio, workspace, agent, LLM ou internet.

## Imagem de teste

`exemplos/assets/personagem_teste/personagem.png` (128×160,
figura estilizada gerada com stdlib `struct+zlib`, 615
bytes). Substitua por uma personagem real mantendo o nome.

## Limitações

1 imagem = unidade (sem segmentação); JPEG exige Pillow;
rotação de widgets segue inexistente no Tk (só a foto
gira); SVG fora do escopo; rig real/IA em fases futuras.
