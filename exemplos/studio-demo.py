"""ELiXX Studio demo (F25) — headless por padrão; UI só com display.

1. cria/abre projeto temporário; 2. cria main.elixx; 3. abre editor;
4. executa preview; 5. seleciona personagem; 6. mostra inspetor;
7. mostra timeline; 8. mostra console; 9. salva; 10. fecha.
"""
import tempfile
from pathlib import Path

from elixx.studio import (
    InspecaoPersonagem,
    StudioApp,
    StudioCommand,
    Timeline,
    fluxo_personagem,
)
from elixx.visual.personagem import Pose


def main(headless: bool = True) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="studio_demo_"))
    app = StudioApp()

    # 1. projeto temporário
    app.workspace.criar_projeto(tmp / "juh_app", "JuhApp")
    print(f"1. projeto: {app.workspace.projeto.nome} em {tmp.name}")

    # 2-3. main.elixx + editor
    fonte = ("janela p {\n titulo: \"Juh\"\n personagem Juh {\n"
             "  posição: 100px 100px\n  parte corpo {\n"
             "   imagem: \"corpo.png\"\n  }\n"
             "  pose neutra {\n   corpo:\n    rotação: 0deg\n  }\n"
             " }\n}\n")
    app.arquivos.criar_arquivo("src/cenas.elixx", fonte)
    app.executar_comando(StudioCommand("abrir_arquivo",
                                       "src/main.elixx"))
    doc = app.documentos.obter("src/main.elixx")
    doc.definir_texto(fonte)  # editor: main recebe o programa
    print(f"2-3. editor: {doc.linhas()} linhas, dirty={doc.dirty}")

    # 4. preview (headless: pipeline oficial, sem janela)
    out = app.executar_comando(StudioCommand("executar",
                                             "src/main.elixx"))
    print(f"4. preview: ok={out['ok']} resumo={out['resumo']}")

    # 5-6. personagem via fluxo F23/F24 + inspetor
    _rig, perso, _drig = fluxo_personagem("Juh", [
        {"id": "tronco", "tipo": "tronco"},
        {"id": "cabeca", "tipo": "cabeca", "parent_id": "tronco"},
    ])
    app.executar_comando(StudioCommand(
        "selecionar", "cabeca", {"tipo": "parte"}))
    insp = InspecaoPersonagem(perso)
    print(f"5-6. selecao={app.inspetor.selecao} "
          f"inspetor={insp.resumo()}")

    # 7. timeline a partir de motions F11
    defs = perso.transicionar_pose(
        Pose("olhar", entradas={"cabeca": {"rotacao": 10.0}}))
    linha = Timeline()
    for d in defs:
        linha.adicionar(d.alvo, d.nome, 0.0, d.duracao_ms)
    print(f"7. timeline: {linha}")

    # 8-10. console, salvar, fechar
    print(f"8. console: {[e['mensagem'] for e in app.logs.entradas]}")
    app.executar_comando(StudioCommand("salvar", "src/main.elixx"))
    print(f"9. salvo: sujos={app.documentos.sujos()}")
    app.workspace.fechar_projeto()
    print(f"10. fechado: aberto={app.workspace.aberto}")

    if not headless and StudioApp.interface_disponivel():
        app2 = StudioApp()
        janela = app2.montar_ui()
        janela.after(1500, janela.destroy)
        janela.mainloop()
        app2.fechar_ui()
        print("ui: janela exibida e fechada")
    else:
        print("ui: headless (passe headless=False com display)")


if __name__ == "__main__":
    main()
