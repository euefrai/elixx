# ELiXX — linguagem visual em português (Fase 02: renderer nativo)

Requisito: Python >= 3.10 (usa só a biblioteca padrão; sem dependências).

```elixx
janela principal {
    titulo: "Minha primeira aplicação"
    tamanho: 800px 600px
    botão teste {
        texto: "Olá ELiXX"
        quando clicar {
            mostrar("Olá, mundo!")
        }
    }
}
```

## Instalação rápida (Windows)

```powershell
.\instalar.ps1
```

O instalador é idempotente: detecta o Python, confere a versão mínima,
usa as ferramentas locais (pip/setuptools, sem downloads se já
existirem), instala em modo editável, localiza o diretório de Scripts,
confere o PATH (só anexa se faltar, sem remover nada) e valida em um
novo processo PowerShell. Se o PATH precisar mudar, abra um novo
PowerShell para enxergar o comando.

## Uso

```powershell
elixx versao
elixx verificar exemplos/interface.elixx
elixx executar exemplos/interface.elixx   # abre janela nativa real
elixx executar exemplos/dashboard.elixx   # dados reais da máquina
elixx executar exemplos/grafico.elixx     # gráficos reativos
elixx executar exemplos/aplicacao-completa.elixx  # tema, telas, form
elixx executar exemplos/09_app_completa.elixx     # composição Fase 09
elixx executar app/principal.elixx                # app multimódulo real
```

## Desenvolvimento

```powershell
python -m pytest -q
```

Documentação em `docs/` (comece por `docs/01-visao-geral.md`;
Fase 09 em `docs/fase-09.md`).
Relatórios em `RELATORIO-FASE-*.md`.
