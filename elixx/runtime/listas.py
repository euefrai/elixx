"""Listas dinâmicas da ELiXX (Fase 09) — coleção vira N itens visuais.

O GerenciadorListas pertence ao runtime (não ao renderer): reconcilia
dados → linhas com identidade por chave, cria/destrói namespaces de
estado local e avalia bindings por linha com item+ns no contexto do
Executor. O renderer só desenha/remove widgets e despacha eventos com
a linha correspondente. Sem sistema paralelo: usa Memoria (nada novo),
Estado (versões), Vinculador (pacotes) e Cena (cópias NoVisual).
"""
from __future__ import annotations

import copy


def _literal(valor: object):
    """Literal AST → valor Python (padrões de estado local)."""
    from ..compilador import ast as A

    if isinstance(valor, A.TextoLit):
        return valor.valor
    if isinstance(valor, A.NumeroLit):
        return valor.valor
    if isinstance(valor, A.Booleano):
        return valor.valor
    if isinstance(valor, A.ListaLit):
        return [_literal(item) for item in valor.itens]
    return None


class GerenciadorListas:
    """Dono das linhas vivas: {id_lista: {chave: linha}}.

    linha = {"chave", "item", "indice", "ns", "copias": [NoVisual]}.
    """

    def __init__(self, executor) -> None:
        self.executor = executor
        self.linhas: dict[int, dict] = {}

    def limpar(self) -> None:
        self.linhas = {}

    def reconciliar(self, no_lista, valores: list,
                    chave_expr=None) -> dict:
        """Diff por chave: cria/atualiza/destrói linhas. Retorna plano
        {"linhas": [...], "removidas": [...]} para o renderer."""
        from ..compilador import ast as A

        id_lista = id(no_lista)
        anteriores = self.linhas.setdefault(id_lista, {})
        novas: dict = {}
        ordem: list = []
        for indice, item in enumerate(valores):
            chave = self._chave(chave_expr, item, indice, no_lista)
            if chave in novas:
                # Chave duplicada no mesmo lote: último vence, sem duplicar
                # a linha (identidade é por chave, documentado).
                linha = novas[chave]
                linha["item"] = item
                linha["indice"] = indice
                continue
            ordem.append(chave)
            if chave in anteriores:
                linha = anteriores[chave]
                linha["item"] = item
                linha["indice"] = indice
            else:
                ns = f"{no_lista.nome or 'lista'}#{chave}"
                linha = {"chave": chave, "item": item, "indice": indice,
                         "ns": ns, "copias": self._copiar_modelo(
                             no_lista, chave)}
                self._inicializar_ns(ns, linha["copias"])
            novas[chave] = linha
        removidas = [c for c in anteriores if c not in novas]
        for chave in removidas:
            ns = anteriores[chave]["ns"]
            self.executor.locais.pop(ns, None)
            self.executor._versoes_locais.pop(ns, None)
        self.linhas[id_lista] = novas
        return {"linhas": [novas[c] for c in ordem], "removidas": [
            {"chave": c, "copias": anteriores[c]["copias"]}
            for c in removidas]}

    def _chave(self, chave_expr, item, indice: int, no_lista) -> str:
        if chave_expr is None:
            return str(indice)
        ex = self.executor
        with ex.contexto_item(item, indice):
            try:
                valor = ex.avaliar(chave_expr)
            except Exception:
                return str(indice)
        return str(valor) if valor is not None else str(indice)

    def _copiar_modelo(self, no_lista, chave) -> list:
        """Cópias NoVisual por linha (nomes únicos p/ buscar)."""
        copias = copy.deepcopy(no_lista.modelo)
        sufixo = f"#{chave}"
        pilha = list(copias)
        while pilha:
            no = pilha.pop()
            if getattr(no, "nome", ""):
                no.nome = f"{no.nome}{sufixo}"
            pilha.extend(getattr(no, "filhos", []))
            pilha.extend(getattr(no, "modelo", []))
        return copias

    def _inicializar_ns(self, ns: str, copias: list) -> None:
        """Padrões do estado local vindos da definição (via def_origem)."""
        ex = self.executor
        if ns in ex.locais:
            return
        valores: dict = {}
        pilha = list(copias)
        vistos: set[str] = set()
        while pilha:
            no = pilha.pop()
            origem = getattr(no, "def_origem", None)
            if origem and origem not in vistos:
                vistos.add(origem)
                padroes = ex.defs.get(origem)
                if padroes is not None:
                    bloco = getattr(padroes, "estado", None)
                    if bloco is not None:
                        for prop in bloco.propriedades:
                            v = (prop.valores[0]
                                 if prop.valores else None)
                            valores[prop.nome] = _literal(v)
            pilha.extend(getattr(no, "filhos", []))
            pilha.extend(getattr(no, "modelo", []))
        ex.locais[ns] = valores
        ex._versoes_locais[ns] = {k: 0 for k in valores}

    def pacotes_todas(self, cena) -> list:
        """[(no_lista, plano)] p/ o Vinculador repassar ao renderer.

        plano = {"linhas": [{chave, copias, pacotes}], "removidas": [...]}.
        Só linhas novas ou com dependência mudada entram (mínimo).
        """
        out = []
        for jan in cena.janelas:
            for no in jan.todos():
                if not getattr(no, "dinamica", False):
                    continue
                plano = self._pacotes_lista(no)
                if plano is not None:
                    out.append((no, plano))
        return out

    def _pacotes_lista(self, no_lista) -> dict | None:
        ex = self.executor
        origem = getattr(no_lista, "origem_expr", None)
        if origem is None:
            return None
        try:
            bruto = ex.avaliar(origem)
        except Exception:
            bruto = "indisponível"
        valores = list(bruto) if isinstance(bruto, (list, tuple)) else []
        plano = self.reconciliar(no_lista, valores, no_lista.chave_expr)
        linhas_out = []
        for linha in plano["linhas"]:
            pacotes = self._pacotes_se_mudou(no_lista, linha)
            if pacotes is not None:
                linhas_out.append({"chave": linha["chave"],
                                    "ns": linha["ns"],
                                    "item": linha["item"],
                                    "indice": linha["indice"],
                                    "copias": linha["copias"],
                                    "pacotes": pacotes})
        if not linhas_out and not plano["removidas"]:
            return None
        return {"linhas": linhas_out, "removidas": plano["removidas"]}

    def _pacotes_se_mudou(self, no_lista, linha):
        """None se nada mudou (versões + identidade do item)."""
        ex = self.executor
        deps, tem_dados = self._deps_modelo(no_lista)
        versoes = {k: ex.estado.versao(k) for k in deps
                   if not k.startswith("local:")}
        for k in [d[6:] for d in deps if d.startswith("local:")]:
            versoes[f"local:{linha['ns']}.{k}"] = ex.versao_local(
                linha["ns"], k)
        anterior = linha.get("versoes")
        mesma_versao = anterior == versoes
        mesmo_item = linha.get("item_id") == id(linha["item"])
        if (mesma_versao and mesmo_item and not tem_dados
                and "pacotes" in linha):
            ex.listar_pulados = getattr(ex, "listar_pulados", 0) + 1
            return None
        linha["versoes"] = versoes
        linha["item_id"] = id(linha["item"])
        pacotes = self.pacotes_linha(no_lista, linha)
        linha["pacotes"] = pacotes
        return pacotes

    def _deps_modelo(self, no_lista) -> tuple[set[str], bool]:
        from ..visual.reativo import dependencias_origem
        from ..compilador import ast as A

        deps: set[str] = set()
        tem_dados = False
        pilha = list(no_lista.modelo)
        while pilha:
            no = pilha.pop()
            for prop in getattr(no, "propriedades", []):
                for valor in prop.valores:
                    sub, sub_d = dependencias_origem(valor)
                    deps |= sub
                    tem_dados = tem_dados or sub_d
            ligado = getattr(no, "ligado_a", None)
            if ligado:
                deps.add(f"local:{ligado}" if ligado.startswith(
                    "local.") else ligado)
            pilha.extend(getattr(no, "filhos", []))
            pilha.extend(getattr(no, "modelo", []))
        return deps, tem_dados

    def pacotes_linha(self, no_lista, linha: dict) -> list:
        """[(copia, pacote)] avaliados com item+ns da linha no contexto."""
        ex = self.executor
        pacotes = []
        with ex.contexto_ns(linha["ns"]):
            with ex.contexto_item(linha["item"], linha["indice"]):
                for copia in linha["copias"]:
                    for no, pacote in self._pacotes_subarvore(copia):
                        pacotes.append((no, pacote))
        return pacotes

    def _pacotes_subarvore(self, raiz) -> list:
        from ..visual.reativo import Vinculador

        pacotes = []
        pilha = [raiz]
        while pilha:
            no = pilha.pop()
            pacote = self._pacote_no(no)
            if pacote is not None:
                pacotes.append((no, pacote))
            pilha.extend(getattr(no, "filhos", []))
            pilha.extend(getattr(no, "modelo", []))
        return pacotes

    def _pacote_no(self, no):
        ex = self.executor
        origem = getattr(no, "origem_expr", None)
        if origem is None:
            ligado = getattr(no, "ligado_a", None)
            if not ligado:
                return None
            return self._ler_ligado(no, ligado)
        try:
            bruto = ex.avaliar(origem)
        except Exception:
            bruto = "indisponível"
        from ..visual.reativo import Vinculador

        return Vinculador._pacote(no, bruto)

    def _ler_ligado(self, no, ligado: str):
        ex = self.executor
        partes = ligado.split(".")
        try:
            if partes[0] == "estado":
                return ex.estado.obter(partes[1])
            if partes[0] == "local" and len(partes) == 2:
                ns = ex.ns_topo()
                if ns is None:
                    return None
                return ex.obter_local(ns, partes[1])
        except Exception:
            pass
        return None

    def despachar_no(self, copia, evento: str, linha: dict) -> bool:
        """Dispara evento de UMA cópia com item+ns da linha (M10)."""
        ref = getattr(copia, "ref_objeto", None)
        if ref is None or evento not in ref.eventos:
            return False
        ex = self.executor
        with ex.contexto_ns(linha["ns"]):
            with ex.contexto_item(linha["item"], linha["indice"]):
                ex.disparar(ref, evento)
                return True
