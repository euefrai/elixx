"""ELiXX Studio (Fase 25) — ambiente visual de desenvolvimento.

Fundação: projeto, workspace, documentos, editor, preview (Tk e
headless), inspetor, assets, timeline, logs, diagnósticos, comandos,
eventos e configuração — sobre o MESMO modelo semântico do
compilador/runtime (nunca um "mini-ELiXX" paralelo).

"O Studio é uma ferramenta de desenvolvimento do ELiXX, não uma
dependência necessária para executar aplicações ELiXX."

"Código e visual são representações diferentes do mesmo projeto."
"""
from elixx.studio.app import StudioApp
from elixx.studio.arquivos import ArvoreArquivos
from elixx.studio.assets import Asset, GerenciadorAssets
from elixx.studio.cena import ModeloCena, Timeline, timeline_de_motions
from elixx.studio.comandos import (
    AgentChange,
    AgentCommand,
    AgentContext,
    AgentProposal,
    FilaComandos,
    StudioCommand,
)
from elixx.studio.documento import DocumentoELiXX, GerenciadorDocumentos
from elixx.studio.editor import (
    Diagnostic,
    EditorCodigo,
    diagnosticar_texto,
)
from elixx.studio.estado import Configuracao
from elixx.studio.eventos import EventBus
from elixx.studio.inspetor import (
    InspecaoPersonagem,
    Inspetor,
    Selecao,
    fluxo_personagem,
)
from elixx.studio.logs import PainelLogs
from elixx.studio.preview import (
    HeadlessPreview,
    PreviewResultado,
    StudioPreview,
    TkPreview,
)
from elixx.studio.projeto import ProjetoELiXX
from elixx.studio.workspace import Workspace
from elixx.studio.workspace_ui import (
    ArvoreProjeto,
    ConsoleModelo,
    DiagnosticosModelo,
    EditorModelo,
    InspectorModelo,
    Layout,
    PainelAgent,
    PreviewModelo,
    StudioWorkspace,
    destacar_lexico,
    montar_workspace_ui,
)

__all__ = [
    "StudioApp",
    "ArvoreArquivos",
    "Asset", "GerenciadorAssets",
    "ModeloCena", "Timeline", "timeline_de_motions",
    "AgentChange", "AgentCommand", "AgentContext", "AgentProposal",
    "FilaComandos", "StudioCommand",
    "DocumentoELiXX", "GerenciadorDocumentos",
    "Diagnostic", "EditorCodigo", "diagnosticar_texto",
    "Configuracao",
    "EventBus",
    "InspecaoPersonagem", "Inspetor", "Selecao", "fluxo_personagem",
    "PainelLogs",
    "HeadlessPreview", "PreviewResultado", "StudioPreview",
    "TkPreview",
    "ProjetoELiXX",
    "Workspace",
    "ArvoreProjeto", "ConsoleModelo", "DiagnosticosModelo",
    "EditorModelo", "InspectorModelo", "Layout", "PainelAgent",
    "PreviewModelo", "StudioWorkspace", "destacar_lexico",
    "montar_workspace_ui",
]
