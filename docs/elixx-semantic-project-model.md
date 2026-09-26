# F27 — ELiXX Semantic Project Model

> "O Modelo Semântico não substitui o AST."

> "O Modelo Semântico não executa o projeto."

Camada de **leitura e indexação** sobre o que o ELiXX já possui:
responde "o que existe?", "onde está definido?", "o que referencia
o quê?" — sem busca textual, sem IA, sem rede.

## Arquitetura

```text
ELiXX Code → Parser/AST (existente) → AdaptadorAST → ModeloSemantico
    → Indice/Consulta → Studio / Agent (opcional)
```

Pacote `elixx/studio/modelo/` (6 módulos): `modelo`, `indice`,
`consulta`, `adaptador`, `validacao`, `__init__`. Nenhum arquivo
F01–F26 foi modificado (integrações por adaptador; regra B).

## Entidades e relações

`EntidadeSemantica(id, tipo, nome?, arquivo?, linha?, dados?, tags?)`:
vocabulário fechado de 20 tipos (projeto, arquivo, tela, janela,
componente, personagem, parte, pose, expressao, animacao, asset...);
ID único (duplicata = erro, sem substituição); dados só JSON finito
(teto 100KB); serializável.

`RelacaoSemantica(origem, tipo, destino)`: 8 tipos descritivos
(contem, possui, usa_asset, atua_em, responde, depende_de, define,
referencia). Só entre entidades existentes (alvo ausente = relação
não criada, contada como ignorada — sem adivinhar).

## Índice e consultas

`IndiceSemantico`: por id/nome/tipo/arquivo e relações de/para;
reconstrução explícita (sem cache desatualizável). `ConsultaSemantica`:
`encontrar_por_nome/tipo/arquivo`, `relacoes_de/para`, `vizinhanca`.

## Adaptador AST (o coração honesto)

Caminha `Programa` com `isinstance` (janelas/telas → componentes →
`Personagem` em `componentes` → `Parte` recursiva → `PoseDef`;
`ComponenteDef`, `Funcao`, `AcaoDef`, `Import`, `EstadoDef`,
`FonteDef`, `Evento`, `AnimacaoDef`). Extrai só o que o AST fornece:
nomes, tipos, linhas, alvos, caminhos de import, assets de props
conhecidas (`imagem/src/som/...` + texto + extensão conhecida).
IDs determinísticos (`personagem:juh`, `parte:juh.corpo`,
`componente:p.entrar`). Alvo de animação vira `atua_em` só resolvido.

## Projeto e atualização

`analisar_projeto(raiz)`: `.elixx` → parser → modelo (parse nunca
executa; erro vira diagnóstico + status). `atualizar_arquivo`:
remove entidades do arquivo e re-analisa (sem watcher/hot reload).
Caminhos relativos contidos (traversal recusado); conteúdo completo
não fica em memória (só hash).

## Integrações (todas opcionais, sem tocar F25/F26)

- **Personagem/animação/assets**: partes/poses/expressões com
  `possui`; animação com `atua_em` resolvido; asset com `usa_asset`
  (texto solto nunca vira asset). Sem duplicar Character/Rig/Motion.
- **Studio**: `resumo_para_inspetor` (entidade + origem + relações).
- **Agent**: `modelo_para_contexto` (entidades como símbolos, com
  teto; Agent funciona sem modelo).
- **ChangeSet**: `MutacaoSemantica` + `mutacao_para_changeset`
  (ChangeSet **proposto**; aplicação exige aprovação F26).

## Snapshot e validação

`SnapshotSemantico` (entidades/relações/arquivos/versão, imutável) +
`comparar_snapshots` (adicionados/removidos/alterados). `validar_modelo`:
refs existentes, paths contidos, dados válidos (regras com evidência).

## Segurança e performance

Traversal/absolutos recusados; strings maliciosas inertes; JSON
inválido/duplicadas/payloads/recursão bloqueados; sem `eval/exec/
importlib/__import__/pickle/subprocess` (scan no pacote). Medido:
100/500/1000 arquivos e 100/1000/5000 entidades < 60s.

## Limitações honestas

Sem LLM/NLU/visão/planejamento/geração/cloud/plugins/3D; sem fuzzy,
embeddings ou banco vetorial; `Instancia` e corpos de função/ação não
viram entidades (sem modelo novo — documentado); import não resolvido
não vira relação; sem watcher, file events ou UI semântica.

## Testes

`testes/test_fase27.py`: 60 testes (entidade→regressão). Demo:
`exemplos/semantic-model-demo.py` (14 passos, headless).
