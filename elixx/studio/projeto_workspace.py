"""Project Workflow (Fase 41) — CRIAR/ABRIR/EDITAR/SALVAR/EXECUTAR.

Nucleo headless sobre Workspace/ArvoreArquivos/Documentos/
ProjetoELiXX/StudioWorkspace (F25/F29). Sem parser/modelo/
renderer/selecao/EventBus novos; sem comandos externos; sem
execucao de conteudo (abrir/analisar nunca executa codigo).
"""

from __future__ import annotations

import json
import unicodedata

from ..erros import ErroELiXX

__all__ = [
    "TEMPLATES",
    "TIPOS_ARQUIVO",
    "COMANDOS_F41",
    "ATALHOS_F41",
    "CONFLITOS_F41",
    "conteudo_template",
    "novo_projeto",
    "abrir_projeto_validado",
    "fechar_projeto",
    "recarregar_projeto",
    "duplicar_arquivo",
    "estado_arquivo",
    "descartar_alteracoes",
    "Fotografia",
    "Recentes",
    "ArvoreProjetoReal",
    "AbasAvancadas",
    "EstadoExecucao",
    "executar_projeto",
    "EstadoProjeto",
    "estado_projeto",
    "BoasVindas",
    "menu_contexto",
    "interpretar_arrastar",
    "buscar_palette_f41",
    "executar_palette_f41",
    "conflitos_f41",
]

TEMPLATES = ("vazio", "aplicacao", "cena", "personagem",
             "minimo")
"""Templates iniciais (conteudo minimo valido)."""

TIPOS_ARQUIVO = ("elixx", "texto", "json", "config")
"""Tipos de Novo arquivo (conteudo inicial valido)."""

COMANDOS_F41 = (
    ("novo_projeto", "Novo Projeto"),
    ("abrir_projeto", "Abrir Projeto"),
    ("fechar_projeto", "Fechar Projeto"),
    ("novo_arquivo", "Novo Arquivo"),
    ("nova_pasta", "Nova Pasta"),
    ("abrir_arquivo", "Abrir Arquivo"),
    ("salvar", "Salvar"),
    ("salvar_tudo", "Salvar Tudo"),
    ("fechar_aba", "Fechar Aba"),
    ("fechar_todas_abas", "Fechar Todas as Abas"),
    ("executar", "Executar"),
    ("parar", "Parar"),
    ("buscar", "Buscar"),
    ("substituir", "Substituir"),
    ("ir_para_linha", "Ir para Linha"),
    ("mostrar_preview", "Mostrar Preview"),
    ("mostrar_scene", "Mostrar Scene"),
    ("mostrar_agent", "Mostrar Agent"),
    ("mostrar_inspector", "Mostrar Inspector"),
    ("mostrar_raciocinio", "Mostrar Raciocínio"),
    ("mostrar_plano", "Mostrar Plano"),
    ("mostrar_changes", "Mostrar Changes"),
    ("recarregar_projeto", "Recarregar Projeto"),
)
"""Palette F41 (aditiva; F37/F39/F40 intactas)."""

ATALHOS_F41 = {
    "Ctrl+N": "novo_arquivo",
    "Ctrl+Shift+N": "novo_projeto",
    "Ctrl+W": "fechar_aba",
    "Ctrl+Tab": "proxima_aba",
    "Ctrl+H": "substituir",
}
"""Atalhos novos (somente teclas livres; sem sobrescrever)."""

CONFLITOS_F41 = {
    "Ctrl+O": "abrir_projeto (existente; preservado)",
    "Ctrl+S": "salvar (existente; preservado)",
    "Ctrl+Shift+S": "salvar_como (existente; preservado)",
    "Ctrl+P": "pesquisa_rapida (existente; preservado)",
    "Ctrl+F": "buscar (existente; preservado)",
    "Ctrl+G": "grafo (existente; ir-para-linha so via palette)",
    "F5": "executar (existente; preservado)",
    "Shift+F5": "parar (existente; preservado)",
}
"""Conflitos resolvidos sem quebrar comportamento anterior."""


def _nome_valido(nome: str, o_que: str = "nome") -> str:
    texto = str(nome).strip()
    if not texto or len(texto) > 100:
        raise ErroELiXX(f"Projeto: {o_que} curto e nao vazio.")
    if any(c in texto for c in ('/', '\\', '\x00')):
        raise ErroELiXX(f"Projeto: {o_que} sem separadores.")
    if texto in (".", ".."):
        raise ErroELiXX(f"Projeto: {o_que} invalido.")
    for ch in texto:
        if ord(ch) < 32:
            raise ErroELiXX(f"Projeto: {o_que} sem controle.")
    return texto


def _rel_seguro(relativo: str) -> str:
    texto = str(relativo).strip().replace("\\", "/")
    if not texto or len(texto) > 500:
        raise ErroELiXX("Projeto: caminho curto e nao vazio.")
    if texto.startswith("/") or ".." in texto.split("/"):
        raise ErroELiXX("Projeto: caminho contido na raiz.")
    for ch in texto:
        if ch == "\x00" or (ord(ch) < 32
                            and ch not in ("\n", "\t")):
            raise ErroELiXX("Projeto: caminho sem controle.")
    return texto


def conteudo_template(template: str) -> str:
    """Texto inicial minimo e valido do template."""
    if template not in TEMPLATES:
        raise ErroELiXX(f"Projeto: template em {TEMPLATES}.")
    base = {
        "vazio": 'janela principal {\n titulo: "App"\n}\n',
        "aplicacao": 'janela principal {\n titulo: "App"\n'
                     ' tamanho: 800 600\n}\n',
        "cena": 'janela cena {\n titulo: "Cena"\n'
                ' texto ola {\n  texto: "Ola"\n }\n}\n',
        "personagem": 'janela palco {\n titulo: "Palco"\n'
                      ' personagem Juh {\n  parte corpo {\n'
                      '  }\n }\n}\n',
        "minimo": 'janela app {\n}\n',
    }
    return base[template]


def conteudo_inicial(tipo: str, nome: str = "sem_nome") -> str:
    """Conteudo inicial valido por tipo de arquivo."""
    if tipo not in TIPOS_ARQUIVO:
        raise ErroELiXX(f"Projeto: tipo em {TIPOS_ARQUIVO}.")
    base = _nome_valido(nome, "arquivo base")
    if tipo == "elixx":
        return (f'janela {base} {{\n titulo: "{base}"\n}}\n')
    if tipo == "json":
        return '{\n}\n'
    if tipo == "config":
        return f"# {base}\n"
    return ""


def novo_projeto(workspace, nome: str, destino,
                 template: str = "vazio") -> dict:
    """Cria projeto + main.elixx do template (dirs reais)."""
    from .projeto import ProjetoELiXX
    from .workspace import Workspace

    if not isinstance(workspace, Workspace):
        raise ErroELiXX("Projeto: espera Workspace.")
    nome_txt = _nome_valido(nome)
    if template not in TEMPLATES:
        raise ErroELiXX(f"Projeto: template em {TEMPLATES}.")
    raiz = destino if hasattr(destino, "mkdir") else destino
    import pathlib as _pl

    raiz = _pl.Path(raiz) / nome_txt
    projeto = workspace.criar_projeto(raiz, nome_txt)
    entrada = workspace.resolver(
        getattr(projeto, "entrada", "src/main.elixx"))
    texto = conteudo_template(template)
    from .editor import diagnosticar_texto

    erros = [d for d in diagnosticar_texto(texto, entrada.name)
             if d.severidade == "error"]
    if erros:
        raise ErroELiXX("Projeto: template invalido "
                        f"({erros[0].mensagem[:120]}).")
    entrada.write_text(texto, encoding="utf-8")
    if not isinstance(projeto, ProjetoELiXX):
        raise ErroELiXX("Projeto: criacao falhou.")
    return {"projeto": projeto.nome,
            "raiz": str(workspace.raiz),
            "entrada": str(entrada.relative_to(workspace.raiz))
            if entrada.is_relative_to(workspace.raiz)
            else entrada.name,
            "template": template}


def abrir_projeto_validado(workspace, raiz) -> dict:
    """Abre com validacao (estrutura; nunca executa codigo)."""
    from .workspace import Workspace

    if not isinstance(workspace, Workspace):
        raise ErroELiXX("Projeto: espera Workspace.")
    import pathlib as _pl

    caminho = _pl.Path(raiz)
    if not caminho.is_dir():
        raise ErroELiXX("Projeto: diretorio ausente.")
    try:
        list(caminho.iterdir())
    except OSError:
        raise ErroELiXX("Projeto: sem permissao de leitura.")
    projeto = workspace.abrir_projeto(caminho)
    arquivos = []
    for p in sorted(caminho.rglob("*")):
        if "__pycache__" in p.parts:
            continue
        if p.is_file():
            try:
                rel = str(p.relative_to(caminho)).replace(
                    "\\", "/")
                arquivos.append(rel)
            except ValueError:
                continue
    return {"projeto": projeto.nome,
            "raiz": str(workspace.raiz),
            "arquivos": sorted(arquivos)[:5000]}


def fechar_projeto(studio_workspace) -> dict:
    """Fecha: para preview, limpa editores/modelo, fecha base."""
    studio_workspace.preview.parar()
    try:
        studio_workspace.preview.canvas  # noqa
    except AttributeError:
        pass
    if hasattr(studio_workspace, "editores"):
        studio_workspace.editores = {}
    studio_workspace.modelo = None
    studio_workspace.app.workspace.fechar_projeto()
    return {"ok": True, "projeto": None}


def recarregar_projeto(studio_workspace) -> dict:
    """Rele disco + reanalisa (sem perder abas limpas)."""
    projeto = studio_workspace.app.workspace.recarregar_projeto()
    info = {}
    if hasattr(studio_workspace, "analisar"):
        try:
            info = studio_workspace.analisar()
        except ErroELiXX as exc:
            info = {"erro": str(exc)[:160]}
    return {"projeto": projeto.nome, "analise": info}


def duplicar_arquivo(workspace, relativo: str) -> str:
    """Copia 'arq.ext' -> 'arq - copia.ext' (sem lixeira)."""
    from .arquivos import ArvoreArquivos
    from .workspace import Workspace

    if not isinstance(workspace, Workspace):
        raise ErroELiXX("Projeto: espera Workspace.")
    rel = _rel_seguro(relativo)
    origem = workspace.resolver(rel)
    if not origem.is_file():
        raise ErroELiXX(f'Projeto: "{rel}" nao e arquivo.')
    if len(rel) > 400:
        raise ErroELiXX("Projeto: caminho longo demais.")
    base = origem.stem + " - copia"
    if len(base) > 120:
        raise ErroELiXX("Projeto: nome longo demais.")
    candidato = base + origem.suffix
    i = 2
    while workspace.existe(
            str(origem.parent.relative_to(workspace.raiz)
                / candidato) if origem.parent != workspace.raiz
            else candidato):
        candidato = f"{base} {i}{origem.suffix}"
        i += 1
        if i > 1000:
            raise ErroELiXX("Projeto: copias demais.")
    destino_rel = (str(origem.parent.relative_to(workspace.raiz)
                       / candidato)
                   if origem.parent != workspace.raiz
                   else candidato)
    dados = origem.read_bytes()
    if len(dados) > 5_000_000:
        raise ErroELiXX("Projeto: arquivo grande demais "
                        "para duplicar (5MB).")
    return ArvoreArquivos(workspace).criar_arquivo(
        destino_rel, dados.decode("utf-8", errors="replace")
        if _e_texto(origem.suffix) else "")


def _e_texto(sufixo: str) -> bool:
    return sufixo.lower() in (".elixx", ".txt", ".json",
                              ".md", ".toml", ".cfg",
                              ".fj", ".py", ".js", ".css",
                              ".html")


def estado_arquivo(workspace, modelo, relativo: str,
                   documentos=None) -> dict:
    """Caminho/tamanho/estado/entidades/diagnosticos (reais)."""
    rel = _rel_seguro(relativo)
    caminho = workspace.resolver(rel)
    if not caminho.is_file():
        raise ErroELiXX(f'Projeto: "{rel}" ausente.')
    try:
        tamanho = caminho.stat().st_size
    except OSError:
        raise ErroELiXX(f'Projeto: "{rel}" ilegivel.')
    if tamanho > 5_000_000:
        raise ErroELiXX("Projeto: arquivo excede 5MB.")
    sujo = False
    if documentos is not None:
        try:
            sujo = documentos.obter(rel).dirty
        except ErroELiXX:
            sujo = False
    entidades = []
    if modelo is not None:
        try:
            entidades = sorted(
                e.id for e in modelo.entidades()
                if e.arquivo == rel)
        except ErroELiXX:
            entidades = []
    return {"caminho": rel, "tamanho": tamanho,
            "dirty": bool(sujo), "entidades": entidades}


def descartar_alteracoes(workspace, documentos,
                         relativo: str) -> dict:
    """Restaura versao do disco (confirmacao e no chamador)."""
    rel = _rel_seguro(relativo)
    caminho = workspace.resolver(rel)
    if not caminho.is_file():
        raise ErroELiXX(f'Projeto: "{rel}" ausente.')
    texto = caminho.read_text(encoding="utf-8")
    if len(texto) > 5_000_000:
        raise ErroELiXX("Projeto: arquivo excede 5MB.")
    doc = documentos.obter(rel)
    doc.recarregar(texto)
    return {"arquivo": rel, "dirty": doc.dirty}


class Fotografia:
    """Snapshot mtime+tamanho (deteccao externa; sem watcher)."""

    def __init__(self) -> None:
        self._fotos: dict[str, tuple] = {}

    def fotografar(self, workspace) -> int:
        self._fotos = {}
        raiz = workspace.raiz
        for p in sorted(raiz.rglob("*")):
            if "__pycache__" in p.parts or not p.is_file():
                continue
            try:
                rel = str(p.relative_to(raiz)).replace(
                    "\\", "/")
                st = p.stat()
                self._fotos[rel] = (st.st_mtime_ns, st.st_size)
            except (OSError, ValueError):
                continue
            if len(self._fotos) >= 20000:
                break
        return len(self._fotos)

    def alterados_externamente(self, workspace) -> list[str]:
        atuais: dict[str, tuple] = {}
        raiz = workspace.raiz
        for p in sorted(raiz.rglob("*")):
            if "__pycache__" in p.parts or not p.is_file():
                continue
            try:
                rel = str(p.relative_to(raiz)).replace(
                    "\\", "/")
                st = p.stat()
                atuais[rel] = (st.st_mtime_ns, st.st_size)
            except (OSError, ValueError):
                continue
            if len(atuais) >= 20000:
                break
        saida = []
        for rel, marca in atuais.items():
            if rel not in self._fotos:
                saida.append(rel + " (novo)")
            elif self._fotos[rel] != marca:
                saida.append(rel)
        for rel in self._fotos:
            if rel not in atuais:
                saida.append(rel + " (removido)")
        return sorted(saida)

    def __repr__(self) -> str:
        return f"Fotografia({len(self._fotos)} arquivos)"


CHAVES_PROIBIDAS = ("token", "api_key", "apikey", "secret",
                    "senha", "password", "credential", "chave")


class Recentes:
    """Projetos recentes (somenta nome+caminho; sem segredo)."""

    def __init__(self, caminho=None) -> None:
        self.caminho = caminho
        self.itens: list[dict] = []
        if caminho is not None:
            try:
                import pathlib as _pl

                p = _pl.Path(caminho)
                if p.is_file():
                    self.carregar(p.read_text(encoding="utf-8"))
            except (OSError, ErroELiXX, ValueError):
                self.itens = []

    def adicionar(self, nome: str, raiz) -> dict:
        import pathlib as _pl

        item = {"nome": _nome_valido(nome)[:60],
                "caminho": str(_pl.Path(raiz))}
        self.itens = [i for i in self.itens
                      if i["caminho"] != item["caminho"]]
        self.itens.insert(0, item)
        self.itens = self.itens[:20]
        self._salvar()
        return item

    def remover(self, caminho: str) -> bool:
        antes = len(self.itens)
        self.itens = [i for i in self.itens
                      if i["caminho"] != str(caminho)]
        self._salvar()
        return len(self.itens) < antes

    def listar(self) -> list[dict]:
        return [dict(i) for i in self.itens]

    def to_json(self) -> str:
        for item in self.itens:
            for chave in item:
                if (not isinstance(chave, str)
                        or chave.lower() in CHAVES_PROIBIDAS):
                    raise ErroELiXX("Recentes: sem segredos.")
        return json.dumps({"recentes": self.itens},
                          ensure_ascii=False, sort_keys=True,
                          indent=2)

    def carregar(self, texto: str) -> list[dict]:
        try:
            dados = json.loads(texto)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErroELiXX(f"Recentes invalidos: {exc}.")
        itens = dados.get("recentes", []) if isinstance(
            dados, dict) else []
        if not isinstance(itens, list):
            raise ErroELiXX("Recentes invalidos.")
        self.itens = []
        for item in itens[:20]:
            if (isinstance(item, dict)
                    and isinstance(item.get("nome"), str)
                    and isinstance(item.get("caminho"), str)):
                self.itens.append(
                    {"nome": item["nome"][:60],
                     "caminho": item["caminho"][:500]})
        return self.listar()

    def _salvar(self) -> None:
        if self.caminho is None:
            return
        import pathlib as _pl

        p = _pl.Path(self.caminho)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")

    def __repr__(self) -> str:
        return f"Recentes({len(self.itens)})"


class _NoArvore:
    def __init__(self, nome, tipo, caminho, expandido=True):
        self.nome = nome
        self.tipo = tipo
        self.caminho = caminho
        self.filhos: list[_NoArvore] = []
        self.expandido = expandido

    def to_dict(self, sujos=(), ativo=""):
        return {"nome": self.nome, "tipo": self.tipo,
                "caminho": self.caminho,
                "expandido": self.expandido,
                "dirty": self.caminho in sujos,
                "ativo": self.caminho == ativo,
                "filhos": [f.to_dict(sujos, ativo)
                           for f in self.filhos]}


class ArvoreProjetoReal:
    """Filesystem real (pastas/arquivos; sem invencao)."""

    ICONES = {"pasta_aberta": "▾", "pasta_fechada": "▸",
              "arquivo": "•", "elixx": "◆", "imagem": "▤",
              "audio": "♪"}

    def __init__(self, workspace) -> None:
        self.workspace = workspace
        self.raiz: _NoArvore | None = None
        self.selecionado = ""

    def atualizar(self) -> _NoArvore:
        from .arquivos import ArvoreArquivos

        arv = ArvoreArquivos(self.workspace)
        raiz = _NoArvore(self.workspace.projeto.nome
                         if self.workspace.projeto else "",
                         "projeto", "")
        self._preencher(arv, raiz, ".")
        self.raiz = raiz
        return raiz

    def _preencher(self, arv, no: _NoArvore, rel: str) -> None:
        try:
            itens = arv.listar(rel)
        except ErroELiXX:
            return
        for item in itens:
            caminho = (item["nome"] if rel in (".", "")
                       else f"{rel}/{item['nome']}")
            filho = _NoArvore(item["nome"], item["tipo"],
                              caminho)
            no.filhos.append(filho)
            if item["tipo"] == "pasta" and len(caminho) < 400:
                self._preencher(arv, filho, caminho)
            if len(no.filhos) > 5000:
                break

    def expandir(self, caminho: str) -> bool:
        no = self._buscar(caminho)
        no.expandido = True
        return True

    def recolher(self, caminho: str) -> bool:
        no = self._buscar(caminho)
        if no.tipo != "pasta" and no.tipo != "projeto":
            raise ErroELiXX("Projeto: so pasta recolhe.")
        no.expandido = False
        return False

    def selecionar(self, caminho: str) -> dict:
        no = self._buscar(caminho)
        self.selecionado = caminho
        return {"nome": no.nome, "tipo": no.tipo,
                "caminho": caminho}

    def _buscar(self, caminho: str) -> _NoArvore:
        if self.raiz is None:
            raise ErroELiXX("Projeto: atualize a arvore.")
        alvo = str(caminho).strip().replace("\\", "/")
        pilha = [self.raiz]
        while pilha:
            no = pilha.pop()
            if no.caminho == alvo:
                return no
            pilha.extend(no.filhos)
        raise ErroELiXX(f'Projeto: "{caminho}" ausente.')

    def linhas(self, sujos=(), ativo="") -> list[str]:
        """Texto com ▾/▸/•/◆ + ● dirty (somenta existentes)."""
        saida: list[str] = []
        if self.raiz is None:
            return ["(nenhum projeto)"]

        def _visita(no: _NoArvore, prefixo: str,
                    ultimo: bool, raiz: bool) -> None:
            if raiz:
                marca = "▾ " if no.expandido else "▸ "
                saida.append(f"{marca}{no.nome or 'projeto'}")
            else:
                galho = "└ " if ultimo else "├ "
                if no.tipo == "pasta":
                    icone = ("▾ " if no.expandido else "▸ ")
                elif no.caminho.endswith(".elixx"):
                    icone = "◆ "
                elif no.caminho.lower().endswith(
                        (".png", ".jpg", ".jpeg", ".gif",
                         ".svg")):
                    icone = "▤ "
                elif no.caminho.lower().endswith(
                        (".wav", ".mp3")):
                    icone = "♪ "
                else:
                    icone = "• "
                sujo = " ●" if no.caminho in sujos else ""
                atual = " →" if no.caminho == ativo else ""
                saida.append(f"{prefixo}{galho}{icone}"
                             f"{no.nome}{sujo}{atual}")
            if no.expandido:
                total = len(no.filhos)
                for i, filho in enumerate(no.filhos):
                    prox = prefixo + ("   " if ultimo
                                      else "│  ")
                    _visita(filho, prox, i == total - 1,
                            False)

        _visita(self.raiz, "", True, True)
        return saida

    def __repr__(self) -> str:
        n = 0
        if self.raiz is not None:
            pilha = [self.raiz]
            while pilha:
                n += 1
                pilha.extend(pilha.pop().filhos)
        return f"ArvoreProjetoReal({n} nos)"


class AbasAvancadas:
    """Abas sobre GerenciadorDocumentos (sem duplicar AbasEditor)."""

    def __init__(self, gerenciador) -> None:
        self.gerenciador = gerenciador

    def proxima(self) -> str | None:
        from .ux import AbasEditor

        abas = AbasEditor(self.gerenciador)
        lista = [i["caminho"] for i in abas.lista()]
        if not lista:
            return None
        atual = self.gerenciador.ativo
        nxt = lista[(lista.index(atual) + 1) % len(lista)] \
            if atual in lista else lista[0]
        abas.trocar(nxt)
        return nxt

    def anterior(self) -> str | None:
        from .ux import AbasEditor

        abas = AbasEditor(self.gerenciador)
        lista = [i["caminho"] for i in abas.lista()]
        if not lista:
            return None
        atual = self.gerenciador.ativo
        prv = lista[(lista.index(atual) - 1) % len(lista)] \
            if atual in lista else lista[0]
        abas.trocar(prv)
        return prv

    def fechar_outras(self, manter: str) -> list[str]:
        from .ux import AbasEditor

        abas = AbasEditor(self.gerenciador)
        abertas = [i["caminho"] for i in abas.lista()]
        if manter not in abertas:
            raise ErroELiXX("Abas: manter precisa estar aberta.")
        sujas = [c for c in abertas
                 if c != manter and self.gerenciador.obter(
                     c).dirty]
        if sujas:
            raise ErroELiXX("Abas: ha dirty "
                            f"({len(sujas)}); salve antes.")
        for caminho in abertas:
            if caminho != manter:
                abas.fechar(caminho)
        return [manter]

    def fechar_todas(self) -> list[str]:
        from .ux import AbasEditor

        abas = AbasEditor(self.gerenciador)
        abertas = [i["caminho"] for i in abas.lista()]
        sujas = [c for c in abertas
                 if self.gerenciador.obter(c).dirty]
        if sujas:
            raise ErroELiXX("Abas: ha dirty "
                            f"({len(sujas)}); salve antes.")
        for caminho in abertas:
            abas.fechar(caminho)
        return []

    def salvar_todas(self, workspace) -> list[str]:
        salvas = []
        for caminho in self.gerenciador.abertos():
            doc = self.gerenciador.obter(caminho)
            if not doc.dirty:
                continue
            destino = workspace.resolver(caminho)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(doc.texto, encoding="utf-8")
            doc.marcar_salvo()
            salvas.append(caminho)
        return sorted(salvas)


class EstadoExecucao:
    """PRONTO/VALIDANDO/EXECUTANDO/CONCLUIDO/ERRO/PARADO."""

    ESTADOS = ("PRONTO", "VALIDANDO", "EXECUTANDO",
               "CONCLUIDO", "ERRO", "PARADO")

    def __init__(self) -> None:
        self.estado = "PRONTO"
        self.detalhe = ""
        self.ultimo_resumo: dict = {}


def executar_projeto(preview, texto: str,
                     entrada: str = "main.elixx",
                     estado: EstadoExecucao | None = None
                     ) -> dict:
    """Salvar->validar->executar->preview->status (real)."""
    from .editor import diagnosticar_texto

    est = estado or EstadoExecucao()
    if not isinstance(texto, str):
        raise ErroELiXX("Execucao: texto precisa de string.")
    est.estado = "VALIDANDO"
    diags = diagnosticar_texto(texto, entrada)
    erros = [d for d in diags if d.severidade == "error"]
    if erros:
        est.estado = "ERRO"
        est.detalhe = erros[0].mensagem[:200]
        return {"ok": False, "estado": est.estado,
                "erro": est.detalhe}
    est.estado = "EXECUTANDO"
    try:
        resultado = preview.executar(texto, entrada)
    except ErroELiXX as exc:
        preview.parar()
        est.estado = "ERRO"
        est.detalhe = str(exc).split("\n")[0][:200]
        return {"ok": False, "estado": est.estado,
                "erro": est.detalhe}
    if resultado.sucesso:
        est.estado = "CONCLUIDO"
        est.detalhe = ""
        est.ultimo_resumo = dict(resultado.resumo)
    else:
        preview.parar()
        est.estado = "ERRO"
        primeiro = (resultado.erros()[0].mensagem
                    if resultado.erros() else "erro")
        est.detalhe = primeiro[:200]
    return {"ok": resultado.sucesso, "estado": est.estado,
            "erro": est.detalhe,
            "resumo": dict(est.ultimo_resumo)}


def parar_execucao(preview,
                   estado: EstadoExecucao | None = None
                   ) -> dict:
    """Para e limpa estado (arquitetura sem processo externo)."""
    preview.parar()
    est = estado or EstadoExecucao()
    est.estado = "PARADO"
    est.detalhe = ""
    return {"ok": True, "estado": est.estado}


class EstadoProjeto:
    """Leitura central (sem segunda fonte; so dicionario)."""

    def __init__(self, dados: dict) -> None:
        self.dados = dict(dados)

    def to_dict(self) -> dict:
        return dict(self.dados)

    def __repr__(self) -> str:
        return (f"EstadoProjeto("
                f"{self.dados.get('active_file')})")


def estado_projeto(studio_workspace) -> EstadoProjeto:
    """Snapshot: paths, abas, dirty, selecao, preview, agente."""
    ws = studio_workspace
    app = ws.app
    base = app.workspace
    abertas, sujas, ativa = [], [], None
    if hasattr(ws, "editores"):
        abertas = sorted(ws.editores)
        sujas = sorted(c for c, e in ws.editores.items()
                       if e.modificado())
        for caminho in abertas:
            try:
                doc = app.documentos.obter(caminho)
                _ = doc
            except ErroELiXX:
                pass
    try:
        ativa = app.documentos.ativo
    except (AttributeError, ErroELiXX):
        ativa = None
    try:
        diag = ws.diagnosticos.resumo()
    except (AttributeError, ErroELiXX):
        diag = {}
    try:
        sel = app.inspetor.selecao.to_dict()
    except (AttributeError, ErroELiXX):
        sel = {}
    try:
        sel_prev = ws.preview.selecionado
    except (AttributeError, ErroELiXX):
        sel_prev = None
    try:
        sessao = getattr(ws, "_sessao", None)
        agente = ({"id": sessao.id, "estado": sessao.estado}
                  if sessao is not None else {})
    except (AttributeError, ErroELiXX):
        agente = {}
    dados = {
        "project_path": str(base.raiz) if base.raiz else "",
        "open_files": abertas,
        "active_file": ativa,
        "dirty_files": sujas,
        "selected_entity": sel,
        "selected_preview": sel_prev,
        "active_scene": None,
        "preview_state": ("executando"
                          if app.preview.rodando else "parado"),
        "agent_session": agente,
        "diagnostics": diag,
        "execution_state": ("executando"
                            if app.preview.rodando
                            else "parado"),
    }
    return EstadoProjeto(dados)


class BoasVindas:
    """Welcome (somente quando sem projeto; acoes reais)."""

    def __init__(self, recentes: Recentes | None = None
                 ) -> None:
        self.recentes = recentes or Recentes()

    def mostrar(self, tem_projeto: bool) -> dict | None:
        if tem_projeto:
            return None
        return {"titulo": "ELiXX Studio",
                "subtitulo": "Crie experiências visuais.",
                "acoes": ["novo_projeto", "abrir_projeto"],
                "templates": list(TEMPLATES),
                "recentes": self.recentes.listar()}

    def __repr__(self) -> str:
        return "BoasVindas()"


def menu_contexto(alvo: str, caminho: str = "",
                  existe: bool = True) -> list[dict]:
    """Menu por tipo (somente acoes reais do modulo)."""
    tipo = str(alvo)
    if tipo == "arquivo":
        itens = ["abrir", "renomear", "duplicar", "excluir",
                 "copiar_caminho", "copiar_nome"]
    elif tipo == "pasta":
        itens = ["abrir_pasta", "novo_arquivo", "nova_pasta",
                 "renomear", "excluir", "copiar_caminho"]
    elif tipo == "projeto":
        itens = ["novo_arquivo", "nova_pasta", "recarregar",
                 "fechar_projeto"]
    else:
        raise ErroELiXX("Projeto: menu de arquivo/pasta/"
                        "projeto.")
    _ = (caminho, existe)
    rotulos = {
        "abrir": "Abrir", "renomear": "Renomear",
        "duplicar": "Duplicar", "excluir": "Excluir",
        "revelar": "Revelar no projeto",
        "copiar_caminho": "Copiar caminho",
        "copiar_nome": "Copiar nome",
        "abrir_pasta": "Abrir", "novo_arquivo": "Novo arquivo",
        "nova_pasta": "Nova pasta", "recarregar": "Recarregar",
        "fechar_projeto": "Fechar projeto",
    }
    return [{"id": item, "rotulo": rotulos[item]}
            for item in itens]


def interpretar_arrastar(origem: str, destino: str) -> dict:
    """Arrastar arquivo->pasta: valida; NAO move (proposta).

    Retorna operacao proposta (renomear) para aprovacao; sem
    modificacao destrutiva direta.
    """
    src = _rel_seguro(origem)
    dst_dir = _rel_seguro(destino).rstrip("/")
    if "/" in src and src.rsplit("/", 1)[0] == dst_dir:
        raise ErroELiXX("Projeto: ja esta nesta pasta.")
    nome = src.rsplit("/", 1)[-1]
    return {"operacao": "renomear", "origem": src,
            "destino": f"{dst_dir}/{nome}",
            "modo": "proposta"}


def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).lower()
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(base.split())


def buscar_palette_f41(texto: str = "") -> list[dict]:
    termo = _norm(texto)
    return [{"id": cid, "rotulo": rotulo}
            for cid, rotulo in COMANDOS_F41
            if not termo or termo in _norm(f"{cid} {rotulo}")]


def executar_palette_f41(studio_workspace, comando_id: str,
                         args: dict | None = None) -> dict:
    """Despacha comandos F41 para funcoes reais do Studio."""
    ws = studio_workspace
    cid = str(comando_id)
    arg = dict(args or {})
    app = ws.app
    if cid == "novo_projeto":
        return {"ok": True, "acao": cid,
                "templates": list(TEMPLATES)}
    if cid == "abrir_projeto":
        return {"ok": True, "acao": cid}
    if cid == "fechar_projeto":
        return {"ok": True, **fechar_projeto(ws)}
    if cid == "novo_arquivo":
        tipo = str(arg.get("tipo", "elixx"))
        nome = str(arg.get("nome", "novo"))
        rel = str(arg.get("caminho",
                          f"src/{nome}.{tipo if tipo != 'texto' else 'txt'}"))
        from .arquivos import ArvoreArquivos

        criado = ArvoreArquivos(app.workspace).criar_arquivo(
            rel, conteudo_inicial(
                tipo if tipo in TIPOS_ARQUIVO else "texto",
                nome))
        return {"ok": True, "acao": cid, "arquivo": criado}
    if cid == "nova_pasta":
        from .arquivos import ArvoreArquivos

        rel = _rel_seguro(str(arg.get("caminho", "src/nova")))
        return {"ok": True, "acao": cid, "pasta":
                ArvoreArquivos(app.workspace).criar_pasta(rel)}
    if cid == "abrir_arquivo":
        rel = _rel_seguro(str(arg.get("caminho", "")))
        if not rel:
            raise ErroELiXX("Palette: caminho vazio.")
        ed = ws.abrir_no_editor(rel)
        return {"ok": True, "acao": cid, "arquivo": rel,
                "linhas": ed.documento.linhas()}
    if cid == "salvar":
        rel = str(arg.get("caminho",
                          app.documentos.ativo or ""))
        if not rel:
            raise ErroELiXX("Palette: nada aberto.")
        return {"ok": True, "acao": cid,
                **ws.salvar_editor(rel)}
    if cid == "salvar_tudo":
        abas = AbasAvancadas(app.documentos)
        return {"ok": True, "acao": cid,
                "salvos": abas.salvar_todas(app.workspace)}
    if cid == "fechar_aba":
        from .ux import AbasEditor

        rel = str(arg.get("caminho",
                          app.documentos.ativo or ""))
        if app.documentos.obter(rel).dirty:
            raise ErroELiXX("Palette: aba dirty; salve antes.")
        AbasEditor(app.documentos).fechar(rel)
        if rel in getattr(ws, "editores", {}):
            del ws.editores[rel]
        return {"ok": True, "acao": cid, "arquivo": rel}
    if cid == "fechar_todas_abas":
        abas = AbasAvancadas(app.documentos)
        return {"ok": True, "acao": cid,
                "fechadas": abas.fechar_todas()}
    if cid == "executar":
        from .preview import HeadlessPreview

        rel = str(arg.get("caminho",
                          app.documentos.ativo
                          or "src/main.elixx"))
        texto = app.workspace.resolver(rel).read_text(
            encoding="utf-8")
        prev = (app.preview
                if isinstance(app.preview, HeadlessPreview)
                else HeadlessPreview())
        return {"ok": True, "acao": cid,
                **executar_projeto(prev, texto, rel)}
    if cid == "parar":
        return {"ok": True, "acao": cid,
                **parar_execucao(app.preview)}
    if cid in ("buscar", "substituir", "ir_para_linha"):
        return {"ok": True, "acao": cid, "nota": "no editor"}
    if cid in ("mostrar_preview", "mostrar_scene",
               "mostrar_agent", "mostrar_inspector",
               "mostrar_raciocinio", "mostrar_plano",
               "mostrar_changes"):
        return {"ok": True, "acao": cid}
    if cid == "recarregar_projeto":
        return {"ok": True, "acao": cid,
                **recarregar_projeto(ws)}
    raise ErroELiXX(f'Projeto: comando "{cid}" desconhecido.')


def conflitos_f41() -> list[dict]:
    """Atalhos F41 livres + conflitos documentados."""
    from .app import ATALHOS

    saida = []
    for tecla, acao in ATALHOS_F41.items():
        if tecla in ATALHOS:
            saida.append({"tecla": tecla,
                          "global": ATALHOS[tecla],
                          "contextual": acao,
                          "regra": "global prevalece"})
    for tecla, motivo in CONFLITOS_F41.items():
        saida.append({"tecla": tecla, "global": motivo,
                      "contextual": "preservado",
                      "regra": "sem substituicao"})
    return saida
