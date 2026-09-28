"""Renderer nativo da ELiXX — backend Tkinter (stdlib, zero dependências).

Por que Tkinter (decisão documentada em docs/renderer-nativo.md):
biblioteca padrão (distribuição sem custo), nativo no Windows, eventos
maduros, Canvas/Label/Button para 2D, imagens via PhotoImage (+Pillow
opcional), animação futura via after(). Troca de backend futura não toca
o runtime: basta outra subclasse de Renderizador.

Limitações assumidas na Fase 02: sem alfa por pixel (hex de 8 dígitos é
reduzido para 6), rotação/escala de widgets não aplicadas (guardadas na
Cena para a Fase 03), vídeo/áudio ainda sem saída real.
"""
from __future__ import annotations

import time

from ..erros import ErroELiXX
from ..multimidia.recursos import GerenciadorRecursos
from .renderizador import Renderizador, registrar_renderizador


class RenderizadorTk(Renderizador):
    """Backend nativo: uma janela real por Janela ELiXX."""

    nome = "nativo"
    TICK_MS = 50

    def __init__(self, executor=None) -> None:
        super().__init__(executor)
        import tkinter as tk

        self._tk = tk
        self.raiz = None
        self._itens: dict[int, tuple] = {}  # id(NoVisual) -> (widget, place_info)
        self._barras: list = []  # labels de mensagem (mostrar)
        self._paineis: dict[int, dict] = {}  # id(NoVisual) -> refs de widgets
        self._geom: dict[int, tuple] = {}  # id(NoVisual) -> geometria aplicada
        self._resize_id = None  # debounce do recálculo no resize
        self._aberto = False
        self.ultima_mensagem = ""
        # Fase 07: recursos (imagens/SVG/áudio); nativo ajusta base_dir.
        self.recursos = GerenciadorRecursos(".")
        # Fase 09: linhas dinâmicas (widget → linha) e ns vigente no desenho.
        self._linhas_por_no: dict = {}
        self._ns_atual: str | None = None
        # Fase 10: nós por id + ordem de criação (camadas determinísticas).
        self._nos: dict[int, object] = {}
        self._ordem: list[int] = []
        self._ordem_set: set[int] = set()
        self._camadas_aplicadas: tuple = ()
        # F41: último transform aplicado por nó (refresh de foto só
        # quando escala/rotação mudam; posição usa place, sem reload).
        self._transf_aplicada: dict[int, tuple] = {}

    # ----- construção -----

    def montar(self, cena) -> None:
        if not cena.janelas:
            raise ErroELiXX("Nada para mostrar: o programa não tem janelas.")
        self.cena = cena
        janelas = [n for n in cena.janelas if n.tipo == "janela"]
        telas = [n for n in cena.janelas if n.tipo == "tela"]
        area = None
        if janelas:
            for no_janela in janelas:
                area = self.criar_janela(no_janela)
        else:
            area = self.criar_janela_raiz(telas[0] if telas else None)
        for no_tela in telas:
            self.criar_tela(no_tela, area)
        self.remedir()
        self._aberto = True
        self._aplicar_camadas()

    def criar_janela_raiz(self, no):
        """Janela raiz implícita quando o programa só tem telas."""
        tk = self._tk
        widget = tk.Tk()
        self.raiz = widget
        titulo = (no.titulo if no is not None else "") or "ELiXX"
        largura = int((no.largura if no is not None else None) or 800)
        altura = int((no.altura if no is not None else None) or 600)
        widget.title(titulo)
        widget.geometry(f"{largura}x{altura}")
        widget.configure(bg=(no.fundo_hex if no is not None else None)
                         or "#f0f0f0")
        widget.protocol("WM_DELETE_WINDOW", self.fechar)
        area = tk.Frame(widget, bg=widget.cget("bg"))
        area.pack(fill=tk.BOTH, expand=True)
        barra = tk.Label(widget, text="", anchor="w", bg="#202020",
                         fg="#ffffff", font=("Segoe UI", 10))
        barra.pack(side=tk.BOTTOM, fill=tk.X)
        self._barras.append(barra)
        return area

    def criar_tela(self, no, area):
        """Tela = Frame em tela cheia dentro da janela (navegável)."""
        tk = self._tk
        fundo = no.fundo_hex or (area.cget("bg") if area is not None
                                 else "#f0f0f0")
        moldura = tk.Frame(area, bg=fundo)
        info = {"relx": 0, "rely": 0, "relwidth": 1, "relheight": 1}
        moldura.place(**info)
        self._itens[id(no)] = (moldura, info)
        self._paineis[id(no)] = {"kind": "tela"}
        for filho in no.filhos:
            self._desenhar(filho, moldura)
        self._aplicar_visibilidade(no)
        return moldura

    def remedir(self) -> None:
        """Fase 04: mede widgets de tamanho automático dentro de layouts
        (pós-montagem) e recalcula a Cena. O tick reposiciona no próximo
        ciclo via _aplicar_geometria."""
        if self.cena is None or self.raiz is None:
            return
        try:
            self.raiz.update_idletasks()
        except self._tk.TclError:
            return
        from .cena import LAYOUTS, recalcular

        mudou = False
        for jan in self.cena.janelas:
            for no in jan.todos()[1:]:
                if (no.pai is None or no.pai.tipo not in LAYOUTS
                        or (no.largura is not None
                            and no.altura is not None)):
                    continue
                entrada = self._itens.get(id(no))
                if entrada is None:
                    continue
                try:
                    widget = entrada[0]
                    if no.largura is None:
                        no.largura = float(widget.winfo_reqwidth())
                    if no.altura is None:
                        no.altura = float(widget.winfo_reqheight())
                    mudou = True
                except self._tk.TclError:
                    pass
        if mudou:
            recalcular(self.cena)

    def criar_janela(self, no) -> object:
        tk = self._tk
        if self.raiz is None:
            widget = tk.Tk()
            self.raiz = widget
        else:
            widget = tk.Toplevel(self.raiz)
        widget.title(no.titulo or no.nome or "ELiXX")
        largura = int(no.largura or 800)
        altura = int(no.altura or 600)
        widget.geometry(f"{largura}x{altura}+{int(no.x)}+{int(no.y)}")
        widget.configure(bg=no.fundo_hex or "#f0f0f0")
        widget.protocol("WM_DELETE_WINDOW", self.fechar)
        widget.bind("<Configure>",
                    lambda evento: self._ao_redimensionar(no, evento))
        area = tk.Frame(widget, bg=no.fundo_hex or "#f0f0f0")
        area.pack(fill=tk.BOTH, expand=True)
        barra = tk.Label(widget, text="", anchor="w", bg="#202020",
                         fg="#ffffff", font=("Segoe UI", 10))
        barra.pack(side=tk.BOTTOM, fill=tk.X)
        self._barras.append(barra)
        if self.ultima_mensagem:
            barra.configure(text=self.ultima_mensagem)
        for filho in no.filhos:
            self._desenhar(filho, area)
        self._itens[id(no)] = (widget, {})
        return widget

    def _desenhar(self, no, pai):
        # Fase 10: registra nó + ordem (camadas) uma vez por id.
        self._nos[id(no)] = no
        if id(no) not in self._ordem_set:
            self._ordem_set.add(id(no))
            self._ordem.append(id(no))
        if no.tipo == "texto":
            widget = self.desenhar_texto(no, pai)
        elif no.tipo == "botao":
            widget = self.desenhar_botao(no, pai)
        elif no.tipo in ("painel", "cartao"):
            widget = self.desenhar_painel(no, pai)
            for neto in no.filhos:
                # filhos do painel usam coordenadas relativas ao painel
                self._desenhar(neto, widget)
            return widget
        elif no.tipo in ("grupo", "objeto"):
            # Fase 10: contêiner do Visual Core (Frame; filhos relativos,
            # transformação conjunta; ordem por camada no tick).
            widget = self.desenhar_grupo(no, pai)
            for neto in no.filhos:
                self._desenhar(neto, widget)
            return widget
        elif no.tipo in ("personagem", "parte"):
            # Fase 12: entidade articulada (mesmo Frame do grupo; a
            # imagem do nó, se houver, vira fundo via _foto_raster).
            widget = self.desenhar_grupo(no, pai)
            for neto in no.filhos:
                self._desenhar(neto, widget)
            return widget
        elif no.tipo in ("linha", "coluna", "grade", "pilha"):
            # Fase 04: contêiner de layout (Frame; filhos relativos).
            widget = self.desenhar_painel(no, pai)
            for neto in no.filhos:
                self._desenhar(neto, widget)
            return widget
        elif no.tipo == "entrada":
            widget = self.desenhar_entrada(no, pai)
        elif no.tipo == "checkbox":
            widget = self.desenhar_checkbox(no, pai)
        elif no.tipo == "selecao":
            widget = self.desenhar_selecao(no, pai)
        elif no.tipo == "separador":
            widget = self.desenhar_separador(no, pai)
        elif no.tipo == "indicador":
            widget = self.desenhar_indicador(no, pai)
        elif no.tipo == "barra":
            widget = self.desenhar_barra(no, pai)
        elif no.tipo == "grafico":
            widget = self.desenhar_grafico(no, pai)
        elif no.tipo == "lista":
            widget = self.desenhar_lista(no, pai)
        elif no.tipo == "icone":
            widget = self.desenhar_icone(no, pai)
        elif no.tipo == "imagem":
            widget = self.desenhar_imagem(no, pai)
        elif no.tipo == "audio":
            widget = self.desenhar_audio(no, pai)
        elif no.tipo == "video":
            widget = self.desenhar_video(no, pai)
        elif no.tipo == "modal":
            widget = self.desenhar_modal(no, pai)
            for neto in no.filhos:
                area_modal = self._paineis[id(no)]["area"]
                self._desenhar(neto, area_modal)
            return widget
        elif no.tipo == "abas":
            widget = self.desenhar_abas(no, pai)
            return widget
        elif no.tipo == "aba":
            widget = self.desenhar_painel(no, pai)
            for neto in no.filhos:
                self._desenhar(neto, widget)
            return widget
        elif no.tipo == "menu":
            widget = self.desenhar_menu(no, pai)
            return widget
        elif no.tipo == "tabela":
            widget = self.desenhar_tabela(no, pai)
        else:
            widget = self._desenhar_provisorio(no, pai)
        for neto in no.filhos:
            self._desenhar(neto, pai)
        return widget

    def desenhar_painel(self, no, pai) -> object:
        """Contêiner (painel/cartao): Frame que agrupa filhos."""
        tk = self._tk
        fundo = no.fundo_hex or pai.cget("bg")
        moldura = tk.Frame(pai, bg=fundo)
        if no.tipo == "cartao":
            moldura.configure(highlightthickness=1,
                              highlightbackground="#3a4058")
        info: dict = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = int(no.largura)
        if no.altura:
            info["height"] = int(no.altura)
        moldura.place(**info)
        self._itens[id(no)] = (moldura, info)
        self._aplicar_visibilidade(no)
        return moldura

    @staticmethod
    def _escala_no(no) -> tuple[float, float]:
        """Escala efetiva (Fase 10: eixos; legado uniforme como fallback)."""
        try:
            sx = float(getattr(no, "escala_x", None)
                       if getattr(no, "escala_x", None) is not None
                       else getattr(no, "escala", 1.0) or 1.0)
            sy = float(getattr(no, "escala_y", None)
                       if getattr(no, "escala_y", None) is not None
                       else getattr(no, "escala", 1.0) or 1.0)
        except (TypeError, ValueError):
            return (1.0, 1.0)
        return (sx if sx > 0 else 1.0, sy if sy > 0 else 1.0)

    def _info_place(self, no) -> dict:
        """placeinfo com escala aplicada (tamanho visual real)."""
        sx, sy = self._escala_no(no)
        info: dict = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = max(1, int(no.largura * sx))
        if no.altura:
            info["height"] = max(1, int(no.altura * sy))
        return info

    def desenhar_grupo(self, no, pai) -> object:
        """Grupo/objeto (Fase 10): Frame invisível que move junto.

        Filhos usam coordenadas locais; a ordem de desenho segue a camada
        (aplicada no tick). Rotação de widgets não existe no Tk (estado
        interno preservado para futuros backends); escala altera o tamanho
        real; opacidade por widget não existe no Tk (só alfa da janela).
        """
        tk = self._tk
        try:
            fundo = no.fundo_hex or pai.cget("bg")
        except tk.TclError:
            fundo = "#f0f0f0"
        moldura = tk.Frame(pai, bg=fundo)
        info = self._info_place(no)
        moldura.place(**info)
        self._itens[id(no)] = (moldura, info)
        self._aplicar_visibilidade(no)
        # Fase 12: `imagem:` no personagem/parte vira fundo do Frame
        # (mesmo carregamento das imagens; filhos desenham por cima).
        if no.tipo in ("personagem", "parte") and no.fonte_recurso:
            rotulo = tk.Label(moldura, bg=fundo)
            rotulo.place(x=0, y=0)
            self._paineis[id(no)] = {"kind": "parte", "quadro": moldura,
                                     "rotulo": rotulo, "fotos": [],
                                     "carregada": False}
            if no.fonte_recurso == "arquivo":
                self._carregar_imagem_local(no)
            elif no.fonte_recurso == "url":
                self.recursos.baixar_async(
                    no.caminho_recurso,
                    lambda dados, n=no: self.programar(
                        0, lambda: self._aplicar_bytes_imagem(n, dados)))
        return moldura

    def desenhar_barra(self, no, pai) -> object:
        """Barra de progresso 0-100 (Canvas com 2 retângulos)."""
        tk = self._tk
        largura = int(no.largura or 200)
        altura = int(no.altura or 20)
        fundo = tk.Canvas(pai, width=largura, height=altura,
                          bg="#2a2e3f", highlightthickness=0)
        fundo.create_rectangle(0, 0, largura, altura,
                               fill="#2a2e3f", outline="")
        preench = fundo.create_rectangle(0, 0, 0, altura,
                                         fill=no.cor_hex or "#4ade80",
                                         outline="")
        info = {"x": int(no.x), "y": int(no.y)}
        fundo.place(**info)
        self._itens[id(no)] = (fundo, info)
        self._paineis[id(no)] = {"kind": "barra", "canvas": fundo,
                                 "id": preench, "largura": largura}
        self._aplicar_visibilidade(no)
        return fundo

    def desenhar_grafico(self, no, pai) -> object:
        """Gráfico de linha do histórico (Canvas redesenhado a cada tick)."""
        tk = self._tk
        largura = int(no.largura or 300)
        altura = int(no.altura or 120)
        quadro = tk.Frame(pai, bg=pai.cget("bg"))
        titulo = tk.Label(quadro, text=no.texto or no.nome or "Gráfico",
                          font=("Segoe UI", 10, "bold"),
                          fg=no.cor_hex or "#e6e8f0", bg=pai.cget("bg"))
        titulo.pack(anchor="w")
        tela = tk.Canvas(quadro, width=largura, height=altura,
                         bg="#14161f", highlightthickness=1,
                         highlightbackground="#3a4058")
        tela.pack()
        info = {"x": int(no.x), "y": int(no.y)}
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "grafico", "canvas": tela,
                                 "titulo": titulo, "largura": largura,
                                 "altura": altura}
        self._aplicar_visibilidade(no)
        return quadro

    def desenhar_lista(self, no, pai) -> object:
        """Lista: estática (Listbox) ou dinâmica (linhas do modelo)."""
        if getattr(no, "dinamica", False):
            return self.desenhar_lista_dinamica(no, pai)
        tk = self._tk
        largura_px = int(no.largura or 220)
        altura_px = int(no.altura or 130)
        colunas = max(10, largura_px // 8)
        linhas = max(3, altura_px // 18)
        caixa = tk.Listbox(pai, width=colunas, height=linhas,
                           bg="#14161f", fg="#e6e8f0",
                           highlightthickness=1,
                           highlightbackground="#3a4058",
                           selectbackground="#3a4058")
        info = {"x": int(no.x), "y": int(no.y)}
        caixa.place(**info)
        self._itens[id(no)] = (caixa, info)
        self._paineis[id(no)] = {"kind": "lista", "caixa": caixa,
                                 "atual": []}
        if no.ligado_a:
            caixa.bind("<<ListboxSelect>>",
                       lambda _e, n=no: self._selecionar_lista(n))
        self._aplicar_visibilidade(no)
        return caixa

    def desenhar_lista_dinamica(self, no, pai) -> object:
        """Contêiner de linhas (Fase 09); linhas chegam via definir."""
        tk = self._tk
        quadro = tk.Frame(pai, bg=pai.cget("bg"))
        info = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = int(no.largura)
        if no.altura:
            info["height"] = int(no.altura)
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "lista_dinamica",
                                 "quadro": quadro, "linhas": {}}
        self._aplicar_visibilidade(no)
        return quadro

    def _reconciliar_linhas(self, no, plano: dict) -> None:
        """Cria/atualiza/remove frames de linha (preserva identidade)."""
        tk = self._tk
        refs = self._paineis.get(id(no))
        if refs is None:
            return
        quadro = refs["quadro"]
        estado_linhas = refs["linhas"]
        for removida in plano.get("removidas", []):
            chave = removida["chave"]
            info_linha = estado_linhas.pop(chave, None)
            if info_linha is None:
                continue
            for copia in removida.get("copias", []):
                self._limpar_no(copia)
            try:
                info_linha["frame"].destroy()
            except tk.TclError:
                pass
            for chave_reg, linha_reg in list(self._linhas_por_no.items()):
                if linha_reg.get("frame_id") == id(info_linha["frame"]):
                    del self._linhas_por_no[chave_reg]
        for linha in plano.get("linhas", []):
            chave = linha["chave"]
            info_linha = estado_linhas.get(chave)
            if info_linha is None:
                frame = tk.Frame(quadro, bg=quadro.cget("bg"),
                                 highlightthickness=1,
                                 highlightbackground="#3a4058")
                info_linha = {"frame": frame, "copias": linha["copias"],
                              "y": 0}
                estado_linhas[chave] = info_linha
                anterior_ns = self._ns_atual
                self._ns_atual = linha["ns"]
                try:
                    for copia in linha["copias"]:
                        self._desenhar(copia, frame)
                        self._linhas_por_no[id(copia)] = {
                            "ns": linha["ns"], "item": linha["item"],
                            "indice": linha["indice"],
                            "frame_id": id(frame),
                            "no_lista": no,
                        }
                        for sub in copia.todos() if hasattr(
                                copia, "todos") else []:
                            self._linhas_por_no.setdefault(id(sub), {
                                "ns": linha["ns"], "item": linha["item"],
                                "indice": linha["indice"],
                                "frame_id": id(frame),
                                "no_lista": no,
                            })
                finally:
                    self._ns_atual = anterior_ns
            for copia, pacote in linha.get("pacotes", []):
                try:
                    self.definir_valor(copia, pacote)
                except Exception:
                    pass
        self._empilhar_linhas(no)

    def _empilhar_linhas(self, no) -> None:
        refs = self._paineis.get(id(no))
        if refs is None:
            return
        try:
            refs["quadro"].update_idletasks()
        except self._tk.TclError:
            return
        cursor = 0
        for chave, info_linha in refs["linhas"].items():
            frame = info_linha["frame"]
            try:
                altura = max(20, frame.winfo_reqheight())
                largura = refs["quadro"].winfo_width() or None
            except self._tk.TclError:
                continue
            try:
                if largura:
                    frame.configure(width=largura)
                frame.place(x=0, y=cursor, width=largura,
                            height=altura)
            except self._tk.TclError:
                continue
            cursor += altura + 6

    def _limpar_no(self, no) -> None:
        """Remove registros de widget de uma cópia destruída."""
        self._itens.pop(id(no), None)
        self._paineis.pop(id(no), None)
        for filho in getattr(no, "filhos", []):
            self._limpar_no(filho)
        for modelo in getattr(no, "modelo", []):
            self._limpar_no(modelo)

    def _selecionar_lista(self, no) -> None:
        refs = self._paineis.get(id(no))
        if refs is None:
            return
        try:
            atual = refs["caixa"].curselection()
        except self._tk.TclError:
            return
        if atual:
            self._escrever_indice(no, atual[0])
        self._gesto(no, "mudanca")

    def _escrever_indice(self, no, indice: int) -> None:
        estado = getattr(self.executor, "estado", None)
        if estado is None or not no.ligado_a:
            return
        try:
            if estado.obter(no.ligado_a) != indice:
                estado.definir(no.ligado_a, indice)
        except Exception:
            pass

    # ----- Fase 04: formulário e layout -----

    def desenhar_entrada(self, no, pai) -> object:
        """Campo de texto (leitura do valor chega na Fase 05)."""
        tk = self._tk
        largura_px = int(no.largura or 200)
        campo = tk.Entry(pai, width=max(8, largura_px // 8),
                         bg="#ffffff", fg="#111111",
                         highlightthickness=1,
                         highlightbackground="#3a4058")
        if no.texto and no.texto != no.nome:
            campo.insert(0, no.texto)
        info = {"x": int(no.x), "y": int(no.y)}
        campo.place(**info)
        self._itens[id(no)] = (campo, info)
        self._paineis[id(no)] = {"kind": "entrada", "campo": campo,
                                 "ns": self._ns_atual}
        self._ligar_estado(no, campo)
        campo.bind("<KeyRelease>", lambda _e, n=no: self._gesto(n, "mudanca"))
        self._aplicar_visibilidade(no)
        return campo

    def desenhar_checkbox(self, no, pai) -> object:
        tk = self._tk
        var = tk.BooleanVar(value=False)
        caixa = tk.Checkbutton(pai, text=no.texto or no.nome, variable=var,
                               bg=pai.cget("bg"), fg=no.cor_hex or "#e6e8f0",
                               selectcolor=pai.cget("bg"), anchor="w",
                               font=("Segoe UI", max(6, int(round(no.fonte_px)))))
        info = {"x": int(no.x), "y": int(no.y)}
        caixa.place(**info)
        self._itens[id(no)] = (caixa, info)
        self._paineis[id(no)] = {"kind": "checkbox", "var": var,
                                 "ns": self._ns_atual}
        if no.ligado_a and self.executor is not None:
            var.trace_add("write",
                          lambda *_a, n=no: self._escrever_estado(n))
        caixa.configure(command=lambda n=no: self._gesto(n, "mudanca"))
        self._aplicar_visibilidade(no)
        return caixa

    def desenhar_selecao(self, no, pai) -> object:
        from tkinter import ttk

        combo = ttk.Combobox(pai, values=no.opcoes or ["—"],
                             state="readonly",
                             width=max(8, int((no.largura or 200)) // 8))
        if no.opcoes:
            combo.current(0)
        info = {"x": int(no.x), "y": int(no.y)}
        combo.place(**info)
        self._itens[id(no)] = (combo, info)
        self._paineis[id(no)] = {"kind": "selecao", "combo": combo,
                                 "ns": self._ns_atual}
        self._ligar_estado(no, combo, evento="<<ComboboxSelected>>")
        combo.bind("<<ComboboxSelected>>",
                   lambda _e, n=no: self._gesto(n, "mudanca"), add="+")
        self._aplicar_visibilidade(no)
        return combo

    def desenhar_separador(self, no, pai) -> object:
        tk = self._tk
        largura_px = int(no.largura or 200)
        linha = tk.Frame(pai, width=largura_px, height=2, bg="#3a4058")
        info = {"x": int(no.x), "y": int(no.y)}
        linha.place(**info)
        self._itens[id(no)] = (linha, info)
        self._aplicar_visibilidade(no)
        return linha

    def desenhar_indicador(self, no, pai) -> object:
        """Bolinha de estado + rótulo (bool via origem → verde/vermelho)."""
        tk = self._tk
        quadro = tk.Frame(pai, bg=pai.cget("bg"))
        ponto = tk.Canvas(quadro, width=14, height=14, bg=pai.cget("bg"),
                          highlightthickness=0)
        bola = ponto.create_oval(1, 1, 13, 13,
                                 fill=no.cor_hex or "#6b7280", outline="")
        ponto.pack(side="left")
        rotulo = tk.Label(quadro, text=no.texto or no.nome,
                          bg=pai.cget("bg"),
                          fg=no.cor_hex or "#e6e8f0",
                          font=("Segoe UI", max(6, int(round(no.fonte_px)))))
        rotulo.pack(side="left", padx=6)
        info = {"x": int(no.x), "y": int(no.y)}
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "indicador", "canvas": ponto,
                                 "id": bola}
        self._aplicar_visibilidade(no)
        return quadro

    def desenhar_texto(self, no, pai) -> object:
        tk = self._tk
        rotulo = tk.Label(
            pai, text=no.texto or no.nome,
            font=("Segoe UI", max(6, int(round(no.fonte_px)))),
            fg=no.cor_hex or "#000000",
            bg=pai.cget("bg"),
        )
        info: dict = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = int(no.largura)
        if no.altura:
            info["height"] = int(no.altura)
        rotulo.place(**info)
        self._itens[id(no)] = (rotulo, info)
        self._aplicar_visibilidade(no)
        return rotulo

    def desenhar_botao(self, no, pai) -> object:
        tk = self._tk
        botao = tk.Button(
            pai, text=no.texto or no.nome or "Botão",
            font=("Segoe UI", max(6, int(round(no.fonte_px)))),
            command=lambda: self._clique(no),
        )
        if no.fundo_hex:
            try:
                botao.configure(bg=no.fundo_hex)
            except tk.TclError:
                pass
        info: dict = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = int(no.largura)
        if no.altura:
            info["height"] = int(no.altura)
        botao.place(**info)
        # passar o cursor também é evento ELiXX real (sem sistema paralelo)
        botao.bind("<Enter>",
                   lambda _e: self._gesto(no, "passar_por_cima"))
        self._itens[id(no)] = (botao, info)
        self._aplicar_visibilidade(no)
        return botao

    def _desenhar_provisorio(self, no, pai) -> object:
        tk = self._tk
        rotulo = tk.Label(
            pai, text=f"[{no.tipo}: {no.nome} — Fase 03]",
            fg="#666666", bg=pai.cget("bg"),
        )
        info = {"x": int(no.x), "y": int(no.y)}
        rotulo.place(**info)
        self._itens[id(no)] = (rotulo, info)
        return rotulo

    # ----- Fase 07: multimídia -----

    @staticmethod
    def _pillow():
        try:
            from PIL import Image, ImageTk

            return Image, ImageTk
        except ImportError:
            return None, None

    def desenhar_imagem(self, no, pai) -> object:
        """Imagem real: arquivo local (sync) ou URL (async)."""
        tk = self._tk
        quadro = tk.Frame(pai, bg=pai.cget("bg"))
        rotulo = tk.Label(quadro, bg=pai.cget("bg"), fg="#9aa0b4",
                          text="carregando imagem…")
        rotulo.pack()
        info = {"x": int(no.x), "y": int(no.y)}
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "imagem", "quadro": quadro,
                                 "rotulo": rotulo, "fotos": [],
                                 "carregada": False}
        if no.fonte_recurso == "arquivo":
            self._carregar_imagem_local(no)
        elif no.fonte_recurso == "url":
            self.recursos.baixar_async(
                no.caminho_recurso,
                lambda dados, n=no: self.programar(
                    0, lambda: self._aplicar_bytes_imagem(n, dados)))
        else:
            self._imagem_erro(no, "sem arquivo nem url")
        self._aplicar_visibilidade(no)
        return quadro

    def _carregar_imagem_local(self, no) -> None:
        try:
            absoluto = self.recursos.caminho_local(no.caminho_recurso)
            dados = self.recursos.bytes_local(no.caminho_recurso)
        except ErroELiXX as exc:
            self._imagem_erro(no, exc.mensagem, tentar_reserva=True)
            return
        self._aplicar_bytes_imagem(no, dados, caminho_abs=absoluto)

    def _aplicar_bytes_imagem(self, no, dados, caminho_abs=None) -> None:
        refs = self._paineis.get(id(no))
        if refs is None:
            return
        refs["dados"] = dados  # F41: cache p/ refresh de transform
        try:
            if dados is None:
                raise ErroELiXX("Download vazio ou falhou.")
            tipo = self._tipo_imagem(no, dados, caminho_abs)
            if tipo == "svg":
                self._mostrar_svg(no, refs, dados.decode("utf-8",
                                                         errors="replace"))
                return
            foto = self._foto_raster(no, dados, caminho_abs)
            refs["rotulo"].configure(image=foto, text="")
            refs["fotos"].append(foto)  # sem ref: o Tk apaga a imagem!
            refs["carregada"] = True
            larg, alt = int(foto.width()), int(foto.height())
            if no.largura is None:
                no.largura = float(larg)
            if no.altura is None:
                no.altura = float(alt)
        except ErroELiXX as exc:
            self._imagem_erro(no, exc.mensagem, tentar_reserva=True)
        except Exception as exc:
            self._imagem_erro(no, f"imagem inválida ({exc})",
                              tentar_reserva=True)

    def _tipo_imagem(self, no, dados: bytes, caminho_abs) -> str:
        nome = (caminho_abs or no.caminho_recurso or "").lower()
        if nome.endswith(".svg"):
            return "svg"
        if dados[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if dados[:6] in (b"GIF87a", b"GIF89a"):
            return "gif"
        if dados[:2] == b"\xff\xd8":
            return "jpg"
        if nome.endswith((".png", ".gif", ".jpg", ".jpeg")):
            return "extensao"
        return "?"

    def _foto_raster(self, no, dados: bytes, caminho_abs):
        tk = self._tk
        tipo = self._tipo_imagem(no, dados, caminho_abs)
        Image, ImageTk = self._pillow()
        if tipo in ("png", "gif"):
            import base64
            import io

            if tipo == "png" and Image is not None and (
                    self._precisa_ajuste(no) or self._tem_transformacao(no)):
                return self._foto_pillow(no, io.BytesIO(dados))
            codificada = base64.b64encode(dados).decode("ascii")
            try:
                foto = tk.PhotoImage(data=codificada)
            except tk.TclError:
                raise ErroELiXX("PNG/GIF inválido ou corrompido.")
            return self._foto_ajustada(no, foto)
        if tipo == "jpg":
            if Image is None:
                raise ErroELiXX(
                    "JPEG precisa de Pillow (pip install pillow). "
                    "Sem ela: PNG e GIF funcionam nativos.")
            import io

            return self._foto_pillow(no, io.BytesIO(dados))
        if tipo == "extensao":
            raise ErroELiXX("Extensão de imagem não suportada.")
        raise ErroELiXX("Formato de imagem desconhecido (use PNG/GIF).")

    def _precisa_ajuste(self, no) -> bool:
        return (no.ajuste in ("preencher", "esticar")
                and no.largura is not None and no.altura is not None)

    def _tem_transformacao(self, no) -> bool:
        """Rotação ou escala não-unitária (Fase 10: via Pillow, se houver)."""
        sx, sy = self._escala_no(no)
        return (float(getattr(no, "rotacao", 0.0) or 0.0) % 360.0 != 0.0
                or sx != 1.0 or sy != 1.0)

    def _foto_ajustada(self, no, foto):
        if no.ajuste == "conter" and (no.largura or no.altura):
            alvo_l = int(no.largura or foto.width())
            alvo_a = int(no.altura or foto.height())
            fx = max(1, -(-foto.width() // max(1, alvo_l)))
            fy = max(1, -(-foto.height() // max(1, alvo_a)))
            fator = max(fx, fy)
            if fator > 1:
                try:
                    foto = foto.subsample(fator, fator)
                except self._tk.TclError:
                    pass
        return foto

    def _foto_pillow(self, no, origem):
        """Redimensiona (ajuste + escala Fase 10) e gira (Fase 10).

        Rotação em graus horários (convenção ELiXX); Pillow gira
        anti-horário, por isso o sinal negativo. Sem Pillow, o caminho
        nativo PhotoImage desenha sem rotação/escala (limitação honesta).
        """
        _Image, ImageTk = self._pillow()
        try:
            img = _Image.open(origem).convert("RGBA")
        except Exception:
            raise ErroELiXX("Imagem inválida ou corrompida.")
        sx, sy = self._escala_no(no)
        alvo_l = max(1, int((no.largura or img.width) * sx))
        alvo_a = max(1, int((no.altura or img.height) * sy))
        if no.ajuste == "conter":
            img.thumbnail((alvo_l, alvo_a))
        else:
            img = img.resize((alvo_l, alvo_a))
        rotacao = float(getattr(no, "rotacao", 0.0) or 0.0) % 360.0
        if rotacao:
            try:
                img = img.rotate(-rotacao, expand=True,
                                 resample=_Image.BICUBIC)
            except Exception:
                pass
        return ImageTk.PhotoImage(img)

    def _imagem_erro(self, no, mensagem: str, tentar_reserva=False) -> None:
        refs = self._paineis.get(id(no))
        if tentar_reserva and no.reserva and not getattr(
                no, "_reserva_tentada", False):
            no._reserva_tentada = True
            no.fonte_recurso = "arquivo"
            no.caminho_recurso = no.reserva
            self._carregar_imagem_local(no)
            return
        if refs is None:
            return
        try:
            refs["rotulo"].configure(
                image="", text=f"[imagem: {no.nome or '?'} — {mensagem}]")
        except self._tk.TclError:
            pass
        self.mostrar_mensagem(f"Imagem: {mensagem}")

    def _mostrar_svg(self, no, refs, texto: str) -> None:
        from ..multimidia.svg import parse_svg

        try:
            desenho = parse_svg(texto)
        except ErroELiXX as exc:
            self._imagem_erro(no, exc.mensagem, tentar_reserva=True)
            return
        tk = self._tk
        sx, sy = self._escala_no(no)
        base_l = int(no.largura or desenho.largura or 64)
        base_a = int(no.altura or desenho.altura or 64)
        # Fase 10: escala no tamanho (rotação de SVG não suportada no Tk).
        larg = max(1, int(base_l * sx))
        alt = max(1, int(base_a * sy))
        tela = tk.Canvas(refs["quadro"], width=larg, height=alt,
                         bg=refs["quadro"].cget("bg"),
                         highlightthickness=0)
        tela.pack()
        refs["rotulo"].pack_forget()
        self._pintar_svg(tela, desenho, larg, alt,
                         no.cor_hex or "#e6e8f0")
        refs["fotos"].append(tela)
        refs["carregada"] = True
        if no.largura is None:
            no.largura = float(larg)
        if no.altura is None:
            no.altura = float(alt)

    def _pintar_svg(self, tela, desenho, larg: int, alt: int,
                    cor_padrao: str) -> None:
        esc = min(larg / (desenho.largura or 1),
                  alt / (desenho.altura or 1))
        if esc <= 0:
            esc = 1.0
        for op in desenho.ops:
            try:
                self._pintar_op(tela, op, esc, cor_padrao)
            except self._tk.TclError:
                pass

    def _pintar_op(self, tela, op, esc: float, cor_padrao: str) -> None:
        tipo = op[0]
        if tipo == "rect":
            _t, x, y, w, h, est = op
            tela.create_rectangle(x * esc, y * esc, (x + w) * esc,
                                  (y + h) * esc,
                                  fill=self._cor_svg(est["fill"], cor_padrao),
                                  outline=self._cor_svg(est["stroke"],
                                                        cor_padrao),
                                  width=max(1, int(est["width"] * esc)))
        elif tipo == "oval":
            _t, cx, cy, r, est = op
            tela.create_oval((cx - r) * esc, (cy - r) * esc,
                             (cx + r) * esc, (cy + r) * esc,
                             fill=self._cor_svg(est["fill"], cor_padrao),
                             outline=self._cor_svg(est["stroke"],
                                                   cor_padrao),
                             width=max(1, int(est["width"] * esc)))
        elif tipo == "ellipse":
            _t, cx, cy, rx, ry, est = op
            tela.create_oval((cx - rx) * esc, (cy - ry) * esc,
                             (cx + rx) * esc, (cy + ry) * esc,
                             fill=self._cor_svg(est["fill"], cor_padrao),
                             outline=self._cor_svg(est["stroke"],
                                                   cor_padrao),
                             width=max(1, int(est["width"] * esc)))
        elif tipo == "line":
            _t, x1, y1, x2, y2, est = op
            tela.create_line(x1 * esc, y1 * esc, x2 * esc, y2 * esc,
                             fill=self._cor_svg(est["stroke"] or
                                                est["fill"], cor_padrao),
                             width=max(1, int(est["width"] * esc)))
        elif tipo == "poly":
            _t, pts, est, fechado = op
            coords = [c * esc for pt in pts for c in pt]
            if fechado:
                tela.create_polygon(
                    coords, fill=self._cor_svg(est["fill"], cor_padrao),
                    outline=self._cor_svg(est["stroke"], cor_padrao),
                    width=max(1, int(est["width"] * esc)))
            else:
                tela.create_line(
                    coords, fill=self._cor_svg(est["stroke"] or
                                               est["fill"] or "#000000",
                                               cor_padrao),
                    width=max(1, int(est["width"] * esc)))
        elif tipo == "text":
            _t, x, y, conteudo, tamanho, est = op
            tela.create_text(x * esc, y * esc, text=conteudo,
                             fill=self._cor_svg(est["fill"] or
                                                est["stroke"], cor_padrao),
                             font=("Segoe UI", max(6, int(tamanho * esc))))

    @staticmethod
    def _cor_svg(valor: str, cor_padrao: str) -> str:
        if not valor:
            return ""
        if valor == "currentcolor":
            return cor_padrao
        return valor

    def desenhar_icone(self, no, pai) -> object:
        """Ícone: SVG embutido (nome) ou arquivo SVG."""
        tk = self._tk
        quadro = tk.Frame(pai, bg=pai.cget("bg"))
        larg = int(no.largura or 24)
        alt = int(no.altura or 24)
        tela = tk.Canvas(quadro, width=larg, height=alt,
                         bg=pai.cget("bg"), highlightthickness=0)
        tela.pack()
        info = {"x": int(no.x), "y": int(no.y)}
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "icone", "canvas": tela}
        try:
            from ..multimidia.icones import obter
            from ..multimidia.svg import parse_svg

            if no.fonte_recurso == "arquivo":
                texto = self.recursos.bytes_local(
                    no.caminho_recurso).decode("utf-8", errors="replace")
            else:
                texto = obter(no.nome_icone or no.nome)
            desenho = parse_svg(texto)
            self._pintar_svg(tela, desenho, larg, alt,
                             no.cor_hex or "#e6e8f0")
        except ErroELiXX as exc:
            tela.create_text(larg / 2, alt / 2, text="?",
                             fill="#f87171")
            self.mostrar_mensagem(f"Ícone: {exc.mensagem}")
        if no.texto and no.texto != no.nome:
            rotulo = tk.Label(quadro, text=no.texto, bg=pai.cget("bg"),
                              fg=no.cor_hex or "#e6e8f0")
            rotulo.pack()
        self._aplicar_visibilidade(no)
        return quadro

    def desenhar_modal(self, no, pai) -> object:
        """Modal real: Toplevel com grab (foco preso até fechar)."""
        tk = self._tk
        try:
            mestre = pai.winfo_toplevel()
        except tk.TclError:
            mestre = self.raiz
        janela = tk.Toplevel(mestre)
        janela.title(no.titulo or no.nome or "Diálogo")
        largura = int(no.largura or 400)
        altura = int(no.altura or 250)
        try:
            px = mestre.winfo_x() + max(0, (mestre.winfo_width()
                                            - largura) // 2)
            py = mestre.winfo_y() + max(0, (mestre.winfo_height()
                                            - altura) // 2)
            janela.geometry(f"{largura}x{altura}+{px}+{py}")
        except tk.TclError:
            janela.geometry(f"{largura}x{altura}")
        janela.configure(bg=no.fundo_hex or "#1a1d29")
        janela.protocol("WM_DELETE_WINDOW",
                        lambda n=no: self._fechar_modal(n))
        area = tk.Frame(janela, bg=janela.cget("bg"))
        area.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        self._itens[id(no)] = (janela, {})
        self._paineis[id(no)] = {"kind": "modal", "area": area,
                                 "janela": janela}
        self._aplicar_visibilidade(no)
        return janela

    def _fechar_modal(self, no) -> None:
        objeto = no.ref_objeto
        if objeto is not None:
            objeto.visivel = False
            if self.executor is not None:
                try:
                    self.executor.disparar(objeto, "fechar")
                except Exception:
                    pass

    def desenhar_abas(self, no, pai) -> object:
        """Abas: botões + conteúdo alternado (estado opcional)."""
        tk = self._tk
        quadro = tk.Frame(pai, bg=pai.cget("bg"))
        faixa = tk.Frame(quadro, bg=pai.cget("bg"))
        faixa.pack(side=tk.TOP, fill=tk.X)
        conteudo = tk.Frame(quadro, bg=pai.cget("bg"))
        conteudo.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        abas = [f for f in no.filhos if f.tipo == "aba"]
        botoes = []
        paineis = {}
        for i, aba in enumerate(abas):
            titulo = aba.texto or aba.nome or f"Aba {i + 1}"
            botao = tk.Button(faixa, text=titulo,
                              command=lambda i=i, n=no:
                              self._clicar_aba(n, i))
            botao.pack(side=tk.LEFT, padx=2)
            botoes.append(botao)
            painel = tk.Frame(conteudo, bg=pai.cget("bg"))
            painel.place(relx=0, rely=0, relwidth=1, relheight=1)
            for neto in aba.filhos:
                self._desenhar(neto, painel)
            paineis[id(aba)] = painel
        info = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = int(no.largura)
        if no.altura:
            info["height"] = int(no.altura)
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "abas", "botoes": botoes,
                                 "paineis": paineis, "abas": abas,
                                 "ativa": no.ativa_index or 0}
        self._mostrar_aba(no, self._paineis[id(no)]["ativa"],
                          escrever=False)
        self._aplicar_visibilidade(no)
        return quadro

    def _clicar_aba(self, no, indice: int) -> None:
        self._mostrar_aba(no, indice, escrever=True)

    def _mostrar_aba(self, no, indice: int, escrever: bool) -> None:
        refs = self._paineis.get(id(no))
        if refs is None:
            return
        total = len(refs["abas"])
        indice = max(0, min(total - 1, indice)) if total else 0
        refs["ativa"] = indice
        try:
            for i, aba in enumerate(refs["abas"]):
                painel = refs["paineis"][id(aba)]
                botao = refs["botoes"][i]
                if i == indice:
                    painel.place(relx=0, rely=0, relwidth=1, relheight=1)
                    botao.configure(relief="sunken")
                else:
                    painel.place_forget()
                    botao.configure(relief="raised")
        except self._tk.TclError:
            pass
        if escrever and no.ligado_a and self.executor is not None:
            try:
                estado = getattr(self.executor, "estado", None)
                if estado is not None and estado.obter(
                        no.ligado_a) != indice:
                    estado.definir(no.ligado_a, indice)
            except Exception:
                pass

    def desenhar_menu(self, no, pai) -> object:
        """Menu: botões filhos enfileirados (sem posição manual)."""
        tk = self._tk
        quadro = tk.Frame(pai, bg=no.fundo_hex or pai.cget("bg"))
        for filho in no.filhos:
            self._desenhar(filho, quadro)
        try:
            quadro.update_idletasks()
        except tk.TclError:
            pass
        cursor = 8
        for filho in no.filhos:
            entrada = self._itens.get(id(filho))
            if entrada is None:
                continue
            try:
                larg = entrada[0].winfo_reqwidth()
                entrada[0].place(x=cursor, y=4)
                info = dict(entrada[1])
                info.update({"x": cursor, "y": 4})
                self._itens[id(filho)] = (entrada[0], info)
                cursor += larg + 8
            except tk.TclError:
                pass
        altura = 0
        for filho in no.filhos:
            entrada = self._itens.get(id(filho))
            if entrada is None:
                continue
            try:
                altura = max(altura, entrada[0].winfo_reqheight())
            except tk.TclError:
                pass
        info = {"x": int(no.x), "y": int(no.y)}
        if no.largura:
            info["width"] = int(no.largura)
        info["height"] = int(altura or 40) + 8
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "menu"}
        self._aplicar_visibilidade(no)
        return quadro

    @staticmethod
    def _celula(valor: object) -> str:
        if isinstance(valor, bool):
            return "verdadeiro" if valor else "falso"
        if isinstance(valor, (dict, list)):
            import json

            try:
                return json.dumps(valor, ensure_ascii=False)
            except (TypeError, ValueError):
                return str(valor)
        return "" if valor is None else str(valor)

    def desenhar_tabela(self, no, pai) -> object:
        """Tabela reativa (ttk.Treeview, stdlib)."""
        from tkinter import ttk

        colunas = list(no.colunas_nomes) or ["coluna"]
        tree = ttk.Treeview(pai, columns=colunas, show="headings",
                            height=max(3, int((no.altura or 150)) // 22))
        for coluna in colunas:
            tree.heading(coluna, text=coluna)
            tree.column(coluna, width=max(60, int(
                (no.largura or 300)) // max(1, len(colunas))))
        info = {"x": int(no.x), "y": int(no.y)}
        tree.place(**info)
        self._itens[id(no)] = (tree, info)
        self._paineis[id(no)] = {"kind": "tabela", "tree": tree,
                                 "atual": [], "colunas": colunas}
        self._aplicar_visibilidade(no)
        return tree

    def desenhar_audio(self, no, pai) -> object:
        tk = self._tk
        rotulo = tk.Label(pai, text=f"♪ {no.texto or no.nome} (áudio)",
                          bg=pai.cget("bg"), fg=no.cor_hex or "#e6e8f0",
                          font=("Segoe UI", max(6, int(round(no.fonte_px)))))
        info = {"x": int(no.x), "y": int(no.y)}
        rotulo.place(**info)
        self._itens[id(no)] = (rotulo, info)
        self._paineis[id(no)] = {"kind": "audio"}
        self._aplicar_visibilidade(no)
        return rotulo

    def desenhar_video(self, no, pai) -> object:
        tk = self._tk
        quadro = tk.Frame(pai, bg="#0b0d14", highlightthickness=1,
                          highlightbackground="#3a4058")
        larg = int(no.largura or 320)
        alt = int(no.altura or 180)
        aviso = tk.Label(quadro, text=f"▶ {no.texto or no.nome}\n"
                                      "(vídeo: backend futuro)",
                         bg="#0b0d14", fg="#9aa0b4")
        aviso.place(relx=0.5, rely=0.5, anchor="center")
        info = {"x": int(no.x), "y": int(no.y), "width": larg,
                "height": alt}
        quadro.place(**info)
        self._itens[id(no)] = (quadro, info)
        self._paineis[id(no)] = {"kind": "video"}
        self._aplicar_visibilidade(no)
        return quadro

    # ----- eventos: gesto → objeto → runtime -----

    def ao_interagir(self, no, evento: str) -> None:
        """Gesto → (linha, se for item dinâmico) → objeto → runtime."""
        if self.executor is None:
            return
        linha = getattr(self, "_linhas_por_no", {}).get(id(no))
        if linha is not None:
            with self.executor.contexto_ns(linha["ns"]):
                with self.executor.contexto_item(linha["item"],
                                                 linha["indice"]):
                    objeto = no.ref_objeto
                    if objeto is None:
                        return
                    self.executor.disparar(objeto, evento)
            return
        objeto = no.ref_objeto
        if objeto is None:
            return
        self.executor.disparar(objeto, evento)

    def _clique(self, no) -> None:
        self._gesto(no, "clicar")

    def _gesto(self, no, evento: str) -> None:
        try:
            self.ao_interagir(no, evento)
        except ErroELiXX as erro:
            self.mostrar_mensagem(f"Erro: {erro.mensagem}")

    # ----- loop -----

    def atualizar(self, dt_ms: float) -> None:
        """Sincroniza visibilidade + geometria runtime → tela.

        Só toca no widget quando algo mudou (sem churn por tick).
        """
        if self.cena is None:
            return
        for no in self.cena.janelas:
            for item in no.todos():
                self._aplicar_visibilidade(item)
                self._aplicar_geometria(item)
        self._aplicar_camadas()

    def _aplicar_camadas(self) -> None:
        """Ordem visual por camada (Fase 10: menor atrás, maior na frente).

        Estável: empate de camada mantém a ordem de criação. Só chama
        lift() quando a ordem muda (sem flicker por tick).
        """
        if not self._nos:
            return
        grupos: dict[int, list] = {}
        for nid in self._ordem:
            no = self._nos.get(nid)
            if no is None:
                continue
            pai = getattr(no, "pai", None)
            grupos.setdefault(id(pai) if pai is not None else 0, []).append(
                (float(getattr(no, "camada", 0.0) or 0.0),
                 int(getattr(no, "_seq", 0)), nid))
        assinatura: list = []
        for pid, filhos in grupos.items():
            filhos.sort(key=lambda t: (t[0], t[1]))
            assinatura.append((pid, tuple(nid for _, _, nid in filhos)))
        assinatura_t = tuple(assinatura)
        if assinatura_t == self._camadas_aplicadas:
            return
        self._camadas_aplicadas = assinatura_t
        for _pid, ordem in assinatura:
            for nid in ordem:
                entrada = self._itens.get(nid)
                if not entrada:
                    continue
                try:
                    entrada[0].lift()
                except self._tk.TclError:
                    pass

    def _aplicar_geometria(self, no) -> None:
        entrada = self._itens.get(id(no))
        if not entrada:
            return
        widget, _info = entrada
        try:
            if no.tipo == "tela":
                return  # preenche a janela (visibilidade sincronizada à parte)
            if no.tipo == "janela":
                chave = ("jan", int(no.largura or 800), int(no.altura or 600),
                         int(no.x), int(no.y), round(no.opacidade, 3))
                if self._geom.get(id(no)) == chave:
                    return
                self._geom[id(no)] = chave
                _k, larg, alt, x, y, alfa = chave
                widget.geometry(f"{larg}x{alt}+{x}+{y}")
                widget.attributes("-alpha", max(0.0, min(1.0, alfa)))
                return
            args: dict = {"x": int(no.x), "y": int(no.y)}
            sx, sy = self._escala_no(no)
            if no.largura is not None:
                args["width"] = max(1, int(no.largura * sx))
            if no.altura is not None:
                args["height"] = max(1, int(no.altura * sy))
            chave = ("w", args.get("x"), args.get("y"),
                     args.get("width"), args.get("height"))
            if self._geom.get(id(no)) == chave:
                return
            self._geom[id(no)] = chave
            widget.place(**args)
            # F41: escala/rotação mudaram? Regenera a foto com o
            # MESMO carregamento (bytes em cache; sem reparse).
            try:
                transf = (round(float(
                    getattr(no, "rotacao", 0.0) or 0.0), 3),
                    round(float(sx), 4), round(float(sy), 4))
            except (TypeError, ValueError):
                return
            if self._transf_aplicada.get(id(no)) == transf:
                return
            primeira = id(no) not in self._transf_aplicada
            self._transf_aplicada[id(no)] = transf
            if primeira:
                return
            refs = self._paineis.get(id(no))
            if refs is None or refs.get("kind") not in (
                    "imagem", "parte"):
                return
            if not refs.get("carregada"):
                return
            try:
                dados = refs.get("dados")
                if dados is None:
                    self._carregar_imagem_local(no)
                else:
                    self._aplicar_bytes_imagem(no, dados)
            except Exception:
                pass
        except self._tk.TclError:
            pass

    def _aplicar_visibilidade(self, no) -> None:
        entrada = self._itens.get(id(no))
        if not entrada:
            return
        widget, info = entrada
        objeto = no.ref_objeto
        visivel = objeto.visivel if objeto is not None else no.visivel
        refs = self._paineis.get(id(no))
        if refs is not None and refs.get("kind") == "modal":
            # Fase 08: modal é Toplevel (mostrar/esconder de verdade).
            try:
                if visivel:
                    widget.deiconify()
                    try:
                        widget.grab_set()
                    except self._tk.TclError:
                        pass
                else:
                    try:
                        widget.grab_release()
                    except self._tk.TclError:
                        pass
                    widget.withdraw()
            except self._tk.TclError:
                pass
            return
        try:
            mapeado = bool(widget.winfo_ismapped())
        except self._tk.TclError:
            return
        try:
            if visivel and not mapeado and info:
                widget.place(**info)
            elif not visivel and mapeado:
                widget.place_forget()
        except self._tk.TclError:
            pass

    def programar(self, ms: int, funcao) -> None:
        if self.raiz is not None:
            self.raiz.after(int(ms), funcao)

    def mostrar_mensagem(self, texto: str) -> None:
        self.ultima_mensagem = texto
        for barra in self._barras:
            try:
                barra.configure(text=texto)
            except self._tk.TclError:
                pass

    def focar_em(self, nome: str) -> bool:
        """Dá foco ao componente (ação focar). False se não achou."""
        if self.cena is None:
            return False
        no = self.cena.buscar(nome)
        if no is None:
            return False
        entrada = self._itens.get(id(no))
        if entrada is None:
            return False
        try:
            entrada[0].focus_set()
            return True
        except self._tk.TclError:
            return False

    def refrescar_tema(self) -> None:
        """Reaplica cores/fonte da Cena (troca sem reconstruir)."""
        if self.cena is None:
            return
        tk = self._tk
        for jan in self.cena.janelas:
            for no in jan.todos():
                entrada = self._itens.get(id(no))
                if entrada is None:
                    continue
                widget = entrada[0]
                try:
                    classe = widget.winfo_class()
                except tk.TclError:
                    continue
                try:
                    if classe in ("Frame", "Labelframe", "Toplevel", "Tk"):
                        if no.fundo_hex:
                            widget.configure(bg=no.fundo_hex)
                    elif classe == "Label":
                        if no.cor_hex:
                            widget.configure(fg=no.cor_hex)
                        fundo = no.fundo_hex
                        if fundo is None:
                            try:
                                fundo = widget.master.cget("bg")
                            except tk.TclError:
                                fundo = None
                        if fundo:
                            widget.configure(bg=fundo)
                        try:
                            atual = widget.cget("font")
                            widget.configure(font=self._fonte_tamanho(
                                atual, no.fonte_px))
                        except tk.TclError:
                            pass
                    elif classe == "Button":
                        if no.fundo_hex:
                            try:
                                widget.configure(bg=no.fundo_hex)
                            except tk.TclError:
                                pass
                        if no.cor_hex:
                            try:
                                widget.configure(fg=no.cor_hex)
                            except tk.TclError:
                                pass
                    elif classe == "Checkbutton":
                        if no.cor_hex:
                            widget.configure(fg=no.cor_hex)
                        try:
                            widget.configure(bg=widget.master.cget("bg"))
                        except tk.TclError:
                            pass
                except tk.TclError:
                    pass

    @staticmethod
    def _fonte_tamanho(atual, px: float) -> tuple:
        try:
            import tkinter.font as tkfont

            fonte = tkfont.nametofont(atual)
            return (fonte.cget("family"), max(6, int(round(px))))
        except Exception:
            return ("Segoe UI", max(6, int(round(px))))

    # ----- Fase 05: two-way binding (widget → estado) -----

    def _ligar_estado(self, no, widget, evento=None) -> None:
        """Se há ligado_a, escreve no estado ao interagir (sem loop:
        só escreve quando o valor mudou)."""
        if not no.ligado_a or self.executor is None:
            return
        if evento:
            widget.bind(evento, lambda _e, n=no: self._escrever_estado(n))
        else:
            widget.bind("<FocusOut>",
                        lambda _e, n=no: self._escrever_estado(n))
            widget.bind("<Return>",
                        lambda _e, n=no: self._escrever_estado(n))

    def _escrever_estado(self, no) -> None:
        # Fase 09: ligado_a local.* usa o ns do refs (linha) ou o topo.
        refs = self._paineis.get(id(no))
        if refs is None:
            return
        ligado = no.ligado_a
        if not ligado:
            return
        ns = refs.get("ns")
        try:
            kind = refs.get("kind")
            if kind == "entrada":
                valor = refs["campo"].get()
            elif kind == "checkbox":
                valor = bool(refs["var"].get())
            elif kind == "selecao":
                valor = refs["combo"].get()
            else:
                return
            self._gravar_ligacao(ligado, ns, valor)
        except Exception as exc:
            from ..erros import ErroELiXX

            if isinstance(exc, ErroELiXX):
                self.mostrar_mensagem(f"Erro: {exc.mensagem}")

    def _gravar_ligacao(self, ligado: str, ns, valor) -> None:
        """Escreve ligado_a em estado ou local (só se mudou)."""
        if self.executor is None:
            return
        if ligado.startswith("local."):
            chave = ligado.split(".", 1)[1]
            alvo = ns or self.executor.ns_topo()
            if alvo is None:
                return
            atual = self.executor._obter_local_ou_nulo(alvo, chave)
            if atual != valor:
                self.executor.definir_local(alvo, chave, valor)
            return
        estado = getattr(self.executor, "estado", None)
        if estado is None:
            return
        atual = estado.obter(ligado) if ligado in estado else None
        if atual != valor:
            estado.definir(ligado, valor)

    def _ler_ligacao(self, ligado: str, ns):
        """Lê ligado_a (None se ausente)."""
        if self.executor is None:
            return None
        if ligado.startswith("local."):
            chave = ligado.split(".", 1)[1]
            alvo = ns or self.executor.ns_topo()
            if alvo is None:
                return None
            return self.executor._obter_local_ou_nulo(alvo, chave)
        estado = getattr(self.executor, "estado", None)
        if estado is None:
            return None
        try:
            return estado.obter(ligado) if ligado in estado else None
        except Exception:
            return None

    # ----- reatividade: aplica pacotes do Vinculador -----

    def definir_valor(self, no, valor) -> None:
        """Atualiza o widget sem reconstruir a janela."""
        refs = self._paineis.get(id(no))
        entrada = self._itens.get(id(no))
        if no.tipo == "texto":
            if valor is not None and entrada is not None:
                try:
                    entrada[0].configure(text=str(valor))
                except self._tk.TclError:
                    pass
        elif no.tipo == "barra" and refs is not None:
            if valor is None:
                return
            try:
                largura = refs["largura"]
                tela = refs["canvas"]
                x = largura * float(valor) / 100.0
                tela.coords(refs["id"], 0, 0, x, tela.winfo_height() or 20)
                cor = ("#4ade80" if float(valor) < 60
                       else "#facc15" if float(valor) < 85 else "#f87171")
                tela.itemconfigure(refs["id"], fill=no.cor_hex or cor)
            except (self._tk.TclError, ValueError, TypeError):
                pass
        elif no.tipo == "grafico" and refs is not None:
            try:
                self._redesenhar_grafico(no, refs)
                if valor is not None:
                    refs["titulo"].configure(
                        text=f"{no.texto or no.nome} — {valor}")
            except self._tk.TclError:
                pass
        elif no.tipo == "lista" and refs is not None:
            if isinstance(valor, dict) and "linhas" in valor:
                # Fase 09: plano do GerenciadorListas (linhas dinâmicas).
                try:
                    self._reconciliar_linhas(no, valor)
                except self._tk.TclError:
                    pass
                return
            if isinstance(valor, int) and not isinstance(valor, bool):
                try:
                    caixa = refs["caixa"]
                    atual = caixa.curselection()
                    atual = atual[0] if atual else -1
                    if atual != valor:
                        caixa.selection_clear(0, "end")
                        caixa.selection_set(valor)
                        caixa.see(valor)
                except self._tk.TclError:
                    pass
                return
            if not isinstance(valor, list):
                return
            try:
                if valor != refs["atual"]:
                    caixa = refs["caixa"]
                    caixa.delete(0, "end")
                    for item in valor[:50]:
                        caixa.insert("end", item)
                    refs["atual"] = list(valor)
            except self._tk.TclError:
                pass
        elif no.tipo == "tabela" and refs is not None:
            if not isinstance(valor, list):
                return
            try:
                if valor != refs["atual"]:
                    tree = refs["tree"]
                    for item in tree.get_children():
                        tree.delete(item)
                    for linha in valor[:200]:
                        if isinstance(linha, dict):
                            tree.insert("", "end", values=[
                                self._celula(linha.get(c, "")) for c in
                                refs.get("colunas",
                                         no.colunas_nomes or ["coluna"])])
                        else:
                            tree.insert("", "end", values=[str(linha)])
                    refs["atual"] = list(valor)
            except self._tk.TclError:
                pass
        elif no.tipo == "abas" and refs is not None:
            if isinstance(valor, bool):
                return
            try:
                numero = int(valor)
            except (TypeError, ValueError):
                return
            self._mostrar_aba(no, numero, escrever=False)
        elif no.tipo == "indicador" and refs is not None:
            if not isinstance(valor, bool):
                return
            try:
                refs["canvas"].itemconfigure(
                    refs["id"], fill="#4ade80" if valor else "#f87171")
            except self._tk.TclError:
                pass
        elif no.tipo == "entrada" and refs is not None:
            if valor is None:
                return
            try:
                campo = refs["campo"]
                # Não briga com o usuário digitando (foco = pausa o push).
                foco = campo.focus_get() if hasattr(campo, "focus_get") else None
                if foco is not None and str(foco) == str(campo):
                    return
                atual = campo.get()
                novo = str(valor)
                if atual != novo:
                    campo.delete(0, "end")
                    campo.insert(0, novo)
            except self._tk.TclError:
                pass
        elif no.tipo == "checkbox" and refs is not None:
            if not isinstance(valor, bool):
                return
            try:
                if bool(refs["var"].get()) != valor:
                    refs["var"].set(valor)
            except self._tk.TclError:
                pass
        elif no.tipo == "selecao" and refs is not None:
            if not isinstance(valor, str):
                return
            try:
                combo = refs["combo"]
                if valor in list(combo.cget("values")) and combo.get() != valor:
                    combo.set(valor)
            except self._tk.TclError:
                pass

    def _ao_redimensionar(self, no, evento) -> None:
        """Fase 04: usuário redimensionou → recalcula relativos + layout
        (com debounce; sem loop porque só reage a mudança real)."""
        entrada = self._itens.get(id(no))
        if entrada is None or evento.widget is not entrada[0]:
            return
        if self._resize_id is not None and self.raiz is not None:
            try:
                self.raiz.after_cancel(self._resize_id)
            except self._tk.TclError:
                pass
            self._resize_id = None

        def aplicar():
            self._resize_id = None
            try:
                nova_larg = float(entrada[0].winfo_width())
                nova_alt = float(entrada[0].winfo_height())
            except self._tk.TclError:
                return
            if nova_larg == (no.largura or 0) and nova_alt == (no.altura or 0):
                return
            no.largura, no.altura = nova_larg, nova_alt
            from .cena import recalcular

            recalcular(self.cena)

        if self.raiz is not None:
            try:
                self._resize_id = self.raiz.after(150, aplicar)
            except self._tk.TclError:
                pass

    PALETA_GRAFICO = ("#4ade80", "#7aa2ff", "#facc15", "#f87171",
                       "#c084fc", "#22d3ee", "#fb923c", "#94a3b8")

    def _dados_grafico(self, no) -> list:
        """Série externa (Fase 07) ou histórico (modo legado)."""
        if no.serie:
            return list(no.serie[-120:])
        return list(no.historico[-60:])

    def _redesenhar_grafico(self, no, refs) -> None:
        tela = refs["canvas"]
        largura, altura = refs["largura"], refs["altura"]
        tela.delete("all")
        for fracao in (0.25, 0.5, 0.75):
            y = altura * fracao
            tela.create_line(0, y, largura, y, fill="#2a2e3f")
        pontos = self._dados_grafico(no)
        if len(pontos) < 1:
            return
        tipo = (no.tipo_grafico or "linha").lower()
        if tipo == "barras":
            self._grafico_barras(tela, pontos, largura, altura, no)
        elif tipo == "pizza":
            self._grafico_pizza(tela, pontos, largura, altura, no)
        elif tipo == "area":
            self._grafico_linha(tela, pontos, largura, altura, no,
                                preencher=True)
        else:
            if len(pontos) >= 2:
                self._grafico_linha(tela, pontos, largura, altura, no)

    def _grafico_linha(self, tela, pontos, largura, altura, no,
                       preencher=False) -> None:
        maximo = max(pontos) if max(pontos) > 0 else 1.0
        passo = largura / max(1, len(pontos) - 1) if len(pontos) > 1 else 0
        coords = []
        for i, v in enumerate(pontos):
            x = i * passo
            y = altura - max(0.0, v) / maximo * altura
            coords += [x, y]
        cor = no.cor_hex or "#4ade80"
        if preencher and len(coords) >= 4:
            tela.create_polygon(coords + [coords[-2], altura, coords[0],
                                          altura],
                                fill=cor, outline="", stipple="gray25")
        if len(coords) >= 4:
            tela.create_line(*coords, fill=cor, width=2)

    def _grafico_barras(self, tela, pontos, largura, altura, no) -> None:
        maximo = max(pontos) if max(pontos) > 0 else 1.0
        n = len(pontos)
        passo = largura / max(1, n)
        for i, v in enumerate(pontos):
            h = max(0.0, v) / maximo * altura
            cor = (no.cor_hex or self.PALETA_GRAFICO[i % len(
                self.PALETA_GRAFICO)])
            tela.create_rectangle(i * passo + 2, altura - h,
                                  (i + 1) * passo - 2, altura,
                                  fill=cor, outline="")

    def _grafico_pizza(self, tela, pontos, largura, altura, no) -> None:
        total = sum(max(0.0, v) for v in pontos)
        if total <= 0:
            return
        cx, cy = largura / 2.0, altura / 2.0
        raio = min(largura, altura) / 2.0 - 4
        inicio = 0.0
        for i, v in enumerate(pontos):
            fracao = max(0.0, v) / total * 360.0
            cor = (no.cor_hex if i == 0 and len(pontos) == 1
                   else self.PALETA_GRAFICO[i % len(self.PALETA_GRAFICO)])
            tela.create_arc(cx - raio, cy - raio, cx + raio, cy + raio,
                            start=inicio, extent=fracao, fill=cor,
                            outline="#14161f")
            inicio += fracao

    def executar_loop(self) -> None:
        if self.raiz is None:
            return
        self._ultimo = time.monotonic()
        self._tick()
        self.raiz.mainloop()

    def _tick(self) -> None:
        if not self._aberto or self.raiz is None:
            return
        agora = time.monotonic()
        dt_ms = (agora - self._ultimo) * 1000.0
        self._ultimo = agora
        self.atualizar(dt_ms)
        # Reatividade no MESMO loop (sem segundo mainloop concorrente).
        if self.vinculador is not None:
            try:
                for no, pacote in self.vinculador.atualizar(agora * 1000.0):
                    try:
                        self.definir_valor(no, pacote)
                    except Exception:
                        pass
            except Exception:
                pass
        # Fase 03: motor de animação avança com dt real; a geometria
        # aplicada em atualizar() no próximo tick reflete a Cena.
        if self.motor is not None:
            try:
                self.motor.atualizar(dt_ms)
            except ErroELiXX as erro:
                self.mostrar_mensagem(f"Erro: {erro.mensagem}")
        # Fase 06: fontes remotas periódicas (o executor agenda buscas
        # assíncronas; o resultado cai no estado e o Vinculador repassa).
        if self.executor is not None:
            try:
                self.executor.atualizar(dt_ms)
            except Exception:
                pass
        try:
            self.raiz.after(self.TICK_MS, self._tick)
        except self._tk.TclError:
            self._aberto = False

    def fechar(self) -> None:
        self._aberto = False
        if self.raiz is not None:
            try:
                self.raiz.destroy()
            except self._tk.TclError:
                pass
            self.raiz = None


registrar_renderizador("nativo", RenderizadorTk)
