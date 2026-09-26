"""Reatividade da ELiXX — ligação componente ← dado/estado (Fase 05).

O Vinculador percorre a Cena e resolve cada vínculo:

- `origem: dados.fonte.campo` (lido nas fontes, sem versão);
- `origem: estado.nome` (lido no estado, com versão);
- `origem: <expressão>` (avaliada no executor; depende do que usar);
- `ligado_a: estado.nome` (two-way; a leitura inicial passa aqui).

Devolve pacotes (nó, valor) para o renderer aplicar via `definir_valor`.
Atualização mínima: versões evitam re-resolver estado intacto; o último
valor enviado evita reescrever widget igual. Sem callbacks encadeados
(pull no tick) — ciclos não causam recursão.

Métrica: se o estado tiver a chave `atualizacoes`, ela conta os ciclos
de alimentação (documentado; usado pelo dashboard).
"""
from __future__ import annotations

import time

HISTORICO_MAX = 60

_VAZIO = object()


def formatar_valor(valor: object, formato: str) -> str:
    """Formata um valor bruto para exibição (nunca levanta exceção)."""
    if formato == "json":
        try:
            import json

            return json.dumps(valor, ensure_ascii=False)
        except (TypeError, ValueError):
            pass
    try:
        if formato == "percentual":
            return f"{float(valor):g}%"
        if formato == "inteiro":
            return f"{int(float(valor))}"
        if formato == "gb":
            return f"{float(valor) / 1e9:.1f} GB".replace(".", ",")
        if formato == "mb":
            return f"{float(valor) / 1e6:.1f} MB".replace(".", ",")
    except (TypeError, ValueError):
        pass
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def numero_ou_nulo(valor: object) -> float | None:
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return numero


def formatar_item(item: object, formato: str) -> str:
    """Item de lista: dict/lista vira JSON legível; resto, texto."""
    if isinstance(item, (dict, list)):
        return formatar_valor(item, "json")
    return formatar_valor(item, formato or "texto")


def dependencias_origem(expr: object) -> tuple[set[str], bool]:
    """Chaves estado.* (e local:*) e se há dados.* numa expressão."""
    from ..compilador import ast as A

    if isinstance(expr, A.Membro):
        caminho = A.caminho_de_membro(expr)
        partes = caminho.split(".")
        if partes[0] == "estado" and len(partes) == 2:
            return {partes[1]}, False
        if partes[0] == "local" and len(partes) == 2:
            # Fase 09: resolvido contra o namespace vigente.
            return {"local:" + partes[1]}, False
        if partes[0] == "dados":
            return set(), True
        base_deps, base_dados = dependencias_origem(expr.base)
        return base_deps, base_dados
    if isinstance(expr, A.Binaria):
        esq, esq_d = dependencias_origem(expr.esquerda)
        dir_, dir_d = dependencias_origem(expr.direita)
        if expr.op == "nao":
            return dir_, dir_d
        return esq | dir_, esq_d or dir_d
    if isinstance(expr, A.ListaLit):
        deps: set[str] = set()
        tem_dados = False
        for item in expr.itens:
            sub, sub_d = dependencias_origem(item)
            deps |= sub
            tem_dados = tem_dados or sub_d
        return deps, tem_dados
    if isinstance(expr, A.Chamada):
        deps = set()
        tem_dados = False
        for arg in expr.args:
            sub, sub_d = dependencias_origem(arg)
            deps |= sub
            tem_dados = tem_dados or sub_d
        return deps, tem_dados
    return set(), False


class Vinculador:
    """Liga os nós com `origem`/`ligado_a` às fontes e ao estado."""

    def __init__(self, cena, fontes: dict, estado=None, executor=None,
                 intervalo_ms: int = 1000) -> None:
        self.cena = cena
        self.fontes = fontes
        self.estado = estado
        self.executor = executor
        self.intervalo_ms = intervalo_ms
        self.automatico = True
        self.ciclos = 0
        self.estatisticas = {"resolucoes": 0, "envios": 0,
                             "pulados_versao": 0, "pulados_iguais": 0}
        self._ultima_leitura = 0.0
        self._forcar = True  # primeira passada sempre lê
        # vínculo: dict(no, tipo, fonte, sub, expr, deps, tem_dados,
        #              versoes, ultimo)
        self.vinculos: list = []
        for janela in cena.janelas:
            for no in janela.todos():
                self._coletar(no)

    def _coletar(self, no) -> None:
        if getattr(no, "dinamica", False):
            return  # Fase 09: linhas dinâmicas via GerenciadorListas
        if no.origem:
            partes = no.origem.split(".")
            if len(partes) >= 3 and partes[0] == "dados":
                self.vinculos.append(self._novo(
                    no, "dados", fonte=partes[1],
                    sub=".".join(partes[2:])))
                return
        if no.origem_expr is not None:
            deps, tem_dados = dependencias_origem(no.origem_expr)
            self.vinculos.append(self._novo(
                no, "expr", expr=no.origem_expr, deps=deps,
                tem_dados=tem_dados))
            return
        if no.ligado_a:
            self.vinculos.append(self._novo(
                no, "estado", sub=no.ligado_a, deps={no.ligado_a}))

    @staticmethod
    def _novo(no, tipo, fonte=None, sub=None, expr=None, deps=None,
              tem_dados=False):
        return {"no": no, "tipo": tipo, "fonte": fonte, "sub": sub,
                "expr": expr, "deps": set(deps or ()),
                "tem_dados": tem_dados, "versoes": {},
                "ultimo": _VAZIO}

    def atualizar_agora(self) -> int:
        """Força releitura imediata. Retorna quantos vínculos atualizou."""
        self._forcar = True
        return len(self._alimentar(time.monotonic() * 1000.0))

    def primeira_carga(self) -> list:
        """Alimentação síncrona inicial. Retorna [(nó, pacote)]."""
        self._forcar = True
        return self._alimentar(time.monotonic() * 1000.0)

    def alternar(self) -> bool:
        """Liga/desliga a atualização automática. Retorna o novo estado."""
        self.automatico = not self.automatico
        return self.automatico

    def atualizar(self, agora_ms: float) -> list:
        """Chamado pelo tick. Retorna [(nó, pacote)] para o renderer."""
        if not self.automatico and not self._forcar:
            return []
        if not self._forcar and agora_ms - self._ultima_leitura < self.intervalo_ms:
            return []
        return self._alimentar(agora_ms)

    def _alimentar(self, agora_ms: float) -> list:
        forcado = self._forcar
        self._forcar = False
        self._ultima_leitura = agora_ms
        for fonte in self.fontes.values():
            try:
                fonte.atualizar()
            except Exception:
                pass
        self.ciclos += 1
        if self.estado is not None and "atualizacoes" in self.estado:
            try:
                self.estado.definir("atualizacoes", self.ciclos)
            except Exception:
                pass
        pacotes = []
        for vinc in self.vinculos:
            bruto = self._resolver(vinc, forcado)
            if bruto is _VAZIO:
                continue
            no = vinc["no"]
            pacote = self._pacote(no, bruto)
            if pacote is None:
                continue
            if not forcado and self._igual(pacote, vinc["ultimo"]):
                self.estatisticas["pulados_iguais"] += 1
                continue
            vinc["ultimo"] = pacote
            self.estatisticas["envios"] += 1
            pacotes.append((no, pacote))
        # Fase 09: linhas dinâmicas (GerenciadorListas; mesma forma).
        gerenciador = None
        if self.executor is not None:
            gerenciador = getattr(self.executor, "listas", None)
        if gerenciador is not None:
            try:
                for no, pacote in gerenciador.pacotes_todas(self.cena):
                    self.estatisticas["envios"] += 1
                    pacotes.append((no, pacote))
            except Exception:
                pass
        return pacotes

    @staticmethod
    def _igual(pacote, ultimo) -> bool:
        if ultimo is _VAZIO:
            return False
        try:
            return bool(pacote == ultimo)
        except Exception:
            return False

    def _resolver(self, vinc: dict, forcado: bool):
        """Resolve o valor bruto; _VAZIO = nada mudou (pular)."""
        tipo = vinc["tipo"]
        if tipo == "dados":
            fonte = self.fontes.get(vinc["fonte"])
            if fonte is None:
                return _VAZIO
            try:
                bruto = fonte.obter(vinc["sub"])
            except Exception:
                bruto = "indisponível"
            self.estatisticas["resolucoes"] += 1
            return bruto
        if self.estado is None:
            return _VAZIO
        if not forcado and vinc["deps"] and not vinc["tem_dados"]:
            intacto = all(
                self.estado.versao(k) == vinc["versoes"].get(k)
                for k in vinc["deps"])
            if intacto:
                self.estatisticas["pulados_versao"] += 1
                return _VAZIO
        if tipo == "estado":
            try:
                bruto = self.estado.obter(vinc["sub"])
            except Exception:
                bruto = "indisponível"
        else:  # expr
            if self.executor is None:
                return _VAZIO
            try:
                bruto = self.executor.avaliar(vinc["expr"])
            except Exception:
                bruto = "indisponível"
        vinc["versoes"] = {k: self.estado.versao(k) for k in vinc["deps"]}
        self.estatisticas["resolucoes"] += 1
        return bruto

    @staticmethod
    def _pacote(no, bruto: object):
        if no.tipo == "barra":
            numero = numero_ou_nulo(bruto)
            return max(0.0, min(100.0, numero)) if numero is not None else None
        if no.tipo == "grafico":
            # Fase 07: lista/tupla = série externa (substitui); número =
            # amostra do histórico (modo legado, ex. CPU). Só números.
            if isinstance(bruto, (list, tuple)):
                serie = [numero_ou_nulo(v) for v in bruto]
                serie = [v for v in serie if v is not None]
                if serie:
                    no.serie = serie[:120]
                    return formatar_valor(serie[-1],
                                          no.formato or "percentual")
                return None
            numero = numero_ou_nulo(bruto)
            if numero is not None:
                no.historico.append(numero)
                del no.historico[:-HISTORICO_MAX]
            return formatar_valor(bruto, no.formato or "percentual")
        if no.tipo == "lista":
            if isinstance(bruto, (list, tuple)):
                return [formatar_item(item, no.formato) for item in bruto]
            if isinstance(bruto, int) and not isinstance(bruto, bool):
                return bruto  # seleção (ligado_a) — renderer seleciona
            return [formatar_item(bruto, no.formato)]
        if no.tipo == "tabela":
            if isinstance(bruto, (list, tuple)):
                return [dict(item) if isinstance(item, dict) else item
                        for item in bruto]
            return None
        if no.tipo == "abas":
            numero = numero_ou_nulo(bruto)
            return int(numero) if numero is not None else None
        if no.tipo == "indicador":
            if isinstance(bruto, bool):
                return bruto
            if isinstance(bruto, str):
                return bruto.strip().lower() in ("verdadeiro", "true",
                                                 "on", "online", "1")
            return None
        if no.tipo == "checkbox":
            return bruto if isinstance(bruto, bool) else None
        if no.tipo in ("entrada", "selecao"):
            return None if bruto is None else formatar_valor(
                bruto, no.formato or "texto")
        return formatar_valor(bruto, no.formato)
