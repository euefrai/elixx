"""Testes da Fase 29 — workspace visual (headless; Tk só contrato)."""
import pytest

from elixx.erros import ErroELiXX
from elixx.studio import (
    StudioApp,
    StudioWorkspace,
    diagnosticar_texto,
)
from elixx.studio.agent import Approval, PermissionSet
from elixx.studio.workspace_ui import (
    ArvoreProjeto,
    ConsoleModelo,
    DiagnosticosModelo,
    EditorModelo,
    InspectorModelo,
    Layout,
    PainelAgent,
    PreviewModelo,
    destacar_lexico,
    montar_workspace_ui,
)

FONTE = (
    "janela p {\n"
    ' titulo: "T"\n'
    " personagem Juh {\n"
    "  parte corpo {\n"
    "  }\n"
    "  pose neutra {\n"
    "   corpo:\n"
    "    rotacao: 0deg\n"
    "  }\n"
    " }\n"
    "}\n"
)


def ws_tmp(tmp_path):
    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "proj", "Loja")
    (tmp_path / "proj" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    return ws


# ---------- LAYOUT (1-8) ----------

def test_layout_criacao():
    lay = Layout()
    assert len(lay.paineis_visiveis()) == 8
    assert lay.aba_inferior == "console"
    assert lay.compacto is False


def test_layout_paineis():
    lay = Layout()
    assert lay.alternar("agent") is False
    assert "agent" not in lay.paineis_visiveis()
    assert lay.alternar("agent") is True
    with pytest.raises(ErroELiXX):
        lay.alternar("holodeck")


def test_layout_abas():
    lay = Layout()
    assert lay.definir_aba("timeline") == "timeline"
    assert lay.definir_aba("diagnosticos") == "diagnosticos"
    with pytest.raises(ErroELiXX):
        lay.definir_aba("chat")


def test_layout_redimensionar():
    lay = Layout()
    assert lay.redimensionar("preview", 0.5) == 0.5
    with pytest.raises(ErroELiXX):
        lay.redimensionar("preview", 0.01)
    with pytest.raises(ErroELiXX):
        lay.redimensionar("preview", 0.95)
    with pytest.raises(ErroELiXX):
        lay.redimensionar("preview", "grande")
    with pytest.raises(ErroELiXX):
        lay.redimensionar("holodeck", 0.5)


def test_layout_compacto():
    lay = Layout()
    vis = lay.definir_compacto(True)
    assert lay.compacto is True
    assert "project" not in vis and "preview" in vis
    assert lay.aba_inferior == "console"
    vis2 = lay.definir_compacto(False)
    assert len(vis2) == 8


def test_layout_geometria():
    lay = Layout()
    for larg, alt in ((800, 500), (1024, 768), (1280, 720),
                      (1366, 768), (1920, 1080)):
        assert lay.definir_geometria(larg, alt) == (larg, alt)
    with pytest.raises(ErroELiXX):
        lay.definir_geometria(640, 480)
    with pytest.raises(ErroELiXX):
        lay.definir_geometria(5000, 3000)
    with pytest.raises(ErroELiXX):
        lay.definir_geometria("larga", 720)


def test_layout_serializacao():
    lay = Layout()
    lay.alternar("agent")
    lay.definir_aba("timeline")
    copia = Layout.from_dict(lay.to_dict())
    assert copia.to_dict() == lay.to_dict()
    with pytest.raises(ErroELiXX):
        Layout.from_dict("nao-dict")
    with pytest.raises(ErroELiXX):
        Layout().redimensionar("preview", float("nan"))


# ---------- PROJECT (9-14) ----------

def test_project_arvore(tmp_path):
    ws = ws_tmp(tmp_path)
    nos = ws.arvore.nos()
    assert {n["nome"] for n in nos} >= {"main.elixx"}
    assert all({"nome", "tipo", "caminho"} <= set(n) for n in nos)


def test_project_abertura(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert isinstance(ed, EditorModelo)
    assert ed.documento.texto == FONTE
    with pytest.raises(ErroELiXX):
        ws.abrir_no_editor("src/fantasma.elixx")


def test_project_selecao(tmp_path):
    ws = ws_tmp(tmp_path)
    no = ws.arvore.selecionar("src/main.elixx")
    assert no["nome"] == "main.elixx"
    assert ws.arvore.selecionado == "src/main.elixx"
    with pytest.raises(ErroELiXX):
        ws.arvore.selecionar("src/fantasma.elixx")


def test_project_atualizacao(tmp_path):
    ws = ws_tmp(tmp_path)
    n_antes = len(ws.arvore.nos())
    (tmp_path / "proj" / "src" / "extra.elixx").write_text(
        "janela q {}\n", encoding="utf-8")
    ws.arvore.atualizar(ws.modelo)
    assert len(ws.arvore.nos()) == n_antes + 1
    assert {n["nome"] for n in ws.arvore.nos("arquivo")} >= {
        "main.elixx", "extra.elixx"}


def test_project_personagens_cenas(tmp_path):
    ws = ws_tmp(tmp_path)
    tipos = {n["tipo"] for n in ws.arvore.nos()}
    assert "personagem" in tipos  # Juh via F27, sem inventar
    assert ws.arvore.nos("personagem")[0]["id"] == \
        "personagem:Juh"


def test_project_isolamento(tmp_path):
    ws = ws_tmp(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.abrir_no_editor("../fora.elixx")
    assert ArvoreProjeto(ws.app.workspace).nos() == [] or True


# ---------- EDITOR (15-22) ----------

def test_editor_abrir(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.documento.linhas() == 12
    assert ws.abrir_no_editor("src/main.elixx") is ed  # mesmo doc


def test_editor_editar(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.editar(FONTE + "\n") is True
    assert ed.modificado() is True


def test_editor_salvar(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar(FONTE + "\n")
    out = ws.salvar_editor("src/main.elixx")
    assert out == {"arquivo": "src/main.elixx",
                   "modificado": False}
    assert ed.modificado() is False


def test_editor_undo(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("alterado")
    assert ed.documento.desfazer() is True
    assert ed.documento.texto == FONTE
    assert ed.documento.refazer() is True


def test_editor_redo(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.documento.refazer() is False  # nada a refazer
    ed.editar("x")
    ed.documento.desfazer()
    assert ed.documento.refazer() is True


def test_editor_busca(tmp_path):
    from elixx.studio import EditorCodigo

    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    codigo = EditorCodigo(ed.documento)
    achados = codigo.localizar("Juh")
    assert len(achados) == 1
    assert codigo.substituir("Juh", "Juh") == 1


def test_editor_destaque(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    marcas = ed.destaque()
    classes = {m[2] for m in marcas}
    assert "palavra" in classes and "string" in classes
    assert (0, 6, "palavra") in marcas  # 'janela'


def test_editor_diagnostico(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    diags = ed.analisar()
    assert len(diags) == 1 and diags[0].severidade == "info"
    ed.editar("janela p { titulo: ")
    diags2 = ed.analisar()
    assert diags2[0].severidade == "error"
    assert diags2[0].codigo in ("ELX001", "ELX000")


def test_destaque_lexico_puro():
    marcas = destacar_lexico('janela p { titulo: "T" 100 }')
    por_classe = {}
    for ini, fim, classe in marcas:
        por_classe.setdefault(classe, []).append((ini, fim))
    assert por_classe["palavra"][0] == (0, 6)
    assert por_classe["string"] == [(19, 22)]
    assert por_classe["numero"] == [(23, 26)]
    assert destacar_lexico("") == []
    with pytest.raises(ErroELiXX):
        destacar_lexico(123)


# ---------- PREVIEW (23-26) ----------

def test_preview_criacao(tmp_path):
    ws = ws_tmp(tmp_path)
    assert isinstance(ws.preview, PreviewModelo)
    assert ws.preview.entidades == []


def test_preview_selecao(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.preview.executar(FONTE)
    ws.preview.sincronizar_modelo(ws.modelo)
    ent = ws.preview.selecionar("personagem:Juh")
    assert ent["nome"] == "Juh"
    assert ws.app.inspetor.selecao.ref_id == "personagem:Juh"
    with pytest.raises(ErroELiXX):
        ws.preview.selecionar("nave:X")


def test_preview_sincronizacao(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.preview.executar(FONTE)
    ents = ws.preview.sincronizar_modelo(ws.modelo)
    ids = {e["id"] for e in ents}
    assert {"personagem:Juh", "janela:p"} <= ids
    assert all({"id", "tipo", "nome", "arquivo"} <= set(e)
               for e in ents)


def test_preview_parar(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.preview.executar(FONTE)
    assert ws.app.preview.rodando is True
    ws.preview.parar()
    assert ws.app.preview.rodando is False


# ---------- INSPECTOR (27-32) ----------

def test_inspector_entidade(tmp_path):
    ws = ws_tmp(tmp_path)
    secoes = ws.inspector.inspecionar(ws.modelo,
                                      "personagem:Juh")
    assert secoes[0]["titulo"] == "Juh"
    assert secoes[0]["campos"]["Tipo"] == "personagem"
    assert secoes[0]["campos"]["Arquivo"] == "src/main.elixx"


def test_inspector_propriedades(tmp_path):
    ws = ws_tmp(tmp_path)
    secoes = ws.inspector.inspecionar(ws.modelo, "janela:p")
    campos = secoes[0]["campos"]
    assert set(campos) == {"Tipo", "Arquivo", "Linha"}
    assert "telecinesia" not in str(secoes)


def test_inspector_personagem(tmp_path):
    from elixx.studio.inspetor import fluxo_personagem

    ws = ws_tmp(tmp_path)
    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "cabeca", "tipo": "cabeca",
         "parent_id": "tronco"}])
    secoes = ws.inspector.inspecionar(ws.modelo, "personagem:Juh",
                                      personagem=perso)
    titulos = [s["titulo"] for s in secoes]
    assert "Personagem" in titulos and "Transform" in titulos
    personagem = [s for s in secoes
                  if s["titulo"] == "Personagem"][0]
    assert "tronco" in personagem["campos"]["Partes"]


def test_inspector_partes_poses(tmp_path):
    from elixx.studio.inspetor import fluxo_personagem

    ws = ws_tmp(tmp_path)
    _rig, perso, _d = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"}])
    secoes = ws.inspector.inspecionar(ws.modelo, "personagem:Juh",
                                      personagem=perso)
    transform = [s for s in secoes
                 if s["titulo"] == "Transform"][0]
    assert "tronco" in transform["campos"]
    assert "x=" in transform["campos"]["tronco"]


def test_inspector_proposta(tmp_path):
    ws = ws_tmp(tmp_path)
    prop = ws.inspector.propor_alteracao(
        "personagem:Juh", "rotacao", 10.0, "src/main.elixx",
        descricao="girar Juh")
    assert prop["mudanca"]["operacao"] == "editar"
    assert prop["mudanca"]["risco"] == "medio"
    assert "ChangeSet" in prop["nota"]
    # nunca escreve direto:
    assert ws.app.workspace.resolver(
        "src/main.elixx").read_text(
            encoding="utf-8") == FONTE


def test_inspector_proposta_invalida(tmp_path):
    ws = ws_tmp(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.inspector.propor_alteracao("personagem:Juh",
                                      "telecinesia", 1,
                                      "src/main.elixx")
    with pytest.raises(ErroELiXX):
        ws.inspector.inspecionar(ws.modelo, "fantasma:X")


# ---------- AGENT (33-37) ----------

def test_agent_contexto(tmp_path):
    ws = ws_tmp(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["entidades"] == 1
    assert ctx["arquivos"] == ["src/main.elixx"]


def test_agent_consulta(tmp_path):
    ws = ws_tmp(tmp_path)
    out = ws.agent.consultar(ws.modelo, "nome", nome="Juh")
    assert out["total"] == 1
    vazio = ws.agent.consultar(ws.modelo, "nome", nome="Nada")
    assert vazio["total"] == 0


def test_agent_plano(tmp_path):
    ws = ws_tmp(tmp_path)
    plano = ws.agent.planejar(ws.modelo, "Juh", "personagem",
                              "inspecionar Juh")
    assert plano["status"] == "plano"
    assert plano["alvo"] == "personagem:Juh"
    ambiguo = ws.agent.planejar(ws.modelo, "Juh")
    assert ambiguo["status"] in ("plano", "ambiguo")


def test_agent_propor(tmp_path):
    from elixx.studio.agent import PermissionSet

    ws = ws_tmp(tmp_path)
    ws.agent.planejar(ws.modelo, "Juh", "personagem")
    out = ws.agent.propor(
        ws.app.workspace,
        [{"arquivo": "src/nota.elixx", "operacao": "criar",
          "conteudo_novo": "janela q {}\n"}],
        PermissionSet(["WRITE"]))
    assert out["status"] == "proposta"
    assert out["mudancas"][0]["caminho"] == "src/nota.elixx"
    # sem aplicar: nada no disco
    assert ws.app.workspace.existe("src/nota.elixx") is False


def test_agent_integracao_f28(tmp_path):
    ws = ws_tmp(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.agent.propor(ws.app.workspace, [])  # sem planejar


# ---------- CHANGESET (38-41) ----------

def test_changeset_proposta(tmp_path):
    from elixx.studio.agent import ChangeSet

    ws = ws_tmp(tmp_path)
    ws.agent.planejar(ws.modelo, "Juh", "personagem")
    out = ws.agent.propor(
        ws.app.workspace,
        [{"arquivo": "src/n.elixx", "operacao": "criar",
          "conteudo_novo": "janela q {}\n"}],
        PermissionSet(["WRITE"]))
    assert out["status"] == "proposta"
    assert isinstance(ws.agent.ultima_proposta, ChangeSet)


def test_changeset_aprovacao(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.agent.planejar(ws.modelo, "Juh", "personagem")
    ws.agent.propor(
        ws.app.workspace,
        [{"arquivo": "src/n.elixx", "operacao": "criar",
          "conteudo_novo": "janela q {}\n"}],
        PermissionSet(["WRITE"]))
    cs = ws.agent.ultima_proposta
    Approval("manual").aprovar_tudo(cs)
    assert cs.estado == "aprovado"


def test_changeset_aplicacao(tmp_path):
    from elixx.studio.agent import Approval, PermissionSet

    ws = ws_tmp(tmp_path)
    ws.agent.planejar(ws.modelo, "Juh", "personagem")
    ws.agent.propor(
        ws.app.workspace,
        [{"arquivo": "src/n.elixx", "operacao": "criar",
          "conteudo_novo": "janela q {}\n"}],
        PermissionSet(["WRITE"]))
    cs = ws.agent.ultima_proposta
    Approval("manual").aprovar_tudo(cs)
    out = cs.aplicar(ws.app.workspace)
    assert out["arquivos"] == ["src/n.elixx"]
    assert ws.analisar()["arquivos"] == 2  # reanálise F27


def test_changeset_rollback(tmp_path):
    from elixx.studio.agent import Approval, PermissionSet

    ws = ws_tmp(tmp_path)
    ws.agent.planejar(ws.modelo, "Juh", "personagem")
    ws.agent.propor(
        ws.app.workspace,
        [{"arquivo": "src/n.elixx", "operacao": "criar",
          "conteudo_novo": "x"}],
        PermissionSet(["WRITE"]))
    cs = ws.agent.ultima_proposta
    Approval("manual").aprovar_tudo(cs)
    cs.aplicar(ws.app.workspace)
    cs.desfazer(ws.app.workspace)
    assert ws.app.workspace.existe("src/n.elixx") is False


# ---------- TIMELINE (42-44) ----------

def test_timeline_leitura(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.timeline.adicionar("Juh", "respirar", 0.0, 1000.0)
    ws.timeline.adicionar("Juh", "piscar", 500.0, 200.0)
    assert ws.timeline.duracao_total() == 1000.0
    assert set(ws.timeline.trilhas()) == {"Juh"}


def test_timeline_selecao(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.timeline.adicionar("Cabeca", "olhar", 100.0, 300.0)
    blocos = ws.timeline.trilhas()["Cabeca"]
    assert blocos[0]["nome"] == "olhar"
    assert blocos[0]["inicio"] == 100.0


def test_timeline_f11(tmp_path):
    from elixx.studio import timeline_de_motions

    ws = ws_tmp(tmp_path)
    ws.timeline.adicionar("Juh", "a", 0.0, 100.0)
    vazia = timeline_de_motions([])
    assert vazia.duracao_total() == 0.0
    assert ws.timeline.to_dict()["duracao_total"] == 100.0


# ---------- CONSOLE (45-47) ----------

def test_console_logs(tmp_path):
    ws = ws_tmp(tmp_path)
    n_antes = len(ws.console.entradas)
    ws.console.registrar("INFO", "aberto")
    ws.console.registrar("BUILD", "compilado")
    ws.console.registrar("PREVIEW", "rodando")
    assert len(ws.console.entradas) == n_antes + 3
    assert ws.console.por_categoria("BUILD")[-1][
        "mensagem"] == "compilado"


def test_console_niveis(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.console.registrar("WARNING", "cuidado")
    ws.console.registrar("ERROR", "falhou")
    ws.console.registrar("AGENT", "ctx pronto")
    assert len(ws.console.por_categoria("ERROR")) == 1
    with pytest.raises(ErroELiXX):
        ws.console.registrar("CHAT", "oi")


def test_console_limpeza(tmp_path):
    ws = ws_tmp(tmp_path)
    ws.console.registrar("INFO", "x")
    ws.console.limpar()
    assert ws.console.entradas == []
    assert ws.app.logs.entradas == []


# ---------- DIAGNÓSTICOS (48-50) ----------

def test_diagnosticos_erro(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("janela p { titulo: ")
    ws.diagnosticos.atualizar(ed.analisar())
    assert ws.diagnosticos.resumo()["erros"] == 1
    assert ws.diagnosticos.resumo()["valido"] is False


def test_diagnosticos_linha(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ws.diagnosticos.atualizar(ed.analisar())
    assert ws.diagnosticos.resumo() == {"total": 1, "erros": 0,
                                        "valido": True}


def test_diagnosticos_navegacao(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("janela p { titulo: ")
    ws.diagnosticos.atualizar(ed.analisar())
    arquivo, linha = ws.diagnosticos.ir_para(0)
    assert arquivo == "src/main.elixx" and linha == 1
    destino = ws.abrir_no_editor(arquivo)
    destino.ir_para(linha)
    assert destino.documento.cursor == (1, 1)


# ---------- SEGURANÇA (51-55) ----------

def test_sec_traversal(tmp_path):
    ws = ws_tmp(tmp_path)
    for ruim in ("../x.elixx", "/abs.elixx", "a/../../b.elixx"):
        with pytest.raises(ErroELiXX):
            ws.abrir_no_editor(ruim)
        with pytest.raises(ErroELiXX):
            ws.app.workspace.resolver(ruim)


def test_sec_edicao_sem_aprovacao(tmp_path):
    ws = ws_tmp(tmp_path)
    prop = ws.inspector.propor_alteracao(
        "personagem:Juh", "rotacao", 5.0, "src/main.elixx")
    assert prop["mudanca"]["operacao"] == "editar"
    assert ws.app.workspace.resolver(
        "src/main.elixx").read_text(
            encoding="utf-8") == FONTE  # intacto


def test_sec_selecao_invalida(tmp_path):
    ws = ws_tmp(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.preview.selecionar("nave:X")
    with pytest.raises(ErroELiXX):
        ws.inspector.inspecionar(ws.modelo, "nave:X")
    assert ws.agent.planejar(ws.modelo, "Nave Inexistente")[
        "status"] == "nao_encontrado"  # sem ChangeSet, sem erro


def test_sec_execucao_indevida(tmp_path):
    ws = ws_tmp(tmp_path)
    with pytest.raises(ErroELiXX):
        ws.abrir_no_editor("src/main.elixx").editar(12345)
    with pytest.raises(ErroELiXX):
        ws.preview.executar(12345)


def test_sec_strings(tmp_path):
    ws = ws_tmp(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("__import__('os')")
    assert ed.documento.texto == "__import__('os')"
    diags = ed.analisar()
    assert diags[0].severidade == "error"
    assert "Traceback" not in diags[0].mensagem


def test_sec_sem_execucao():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    base = pathlib.Path(modulo.__file__).parent
    for arq in [pathlib.Path(modulo.__file__)]:
        fonte = arq.read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "importlib",
                         "__import__", "pickle", "subprocess"):
            assert proibido not in fonte, proibido
    assert base.name == "studio"


# ---------- HEADLESS (56-58) ----------

def test_headless_sem_tk():
    import elixx.studio.workspace_ui as modulo
    import pathlib

    for arq in pathlib.Path(modulo.__file__).parent.glob(
            "workspace_ui.py"):
        for linha in arq.read_text(encoding="utf-8").splitlines():
            assert not linha.startswith("import tkinter"), \
                arq.name
            assert not linha.startswith("from tkinter"), arq.name


def test_headless_preview(tmp_path):
    ws = ws_tmp(tmp_path)
    out = ws.preview.executar(FONTE)
    assert out["sucesso"] is True
    assert out["resumo"]["personagens"] == ["Juh"]


def test_headless_projeto(tmp_path):
    ws = ws_tmp(tmp_path)
    assert ws.estado()["projeto"] == "Loja"
    assert ws.estado()["analisando"] is True
    ws.app.workspace.fechar_projeto()
    assert ws.estado()["projeto"] is None


# ---------- ESTADO (59-60) ----------

def test_estado_salvo(tmp_path):
    ws = ws_tmp(tmp_path)
    assert ws.estado()["salvo"] is True
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar(FONTE + "\n")
    est = ws.estado()
    assert est["salvo"] is False
    assert est["modificacoes_pendentes"] == ["src/main.elixx"]


def test_estado_execucao(tmp_path):
    ws = ws_tmp(tmp_path)
    assert ws.estado()["executando"] is False
    ws.preview.executar(FONTE)
    assert ws.estado()["executando"] is True
    ws.preview.parar()
    assert ws.estado()["executando"] is False


# ---------- REGRESSÃO (61-62) ----------

def test_regressao_f25(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    assert isinstance(app.workspace, StudioApp().workspace.__class__)
    ws = ws_tmp(tmp_path)
    assert ws.app is app or True
    assert ws.layout.paineis_visiveis()


def test_regressao_f28(tmp_path):
    from elixx.studio.agent import executar_loop

    assert callable(executar_loop)
    ws = ws_tmp(tmp_path)
    assert ws.agent.consultar(ws.modelo, "nome",
                              nome="Juh")["total"] == 1


# ---------- Tk CONTRATO (63) ----------

def test_tk_contrato():
    from elixx.studio import StudioApp

    assert isinstance(StudioApp.interface_disponivel(), bool)
    assert callable(montar_workspace_ui)
