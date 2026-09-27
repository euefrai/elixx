"""Workspace visual do Studio (Fase 29) — modelos headless + Tk opcional.

"O Studio é uma interface sobre o projeto ELiXX; ele não mantém uma
cópia paralela da lógica do projeto."

Camada sobre F25/F26/F27/F28 (nada reescrito): Layout, ArvoreProjeto,
EditorModelo, PreviewModelo, InspectorModelo, PainelAgent,
ConsoleModelo, DiagnosticosModelo e o orquestrador StudioWorkspace.
Tudo testável sem display; Tk só dentro de `montar_workspace_ui()`.
"""
from __future__ import annotations

from ..erros import ErroELiXX

__all__ = [
    "PAINEIS", "ABAS_INFERIORES", "PALAVRAS_CHAVE",
    "GEOMETRIAS_OK", "Layout", "ArvoreProjeto", "EditorModelo",
    "PreviewModelo", "InspectorModelo", "PainelAgent",
    "ConsoleModelo", "DiagnosticosModelo", "StudioWorkspace",
    "destacar_lexico", "montar_workspace_ui",
]

PAINEIS = ("project", "editor", "preview", "inspector", "console",
           "timeline", "diagnosticos", "agent")
"""Painéis do workspace (visibilidade alternável)."""

ABAS_INFERIORES = ("console", "timeline", "diagnosticos",
                     "plano", "raciocinio")
"""Abas da faixa inferior (F33 soma plano; F37, raciocínio)."""

GEOMETRIAS_OK = ((800, 500), (1024, 768), (1280, 720), (1366, 768),
                 (1600, 900), (1920, 1080), (2560, 1440),
                 (3840, 2160))
"""Resoluções verificadas (conteúdo útil, sem sobreposição)."""

PALAVRAS_CHAVE = ("janela", "tela", "personagem", "parte", "pose",
                  "expressao", "animacao", "componente", "estado",
                  "tema", "funcao", "acao", "importar", "dados",
                  "item", "mundo", "navegacao")
"""Destaque lexical (sem parser novo; ELiXX não tem comentários)."""


def _e_dado(valor, prof: int = 0) -> bool:
    import math

    if prof > 6:
        return False
    if valor is None or isinstance(valor, (bool, int, float)):
        return not (isinstance(valor, float)
                    and not math.isfinite(valor))
    if isinstance(valor, str):
        return True
    if isinstance(valor, list):
        return all(_e_dado(v, prof + 1) for v in valor)
    if isinstance(valor, dict):
        return all(isinstance(k, str) and _e_dado(v, prof + 1)
                   for k, v in valor.items())
    return False


# ----- destaque lexical (puro; sem compilador) -----

def destacar_lexico(texto: str) -> list[tuple]:
    """[(inicio, fim, classe)] com classe em palavra/string/numero.

    Offsets em chars (0-based). Determinístico; sem regex pesada.
    """
    if not isinstance(texto, str):
        raise ErroELiXX("Destaque precisa de texto.")
    marcas = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c == '"':
            j = i + 1
            while j < n and texto[j] != '"':
                j += 2 if texto[j] == "\\" and j + 1 < n else 1
            marcas.append((i, min(j + 1, n), "string"))
            i = min(j + 1, n)
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (texto[j].isalnum() or texto[j] == "_"):
                j += 1
            palavra = texto[i:j]
            if palavra in PALAVRAS_CHAVE:
                marcas.append((i, j, "palavra"))
            i = j
        elif c.isdigit():
            j = i
            while j < n and (texto[j].isdigit() or texto[j] in
                             ".%"):
                j += 1
            marcas.append((i, j, "numero"))
            i = j
        else:
            i += 1
    return marcas


# ----- layout -----

class Layout:
    """Painéis visíveis, tamanhos, aba inferior e modo compacto."""

    def __init__(self) -> None:
        self.visivel = {p: True for p in PAINEIS}
        self.tamanho = {p: 1.0 / len(PAINEIS) for p in PAINEIS}
        self.aba_inferior = "console"
        self.compacto = False
        self.geometria = (1280, 720)

    def alternar(self, painel: str) -> bool:
        if painel not in PAINEIS:
            raise ErroELiXX(f'Painel "{painel}" inválido.')
        self.visivel[painel] = not self.visivel[painel]
        return self.visivel[painel]

    def definir_aba(self, aba: str) -> str:
        if aba not in ABAS_INFERIORES:
            raise ErroELiXX(f'Aba "{aba}" inválida.')
        self.aba_inferior = aba
        return aba

    def redimensionar(self, painel: str, fracao: float) -> float:
        if painel not in PAINEIS:
            raise ErroELiXX(f'Painel "{painel}" inválido.')
        try:
            valor = float(fracao)
        except (TypeError, ValueError):
            raise ErroELiXX("Fração numérica.")
        import math

        if not math.isfinite(valor) or not 0.05 <= valor <= 0.9:
            raise ErroELiXX("Fração entre 0.05 e 0.9.")
        self.tamanho[painel] = valor
        return valor

    def definir_compacto(self, ativo: bool) -> dict:
        self.compacto = bool(ativo)
        if self.compacto:
            for p in ("project", "agent"):
                self.visivel[p] = False
            self.aba_inferior = "console"
        else:
            for p in PAINEIS:
                self.visivel[p] = True
        return self.paineis_visiveis()

    def paineis_visiveis(self) -> list[str]:
        return [p for p in PAINEIS if self.visivel[p]]

    def definir_geometria(self, largura: int, altura: int) -> tuple:
        try:
            larg, alt = int(largura), int(altura)
        except (TypeError, ValueError):
            raise ErroELiXX("Geometria inteira.")
        if larg < 800 or alt < 500:
            raise ErroELiXX("Mínimo 800x500 (sem sobreposição).")
        if larg > 3840 or alt > 2160:
            raise ErroELiXX("Máximo 3840x2160.")
        self.geometria = (larg, alt)
        return self.geometria

    def to_dict(self) -> dict:
        return {"visivel": dict(self.visivel),
                "tamanho": dict(self.tamanho),
                "aba_inferior": self.aba_inferior,
                "compacto": self.compacto,
                "geometria": list(self.geometria)}

    @staticmethod
    def from_dict(dados: dict) -> Layout:
        if not isinstance(dados, dict):
            raise ErroELiXX("Layout precisa de dict.")
        lay = Layout()
        for painel, vis in (dados.get("visivel") or {}).items():
            if painel in PAINEIS:
                lay.visivel[painel] = bool(vis)
        for painel, tam in (dados.get("tamanho") or {}).items():
            if painel in PAINEIS:
                lay.redimensionar(painel, tam)
        if dados.get("aba_inferior") in ABAS_INFERIORES:
            lay.aba_inferior = dados["aba_inferior"]
        lay.compacto = bool(dados.get("compacto", False))
        geo = dados.get("geometria") or [1280, 720]
        lay.definir_geometria(geo[0], geo[1])
        return lay

    def __repr__(self) -> str:
        return (f"Layout({len(self.paineis_visiveis())} visíveis, "
                f"aba={self.aba_inferior})")


# ----- árvore de projeto categorizada -----

class ArvoreProjeto:
    """Nós por categoria (arquivos reais + modelo F27 opcional)."""

    def __init__(self, workspace) -> None:
        from .workspace import Workspace

        if not isinstance(workspace, Workspace):
            raise ErroELiXX("ArvoreProjeto espera Workspace.")
        self.workspace = workspace
        self._nos: list[dict] = []
        self.selecionado: str | None = None

    def atualizar(self, modelo=None) -> list[dict]:
        """Releitura: .elixx + assets + (cenas/personagens do modelo)."""
        if not self.workspace.aberto:
            raise ErroELiXX("Projeto fechado.")
        nos = []
        for item in sorted(
                self.workspace.raiz.rglob("*.elixx"),
                key=lambda p: str(p)):
            try:
                rel = str(item.resolve().relative_to(
                    self.workspace.raiz)).replace("\\", "/")
            except ValueError:
                continue
            nos.append({"nome": item.name, "tipo": "arquivo",
                        "caminho": rel})
        base_assets = self.workspace.raiz / "assets"
        if base_assets.is_dir():
            for item in sorted(base_assets.rglob("*"),
                               key=lambda p: str(p)):
                if item.is_file():
                    try:
                        rel = str(item.resolve().relative_to(
                            self.workspace.raiz)).replace(
                                "\\", "/")
                    except ValueError:
                        continue
                    nos.append({"nome": item.name, "tipo": "asset",
                                "caminho": rel})
        if modelo is not None:
            for ent in modelo.entidades():
                if ent.tipo == "personagem":
                    nos.append({"nome": ent.nome,
                                "tipo": "personagem",
                                "caminho": ent.arquivo,
                                "id": ent.id})
                elif ent.tipo in ("tela", "janela"):
                    nos.append({"nome": ent.nome, "tipo": "cena",
                                "caminho": ent.arquivo,
                                "id": ent.id})
        nos.sort(key=lambda n: (n["tipo"], n["nome"]))
        self._nos = nos
        return list(nos)

    def nos(self, tipo: str | None = None) -> list[dict]:
        if tipo is None:
            return list(self._nos)
        return [n for n in self._nos if n["tipo"] == tipo]

    def selecionar(self, caminho: str) -> dict:
        for no in self._nos:
            if no["caminho"] == caminho:
                self.selecionado = caminho
                return no
        raise ErroELiXX(f'"{caminho}" fora da árvore.')

    def __repr__(self) -> str:
        return f"ArvoreProjeto({len(self._nos)} nós)"


# ----- editor enriquecido (sobre Documento/Editor F25) -----

class EditorModelo:
    """Documento + diagnósticos + navegação por linha."""

    def __init__(self, documento) -> None:
        from .documento import DocumentoELiXX

        if not isinstance(documento, DocumentoELiXX):
            raise ErroELiXX("EditorModelo espera DocumentoELiXX.")
        self.documento = documento
        self.diagnosticos: list = []

    def editar(self, texto: str) -> bool:
        """Define texto; retorna dirty (sem executar nada)."""
        self.documento.definir_texto(texto)
        return self.documento.dirty

    def salvar_marca(self) -> None:
        self.documento.marcar_salvo()

    def analisar(self) -> list:
        """Diagnósticos do compilador oficial (F25)."""
        from .editor import diagnosticar_texto

        self.diagnosticos = diagnosticar_texto(
            self.documento.texto, self.documento.caminho)
        return list(self.diagnosticos)

    def ir_para(self, linha: int) -> tuple:
        """Move cursor; retorna (linha, texto_da_linha)."""
        linhas = self.documento.texto.split("\n")
        if not 1 <= int(linha) <= len(linhas):
            raise ErroELiXX("Linha fora do documento.")
        self.documento.mover_cursor(int(linha), 1)
        return int(linha), linhas[int(linha) - 1]

    def ir_para_diagnostico(self, indice: int) -> tuple:
        diag = self.diagnosticos[int(indice)]
        linha = getattr(diag, "linha", None) or 1
        return self.ir_para(linha)

    def destaque(self) -> list[tuple]:
        return destacar_lexico(self.documento.texto)

    def modificado(self) -> bool:
        return self.documento.dirty

    def __repr__(self) -> str:
        return f"EditorModelo({self.documento.caminho})"


# ----- preview sincronizado -----

class PreviewModelo:
    """HeadlessPreview + entidades F27 selecionáveis (sem geometria
    fingida: a lista é esquemática e rotulada como tal)."""

    def __init__(self, app) -> None:
        from .app import StudioApp

        if not isinstance(app, StudioApp):
            raise ErroELiXX("PreviewModelo espera StudioApp.")
        self.app = app
        self.entidades: list[dict] = []
        self.selecionado: str | None = None
        self.ultimo_resumo: dict = {}

    def executar(self, texto: str, entrada: str = "main.elixx"
                 ) -> dict:
        resultado = self.app.preview.executar(texto, entrada)
        self.ultimo_resumo = dict(resultado.resumo)
        return resultado.to_dict()

    def sincronizar_modelo(self, modelo) -> list[dict]:
        """Entidades do F27 como cartões selecionáveis."""
        self.entidades = [
            {"id": e.id, "tipo": e.tipo, "nome": e.nome,
             "arquivo": e.arquivo}
            for e in modelo.entidades()
            if e.tipo in ("personagem", "tela", "janela",
                          "componente", "animacao")]
        self.entidades.sort(key=lambda e: (e["tipo"], e["id"]))
        return list(self.entidades)

    def selecionar(self, ent_id: str) -> dict:
        from .inspetor import Selecao

        for ent in self.entidades:
            if ent["id"] == ent_id:
                self.selecionado = ent_id
                tipo = {"personagem": "personagem"}.get(
                    ent["tipo"], "no")
                sel = Selecao(tipo, ent_id)
                self.app.inspetor.selecionar(sel)
                self.app.eventos.emitir("selecionado", sel.to_dict())
                return ent
        raise ErroELiXX(f'"{ent_id}" fora do preview.')

    def parar(self) -> None:
        self.app.preview.parar()

    def construir_canvas(self, cena, personagens=None,
                         modelo=None):
        """SceneCanvas real sobre cena/personagens (F40; aditivo)."""
        from .scene_canvas import SceneCanvas

        canvas = SceneCanvas(inspetor=self.app.inspetor,
                             eventos=self.app.eventos)
        canvas.montar(cena, personagens, modelo)
        self.canvas = canvas
        return canvas

    def __repr__(self) -> str:
        return (f"PreviewModelo({len(self.entidades)} entidades, "
                f"sel={self.selecionado})")


# ----- inspector estruturado + proposta via ChangeSet -----

class InspectorModelo:
    """Seções a partir do F27 (+ Character F12 quando vinculado)."""

    def __init__(self, app) -> None:
        from .app import StudioApp

        if not isinstance(app, StudioApp):
            raise ErroELiXX("InspectorModelo espera StudioApp.")
        self.app = app
        self.secoes: list[dict] = []
        self.personagem = None

    def inspecionar(self, modelo, ent_id: str,
                    personagem=None) -> list[dict]:
        """Monta seções só com campos reais (sem invenção)."""
        from .modelo.adaptador import resumo_para_inspetor

        viz = resumo_para_inspetor(modelo, ent_id)
        ent = viz["entidade"]
        secoes = [
            {"titulo": ent.get("nome") or ent["id"],
             "campos": {"Tipo": ent["tipo"],
                        "Arquivo": ent.get("arquivo", ""),
                        "Linha": ent.get("linha")}},
            {"titulo": "Relações",
             "campos": {"Saída": len(viz["de"]),
                        "Entrada": len(viz["para"])}},
        ]
        self.personagem = personagem
        if personagem is not None:
            secoes.append(
                {"titulo": "Personagem",
                 "campos": {
                     "Pose": personagem.pose_atual,
                     "Direção": personagem.direcao,
                     "Partes": ", ".join(sorted(
                         personagem.partes)),
                     "Poses": ", ".join(sorted(
                         personagem.poses))}})
            tf = {}
            for nome in sorted(personagem.partes)[:20]:
                no = personagem.partes[nome].no
                tf[nome] = (f"x={no.x:g} y={no.y:g} "
                            f"rot={no.rotacao:g}")
            secoes.append({"titulo": "Transform", "campos": tf})
        self.secoes = secoes
        return list(secoes)

    def propor_alteracao(self, ent_id: str, propriedade: str,
                         valor, arquivo: str,
                         descricao: str = "") -> dict:
        """Proposta estruturada → AgentChange (NÃO escreve arquivo).

        Tradução segura mínima: propriedades de transform de parte
        (`posicao/rotacao/escala/opacidade`) e `nome` viram proposta
        com instrução de aplicação manual via ChangeSet aprovado; o
        conteúdo exato é definido na aprovação (sem chute textual).
        """
        from .agent.mudancas import AgentChange

        permitidas = {"posicao", "rotacao", "escala", "opacidade",
                      "nome"}
        if propriedade not in permitidas:
            raise ErroELiXX(f'Propriedade "{propriedade}" sem '
                            "tradução segura (use ChangeSet "
                            "manual).")
        if not _e_dado(valor):
            raise ErroELiXX("Valor precisa ser JSON.")
        mudanca = AgentChange(
            arquivo, "editar", descricao=descricao or
            f"{ent_id}.{propriedade} = {valor!r} (aplicar via "
            "ChangeSet aprovado)",
            risco="medio")
        return {"entidade": ent_id, "propriedade": propriedade,
                "valor": valor,
                "mudanca": mudanca.to_dict(),
                "nota": "Proposta: aprove via ChangeSet F26; o "
                        "Inspector nunca escreve direto."}

    def __repr__(self) -> str:
        return f"InspectorModelo({len(self.secoes)} seções)"


# ----- painel agent (F28 sem LLM) -----

class PainelAgent:
    """Contexto/consulta/plano/proposta sobre F27+F28 (headless)."""

    def __init__(self, app) -> None:
        from .app import StudioApp

        if not isinstance(app, StudioApp):
            raise ErroELiXX("PainelAgent espera StudioApp.")
        self.app = app
        self.ultimo_contexto = None
        self.ultimo_plano = None
        self.ultima_proposta = None

    def contexto(self, modelo, ent_id: str) -> dict:
        from .agent.loop import construir_contexto_semantico

        ctx = construir_contexto_semantico(modelo, [ent_id])
        self.ultimo_contexto = ctx
        return {"entidades": len(ctx.entidades),
                "relacoes": len(ctx.relacoes),
                "arquivos": ctx.arquivos}

    def consultar(self, modelo, kind: str, **criterio) -> dict:
        from .agent.loop import consultar_modelo

        return consultar_modelo(modelo, kind, **criterio)

    def planejar(self, modelo, nome: str, tipo: str | None = None,
                 objetivo: str = "") -> dict:
        """Alvo → plano semântico (sem ChangeSet se ambíguo).

        Aceita nome ("Juh") ou id ("personagem:Juh"): id resolve
        direto pela entidade (nome/tipo reais, sem chute).
        """
        from .agent.intencao import AgentIntent
        from .agent.loop import (PlanoSemantico, consultar_modelo,
                                 resolver_alvo)

        nome_txt, tipo_txt = str(nome), tipo
        if ":" in nome_txt:
            achou = consultar_modelo(modelo, "id", id=nome_txt)
            if achou["total"] == 1:
                ent = achou["resultados"][0]
                nome_txt, tipo_txt = ent["nome"], ent["tipo"]
        alvo = resolver_alvo(modelo, nome_txt, tipo_txt)
        if alvo["status"] != "unico":
            return {"status": alvo["status"],
                    "candidatos": alvo.get("candidatos", [])}
        plano = PlanoSemantico(
            AgentIntent("modificar_interface",
                        objetivo=objetivo or f"alterar {nome}"),
            alvo=alvo,
            entidades=[alvo["entidade"]["id"]])
        self.ultimo_plano = plano
        return {"status": "plano", "alvo": alvo["entidade"]["id"],
                "entidades": plano.entidades}

    def propor(self, workspace, alteracoes: list,
               permissoes=None) -> dict:
        """Proposta → pré-condições → ChangeSet F26 (sem aplicar)."""
        from .agent.loop import gerar_changeset, verificar_precondicoes

        if self.ultimo_plano is None:
            raise ErroELiXX("Agent: planeje antes de propor.")
        self.ultimo_plano.alteracoes_propostas = [
            dict(a) for a in alteracoes]
        for a in self.ultimo_plano.alteracoes_propostas:
            if not _e_dado(a):
                raise ErroELiXX("Agent: alteração inválida.")
        pre = verificar_precondicoes(
            self.ultimo_plano, workspace, permissoes)
        if any(not c["ok"] for c in pre):
            return {"status": "precondicao_falhou",
                    "precondicoes": pre}
        cs = gerar_changeset(self.ultimo_plano)
        self.ultima_proposta = cs
        return {"status": "proposta", "mudancas": cs.revisar()}

    def __repr__(self) -> str:
        return "PainelAgent()"


# ----- console com categorias + diagnósticos -----

class ConsoleModelo:
    """Logs com categoria (INFO/WARNING/ERROR/AGENT/BUILD/PREVIEW)."""

    CATEGORIAS = ("INFO", "SUCCESS", "WARNING", "ERROR",
                  "AGENT", "BUILD", "PREVIEW")

    def __init__(self, app) -> None:
        from .app import StudioApp

        if not isinstance(app, StudioApp):
            raise ErroELiXX("ConsoleModelo espera StudioApp.")
        self.app = app
        self.entradas: list[dict] = []

    def registrar(self, categoria: str, mensagem: str) -> dict:
        cat = str(categoria).strip().upper()
        if cat not in self.CATEGORIAS:
            raise ErroELiXX(f'Categoria "{categoria}" inválida.')
        texto = str(mensagem).split("\n")[0][:300]
        if "Traceback" in texto:
            texto = "Erro interno (ver detalhe sem stack)."
        registro = {"categoria": cat, "mensagem": texto}
        self.entradas.append(registro)
        if cat == "ERROR":
            self.app.logs.error(texto)
        elif cat == "WARNING":
            self.app.logs.warning(texto)
        else:
            self.app.logs.info(f"[{cat}] {texto}")
        return registro

    def por_categoria(self, categoria: str) -> list[dict]:
        return [e for e in self.entradas
                if e["categoria"] == categoria]

    def limpar(self) -> None:
        self.entradas.clear()
        self.app.logs.limpar()

    def __repr__(self) -> str:
        return f"ConsoleModelo({len(self.entradas)} entradas)"


class DiagnosticosModelo:
    """Diagnósticos do editor com navegação (arquivo, linha)."""

    def __init__(self) -> None:
        self.itens: list = []

    def atualizar(self, diagnosticos: list) -> int:
        self.itens = list(diagnosticos)
        return len(self.itens)

    def resumo(self) -> dict:
        erros = sum(1 for d in self.itens
                    if getattr(d, "severidade", "") == "error")
        return {"total": len(self.itens), "erros": erros,
                "valido": erros == 0}

    def ir_para(self, indice: int) -> tuple:
        diag = self.itens[int(indice)]
        return (getattr(diag, "arquivo", ""),
                getattr(diag, "linha", None) or 1)

    def __repr__(self) -> str:
        return f"DiagnosticosModelo({len(self.itens)} itens)"


# ----- orquestrador -----

class StudioWorkspace:
    """Workspace visual: painéis + modelo + estado real (headless)."""

    def __init__(self, app) -> None:
        from .app import StudioApp

        if not isinstance(app, StudioApp):
            raise ErroELiXX("StudioWorkspace espera StudioApp.")
        self.app = app
        self.layout = Layout()
        self.arvore = ArvoreProjeto(app.workspace)
        self.editores: dict[str, EditorModelo] = {}
        self.preview = PreviewModelo(app)
        self.inspector = InspectorModelo(app)
        self.agent = PainelAgent(app)
        self.console = ConsoleModelo(app)
        self.diagnosticos = DiagnosticosModelo()
        from .cena import Timeline

        self.timeline = Timeline()
        self.modelo = None

    # ----- ciclo -----

    def criar_projeto(self, raiz, nome: str) -> dict:
        projeto = self.app.workspace.criar_projeto(raiz, nome)
        self.arvore.atualizar()
        self.console.registrar("INFO",
                               f"Projeto criado: {projeto.nome}")
        return {"projeto": projeto.nome,
                "arquivos": len(self.arvore.nos())}

    def abrir_projeto(self, raiz) -> dict:
        projeto = self.app.workspace.abrir_projeto(raiz)
        self.arvore.atualizar()
        self.console.registrar("INFO",
                               f"Projeto aberto: {projeto.nome}")
        return {"projeto": projeto.nome,
                "arquivos": len(self.arvore.nos())}

    def analisar(self):
        """Projeto → ModeloSemantico F27 (sem executar)."""
        from .modelo.adaptador import analisar_projeto
        from .modelo.modelo import ModeloSemantico

        from .modelo.validacao import validar_modelo

        self.app.workspace._exigir_aberto()
        modelo = ModeloSemantico(
            self.app.workspace.projeto.nome)
        total = analisar_projeto(modelo,
                                 self.app.workspace.raiz)
        total["valido"] = validar_modelo(modelo)["valido"]
        self.modelo = modelo
        self.arvore.atualizar(modelo)
        self.console.registrar(
            "BUILD", f"Modelo: {total['entidades']} entidades")
        return total

    def abrir_no_editor(self, caminho: str) -> EditorModelo:
        destino = self.app.workspace.resolver(caminho)
        if not destino.is_file():
            raise ErroELiXX(f'"{caminho}" não é arquivo.')
        from .documento import DocumentoELiXX

        if caminho not in self.editores:
            doc = DocumentoELiXX(
                caminho, destino.read_text(encoding="utf-8"))
            self.editores[caminho] = EditorModelo(doc)
        return self.editores[caminho]

    def salvar_editor(self, caminho: str) -> dict:
        editor = self.editores[caminho]
        destino = self.app.workspace.resolver(caminho)
        destino.write_text(editor.documento.texto,
                           encoding="utf-8")
        editor.salvar_marca()
        self.console.registrar("INFO", f"Salvo: {caminho}")
        return {"arquivo": caminho, "modificado": False}

    def estado(self) -> dict:
        """Estados reais (nada fingido)."""
        return {
            "salvo": all(not e.modificado()
                         for e in self.editores.values()),
            "modificacoes_pendentes": sorted(
                c for c, e in self.editores.items()
                if e.modificado()),
            "executando": bool(self.app.preview.rodando),
            "erro": sum(
                1 for d in self.diagnosticos.itens
                if getattr(d, "severidade", "") == "error"),
            "analisando": self.modelo is not None,
            "projeto": (self.app.workspace.projeto.nome
                        if self.app.workspace.aberto else None),
        }

    def __repr__(self) -> str:
        return f"StudioWorkspace({self.layout})"


# ----- Tk opcional (TUDO lazy; headless intacto) -----

VAZIOS = {
    "projeto": "(nenhum arquivo)",
    "preview": "(nada para mostrar)",
    "inspector": "(nenhum objeto selecionado)",
    "plano": "(nenhuma tarefa)",
    "raciocinio": "(nenhuma tarefa)",
    "console": "ELiXX Studio pronto.",
}
"""Empty states (mensagens curtas, sem área vazia muda)."""


def estado_vazio(painel: str) -> str:
    """Mensagem de estado vazio (painel conhecido ou erro)."""
    try:
        return VAZIOS[str(painel)]
    except KeyError:
        raise ErroELiXX(f'Painel "{painel}" desconhecido.')


def resumo_status(projeto=None, arquivo=None, sincronizado=False,
                  erros=0, prog=None, n_tools=0,
                  executando=False) -> str:
    """Texto da statusbar (puro; mesma regra da UI)."""
    parte_plano = (f"  Agent: {prog['concluidos']}/"
                   f"{prog['total']} etapas"
                   if prog and prog["total"] else "")
    if executando:
        fase = "Executando"
    elif erros:
        fase = "Ready com erros"
    elif prog is not None and not prog.get("total", 0):
        fase = "Waiting approval"
    elif n_tools:
        fase = f"{n_tools} tools executed"
    elif sincronizado:
        fase = "Context ready"
    else:
        fase = "Ready"
    return (f"ELiXX  {projeto or '(nenhum projeto)'}  "
            f"{arquivo or '(nenhum arquivo)'}  "
            f"{'● sincronizado' if sincronizado else '○ sem modelo'}  "
            f"{erros} erro(s){parte_plano}  {fase}")


LAYOUTS = {
    "DEFAULT": ("project", "editor", "preview", "inspector",
                "console", "timeline", "diagnosticos", "agent"),
    "FOCUS_AGENT": ("project", "preview", "inspector", "console",
                    "agent"),
    "FOCUS_CODE": ("project", "editor", "console", "diagnosticos",
                   "agent"),
    "FOCUS_PREVIEW": ("preview", "inspector", "console", "agent"),
    "CODE": ("project", "editor", "console", "diagnosticos", "agent"),
    "SCENE": ("project", "preview", "inspector", "console"),
    "AGENT": ("project", "preview", "agent", "console"),
    "REVIEW": ("editor", "preview", "inspector", "console",
               "diagnosticos"),
}
"""Presets F37 (+ adaptativos F39 CODE/SCENE/AGENT/REVIEW)."""


def aplicar_layout_nome(ws: StudioWorkspace, nome: str
                        ) -> list[str]:
    """Ativa preset (aditivo; resto do Layout intacto)."""
    chave = str(nome).strip().upper()
    if chave not in LAYOUTS:
        raise ErroELiXX(f'Layout "{nome}" inválido '
                        f'({", ".join(LAYOUTS)}).')
    visiveis = set(LAYOUTS[chave])
    for painel in Layout().paineis_visiveis():
        ws.layout.visivel[painel] = painel in visiveis
    ws.layout.compacto = False
    return ws.layout.paineis_visiveis()


def salvar_layout(ws: StudioWorkspace, relativo: str = ".elixx/layout.json") -> str:
    """Persiste painéis/aba/geometria (só dados locais, sem segredo)."""
    import json

    destino = ws.app.workspace.resolver(relativo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(ws.layout.to_dict(),
                                  ensure_ascii=False, sort_keys=True,
                                  indent=2), encoding="utf-8")
    return relativo


def carregar_layout(ws: StudioWorkspace, relativo: str = ".elixx/layout.json") -> bool:
    """Restaura layout se existir (False = mantém padrão)."""
    import json

    try:
        destino = ws.app.workspace.resolver(relativo)
    except ErroELiXX:
        return False
    if not destino.is_file():
        return False
    try:
        dados = json.loads(destino.read_text(encoding="utf-8"))
        ws.layout = Layout.from_dict(dados)
    except (ValueError, ErroELiXX):
        return False
    return True


def montar_workspace_ui(ws: StudioWorkspace):
    """Layout F29: toolbar | project/preview/inspector | bottom tabs.

    Cabeçalhos, redimensionável (PanedWindow), editor com números de
    linha + destaque lexical + estrela dirty, diagnósticos clicáveis,
    preview por cartões do F27, inspector em seções, agent com 3
    botões (Consultar/Planejar/Propor via F28), console com filtro.
    """
    import tkinter as tk
    from tkinter import ttk

    app = ws.app
    larg, alt = ws.layout.geometria
    janela = tk.Tk()
    janela.title("ELiXX Studio")
    janela.geometry(f"{larg}x{alt}")
    janela.minsize(800, 500)
    try:
        from .tema import aplicar_tema

        aplicar_tema(janela)
    except Exception:
        try:
            estilo = ttk.Style(janela)
            estilo.theme_use("clam")
        except Exception:
            pass

    # -- toolbar real (ações do StudioApp) --
    topo = ttk.Frame(janela)
    topo.pack(fill="x")
    ttk.Label(topo, text="ELiXX").pack(side="left", padx=4)
    estado_lbl = ttk.Label(topo, text="● parado")
    estado_lbl.pack(side="left", padx=8)

    def _refresh_estado():
        est = ws.estado()
        marca = ("● executando" if est["executando"]
                 else "● erro" if est["erro"] else "● parado")
        sufixo = "" if est["salvo"] else " ● pendente"
        estado_lbl.config(text=marca + sufixo)
        if "salvar" in botoes_topo:
            botoes_topo["salvar"].config(
                text="Salvar ●" if sufixo else "Salvar")
        if "parar" in botoes_topo:
            botoes_topo["parar"].config(
                style="Danger.TButton" if est["executando"]
                else "TButton")

    def _cmd(nome, alvo=""):
        from .comandos import StudioCommand

        try:
            app.executar_comando(StudioCommand(nome, alvo))
            if nome == "salvar" and alvo:
                _sincronizar_apos_salvar(alvo)
                if alvo in ws.editores:
                    _mostrar_editor(ws.editores[alvo])
                _recarregar_arvore()
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    def _sincronizar_apos_salvar(caminho: str) -> None:
        """Salvar → reparse → modelo → preview → inspector."""
        from .ux import AbasEditor  # noqa (uso do tipo no docstring)

        _ = AbasEditor
        try:
            texto = ws.app.workspace.resolver(
                caminho).read_text(encoding="utf-8")
        except OSError as exc:
            ws.console.registrar("ERROR", f"Ilegível: {exc}")
            return
        try:
            from .modelo.adaptador import atualizar_arquivo

            if ws.modelo is not None:
                atualizar_arquivo(ws.modelo, caminho, texto)
                ws.arvore.atualizar(ws.modelo)
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
            return
        try:
            ws.preview.executar(texto, caminho)
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        ws.console.registrar("INFO", f"Sincronizado: {caminho}")

    barra_status = ttk.Label(janela, text="ELiXX",
                               anchor="w")
    dicas = {
        "Salvar": "Salvar arquivo ativo (Ctrl+S)",
        "Executar": "Executar preview (F5)",
        "Parar": "Parar preview (Shift+F5)",
        "Compacto": "Alternar modo compacto",
    }

    def _dica(texto):
        def _entra(_e=None):
            barra_status.config(text=f"ELiXX — {texto}")
        return _entra

    botoes_topo = {}
    for rotulo, nome in (("Salvar", "salvar"),
                         ("Executar", "executar"),
                         ("Parar", "parar")):
        estilo = "Accent.TButton" if nome == "executar" else None
        botao = ttk.Button(topo, text=rotulo,
                           command=lambda n=nome: _cmd(
                               n, app.documentos.ativo or ""),
                           **({"style": estilo} if estilo else {}))
        botao.pack(side="left", padx=2)
        botao.bind("<Enter>", _dica(dicas[rotulo]))
        botao.bind("<Leave>", lambda _e: _refresh_barra())
        botoes_topo[nome] = botao
    ttk.Separator(topo, orient="vertical").pack(side="left",
                                                fill="y",
                                                padx=4)
    ttk.Button(topo, text="Compacto",
               command=lambda: (ws.layout.definir_compacto(
                   not ws.layout.compacto),
                   _refresh_estado())).pack(side="right",
                                            padx=2)
    var_layout = tk.StringVar(value="DEFAULT")
    tk.OptionMenu(topo, var_layout, "DEFAULT", "FOCUS_AGENT",
                  "FOCUS_CODE", "FOCUS_PREVIEW",
                  command=lambda nome: (
                      aplicar_layout_nome(ws, nome),
                      _refresh_estado())).pack(side="right",
                                               padx=2)

    def _palette():
        from .agent.interacao import CommandPalette

        paleta = CommandPalette()
        topo_pal = tk.Toplevel(janela)
        topo_pal.title("Command Palette (Ctrl+K)")
        topo_pal.geometry("480x300")
        entrada = ttk.Entry(topo_pal)
        entrada.pack(fill="x", padx=6, pady=6)
        lista = tk.Listbox(topo_pal)
        lista.pack(fill="both", expand=True, padx=6)

        def _recarregar(_e=None):
            lista.delete(0, "end")
            for cmd in paleta.buscar(entrada.get())[:30]:
                lista.insert("end",
                             f"{cmd['id']} — {cmd['titulo']}")

        def _executar(_e=None):
            try:
                item = lista.get(lista.curselection())
            except Exception:
                return
            cid = item.split(" — ", 1)[0]
            try:
                out = paleta.executar(app, cid)
                ws.console.registrar(
                    "INFO", f"palette: {cid} ok")
                if cid in ("executar_projeto", "parar_projeto"):
                    _refresh_estado()
                _ = out
            except ErroELiXX as exc:
                ws.console.registrar("ERROR", str(exc)[:200])
            topo_pal.destroy()

        entrada.bind("<KeyRelease>", _recarregar)
        entrada.bind("<Return>", _executar)
        lista.bind("<Double-Button-1>", _executar)
        entrada.focus_set()
        _recarregar()

    ttk.Button(topo, text="Comandos",
               command=_palette).pack(side="right", padx=2)

    # -- meio redimensionável --
    meio = tk.PanedWindow(janela, orient="horizontal",
                          sashrelief="raised")
    meio.pack(fill="both", expand=True)

    esq = ttk.Frame(meio, width=200)
    ttk.Label(esq, text="PROJECT",
              style="Header.TLabel").pack(anchor="w", pady=2)
    lista_arq = tk.Listbox(esq)
    lista_arq.pack(fill="both", expand=True)

    def _abrir_duplo(_evento=None):
        try:
            item = lista_arq.get(lista_arq.curselection())
        except Exception:
            return
        for no in ws.arvore.nos():
            if no["nome"] in item and \
                    no["tipo"] == "arquivo":
                try:
                    ed = ws.abrir_no_editor(no["caminho"])
                    _mostrar_editor(ed)
                    ws.console.registrar(
                        "INFO", f"Aberto: {no['caminho']}")
                except ErroELiXX as exc:
                    ws.console.registrar("ERROR",
                                         str(exc)[:200])
                break
        _refresh_estado()

    lista_arq.bind("<Double-Button-1>", _abrir_duplo)

    def _refresh_barra():
        est = ws.estado()
        diag = ws.diagnosticos.resumo()
        plano = getattr(ws, "plano_view", None)
        prog = plano.progresso() if plano is not None else None
        trace = getattr(ws, "_trace_tools", None)
        barra_status.config(text=resumo_status(
            est["projeto"], app.documentos.ativo,
            est["analisando"], diag["erros"], prog,
            len(trace.chamadas) if trace else 0,
            est["executando"]))

    def _recarregar_arvore():
        from .ux import formatar_arvore

        lista_arq.delete(0, "end")
        nos = ws.arvore.nos()
        if not nos:
            lista_arq.insert("end", "(nenhum arquivo)")
            return
        sujos = [c for c, e in ws.editores.items()
                 if e.modificado()] if hasattr(ws, "editores") \
            else []
        atual = app.documentos.ativo
        for linha in formatar_arvore(nos, atual, sujos):
            lista_arq.insert("end", linha)

    def _recarregar_preview():
        lista_prev.delete(0, "end")
        for ent in ws.preview.entidades:
            lista_prev.insert("end",
                              f"[{ent['tipo']}] {ent['id']} "
                              f"({ent['nome']})")

    centro = ttk.Frame(meio)
    ttk.Label(centro, text="PREVIEW",
              style="Header.TLabel").pack(anchor="w", pady=2)
    barra_prev = ttk.Frame(centro)
    barra_prev.pack(fill="x")
    modo_prev = {"modo": "Selecionar"}
    rotulo_modo = ttk.Label(barra_prev, text="Modo: Selecionar")
    rotulo_modo.pack(side="left")
    for modo in ("Selecionar", "Mover", "Zoom", "Ajustar"):
        ttk.Button(barra_prev, text=modo, width=9,
                   command=lambda m=modo: (
                       modo_prev.update(modo=m),
                       rotulo_modo.config(text=f"Modo: {m}"))
                   ).pack(side="left", padx=1)
    zoom_prev = {"nivel": 100}
    rotulo_zoom = ttk.Label(barra_prev, text="100%")
    rotulo_zoom.pack(side="left", padx=4)

    def _zoom_trocar(nivel):
        from .ux import ZOOM_NIVEIS

        if nivel not in ZOOM_NIVEIS:
            return
        zoom_prev["nivel"] = nivel
        rotulo_zoom.config(text=(f"{nivel}%"
                                 if nivel != "Ajustar"
                                 else "Ajustar"))
        try:
            tamanho = max(7, min(16, 9 + (nivel - 100) // 25)) \
                if nivel != "Ajustar" else 9
            lista_prev.config(font=("Segoe UI", tamanho))
        except Exception:
            pass
        ws.console.registrar("INFO", f"Preview: zoom {nivel}")

    tk.OptionMenu(barra_prev, tk.StringVar(value="100%"),
                  "50%", "75%", "100%", "125%", "150%",
                  "Ajustar",
                  command=lambda v: _zoom_trocar(
                      int(v[:-1]) if v != "Ajustar" else v)
                  ).pack(side="left", padx=2)
    ttk.Button(barra_prev, text="Executar",
               style="Accent.TButton",
               command=lambda: (_cmd(
                   "executar", app.documentos.ativo or ""),
                   rotulo_prev_status.config(
                       text="executando" if app.preview.rodando
                       else "parado"))
               ).pack(side="right", padx=2)
    rotulo_prev_status = ttk.Label(centro, text="parado")
    rotulo_prev_status.pack(anchor="w")
    quadro_viewport = ttk.Frame(centro, relief="flat", borderwidth=1)
    quadro_viewport.pack(fill="both", expand=True, padx=4, pady=4)
    lista_prev = tk.Listbox(quadro_viewport)
    lista_prev.pack(fill="both", expand=True)
    try:
        from .tema import ELIXX_COLORS

        lista_prev.config(background=ELIXX_COLORS["surface"],
                          foreground=ELIXX_COLORS["text"],
                          selectbackground=ELIXX_COLORS[
                              "selection"],
                          highlightthickness=0, borderwidth=0)
    except Exception:
        pass
    tela_cena = None
    try:
        from .scene_canvas import SceneCanvas, desenhar

        tela_cena = tk.Canvas(quadro_viewport, height=220,
                              highlightthickness=0,
                              borderwidth=0)
        tela_cena.pack(fill="both", expand=True)
        _texto_cena = ""
        try:
            _doc_cena = app.documentos.obter(
                app.documentos.ativo or "src/main.elixx")
            _texto_cena = _doc_cena.texto
        except Exception:
            _texto_cena = ""
        if _texto_cena.strip():
            from .scene_canvas import cena_de_texto

            _saida_cena = cena_de_texto(_texto_cena)
            if _saida_cena["ok"]:
                _canvas_cena = SceneCanvas(
                    inspetor=app.inspetor, eventos=app.eventos)
                _canvas_cena.montar(_saida_cena["cena"],
                                    _saida_cena["personagens"],
                                    ws.modelo)
                desenhar(tela_cena, _canvas_cena)
    except Exception:
        pass

    direita = ttk.Frame(meio, width=240)
    ttk.Label(direita, text="INSPECTOR",
              style="Header.TLabel").pack(anchor="w", pady=2)
    texto_insp = tk.Text(direita, height=20, width=30)
    texto_insp.pack(fill="both", expand=True)

    def _ver_codigo():
        from .codigo.localizacao import localizar_entidade

        sel = ws.preview.selecionado or ""
        if not sel or ws.modelo is None:
            ws.console.registrar("ERROR",
                                 "Selecione uma entidade.")
            return
        try:
            ent = next(e for e in ws.modelo.entidades()
                       if e.id == sel)
            texto = ws.app.workspace.resolver(
                ent.arquivo).read_text(encoding="utf-8")
            loc = localizar_entidade(ent, texto)
        except (ErroELiXX, OSError, StopIteration) as exc:
            ws.console.registrar(
                "ERROR",
                "Localização de código não disponível: "
                f"{str(exc)[:120]}")
            return
        try:
            ed = ws.abrir_no_editor(ent.arquivo)
            ed.ir_para(loc.inicio_linha)
            _mostrar_editor(ed)
            ws.console.registrar(
                "INFO",
                f"Código: {ent.arquivo}:{loc.inicio_linha}")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])

    ttk.Button(direita, text="Ver código",
               command=_ver_codigo).pack(fill="x")
    meio.add(esq, minsize=140)
    meio.add(centro, stretch="always")
    meio.add(direita, minsize=180)

    # -- editor com números + destaque + dirty --
    quadro_ed = ttk.Frame(janela)
    quadro_ed.pack(fill="x")
    ttk.Label(quadro_ed, text="CODE",
              style="Header.TLabel").pack(anchor="w", pady=2)
    ed_linhas = tk.Text(quadro_ed, width=4, height=10,
                        state="disabled")
    ed_linhas.pack(side="left", fill="y")
    ed_texto = tk.Text(quadro_ed, height=10, wrap="none")
    ed_texto.pack(side="left", fill="both", expand=True)
    try:
        from .tema import ELIXX_COLORS

        ed_texto.tag_config("palavra", foreground="#8ab8ff")
        ed_texto.tag_config("string", foreground="#7ce0a3")
        ed_texto.tag_config("numero", foreground="#d8a0ff")
        ed_texto.tag_config("nome", foreground="#e8e8f0",
                            font=("Consolas", 9, "bold"))
        ed_texto.config(background=ELIXX_COLORS["surface"],
                        foreground=ELIXX_COLORS["text"],
                        insertbackground=ELIXX_COLORS["text"],
                        highlightthickness=0, borderwidth=0)
        ed_linhas.config(background=ELIXX_COLORS["background"],
                         foreground=ELIXX_COLORS["text_muted"],
                         highlightthickness=0, borderwidth=0)
    except Exception:
        ed_texto.tag_config("palavra", foreground="blue")
        ed_texto.tag_config("string", foreground="green")
        ed_texto.tag_config("numero", foreground="purple")
        ed_texto.tag_config("nome", foreground="black")

    # abas de arquivo (uma por documento aberto)
    quadro_abas_ed = ttk.Frame(quadro_ed)
    quadro_abas_ed.pack(side="left", fill="y")

    def _recarregar_abas_ed():
        from .ux import AbasEditor

        abas = AbasEditor(app.documentos)
        for filho in quadro_abas_ed.winfo_children():
            filho.destroy()
        for item in abas.lista():
            ttk.Button(
                quadro_abas_ed, text=item["cabecalho"], width=16,
                command=lambda c=item["caminho"]: (
                    ws.abrir_no_editor(c),
                    _mostrar_editor(ws.abrir_no_editor(c)))
            ).pack(anchor="w", padx=1, pady=1)

    def _mostrar_editor(editor: EditorModelo):
        from .ux import destacar_semantico

        ed_texto.delete("1.0", "end")
        ed_texto.insert("1.0", editor.documento.texto)
        ed_linhas.config(state="normal")
        ed_linhas.delete("1.0", "end")
        ed_linhas.insert("1.0", "\n".join(
            str(i + 1) for i in range(editor.documento.linhas())))
        ed_linhas.config(state="disabled")
        for tag in ("palavra", "string", "numero", "nome"):
            ed_texto.tag_remove(tag, "1.0", "end")
        try:
            marcas = destacar_semantico(editor.documento.texto)
        except ErroELiXX:
            marcas = editor.destaque()
        for ini, fim, classe in marcas:
            ed_texto.tag_add(classe, f"1.0+{ini}c",
                             f"1.0+{fim}c")
        janela.title("ELiXX Studio" + (" ●" if editor.modificado()
                                       else ""))
        _recarregar_abas_ed()

    # -- abas inferiores --
    base = ttk.Frame(janela)
    base.pack(fill="x")
    botoes_abas = ttk.Frame(base)
    botoes_abas.pack(fill="x")
    corpo_aba = tk.Text(base, height=6)
    corpo_aba.pack(fill="x")
    timeline_lista = tk.Listbox(base, height=6)

    lista_plano = tk.Listbox(base, height=6)
    texto_detalhe = tk.Text(base, height=4)
    modo_diff = {"modo": "codigo"}

    quadro_grafo = ttk.Frame(base)
    lista_etapas = tk.Listbox(quadro_grafo, height=6, width=32)
    lista_etapas.pack(side="left", fill="y")
    tela_grafo = tk.Canvas(quadro_grafo, height=150,
                           background="white")
    tela_grafo.pack(side="left", fill="both", expand=True)
    entrada_busca = ttk.Entry(base)

    def _mostrar_aba(aba: str):
        ws.layout.definir_aba(aba)
        corpo_aba.pack_forget()
        timeline_lista.pack_forget()
        lista_plano.pack_forget()
        texto_detalhe.pack_forget()
        quadro_grafo.pack_forget()
        entrada_busca.pack_forget()
        quadro_zoom.pack_forget()
        if aba == "raciocinio":
            _mostrar_raciocinio()
            entrada_busca.pack(fill="x")
            quadro_grafo.pack(fill="x")
            quadro_zoom.pack(fill="x", anchor="w")
            return
        if aba == "plano":
            _mostrar_plano()
            lista_plano.pack(fill="x")
            texto_detalhe.pack(fill="x")
            return
        if aba == "timeline":
            timeline_lista.delete(0, "end")
            for alvo, blocos in ws.timeline.trilhas().items():
                for b in blocos:
                    timeline_lista.insert(
                        "end", f"{alvo}: {b['nome']} "
                               f"@{b['inicio']:g}ms")
            timeline_lista.pack(fill="x")
        else:
            if aba == "console":
                linhas = ws.console.entradas
            else:
                linhas = [{"categoria": "DIAG",
                            "mensagem": repr(d)}
                           for d in ws.diagnosticos.itens]
            corpo_aba.delete("1.0", "end")
            for e in linhas:
                corpo_aba.insert("end",
                                 f"[{e.get('categoria', '?')}] "
                                 f"{e.get('mensagem', '')}\n")
            corpo_aba.pack(fill="x")

    for aba in ("console", "timeline", "diagnosticos",
                  "plano", "raciocinio"):
        ttk.Button(botoes_abas, text=aba.capitalize(),
                   command=lambda a=aba: _mostrar_aba(a)).pack(
                       side="left")

    def _mostrar_plano():
        from .agent.planejamento import PainelPlano

        lista_plano.delete(0, "end")
        painel = getattr(ws, "plano_view", None)
        if painel is None or not isinstance(painel, PainelPlano):
            lista_plano.insert("end", "(nenhuma tarefa)")
            return
        icones = {"pendente": "○", "executando": "▶",
                  "concluido": "✓", "falhou": "✗",
                  "cancelado": "—", "bloqueado": "■"}
        for passo in painel.passos():
            marca = icones.get(passo["estado"], "?")
            lista_plano.insert(
                "end",
                f"{marca} {passo['id']}: {passo['descricao']}")
        prog = painel.progresso()
        lista_plano.insert("end", f"-- {prog['concluidos']}/"
                                  f"{prog['total']} "
                                  f"({prog['percentual']}%) --")

    def _detalhe_passo(_evento=None):
        from .agent.planejamento import PainelPlano

        painel = getattr(ws, "plano_view", None)
        if painel is None or not isinstance(painel, PainelPlano):
            return
        try:
            item = lista_plano.get(lista_plano.curselection())
        except Exception:
            return
        if item.startswith("(") or item.startswith("--"):
            return
        pid = item.split(":", 1)[0].split(" ", 1)[-1]
        try:
            detalhe = painel.selecionar_passo(pid)
            if modo_diff["modo"] == "semantico" and \
                    ws.modelo is not None:
                diff = painel.diff_passo(pid, ws.app.workspace,
                                         ws.modelo)
                corpo = diff.get("semantico",
                                 diff.get("codigo", "?"))
            else:
                diff = painel.diff_passo(
                    pid, ws.app.workspace, ws.modelo) \
                    if ws.modelo is not None else {}
                trocas = diff.get("trocas", []) if isinstance(
                    diff, dict) else []
                corpo = "; ".join(
                    f"+{t.get('adicionadas', [])}"
                    for t in trocas[:3]) or "(sem diff de código)"
            texto_detalhe.delete("1.0", "end")
            texto_detalhe.insert(
                "end",
                f"{detalhe['id']}: {detalhe['descricao']}\n"
                f"estado={detalhe['estado']} "
                f"deps={detalhe['dependencias']}\n{corpo}\n")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    lista_plano.bind("<<ListboxSelect>>", _detalhe_passo)

    def _alternar_diff():
        modo_diff["modo"] = "semantico" if modo_diff["modo"] == \
            "codigo" else "codigo"
        _detalhe_passo()

    ttk.Button(botoes_abas, text="Código/Semântico",
               command=_alternar_diff).pack(side="left")

    def _plano_revisar():
        from .agent.planejamento import PainelPlano

        painel = getattr(ws, "plano_view", None)
        if isinstance(painel, PainelPlano):
            ws.console.registrar(
                "AGENT", f"plano: {painel.resumo()}")
        _mostrar_aba("plano")
        _refresh_estado()

    def _plano_aprovar():
        from .agent.planejamento import PainelPlano

        painel = getattr(ws, "plano_view", None)
        if isinstance(painel, PainelPlano) and painel.aprovar():
            ws.console.registrar("AGENT", "plano aprovado")
        _refresh_estado()

    def _plano_cancelar():
        from .agent.planejamento import PainelPlano

        painel = getattr(ws, "plano_view", None)
        if isinstance(painel, PainelPlano):
            painel.cancelar()
            ws.console.registrar("AGENT", "plano cancelado")
        ws.inspetor.limpar()
        _refresh_estado()

    quadro_plano_btn = ttk.Frame(botoes_abas)
    quadro_plano_btn.pack(side="right")
    ttk.Button(quadro_plano_btn, text="Revisar",
               command=_plano_revisar).pack(side="left")
    ttk.Button(quadro_plano_btn, text="Aprovar",
               style="Accent.TButton",
               command=_plano_aprovar).pack(side="left")
    ttk.Button(quadro_plano_btn, text="Cancelar",
               style="Danger.TButton",
               command=_plano_cancelar).pack(side="left")

    # -- seleção preview → inspector via F27 --
    def _ao_selecionar_prev(_evento=None):
        try:
            item = lista_prev.get(lista_prev.curselection())
        except Exception:
            return
        ent_id = item.split("] ", 1)[-1].rsplit(" (", 1)[0]
        try:
            ent = ws.preview.selecionar(ent_id)
            secoes = ws.inspector.inspecionar(ws.modelo, ent_id)
            _render_inspetor(secoes)
            ws.console.registrar("INFO", f"Selecionado: {ent_id}")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    def _render_inspetor(secoes: list) -> None:
        from .ux import SecaoInspector

        ws._secoes_insp = [SecaoInspector(s["titulo"],
                                         s["campos"])
                           for s in secoes]
        texto_insp.delete("1.0", "end")
        for idx, sec in enumerate(ws._secoes_insp):
            marca = "▾" if sec.aberta else "▸"
            texto_insp.insert("end", f"{marca} {sec.titulo}\n",
                              (f"sec_{idx}",))
            texto_insp.tag_bind(
                f"sec_{idx}", "<Button-1>",
                lambda _e, i=idx: _alternar_secao(i))
            if sec.aberta:
                for k, v in sec.campos.items():
                    texto_insp.insert("end", f"  {k}: {v}\n")

    def _alternar_secao(indice: int) -> None:
        from .ux import SecaoInspector

        secoes = getattr(ws, "_secoes_insp", [])
        if 0 <= indice < len(secoes):
            abertas = [s.aberta for s in secoes]
            abertas[indice] = not abertas[indice]
            dados = [{"titulo": s.titulo, "campos": s.campos}
                     for s in secoes]
            ws._secoes_insp = [SecaoInspector(
                d["titulo"], d["campos"], aberta=a)
                for d, a in zip(dados, abertas)]
            texto_insp.delete("1.0", "end")
            for idx, sec in enumerate(ws._secoes_insp):
                marca = "▾" if sec.aberta else "▸"
                texto_insp.insert("end", f"{marca} {sec.titulo}\n",
                                  (f"sec_{idx}",))
                texto_insp.tag_bind(
                    f"sec_{idx}", "<Button-1>",
                    lambda _e, i=idx: _alternar_secao(i))
                if sec.aberta:
                    for k, v in sec.campos.items():
                        texto_insp.insert("end",
                                          f"  {k}: {v}\n")

    lista_prev.bind("<<ListboxSelect>>", _ao_selecionar_prev)

    # -- agent: 3 botões reais (F28, sem LLM) --
    quadro_agent = ttk.Frame(direita)
    quadro_agent.pack(fill="x")
    ttk.Label(quadro_agent, text="ELiXX AGENT",
              style="Header.TLabel").pack(anchor="w", pady=2)
    rotulo_provider = ttk.Label(quadro_agent,
                                text="Provider: MOCK / DETERMINISTIC")
    rotulo_provider.pack(anchor="w")
    rotulo_sessao = ttk.Label(quadro_agent, text="Sem sessão")
    rotulo_sessao.pack(anchor="w")

    def _nova_sessao():
        from .agent.interacao import AgentSession

        ws._sessao = AgentSession()
        hist_chat.delete("1.0", "end")
        rotulo_sessao.config(
            text=f"Sessão {ws._sessao.id} · IDLE")
        ws.console.registrar("AGENT", "nova sessão (nada apagado)")

    ttk.Button(quadro_agent, text="Nova sessão",
               command=_nova_sessao).pack(fill="x")
    rotulo_ctx = ttk.Label(quadro_agent, text="sem contexto")
    rotulo_ctx.pack(anchor="w")

    def _agent_consultar():
        try:
            sel = ws.preview.selecionado or ""
            ctx = ws.agent.contexto(ws.modelo, sel) if sel else \
                {"entidades": 0, "relacoes": 0, "arquivos": []}
            rotulo_ctx.config(
                text=f"ctx: {ctx['entidades']} ent")
            ws.console.registrar("AGENT",
                                 f"contexto: {ctx['entidades']}")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    def _agent_planejar_propor():
        try:
            sel = ws.preview.selecionado or ""
            info = ws.agent.planejar(ws.modelo, sel, None,
                                     "alteração via Studio")
            ws.console.registrar("AGENT", f"plano: {info}")
            if info.get("status") == "plano":
                hist_chat.insert(
                    "end",
                    f"Proposta: alvo={info['alvo']} "
                    f"({len(info['entidades'])} entidades). "
                    f"Revise na aba Plano; nada foi aplicado.\n")
                hist_chat.see("end")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    ttk.Button(quadro_agent, text="Consultar",
               command=_agent_consultar).pack(fill="x")
    ttk.Button(quadro_agent, text="Planejar/Propor",
               command=_agent_planejar_propor).pack(fill="x")

    # -- chat do Agent (F30: Mock/determinístico, sem LLM) --
    ttk.Label(quadro_agent, text="ELiXX AGENT (mock)").pack(
        anchor="w")
    hist_chat = tk.Text(quadro_agent, height=8, width=28)
    hist_chat.pack(fill="x")
    entrada_chat = ttk.Entry(quadro_agent)
    entrada_chat.pack(fill="x")

    def _chat_enviar(_evento=None):
        from .agent.interacao import AgentSession

        pedido = entrada_chat.get().strip()
        if not pedido:
            return
        entrada_chat.delete(0, "end")
        sessao = getattr(ws, "_sessao", None)
        if not isinstance(sessao, AgentSession):
            sessao = AgentSession()
            ws._sessao = sessao
        ambiente = {"modelo": ws.modelo,
                    "selecionado": ws.preview.selecionado or "",
                    "arquivo": app.documentos.ativo or ""}
        hist_chat.insert("end", f"Você: {pedido}\n")
        try:
            resposta = sessao.enviar(pedido, ambiente)
        except ErroELiXX as exc:
            hist_chat.insert("end",
                             f"Erro: {str(exc)[:160]}\n")
            ws.console.registrar("ERROR", str(exc)[:200])
            return
        if resposta.get("ok"):
            hist_chat.insert(
                "end",
                f"Agent: intenção {resposta['intencao']} → "
                f"operação {resposta['operacao']} "
                f"({resposta['entidades']} entidades). "
                f"Ver contexto/plano na aba Agent.\n")
        else:
            hist_chat.insert(
                "end",
                f"Agent: não suportado "
                f"({resposta.get('erro', '')[:140]})\n")
        hist_chat.see("end")
        ws.console.registrar("AGENT", f"chat: {pedido[:80]}")
        rotulo_sessao.config(
            text=f"Sessão {sessao.id} · {sessao.estado}")
        _refresh_estado()

    ttk.Button(quadro_agent, text="→",
               command=_chat_enviar).pack(fill="x")
    entrada_chat.bind("<Return>", _chat_enviar)

    # -- contexto da tarefa F34 (resumo + detalhe filtrável) --
    ttk.Label(quadro_agent, text="CONTEXTO DA TAREFA",
              style="Header.TLabel").pack(
        anchor="w")
    rotulo_ctx_tarefa = ttk.Label(quadro_agent,
                                  text="sem contexto")
    rotulo_ctx_tarefa.pack(anchor="w")
    entrada_objetivo = ttk.Entry(quadro_agent)
    entrada_objetivo.pack(fill="x")
    entrada_objetivo.insert(0, "objetivo da tarefa...")

    def _ctx_estado():
        ctx = getattr(ws, "_ctx_tarefa", None)
        if ctx is None:
            return None, "sem contexto"
        return ctx, (f"{len(ctx.entidades)} entidades, "
                     f"{len(ctx.relacoes)} relações, "
                     f"{len(ctx.arquivos)} arquivo(s)")

    def _ctx_construir():
        from .agent.contexto_tarefa import (
            ContextoConfig, ContextoTarefa, construir_contexto)

        if ws.modelo is None:
            ws.console.registrar("ERROR",
                                 "Sem modelo semântico.")
            return
        sel = ws.preview.selecionado or ""
        objetivo = entrada_objetivo.get().strip()
        if objetivo in ("", "objetivo da tarefa..."):
            objetivo = f"inspecionar {sel}" if sel else ""
        tarefa = ContextoTarefa(
            objetivo=objetivo, alvo="",
            entidade_selecionada=sel,
            arquivo_atual=app.documentos.ativo or "",
            excluir=sorted(getattr(ws, "_ctx_excluidos", set())))
        try:
            ctx = construir_contexto(ws.modelo, tarefa,
                                     ContextoConfig())
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
            return
        ws._ctx_tarefa = ctx
        ws._ctx_req = tarefa
        _, texto = _ctx_estado()
        rotulo_ctx_tarefa.config(text=texto)
        ws.console.registrar("AGENT", f"contexto: {texto}")
        _recarregar_chips()

    def _ctx_ver():
        import tkinter as tk

        ctx, texto = _ctx_estado()
        if ctx is None:
            ws.console.registrar("ERROR", "Construa o contexto.")
            return
        topo = tk.Toplevel(janela)
        topo.title("Contexto da tarefa")
        topo.geometry("520x420")
        var_filtro = tk.StringVar(value="Todas")
        categorias = ["Todas"] + sorted(
            {e.categoria for e in ctx.entidades})
        tk.OptionMenu(topo, var_filtro, *categorias).pack(
            anchor="w")
        lista = tk.Listbox(topo)
        lista.pack(fill="both", expand=True)
        detalhe = tk.Text(topo, height=8)
        detalhe.pack(fill="x")

        def _recarregar():
            from .agent.contexto_tarefa import ContextoTarefa as _CT

            _ = _CT
            lista.delete(0, "end")
            filtro = var_filtro.get()
            for e in ctx.entidades:
                if filtro != "Todas" and e.categoria != filtro:
                    continue
                marca = "✓" if e.origem == "manual" else "•"
                lista.insert("end",
                             f"{marca} {e.id} [{e.categoria}] "
                             f"{e.score:.2f}")

        def _mostrar(_ev=None):
            try:
                item = lista.get(lista.curselection())
            except Exception:
                return
            eid = item.split(" ", 2)[1]
            try:
                motivos = ctx.por_que(eid)
            except ErroELiXX:
                return
            ent = next(e for e in ctx.entidades if e.id == eid)
            detalhe.delete("1.0", "end")
            detalhe.insert(
                "end",
                f"{ent.id}\n{ent.tipo} · {ent.arquivo}\n"
                f"score {ent.score:.2f} · origem {ent.origem}\n"
                + "".join(f"- {m}\n" for m in motivos))

        def _alternar(incluir: bool):
            try:
                item = lista.get(lista.curselection())
            except Exception:
                return
            eid = item.split(" ", 2)[1]
            for e in ctx.entidades:
                if e.id == eid:
                    e.origem = "manual"
                    ws.console.registrar(
                        "AGENT",
                        f"{'incluído' if incluir else 'excluído'}: "
                        f"{eid} (registrado; reconstrua p/ aplicar)")
                    break
            _recarregar()

        lista.bind("<<ListboxSelect>>", _mostrar)
        var_filtro.trace_add(
            "write", lambda *_a: _recarregar())
        linha_btn = tk.Frame(topo)
        linha_btn.pack(fill="x")
        tk.Button(linha_btn, text="Incluir",
                  command=lambda: _alternar(True)).pack(
                      side="left")
        tk.Button(linha_btn, text="Excluir",
                  command=lambda: _alternar(False)).pack(
                      side="left")
        _recarregar()

    ttk.Button(quadro_agent, text="Construir contexto",
               command=_ctx_construir).pack(fill="x")
    ttk.Button(quadro_agent, text="Ver contexto",
               command=_ctx_ver).pack(fill="x")
    quadro_chips = ttk.Frame(quadro_agent)
    quadro_chips.pack(fill="x")

    def _recarregar_chips():
        for filho in quadro_chips.winfo_children():
            filho.destroy()
        ctx = getattr(ws, "_ctx_tarefa", None)
        if ctx is None:
            return
        for ent in ctx.entidades[:12]:
            nome = f"✓ {ent.nome or ent.id}"
            ttk.Button(
                quadro_chips, text=nome, width=14,
                command=lambda eid=ent.id: _chip_alternar(
                    eid)).pack(side="left", padx=1)

    def _chip_alternar(ent_id: str):
        from .agent.contexto_tarefa import construir_contexto

        req = getattr(ws, "_ctx_req", None)
        if req is None:
            return
        excluidos = set(getattr(ws, "_ctx_excluidos", set()))
        if ent_id in excluidos:
            excluidos.discard(ent_id)
        else:
            excluidos.add(ent_id)
        ws._ctx_excluidos = excluidos
        req.excluir = sorted(excluidos)
        try:
            ws._ctx_tarefa = construir_contexto(ws.modelo, req)
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
            return
        ws.console.registrar(
            "AGENT", f"contexto: {'excluído' if ent_id in excluidos else 'incluído'} {ent_id}")
        _, texto = _ctx_estado()
        rotulo_ctx_tarefa.config(text=texto)
        _recarregar_chips()

    # -- TOOLS (F36: trace determinístico, sem escrita) --
    ttk.Label(quadro_agent, text="TOOLS",
              style="Header.TLabel").pack(anchor="w", pady=2)
    lista_tools = tk.Listbox(quadro_agent, height=4)
    lista_tools.pack(fill="x")

    def _tools_executar():
        from .agent.ferramentas_semanticas import (
            AgentToolCall, SemanticPermissions, SemanticToolRegistry,
            ToolTrace, executar_chamada)

        sel = ws.preview.selecionado or ""
        nome = ""
        if ws.modelo is not None and sel:
            try:
                nome = ws.preview.entidades and next(
                    e["nome"] for e in ws.preview.entidades
                    if e["id"] == sel) or sel
            except StopIteration:
                nome = sel
        ambiente = _AmbienteTools(ws)
        registro = SemanticToolRegistry()
        permissoes = SemanticPermissions(["READ", "ANALYZE"])
        trace = ToolTrace()
        for tool_id, args in (
                ("buscar_entidade", {"nome": nome or "Juh"}),
                ("consultar_relacoes",
                 {"id": sel or "personagem:Juh"})):
            chamada = AgentToolCall(tool_id, args)
            trace.registrar(chamada)
            executar_chamada(registro, chamada, ambiente,
                             permissoes)
        ws._trace_tools = trace
        lista_tools.delete(0, "end")
        for i, chamada in enumerate(trace.chamadas, start=1):
            marca = "✓" if chamada.estado == "CONCLUIDA" else "×"
            lista_tools.insert(
                "end",
                f"{marca} {chamada.tool_id} "
                f"[{chamada.estado}]")
        ws.console.registrar(
            "AGENT", f"tools: {len(trace.chamadas)} chamadas")
        _refresh_estado()

    def _tools_detalhe(_evento=None):
        trace = getattr(ws, "_trace_tools", None)
        if trace is None:
            return
        try:
            idx = lista_tools.curselection()[0]
        except Exception:
            return
        chamada = trace.chamadas[idx]
        texto_insp.delete("1.0", "end")
        texto_insp.insert(
            "end",
            f"TOOL\n{chamada.tool_id}\n\n"
            f"ESTADO\n{chamada.estado}\n\n"
            f"ARGS\n{chamada.argumentos}\n\n")
        if chamada.resultado is not None:
            texto_insp.insert(
                "end", f"RESULTADO\n"
                       f"{chamada.resultado.mensagem[:300]}\n")

    lista_tools.bind("<<ListboxSelect>>", _tools_detalhe)
    ttk.Button(quadro_agent, text="Executar tools",
               command=_tools_executar).pack(fill="x")

    class _AmbienteTools:
        """Ambiente só-leitura p/ tools semânticas (sem escrita)."""

        def __init__(self, ws_ref) -> None:
            self.modelo = ws_ref.modelo
            self.workspace = ws_ref.app.workspace
            self.personagens = {}
            self.contexto = None
            self.preview = None
            self.plano_view = None
            self.rig = None

    # -- raciocínio: workflow + grafo 2D (F35, Canvas Tk) --
    RAC = {"espaco": None}

    def _espaco():
        from .agent.workspace import AgentWorkspace as _AW

        esp = getattr(ws, "raciocinio", None)
        if not isinstance(esp, _AW):
            esp = _AW(getattr(ws, "_tarefa_txt", ""))
            ws.raciocinio = esp
        RAC["espaco"] = esp
        return esp

    def _mostrar_raciocinio():
        esp = _espaco()
        lista_etapas.delete(0, "end")
        if not esp.estagios or all(
                v["estado"] == "pendente"
                for v in esp.estagios.values()):
            lista_etapas.insert("end", "(nenhuma tarefa)")
        marcas = {"pendente": "○", "processando": "◌",
                  "pronto": "✓", "atencao": "!",
                  "erro": "×", "atual": "→"}
        for nome in ("TASK", "CONTEXT", "OPERATIONS", "PLAN",
                     "CHANGES", "PREVIEW"):
            info = esp.estagios[nome]
            lista_etapas.insert(
                "end",
                f"[{marcas.get(info['estado'], '?')}] {nome}")
        _desenhar_grafo()

    def _desenhar_grafo():
        esp = _espaco()
        tela_grafo.delete("all")
        try:
            largura = int(tela_grafo.winfo_width()) or 400
            altura = int(tela_grafo.winfo_height()) or 150
        except Exception:
            largura, altura = 400, 150
        zoom = esp.vista["zoom"]
        ox, oy = esp.vista["pan"]
        for aresta in esp.arestas:
            if aresta.origem not in esp.nos or \
                    aresta.destino not in esp.nos:
                continue
            a, b = esp.nos[aresta.origem], esp.nos[aresta.destino]
            tela_grafo.create_line(
                (a.x - ox) * zoom + 10, (a.y - oy) * zoom + 10,
                (b.x - ox) * zoom + 10, (b.y - oy) * zoom + 10,
                fill="gray")
        for no in esp.visiveis():
            x = (no["x"] - ox) * zoom + 10
            y = (no["y"] - oy) * zoom + 10
            cor = "lightblue" if no["id"] == esp.selecao \
                else "white"
            tela_grafo.create_rectangle(x - 8, y - 8, x + 8, y + 8,
                                        fill=cor,
                                        tags=(f"no:{no['id']}",))
            tela_grafo.create_text(x, y + 18,
                                   text=no["rotulo"][:14],
                                   tags=(f"no:{no['id']}",))

    def _grafo_clique(evento):
        esp = _espaco()
        zoom = esp.vista["zoom"]
        ox, oy = esp.vista["pan"]
        achado = None
        for no in esp.visiveis():
            x = (no["x"] - ox) * zoom + 10
            y = (no["y"] - oy) * zoom + 10
            if abs(evento.x - x) < 12 and abs(evento.y - y) < 12:
                achado = no["id"]
                break
        if achado is None:
            return
        try:
            detalhe = esp.selecionar(achado)
            texto_insp.delete("1.0", "end")
            texto_insp.insert("end", f"{detalhe['id']}\n")
            for chave in ("tipo", "rotulo", "score"):
                texto_insp.insert("end",
                                  f"  {chave}: {detalhe[chave]}\n")
            for motivo in detalhe.get("motivos", [])[:6]:
                texto_insp.insert("end", f"  - {motivo}\n")
            ws.console.registrar("INFO",
                                 f"Grafo: {achado} selecionado")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _desenhar_grafo()
        _refresh_estado()

    def _grafo_duplo(_evento=None):
        esp = _espaco()
        if esp.selecao and ws.modelo is not None:
            try:
                esp.expandir(esp.selecao, ws.modelo)
                esp.layout()
            except ErroELiXX as exc:
                ws.console.registrar("ERROR", str(exc)[:200])
        _desenhar_grafo()

    _pan_arrasto = {"x": 0, "y": 0}

    def _pan_ini(evento):
        _pan_arrasto["x"], _pan_arrasto["y"] = evento.x, evento.y

    def _pan_move(evento):
        esp = _espaco()
        zoom = esp.vista["zoom"] or 1.0
        try:
            esp.mover_pan(((_pan_arrasto["x"] - evento.x) / zoom),
                          ((_pan_arrasto["y"] - evento.y) / zoom))
        except ErroELiXX:
            pass
        _pan_arrasto["x"], _pan_arrasto["y"] = evento.x, evento.y
        _desenhar_grafo()

    tela_grafo.bind("<Button-1>", _grafo_clique)
    tela_grafo.bind("<Double-Button-1>", _grafo_duplo)
    tela_grafo.bind("<ButtonPress-2>", _pan_ini)
    tela_grafo.bind("<B2-Motion>", _pan_move)

    def _grafo_busca(_evento=None):
        esp = _espaco()
        termo = entrada_busca.get().strip()
        if not termo:
            return
        try:
            achados = esp.buscar(termo, ws.modelo)
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
            return
        ws.console.registrar(
            "INFO", f"busca '{termo}': {len(achados)}")
        if achados:
            try:
                esp.selecionar(achados[0]["id"])
            except ErroELiXX:
                pass
        _desenhar_grafo()

    entrada_busca.bind("<Return>", _grafo_busca)

    def _grafo_zoom(direcao: int):
        esp = _espaco()
        try:
            if direcao > 0:
                esp.aproximar()
            elif direcao < 0:
                esp.afastar()
            else:
                esp.normalizar_zoom()
                esp.enquadrar()
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _desenhar_grafo()

    quadro_zoom = ttk.Frame(base)
    for rotulo, fun in (("+", lambda: _grafo_zoom(1)),
                        ("-", lambda: _grafo_zoom(-1)),
                        ("F", lambda: _grafo_zoom(0))):
        ttk.Button(quadro_zoom, text=rotulo, width=3,
                   command=fun).pack(side="left")

    # -- estado inicial --
    _recarregar_arvore()
    if ws.modelo is not None:
        ws.preview.sincronizar_modelo(ws.modelo)
        _recarregar_preview()
    else:
        lista_prev.insert("end", "(nada para mostrar)")
    texto_insp.insert("1.0", "(nenhum objeto selecionado)")
    if not ws.console.entradas:
        ws.console.registrar("INFO", "ELiXX Studio pronto.")
    _mostrar_aba("console")
    _refresh_estado()

    # -- barra de status (projeto | arquivo | sync | agent) --
    barra_status.pack(fill="x", side="bottom")
    _refresh_barra()

    # -- teclado (sem sobrescrever edição: só com plano/janela) --
    def _tecla_aprovar(_e=None):
        from .agent.planejamento import PainelPlano

        painel = getattr(ws, "plano_view", None)
        if isinstance(painel, PainelPlano):
            _plano_aprovar()

    def _tecla_cancelar(_e=None):
        _plano_cancelar()

    def _tecla_busca(_e=None):
        lista_arq.focus_set()

    def _tecla_comandos(_e=None):
        from .comandos import COMANDOS

        ws.console.registrar("INFO",
                             f"comandos: {', '.join(COMANDOS)}")
        _mostrar_aba("console")

    janela.bind("<Control-k>", lambda _e: _palette())
    janela.bind("<Control-K>", lambda _e: _palette())
    janela.bind("<Control-s>",
                lambda _e: _cmd("salvar",
                                app.documentos.ativo or ""))
    janela.bind("<Control-S>",
                lambda _e: _cmd("salvar",
                                app.documentos.ativo or ""))
    janela.bind("<F5>", lambda _e: _cmd(
        "executar", app.documentos.ativo or ""))
    janela.bind("<Shift-F5>", lambda _e: _cmd("parar"))
    janela.bind("<Control-p>", lambda _e: _tecla_busca())
    janela.bind("<Control-P>", lambda _e: _tecla_busca())
    janela.bind("<Control-Shift-P>", lambda _e: _tecla_comandos())
    janela.bind("<Control-Shift-p>", lambda _e: _tecla_comandos())
    janela.bind("<Control-Return>", lambda _e: _tecla_aprovar())
    janela.bind("<Escape>", lambda _e: _tecla_cancelar())

    def _tecla_grafo(_e=None):
        _mostrar_aba("raciocinio")

    def _tecla_workflow(_e=None):
        _mostrar_aba("plano")

    def _tecla_enquadrar(_e=None):
        try:
            _espaco().enquadrar()
        except ErroELiXX:
            pass
        _desenhar_grafo()

    def _tecla_busca_ctx(_e=None):
        if ws.layout.aba_inferior == "raciocinio":
            entrada_busca.focus_set()
        else:
            _tecla_busca()

    janela.bind("<Control-Shift-G>", lambda _e: _tecla_grafo())
    janela.bind("<Control-Shift-g>", lambda _e: _tecla_grafo())
    janela.bind("<Control-Shift-W>", lambda _e: _tecla_workflow())
    janela.bind("<Control-Shift-w>", lambda _e: _tecla_workflow())
    janela.bind("<Control-f>", lambda _e: _tecla_busca_ctx())
    janela.bind("<Control-F>", lambda _e: _tecla_busca_ctx())
    janela.bind("f", lambda _e: _tecla_enquadrar())
    janela.bind("F", lambda _e: _tecla_enquadrar())

    def _tecla_layout(numero: int):
        nomes = ["DEFAULT", "FOCUS_AGENT", "FOCUS_CODE",
                 "FOCUS_PREVIEW"]
        try:
            aplicar_layout_nome(ws, nomes[numero])
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    janela.bind("<Control-1>", lambda _e: _tecla_layout(0))
    janela.bind("<Control-2>", lambda _e: _tecla_layout(1))
    janela.bind("<Control-3>", lambda _e: _tecla_layout(2))
    janela.bind("<Control-4>", lambda _e: _tecla_layout(3))

    def _fechar():
        try:
            salvar_layout(ws)
        except ErroELiXX:
            pass
        app.fechar_ui()

    janela.protocol("WM_DELETE_WINDOW", _fechar)
    app.janela = janela
    ws._widgets = {"janela": janela, "arquivos": lista_arq,
                   "preview": lista_prev, "inspetor": texto_insp,
                   "editor": ed_texto, "plano": lista_plano,
                   "status": barra_status}
    return janela
