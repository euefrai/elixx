"""Expansão de componentes reutilizáveis (Fase 08).

`componente Nome { ... }` define; `Nome inst { ... }` instancia. A
expansão roda entre parse e semântica (cli.pipeline): substitui cada
Instancia por Componentes reais, com parâmetros trocados, nomes
internos isolados (`inst__nome`) e slot `conteudo` preenchido.

Regras: sem recursão (erro claro), sem nomes duplicados de definição,
parâmetros conferidos, eventos da instância vão para a primeira raiz.
"""
from __future__ import annotations

import copy

from ..erros import ErroSemantico, sugerir
from . import ast as A


def expandir_componentes(programa: A.Programa) -> None:
    """Expande in-place todas as instâncias do programa."""
    defs: dict[str, A.ComponenteDef] = {}
    for definicao in programa.componentes:
        if definicao.nome in defs:
            raise ErroSemantico(
                f'Componente "{definicao.nome}" definido duas vezes.',
                linha=definicao.linha,
            )
        defs[definicao.nome] = definicao
    for janela in list(programa.janelas) + list(programa.telas):
        janela.componentes = _expandir_lista(
            janela.componentes, defs, janela, programa, pilha=())
        for anim in janela.animacoes:
            _reescrever_alvo_anim(anim, janela)


def _reescrever_alvo_anim(anim, janela) -> None:
    # alvos renomeados pela expansão (mapa guardado na janela)
    mapa = getattr(janela, "_mapa_nomes", {})
    if anim.alvo in mapa:
        anim.alvo = mapa[anim.alvo]


def _expandir_lista(itens: list, defs: dict, janela, programa,
                     pilha: tuple, em_modelo: bool = False) -> list:
    saida: list = []
    for item in itens:
        if isinstance(item, A.Instancia):
            saida.extend(_expandir_instancia(item, defs, janela, programa,
                                             pilha, em_modelo))
        elif isinstance(item, A.Componente):
            item.filhos = _expandir_lista(item.filhos, defs, janela,
                                          programa, pilha, em_modelo)
            item.modelo = _expandir_lista(item.modelo, defs, janela,
                                          programa, pilha, True)
            saida.append(item)
        elif isinstance(item, A.Personagem):
            # Fase 12: instanciações dentro de personagem/parte expandem;
            # poses guardam só nomes (resolvidos no Character Core).
            item.filhos = _expandir_lista(item.filhos, defs, janela,
                                          programa, pilha, em_modelo)
            for parte in item.partes:
                _expandir_parte(parte, defs, janela, programa, pilha,
                                em_modelo)
            saida.append(item)
        else:
            saida.append(item)
    return saida


def _expandir_parte(parte: A.Parte, defs: dict, janela, programa,
                    pilha: tuple, em_modelo: bool = False) -> None:
    """Expande in-place instanciações dentro de uma parte (recursivo)."""
    parte.filhos = _expandir_lista(parte.filhos, defs, janela, programa,
                                   pilha, em_modelo)
    for sub in parte.partes:
        _expandir_parte(sub, defs, janela, programa, pilha, em_modelo)


def _expandir_instancia(inst: A.Instancia, defs: dict, janela, programa,
                        pilha: tuple, em_modelo: bool = False) -> list:
    if inst.tipo_nome not in defs:
        parecidos = sugerir(inst.tipo_nome, sorted(defs))
        dica = (f" Você quis dizer: {', '.join(parecidos)}?"
                if parecidos else "")
        raise ErroSemantico(
            f'Componente "{inst.tipo_nome}" não definido.{dica} '
            "Crie com componente Nome { ... }.",
            linha=inst.linha,
        )
    if inst.tipo_nome in pilha:
        ciclo = " → ".join(list(pilha) + [inst.tipo_nome])
        raise ErroSemantico(
            f"Componente recursivo: {ciclo}. Componentes não podem "
            "conter a si mesmos.",
            linha=inst.linha,
        )
    definicao = defs[inst.tipo_nome]
    args = _conferir_argumentos(inst, definicao)
    corpo = copy.deepcopy(definicao.corpo)
    # nomes internos isolados: inst__nome (filhos do slot são públicos:
    # o usuário os nomeou no uso, então não recebem prefixo)
    nomes_internos = _nomes_subarvore(corpo)
    prefixo = f"{inst.nome}__"
    mapa = {antigo: prefixo + antigo for antigo in nomes_internos}
    _renomear_subarvore(corpo, mapa)
    _marcar_origem(corpo, inst.tipo_nome)
    # Fase 09: fora de modelo, local.* vira estado.<ns>__x (estático,
    # sem contexto em runtime). Dentro de modelo, fica dinâmico
    # (namespace da linha). Padrões só existem com bloco estado.
    ns = None if em_modelo else inst.nome
    _substituir_params(corpo, args, definicao, inst,
                       ns_estatico=ns)
    if not em_modelo:
        _registrar_locais(programa, inst, definicao)
    corpo = _preencher_slot(corpo, inst, pilha, defs, janela)
    # expande instâncias aninhadas ANTES de validar raízes (assim
    # ciclos indiretos A→B→A são detectados, não mascarados)
    pilha_nova = pilha + (inst.tipo_nome,)
    expandido = _expandir_lista(corpo, defs, janela, programa, pilha_nova)
    # eventos da instância vão para a primeira raiz
    raizes = [n for n in expandido if isinstance(n, A.Componente)]
    if not raizes:
        raise ErroSemantico(
            f'Componente "{definicao.nome}" tem corpo vazio.',
            linha=definicao.linha,
        )
    for ev in inst.eventos:
        raizes[0].eventos.append(ev)
    # registra mapa p/ reescrever alvos de animação da janela
    anterior = getattr(janela, "_mapa_nomes", {})
    anterior.update(mapa)
    janela._mapa_nomes = anterior
    return expandido


def _conferir_argumentos(inst: A.Instancia,
                         definicao: A.ComponenteDef) -> dict:
    params = {p.nome: p for p in definicao.params}
    dados = {p.nome: (p.valores[0] if p.valores else None)
             for p in inst.propriedades}
    for chave in dados:
        if chave not in params:
            parecidas = sugerir(chave, sorted(params))
            dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                    if parecidas else "")
            raise ErroSemantico(
                f'"{inst.tipo_nome}" não tem propriedade "{chave}".{dica}',
                linha=inst.linha,
            )
    args = {}
    for nome, param in params.items():
        if nome in dados:
            args[nome] = copy.deepcopy(dados[nome])
        elif param.padrao is not None:
            args[nome] = copy.deepcopy(param.padrao)
        else:
            raise ErroSemantico(
                f'Falta a propriedade "{nome}" em {inst.nome!r} '
                f'(componente "{inst.tipo_nome}").',
                linha=inst.linha,
            )
    return args


def _nomes_subarvore(corpo: list) -> set[str]:
    nomes: set[str] = set()
    pilha = list(corpo)
    while pilha:
        no = pilha.pop()
        if isinstance(no, A.Componente):
            if no.nome:
                nomes.add(no.nome)
            pilha.extend(no.filhos)
            pilha.extend(no.modelo)
        elif isinstance(no, A.Instancia):
            if no.nome:
                nomes.add(no.nome)
            pilha.extend(no.filhos)
        elif isinstance(no, A.Personagem):
            # Fase 12: personagem/parte entram no isolamento por instância.
            if no.nome:
                nomes.add(no.nome)
            pilha.extend(no.filhos)
            for parte in no.partes:
                _nomes_parte(parte, nomes)
    return nomes


def _nomes_parte(parte: A.Parte, nomes: set[str]) -> None:
    if parte.nome:
        nomes.add(parte.nome)
    for sub in parte.partes:
        _nomes_parte(sub, nomes)
    for filho in parte.filhos:
        if isinstance(filho, (A.Componente, A.Instancia)) and filho.nome:
            nomes.add(filho.nome)


def _renomear_subarvore(corpo: list, mapa: dict) -> None:
    pilha = list(corpo)
    while pilha:
        no = pilha.pop()
        if isinstance(no, A.Componente):
            if no.nome in mapa:
                no.nome = mapa[no.nome]
            for ev in no.eventos:
                _reescrever_textos(ev.bloco, mapa)
            pilha.extend(no.filhos)
            pilha.extend(no.modelo)
        elif isinstance(no, A.Instancia):
            if no.nome in mapa:
                no.nome = mapa[no.nome]
            pilha.extend(no.filhos)
        elif isinstance(no, A.Personagem):
            # Fase 12: isola personagem/partes/refs de pose por instância.
            if no.nome in mapa:
                no.nome = mapa[no.nome]
            for pose in no.poses:
                for entrada in pose.entradas:
                    if entrada.parte in mapa:
                        entrada.parte = mapa[entrada.parte]
            pilha.extend(no.filhos)
            for parte in no.partes:
                _renomear_parte(parte, mapa)


def _renomear_parte(parte: A.Parte, mapa: dict) -> None:
    if parte.nome in mapa:
        parte.nome = mapa[parte.nome]
    for sub in parte.partes:
        _renomear_parte(sub, mapa)
    for filho in parte.filhos:
        if isinstance(filho, (A.Componente, A.Instancia)):
            if filho.nome in mapa:
                filho.nome = mapa[filho.nome]


def _reescrever_textos(bloco, mapa: dict) -> None:
    for cmd in bloco.comandos:
        if isinstance(cmd, A.Acao):
            for i, arg in enumerate(cmd.args):
                if (isinstance(arg, A.TextoLit) and arg.valor in mapa):
                    cmd.args[i] = A.TextoLit(valor=mapa[arg.valor],
                                             linha=arg.linha)
        elif isinstance(cmd, A.Se):
            _reescrever_textos(cmd.entao, mapa)
            if cmd.senao is not None:
                _reescrever_textos(cmd.senao, mapa)
        elif isinstance(cmd, A.Repetir):
            _reescrever_textos(cmd.bloco, mapa)


def _marcar_origem(corpo: list, def_nome: str) -> None:
    """Carimba a def de origem (estado local dinâmico por linha)."""
    pilha = list(corpo)
    while pilha:
        no = pilha.pop()
        if isinstance(no, A.Componente):
            no._def_origem = def_nome
            pilha.extend(no.filhos)
            pilha.extend(no.modelo)
        elif isinstance(no, A.Instancia):
            pilha.extend(no.filhos)


def _substituir_params(corpo: list, args: dict,
                        definicao: A.ComponenteDef, inst,
                        ns_estatico: str | None = None) -> None:
    """Troca param.* pelos args. Com ns_estatico, reescreve local.X
    estático → estado.<ns>__X (Fase 09); dentro de modelo, local.*
    fica para o runtime (namespace da linha)."""
    conhecidos = set(args)

    def trocar(expr, no_modelo: bool = False):
        if isinstance(expr, A.Membro):
            caminho = A.caminho_de_membro(expr)
            partes = caminho.split(".")
            if partes[0] == "param":
                # Fase 09: param.x ou param.x.y (aninhado).
                if len(partes) < 2 or partes[1] not in conhecidos:
                    parecidas = sugerir(partes[1] if len(partes) > 1 else "",
                                        sorted(conhecidos))
                    dica = (f" Você quis dizer: {', '.join(parecidas)}?"
                            if parecidas else "")
                    raise ErroSemantico(
                        f'Parâmetro desconhecido: "{caminho}".{dica} '
                        f'Parâmetros de "{definicao.nome}": '
                        f"{', '.join(sorted(conhecidos)) or 'nenhum'}.",
                        linha=expr.linha,
                    )
                no = copy.deepcopy(args[partes[1]])
                for atributo in partes[2:]:
                    no = A.Membro(base=no, atributo=atributo,
                                  linha=expr.linha)
                return no
            if (partes[0] == "local" and len(partes) == 2
                    and ns_estatico is not None and not no_modelo):
                return A.Membro(
                    base=A.Ident(nome="estado", linha=expr.linha),
                    atributo=f"{ns_estatico}__{partes[1]}",
                    linha=expr.linha)
            # item.* / local.* em modelo ficam p/ o runtime (linha);
            # param fora de def e item fora de modelo o parser já barrou.
            if isinstance(expr.base, A.Membro):
                expr.base = trocar(expr.base, no_modelo)
            return expr
        if isinstance(expr, A.Binaria):
            expr.esquerda = trocar(expr.esquerda, no_modelo)
            expr.direita = trocar(expr.direita, no_modelo)
            return expr
        if isinstance(expr, A.ListaLit):
            expr.itens = [trocar(item, no_modelo) for item in expr.itens]
            return expr
        if isinstance(expr, A.Chamada):
            expr.args = [trocar(a, no_modelo) for a in expr.args]
            return expr
        return expr

    def em_comandos(bloco, no_modelo: bool = False) -> None:
        for i, cmd in enumerate(bloco.comandos):
            if isinstance(cmd, A.Acao):
                cmd.args = [trocar(a, no_modelo) for a in cmd.args]
            elif isinstance(cmd, A.Atribuicao):
                if isinstance(cmd.alvo, A.Membro):
                    alvo = A.caminho_de_membro(cmd.alvo)
                    partes = alvo.split(".")
                    if (partes[0] == "local" and len(partes) == 2
                            and ns_estatico is not None and not no_modelo):
                        cmd.alvo = A.Membro(
                            base=A.Ident(nome="estado",
                                         linha=cmd.alvo.linha),
                            atributo=f"{ns_estatico}__{partes[1]}",
                            linha=cmd.alvo.linha)
                cmd.valor = trocar(cmd.valor, no_modelo)
            elif isinstance(cmd, A.Se):
                cmd.condicao = trocar(cmd.condicao, no_modelo)
                em_comandos(cmd.entao, no_modelo)
                if cmd.senao is not None:
                    em_comandos(cmd.senao, no_modelo)
            elif isinstance(cmd, A.Repetir):
                em_comandos(cmd.bloco, no_modelo)
            elif isinstance(cmd, A.Retornar) and cmd.valor is not None:
                cmd.valor = trocar(cmd.valor, no_modelo)

    def em_comp(no, no_modelo: bool = False) -> None:
        for prop in no.propriedades:
            prop.valores = [trocar(v, no_modelo) for v in prop.valores]
        for ev in no.eventos:
            em_comandos(ev.bloco, no_modelo)
        for filho in no.filhos:
            if isinstance(filho, A.Componente):
                em_comp(filho, no_modelo)
            elif isinstance(filho, A.Personagem):
                em_personagem(filho, no_modelo)
        for modelo in no.modelo:
            if isinstance(modelo, A.Componente):
                em_comp(modelo, True)

    def em_parte(parte, no_modelo: bool = False) -> None:
        # Fase 12: params/locais dentro de partes do personagem.
        for prop in parte.propriedades:
            prop.valores = [trocar(v, no_modelo) for v in prop.valores]
        for sub in parte.partes:
            em_parte(sub, no_modelo)
        for filho in parte.filhos:
            if isinstance(filho, A.Componente):
                em_comp(filho, no_modelo)
            elif isinstance(filho, A.Personagem):
                em_personagem(filho, no_modelo)

    def em_personagem(boneco, no_modelo: bool = False) -> None:
        for prop in boneco.propriedades:
            prop.valores = [trocar(v, no_modelo) for v in prop.valores]
        for parte in boneco.partes:
            em_parte(parte, no_modelo)
        for filho in boneco.filhos:
            if isinstance(filho, A.Componente):
                em_comp(filho, no_modelo)
            elif isinstance(filho, A.Personagem):
                em_personagem(filho, no_modelo)

    for no in corpo:
        if isinstance(no, A.Componente):
            em_comp(no)
        elif isinstance(no, A.Personagem):
            em_personagem(no)


def _registrar_locais(programa, inst, definicao) -> None:
    """Padrões do estado local: programa.locais[ns][chave] = valor."""
    bloco = getattr(definicao, "estado", None)
    if bloco is None:
        return
    valores = {}
    for prop in bloco.propriedades:
        valor = prop.valores[0] if prop.valores else None
        valores[prop.nome] = _literal_para_valor(valor)
    programa.locais[inst.nome] = valores


def _literal_para_valor(valor: object):
    from . import ast as _A

    if isinstance(valor, _A.TextoLit):
        return valor.valor
    if isinstance(valor, _A.NumeroLit):
        return valor.valor
    if isinstance(valor, _A.Booleano):
        return valor.valor
    if isinstance(valor, _A.ListaLit):
        return [_literal_para_valor(item) for item in valor.itens]
    return None


def _preencher_slot(corpo: list, inst: A.Instancia,
                    pilha: tuple, defs: dict, janela) -> list:
    filhos = [copy.deepcopy(f) for f in inst.filhos]

    def tem_slot(nos: list) -> bool:
        for no in nos:
            if isinstance(no, A.Componente):
                if no.tipo == "conteudo":
                    return True
                if tem_slot(no.filhos) or tem_slot(no.modelo):
                    return True
        return False

    def preencher(nos: list) -> list:
        saida = []
        for no in nos:
            if isinstance(no, A.Componente) and no.tipo == "conteudo":
                if no.propriedades or no.eventos:
                    raise ErroSemantico(
                        'O marcador "conteudo" não aceita propriedades '
                        "nem eventos (só marca o lugar).",
                        linha=no.linha,
                    )
                saida.extend(copy.deepcopy(f) for f in filhos)
            else:
                if isinstance(no, A.Componente):
                    no.filhos = preencher(no.filhos)
                    no.modelo = preencher(no.modelo)
                saida.append(no)
        return saida

    if filhos and not tem_slot(corpo):
        raise ErroSemantico(
            f'A instância {inst.nome!r} tem filhos mas "{inst.tipo_nome}" '
            'não tem marcador "conteudo".',
            linha=inst.linha,
        )
    return preencher(corpo)
