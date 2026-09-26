"""Testes da Fase 27 — Semantic Project Model (leitura, sem LLM)."""
import json

import pytest

from elixx.erros import ErroELiXX
from elixx.studio.modelo import (
    AdaptadorAST,
    ConsultaSemantica,
    EntidadeSemantica,
    IndiceSemantico,
    ModeloSemantico,
    MutacaoSemantica,
    RelacaoSemantica,
    SnapshotSemantico,
    analisar_projeto,
    analisar_texto,
    atualizar_arquivo,
    comparar_snapshots,
    modelo_para_contexto,
    mutacao_para_changeset,
    resumo_para_inspetor,
    validar_modelo,
)

FONTE_JUH = (
    "janela p {\n"
    ' titulo: "T"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    '   imagem: "corpo.png"\n'
    "  }\n"
    "  parte cabeca {\n"
    "  }\n"
    "  pose neutra {\n"
    "   corpo:\n"
    "    rotacao: 0deg\n"
    "  }\n"
    "  expressao sorriso {\n"
    "   cabeca:\n"
    "    rotacao: 5deg\n"
    "  }\n"
    " }\n"
    " botao entrar {\n"
    '  texto: "Entrar"\n'
    " }\n"
    "}\n"
)


def modelo_juh():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE_JUH, "src/main.elixx")
    return m


# ---------- entidade (1-6) ----------

def test_entidade():
    e = EntidadeSemantica("personagem:juh", "personagem", "Juh",
                          "personagens/juh.elixx", linha=3,
                          tags=["principal"])
    assert e.id == "personagem:juh" and e.linha == 3
    assert EntidadeSemantica.from_dict(e.to_dict()).nome == "Juh"


def test_entidade_tipos():
    for tipo in ("tela", "componente", "pose", "animacao",
                 "asset", "evento", "estado", "arquivo"):
        assert EntidadeSemantica(f"x:{tipo}", tipo).tipo == tipo
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("x", "nave_espacial")


def test_entidade_campos_opcionais():
    e = EntidadeSemantica("a:b", "simbolo")
    assert e.nome == "" and e.arquivo == "" and e.linha is None
    assert e.dados == {} and e.tags == []


def test_entidade_invalida():
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("  ", "personagem")
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("a", "personagem", linha=-1)
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("a", "personagem",
                          dados={"f": object()})
    with pytest.raises(ErroELiXX):
        EntidadeSemantica.from_dict("nao-dict")


def test_entidade_linha():
    assert EntidadeSemantica("a", "simbolo", linha=0).linha == 0
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("a", "simbolo", linha="dez")


# ---------- relação (7-10) ----------

def test_relacao():
    r = RelacaoSemantica("personagem:juh", "possui",
                         "parte:juh.corpo")
    assert r.to_dict()["tipo"] == "possui"
    assert RelacaoSemantica.from_dict(r.to_dict()).destino == \
        "parte:juh.corpo"


def test_relacao_tipos():
    for tipo in ("contem", "usa_asset", "atua_em", "responde",
                 "depende_de", "define", "referencia"):
        assert RelacaoSemantica("a", tipo, "b").tipo == tipo
    with pytest.raises(ErroELiXX):
        RelacaoSemantica("a", "teleporta", "b")


def test_relacao_ids():
    with pytest.raises(ErroELiXX):
        RelacaoSemantica("", "possui", "b")
    with pytest.raises(ErroELiXX):
        RelacaoSemantica("a", "possui", "  ")
    with pytest.raises(ErroELiXX):
        RelacaoSemantica.from_dict([])


# ---------- modelo (11-16) ----------

def test_modelo_crud():
    m = ModeloSemantico("t")
    m.adicionar_entidade(EntidadeSemantica("a", "simbolo", "A"))
    assert "a" in m and len(m) == 1
    assert m.obter_entidade("a").nome == "A"
    assert [e.id for e in m.entidades()] == ["a"]
    m.remover_entidade("a")
    assert len(m) == 0
    with pytest.raises(ErroELiXX):
        m.obter_entidade("a")


def test_modelo_duplicada():
    m = ModeloSemantico("t")
    m.adicionar_entidade(EntidadeSemantica("a", "simbolo"))
    with pytest.raises(ErroELiXX):
        m.adicionar_entidade(EntidadeSemantica("a", "simbolo"))
    with pytest.raises(ErroELiXX):
        m.adicionar_entidade("nao-entidade")


def test_modelo_relacoes():
    m = ModeloSemantico("t")
    m.adicionar_entidade(EntidadeSemantica("a", "simbolo"))
    m.adicionar_entidade(EntidadeSemantica("b", "simbolo"))
    m.adicionar_relacao(RelacaoSemantica("a", "possui", "b"))
    assert len(m.relacoes()) == 1
    with pytest.raises(ErroELiXX):
        m.adicionar_relacao(RelacaoSemantica("a", "possui", "b"))
    with pytest.raises(ErroELiXX):
        m.adicionar_relacao(RelacaoSemantica("a", "possui",
                                             "fantasma"))
    m.remover_relacao("a", "possui", "b")
    assert m.relacoes() == []
    with pytest.raises(ErroELiXX):
        m.remover_relacao("a", "possui", "b")


def test_modelo_remove_limpa_relacoes():
    m = modelo_juh()
    total_antes = len(m.relacoes())
    assert total_antes > 0
    m.remover_entidade("personagem:Juh")
    assert all(r.origem != "personagem:Juh"
               and r.destino != "personagem:Juh"
               for r in m.relacoes())
    assert len(m.relacoes()) < total_antes


def test_modelo_arquivos_diagnosticos():
    m = ModeloSemantico("t")
    reg = m.registrar_arquivo("src/a.elixx", status="ok",
                              conteudo_hash="abc123")
    assert reg["hash"] == "abc123"
    assert m.arquivos()[0]["caminho"] == "src/a.elixx"
    m.adicionar_diagnostico({"codigo": "parse"})
    assert m.diagnosticos() == [{"codigo": "parse"}]
    with pytest.raises(ErroELiXX):
        m.registrar_arquivo("../fora.elixx")
    with pytest.raises(ErroELiXX):
        m.adicionar_diagnostico("nao-dict")


def test_modelo_json():
    m = modelo_juh()
    copia = ModeloSemantico.from_dict(m.to_dict())
    assert copia.to_json() == m.to_json()
    with pytest.raises(ErroELiXX):
        ModeloSemantico.from_dict("nao-dict")


# ---------- índice (17-20) ----------

def test_indice():
    m = modelo_juh()
    idx = IndiceSemantico(m)
    assert idx.buscar_por_id("personagem:Juh").nome == "Juh"
    assert [e.id for e in idx.buscar_por_nome("Juh")] == \
        ["personagem:Juh"]
    assert idx.buscar_por_nome("Fantasma") == []
    with pytest.raises(ErroELiXX):
        idx.buscar_por_id("fantasma")


def test_indice_tipo_arquivo():
    m = modelo_juh()
    idx = IndiceSemantico(m)
    assert {e.tipo for e in idx.buscar_por_tipo(
        "personagem")} == {"personagem"}
    assert len(idx.buscar_por_arquivo("src/main.elixx")) == len(m)
    assert idx.buscar_por_tipo("nave") == []


def test_indice_relacoes():
    m = modelo_juh()
    idx = IndiceSemantico(m)
    de = idx.buscar_relacoes_de("personagem:Juh")
    para = idx.buscar_relacoes_para("parte:Juh.corpo")
    assert any(r.tipo == "possui" for r in de)
    assert any(r.tipo == "possui" for r in para)
    assert idx.buscar_relacoes_de("fantasma") == []


def test_indice_reconstroi():
    m = ModeloSemantico("t")
    idx = IndiceSemantico(m)
    assert idx.buscar_por_nome("X") == []
    m.adicionar_entidade(EntidadeSemantica("x", "simbolo", "X"))
    assert idx.buscar_por_nome("X") == []  # índice antigo
    idx.reconstruir()
    assert [e.id for e in idx.buscar_por_nome("X")] == ["x"]


# ---------- consulta (21-24) ----------

def test_consulta():
    m = modelo_juh()
    q = ConsultaSemantica(m)
    assert [e.id for e in q.encontrar_por_nome("Juh")] == \
        ["personagem:Juh"]
    assert len(q.encontrar_por_tipo("parte")) == 2
    assert len(q.encontrar_por_arquivo("src/main.elixx")) == len(m)
    assert len(q.relacoes_de("personagem:Juh")) >= 2
    assert len(q.relacoes_para("asset:corpo.png")) == 1


def test_consulta_vizinhanca():
    q = ConsultaSemantica(modelo_juh())
    viz = q.vizinhanca("personagem:Juh")
    assert viz["entidade"]["nome"] == "Juh"
    assert any(r["destino"] == "pose:Juh.neutra"
               for r in viz["de"])
    assert any(r["origem"] == "janela:p" for r in viz["para"])


def test_consulta_atualizar():
    m = ModeloSemantico("t")
    q = ConsultaSemantica(m)
    m.adicionar_entidade(EntidadeSemantica("x", "simbolo", "X"))
    q.atualizar()
    assert [e.id for e in q.encontrar_por_nome("X")] == ["x"]


# ---------- AST (25-32) ----------

def test_ast_basico():
    m = ModeloSemantico("t")
    out = analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n",
                         "src/a.elixx")
    assert out["entidades"] == 1 and out.get("erro") is None
    assert m.obter_entidade("janela:p").linha == 1


def test_ast_personagem_partes_poses():
    m = modelo_juh()
    assert "personagem:Juh" in m
    assert "parte:Juh.corpo" in m and "parte:Juh.cabeca" in m
    assert m.obter_entidade("pose:Juh.neutra").tipo == "pose"
    assert m.obter_entidade(
        "expressao:Juh.sorriso").tipo == "expressao"


def test_ast_componentes_eventos():
    m = ModeloSemantico("t")
    analisar_texto(m, "janela p {\n botao entrar {\n"
                      '  texto: "Ir"\n'
                      "  quando clicar {\n"
                      '   mostrar("oi")\n'
                      "  }\n"
                      " }\n}\n", "src/a.elixx")
    assert "componente:p.entrar" in m
    tipos = {e.tipo for e in m.entidades()}
    assert "evento" in tipos


def test_ast_funcoes_acoes_imports():
    m = ModeloSemantico("t")
    analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n"
                      "funcao soma(x) {\n retornar x\n}\n"
                      "acao iniciar {\n}\n"
                      "importar modulo.util\n", "src/a.elixx")
    assert "funcao:soma" in m and "acao:iniciar" in m
    assert "import:modulo.util" in m


def test_ast_animacao_alvo():
    m = ModeloSemantico("t")
    analisar_texto(m, FONTE_JUH + "janela q {\n"
                      " animacao acenar {\n"
                      "  alvo: corpo\n"
                      " }\n}\n", "src/a.elixx")
    assert "animacao:acenar" in m
    assert m.obter_entidade(
        "animacao:acenar").dados["alvo"] == "corpo"


def test_ast_erro_parse():
    m = ModeloSemantico("t")
    out = analisar_texto(m, "janela p { titulo: ", "src/ruim.elixx")
    assert out.get("erro") is True
    assert len(m.diagnosticos()) == 1
    assert len(m) == 0


def test_ast_sem_adivinhacao():
    m = ModeloSemantico("t")
    out = analisar_texto(m, "janela p {\n titulo: \"T\"\n}\n",
                         "src/a.elixx")
    assert out["ignorados"] == 0
    tipos = {e.tipo for e in m.entidades()}
    assert tipos == {"janela"}  # só o que o AST fornece


def test_ast_adapter_classes():
    m = ModeloSemantico("t")
    ad = AdaptadorAST(m, "src/a.elixx")
    with pytest.raises(ErroELiXX):
        AdaptadorAST("nao-modelo")
    with pytest.raises(ErroELiXX):
        ad.adaptar_programa("nao-programa")


# ---------- projeto (33-37) ----------

def test_projeto(tmp_path):
    from pathlib import Path

    base = tmp_path / "proj"
    (base / "src").mkdir(parents=True)
    (base / "src" / "main.elixx").write_text(
        "janela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    (base / "src" / "ruim.elixx").write_text("janela p {",
                                             encoding="utf-8")
    (base / "README.md").write_text("oi", encoding="utf-8")
    m = ModeloSemantico("p")
    total = analisar_projeto(m, base)
    assert total["arquivos"] == 2  # só .elixx
    assert total["erros"] == 1
    assert "janela:p" in m


def test_projeto_raiz_ausente(tmp_path):
    with pytest.raises(ErroELiXX):
        analisar_projeto(ModeloSemantico("t"),
                         tmp_path / "sem-pasta")


def test_projeto_arquivo_registro():
    m = modelo_juh()
    assert m.arquivos()[0]["caminho"] == "src/main.elixx"
    assert len(m.arquivos()[0]["hash"]) == 16


# ---------- atualização (38-40) ----------

def test_atualizar():
    m = modelo_juh()
    n_antes = len(m)
    out = atualizar_arquivo(m, "src/main.elixx",
                            "janela p {\n titulo: \"T\"\n}\n")
    assert out["entidades"] == 1
    assert "personagem:Juh" not in m
    assert len(m) == 1 < n_antes


def test_atualizar_seguranca():
    m = modelo_juh()
    with pytest.raises(ErroELiXX):
        atualizar_arquivo(m, "../fora.elixx", "x")
    with pytest.raises(ErroELiXX):
        atualizar_arquivo("nao-modelo", "src/a.elixx", "x")


# ---------- personagem/animação/assets (41-46) ----------

def test_personagem_relacoes():
    m = modelo_juh()
    q = ConsultaSemantica(m)
    possui = [r.destino for r in q.relacoes_de("personagem:Juh")
              if r.tipo == "possui"]
    assert "parte:Juh.corpo" in possui
    assert "pose:Juh.neutra" in possui
    assert "expressao:Juh.sorriso" in possui


def test_animacao_relacao():
    m = modelo_juh()
    assert "animacao" not in {e.tipo for e in m.entidades()}
    m2 = ModeloSemantico("t")
    analisar_texto(m2, "janela p {\n"
                       " personagem Juh {\n"
                       "  parte corpo {\n"
                       "  }\n"
                       " }\n"
                       " animacao acenar {\n"
                       "  alvo: corpo\n"
                       " }\n}\n", "src/a.elixx")
    rels = [(r.origem, r.tipo, r.destino)
            for r in m2.relacoes()]
    assert ("animacao:acenar", "atua_em",
            "parte:Juh.corpo") in rels


def test_assets():
    m = modelo_juh()
    ent = m.obter_entidade("asset:corpo.png")
    assert ent.dados["caminho"] == "corpo.png"
    q = ConsultaSemantica(m)
    assert q.relacoes_para("asset:corpo.png")[0].tipo == \
        "usa_asset"


def test_assets_sem_chute():
    m = ModeloSemantico("t")
    analisar_texto(m, "janela p {\n botao b {\n"
                      '  texto: "foto.png"\n'
                      " }\n}\n", "src/a.elixx")
    assert "asset:foto.png" not in m  # texto ≠ prop de asset


# ---------- Studio (47-49) ----------

def test_studio_resumo():
    m = modelo_juh()
    resumo = resumo_para_inspetor(m, "personagem:Juh")
    assert resumo["entidade"]["tipo"] == "personagem"
    assert resumo["entidade"]["arquivo"] == "src/main.elixx"
    assert len(resumo["de"]) >= 2


def test_studio_resumo_ausente():
    with pytest.raises(ErroELiXX):
        resumo_para_inspetor(modelo_juh(), "fantasma:x")


# ---------- Agent (50-52) ----------

def test_agent_contexto():
    from elixx.studio.agent import AgentContext

    ctx = AgentContext("P")
    modelo_para_contexto(ctx, modelo_juh())
    assert len(ctx.simbolos) == len(modelo_juh())
    assert all(s["tipo"].startswith("semantico:")
               for s in ctx.simbolos)


def test_agent_contexto_limite():
    from elixx.studio.agent import AgentContext

    m = ModeloSemantico("t")
    for i in range(100):
        m.adicionar_entidade(
            EntidadeSemantica(f"s:{i}", "simbolo", f"S{i}"))
    ctx = AgentContext("P")
    modelo_para_contexto(ctx, m, max_entidades=10)
    assert len(ctx.simbolos) == 10


def test_agent_sem_modelo():
    from elixx.studio.agent import AgentContext, MockAgentProvider

    ctx = AgentContext("P")  # Agent funciona sem F27
    assert MockAgentProvider().disponivel() is True
    assert ctx.simbolos == []


# ---------- mutação → changeset (53-54) ----------

def test_mutacao():
    from elixx.studio.agent import ChangeSet

    m = modelo_juh()
    mut = MutacaoSemantica("personagem:Juh", "nome", "Juh")
    assert mut.to_dict()["alvo"] == "personagem:Juh"
    cs = mutacao_para_changeset(mut, m)
    assert isinstance(cs, ChangeSet) and cs.estado == "proposto"
    with pytest.raises(ErroELiXX):
        mutacao_para_changeset(
            MutacaoSemantica("fantasma:x", "nome", "Y"), m)
    with pytest.raises(ErroELiXX):
        MutacaoSemantica("", "nome", "Y")
    with pytest.raises(ErroELiXX):
        mutacao_para_changeset("nao-mutacao", m)


# ---------- validação (55-57) ----------

def test_validacao():
    assert validar_modelo(modelo_juh())["valido"] is True
    m = ModeloSemantico("t")
    m.adicionar_entidade(EntidadeSemantica("a", "simbolo"))
    m._relacoes.append(RelacaoSemantica("a", "possui", "fantasma"))
    out = validar_modelo(m)
    assert out["valido"] is False and out["total"] == 1
    with pytest.raises(ErroELiXX):
        validar_modelo("nao-modelo")


# ---------- snapshot (58-59) ----------

def test_snapshot():
    m = modelo_juh()
    snap = SnapshotSemantico.de_modelo(m, versao=2)
    assert snap.versao == 2
    assert "personagem:Juh" in snap.entidades()
    m2 = ModeloSemantico.from_dict(m.to_dict())
    diff = comparar_snapshots(snap,
                              SnapshotSemantico.de_modelo(m2))
    assert diff == {"adicionados": [], "removidos": [],
                    "alterados": []}


def test_snapshot_diff():
    m = modelo_juh()
    antes = SnapshotSemantico.de_modelo(m)
    m.adicionar_entidade(EntidadeSemantica("novo:x", "simbolo"))
    m.remover_entidade("pose:Juh.neutra")
    depois = SnapshotSemantico.de_modelo(m)
    diff = comparar_snapshots(antes, depois)
    assert diff["adicionados"] == ["novo:x"]
    assert diff["removidos"] == ["pose:Juh.neutra"]
    with pytest.raises(ErroELiXX):
        comparar_snapshots(antes, "nao-snapshot")
    with pytest.raises(ErroELiXX):
        SnapshotSemantico("nao-dict")


# ---------- serialização (60) ----------

def test_serializacao_json():
    m = modelo_juh()
    texto = m.to_json()
    assert json.loads(texto)["nome"] == "t"
    assert "pickle" not in texto and "eval" not in texto


# ---------- segurança (61-68) ----------

def test_sec_traversal():
    m = ModeloSemantico("t")
    for ruim in ("../a.elixx", "/abs.elixx", "a/../../b.elixx"):
        with pytest.raises(ErroELiXX):
            m.registrar_arquivo(ruim)
        with pytest.raises(ErroELiXX):
            atualizar_arquivo(m, ruim, "x")


def test_sec_maliciosas():
    m = ModeloSemantico("t")
    m.adicionar_entidade(EntidadeSemantica(
        "__import__('os')", "simbolo", "<script>",
        dados={"x": "{{7*7}}"}))
    assert "__import__('os')" in m
    assert m.to_json()


def test_sec_json_invalido():
    with pytest.raises(ErroELiXX):
        ModeloSemantico.from_dict({"entidades": [{"id": "a"}]})
    with pytest.raises(ErroELiXX):
        EntidadeSemantica.from_dict({"id": "a", "tipo": "x",
                                     "dados": {"f": object()}})


def test_sec_duplicadas():
    m = modelo_juh()
    with pytest.raises(ErroELiXX):
        m.adicionar_entidade(
            EntidadeSemantica("personagem:Juh", "personagem"))


def test_sec_payload():
    m = ModeloSemantico("t")
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("a", "simbolo",
                          dados={"x": "y" * 100_001})
    m.adicionar_entidade(EntidadeSemantica("ok", "simbolo",
                                           dados={"x": "y"}))
    assert m.to_json()  # modelo segue válido


def test_sec_dados_exec():
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("a", "simbolo", dados={"f": object()})
    with pytest.raises(ErroELiXX):
        EntidadeSemantica("a", "simbolo", dados={"f": (1, 2)})


def test_sec_sem_execucao():
    import pathlib

    import elixx.studio.modelo as pacote

    base = pathlib.Path(pacote.__file__).parent
    for arq in base.glob("*.py"):
        fonte = arq.read_text(encoding="utf-8")
        assert "eval(" not in fonte, arq.name
        assert "exec(" not in fonte, arq.name
        assert "importlib" not in fonte, arq.name
        assert "__import__" not in fonte, arq.name
        assert "pickle" not in fonte, arq.name
        assert "subprocess" not in fonte, arq.name


# ---------- performance (69-71) ----------

def test_perf_entidades():
    import time as _t

    for total in (100, 1000, 5000):
        m = ModeloSemantico("p")
        t0 = _t.perf_counter()
        for i in range(total):
            m.adicionar_entidade(EntidadeSemantica(
                f"s:{i:05d}", "simbolo", f"S{i}",
                arquivo="src/a.elixx"))
        t_build = _t.perf_counter()
        idx = IndiceSemantico(m)
        t_idx = _t.perf_counter()
        assert len(idx.buscar_por_tipo("simbolo")) == total
        assert len(idx.buscar_por_arquivo("src/a.elixx")) == total
        t_busca = _t.perf_counter()
        m.to_json()
        t_ser = _t.perf_counter()
        assert (t_ser - t0) < 60.0
        if total == 5000:
            print(f"\n5000 ent: build={t_build - t0:.2f}s "
                  f"idx={t_idx - t_build:.2f}s "
                  f"busca={t_busca - t_idx:.2f}s "
                  f"json={t_ser - t_busca:.2f}s")


def test_perf_arquivos(tmp_path):
    import time as _t

    base = tmp_path / "proj"
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


def test_perf_consulta():
    import time as _t

    m = ModeloSemantico("p")
    for i in range(1000):
        m.adicionar_entidade(EntidadeSemantica(
            f"s:{i:04d}", "simbolo", f"S{i}"))
    for i in range(0, 1000, 2):
        m.adicionar_relacao(RelacaoSemantica(
            f"s:{i:04d}", "referencia",
            f"s:{(i + 1) % 1000:04d}"))
    q = ConsultaSemantica(m)
    t0 = _t.perf_counter()
    for i in range(0, 1000, 10):
        q.relacoes_de(f"s:{i:04d}")
        q.encontrar_por_nome(f"S{i}")
    assert (_t.perf_counter() - t0) < 30.0


# ---------- determinismo + regressão (72-73) ----------

def test_determinismo():
    a = modelo_juh().to_json()
    b = modelo_juh().to_json()
    assert a == b
    m = modelo_juh()
    assert [r.to_dict() for r in m.relacoes()] == \
        [r.to_dict() for r in ModeloSemantico.from_dict(
            m.to_dict()).relacoes()]


def test_regressao_f25_f26():
    from elixx.studio import StudioApp, Workspace
    from elixx.studio.agent import AgentContext, MockAgentProvider

    assert isinstance(StudioApp().workspace, Workspace)
    assert MockAgentProvider().disponivel() is True
    assert AgentContext("P").simbolos == []
    import elixx.studio.agent.contexto as antiguo
    import elixx.studio.workspace as wmod

    assert "modelo" not in open(antiguo.__file__,
                                encoding="utf-8").read()
    assert "modelo" not in open(wmod.__file__,
                                encoding="utf-8").read()
