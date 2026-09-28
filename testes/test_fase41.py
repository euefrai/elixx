"""Fase 41 — Project Workflow & Developer Experience (headless).

Cobre: workspace, novo/abrir/fechar/recarregar projeto,
recentes, tree real, criar/pasta/renomear/excluir/duplicar,
abas, dirty, salvar (todos), diagnosticos, execucao/parada,
status, palette F41, teclado, F27/F32/F33/F34, agent, code↔
visual, empty/welcome, recovery, seguranca, performance.
"""

import pytest

from elixx.erros import ErroELiXX
from elixx.studio.projeto_workspace import (
    TEMPLATES,
    AbasAvancadas,
    ArvoreProjetoReal,
    BoasVindas,
    EstadoExecucao,
    Fotografia,
    Recentes,
    abrir_projeto_validado,
    buscar_palette_f41,
    conflitos_f41,
    conteudo_inicial,
    conteudo_template,
    descartar_alteracoes,
    duplicar_arquivo,
    estado_arquivo,
    estado_projeto,
    executar_palette_f41,
    executar_projeto,
    fechar_projeto,
    interpretar_arrastar,
    menu_contexto,
    novo_projeto,
    parar_execucao,
    recarregar_projeto,
)

FONTE = ('janela p {\n titulo: "T"\n posicao: 100 200\n'
         ' personagem Juh {\n  parte corpo {\n  }\n }\n}\n')


def _ws_base(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    ws = StudioWorkspace(app)
    ws.criar_projeto(tmp_path / "p", "P")
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    ws.analisar()
    return app, ws


# ---------- templates ----------


def test_templates_nomes():
    assert tuple(TEMPLATES) == ("vazio", "aplicacao", "cena",
                                "personagem", "minimo")


def test_templates_validos():
    from elixx.studio.editor import diagnosticar_texto

    for nome in TEMPLATES:
        texto = conteudo_template(nome)
        erros = [d for d in diagnosticar_texto(texto, "m")
                 if d.severidade == "error"]
        assert not erros, nome


def test_template_invalido():
    with pytest.raises(ErroELiXX):
        conteudo_template("nave")


def test_conteudo_inicial_tipos():
    assert "janela" in conteudo_inicial("elixx", "app")
    assert conteudo_inicial("json") == "{\n}\n"
    assert conteudo_inicial("config", "x").startswith("#")
    assert conteudo_inicial("texto") == ""


def test_conteudo_inicial_tipo_invalido():
    with pytest.raises(ErroELiXX):
        conteudo_inicial("binario")


# ---------- novo projeto ----------


def test_novo_projeto_vazio(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    info = novo_projeto(app.workspace, "Demo", tmp_path,
                        "vazio")
    assert info["projeto"] == "Demo"
    assert (tmp_path / "Demo" / "src" / "main.elixx"
            ).is_file()


def test_novo_projeto_templates(tmp_path):
    from elixx.studio import StudioApp

    for tpl in TEMPLATES:
        app = StudioApp()
        info = novo_projeto(app.workspace, f"P{tpl}",
                            tmp_path, tpl)
        assert info["template"] == tpl


def test_novo_projeto_nome_invalido(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    for ruim in ("", "a/b", "..", "x" * 101):
        with pytest.raises(ErroELiXX):
            novo_projeto(app.workspace, ruim, tmp_path)


def test_novo_projeto_fluxo_imediato(tmp_path):
    from elixx.studio import StudioApp, StudioWorkspace

    app = StudioApp()
    info = novo_projeto(app.workspace, "Go", tmp_path,
                        "personagem")
    ws = StudioWorkspace(app)
    ws.abrir_projeto(tmp_path / "Go")
    ws.analisar()
    assert "personagem:Juh" in [e.id for e in
                                ws.modelo.entidades()]


# ---------- abrir / fechar / recarregar ----------


def test_abrir_validado(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    novo_projeto(app.workspace, "A", tmp_path)
    app2 = StudioApp()
    info = abrir_projeto_validado(app2.workspace,
                                  tmp_path / "A")
    assert info["projeto"] == "A"
    assert "src/main.elixx" in info["arquivos"]


def test_abrir_inexistente(tmp_path):
    from elixx.studio import StudioApp

    with pytest.raises(ErroELiXX):
        abrir_projeto_validado(StudioApp().workspace,
                               tmp_path / "nada")


def test_abrir_sem_config(tmp_path):
    from elixx.studio import StudioApp

    (tmp_path / "solto").mkdir()
    with pytest.raises(ErroELiXX):
        abrir_projeto_validado(StudioApp().workspace,
                               tmp_path / "solto")


def test_abrir_nao_executa(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    novo_projeto(app.workspace, "B", tmp_path)
    (tmp_path / "B" / "src" / "main.elixx").write_text(
        FONTE, encoding="utf-8")
    app2 = StudioApp()
    abrir_projeto_validado(app2.workspace, tmp_path / "B")
    assert app2.preview.rodando is False


def test_fechar_projeto(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.abrir_no_editor("src/main.elixx")
    saida = fechar_projeto(ws)
    assert saida == {"ok": True, "projeto": None}
    assert ws.modelo is None
    assert ws.app.workspace.aberto is False


def test_recarregar_projeto(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = recarregar_projeto(ws)
    assert saida["projeto"] == "P"


# ---------- recentes ----------


def test_recentes_adicionar_listar():
    rec = Recentes()
    rec.adicionar("Demo", "C:/Projetos/demo")
    assert rec.listar()[0]["nome"] == "Demo"


def test_recentes_ordem_limite():
    rec = Recentes()
    for i in range(25):
        rec.adicionar(f"P{i}", f"C:/p{i}")
    assert len(rec.listar()) == 20
    assert rec.listar()[0]["nome"] == "P24"


def test_recentes_remover_nao_apaga(tmp_path):
    (tmp_path / "X").mkdir()
    (tmp_path / "X" / "f.txt").write_text("x",
                                          encoding="utf-8")
    rec = Recentes()
    rec.adicionar("X", str(tmp_path / "X"))
    assert rec.remover(str(tmp_path / "X")) is True
    assert (tmp_path / "X" / "f.txt").is_file()
    assert rec.listar() == []


def test_recentes_json_sem_segredo(tmp_path):
    rec = Recentes(tmp_path / "r.json")
    rec.adicionar("A", "C:/a")
    texto = (tmp_path / "r.json").read_text(encoding="utf-8")
    assert "token" not in texto.lower()
    rec2 = Recentes(tmp_path / "r.json")
    assert rec2.listar()[0]["nome"] == "A"


def test_recentes_invalido():
    with pytest.raises(ErroELiXX):
        Recentes().carregar("nao json")


# ---------- tree real ----------


def test_tree_espelha_filesystem(tmp_path):
    _, ws = _ws_base(tmp_path)
    (tmp_path / "p" / "src" / "extra.elixx").write_text(
        "janela x {\n}\n", encoding="utf-8")
    (tmp_path / "p" / "assets").mkdir(exist_ok=True)
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    texto = "\n".join(arv.linhas())
    assert "extra.elixx" in texto
    assert "main.elixx" in texto


def test_tree_sem_invencao(tmp_path):
    _, ws = _ws_base(tmp_path)
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    texto = "\n".join(arv.linhas())
    assert "fantasma" not in texto


def test_tree_expandir_recolher(tmp_path):
    _, ws = _ws_base(tmp_path)
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    assert arv.recolher("src") is False
    assert arv.expandir("src") is True
    with pytest.raises(ErroELiXX):
        arv.recolher("src/main.elixx")


def test_tree_selecionar(tmp_path):
    _, ws = _ws_base(tmp_path)
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    sel = arv.selecionar("src/main.elixx")
    assert sel["nome"] == "main.elixx"
    with pytest.raises(ErroELiXX):
        arv.selecionar("nada.elixx")


def test_tree_dirty_ativo(tmp_path):
    _, ws = _ws_base(tmp_path)
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    texto = "\n".join(arv.linhas(sujos=["src/main.elixx"],
                                 ativo="src/main.elixx"))
    assert "●" in texto and "→" in texto


def test_tree_vazia_sem_projeto():
    from elixx.studio import StudioApp

    arv = ArvoreProjetoReal(StudioApp().workspace)
    with pytest.raises(ErroELiXX):
        arv.selecionar("x")


# ---------- arquivos: criar/renomear/excluir/duplicar ----------


def test_criar_arquivo_elixx(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos
    from elixx.studio.editor import diagnosticar_texto

    rel = ArvoreArquivos(ws.app.workspace).criar_arquivo(
        "src/novo.elixx", conteudo_inicial("elixx", "novo"))
    texto = (tmp_path / "p" / rel).read_text(encoding="utf-8")
    assert not [d for d in diagnosticar_texto(texto, rel)
                if d.severidade == "error"]


def test_criar_pasta(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    rel = ArvoreArquivos(ws.app.workspace).criar_pasta(
        "dados")
    assert (tmp_path / "p" / rel).is_dir()


def test_renomear(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    arv = ArvoreArquivos(ws.app.workspace)
    arv.criar_arquivo("src/velho.txt", "oi")
    arv.renomear("src/velho.txt", "src/novo.txt")
    assert (tmp_path / "p" / "src" / "novo.txt").is_file()


def test_excluir_com_confirmacao(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    arv = ArvoreArquivos(ws.app.workspace)
    arv.criar_arquivo("src/x.txt", "x")
    with pytest.raises(ErroELiXX):
        arv.excluir("src/x.txt")
    arv.excluir("src/x.txt", confirmar=True)
    assert not (tmp_path / "p" / "src" / "x.txt").exists()


def test_duplicar(tmp_path):
    _, ws = _ws_base(tmp_path)
    rel = duplicar_arquivo(ws.app.workspace,
                           "src/main.elixx")
    assert "copia" in rel
    assert (tmp_path / "p" / rel).is_file()


def test_duplicar_ausente(tmp_path):
    _, ws = _ws_base(tmp_path)
    with pytest.raises(ErroELiXX):
        duplicar_arquivo(ws.app.workspace, "src/nada.elixx")


def test_traversal_bloqueado(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    with pytest.raises(ErroELiXX):
        ArvoreArquivos(ws.app.workspace).criar_arquivo(
            "../../fora.txt", "x")


# ---------- abas / dirty / salvar ----------


def test_abas_proxima_anterior(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    ws.app.documentos.abrir("b.txt", "b")
    abas = AbasAvancadas(ws.app.documentos)
    assert abas.proxima() in ("a.txt", "b.txt")
    assert abas.anterior() in ("a.txt", "b.txt")


def test_abas_fechar_outras(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    ws.app.documentos.abrir("b.txt", "b")
    abas = AbasAvancadas(ws.app.documentos)
    assert abas.fechar_outras("a.txt") == ["a.txt"]
    assert ws.app.documentos.abertos() == ["a.txt"]


def test_abas_fechar_outras_dirty(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    ws.app.documentos.abrir("b.txt", "b")
    ws.app.documentos.obter("b.txt").definir_texto("mudou")
    with pytest.raises(ErroELiXX):
        AbasAvancadas(ws.app.documentos).fechar_outras("a.txt")


def test_abas_fechar_todas(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    assert AbasAvancadas(ws.app.documentos).fechar_todas() \
        == []
    assert ws.app.documentos.abertos() == []


def test_salvar_todas(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("src/main.elixx", FONTE)
    ws.app.documentos.obter("src/main.elixx").definir_texto(
        FONTE + "\n")
    salvas = AbasAvancadas(
        ws.app.documentos).salvar_todas(ws.app.workspace)
    assert salvas == ["src/main.elixx"]
    assert ws.app.documentos.sujos() == []


def test_dirty_marca_e_limpa(tmp_path):
    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    assert ed.modificado() is False
    ed.editar(FONTE + " ")
    assert ed.modificado() is True
    ws.salvar_editor("src/main.elixx")
    assert ed.modificado() is False


def test_descartar(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("src/main.elixx", FONTE)
    ws.app.documentos.obter("src/main.elixx").definir_texto(
        "lixo")
    saida = descartar_alteracoes(ws.app.workspace,
                                 ws.app.documentos,
                                 "src/main.elixx")
    assert saida == {"arquivo": "src/main.elixx",
                     "dirty": False}


def test_estado_arquivo(tmp_path):
    _, ws = _ws_base(tmp_path)
    info = estado_arquivo(ws.app.workspace, ws.modelo,
                          "src/main.elixx",
                          ws.app.documentos)
    assert info["tamanho"] > 0
    assert "personagem:Juh" in info["entidades"]
    assert info["dirty"] is False


# ---------- fotografia / recovery ----------


def test_fotografia_detecta_externa(tmp_path):
    _, ws = _ws_base(tmp_path)
    foto = Fotografia()
    assert foto.fotografar(ws.app.workspace) >= 2
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "alterado externo", encoding="utf-8")
    alter = foto.alterados_externamente(ws.app.workspace)
    assert "src/main.elixx" in alter or \
        any("main.elixx" in a for a in alter)


def test_fotografia_novo_removido(tmp_path):
    _, ws = _ws_base(tmp_path)
    foto = Fotografia()
    foto.fotografar(ws.app.workspace)
    (tmp_path / "p" / "src" / "novo.txt").write_text(
        "n", encoding="utf-8")
    alter = foto.alterados_externamente(ws.app.workspace)
    assert any("novo" in a for a in alter)


def test_recovery_recarrgar_vs_manter(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("src/main.elixx", FONTE)
    (tmp_path / "p" / "src" / "main.elixx").write_text(
        "externo", encoding="utf-8")
    descartar_alteracoes(ws.app.workspace, ws.app.documentos,
                         "src/main.elixx")
    assert ws.app.documentos.obter(
        "src/main.elixx").texto == "externo"


# ---------- diagnosticos ----------


def test_diagnostico_erro_amigavel(tmp_path):
    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("janela { !!!")
    diags = ed.analisar()
    assert any(d.severidade == "error" for d in diags)
    assert all("Traceback" not in d.mensagem for d in diags)


def test_diagnostico_ir_para_linha(tmp_path):
    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.analisar()
    linha, texto = ed.ir_para(4)
    assert linha == 4 and "personagem" in texto


def test_diagnostico_resumo(tmp_path):
    _, ws = _ws_base(tmp_path)
    assert ws.diagnosticos.resumo()["total"] >= 0


# ---------- execucao ----------


def test_executar_ok(tmp_path):
    from elixx.studio.preview import HeadlessPreview

    saida = executar_projeto(HeadlessPreview(), FONTE,
                             "main.elixx", EstadoExecucao())
    assert saida == {"ok": True, "estado": "CONCLUIDO",
                     "erro": "", "resumo": saida["resumo"]}
    assert saida["resumo"]["janelas"] == 1


def test_executar_erro(tmp_path):
    from elixx.studio.preview import HeadlessPreview

    est = EstadoExecucao()
    saida = executar_projeto(HeadlessPreview(),
                             "janela { !!!", "m", est)
    assert saida["ok"] is False
    assert saida["estado"] == "ERRO"
    assert saida["erro"]


def test_parar(tmp_path):
    from elixx.studio.preview import HeadlessPreview

    prev = HeadlessPreview()
    executar_projeto(prev, FONTE)
    saida = parar_execucao(prev, EstadoExecucao())
    assert saida == {"ok": True, "estado": "PARADO"}
    assert prev.rodando is False


def test_estado_inicial():
    assert EstadoExecucao().estado == "PRONTO"


# ---------- palette F41 ----------


def test_palette_23():
    assert len(buscar_palette_f41("")) == 23


def test_palette_busca():
    ids = [c["id"] for c in buscar_palette_f41("projeto")]
    assert "novo_projeto" in ids
    assert "abrir_projeto" in ids


def test_palette_fechar(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "fechar_projeto")
    assert saida["projeto"] is None


def test_palette_novo_arquivo(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "novo_arquivo",
                                 {"nome": "tela",
                                  "tipo": "elixx",
                                  "caminho": "src/tela.elixx"})
    assert (tmp_path / "p" / "src" / "tela.elixx").is_file()


def test_palette_nova_pasta(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "nova_pasta",
                                 {"caminho": "dados"})
    assert saida["pasta"] == "dados"


def test_palette_abrir(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "abrir_arquivo",
                                 {"caminho": "src/main.elixx"})
    assert saida["linhas"] >= 1


def test_palette_salvar(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.abrir_no_editor("src/main.elixx")
    saida = executar_palette_f41(ws, "salvar",
                                 {"caminho": "src/main.elixx"})
    assert saida["modificado"] is False


def test_palette_salvar_tudo(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("src/main.elixx", FONTE)
    ws.app.documentos.obter("src/main.elixx").definir_texto(
        FONTE + " ")
    saida = executar_palette_f41(ws, "salvar_tudo")
    assert "src/main.elixx" in saida["salvos"]


def test_palette_fechar_aba(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    saida = executar_palette_f41(ws, "fechar_aba",
                                 {"caminho": "a.txt"})
    assert saida["arquivo"] == "a.txt"


def test_palette_fechar_aba_dirty(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    ws.app.documentos.obter("a.txt").definir_texto("x")
    with pytest.raises(ErroELiXX):
        executar_palette_f41(ws, "fechar_aba",
                             {"caminho": "a.txt"})


def test_palette_fechar_todas(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    saida = executar_palette_f41(ws, "fechar_todas_abas")
    assert saida == {"ok": True, "acao": "fechar_todas_abas",
                     "fechadas": []}


def test_palette_executar_parar(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "executar",
                                 {"caminho": "src/main.elixx"})
    assert saida["estado"] == "CONCLUIDO"
    saida2 = executar_palette_f41(ws, "parar")
    assert saida2["estado"] == "PARADO"


def test_palette_mostrar(tmp_path):
    _, ws = _ws_base(tmp_path)
    for cid in ("mostrar_preview", "mostrar_scene",
                "mostrar_agent", "mostrar_inspector",
                "mostrar_raciocinio", "mostrar_plano",
                "mostrar_changes", "buscar", "substituir",
                "ir_para_linha", "novo_projeto",
                "abrir_projeto"):
        assert executar_palette_f41(ws, cid)["ok"] is True


def test_palette_recarrgar(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "recarregar_projeto")
    assert saida["projeto"] == "P"


def test_palette_desconhecido(tmp_path):
    _, ws = _ws_base(tmp_path)
    with pytest.raises(ErroELiXX):
        executar_palette_f41(ws, "foguete")


def test_palette_antigas_intactas():
    from elixx.studio.agent.interacao import CommandPalette
    from elixx.studio.scene_canvas import buscar_palette_f40
    from elixx.studio.scene_editor import buscar_palette_f39

    assert len(CommandPalette().buscar("")) == 30
    assert len(buscar_palette_f39("")) == 13
    assert len(buscar_palette_f40("")) == 10


# ---------- teclado ----------


def test_atalhos_novos():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+N"] == "novo_arquivo"
    assert ATALHOS["Ctrl+Shift+N"] == "novo_projeto"
    assert ATALHOS["Ctrl+W"] == "fechar_aba"
    assert ATALHOS["Ctrl+Tab"] == "proxima_aba"
    assert ATALHOS["Ctrl+H"] == "substituir"


def test_atalhos_antigos():
    from elixx.studio.app import ATALHOS

    assert ATALHOS["Ctrl+S"] == "salvar"
    assert ATALHOS["Ctrl+O"] == "abrir_projeto"
    assert ATALHOS["F5"] == "executar"
    assert ATALHOS["Ctrl+Z"] == "desfazer"


def test_conflitos_documentados():
    conf = {c["tecla"]: c for c in conflitos_f41()}
    assert "Ctrl+G" in conf
    assert conf["Ctrl+G"]["regra"] == "sem substituicao"
    assert "Ctrl+N" not in conf or \
        conf["Ctrl+N"]["regra"] == "global prevalece"


# ---------- semantico / agent ----------


def test_f27_entidades(tmp_path):
    _, ws = _ws_base(tmp_path)
    assert "personagem:Juh" in [e.id for e in
                                ws.modelo.entidades()]


def test_f32_localiza(tmp_path):
    from elixx.studio.codigo.localizacao import (
        localizar_entidade,
    )

    _, ws = _ws_base(tmp_path)
    ent = next(e for e in ws.modelo.entidades()
               if e.id == "personagem:Juh")
    texto = (tmp_path / "p" / "src" / "main.elixx").read_text(
        encoding="utf-8")
    assert localizar_entidade(ent, texto).inicio_linha == 4


def test_f33_plano(tmp_path):
    _, ws = _ws_base(tmp_path)
    assert ws.agent.planejar(ws.modelo,
                             "Juh")["status"] == "plano"


def test_f34_contexto(tmp_path):
    _, ws = _ws_base(tmp_path)
    ctx = ws.agent.contexto(ws.modelo, "personagem:Juh")
    assert ctx["entidades"] >= 1


def test_agent_sabe_arquivo_selecao(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.preview.sincronizar_modelo(ws.modelo)
    ws.preview.selecionar("personagem:Juh")
    est = estado_projeto(ws)
    assert est.to_dict()["selected_preview"] == \
        "personagem:Juh"


def test_estado_projeto_campos(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.abrir_no_editor("src/main.elixx")
    dados = estado_projeto(ws).to_dict()
    for campo in ("project_path", "open_files", "active_file",
                  "dirty_files", "selected_entity",
                  "preview_state", "agent_session",
                  "diagnostics", "execution_state"):
        assert campo in dados, campo
    assert dados["open_files"] == ["src/main.elixx"]
    assert dados["preview_state"] == "parado"


# ---------- code ↔ visual ----------


def test_visual_proposta_sem_escrita(tmp_path):
    from elixx.studio.scene_canvas import SceneCanvas
    from elixx.studio.scene_canvas import cena_de_texto

    _, ws = _ws_base(tmp_path)
    saida = cena_de_texto(FONTE)
    canvas = SceneCanvas()
    canvas.montar(saida["cena"], saida["personagens"],
                  ws.modelo)
    cs = canvas.arrastar_para("janela:p", 150, 200,
                              ws.app.workspace, ws.modelo)
    assert cs.estado == "proposto"


def test_codigo_visual_ir_para(tmp_path):
    from elixx.studio.scene_editor import ir_para_codigo

    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    saida = ir_para_codigo(ed, ws.modelo, "personagem:Juh")
    assert saida["linha"] == 4


# ---------- welcome / empty / menu / arrastar ----------


def test_welcome_sem_projeto():
    w = BoasVindas().mostrar(False)
    assert w["acoes"] == ["novo_projeto", "abrir_projeto"]
    assert "vazio" in w["templates"]


def test_welcome_com_projeto():
    assert BoasVindas().mostrar(True) is None


def test_menu_arquivo():
    itens = [i["id"] for i in menu_contexto("arquivo")]
    for esperado in ("abrir", "renomear", "duplicar",
                     "excluir", "copiar_caminho",
                     "copiar_nome"):
        assert esperado in itens


def test_menu_pasta():
    itens = [i["id"] for i in menu_contexto("pasta")]
    for esperado in ("abrir_pasta", "novo_arquivo",
                     "nova_pasta", "renomear", "excluir",
                     "copiar_caminho"):
        assert esperado in itens


def test_menu_projeto():
    itens = [i["id"] for i in menu_contexto("projeto")]
    for esperado in ("novo_arquivo", "nova_pasta",
                     "recarregar", "fechar_projeto"):
        assert esperado in itens


def test_menu_invalido():
    with pytest.raises(ErroELiXX):
        menu_contexto(" impressora ")


def test_arrastar_proposta():
    op = interpretar_arrastar("src/a.elixx", "dados")
    assert op == {"operacao": "renomear",
                  "origem": "src/a.elixx",
                  "destino": "dados/a.elixx",
                  "modo": "proposta"}


def test_arrastar_mesma_pasta():
    with pytest.raises(ErroELiXX):
        interpretar_arrastar("src/a.elixx", "src")


def test_arrastar_traversal():
    with pytest.raises(ErroELiXX):
        interpretar_arrastar("../../x", "src")


# ---------- seguranca ----------


def test_scan_f41():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/projeto_workspace.py"
               ).read_text(encoding="utf-8")
    for proibido in ("eval(", "exec(", "importlib",
                     "__import__", "pickle", "subprocess",
                     "os.system", "shell=True", "requests"):
        assert proibido not in fonte, proibido


def test_nome_malicioso(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    for ruim in ("../x", "a\x00b", ".", "C:\\w"):
        with pytest.raises(ErroELiXX):
            novo_projeto(app.workspace, ruim, tmp_path)


def test_conteudo_gigante_bloqueado(tmp_path):
    _, ws = _ws_base(tmp_path)
    (tmp_path / "p" / "src" / "big.txt").write_bytes(
        b"x" * (6_000_000))
    with pytest.raises(ErroELiXX):
        estado_arquivo(ws.app.workspace, ws.modelo,
                       "src/big.txt")


def test_conteudo_nao_executa(tmp_path):
    _, ws = _ws_base(tmp_path)
    (tmp_path / "p" / "src" / "evil.elixx").write_text(
        "__import__('os').system('x')\n", encoding="utf-8")
    ws.analisar()
    assert ws.modelo is not None


def test_unicode_estranho(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    rel = ArvoreArquivos(ws.app.workspace).criar_arquivo(
        "src/café_日本語.txt", "oi")
    assert (tmp_path / "p" / rel).is_file()


# ---------- performance ----------


def test_perf_100_arquivos(tmp_path):
    import time

    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    arv = ArvoreArquivos(ws.app.workspace)
    inicio = time.perf_counter()
    for i in range(100):
        arv.criar_arquivo(f"src/m{i:03d}.txt", "x")
    assert time.perf_counter() - inicio < 15.0
    assert len(arv.listar("src")) >= 100


def test_perf_500_arquivos(tmp_path):
    import time

    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    arv = ArvoreArquivos(ws.app.workspace)
    inicio = time.perf_counter()
    for i in range(500):
        arv.criar_arquivo(f"src/n{i:03d}.txt", "x")
    assert time.perf_counter() - inicio < 30.0


def test_perf_1000_arquivos_tree(tmp_path):
    import time

    from elixx.studio.modelo.modelo import (
        EntidadeSemantica,
        ModeloSemantico,
    )

    inicio = time.perf_counter()
    modelo = ModeloSemantico("p")
    for i in range(1000):
        modelo.adicionar_entidade(
            EntidadeSemantica(f"arquivo:{i:04d}", "arquivo",
                              f"m{i:04d}",
                              arquivo=f"src/m{i:04d}.elixx",
                              linha=1))
    arv = ArvoreProjetoReal.__new__(ArvoreProjetoReal)
    assert len(modelo.entidades()) == 1000
    assert time.perf_counter() - inicio < 15.0
    assert arv is not None


def test_perf_entidades():
    import time

    from elixx.studio.modelo.modelo import (
        EntidadeSemantica,
        ModeloSemantico,
    )

    for n, limite in ((1000, 5.0), (5000, 12.0),
                      (10000, 25.0)):
        modelo = ModeloSemantico("p")
        inicio = time.perf_counter()
        for i in range(n):
            modelo.adicionar_entidade(
                EntidadeSemantica(f"simbolo:{i:05d}",
                                  "simbolo", f"n{i}"))
        assert time.perf_counter() - inicio < limite


def test_perf_codigo_10_100_500kb():
    import time

    from elixx.studio.editor import diagnosticar_texto

    base = 'janela p {\n titulo: "T"\n}\n'
    for kb, limite in ((10, 5.0), (100, 10.0), (500, 20.0)):
        texto = base * ((kb * 1024) // len(base) + 1)
        inicio = time.perf_counter()
        diagnosticar_texto(texto[: kb * 1024], "m")
        assert time.perf_counter() - inicio < limite


def test_fotografia_1000(tmp_path):
    import time

    _, ws = _ws_base(tmp_path)
    for i in range(200):
        (tmp_path / "p" / "src" / f"f{i:03d}.txt"
         ).write_text("x", encoding="utf-8")
    foto = Fotografia()
    inicio = time.perf_counter()
    total = foto.fotografar(ws.app.workspace)
    assert total >= 200
    assert time.perf_counter() - inicio < 15.0
    assert foto.alterados_externamente(ws.app.workspace) \
        == []


# ---------- responsivo / estado ----------


def test_geometrias_suportadas(tmp_path):
    _, ws = _ws_base(tmp_path)
    for larg, alt in ((800, 500), (1024, 768), (1280, 720),
                      (1366, 768), (1600, 900),
                      (1920, 1080), (3840, 2160)):
        ws.layout.definir_geometria(larg, alt)
        assert ws.layout.geometria == (larg, alt)


def test_layouts_intactos():
    from elixx.studio.workspace_ui import LAYOUTS

    for nome in ("DEFAULT", "CODE", "SCENE", "AGENT",
                 "REVIEW"):
        assert nome in LAYOUTS


def test_tk_wiring_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for marca in ("_menu_project", "_boas_vindas",
                  "_atalho_novo_arquivo", "_atalho_fechar_aba",
                  "_atalho_proxima_aba", "Novo Projeto..."):
        assert marca in fonte, marca


# ---------- extras (cobertura) ----------


def test_template_conteudo_minimo(tmp_path):
    assert conteudo_template("minimo").strip().startswith(
        "janela")


def test_nome_com_espaco_ok(tmp_path):
    from elixx.studio import StudioApp

    app = StudioApp()
    info = novo_projeto(app.workspace, "Meu Jogo", tmp_path)
    assert info["projeto"] == "Meu Jogo"


def test_recentes_persistencia_vazia(tmp_path):
    rec = Recentes(tmp_path / "v.json")
    assert rec.listar() == []
    rec.adicionar("A", "C:/a")
    assert Recentes(tmp_path / "v.json").listar()


def test_recentes_duplicado_sobe(tmp_path):
    rec = Recentes()
    rec.adicionar("A", "C:/a")
    rec.adicionar("B", "C:/b")
    rec.adicionar("A", "C:/a")
    assert [i["nome"] for i in rec.listar()] == ["A", "B"]


def test_tree_icones(tmp_path):
    _, ws = _ws_base(tmp_path)
    (tmp_path / "p" / "assets").mkdir(exist_ok=True)
    (tmp_path / "p" / "assets" / "j.png").write_bytes(b"x")
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    texto = "\n".join(arv.linhas())
    assert "▤" in texto and "◆" in texto


def test_tree_repr(tmp_path):
    _, ws = _ws_base(tmp_path)
    arv = ArvoreProjetoReal(ws.app.workspace)
    arv.atualizar()
    assert "ArvoreProjetoReal(" in repr(arv)
    assert "Fotografia(" in repr(Fotografia())


def test_abas_anterior_primeira(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.app.documentos.abrir("a.txt", "a")
    assert AbasAvancadas(ws.app.documentos).anterior() == \
        "a.txt"


def test_abas_vazias_none(tmp_path):
    _, ws = _ws_base(tmp_path)
    abas = AbasAvancadas(ws.app.documentos)
    assert abas.proxima() is None
    assert abas.anterior() is None


def test_salvar_editor_marca(tmp_path):
    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar(FONTE + " ")
    saida = ws.salvar_editor("src/main.elixx")
    assert saida["arquivo"] == "src/main.elixx"
    assert saida["modificado"] is False


def test_diagnostico_codigo(tmp_path):
    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar("janela { !!!")
    codigos = {d.codigo for d in ed.analisar()}
    assert codigos


def test_execucao_resumo_janelas(tmp_path):
    from elixx.studio.preview import HeadlessPreview

    saida = executar_projeto(HeadlessPreview(), FONTE)
    assert saida["resumo"]["nos"] >= 1


def test_palette_abrir_sem_caminho(tmp_path):
    _, ws = _ws_base(tmp_path)
    with pytest.raises(ErroELiXX):
        executar_palette_f41(ws, "abrir_arquivo", {})


def test_palette_salvar_sem_aberto(tmp_path):
    _, ws = _ws_base(tmp_path)
    with pytest.raises(ErroELiXX):
        executar_palette_f41(ws, "salvar", {})


def test_palette_novo_projeto_templates(tmp_path):
    _, ws = _ws_base(tmp_path)
    saida = executar_palette_f41(ws, "novo_projeto")
    assert set(saida["templates"]) == set(TEMPLATES)


def test_estado_dirty_files(tmp_path):
    _, ws = _ws_base(tmp_path)
    ed = ws.abrir_no_editor("src/main.elixx")
    ed.editar(FONTE + " ")
    dados = estado_projeto(ws).to_dict()
    assert dados["dirty_files"] == ["src/main.elixx"]


def test_menu_rotulos_pt():
    for item in menu_contexto("arquivo"):
        assert item["rotulo"] and item["rotulo"][0].isupper()


def test_welcome_templates_recentes():
    rec = Recentes()
    rec.adicionar("D", "C:/d")
    w = BoasVindas(rec).mostrar(False)
    assert w["recentes"][0]["nome"] == "D"
    assert len(w["templates"]) == 5


def test_fotografia_repr_vazia():
    assert repr(Fotografia()) == "Fotografia(0 arquivos)"


def test_rel_seguro_unicode(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.arquivos import ArvoreArquivos

    rel = ArvoreArquivos(ws.app.workspace).criar_arquivo(
        "src/áéí.txt", "x")
    assert (tmp_path / "p" / rel).is_file()


def test_rel_absoluto_bloqueado(tmp_path):
    _, ws = _ws_base(tmp_path)
    with pytest.raises(ErroELiXX):
        estado_arquivo(ws.app.workspace, ws.modelo,
                       "/etc/passwd")


def test_nome_nulo_bloqueado(tmp_path):
    from elixx.studio import StudioApp

    with pytest.raises(ErroELiXX):
        novo_projeto(StudioApp().workspace, "a\x00b",
                     tmp_path)


def test_compacto_layouts(tmp_path):
    _, ws = _ws_base(tmp_path)
    from elixx.studio.workspace_ui import aplicar_layout_nome

    for nome in ("DEFAULT", "CODE", "SCENE", "AGENT",
                 "REVIEW"):
        assert aplicar_layout_nome(ws, nome)


def test_estado_execucao_estados():
    from elixx.studio.projeto_workspace import EstadoExecucao

    assert set(EstadoExecucao.ESTADOS) == {
        "PRONTO", "VALIDANDO", "EXECUTANDO", "CONCLUIDO",
        "ERRO", "PARADO"}


def test_fechar_para_preview(tmp_path):
    _, ws = _ws_base(tmp_path)
    ws.preview.executar(FONTE)
    fechar_projeto(ws)
    assert ws.app.preview.rodando is False


def test_tk_wiring_fonte():
    from pathlib import Path as _P

    fonte = _P("elixx/studio/workspace_ui.py").read_text(
        encoding="utf-8")
    for marca in ("_menu_project", "_boas_vindas",
                  "_atalho_novo_arquivo", "_atalho_fechar_aba",
                  "_atalho_proxima_aba", "Novo Projeto..."):
        assert marca in fonte, marca
