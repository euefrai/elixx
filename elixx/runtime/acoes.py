"""Ações da ELiXX — sistema extensível por registro.

Novas ações são criadas assim, sem modificar o núcleo:

    from elixx.runtime.acoes import acao

    @acao("girar")
    def girar(ctx, graus):
        ...

Ações da Fase 01: mostrar, esconder, abrir, fechar, mover, redimensionar,
alterar, reproduzir, parar e animar (simplificada — aplica o estado final
e registra a intenção; interpolação real vem na próxima fase).
"""
from __future__ import annotations

from typing import Callable

from ..erros import ErroExecucao, sugerir

REGISTRO: dict[str, Callable] = {}


def acao(nome: str) -> Callable:
    """Decorador que registra uma nova ação da linguagem."""

    def decoradora(funcao: Callable) -> Callable:
        REGISTRO[nome] = funcao
        return funcao

    return decoradora


def formatar(valor: object) -> str:
    if isinstance(valor, bool):
        return "verdadeiro" if valor else "falso"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, tuple) and len(valor) == 2:
        numero, unidade = valor
        texto_num = str(int(numero)) if float(numero).is_integer() else str(numero)
        return f"{texto_num}{unidade}"
    return str(valor)


class Contexto:
    """O que as ações podem usar: saída, objetos e memória.

    Fase 02: `ao_mostrar` é um gancho opcional chamado com cada texto de
    `mostrar(...)` — o renderer nativo o usa para a barra de mensagens.
    Sem o gancho, o comportamento é idêntico ao da Fase 01.
    """

    def __init__(self, objetos: list, memoria, ao_mostrar=None) -> None:
        self.objetos = objetos
        self.memoria = memoria
        self.saida: list[str] = []
        self.ao_mostrar = ao_mostrar
        # Extensão dashboard (opcionais; nativo.py conecta ambos):
        # - vinculador: Vinculador da Cena (atualizar/alternar dados);
        # - ao_sair: chamado pela ação sair() (fecha a aplicação).
        # Fase 03: motor de animação (iniciar/pausar/continuar/cancelar).
        # Fase 05: estado reativo (incrementar e amigos; Executor conecta).
        # Fase 06: sincronizar fontes (nativo conecta ao_sincronizar).
        # Fase 07: mídia (executor, audio lazy, video) — Executor conecta.
        # Fase 08: renderer (temas/foco; nativo conecta).
        self.vinculador = None
        self.ao_sair = None
        self.motor = None
        self.estado = None
        self.ao_sincronizar = None
        self.executor = None
        self.audio = None
        self.video = None
        self.renderer = None


def executar_acao(nome: str, args: list, ctx: Contexto,
                  *, linha: int | None = None) -> None:
    funcao = REGISTRO.get(nome)
    if funcao is None:
        parecidas = sugerir(nome, sorted(REGISTRO))
        dica = f" Você quis dizer: {', '.join(parecidas)}?" if parecidas else ""
        raise ErroExecucao(
            f"Ação desconhecida: {nome!r}.{dica} "
            f"Ações válidas: {', '.join(sorted(REGISTRO))}.",
            linha=linha,
            exemplo='mostrar("Olá, mundo!")',
        )
    funcao(ctx, *args)


def _buscar(ctx: Contexto, nome: str):
    for raiz in ctx.objetos:
        achado = raiz.buscar(nome)
        if achado is not None:
            return achado
    return None


@acao("mostrar")
def _mostrar(ctx: Contexto, *args) -> None:
    texto = " ".join(formatar(a) for a in args)
    ctx.saida.append(texto)
    if ctx.ao_mostrar is not None:
        ctx.ao_mostrar(texto)


@acao("esconder")
def _esconder(ctx: Contexto, *args) -> None:
    for nome in args:
        obj = _buscar(ctx, str(nome))
        if obj is not None:
            obj.visivel = False
    ctx.saida.append("(elemento escondido)" if args else "(esconder)")


@acao("exibir")
def _exibir(ctx: Contexto, *args) -> None:
    """Torna visível um componente escondido (par de esconder)."""
    for nome in args:
        obj = _buscar(ctx, str(nome))
        if obj is not None:
            obj.visivel = True
    ctx.saida.append("(elemento exibido)" if args else "(exibir)")


@acao("atualizar_dados")
def _atualizar_dados(ctx: Contexto, *args) -> None:
    """Força releitura imediata das fontes (botão Atualizar)."""
    if ctx.vinculador is not None:
        total = ctx.vinculador.atualizar_agora()
        ctx.saida.append(f"(dados atualizados: {total} vínculo(s))")
    else:
        ctx.saida.append("(sem vinculador de dados)")


@acao("alternar_atualizacao")
def _alternar_atualizacao(ctx: Contexto, *args) -> None:
    """Liga/desliga a atualização automática (botão ON/OFF)."""
    if ctx.vinculador is not None:
        estado = ctx.vinculador.alternar()
        texto = "ON" if estado else "OFF"
        ctx.saida.append(f"(atualização automática: {texto})")
        if ctx.ao_mostrar is not None:
            ctx.ao_mostrar(f"Atualização automática: {texto}")
    else:
        ctx.saida.append("(sem vinculador de dados)")


@acao("sair")
def _sair(ctx: Contexto, *args) -> None:
    """Fecha a aplicação (nativo.py conecta ao fechamento real)."""
    ctx.saida.append("(saindo)")
    if ctx.ao_sair is not None:
        ctx.ao_sair()


@acao("incrementar")
def _incrementar(ctx: Contexto, *args) -> None:
    """Soma ao estado (cria com 0): incrementar("contador") ou ("n", 2)."""
    if ctx.estado is None or not args:
        ctx.saida.append("(incrementar precisa de estado e nome)")
        return
    nome = str(args[0])
    passo = float(args[1]) if len(args) > 1 else 1.0
    novo = ctx.estado.incrementar(nome, passo)
    ctx.saida.append(f"(incrementado {nome}: {formatar(novo)})")


@acao("sincronizar")
def _sincronizar(ctx: Contexto, *args) -> None:
    """Busca fonte agora (assíncrona): sincronizar() ou ("usuarios")."""
    if ctx.ao_sincronizar is None:
        ctx.saida.append("(sem fontes para sincronizar)")
        return
    nome = str(args[0]) if args else None
    try:
        total = ctx.ao_sincronizar(nome)
    except ErroExecucao as exc:
        ctx.saida.append(f"Erro: {exc.mensagem}")
        return
    ctx.saida.append(f"(sincronizando {total} fonte(s))")


def _com_motor(ctx: Contexto, acao_nome: str):
    if ctx.motor is None:
        ctx.saida.append(f"(sem motor de animação para {acao_nome})")
        return None
    return ctx.motor


@acao("iniciar")
def _iniciar(ctx: Contexto, *args) -> None:
    """Inicia uma animação manual (ex. iniciar("entrada"))."""
    motor = _com_motor(ctx, "iniciar")
    if motor is None:
        return
    for nome in args:
        motor.iniciar(str(nome))
    ctx.saida.append(f"(animação iniciada: {' '.join(map(str, args))})")


@acao("cancelar")
def _cancelar(ctx: Contexto, *args) -> None:
    motor = _com_motor(ctx, "cancelar")
    if motor is None:
        return
    for nome in args:
        motor.cancelar(str(nome))
    ctx.saida.append("(animação cancelada)" if args else "(cancelar)")


@acao("abrir")
def _abrir(ctx: Contexto, *args) -> None:
    if args:
        nome = str(args[0])
        if _navegar_para(ctx, nome):
            return
        if _alternar_modal(ctx, nome, True):
            return
    alvo = formatar(args[0]) if args else "janela"
    ctx.saida.append(f"(abrir {alvo})")


@acao("fechar")
def _fechar(ctx: Contexto, *args) -> None:
    if args and _alternar_modal(ctx, str(args[0]), False):
        return
    alvo = formatar(args[0]) if args else "janela"
    ctx.saida.append(f"(fechar {alvo})")


def _navegador(ctx: Contexto):
    executor = getattr(ctx, "executor", None)
    navegador = getattr(executor, "navegador", None) if executor else None
    if navegador is None or not getattr(navegador, "telas", {}):
        return None
    return navegador


def _navegar_para(ctx: Contexto, nome: str) -> bool:
    """True se navegou (nome é tela)."""
    navegador = _navegador(ctx)
    if navegador is None or nome not in navegador.telas:
        return False
    try:
        navegador.ir(nome)
        ctx.saida.append(f"(tela {nome})")
    except ErroExecucao as exc:
        ctx.saida.append(f"Erro: {exc.mensagem}")
    return True


def _alternar_modal(ctx: Contexto, nome: str, mostrar: bool) -> bool:
    """True se alternou modal (nome é modal)."""
    obj = _buscar(ctx, nome)
    if obj is None or obj.tipo != "modal":
        return False
    obj.visivel = mostrar
    executor = getattr(ctx, "executor", None)
    if executor is not None:
        try:
            executor.disparar(obj, "mostrar" if mostrar else "esconder")
        except ErroExecucao:
            pass
    ctx.saida.append(f"(modal {nome} {'aberto' if mostrar else 'fechado'})")
    return True


@acao("ir")
def _ir(ctx: Contexto, *args) -> None:
    """Vai para tela: ir("perfil"). Parâmetros via estado antes."""
    if not args:
        _dizer(ctx, 'Uso: ir("nome_da_tela").')
        return
    if not _navegar_para(ctx, str(args[0])):
        _dizer(ctx, f'Não há tela "{args[0]}" para ir.')


@acao("voltar")
def _voltar(ctx: Contexto, *args) -> None:
    navegador = _navegador(ctx)
    if navegador is None:
        _dizer(ctx, "(sem navegação: nenhuma tela no programa)")
        return
    try:
        navegador.voltar()
        ctx.saida.append(f"(tela {navegador.atual})")
    except ErroExecucao as exc:
        ctx.saida.append(f"Erro: {exc.mensagem}")


@acao("inicio")
def _inicio(ctx: Contexto, *args) -> None:
    navegador = _navegador(ctx)
    if navegador is None:
        _dizer(ctx, "(sem navegação: nenhuma tela no programa)")
        return
    try:
        navegador.inicio()
        ctx.saida.append(f"(tela {navegador.atual})")
    except ErroExecucao as exc:
        ctx.saida.append(f"Erro: {exc.mensagem}")


@acao("usar_tema")
def _usar_tema(ctx: Contexto, *args) -> None:
    """Troca o tema sem reconstruir: usar_tema("claro")."""
    executor = getattr(ctx, "executor", None)
    if executor is None or not args:
        _dizer(ctx, 'Uso: usar_tema("nome_do_tema").')
        return
    nome = str(args[0])
    if nome not in executor.temas:
        _dizer(ctx, f'Tema "{nome}" não existe. '
                    f"Válidos: {', '.join(sorted(executor.temas)) or 'nenhum'}.")
        return
    executor.tema_atual = nome
    from ..visual.cena import aplicar_tema

    renderer = getattr(ctx, "renderer", None)
    cena = getattr(renderer, "cena", None) if renderer else None
    if cena is not None:
        aplicar_tema(cena, executor.temas, nome)
        refrescar = getattr(renderer, "refrescar_tema", None)
        if refrescar is not None:
            try:
                refrescar()
            except Exception:
                pass
    ctx.saida.append(f"(tema {nome})")


@acao("focar")
def _focar(ctx: Contexto, *args) -> None:
    """Dá foco a um campo: focar("nome"). Sem janela: só registra."""
    if not args:
        _dizer(ctx, 'Uso: focar("nome_do_campo").')
        return
    renderer = getattr(ctx, "renderer", None)
    focar_em = getattr(renderer, "focar_em", None) if renderer else None
    if focar_em is not None:
        try:
            if focar_em(str(args[0])):
                ctx.saida.append(f"(foco em {args[0]})")
                return
        except Exception:
            pass
    ctx.saida.append(f"(foco em {args[0]})")


@acao("validar")
def _validar_form(ctx: Contexto, *args) -> None:
    """Valida formulário: validar("cadastro"). Escreve estado.*_valido."""
    if not args:
        _dizer(ctx, 'Uso: validar("nome_do_formulario").')
        return
    executor = getattr(ctx, "executor", None)
    if executor is None:
        _dizer(ctx, "(sem executor para validar)")
        return
    try:
        ok = executor.validar_formulario(str(args[0]))
        ctx.saida.append(f"(formulário {args[0]}: "
                         f"{'válido' if ok else 'inválido'})")
    except ErroExecucao as exc:
        ctx.saida.append(f"Erro: {exc.mensagem}")


@acao("enviar")
def _enviar(ctx: Contexto, *args) -> None:
    """Valida e POSTa: enviar("cadastro", "usuarios")."""
    if len(args) < 2:
        _dizer(ctx, 'Uso: enviar("formulario", "fonte").')
        return
    executor = getattr(ctx, "executor", None)
    if executor is None:
        _dizer(ctx, "(sem executor para enviar)")
        return
    try:
        if not executor.validar_formulario(str(args[0])):
            erros = executor.estado.obter(
                f"{args[0]}_erros", linha=None) if f"{args[0]}_erros" in (
                    executor.estado) else []
            _dizer(ctx, "Formulário inválido: " + "; ".join(erros))
            return
        total = executor.enviar_formulario(str(args[0]), str(args[1]))
        ctx.saida.append(f"(enviado via {args[1]}: {total} campo(s))")
    except ErroExecucao as exc:
        ctx.saida.append(f"Erro: {exc.mensagem}")


@acao("mover")
def _mover(ctx: Contexto, *args) -> None:
    ctx.saida.append(f"(mover para {' '.join(formatar(a) for a in args)})")


@acao("redimensionar")
def _redimensionar(ctx: Contexto, *args) -> None:
    ctx.saida.append(
        f"(redimensionar para {' '.join(formatar(a) for a in args)})")


@acao("alterar")
def _alterar(ctx: Contexto, *args) -> None:
    ctx.saida.append(f"(alterar {' '.join(formatar(a) for a in args)})")


@acao("reproduzir")
def _reproduzir(ctx: Contexto, *args) -> None:
    alvo = _alvo_midia(ctx, args)
    if alvo is None:
        ctx.saida.append(f"(reproduzir {formatar(args[0]) if args else 'mídia'})")
        return
    tipo, motor, caminho, volume, repetir = alvo
    if caminho is None:
        _dizer(ctx, "Vídeo: informe arquivo. A reprodução usa backend "
                    "futuro dedicado."
               if tipo == "video" else
               "Áudio sem arquivo: use arquivo: \"assets/som.wav\".")
        return
    try:
        _dizer(ctx, motor.reproduzir(caminho, volume=volume,
                                     repetir=repetir))
    except ErroExecucao as exc:
        _dizer(ctx, f"Erro: {exc.mensagem}")


@acao("parar")
def _parar(ctx: Contexto, *args) -> None:
    alvo = _alvo_midia(ctx, args)
    if alvo is None:
        ctx.saida.append(f"(parar {formatar(args[0]) if args else 'mídia'})")
        return
    _tipo, motor, _caminho, _volume, _repetir = alvo
    try:
        _dizer(ctx, motor.parar())
    except ErroExecucao as exc:
        _dizer(ctx, f"Erro: {exc.mensagem}")


@acao("pausar")
def _pausar(ctx: Contexto, *args) -> None:
    alvo = _alvo_midia(ctx, args)
    if alvo is not None:
        _tipo, motor, _caminho, _volume, _repetir = alvo
        try:
            _dizer(ctx, motor.pausar())
        except ErroExecucao as exc:
            _dizer(ctx, f"Erro: {exc.mensagem}")
        return
    motor = _com_motor(ctx, "pausar")
    if motor is None:
        return
    for nome in args:
        motor.pausar(str(nome))
    ctx.saida.append("(animação pausada)" if args else "(pausar)")


@acao("continuar")
def _continuar(ctx: Contexto, *args) -> None:
    alvo = _alvo_midia(ctx, args)
    if alvo is not None:
        _tipo, motor, _caminho, _volume, _repetir = alvo
        try:
            _dizer(ctx, motor.continuar())
        except ErroExecucao as exc:
            _dizer(ctx, f"Erro: {exc.mensagem}")
        return
    motor = _com_motor(ctx, "continuar")
    if motor is None:
        return
    for nome in args:
        motor.continuar(str(nome))
    ctx.saida.append("(animação retomada)" if args else "(continuar)")


@acao("volume")
def _volume(ctx: Contexto, *args) -> None:
    """volume("musica", 80) — áudio real guarda; vídeo guarda p/ futuro."""
    alvo = _alvo_midia(ctx, args)
    if alvo is None or len(args) < 2:
        _dizer(ctx, "Uso: volume(\"nome_do_audio\", 0 a 100).")
        return
    _tipo, motor, _caminho, _volume, _repetir = alvo
    try:
        _dizer(ctx, motor.definir_volume(int(float(args[1]))))
    except (ValueError, TypeError):
        _dizer(ctx, "Volume precisa ser número de 0 a 100.")
    except ErroExecucao as exc:
        _dizer(ctx, f"Erro: {exc.mensagem}")


def _dizer(ctx: Contexto, mensagem: str) -> None:
    """Saída + barra de mensagens (mídia aparece na janela também)."""
    ctx.saida.append(mensagem)
    if ctx.ao_mostrar is not None:
        try:
            ctx.ao_mostrar(mensagem)
        except Exception:
            pass


def _alvo_midia(ctx: Contexto, args):
    """(tipo, motor, caminho_abs|None, volume, repetir) ou None.

    None = sem alvo de mídia (mantém comportamento legado da ação).
    """
    if not args:
        return None
    obj = _buscar(ctx, str(args[0]))
    if obj is None or obj.tipo not in ("audio", "video"):
        return None
    from ..compilador import ast as A

    arquivo = volume = repetir = None
    for nome, valores in getattr(obj, "bruto", {}).items():
        if not valores:
            continue
        primeiro = valores[0]
        if nome == "arquivo" and isinstance(primeiro, A.TextoLit):
            arquivo = primeiro.valor
        elif nome == "volume" and isinstance(primeiro, A.NumeroLit):
            volume = max(0, min(100, int(primeiro.valor)))
        elif nome == "repetir" and isinstance(primeiro, A.Booleano):
            repetir = bool(primeiro.valor)
    if obj.tipo == "audio":
        motor = _motor_audio(ctx)
        if motor is None:
            return ("audio", _MotorSilencioso(
                "Áudio indisponível neste ambiente."), None,
                    volume or 100, bool(repetir))
        caminho = None
        if arquivo:
            base = getattr(ctx.executor, "base_dir", ".") or "."
            from ..multimidia.recursos import resolver_caminho

            caminho = resolver_caminho(base, arquivo)
        return ("audio", motor, caminho, volume or 100, bool(repetir))
    if ctx.video is None:
        from ..multimidia.video import MotorVideo

        ctx.video = MotorVideo()
    return ("video", ctx.video, None, volume or 100, bool(repetir))


def _motor_audio(ctx):
    if ctx.audio is not None:
        return ctx.audio
    try:
        from ..multimidia.audio import MotorWinsound

        ctx.audio = MotorWinsound()
        return ctx.audio
    except ErroExecucao as exc:
        _dizer(ctx, f"Erro: {exc.mensagem}")
        return None


class _MotorSilencioso:
    """Substituto que só explica (quando nem o backend existe)."""

    def __init__(self, mensagem: str) -> None:
        self.mensagem = mensagem

    def reproduzir(self, *a, **k):
        return self.mensagem

    def pausar(self, *a, **k):
        return self.mensagem

    def continuar(self, *a, **k):
        return self.mensagem

    def parar(self, *a, **k):
        return self.mensagem

    def definir_volume(self, *a, **k):
        return self.mensagem


@acao("animar")
def _animar(ctx: Contexto, *args) -> None:
    # Fase 01: registra a intenção; interpolação real na próxima fase.
    ctx.saida.append(f"(animar {' '.join(formatar(a) for a in args)})")
