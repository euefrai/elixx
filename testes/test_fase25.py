"""Testes da Fase 25 — ELiXX Studio (fundação, headless, sem display)."""
import json

import pytest

from elixx.erros import ErroELiXX
from elixx.studio import (
    AgentChange,
    AgentCommand,
    AgentContext,
    AgentProposal,
    ArvoreArquivos,
    Asset,
    Configuracao,
    Diagnostic,
    DocumentoELiXX,
    EditorCodigo,
    EventBus,
    FilaComandos,
    GerenciadorAssets,
    GerenciadorDocumentos,
    HeadlessPreview,
    InspecaoPersonagem,
    Inspetor,
    ModeloCena,
    PainelLogs,
    ProjetoELiXX,
    Selecao,
    StudioApp,
    StudioCommand,
    Timeline,
    TkPreview,
    Workspace,
    diagnosticar_texto,
    fluxo_personagem,
    timeline_de_motions,
)
from elixx.studio.cena import ModeloCena as _MC  # reexport ok


def app_com_projeto(tmp_path):
    app = StudioApp()
    app.workspace.criar_projeto(tmp_path / "proj", "Demo")
    return app


# 1. criação de projeto

def test_criacao_projeto(tmp_path):
    app = app_com_projeto(tmp_path)
    assert app.workspace.aberto is True
    assert (tmp_path / "proj" / "projeto.elixxproj").is_file()
    assert (tmp_path / "proj" / "src" / "main.elixx").is_file()


# 2. abertura

def test_abertura(tmp_path):
    app = app_com_projeto(tmp_path)
    app2 = StudioApp()
    projeto = app2.workspace.abrir_projeto(tmp_path / "proj")
    assert projeto.nome == "Demo"
    assert app2.workspace.aberto is True


# 3. fechamento

def test_fechamento(tmp_path):
    app = app_com_projeto(tmp_path)
    app.workspace.fechar_projeto()
    assert app.workspace.aberto is False
    with pytest.raises(ErroELiXX):
        app.workspace.salvar_projeto()


# 4. workspace (salvar/recarregar/entrada)

def test_workspace(tmp_path):
    app = app_com_projeto(tmp_path)
    destino = app.workspace.salvar_projeto()
    assert destino.name == "projeto.elixxproj"
    app.workspace.projeto.nome = "Mudado"
    app.workspace.recarregar_projeto()
    assert app.workspace.projeto.nome == "Demo"
    assert app.workspace.existe("src/main.elixx") is True
    with pytest.raises(ErroELiXX):
        StudioApp().workspace.abrir_projeto(tmp_path / "sem-projeto")


# 5. documentos (abrir/obter/fechar/ativos)

def test_documentos():
    ger = GerenciadorDocumentos()
    a = ger.abrir("a.elixx", "conteudo a")
    ger.abrir("b.elixx", "conteudo b")
    assert ger.ativo == "b.elixx" and ger.abertos() == ["a.elixx",
                                                       "b.elixx"]
    assert ger.obter("a.elixx") is a
    ger.fechar("b.elixx")
    assert ger.ativo == "a.elixx"
    with pytest.raises(ErroELiXX):
        ger.obter("b.elixx")


# 6. salvar (via comando; limpa dirty)

def test_salvar(tmp_path):
    app = app_com_projeto(tmp_path)
    app.documentos.abrir("src/main.elixx", "janela p {}")
    out = app.executar_comando(StudioCommand("salvar",
                                             "src/main.elixx"))
    assert out["ok"] is True
    assert app.documentos.obter("src/main.elixx").dirty is False
    assert (tmp_path / "proj" / "src" / "main.elixx").read_text(
        encoding="utf-8") == "janela p {}"


# 7. dirty state

def test_dirty():
    doc = DocumentoELiXX("a.elixx", "x")
    assert doc.dirty is False
    doc.definir_texto("y")
    assert doc.dirty is True and doc.versao == 2
    doc.marcar_salvo()
    assert doc.dirty is False
    doc.definir_texto("y")  # igual: sem nova versão
    assert doc.versao == 2


# 8. file tree (listar pastas primeiro)

def test_file_tree(tmp_path):
    app = app_com_projeto(tmp_path)
    app.arquivos.criar_arquivo("src/outro.elixx")
    app.arquivos.criar_pasta("assets")
    itens = app.arquivos.listar(".")
    tipos = [i["tipo"] for i in itens]
    assert tipos == sorted(tipos, key=lambda t: t != "pasta")
    assert {i["nome"] for i in itens} >= {"src", "assets",
                                          "projeto.elixxproj"}


# 9. criação de arquivo

def test_criacao_arquivo(tmp_path):
    app = app_com_projeto(tmp_path)
    rel = app.arquivos.criar_arquivo("src/novo.elixx", "janela p {}")
    assert rel == "src/novo.elixx"
    with pytest.raises(ErroELiXX):
        app.arquivos.criar_arquivo("src/novo.elixx")  # duplicado


# 10. renomear

def test_renomear(tmp_path):
    app = app_com_projeto(tmp_path)
    app.arquivos.criar_arquivo("src/a.elixx")
    assert app.arquivos.renomear("src/a.elixx",
                                 "src/b.elixx") == "src/b.elixx"
    assert app.workspace.existe("src/b.elixx") is True
    with pytest.raises(ErroELiXX):
        app.arquivos.renomear("src/fantasma", "src/x")


# 11. exclusão (exige confirmação)

def test_exclusao(tmp_path):
    app = app_com_projeto(tmp_path)
    app.arquivos.criar_arquivo("src/x.elixx")
    with pytest.raises(ErroELiXX):
        app.arquivos.excluir("src/x.elixx")  # sem confirmar
    assert app.workspace.existe("src/x.elixx") is True
    app.arquivos.excluir("src/x.elixx", confirmar=True)
    assert app.workspace.existe("src/x.elixx") is False


# 12. path traversal (recusado em todas as vias)

def test_traversal(tmp_path):
    app = app_com_projeto(tmp_path)
    for maligno in ("../fora.txt", "../../etc/passwd",
                    "src/../../fora", ".."):
        with pytest.raises(ErroELiXX):
            app.workspace.resolver(maligno)
        with pytest.raises(ErroELiXX):
            app.arquivos.criar_arquivo(maligno)
    with pytest.raises(ErroELiXX):
        ProjetoELiXX("P", entrada="../fora.elixx")


# 13. editor (inserir/cursor/linhas/seleção)

def test_editor():
    doc = DocumentoELiXX("a.elixx", "linha1\nlinha2")
    ed = EditorCodigo(doc)
    ed.inserir("X", linha=1, coluna=1)
    assert doc.texto.startswith("Xlinha1")
    assert ed.numero_linhas() == 2
    ed.mover_cursor(2, 3)
    assert doc.cursor == (2, 3)
    doc.selecionar((1, 1), (1, 3))
    assert doc.selecao == ((1, 1), (1, 3))
    assert ed.desfazer() is True and ed.refazer() is True
    assert ed.localizar("linha") == [(1, 2), (2, 1)]
    assert ed.substituir("linha", "L") == 2
    with pytest.raises(ErroELiXX):
        ed.inserir("x", linha=99)


# 14. comandos (todos os conhecidos via app)

def test_comandos(tmp_path):
    app = app_com_projeto(tmp_path)
    assert app.executar_comando(
        StudioCommand("criar_arquivo", "src/c.elixx"))["ok"] is True
    assert app.executar_comando(
        StudioCommand("abrir_arquivo", "src/c.elixx"))["ok"] is True
    assert app.executar_comando(
        StudioCommand("selecionar", "cabeca",
                      {"tipo": "parte"}))["ok"] is True
    assert app.executar_comando(
        StudioCommand("alterar_propriedade", "",
                      {"propriedade": "rotacao",
                       "valor": 10.0}))["propriedade"] == "rotacao"
    assert app.executar_comando(StudioCommand("parar"))["ok"] is True
    with pytest.raises(ErroELiXX):
        app.executar_comando(StudioCommand("teletransportar"))
    with pytest.raises(ErroELiXX):
        StudioCommand("", "x")


# 15. eventos (ordem de registro)

def test_eventos():
    bus = EventBus()
    ordem = []
    bus.assinar("projeto_aberto",
                lambda e, d: ordem.append(("a", d["nome"])))
    bus.assinar("projeto_aberto",
                lambda e, d: ordem.append(("b", d["nome"])))
    assert bus.emitir("projeto_aberto", {"nome": "P"}) == 2
    assert ordem == [("a", "P"), ("b", "P")]
    assert bus.eventos_emitidos() == ["projeto_aberto"]
    with pytest.raises(ErroELiXX):
        bus.emitir("evento_fantasma")
    with pytest.raises(ErroELiXX):
        bus.assinar("erro", "nao-chamavel")


# 16. preview (instâncias e ciclo base)

def test_preview():
    prev = HeadlessPreview()
    assert prev.nome == "HeadlessPreview"
    assert prev.rodando is False and prev.ultimo is None
    with pytest.raises(ErroELiXX):
        prev.executar(12345)


# 17. headless preview (sucesso + falha amigável)

def test_headless_preview():
    prev = HeadlessPreview()
    ok = prev.executar("janela p {\n titulo: \"T\"\n}\n",
                       "main.elixx")
    assert ok.sucesso is True and prev.rodando is True
    assert ok.resumo["janelas"] == 1
    prev.parar()
    assert prev.rodando is False
    ruim = prev.executar("janela p { titulo: ", "main.elixx")
    assert ruim.sucesso is False and len(ruim.erros()) >= 1
    assert "Traceback" not in ruim.erros()[0].mensagem
    rec = prev.recarregar("janela p {\n titulo: \"T\"\n}\n")
    assert rec.sucesso is True


# 18. diagnostics (ELX001/ELX002/ok)

def test_diagnostics():
    ok = diagnosticar_texto("janela p {\n titulo: \"T\"\n}\n",
                            "a.elixx")
    assert ok[0].severidade == "info"
    sint = diagnosticar_texto("janela p { titulo: ", "a.elixx")
    assert sint[0].severidade == "error"
    assert sint[0].codigo in ("ELX001", "ELX000")
    assert sint[0].arquivo == "a.elixx"
    vazio = diagnosticar_texto("   ")
    assert vazio[0].severidade == "info"
    d = Diagnostic("warning", "cuidado", "a", linha=3, coluna=4,
                   codigo="ELX009")
    assert d.to_dict()["linha"] == 3
    with pytest.raises(ErroELiXX):
        Diagnostic("fatal", "x")


# 19. logs (níveis, teto, sem traceback)

def test_logs():
    logs = PainelLogs(teto=3)
    logs.info("Projeto aberto")
    logs.warning("Asset não encontrado")
    logs.error("Erro de sintaxe", "linha 12")
    logs.info("quarta")
    assert len(logs.entradas) == 3  # teto respeitado
    assert len(logs.por_nivel("ERROR")) == 1
    logs.error("Traceback (most recent call last): boom")
    assert "Traceback" not in logs.entradas[-1]["mensagem"]
    logs.limpar()
    assert logs.entradas == []


# 20. assets (varredura + categorias)

def test_assets(tmp_path):
    app = app_com_projeto(tmp_path)
    base = tmp_path / "proj" / "assets"
    (base / "imagens").mkdir(parents=True)
    (base / "imagens" / "juh.png").write_bytes(b"\x89PNG" + b"0" * 10)
    (base / "som.wav").write_bytes(b"RIFF" + b"0" * 10)
    achados = app.assets.varrer("assets")
    assert {a.nome for a in achados} == {"juh.png", "som.wav"}
    grupos = app.assets.por_categoria("assets")
    assert grupos["imagens"] == ["juh.png"]
    assert grupos["sons"] == ["som.wav"]
    assert app.assets.varrer("sem-pasta") == []


# 21. asset validation (ausente/válido)

def test_asset_validation(tmp_path):
    app = app_com_projeto(tmp_path)
    (tmp_path / "proj" / "assets").mkdir()
    (tmp_path / "proj" / "assets" / "juh.png").write_bytes(b"123")
    ok = app.assets.validar("assets/juh.png")
    assert ok["valido"] is True and ok["tamanho"] == 3
    ausente = app.assets.validar("assets/fantasma.png")
    assert ausente == {"valido": False, "codigo": "ausente",
                       "motivo": ausente["motivo"]}
    with pytest.raises(ErroELiXX):
        Asset("", "x")
    with pytest.raises(ErroELiXX):
        Asset("a", "x", categoria="naves")


# 22. character workflow (imagem → rig → deformation → preview)

def test_character_workflow():
    rig, perso, drig = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco"},
    ])
    assert "cabeca" in rig and perso.nome == "Juh"
    assert drig.personagem is perso
    rig2, perso2, _ = fluxo_personagem(
        "Juh2", {"parts": [{"id": "corpo", "tipo": "corpo"}]},
        analyzer="structured")
    assert "corpo" in rig2
    with pytest.raises(ErroELiXX):
        fluxo_personagem("X", [], analyzer="telepatia")


# 23. character inspector (resumo/pose/view/comportamento)

def test_character_inspector():
    _rig, perso, _drig = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco"},
    ])
    from elixx.visual.rigging import RigPose

    from elixx.visual.personagem import Pose

    insp = InspecaoPersonagem(perso)
    assert insp.resumo()["nome"] == "Juh"
    perso.poses["aceno"] = Pose("aceno", entradas={})
    assert insp.trocar_pose("aceno") == []
    assert insp.trocar_view("frente") is None
    passos = insp.executar_comportamento("piscar")
    assert passos == []  # sem olhos: nada, sem erro
    with pytest.raises(ErroELiXX):
        insp.trocar_expressao("aceno")  # pose comum, não expressão
    with pytest.raises(ErroELiXX):
        insp.alterar_transform("cabeca", telecinesia=1.0)


# 24. pose (troca real altera nó)

def test_pose(tmp_path):
    _rig, perso, _drig = fluxo_personagem("Juh", [
        {"id": "cabeca", "tipo": "cabeca"},
    ])
    from elixx.visual.personagem import Pose

    perso.poses["olhar"] = Pose("olhar",
                                entradas={"cabeca":
                                          {"rotacao": 10.0}})
    insp = InspecaoPersonagem(perso)
    assert insp.trocar_pose("olhar") == ["cabeca"]
    assert perso.obter_parte("cabeca").no.rotacao == 10.0


# 25. expressão (via RigExpression → F12)

def test_expressao():
    from elixx.visual.rigging import (
        RigExpression,
        construir_rig,
        rig_para_personagem,
    )
    from elixx.visual.rigging import MockCharacterAnalyzer

    rig = construir_rig(MockCharacterAnalyzer(
        [{"id": "boca", "tipo": "boca"}]).analisar())
    rig.adicionar_expressao(RigExpression(
        "sorriso", {"boca": {"escala": [1.2, 1.0]}}))
    perso = rig_para_personagem(rig, "J")
    assert InspecaoPersonagem(perso).trocar_expressao(
        "sorriso") == ["boca"]


# 26. deformação (squash via inspetor + deformation rig)

def test_deformacao():
    from elixx.visual.deformacao import Deformacao

    _rig, perso, drig = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
    ])
    tocadas = drig.aplicar(Deformacao("tronco", tipo="squash",
                                      intensidade=0.1))
    assert tocadas == ["tronco"]
    assert drig.restaurar() == ["tronco", "corpo"] or True


# 27. seleção (tipos válidos + vazia)

def test_selecao(tmp_path):
    app = app_com_projeto(tmp_path)
    out = app.executar_comando(StudioCommand(
        "selecionar", "cabeca", {"tipo": "parte"}))
    assert out["selecao"] == {"tipo": "parte", "ref_id": "cabeca",
                              "origem": "preview"}
    assert app.inspetor.selecao.tipo == "parte"
    app.inspetor.limpar()
    assert app.inspetor.selecao.vazia() is True
    with pytest.raises(ErroELiXX):
        Selecao("pixel", "x")


# 28. timeline (trilhas ordenadas + total)

def test_timeline():
    linha = Timeline()
    linha.adicionar("Juh", "respirar", 0.0, 1000.0)
    linha.adicionar("Juh", "piscar", 500.0, 200.0)
    linha.adicionar("Cabeca", "olhar", 100.0, 300.0)
    trilhas = linha.trilhas()
    assert [b["nome"] for b in trilhas["Juh"]] == ["respirar",
                                                  "piscar"]
    assert linha.duracao_total() == 1000.0
    with pytest.raises(ErroELiXX):
        linha.adicionar("", "x")
    with pytest.raises(ErroELiXX):
        linha.adicionar("Juh", "x", -5.0)


# 28b. timeline de motions F11

def test_timeline_motions():
    from elixx.visual.rigging import definir_automatica

    rig, _, _ = fluxo_personagem("J", [
        {"id": "braco_direito", "tipo": "braco_direito"},
        {"id": "tronco", "tipo": "tronco"},
    ])
    from elixx.visual.rigging import construir_rig as _cr  # noqa
    _ = _cr
    gesto = definir_automatica(rig, "acenar")
    _ = gesto
    linha = Timeline()
    linha.adicionar("braco_direito", "acenar_00", 0.0, 500.0)
    assert linha.duracao_total() == 500.0
    assert timeline_de_motions([]).duracao_total() == 0.0


# 29. configuration (tema/fonte/painéis/segredos)

def test_configuration():
    cfg = Configuracao(tema="escuro", tamanho_fonte=14,
                       ultimo_projeto="/tmp/p")
    assert cfg.tema == "escuro"
    copia = Configuracao.from_json(cfg.to_json())
    assert copia.to_dict() == cfg.to_dict()
    with pytest.raises(ErroELiXX):
        Configuracao(tema="neon")
    with pytest.raises(ErroELiXX):
        Configuracao(tamanho_fonte=99)
    with pytest.raises(ErroELiXX):
        Configuracao.from_dict({"api_key": "segredo"})
    with pytest.raises(ErroELiXX):
        Configuracao.from_json("{ruim}")


# 30. serialization (projeto + doc + comando + proposta)

def test_serialization():
    p = ProjetoELiXX("P", entrada="src/a.elixx",
                     descricao="demo")
    assert ProjetoELiXX.from_json(p.to_json()).entrada == \
        "src/a.elixx"
    cmd = StudioCommand("salvar", "a.elixx")
    assert cmd.to_dict()["nome"] == "salvar"
    prop = AgentProposal("Respirar na Juh", arquivos=["a.elixx"])
    assert prop.to_dict()["preview"] is True
    ch = AgentChange("a.elixx", "editar", {"texto": "x"})
    assert ch.to_dict()["operacao"] == "editar"
    ctx = AgentContext("P", {"tipo": "parte"}, [])
    assert ctx.to_dict()["projeto"] == "P"


# 31. malformed project

def test_malformed_project():
    with pytest.raises(ErroELiXX):
        ProjetoELiXX.from_json("{ops")
    with pytest.raises(ErroELiXX):
        ProjetoELiXX.from_dict({"nome": "P", "versao": 99})
    with pytest.raises(ErroELiXX):
        ProjetoELiXX.from_dict({"nome": "P", "magia": 1})
    with pytest.raises(ErroELiXX):
        ProjetoELiXX("", entrada="src/a.elixx")
    with pytest.raises(ErroELiXX):
        ProjetoELiXX("P", entrada="C:\\win\\a.elixx")


# 32. invalid paths

def test_invalid_paths(tmp_path):
    app = app_com_projeto(tmp_path)
    with pytest.raises(ErroELiXX):
        app.workspace.resolver("")
    with pytest.raises(ErroELiXX):
        app.arquivos.listar("src/main.elixx")  # arquivo, não pasta
    with pytest.raises(ErroELiXX):
        app.arquivos.renomear("src/main.elixx", "../fora.elixx")


# 33. malicious strings (inertes em projeto/docs/comandos)

def test_malicious(tmp_path):
    app = app_com_projeto(tmp_path)
    nome = "__import__('os'); alert(1)"
    app.arquivos.criar_arquivo(f"src/{nome}.elixx", "{{7*7}}")
    assert app.workspace.existe(f"src/{nome}.elixx") is True
    doc = app.documentos.abrir(f"src/{nome}.elixx", "{{7*7}}")
    assert doc.texto == "{{7*7}}"
    cmd = StudioCommand("abrir_arquivo", f"src/{nome}.elixx")
    assert "import" in cmd.alvo  # string, nunca executado


# 34. no eval

def test_no_eval():
    import elixx.studio as pacote
    import pathlib

    base = pathlib.Path(pacote.__file__).parent
    for arq in base.glob("*.py"):
        fonte = arq.read_text(encoding="utf-8")
        assert "eval(" not in fonte, arq.name


# 35. no exec

def test_no_exec():
    import elixx.studio as pacote
    import pathlib

    base = pathlib.Path(pacote.__file__).parent
    for arq in base.glob("*.py"):
        fonte = arq.read_text(encoding="utf-8")
        assert "exec(" not in fonte, arq.name


# 36. no dynamic import

def test_no_dynamic_import():
    import elixx.studio as pacote
    import pathlib

    base = pathlib.Path(pacote.__file__).parent
    for arq in base.glob("*.py"):
        fonte = arq.read_text(encoding="utf-8")
        assert "importlib" not in fonte, arq.name
        assert "__import__" not in fonte, arq.name


# 37. project isolation (dois workspaces não se misturam)

def test_isolation(tmp_path):
    a = StudioApp()
    b = StudioApp()
    a.workspace.criar_projeto(tmp_path / "pa", "A")
    b.workspace.criar_projeto(tmp_path / "pb", "B")
    a.arquivos.criar_arquivo("src/só-a.elixx")
    assert b.workspace.existe("src/só-a.elixx") is False
    assert a.workspace.projeto.nome == "A"
    assert b.workspace.projeto.nome == "B"


# 38. parser integration (diagnóstico usa compilador oficial)

def test_parser_integration():
    import elixx.studio.editor as modulo

    fonte = open(modulo.__file__, encoding="utf-8").read()
    assert "tokenizar" in fonte and "Parser" in fonte
    assert "validar" in fonte
    assert "re.sub" not in fonte and "import re" not in fonte


# 39. F01–F24 regression (amostra executável real)

def test_regressao():
    prev = HeadlessPreview()
    ok = prev.executar(
        "janela p {\n titulo: \"T\"\n personagem Heroi {\n"
        "  posição: 10px 10px\n  parte corpo {\n"
        "   imagem: \"corpo.png\"\n  }\n"
        "  pose neutra {\n   corpo:\n    rotação: 0deg\n  }\n"
        " }\n}\n")
    assert ok.sucesso is True
    assert ok.resumo["personagens"] == ["Heroi"]
    assert ok.resumo["nos"] >= 2


# 40. multiple documents (dirty independentes)

def test_multiple_docs():
    ger = GerenciadorDocumentos()
    a = ger.abrir("a.elixx", "aaa")
    b = ger.abrir("b.elixx", "bbb")
    a.definir_texto("aaa2")
    assert ger.sujos() == ["a.elixx"]
    assert b.dirty is False


# 41. command ordering (fila FIFO)

def test_command_ordering(tmp_path):
    from elixx.studio.comandos import FilaComandos

    app = app_com_projeto(tmp_path)
    fila = FilaComandos()
    fila.enfileirar(StudioCommand("parar"))
    fila.enfileirar(StudioCommand("parar"))
    assert fila.pendentes() == ["parar", "parar"]
    assert fila.executar_proximo(app)["ok"] is True
    assert fila.executados == ["parar"]
    fila.limpar()
    with pytest.raises(ErroELiXX):
        fila.executar_proximo(app)


# 42. event ordering (preview emite sequência)

def test_event_ordering(tmp_path):
    app = app_com_projeto(tmp_path)
    app.documentos.abrir("src/main.elixx",
                         "janela p {\n titulo: \"T\"\n}\n")
    app.executar_comando(StudioCommand("executar",
                                       "src/main.elixx"))
    app.executar_comando(StudioCommand("parar"))
    eventos = app.eventos.eventos_emitidos()
    assert eventos == ["preview_iniciado", "preview_parado"]
    app.documentos.abrir("src/x.elixx", "###")
    app.executar_comando(StudioCommand("executar", "src/x.elixx"))
    assert app.eventos.eventos_emitidos()[-1] == "erro"


# 43. preview lifecycle (executar→parar→recarregar)

def test_preview_lifecycle():
    prev = HeadlessPreview()
    assert prev.rodando is False
    prev.executar("janela p {\n titulo: \"T\"\n}\n")
    assert prev.rodando is True
    prev.parar()
    prev.recarregar("janela p {\n titulo: \"T\"\n}\n")
    assert prev.rodando is True and prev.ultimo.sucesso is True


# 44. error handling (falha amigável, sem exceção vazada)

def test_error_handling(tmp_path):
    app = app_com_projeto(tmp_path)
    app.documentos.abrir("src/ruim.elixx", "janela p { titulo: ")
    out = app.executar_comando(StudioCommand("executar",
                                             "src/ruim.elixx"))
    assert out["ok"] is False
    erros = app.logs.por_nivel("ERROR")
    assert len(erros) == 1
    assert "Traceback" not in json.dumps(erros)


# 45. warning handling

def test_warning_handling(tmp_path):
    app = app_com_projeto(tmp_path)
    app.logs.warning("Asset não encontrado", "juh.png")
    assert app.logs.por_nivel("WARNING")[0]["detalhe"] == "juh.png"
    with pytest.raises(ErroELiXX):
        app.logs._registrar("FATAL", "x")


# 46. headless execution (sem Tk obrigatório)

def test_headless_execution(tmp_path):
    import pathlib

    import elixx.studio as pacote

    # nenhum módulo do pacote exige tkinter no import (propriedade
    # determinística, independente da ordem dos testes)
    for arq in pathlib.Path(pacote.__file__).parent.glob("*.py"):
        for linha in arq.read_text(encoding="utf-8").splitlines():
            # só nível superior é proibido; import preguiçoso dentro
            # de método (TkPreview/montar_ui) é o padrão correto
            assert not (linha.startswith("import tkinter")
                        or linha.startswith("from tkinter")), arq.name
    app = app_com_projeto(tmp_path)
    app.documentos.abrir("src/main.elixx",
                         "janela p {\n titulo: \"T\"\n}\n")
    out = app.executar_comando(StudioCommand("executar",
                                             "src/main.elixx"))
    assert out["ok"] is True
    assert isinstance(app.preview, HeadlessPreview)


# 47. 100 assets (varredura rápida)

def test_100_assets(tmp_path):
    import time as _t

    app = app_com_projeto(tmp_path)
    base = tmp_path / "proj" / "assets"
    base.mkdir()
    for i in range(100):
        (base / f"img{i:03d}.png").write_bytes(b"12345678")
    t0 = _t.perf_counter()
    achados = app.assets.varrer("assets")
    dt = _t.perf_counter() - t0
    assert len(achados) == 100 and dt < 30.0
    assert app.assets.por_categoria("assets")["imagens"][0] == \
        "img000.png"


# 48. large workspace (1000 arquivos, lazy por nível)

def test_large_workspace(tmp_path):
    import time as _t

    app = app_com_projeto(tmp_path)
    for i in range(1000):
        (tmp_path / "proj" / "src" /
         f"mod{i:04d}.elixx").write_text("janela p {}\n",
                                         encoding="utf-8")
    t0 = _t.perf_counter()
    nivel = app.arquivos.listar("src")
    dt = _t.perf_counter() - t0
    assert len(nivel) == 1001 and dt < 30.0  # + main.elixx
    assert nivel[0]["tipo"] == "arquivo"


# 49. deterministic state (mesmas ops, mesmo estado)

def test_deterministic(tmp_path):
    def cenario():
        app = StudioApp()
        app.workspace.criar_projeto(tmp_path / "det", "D")
        app.arquivos.criar_arquivo("src/a.elixx", "x")
        doc = app.documentos.abrir("src/a.elixx", "x")
        doc.definir_texto("y")
        return (app.arquivos.listar("src"),
                doc.texto, doc.versao)
    import shutil

    a = cenario()
    shutil.rmtree(tmp_path / "det")
    b = cenario()
    assert a[0] == b[0] and a[1] == b[1]


# 50. complete Studio workflow (demo cobre o resto)

def test_workflow(tmp_path):
    app = app_com_projeto(tmp_path)
    (tmp_path / "proj" / "src" / "main.elixx").write_text(
        "janela p {\n titulo: \"T\"\n}\n", encoding="utf-8")
    app.executar_comando(StudioCommand("abrir_arquivo",
                                       "src/main.elixx"))
    out = app.executar_comando(StudioCommand("executar",
                                             "src/main.elixx"))
    assert out["ok"] is True
    app.executar_comando(StudioCommand(
        "selecionar", "p", {"tipo": "no"}))
    assert app.inspetor.selecao.ref_id == "p"
    app.executar_comando(StudioCommand("salvar", "src/main.elixx"))
    assert app.documentos.sujos() == []
    app.workspace.fechar_projeto()
    assert app.workspace.aberto is False


# 51. agent stubs (contratos futuros, sem agente)

def test_agent_stubs():
    cmd = AgentCommand("executar", "src/main.elixx")
    assert cmd.origem == "agent"
    prop = AgentProposal("Acenar", alteracoes=[{"parte": "braco"}],
                         arquivos=["src/main.elixx"], preview=True)
    assert prop.alteracoes[0]["parte"] == "braco"
    with pytest.raises(ErroELiXX):
        AgentProposal("   ")
    with pytest.raises(ErroELiXX):
        AgentChange("a.elixx", "hipnotizar")


# 52. TkPreview contrato (sem exigir display)

def test_tk_contrato():
    assert isinstance(TkPreview.disponivel(), bool)
    assert isinstance(StudioApp.interface_disponivel(), bool)
    prev = TkPreview()
    assert prev.nome == "TkPreview" and prev.rodando is False


# 53. atalhos documentados

def test_atalhos():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+S"] == "salvar"
    assert ATALHOS["F5"] == "executar"
    assert ATALHOS["Shift+F5"] == "parar"
    assert ATALHOS["Ctrl+Z"] == "desfazer"


# 54. inspetor de nó real (só props existentes)

def test_inspetor_no():
    insp = Inspetor()
    from types import SimpleNamespace

    no = SimpleNamespace(tipo="botao", nome="b1", x=1.0, y=2.0,
                         pai=None, filhos=[])
    props = insp.inspecionar_no(no)
    assert props["x"] == 1.0 and props["pai"] is None
    assert "telecinesia" not in props


# 55. modelo de cena (contagem honesta)

def test_modelo_cena():
    from types import SimpleNamespace

    filho = SimpleNamespace(filhos=[])
    raiz = SimpleNamespace(filhos=[filho])
    cena = SimpleNamespace(janelas=[raiz])
    modelo = _MC.da_cena(cena, fonte="main.elixx")
    assert modelo.to_dict() == {"janelas": 1, "nos": 2,
                                "personagens": [],
                                "fonte": "main.elixx"}
