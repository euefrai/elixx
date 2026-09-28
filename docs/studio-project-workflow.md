# ELiXX Studio — Project Workflow (F41)

Fluxo IDE sobre a arquitetura existente: CRIAR → ABRIR →
EDITAR → SALVAR → EXECUTAR → VISUALIZAR → SELECIONAR →
MODIFICAR → PROPOR → APROVAR → SINCRONIZAR → CONTINUAR.
Módulo: `elixx/studio/projeto_workspace.py` (headless; reusa
Workspace/ArvoreArquivos/Documentos/Projeto/StudioWorkspace).

## Projeto

`novo_projeto(workspace, nome, destino, template)`:
templates vazio/aplicacao/cena/personagem/minimo, todos com
`main.elixx` mínimo e válido (parser oficial). Nome sem
separadores/controle; template validado no parser.

`abrir_projeto_validado`: diretório + leitura + config
válida; lista arquivos (até 5000); nunca executa código.
`fechar_projeto`: para preview, limpa editores/modelo, fecha
base. `recarregar_projeto`: relê disco + reanalisa.

Configuração: `projeto.elixxproj` existente (nome, versão,
entrada, descrição); nenhum formato novo.

## Recentes

`Recentes`: nome + caminho (até 20); JSON explícito; nunca
tokens/senhas (recusados); remover não apaga o projeto.

## Tree real

`ArvoreProjetoReal`: filesystem via `ArvoreArquivos`
(recursivo, limite 5000/pasta); `▾/▸` pastas, `◆` elixx,
`▤` imagem, `♪` áudio, `•` demais; `●` dirty, `→` ativo;
expandir/recolher/selecionar; nada inventado.

## Arquivos

Criar/renomear/excluir (com confirmação)/criar pasta via
`ArvoreArquivos`; `duplicar_arquivo` (`" - copia"`, 5MB);
ELiXX novo usa sintaxe válida real. Exclusão exige
`confirmar=True`; sem lixeira, sem shell.

## Editor

Abas sobre `GerenciadorDocumentos` (`AbasAvancadas`):
próxima/anterior (Ctrl+Tab), fechar_outras/todas (recusam
com dirty), salvar_todas. Dirty via `DocumentoELiXX`;
`descartar_alteracoes` restaura do disco. Diagnósticos do
parser oficial, sem traceback, `ir_para(linha)` clicável.

Salvar: validar → salvar → reanalisar → preview →
limpar dirty; erro de sintaxe preserva conteúdo e editor.

## Execução

`executar_projeto`: VALIDANDO → EXECUTANDO → CONCLUIDO /
ERRO (mensagem curta); `parar_execucao`: PARADO + preview
parado (sem processo externo na arquitetura). Estados
reais, sem fingir.

## Palette / teclado

`COMANDOS_F41` (23, lista própria; F37/F39/F40 intactas)
despachando para funções reais. Novos globais: Ctrl+N,
Ctrl+Shift+N, Ctrl+W, Ctrl+Tab, Ctrl+H. Conflitos
documentados em `CONFLITOS_F41` (Ctrl+O/S/P/F/G, F5…).

## Semântico / Agent

Arquivo → `estado_arquivo` (caminho, tamanho ≤5MB,
dirty, entidades F27). Entidade → ficha/inspector existentes.
Visual → proposta → ChangeSet → aprovação → F32; nada
escreve direto. Agent recebe projeto/arquivo/seleção via
estruturas (sem projeto inteiro).

## Estado / recovery / DnD

`estado_projeto`: snapshot de leitura (paths, abas, dirty,
seleção, preview, agente, diagnósticos, execução) — sem
segunda fonte. `Fotografia`: mtime+tamanho; externas geram
"alterado fora" com Recarregar/Manter (via
`descartar_alteracoes`). `interpretar_arrastar`: valida e
devolve operação proposta (sem mover).

## Welcome / vazios / Tk

`BoasVindas` (só sem projeto): Novo/Abrir/Recentes/
templates. Tk: menu contextual no Project (ações reais),
diálogo de boas-vindas, bindings Ctrl+N/W/Tab. Empty states
existentes mantidos.

## Segurança / performance

Sem eval/exec/importlib/pickle/subprocess/shell; traversal
e absoluto recusados; nomes com controle/NUL recusados;
limites 100 chars (nome), 5MB (arquivo), 5000 (lista).
Conteúdo nunca tratado como Python. 100/500/1000 arquivos,
1k/5k/10k entidades, 10/100/500KB; fotografia incremental.

## Limitações

Sem lixeira; sem watcher automático (fotografia manual);
substituir/ir-para-linha via palette sem UI dedicada;
Ctrl+H foca editor no Tk; drag-and-drop só propõe;
projetos recentes sem caminho salvo global (caminho por
chamador).
