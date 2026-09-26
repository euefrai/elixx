"""StudioApp (F25) — orquestra workspace, editor, preview e painéis.

`executar_comando` é o ponto único de operação estruturada (o futuro
Agent falará por aqui). `montar_ui` constrói o layout Tk compacto
(PROJETO | PREVIEW | INSPETOR / EDITOR / TIMELINE+CONSOLE); tudo
funciona headless sem ela.
"""
from __future__ import annotations

from ..erros import ErroELiXX
from .arquivos import ArvoreArquivos
from .assets import GerenciadorAssets
from .cena import ModeloCena
from .comandos import StudioCommand
from .documento import GerenciadorDocumentos
from .estado import Configuracao
from .eventos import EventBus
from .inspetor import Inspetor, Selecao
from .logs import PainelLogs
from .preview import HeadlessPreview
from .workspace import Workspace

__all__ = ["ATALHOS", "StudioApp"]

ATALHOS = {
    "Ctrl+O": "abrir_projeto",
    "Ctrl+S": "salvar",
    "Ctrl+Shift+S": "salvar_como",
    "F5": "executar",
    "Shift+F5": "parar",
    "Ctrl+Z": "desfazer",
    "Ctrl+Y": "refazer",
    "Ctrl+F": "buscar",
}
"""Mapa atalho → comando (sem quebrar atalhos do sistema: só dentro)."""


class StudioApp:
    """Aplicação do Studio (headless por padrão; UI sob demanda)."""

    def __init__(self, config: Configuracao | None = None) -> None:
        self.config = config or Configuracao()
        self.workspace = Workspace()
        self.documentos = GerenciadorDocumentos()
        self.arquivos = ArvoreArquivos(self.workspace)
        self.assets = GerenciadorAssets(self.workspace)
        self.inspetor = Inspetor()
        self.logs = PainelLogs()
        self.eventos = EventBus()
        self.preview = HeadlessPreview()
        self.modelo_cena = ModeloCena()
        self.janela = None

    # ----- comandos estruturados (futuro Agent usa esta porta) -----

    def executar_comando(self, comando: StudioCommand) -> dict:
        if not isinstance(comando, StudioCommand):
            raise ErroELiXX("executar_comando espera StudioCommand.")
        nome = comando.nome
        if nome == "abrir_projeto":
            projeto = self.workspace.abrir_projeto(comando.alvo)
            self.logs.info(f"Projeto aberto: {projeto.nome}")
            self.eventos.emitir("projeto_aberto",
                                {"nome": projeto.nome})
            return {"ok": True, "projeto": projeto.nome}
        if nome == "salvar":
            doc = self.documentos.obter(comando.alvo)
            destino = self.workspace.resolver(doc.caminho)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(doc.texto, encoding="utf-8")
            doc.marcar_salvo()
            self.logs.info(f"Arquivo salvo: {doc.caminho}")
            self.eventos.emitir("arquivo_salvo",
                                {"arquivo": doc.caminho})
            return {"ok": True, "arquivo": doc.caminho}
        if nome == "executar":
            doc = self.documentos.obter(comando.alvo)
            resultado = self.preview.executar(doc.texto, doc.caminho)
            if resultado.sucesso:
                self.logs.info("Preview iniciado: "
                               f"{resultado.resumo}")
                self.eventos.emitir("preview_iniciado",
                                    {"entrada": doc.caminho})
            else:
                primeiro = (resultado.erros()[0].mensagem
                            if resultado.erros() else "erro")
                self.logs.error(f"Preview falhou: {primeiro}")
                self.eventos.emitir("erro", {"entrada": doc.caminho,
                                             "motivo": primeiro})
            return {"ok": resultado.sucesso,
                    "resumo": dict(resultado.resumo)}
        if nome == "parar":
            self.preview.parar()
            self.logs.info("Preview parado.")
            self.eventos.emitir("preview_parado", {})
            return {"ok": True}
        if nome == "abrir_arquivo":
            caminho = self.workspace.resolver(comando.alvo)
            if not caminho.is_file():
                raise ErroELiXX(f'Arquivo "{comando.alvo}" ausente.')
            doc = self.documentos.abrir(
                comando.alvo,
                caminho.read_text(encoding="utf-8"))
            self.eventos.emitir("arquivo_aberto",
                                {"arquivo": doc.caminho})
            return {"ok": True, "arquivo": doc.caminho}
        if nome == "criar_arquivo":
            rel = self.arquivos.criar_arquivo(
                comando.alvo,
                comando.parametros.get("conteudo", ""))
            return {"ok": True, "arquivo": rel}
        if nome == "selecionar":
            sel = Selecao(comando.parametros.get("tipo", "nenhum"),
                          comando.alvo,
                          comando.parametros.get("origem",
                                                 "preview"))
            self.inspetor.selecionar(sel)
            self.eventos.emitir("selecionado", sel.to_dict())
            return {"ok": True, "selecao": sel.to_dict()}
        if nome == "alterar_propriedade":
            prop = comando.parametros.get("propriedade", "")
            valor = comando.parametros.get("valor")
            if prop not in ("posicao", "rotacao", "escala",
                            "opacidade"):
                raise ErroELiXX(f'Propriedade "{prop}" inválida.')
            return {"ok": True, "propriedade": prop, "valor": valor,
                    "nota": "Aplicada pelo inspetor do personagem "
                            "quando há Character vinculado."}
        raise ErroELiXX(f'Comando "{nome}" desconhecido no Studio.')

    # ----- UI Tk (compacta; opcional; nunca nos testes) -----

    @staticmethod
    def interface_disponivel() -> bool:
        try:
            import tkinter as _tk

            raiz = _tk.Tk()
            raiz.withdraw()
            raiz.destroy()
            return True
        except Exception:
            return False

    def montar_ui(self):
        """Layout: topo | projeto/preview/inspetor | editor | base."""
        try:
            import tkinter as _tk
        except ImportError:
            raise ErroELiXX("Tk indisponível.")
        self.janela = _tk.Tk()
        self.janela.title("ELiXX Studio")
        self.janela.geometry("1100x750")
        topo = _tk.Frame(self.janela)
        topo.pack(fill="x")
        _tk.Label(topo, text="ELiXX Studio").pack(side="left")
        _tk.Button(topo, text="Executar (F5)",
                   command=lambda: None).pack(side="right")
        meio = _tk.PanedWindow(self.janela, orient="horizontal")
        meio.pack(fill="both", expand=True)
        esq = _tk.Frame(meio, width=200)
        self._lista_arquivos = _tk.Listbox(esq)
        self._lista_arquivos.pack(fill="both", expand=True)
        meio.add(esq)
        centro = _tk.Frame(meio)
        self._rotulo_preview = _tk.Label(centro, text="PREVIEW")
        self._rotulo_preview.pack()
        meio.add(centro, stretch="always")
        direita = _tk.Frame(meio, width=220)
        self._texto_inspetor = _tk.Text(direita, height=20, width=28)
        self._texto_inspetor.pack(fill="both", expand=True)
        meio.add(direita)
        self._editor_texto = _tk.Text(self.janela, height=12)
        self._editor_texto.pack(fill="x")
        base = _tk.PanedWindow(self.janela, orient="horizontal")
        base.pack(fill="x")
        self._texto_console = _tk.Text(base, height=6)
        base.add(self._texto_console, stretch="always")
        return self.janela

    def fechar_ui(self) -> None:
        if self.janela is not None:
            try:
                self.janela.destroy()
            except Exception:
                pass
            self.janela = None

    def __repr__(self) -> str:
        return f"StudioApp(workspace={self.workspace.raiz})"
