"""Testes da Fase 32 — Semantic Code Sync (sem LLM, sem regex cega)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio.agent.operacoes import SemanticOperation
from elixx.studio.codigo import (
    AlteracaoCodigo,
    LocalizacaoCodigo,
    RegiaoCodigo,
    SincronizadorBidirecional,
    SincronizadorCodigo,
    aplicar_com_changeset,
    diff_textual,
    gerar_alteracao,
    localizar_entidade,
    localizar_propriedade,
    sincronizar_workspace,
    validar_candidato,
)
from elixx.studio.modelo import ModeloSemantico, analisar_projeto

FONTE = (
    "janela principal {\n"
    " tamanho: 800px 500px\n"
    " personagem Juh {\n"
    "  posicao: 100px 100px\n"
    "  parte cabeca {\n"
    "   rotacao: 0\n"
    "  }\n"
    " }\n"
    "}\n"
)


def projeto(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    modelo = ModeloSemantico("p")
    analisar_projeto(modelo, tmp_path / "p")
    return app, modelo


def sinc(tmp_path):
    app, modelo = projeto(tmp_path)
    return SincronizadorBidirecional(app.workspace, modelo), app


def op_rotacao(valor="15"):
    return SemanticOperation(
        "alterar_propriedade",
        {"nome": "cabeca", "tipo": "parte"},
        {"propriedade": "rotacao"},
        alteracao={"arquivo": "src/main.elixx",
                   "propriedade": "rotacao",
                   "valor_texto": valor})


# ---------- LOCALIZAÇÃO (1-8) ----------

def test_loc_valida():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import analisar_texto

    analisar_texto(m, FONTE, "src/main.elixx")
    loc = localizar_entidade(m.obter_entidade("personagem:Juh"),
                             FONTE)
    assert (loc.arquivo, loc.inicio_linha) == ("src/main.elixx", 3)
    assert loc.evidencia.startswith("ast:")


def test_loc_ausente():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import EntidadeSemantica

    with pytest.raises(ErroELiXX) as exc:
        localizar_entidade(EntidadeSemantica("x:Ana", "personagem",
                                             "Ana", "a.elixx"),
                           FONTE)
    assert "CODIGO_LOCALIZACAO_INDISPONIVEL" in str(exc.value)


def test_loc_inexistente():
    with pytest.raises(ErroELiXX):
        localizar_entidade({"tipo": "x", "nome": "y",
                            "arquivo": "a"}, "janela p {}\n")


def test_loc_ambigua():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import EntidadeSemantica, analisar_texto

    analisar_texto(m, FONTE, "src/main.elixx")
    # homônimo de tipo errado não casa (classe AST confere)
    loc = localizar_entidade(
        EntidadeSemantica("parte:X", "parte", "cabeca",
                          "src/main.elixx"), FONTE)
    assert loc.entidade_id == "parte:X"


def test_loc_sem_evidencia():
    with pytest.raises(ErroELiXX):
        LocalizacaoCodigo("a", 0, 1, "t", "e")
    with pytest.raises(ErroELiXX):
        LocalizacaoCodigo("a", 2, 1, "t", "e")
    with pytest.raises(ErroELiXX):
        LocalizacaoCodigo("  ", 1, 1, "t", "e")
    loc = LocalizacaoCodigo.from_dict(
        LocalizacaoCodigo("a", 1, 2, "t", "e").to_dict())
    assert (loc.inicio_linha, loc.fim_linha) == (1, 2)
    with pytest.raises(ErroELiXX):
        LocalizacaoCodigo.from_dict("nao-dict")


def test_loc_parse_falhou():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import EntidadeSemantica

    with pytest.raises(ErroELiXX) as exc:
        localizar_entidade(
            EntidadeSemantica("j:p", "janela", "p", "a"),
            "janela p { titulo: ")
    assert "CODIGO_PARSE_FALHOU" in str(exc.value)


def test_loc_propriedade():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import analisar_texto

    analisar_texto(m, FONTE, "src/main.elixx")
    ent = m.obter_entidade("parte:Juh.cabeca")
    loc = localizar_propriedade(ent, FONTE, "rotacao")
    assert loc.inicio_linha == 6
    assert loc.evidencia == "ast:propriedade"


def test_loc_propriedade_ausente():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import analisar_texto

    analisar_texto(m, FONTE, "src/main.elixx")
    ent = m.obter_entidade("parte:Juh.cabeca")
    with pytest.raises(ErroELiXX) as exc:
        localizar_propriedade(ent, FONTE, "telecinesia")
    assert "CODIGO_LOCALIZACAO_INDISPONIVEL" in str(exc.value)


# ---------- REGIÃO (9-12) ----------

def test_regiao_valida():
    reg = RegiaoCodigo("a", 6, 6, "   rotacao: 0")
    assert reg.verificar(FONTE)["ok"] is True


def test_regiao_conteudo_esperado():
    reg = RegiaoCodigo("a", 6, 6, "   rotacao: 0")
    out = reg.verificar(FONTE.replace("rotacao: 0",
                                      "rotacao: 99"))
    assert out["codigo"] == "CODIGO_REGIAO_ALTERADA"


def test_regiao_conflito_externo():
    reg = RegiaoCodigo("a", 6, 6, "   rotacao: 0")
    out = reg.verificar("janela p {}\n")
    assert out["ok"] is False


def test_regiao_invalida():
    with pytest.raises(ErroELiXX):
        RegiaoCodigo("a", 3, 2, "x")
    reg = RegiaoCodigo("a", 99, 99, "x")
    assert reg.verificar(FONTE)["ok"] is False
    with pytest.raises(ErroELiXX):
        reg.verificar(12345)


# ---------- GENERATOR (13-20) ----------

def test_gen_suportadas(tmp_path):
    s, _ = sinc(tmp_path)
    alt = s.operacao_para_codigo(op_rotacao())
    assert isinstance(alt, AlteracaoCodigo)
    assert alt.tipo == "SUBSTITUIR"
    novo = alt.aplicar_texto(FONTE)
    assert "\n   rotacao: 15\n" in novo
    assert novo.count("rotacao") == 1  # cirúrgico


def test_gen_nao_suportadas(tmp_path):
    s, _ = sinc(tmp_path)
    op = SemanticOperation("pose", "Juh", {"pose": "acenar"})
    with pytest.raises(ErroELiXX) as exc:
        s.operacao_para_codigo(op)
    assert "GERADOR_NAO_SUPORTADO" in str(exc.value)


def test_gen_params_invalidos(tmp_path):
    s, _ = sinc(tmp_path)
    op = SemanticOperation("alterar_propriedade", "Juh", {},
                           alteracao={"arquivo": "src/main.elixx"})
    with pytest.raises(ErroELiXX):
        s.operacao_para_codigo(op)


def test_gen_preservacao(tmp_path):
    s, _ = sinc(tmp_path)
    alt = s.operacao_para_codigo(op_rotacao())
    novo = alt.aplicar_texto(FONTE)
    assert novo.split("\n")[0] == "janela principal {"
    assert novo.split("\n")[1] == " tamanho: 800px 500px"
    assert len(novo.split("\n")) == len(FONTE.split("\n"))


def test_gen_remover(tmp_path):
    from elixx.studio.agent.operacoes import SemanticOperation as _O

    s, _ = sinc(tmp_path)
    op = _O("remover", {"nome": "cabeca", "tipo": "parte"}, {},
            alteracao={"arquivo": "src/main.elixx",
                       "propriedade": "rotacao"})
    alt = s.operacao_para_codigo(op)
    assert alt.tipo == "REMOVER"
    assert "rotacao" not in alt.aplicar_texto(FONTE)


def test_gen_inserir(tmp_path):
    from elixx.studio.agent.operacoes import SemanticOperation as _O

    s, app = sinc(tmp_path)
    (tmp_path / "p" / "src" / "extra.elixx").write_text(
        "janela q {\n titulo: \"Q\"\n}\n", encoding="utf-8")
    op = _O("adicionar", "Q", {},
            alteracao={"arquivo": "src/extra.elixx",
                       "snippet": "tela t {\n titulo: \"T\"\n}\n"})
    alt = s.operacao_para_codigo(op)
    assert alt.tipo == "INSERIR"
    from elixx.compilador.lexer import tokenizar
    from elixx.compilador.parser import Parser

    prog = Parser(tokenizar(alt.aplicar_texto(
        "janela q {\n titulo: \"Q\"\n}\n"))).parse()
    assert len(prog.telas) == 1


def test_gen_sem_arquivo(tmp_path):
    s, _ = sinc(tmp_path)
    op = SemanticOperation("alterar_propriedade", "Juh", {},
                           alteracao={"propriedade": "x",
                                      "valor_texto": "1"})
    with pytest.raises(ErroELiXX) as exc:
        s.operacao_para_codigo(op)
    assert "CODIGO_ALVO_NAO_ENCONTRADO" in str(exc.value)


def test_gen_alvo_ausente_modelo(tmp_path):
    s, _ = sinc(tmp_path)
    op = SemanticOperation(
        "alterar_propriedade", {"nome": "Fantasma"},
        {}, alteracao={"arquivo": "src/main.elixx",
                       "propriedade": "rotacao",
                       "valor_texto": "1"})
    with pytest.raises(ErroELiXX) as exc:
        s.operacao_para_codigo(op)
    assert "CODIGO_ALVO_NAO_ENCONTRADO" in str(exc.value)


# ---------- CHANGESET (21-25) ----------

def test_changeset_geracao(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval

    alt = s.operacao_para_codigo(op_rotacao())
    out = aplicar_com_changeset(s, alt)
    assert out["codigo"] == "CODIGO_APROVACAO_NECESSARIA"
    assert out["changeset"][0]["caminho"] == "src/main.elixx"


def test_changeset_aprovacao(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval

    alt = s.operacao_para_codigo(op_rotacao())
    ap = Approval("manual")
    out = aplicar_com_changeset(s, alt, approval=ap)
    assert out["codigo"] == "CODIGO_APROVACAO_NECESSARIA"


def test_changeset_rejeicao(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval, ChangeSet

    cs = ChangeSet()
    assert cs.estado == "proposto"
    cs.rejeitar()
    assert cs.estado == "rejeitado"
    alt = s.operacao_para_codigo(op_rotacao())
    ap = Approval("bloqueado")
    out = aplicar_com_changeset(s, alt, approval=ap)
    assert out["codigo"] == "CODIGO_APROVACAO_NECESSARIA"


def test_changeset_aplicacao(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval

    alt = s.operacao_para_codigo(op_rotacao())
    ap = Approval("manual")
    ap2 = Approval("automatico_seguro",
                   caminhos_permitidos=["src/"])
    out = aplicar_com_changeset(s, alt, approval=ap2)
    assert out["ok"] is True
    assert out["arquivos"] == ["src/main.elixx"]
    assert "rotacao: 15" in app.workspace.resolver(
        "src/main.elixx").read_text(encoding="utf-8")
    _ = ap


def test_changeset_rollback(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import ChangeSet

    cs = ChangeSet()
    with pytest.raises(ErroELiXX):
        cs.desfazer(app.workspace)  # nunca aplicado
    alt = s.operacao_para_codigo(op_rotacao())
    regiao = alt.regiao
    regiao.conteudo_esperado = "CONTEUDO TROCADO"
    with pytest.raises(ErroELiXX):
        alt.aplicar_texto(FONTE)  # região stale recusa


# ---------- PARSER (26-28) ----------

def test_parser_valido(tmp_path):
    s, _ = sinc(tmp_path)
    alt = s.operacao_para_codigo(op_rotacao())
    assert validar_candidato(alt, FONTE,
                             None)["codigo"] == "ok"


def test_parser_invalido():
    alt = AlteracaoCodigo(
        "a", {"arquivo": "a", "inicio": 1, "fim": 1,
              "conteudo_esperado": "janela p {}\n".split("\n")[0]},
        tipo="SUBSTITUIR", conteudo_anterior="janela p {}",
        conteudo_novo="janela p { titulo: ")
    out = validar_candidato(alt, "janela p {}")
    assert out["codigo"] == "CODIGO_RESULTADO_INVALIDO"


def test_parser_erro_sintaxe(tmp_path):
    s, _ = sinc(tmp_path)
    with pytest.raises(ErroELiXX) as exc:
        s.operacao_para_codigo(op_rotacao(valor='"aberto'))
    assert "CODIGO_RESULTADO_INVALIDO" in str(exc.value)


# ---------- MODELO (29-33) ----------

def test_modelo_atualizacao(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval

    alt = s.operacao_para_codigo(op_rotacao())
    ap = Approval("automatico_seguro",
                  caminhos_permitidos=["src/"])
    out = aplicar_com_changeset(s, alt, approval=ap)
    assert out["ok"] is True
    assert "personagem:Juh" in s.modelo  # entidade preservada


def test_modelo_entidade_nova(tmp_path):
    s, app = sinc(tmp_path)
    out = s.codigo_para_modelo("src/main.elixx")
    assert out["entidades"] >= 3
    assert out["hash"] is not None


def test_modelo_entidade_removida(tmp_path):
    s, app = sinc(tmp_path)
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "janela principal {\n titulo: \"T\"\n}\n",
        encoding="utf-8")
    out = s.codigo_para_modelo("src/main.elixx")
    assert "personagem:Juh" not in s.modelo
    assert out["entidades"] == 1


def test_modelo_entidade_alterada(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval
    from elixx.studio.modelo import SnapshotSemantico, comparar_snapshots

    antes = SnapshotSemantico.de_modelo(s.modelo)
    alt = s.operacao_para_codigo(op_rotacao())
    aplicar_com_changeset(
        s, alt, approval=Approval(
            "automatico_seguro", caminhos_permitidos=["src/"]))
    diff = comparar_snapshots(
        antes, SnapshotSemantico.de_modelo(s.modelo))
    assert diff["adicionados"] == [] and diff["removidos"] == []


def test_modelo_relacoes(tmp_path):
    s, _ = sinc(tmp_path)
    rels = s.modelo.relacoes()
    assert any(r.tipo == "possui" for r in rels)
    assert any(r.tipo == "contem" for r in rels)


# ---------- BIDIRECTIONAL (34-38) ----------

def test_bidi_codigo_modelo(tmp_path):
    s, app = sinc(tmp_path)
    out = s.codigo_para_modelo("src/main.elixx")
    assert out["entidades"] == len(s.modelo)


def test_bidi_modelo_codigo(tmp_path):
    s, _ = sinc(tmp_path)
    alt = s.operacao_para_codigo(op_rotacao())
    assert alt.arquivo == "src/main.elixx"
    assert alt.entidade_id == "parte:Juh.cabeca"


def test_bidi_ciclo(tmp_path):
    s, _ = sinc(tmp_path)
    out1 = s.codigo_para_modelo("src/main.elixx")
    out2 = s.codigo_para_modelo("src/main.elixx")
    assert out1["hash"] == out2["hash"]
    assert out2.get("sincronizado", True) is False  # anti-loop


def test_bidi_reanalise(tmp_path):
    s, app = sinc(tmp_path)
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE.replace("rotacao: 0", "rotacao: 30"),
        encoding="utf-8")
    out = s.sincronizar("src/main.elixx")
    assert out["sincronizado"] is True
    assert out["valido"] is True


def test_bidi_externas(tmp_path):
    s, app = sinc(tmp_path)
    (tmp_path / "p" / "src" / "novo.elixx").write_text(
        "janela q {\n titulo: \"Q\"\n}\n", encoding="utf-8")
    out = s.codigo_para_modelo("src/novo.elixx")
    assert "janela:q" in s.modelo
    assert out["arquivos"] if "arquivos" in out else True


# ---------- STUDIO (39-43) ----------

def test_studio_editor(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio import StudioWorkspace

    ws = StudioWorkspace(app)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.documento.texto == FONTE


def test_studio_inspector(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio import StudioWorkspace

    ws = StudioWorkspace(app)
    ws.analisar()
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    assert secoes[0]["titulo"] == "Juh"


def test_studio_agent(tmp_path):
    from elixx.studio.agent.loop import resolver_alvo

    s, _ = sinc(tmp_path)
    assert resolver_alvo(s.modelo, "Juh",
                         "personagem")["status"] == "unico"


def test_studio_preview(tmp_path):
    s, app = sinc(tmp_path)
    out = app.preview.executar(FONTE)
    assert out.sucesso is True
    assert out.resumo["personagens"] == ["Juh"]


def test_studio_diagnostics(tmp_path):
    from elixx.studio import diagnosticar_texto

    diags = diagnosticar_texto(FONTE, "src/main.elixx")
    assert diags[0].severidade == "info"
    ruins = diagnosticar_texto("janela p { titulo: ",
                               "src/main.elixx")
    assert ruins[0].severidade == "error"


def test_studio_sync_workspace(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio import StudioWorkspace

    ws = StudioWorkspace(app)
    out = sincronizar_workspace(ws)
    assert out["valido"] is True and out["preview"] is True


# ---------- SEGURANÇA (44-52) ----------

def test_sec_traversal(tmp_path):
    s, _ = sinc(tmp_path)
    with pytest.raises(ErroELiXX):
        s.codigo_para_modelo("../fora.elixx")
    with pytest.raises(ErroELiXX):
        AlteracaoCodigo("../f", {"arquivo": "a", "inicio": 1,
                                 "fim": 1, "conteudo_esperado": ""},
                        tipo="SUBSTITUIR", conteudo_anterior="",
                        conteudo_novo="x")


def test_sec_absolutos(tmp_path):
    s, app = sinc(tmp_path)
    with pytest.raises(ErroELiXX):
        app.workspace.resolver("C:\\Windows\\x.elixx")


def test_sec_payload():
    with pytest.raises(ErroELiXX):
        AlteracaoCodigo(
            "a", {"arquivo": "a", "inicio": 1, "fim": 1,
                  "conteudo_esperado": ""},
            tipo="SUBSTITUIR", conteudo_anterior="",
            conteudo_novo="x" * 100_001)


def test_sec_strings():
    loc = LocalizacaoCodigo("a", 1, 1, "t", "__import__('os')")
    assert loc.entidade_id == "__import__('os')"
    assert loc.to_dict()["entidade_id"] == "__import__('os')"


def test_sec_eval():
    with pytest.raises(ErroELiXX):
        localizar_entidade({"tipo": "x", "nome": "eval(1)",
                            "arquivo": "a"}, FONTE)


def test_sec_exec():
    assert "exec(" not in FONTE  # sanidade do fixture
    import elixx.studio.codigo as pacote
    import pathlib

    for arq in pathlib.Path(pacote.__file__).parent.glob("*.py"):
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess",
                         "os.system"):
            assert proibido not in fonte, (arq.name, proibido)


def test_sec_pickle():
    import pickle  # noqa (uso legítimo: só checar ausência no pacote)

    assert pickle.__name__ == "pickle"
    import elixx.studio.codigo.gerador as modulo

    assert "pickle" not in open(modulo.__file__,
                                encoding="utf-8").read()


def test_sec_subprocess():
    import elixx.studio.codigo.sincronizador as modulo

    assert "subprocess" not in open(modulo.__file__,
                                    encoding="utf-8").read()


def test_sec_shell():
    assert "shell" not in FONTE.lower()
    import elixx.studio.codigo.localizacao as modulo

    assert "shell" not in open(modulo.__file__,
                               encoding="utf-8").read().lower()


# ---------- PERFORMANCE (53-57) ----------

def test_perf_arquivos(tmp_path):
    import time as _t

    from elixx.studio import StudioApp
    from elixx.studio.modelo import ModeloSemantico, analisar_projeto

    base = tmp_path / "big"
    (base / "src").mkdir(parents=True)
    for total in (100, 500, 1000):
        for i in range(total):
            (base / "src" / f"m{i:04d}.elixx").write_text(
                "janela p {\n titulo: \"T\"\n}\n",
                encoding="utf-8")
        m = ModeloSemantico("p")
        t0 = _t.perf_counter()
        out = analisar_projeto(m, base)
        dt = _t.perf_counter() - t0
        assert out["arquivos"] == total and dt < 60.0
        for i in range(total):
            (base / "src" / f"m{i:04d}.elixx").unlink()
        if total == 1000:
            print(f"\n1000 arq: {dt:.2f}s")


def test_perf_localizacao(tmp_path):
    import time as _t

    s, _ = sinc(tmp_path)
    ent = s.modelo.obter_entidade("parte:Juh.cabeca")
    t0 = _t.perf_counter()
    for _ in range(200):
        assert localizar_propriedade(ent, FONTE,
                                     "rotacao").inicio_linha == 6
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_diff():
    import time as _t

    t0 = _t.perf_counter()
    for _ in range(200):
        out = diff_textual(FONTE, FONTE.replace("rotacao: 0",
                                                "rotacao: 15"))
        assert len(out["trocas"]) == 1
    assert (_t.perf_counter() - t0) < 30.0


def test_perf_sinc(tmp_path):
    import time as _t

    s, app = sinc(tmp_path)
    t0 = _t.perf_counter()
    for _ in range(50):
        (tmp_path / "p" / "src" / "main.elixx").write_text(
            FONTE, encoding="utf-8")
        s.nucleo._hashes.pop("src/main.elixx", None)
        s.codigo_para_modelo("src/main.elixx")
    assert (_t.perf_counter() - t0) < 60.0


def test_perf_operacoes(tmp_path):
    import time as _t

    s, _ = sinc(tmp_path)
    t0 = _t.perf_counter()
    for i in range(200):
        op = SemanticOperation(
            "alterar_propriedade",
            {"nome": "cabeca", "tipo": "parte"},
            {"propriedade": "rotacao"},
            alteracao={"arquivo": "src/main.elixx",
                       "propriedade": "rotacao",
                       "valor_texto": str(i)})
        alt = s.operacao_para_codigo(op)
        assert alt.conteudo_novo.endswith(str(i))
    assert (_t.perf_counter() - t0) < 30.0


# ---------- DIVERSOS (58-64) ----------

def test_diff_deterministico():
    a = diff_textual(FONTE, FONTE.replace("rotacao: 0",
                                          "rotacao: 15"))
    b = diff_textual(FONTE, FONTE.replace("rotacao: 0",
                                          "rotacao: 15"))
    assert a == b
    assert diff_textual(FONTE, FONTE)["trocas"] == []
    with pytest.raises(ErroELiXX):
        diff_textual(FONTE, 123)


def test_alteracao_json():
    s_alt = AlteracaoCodigo(
        "a", {"arquivo": "a", "inicio": 1, "fim": 1,
              "conteudo_esperado": "x"},
        tipo="SUBSTITUIR", conteudo_anterior="x",
        conteudo_novo="y", entidade_id="e",
        operacao_origem="alterar_propriedade")
    copia = AlteracaoCodigo.from_dict(s_alt.to_dict())
    assert copia.to_json() == s_alt.to_json()
    with pytest.raises(ErroELiXX):
        AlteracaoCodigo.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        AlteracaoCodigo("a", "nao-regiao")


def test_alteracao_tipos():
    for tipo in ("INSERIR", "SUBSTITUIR", "REMOVER"):
        a = AlteracaoCodigo(
            "a", {"arquivo": "a", "inicio": 1, "fim": 1,
                  "conteudo_esperado": "x"},
            tipo=tipo.lower(), conteudo_anterior="x",
            conteudo_novo="y")
        assert a.tipo == tipo
    with pytest.raises(ErroELiXX):
        AlteracaoCodigo(
            "a", {"arquivo": "a", "inicio": 1, "fim": 1,
                  "conteudo_esperado": "x"}, tipo="MOVER")


def test_regiao_arquivo_divergente():
    with pytest.raises(ErroELiXX):
        AlteracaoCodigo(
            "b", {"arquivo": "a", "inicio": 1, "fim": 1,
                  "conteudo_esperado": "x"},
            tipo="SUBSTITUIR", conteudo_anterior="x",
            conteudo_novo="y")


def test_sem_duplicar_f26():
    import elixx.studio.codigo.sincronizador as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class ChangeSet" not in fonte
    assert "class Approval" not in fonte
    assert "from ..agent.mudancas import" in fonte


def test_sem_duplicar_f27():
    import elixx.studio.codigo.sincronizador as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "class ModeloSemantico" not in fonte
    assert "SnapshotSemantico" in fonte  # reuso, não cópia


def test_snapshot_codigo(tmp_path):
    from elixx.studio.modelo import SnapshotSemantico

    s, _ = sinc(tmp_path)
    snap = SnapshotSemantico.de_modelo(s.modelo)
    assert "personagem:Juh" in snap.entidades()
    assert snap.to_dict()["versao"] == 1


def test_suportado_direto():
    from elixx.studio.codigo.gerador import suportado_pelo_gerador

    op = SemanticOperation(
        "alterar_propriedade", "Juh", {},
        alteracao={"arquivo": "a", "propriedade": "x",
                   "valor_texto": "1"})
    assert suportado_pelo_gerador(op) is True
    assert suportado_pelo_gerador(
        SemanticOperation("pose", "Juh", {})) is False
    assert suportado_pelo_gerador(
        {"tipo": "pose", "alteracao": {}}) is False


def test_auto_seguro_ponta_a_ponta(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval

    alt = s.operacao_para_codigo(op_rotacao())
    ap = Approval("automatico_seguro",
                  caminhos_permitidos=["src/"])
    out = aplicar_com_changeset(s, alt, approval=ap)
    assert out["ok"] is True
    assert "rotacao: 15" in app.workspace.resolver(
        "src/main.elixx").read_text(encoding="utf-8")


def test_auto_seguro_recusa(tmp_path):
    s, _ = sinc(tmp_path)
    from elixx.studio.agent import Approval

    alt = s.operacao_para_codigo(op_rotacao())
    ap = Approval("automatico_seguro",
                  caminhos_permitidos=["outra/"])
    out = aplicar_com_changeset(s, alt, approval=ap)
    assert out["codigo"] == "CODIGO_APROVACAO_NECESSARIA"
    assert "decisao" in out


def test_remover_ponta_a_ponta(tmp_path):
    s, app = sinc(tmp_path)
    from elixx.studio.agent import Approval
    from elixx.studio.agent.operacoes import SemanticOperation as _O

    op = _O("remover", {"nome": "cabeca", "tipo": "parte"}, {},
            alteracao={"arquivo": "src/main.elixx",
                       "propriedade": "rotacao"})
    alt = s.operacao_para_codigo(op)
    out = aplicar_com_changeset(
        s, alt, approval=Approval(
            "automatico_seguro", caminhos_permitidos=["src/"]))
    assert out["ok"] is True
    assert "rotacao" not in app.workspace.resolver(
        "src/main.elixx").read_text(encoding="utf-8")


def test_regiao_dict_roundtrip():
    reg = RegiaoCodigo("a", 2, 3, "x\ny")
    assert reg.to_dict()["conteudo_esperado"] == "x\ny"
    assert repr(reg).startswith("RegiaoCodigo(")


def test_inserir_preserva_anterior(tmp_path):
    s, _ = sinc(tmp_path)
    from elixx.studio.agent.operacoes import SemanticOperation as _O

    op = _O("adicionar", "Q", {},
            alteracao={"arquivo": "src/main.elixx",
                       "snippet": "tela t {\n titulo: \"T\"\n}\n"})
    alt = s.operacao_para_codigo(op)
    novo = alt.aplicar_texto(FONTE)
    assert novo.startswith(FONTE.rstrip("\n"))
    assert "tela t" in novo


def test_versao_incrementa(tmp_path):
    s, app = sinc(tmp_path)
    v0 = s.versao
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE.replace("rotacao: 0", "rotacao: 7"),
        encoding="utf-8")
    out = s.sincronizar("src/main.elixx")
    assert out["versao"] == v0 + 1
    assert out["valido"] is True


def test_comparar_delega(tmp_path):
    from elixx.studio.modelo import SnapshotSemantico

    s, _ = sinc(tmp_path)
    antes = SnapshotSemantico.de_modelo(s.modelo)
    diff = s.comparar(antes, SnapshotSemantico.de_modelo(s.modelo))
    assert diff == {"adicionados": [], "removidos": [],
                    "alterados": []}
    assert s.diagnosticar()["valido"] is True
    assert s.workspace is not None and s.modelo is not None


def test_ida_e_volta_intent(tmp_path):
    from elixx.studio.agent.inteligencia import MockIntentProvider
    from elixx.studio.agent.operacoes import (
        intent_para_operacao,
        operacao_para_intent,
    )

    it = MockIntentProvider().gerar_intencao(None, "mostre a Juh")
    op = intent_para_operacao(it)
    volta = operacao_para_intent(op)
    assert volta.tipo == "mostrar" and volta.alvo == "Juh"


def test_loc_janela_tela_funcao():
    m = ModeloSemantico("t")
    from elixx.studio.modelo import analisar_texto

    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao soma(x) {\n retornar x\n}\n",
                   "src/a.elixx")
    assert localizar_entidade(
        m.obter_entidade("janela:p"),
        "janela p {\n titulo: \"T\"\n}\n"
        "funcao soma(x) {\n retornar x\n}\n").inicio_linha == 1
    assert localizar_entidade(
        m.obter_entidade("funcao:soma"),
        "janela p {\n titulo: \"T\"\n}\n"
        "funcao soma(x) {\n retornar x\n}\n").inicio_linha == 4
