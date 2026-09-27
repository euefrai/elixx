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

ABAS_INFERIORES = ("console", "timeline", "diagnosticos")
"""Abas da faixa inferior (uma ativa por vez)."""

PALAVRAS_CHAVE = ("janela", "tela", "personagem", "parte", "pose",
                  "expressao", "animacao", "componente", "estado",
                  "tema", "funcao", "acao", "importar", "dados",
                  "item", "mundo", "navegacao")
"""Destaque lexical (sem parser novo; ELiXX não tem comentários)."""

GEOMETRIAS_OK = ((800, 500), (1024, 768), (1280, 720), (1366, 768),
                 (1920, 1080))
"""Resoluções verificadas (mínimo 800x500; sem sobreposição)."""


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

    CATEGORIAS = ("INFO", "WARNING", "ERROR", "AGENT", "BUILD",
                  "PREVIEW")

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

    def _cmd(nome, alvo=""):
        from .comandos import StudioCommand

        try:
            app.executar_comando(StudioCommand(nome, alvo))
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    for rotulo, nome in (("Salvar", "salvar"),
                         ("Executar", "executar"),
                         ("Parar", "parar")):
        ttk.Button(topo, text=rotulo,
                   command=lambda n=nome: _cmd(
                       n, app.documentos.ativo or "")).pack(
                           side="left", padx=2)
    ttk.Button(topo, text="Compacto",
               command=lambda: (ws.layout.definir_compacto(
                   not ws.layout.compacto),
                   _refresh_estado())).pack(side="right",
                                            padx=2)

    # -- meio redimensionável --
    meio = tk.PanedWindow(janela, orient="horizontal",
                          sashrelief="raised")
    meio.pack(fill="both", expand=True)

    esq = ttk.Frame(meio, width=200)
    ttk.Label(esq, text="PROJECT").pack(anchor="w")
    lista_arq = tk.Listbox(esq)
    lista_arq.pack(fill="both", expand=True)

    def _recarregar_arvore():
        lista_arq.delete(0, "end")
        for no in ws.arvore.nos():
            lista_arq.insert("end",
                             f"[{no['tipo']}] {no['nome']}")

    def _recarregar_preview():
        lista_prev.delete(0, "end")
        for ent in ws.preview.entidades:
            lista_prev.insert("end",
                              f"[{ent['tipo']}] {ent['id']} "
                              f"({ent['nome']})")

    centro = ttk.Frame(meio)
    ttk.Label(centro, text="PREVIEW").pack(anchor="w")
    lista_prev = tk.Listbox(centro)
    lista_prev.pack(fill="both", expand=True)

    direita = ttk.Frame(meio, width=240)
    ttk.Label(direita, text="INSPECTOR").pack(anchor="w")
    texto_insp = tk.Text(direita, height=20, width=30)
    texto_insp.pack(fill="both", expand=True)
    meio.add(esq, minsize=140)
    meio.add(centro, stretch="always")
    meio.add(direita, minsize=180)

    # -- editor com números + destaque + dirty --
    quadro_ed = ttk.Frame(janela)
    quadro_ed.pack(fill="x")
    ttk.Label(quadro_ed, text="CODE").pack(anchor="w")
    ed_linhas = tk.Text(quadro_ed, width=4, height=10,
                        state="disabled")
    ed_linhas.pack(side="left", fill="y")
    ed_texto = tk.Text(quadro_ed, height=10, wrap="none")
    ed_texto.pack(side="left", fill="both", expand=True)
    ed_texto.tag_config("palavra", foreground="blue")
    ed_texto.tag_config("string", foreground="green")
    ed_texto.tag_config("numero", foreground="purple")

    def _mostrar_editor(editor: EditorModelo):
        ed_texto.delete("1.0", "end")
        ed_texto.insert("1.0", editor.documento.texto)
        ed_linhas.config(state="normal")
        ed_linhas.delete("1.0", "end")
        ed_linhas.insert("1.0", "\n".join(
            str(i + 1) for i in range(editor.documento.linhas())))
        ed_linhas.config(state="disabled")
        for tag in ("palavra", "string", "numero"):
            ed_texto.tag_remove(tag, "1.0", "end")
        for ini, fim, classe in editor.destaque():
            ed_texto.tag_add(classe, f"1.0+{ini}c",
                             f"1.0+{fim}c")
        janela.title("ELiXX Studio" + (" ●" if editor.modificado()
                                       else ""))

    # -- abas inferiores --
    base = ttk.Frame(janela)
    base.pack(fill="x")
    botoes_abas = ttk.Frame(base)
    botoes_abas.pack(fill="x")
    corpo_aba = tk.Text(base, height=6)
    corpo_aba.pack(fill="x")
    timeline_lista = tk.Listbox(base, height=6)

    def _mostrar_aba(aba: str):
        ws.layout.definir_aba(aba)
        corpo_aba.pack_forget()
        timeline_lista.pack_forget()
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

    for aba in ("console", "timeline", "diagnosticos"):
        ttk.Button(botoes_abas, text=aba.capitalize(),
                   command=lambda a=aba: _mostrar_aba(a)).pack(
                       side="left")

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
            texto_insp.delete("1.0", "end")
            for s in secoes:
                texto_insp.insert("end", f"{s['titulo']}\n")
                for k, v in s["campos"].items():
                    texto_insp.insert("end", f"  {k}: {v}\n")
            ws.console.registrar("INFO", f"Selecionado: {ent_id}")
        except ErroELiXX as exc:
            ws.console.registrar("ERROR", str(exc)[:200])
        _refresh_estado()

    lista_prev.bind("<<ListboxSelect>>", _ao_selecionar_prev)

    # -- agent: 3 botões reais (F28, sem LLM) --
    quadro_agent = ttk.Frame(direita)
    quadro_agent.pack(fill="x")
    ttk.Label(quadro_agent, text="AGENT").pack(anchor="w")
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
        from .agent.inteligencia import AgentChat

        pedido = entrada_chat.get().strip()
        if not pedido:
            return
        entrada_chat.delete(0, "end")
        chat = getattr(ws, "_chat", None)
        if chat is None:
            chat = AgentChat()
            ws._chat = chat
        resposta = chat.enviar(pedido, ws.modelo)
        hist_chat.insert("end", f"Você: {pedido}\n")
        if resposta.get("ok"):
            inter = resposta["intencao"]
            hist_chat.insert(
                "end",
                f"Intent: ação={inter['acao']} "
                f"alvo={inter['alvo']} "
                f"params={inter['parametros']}\n"
                f"Plano: resolução="
                f"{resposta['resolucao'].get('status', '?')} "
                f"(Propor alteração na aba Agent)\n")
        else:
            hist_chat.insert(
                "end",
                f"Não suportado "
                f"({resposta.get('codigo', '?')}): "
                f"{resposta.get('motivo', '')[:120]}\n")
        hist_chat.see("end")
        ws.console.registrar("AGENT", f"chat: {pedido[:80]}")

    ttk.Button(quadro_agent, text="→",
               command=_chat_enviar).pack(fill="x")
    entrada_chat.bind("<Return>", _chat_enviar)

    # -- estado inicial --
    _recarregar_arvore()
    if ws.modelo is not None:
        ws.preview.sincronizar_modelo(ws.modelo)
        _recarregar_preview()
    _mostrar_aba("console")
    _refresh_estado()
    app.janela = janela
    ws._widgets = {"janela": janela, "arquivos": lista_arq,
                   "preview": lista_prev, "inspetor": texto_insp,
                   "editor": ed_texto}
    return janela
