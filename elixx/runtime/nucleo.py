"""Núcleo de execução da ELiXX (runtime mínimo da Fase 01).

Fluxo: AST validada → fábrica constrói Objetos → dispara eventos
'aparecer' em pré-ordem → comandos executados (ações, se, repetir,
funções). Toda saída das ações vai para ResultadoExecucao.saida.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

from ..compilador import ast as A
from ..cores import para_cor
from ..dados import FonteSistema
from ..erros import ErroExecucao
from .acoes import Contexto, executar_acao
from .estado import Estado
from .eventos import validar_evento
from .memoria import Memoria
from .objetos import FabricaObjetos, Objeto

LIMITE_REPETICAO = 1000


def _valor_literal(valor: object):
    """Converte literal da AST em valor Python (listas incluídas)."""
    if isinstance(valor, A.TextoLit):
        return valor.valor
    if isinstance(valor, A.NumeroLit):
        return valor.valor
    if isinstance(valor, A.Booleano):
        return valor.valor
    if isinstance(valor, A.CorLit):
        return valor.valor
    if isinstance(valor, A.ListaLit):
        return [_valor_literal(item) for item in valor.itens]
    return None


@dataclass
class ResultadoExecucao:
    saida: list[str] = field(default_factory=list)
    objetos: list[Objeto] = field(default_factory=list)
    avisos: list = field(default_factory=list)

    def texto_janelas(self) -> str:
        linhas = []
        for obj in self.objetos:
            larg, alt = obj.tamanho
            rotulo = "tela" if obj.tipo == "tela" else "janela"
            linhas.append(
                f"{rotulo} {obj.nome}: {larg:g}x{alt:g} "
                f"({len(obj.filhos)} componente(s))")
        return "\n".join(linhas)


class Executor:
    def __init__(self, fontes: dict | None = None) -> None:
        self.memoria = Memoria()
        self.funcoes: dict[str, A.Funcao] = {}
        # Fontes de dados (reatividade): {"sistema": FonteSistema(), ...}.
        # Testes injetam {"falsa": FonteFalsa(...)} — sem valores da máquina.
        self.fontes = dict(fontes) if fontes else {"sistema": FonteSistema()}
        self.fontes_remotas: dict = {}
        self._espelhos: dict = {}  # último snapshot espelhado p/ estado
        self.base_dir = "."
        self.estado = Estado()
        self.ctx = Contexto([], self.memoria)
        self.ctx.estado = self.estado
        # Fase 07: ações de mídia enxergam executor (base_dir) e vídeo.
        self.ctx.executor = self
        from ..multimidia.video import MotorVideo

        self.ctx.video = MotorVideo()
        # Fase 08: temas, navegação e renderer (nativo conecta renderer).
        from .navegacao import Navegador

        self.temas: dict = {}
        self.tema_atual: str | None = None
        self.navegador = Navegador(self)
        self.ctx.renderer = None
        # Fase 09: ações, contexto local/item e listas dinâmicas.
        from .listas import GerenciadorListas

        self.acoes: dict[str, A.AcaoDef] = {}
        self.defs: dict[str, object] = {}
        self.locais: dict[str, dict] = {}
        self._versoes_locais: dict[str, dict] = {}
        self.pilha_ns: list[str] = []
        self.item_atual: object = None
        self.indice_atual: int | None = None
        self.listas = GerenciadorListas(self)
        self.avisos: list[str] = []

    # ----- programa -----

    def executar(self, programa: A.Programa,
                 avisos: list | None = None,
                 base_dir: str = ".") -> ResultadoExecucao:
        fabrica = FabricaObjetos()
        self.funcoes = {f.nome: f for f in programa.funcoes}
        self.acoes = {a.nome: a for a in programa.acoes}
        self.defs = {d.nome: d for d in programa.componentes}
        # Fase 05: estado inicial ANTES de objetos/aparecer — todo
        # componente já nasce com o valor (nunca vazio até 1º evento).
        # Fase 09: locais estáticos (estado.<ns>__chave) semeados juntos.
        iniciais = self._valores_iniciais(programa.estado)
        for ns, valores in (programa.locais or {}).items():
            for chave, valor in valores.items():
                iniciais[f"{ns}__{chave}"] = valor
        self.estado = Estado(iniciais)
        self.ctx.estado = self.estado
        # Fase 09: namespaces dinâmicos começam vazios (linhas criam).
        self.locais = {}
        self._versoes_locais = {}
        self.pilha_ns = []
        self.item_atual = None
        self.indice_atual = None
        self.listas.limpar()
        self.base_dir = base_dir
        # Fase 06: constrói fontes declaradas (sem buscar ainda).
        self._construir_fontes(programa.fontes)
        # Fase 08: temas resolvidos + telas construídas + navegação.
        from .temas import resolver_temas

        self.temas = resolver_temas(programa.temas)
        self.tema_atual = next(iter(self.temas), None)
        raizes = [fabrica.de_janela(j) for j in programa.janelas]
        telas = [fabrica.de_janela(t, tipo="tela") for t in programa.telas]
        self.ctx.objetos = raizes + telas
        inicial = self._tela_inicial(telas)
        self.navegador.registrar(telas, inicial=inicial)
        for raiz in raizes + telas:
            for obj in raiz.todos():
                self.disparar(obj, "criar", silencioso=True)
        for raiz in raizes + telas:
            for obj in raiz.todos():
                self.disparar(obj, "aparecer", silencioso=True)
        return ResultadoExecucao(saida=list(self.ctx.saida),
                                 objetos=raizes + telas,
                                 avisos=list(avisos or []))

    # ----- contexto Fase 09 (local/item) -----

    @contextmanager
    def contexto_ns(self, ns: str):
        """Empilha namespace local (instância ou linha)."""
        self.pilha_ns.append(ns)
        try:
            yield ns
        finally:
            self.pilha_ns.pop()

    @contextmanager
    def contexto_item(self, item: object, indice: int):
        """Define item.* e item.indice durante a avaliação/despacho."""
        anterior_item, anterior_indice = self.item_atual, self.indice_atual
        self.item_atual, self.indice_atual = item, indice
        try:
            yield item
        finally:
            self.item_atual, self.indice_atual = (anterior_item,
                                                  anterior_indice)

    def ns_topo(self) -> str | None:
        return self.pilha_ns[-1] if self.pilha_ns else None

    def obter_local(self, ns: str, chave: str, *,
                    linha: int | None = None) -> object:
        valores = self.locais.get(ns)
        if valores is None or chave not in valores:
            from ..erros import sugerir

            conhecidas = sorted((valores or {}).keys())
            dica = (f" Você quis dizer: {', '.join(sugerir(chave, conhecidas))}?"
                    if conhecidas else "")
            raise ErroExecucao(
                f'Estado local não encontrado: "{chave}" em "{ns}".{dica}',
                linha=linha,
            )
        return valores[chave]

    def definir_local(self, ns: str, chave: str, valor: object,
                      *, linha: int | None = None) -> None:
        """Escrita local cria a chave (dinâmica); leitura exige existir."""
        valores = self.locais.setdefault(ns, {})
        versoes = self._versoes_locais.setdefault(ns, {})
        valores[chave] = valor
        versoes[chave] = versoes.get(chave, 0) + 1

    def versao_local(self, ns: str, chave: str) -> int:
        return self._versoes_locais.get(ns, {}).get(chave, -1)

    @staticmethod
    def _tela_inicial(telas: list) -> str | None:
        for tela in telas:
            estilo = getattr(tela, "estilo", {})
            inicial = estilo.get("inicial")
            from ..compilador import ast as _A

            if isinstance(inicial, _A.Booleano) and inicial.valor:
                return tela.nome
        return telas[0].nome if telas else None

    @staticmethod
    def _valores_iniciais(bloco) -> dict:
        iniciais: dict = {}
        if bloco is None:
            return iniciais
        for prop in bloco.propriedades:
            valor = prop.valores[0] if prop.valores else None
            iniciais[prop.nome] = _valor_literal(valor)
        return iniciais

    # ----- fontes declaradas (Fase 06) -----

    def _construir_fontes(self, definicoes: list) -> None:
        from ..dados.remoto import FonteArquivo, FonteRemota

        self.fontes_remotas = {}
        for fdef in definicoes or []:
            props = {p.nome: (p.valores[0] if p.valores else None)
                     for p in fdef.propriedades}
            blocos = {}
            for bloco in fdef.blocos:
                blocos[bloco.nome] = bloco.propriedades
            alvo = "estado." + fdef.nome
            if "para" in props and props["para"] is not None:
                alvo = A.caminho_de_membro(props["para"])
            chave = alvo.split(".")[1]
            self.estado.garantir(chave)
            if "arquivo" in props:
                fonte = FonteArquivo(
                    nome=fdef.nome, caminho=str(props["arquivo"].valor),
                    base_dir=self.base_dir, alvo=alvo)
            else:
                fonte = FonteRemota(
                    nome=fdef.nome,
                    url=str(props["url"].valor),
                    metodo=self._texto_prop(
                        props, "metodo", "método",
                        padrao="GET").upper() or "GET",
                    cabecalhos=self._literais(blocos.get("cabecalhos", [])),
                    parametros=self._literais(blocos.get("parametros", [])),
                    corpo_raw={p.nome: (p.valores[0] if p.valores else None)
                               for p in blocos.get("corpo", [])} or None,
                    timeout_s=self._tempo_prop(props, "tempo_limite", 10.0),
                    intervalo_s=self._tempo_prop(props, "atualizar", None),
                    alvo=alvo)
                fonte.avaliar_corpo = lambda f=fonte: self._avaliar_corpo(f)
            self.fontes_remotas[fdef.nome] = fonte
            self.fontes[fdef.nome] = fonte

    @staticmethod
    def _texto_prop(props: dict, *nomes, padrao: str = "") -> str:
        for nome in nomes:
            if nome in props and props[nome] is not None:
                return str(props[nome].valor)
        return padrao

    @staticmethod
    def _tempo_prop(props: dict, nome: str, padrao) :
        if nome in props and props[nome] is not None:
            from ..unidades import tempo_para_ms

            medida = props[nome]
            return tempo_para_ms(medida.valor, medida.unidade) / 1000.0
        return padrao

    @staticmethod
    def _literais(propriedades: list) -> dict:
        saida = {}
        for prop in propriedades:
            valor = prop.valores[0] if prop.valores else None
            if isinstance(valor, A.TextoLit):
                saida[prop.nome] = valor.valor
            elif isinstance(valor, A.NumeroLit):
                saida[prop.nome] = valor.valor
            elif isinstance(valor, A.Booleano):
                saida[prop.nome] = valor.valor
        return saida

    def _avaliar_corpo(self, fonte) -> dict:
        corpo = {}
        for chave, expr in (fonte.corpo_raw or {}).items():
            corpo[chave] = self.avaliar(expr) if expr is not None else None
        return corpo

    def atualizar(self, dt_ms: float) -> None:
        """Tick do runtime: periódicas assíncronas + espelho de arquivos."""
        import time

        agora = time.monotonic()
        for fonte in self.fontes_remotas.values():
            if hasattr(fonte, "deve_buscar"):
                try:
                    if fonte.deve_buscar(agora):
                        fonte.marcar_agendada(agora)
                        fonte.buscar_async(ao_chegar=self._fonte_chegou)
                except Exception:
                    pass
            else:
                try:
                    self._espelhar_arquivo(fonte)
                except Exception:
                    pass

    def _espelhar_arquivo(self, fonte) -> None:
        """Arquivo → estado só quando o conteúdo mudou (sem churn)."""
        snap = fonte.snapshot()
        if snap != self._espelhos.get(fonte.nome_fonte):
            self._espelhos[fonte.nome_fonte] = snap
            chave = fonte.alvo.split(".")[1]
            self.estado.garantir(chave)
            self.estado.definir(chave, snap)

    def iniciar_fontes(self) -> int:
        """Primeira busca de cada remota (assíncrona; nativo chama)."""
        import time

        total = 0
        agora = time.monotonic()
        for fonte in self.fontes_remotas.values():
            if not hasattr(fonte, "buscar_async"):
                try:
                    self._espelhar_arquivo(fonte)
                    total += 1
                except Exception:
                    pass
                continue
            try:
                fonte.retomar()
                fonte.marcar_agendada(agora)
                if fonte.buscar_async(ao_chegar=self._fonte_chegou):
                    total += 1
            except Exception:
                pass
        return total

    def buscar_fontes_sincrono(self) -> int:
        """Busca bloqueante única (CLI --sem-janela; respeita timeouts)."""
        total = 0
        for fonte in self.fontes_remotas.values():
            if not hasattr(fonte, "buscar"):
                try:
                    self._espelhar_arquivo(fonte)
                    total += 1
                except Exception:
                    pass
                continue
            try:
                fonte.buscar()
                self._fonte_chegou(fonte)
                total += 1
            except Exception:
                pass
        return total

    def sincronizar_fontes(self, nome: str | None = None) -> int:
        """Ação sincronizar(): busca assíncrona agora (uma ou todas)."""
        if nome is not None and nome not in self.fontes_remotas:
            from ..erros import ErroExecucao, sugerir

            parecidas = sugerir(nome, sorted(self.fontes_remotas))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroExecucao(
                f'Fonte desconhecida: "{nome}".{dica} '
                f"Válidas: {', '.join(sorted(self.fontes_remotas)) or 'nenhuma'}.")
        alvos = ([self.fontes_remotas[nome]] if nome
                 else list(self.fontes_remotas.values()))
        total = 0
        for fonte in alvos:
            if not hasattr(fonte, "buscar_async"):
                continue
            try:
                if fonte.buscar_async(ao_chegar=self._fonte_chegou):
                    total += 1
            except Exception:
                pass
        return total

    def _fonte_chegou(self, fonte) -> None:
        """Resultado → estado (a reatividade faz o resto)."""
        try:
            chave = fonte.alvo.split(".")[1]
            self.estado.garantir(chave)
            self.estado.definir(chave, fonte.snapshot())
        except Exception:
            pass

    # ----- formulários (Fase 08) -----

    def campos_formulario(self, nome: str) -> dict:
        """Campos editáveis do formulário: nome → (objeto, regras, chave)."""
        from ..compilador import ast as A

        for raiz in self.ctx.objetos:
            achado = raiz.buscar(nome)
            if achado is not None and achado.tipo == "formulario":
                form = achado
                break
        else:
            from ..erros import ErroExecucao, sugerir

            nomes = [o.nome for r in self.ctx.objetos for o in r.todos()
                     if o.tipo == "formulario"]
            parecidas = sugerir(nome, nomes)
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroExecucao(
                f'Formulário desconhecido: "{nome}".{dica}')
        campos = {}
        for obj in form.todos()[1:]:
            if obj.tipo not in ("entrada", "checkbox", "selecao"):
                continue
            regras = self._regras_campo(obj)
            chave = self._chave_campo(obj)
            campos[obj.nome or "campo"] = (obj, regras, chave)
        return campos

    @staticmethod
    def _numero_bruto(obj, chave: str):
        vals = obj.bruto.get(chave, [])
        if vals and isinstance(vals[0], A.NumeroLit):
            return float(vals[0].valor)
        return None

    def _regras_campo(self, obj) -> dict:
        from ..compilador import ast as A

        regras: dict = {}
        bruto = obj.bruto
        if bruto.get("obrigatorio", [None])[0] is not None:
            no = bruto["obrigatorio"][0]
            regras["obrigatorio"] = (no.valor if isinstance(no, A.Booleano)
                                     else True)
        vals = bruto.get("validar", [])
        if vals and isinstance(vals[0], A.TextoLit):
            regras["validar"] = vals[0].valor.strip().lower()
        for chave in ("min_caracteres", "max_caracteres", "min_valor",
                      "max_valor"):
            numero = self._numero_bruto(obj, chave)
            if numero is not None:
                regras[chave] = numero
        return regras

    def _chave_campo(self, obj) -> str | None:
        from ..compilador import ast as A

        vals = obj.bruto.get("ligado_a", [])
        if vals and isinstance(vals[0], A.Membro):
            partes = A.caminho_de_membro(vals[0]).split(".")
            if len(partes) == 2 and partes[0] == "estado":
                return partes[1]
        return None

    def validar_formulario(self, nome: str) -> bool:
        """Valida via estado (ligado_a); escreve estado.<form>_valido/erros."""
        from .validacao import validar_formulario

        campos = self.campos_formulario(nome)
        entradas = {}
        for campo_nome, (_obj, regras, chave) in campos.items():
            valor = self.estado.obter(chave) if chave in self.estado else ""
            entradas[campo_nome] = (valor, regras)
        ok, erros = validar_formulario(entradas)
        self.estado.garantir(f"{nome}_valido")
        self.estado.garantir(f"{nome}_erros")
        self.estado.definir(f"{nome}_valido", ok)
        self.estado.definir(f"{nome}_erros", erros)
        return ok

    def enviar_formulario(self, nome: str, fonte_nome: str) -> int:
        """Valida, monta corpo do estado e POSTa assíncrono (Fase 06)."""
        from ..dados.remoto import FonteRemota
        from ..erros import ErroExecucao

        if not self.validar_formulario(nome):
            return 0
        fonte = self.fontes_remotas.get(fonte_nome)
        if fonte is None or not hasattr(fonte, "cliente"):
            raise ErroExecucao(
                f'Fonte HTTP desconhecida: "{fonte_nome}". '
                "Use um bloco dados com url.")
        campos = self.campos_formulario(nome)
        corpo = {}
        for _campo_nome, (_obj, _regras, chave) in campos.items():
            if chave in self.estado:
                corpo[chave] = self.estado.obter(chave)
        envio = FonteRemota(
            nome=fonte.nome_fonte, url=fonte.url, metodo="POST",
            cabecalhos=dict(fonte.cabecalhos),
            parametros=dict(fonte.parametros),
            corpo_raw=None, timeout_s=fonte.cliente.timeout_s,
            intervalo_s=None, alvo=f"estado.{nome}_resposta")
        from ..compilador import ast as A

        def literal(valor):
            if isinstance(valor, bool):
                return A.Booleano(valor=valor)
            if isinstance(valor, (int, float)):
                return A.NumeroLit(valor=float(valor))
            return A.TextoLit(valor=str(valor))

        envio.corpo_raw = {k: literal(v) for k, v in corpo.items()}
        envio.avaliar_corpo = lambda f=envio: self._avaliar_corpo(f)
        self.estado.garantir(f"{nome}_resposta")
        envio.buscar_async(ao_chegar=self._fonte_chegou)
        return len(corpo)

    def disparar(self, obj: Objeto, evento: str,
                 silencioso: bool = False) -> bool:
        """Dispara um evento em um objeto. Retorna True se havia manipulador."""
        validar_evento(evento, linha=obj.linha)
        bloco = obj.eventos.get(evento)
        if bloco is None:
            return False
        self.executar_bloco(bloco)
        return True

    def simular_clique(self, nome: str) -> bool:
        """Encontra um componente pelo nome e dispara 'clicar' (CLI --clicar)."""
        for raiz in self.ctx.objetos:
            alvo = raiz.buscar(nome)
            if alvo is not None:
                return self.disparar(alvo, "clicar")
        raise ErroExecucao(
            f"Não há componente chamado {nome!r} para clicar.",
            sugestao="Verifique o nome do botão na janela.",
        )

    # ----- blocos -----

    def executar_bloco(self, bloco: A.Bloco) -> None:
        for cmd in bloco.comandos:
            self.executar_comando(cmd)

    def executar_comando(self, cmd: object) -> None:
        if isinstance(cmd, A.Acao):
            # Fase 09: executar despacha ação/função do usuário.
            if cmd.nome == "executar":
                self.executar_chamada(cmd)
                return
            if cmd.nome in self.funcoes:
                self.chamar_funcao(cmd.nome,
                                   [self.avaliar(a) for a in cmd.args],
                                   linha=cmd.linha)
            elif cmd.nome in self.acoes:
                self.chamar_acao(cmd.nome,
                                 [self.avaliar(a) for a in cmd.args],
                                 linha=cmd.linha)
            else:
                args = [self.avaliar(a) for a in cmd.args]
                executar_acao(cmd.nome, args, self.ctx, linha=cmd.linha)
        elif isinstance(cmd, A.Se):
            if self.eh_verdadeiro(self.avaliar(cmd.condicao)):
                self.executar_bloco(cmd.entao)
            elif cmd.senao is not None:
                self.executar_bloco(cmd.senao)
        elif isinstance(cmd, A.Repetir):
            if cmd.vezes is None:
                self.avisos.append(
                    "repetir sem número executou 1 vez (Fase 01: "
                    "repetição infinita ainda não suportada).")
                self.executar_bloco(cmd.bloco)
            else:
                vezes = int(self.avaliar(cmd.vezes))
                if vezes > LIMITE_REPETICAO:
                    raise ErroExecucao(
                        f"repetir {vezes} vezes excede o limite da Fase 01 "
                        f"({LIMITE_REPETICAO}).",
                        linha=cmd.linha,
                    )
                for _ in range(max(0, vezes)):
                    self.executar_bloco(cmd.bloco)
        elif isinstance(cmd, A.Retornar):
            raise _Retorno(self.avaliar(cmd.valor)
                           if cmd.valor is not None else None)
        elif isinstance(cmd, A.Atribuicao):
            self.executar_atribuicao(cmd)
        else:
            raise ErroExecucao(f"Comando desconhecido: {cmd!r}.")

    def executar_atribuicao(self, cmd: A.Atribuicao) -> None:
        """estado.x = v (+= -= *= /=); x = v vai para a memória."""
        novo = self.avaliar(cmd.valor)
        alvo = cmd.alvo
        if isinstance(alvo, A.Ident):
            self.memoria.atribuir(alvo.nome, novo)
            return
        caminho = A.caminho_de_membro(alvo)
        partes = caminho.split(".")
        if partes[0] == "dados":
            raise ErroExecucao(
                f'Dados são somente leitura: "{caminho}". '
                "Atribua a estado (ex. estado.copia = dados.sistema.cpu).",
                linha=cmd.linha,
            )
        if partes[0] == "local":
            if len(partes) != 2:
                raise ErroExecucao(
                    "Estado local guarda valores simples: use local.nome.",
                    linha=cmd.linha,
                )
            ns = self.ns_topo()
            if ns is None:
                raise ErroExecucao(
                    '"local" só existe dentro de componente com estado '
                    "ou item de lista.",
                    linha=cmd.linha,
                )
            self.definir_local(ns, partes[1],
                               self._aplicar_op_atribuicao(
                                   self._obter_local_ou_nulo(ns, partes[1]),
                                   novo, cmd.op, caminho, cmd.linha),
                               linha=cmd.linha)
            return
        if partes[0] == "item":
            raise ErroExecucao(
                "Item é somente leitura: copie para estado ou local.",
                linha=cmd.linha,
            )
        if partes[0] == "param":
            raise ErroExecucao(
                '"param" só existe dentro de componente.',
                linha=cmd.linha,
            )
        if partes[0] == "estado":
            if len(partes) != 2:
                raise ErroExecucao(
                    "Estado guarda valores simples: use estado.nome.",
                    linha=cmd.linha,
                )
            nome = partes[1]
            if cmd.op == "=":
                self.estado.definir(nome, novo, linha=cmd.linha)
                return
            atual = self.estado.obter(nome, linha=cmd.linha)
            resultado = self._aplicar_op_atribuicao(
                atual, novo, cmd.op, caminho, cmd.linha)
            self.estado.definir(nome, resultado, linha=cmd.linha)
            return
        raise ErroExecucao(
            f'Atribuição inválida: "{caminho}". Use estado.nome ou variável.',
            linha=cmd.linha,
        )

    def _obter_local_ou_nulo(self, ns: str, chave: str):
        valores = self.locais.get(ns)
        if valores is None or chave not in valores:
            return None
        return valores[chave]

    @staticmethod
    def _aplicar_op_atribuicao(atual, novo, op: str, caminho: str,
                               linha: int):
        """= += -= *= /= com erro PT (tipos ou divisão por zero)."""
        try:
            if op == "=":
                return novo
            if atual is None:
                raise TypeError("sem valor anterior")
            if op == "+=":
                return atual + novo  # type: ignore[operator]
            if op == "-=":
                return atual - novo  # type: ignore[operator]
            if op == "*=":
                return atual * novo  # type: ignore[operator]
            return atual / novo  # type: ignore[operator]
        except (TypeError, ZeroDivisionError):
            raise ErroExecucao(
                f'Operação "{caminho} {op} {novo!r}" inválida '
                "(tipos incompatíveis ou divisão por zero).",
                linha=linha,
            )

    def executar_chamada(self, cmd: A.Acao) -> None:
        """`executar nome` ou `executar nome(args)` (Fase 09)."""
        if not cmd.args:
            raise ErroExecucao(
                'Uso: executar nome_da_acao ou executar nome(arg, ...).',
                linha=cmd.linha,
                exemplo='executar incrementar',
            )
        alvo = cmd.args[0]
        if isinstance(alvo, A.Ident):
            nome, args = alvo.nome, []
        elif isinstance(alvo, A.Chamada):
            nome = alvo.nome
            args = [self.avaliar(a) for a in alvo.args]
        else:
            raise ErroExecucao(
                "executar espera nome de ação ou função.",
                linha=cmd.linha,
                exemplo='executar selecionar(item.id)',
            )
        if nome in self.acoes:
            self.chamar_acao(nome, args, linha=cmd.linha)
        elif nome in self.funcoes:
            self.chamar_funcao(nome, args, linha=cmd.linha)
        else:
            from ..erros import sugerir

            conhecidos = (sorted(self.acoes) + sorted(self.funcoes))
            parecidas = sugerir(nome, conhecidos)
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroExecucao(
                f'Ação ou função desconhecida: "{nome}".{dica}',
                linha=cmd.linha,
            )

    def chamar_acao(self, nome: str, args: list,
                    *, linha: int = 0) -> None:
        """Roda ação reutilizável (params com escopo; sem retorno)."""
        acao = self.acoes.get(nome)
        if acao is None:
            raise ErroExecucao(f'Ação desconhecida: "{nome}".', linha=linha)
        if len(args) != len(acao.params):
            raise ErroExecucao(
                f'Ação "{nome}" espera {len(acao.params)} argumento(s), '
                f"mas recebeu {len(args)}.",
                linha=linha,
            )
        self.memoria.entrar_escopo()
        try:
            for param, valor in zip(acao.params, args):
                self.memoria.definir(param, valor)
            try:
                self.executar_bloco(acao.bloco)
            except _Retorno:
                pass
        finally:
            self.memoria.sair_escopo()

    def chamar_funcao(self, nome: str, args: list,
                      *, linha: int = 0) -> object:
        funcao = self.funcoes.get(nome)
        if funcao is None:
            raise ErroExecucao(f"Função desconhecida: {nome!r}.", linha=linha)
        if len(args) != len(funcao.params):
            raise ErroExecucao(
                f'Função "{nome}" espera {len(funcao.params)} argumento(s), '
                f"mas recebeu {len(args)}.",
                linha=linha,
            )
        self.memoria.entrar_escopo()
        try:
            for param, valor in zip(funcao.params, args):
                self.memoria.definir(param, valor)
            try:
                self.executar_bloco(funcao.bloco)
            except _Retorno as ret:
                return ret.valor
            return None
        finally:
            self.memoria.sair_escopo()

    # ----- expressões -----

    def avaliar(self, expr: object) -> object:
        if isinstance(expr, A.TextoLit):
            return expr.valor
        if isinstance(expr, A.NumeroLit):
            return expr.valor
        if isinstance(expr, A.Medida):
            return (expr.valor, expr.unidade)
        if isinstance(expr, A.CorLit):
            if expr.formato == "hex":
                return para_cor(expr.valor, linha=expr.linha).hexadecimal
            return para_cor(expr.valor, linha=expr.linha).hexadecimal
        if isinstance(expr, A.Booleano):
            return expr.valor
        if isinstance(expr, A.ListaLit):
            return [self.avaliar(item) for item in expr.itens]
        if isinstance(expr, A.Ident):
            if expr.nome == "dados":
                raise ErroExecucao(
                    '"dados" sozinho não é um valor. Use um caminho como '
                    "dados.sistema.cpu, dados.sistema.ram ou dados.sistema.hora.",
                    linha=expr.linha,
                    exemplo='origem: dados.sistema.cpu',
                )
            if expr.nome == "estado":
                raise ErroExecucao(
                    '"estado" sozinho não é um valor. Use estado.nome '
                    "(ex. estado.contador).",
                    linha=expr.linha,
                    exemplo='mostrar(estado.contador)',
                )
            if expr.nome == "local":
                raise ErroExecucao(
                    '"local" sozinho não é um valor. Use local.nome '
                    "dentro de componente com estado ou item de lista.",
                    linha=expr.linha,
                    exemplo='origem: local.favorito',
                )
            if expr.nome == "item":
                if self.item_atual is not None:
                    return self.item_atual
                raise ErroExecucao(
                    '"item" só existe dentro do modelo de uma lista.',
                    linha=expr.linha,
                    exemplo='texto: item.nome',
                )
            if expr.nome == "param":
                raise ErroExecucao(
                    '"param" só existe dentro de componente. '
                    "Use param.nome no corpo de componente Nome { ... }.",
                    linha=expr.linha,
                )
            try:
                return self.memoria.obter(expr.nome, linha=expr.linha)
            except ErroExecucao:
                # nome de objeto/estilo usado como valor → texto
                for raiz in self.ctx.objetos:
                    if raiz.buscar(expr.nome) is not None:
                        return expr.nome
                raise
        if isinstance(expr, A.Chamada):
            if expr.nome in self.funcoes:
                return self.chamar_funcao(
                    expr.nome, [self.avaliar(a) for a in expr.args],
                    linha=expr.linha)
            # função de estilo futura (ex. vermelho.mais_claro) → texto
            return expr.nome
        if isinstance(expr, A.Membro):
            return self.avaliar_membro(expr)
        if isinstance(expr, A.Binaria):
            if expr.op == "nao":
                return not self.eh_verdadeiro(self.avaliar(expr.direita))
            esq = self.avaliar(expr.esquerda)
            dir_ = self.avaliar(expr.direita)
            return self.aplicar_operador(expr.op, esq, dir_, expr.linha)
        raise ErroExecucao(f"Expressão desconhecida: {expr!r}.")

    def avaliar_membro(self, expr: A.Membro) -> object:
        """Resolve acesso por pontos: dados./estado./local./item. ou base."""
        caminho = A.caminho_de_membro(expr)
        partes = caminho.split(".")
        if partes[0] == "local":
            if len(partes) != 2:
                raise ErroExecucao(
                    "Estado local guarda valores simples: use local.nome "
                    f'(recebido "{caminho}").',
                    linha=expr.linha,
                )
            ns = self.ns_topo()
            if ns is None:
                raise ErroExecucao(
                    '"local" só existe dentro de componente com estado '
                    "ou item de lista.",
                    linha=expr.linha,
                    exemplo='origem: local.favorito',
                )
            return self.obter_local(ns, partes[1], linha=expr.linha)
        if partes[0] == "item":
            if self.item_atual is None:
                raise ErroExecucao(
                    '"item" só existe dentro do modelo de uma lista.',
                    linha=expr.linha,
                    exemplo='texto: item.nome',
                )
            if len(partes) == 2 and partes[1] == "indice":
                return self.indice_atual
            if len(partes) != 2:
                raise ErroExecucao(
                    "Item guarda campos simples: use item.campo ou "
                    f'item.indice (recebido "{caminho}").',
                    linha=expr.linha,
                )
            item = self.item_atual
            if isinstance(item, dict) and partes[1] in item:
                return item[partes[1]]
            raise ErroExecucao(
                f'Campo desconhecido no item: "{caminho}".',
                linha=expr.linha,
            )
        if partes[0] == "param":
            raise ErroExecucao(
                '"param" só existe dentro de componente '
                "(a expansão já substitui; fora dela é erro).",
                linha=expr.linha,
            )
        if partes[0] == "estado":
            if len(partes) < 2:
                raise ErroExecucao(
                    "Estado guarda valores: use estado.nome "
                    f'(recebido "{caminho}").',
                    linha=expr.linha,
                )
            valor = self.estado.obter(partes[1], linha=expr.linha)
            for parte in partes[2:]:
                if isinstance(valor, dict) and parte in valor:
                    valor = valor[parte]
                else:
                    raise ErroExecucao(
                        f'Caminho desconhecido em estado: "{caminho}".',
                        linha=expr.linha,
                        sugestao="Verifique os campos (ex. estado.usuarios.valor).",
                    )
            return valor
        if partes[0] == "dados":
            if len(partes) < 3:
                raise ErroExecucao(
                    f'Caminho de dados incompleto: "{caminho}". Use '
                    "dados.fonte.campo (ex. dados.sistema.cpu).",
                    linha=expr.linha,
                )
            fonte = self.fontes.get(partes[1])
            if fonte is None:
                raise ErroExecucao(
                    f'Fonte de dados desconhecida: "{partes[1]}".',
                    linha=expr.linha,
                )
            return fonte.obter(".".join(partes[2:]))
        base = self.avaliar(expr.base) if not isinstance(
            expr.base, A.Ident) else self._avaliar_base(expr.base)
        return self._ler_atributo(base, expr.atributo, caminho, expr.linha)

    def _avaliar_base(self, base: A.Ident) -> object:
        try:
            return self.memoria.obter(base.nome, linha=base.linha)
        except ErroExecucao:
            for raiz in self.ctx.objetos:
                if raiz.buscar(base.nome) is not None:
                    return base.nome
            raise

    @staticmethod
    def _ler_atributo(base: object, atributo: str, caminho: str,
                      linha: int) -> object:
        if isinstance(base, dict) and atributo in base:
            return base[atributo]
        if hasattr(base, atributo):
            return getattr(base, atributo)
        raise ErroExecucao(
            f'Atributo desconhecido: "{caminho}".',
            linha=linha,
        )

    @staticmethod
    def aplicar_operador(op: str, esq: object, dir_: object,
                         linha: int) -> object:
        try:
            if op == "+":
                return esq + dir_  # type: ignore[operator]
            if op == "-":
                return esq - dir_  # type: ignore[operator]
            if op == "*":
                return esq * dir_  # type: ignore[operator]
            if op == "/":
                return esq / dir_  # type: ignore[operator]
            if op == "%":
                return esq % dir_  # type: ignore[operator]
            if op == "==":
                return esq == dir_
            if op == "!=":
                return esq != dir_
            if op == ">":
                return esq > dir_  # type: ignore[operator]
            if op == "<":
                return esq < dir_  # type: ignore[operator]
            if op == ">=":
                return esq >= dir_  # type: ignore[operator]
            if op == "<=":
                return esq <= dir_  # type: ignore[operator]
            if op == "e":
                return Executor.eh_verdadeiro(esq) and Executor.eh_verdadeiro(dir_)
            if op == "ou":
                return Executor.eh_verdadeiro(esq) or Executor.eh_verdadeiro(dir_)
        except (TypeError, ZeroDivisionError):
            raise ErroExecucao(
                f"Operação {esq!r} {op} {dir_!r} inválida "
                "(tipos incompatíveis ou divisão por zero).",
                linha=linha,
            )
        raise ErroExecucao(f"Operador desconhecido: {op!r}.", linha=linha)

    @staticmethod
    def eh_verdadeiro(valor: object) -> bool:
        if valor is None:
            return False
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, (int, float)):
            return valor != 0
        if isinstance(valor, str):
            return valor != ""
        return True


class _Retorno(Exception):
    def __init__(self, valor: object) -> None:
        self.valor = valor
