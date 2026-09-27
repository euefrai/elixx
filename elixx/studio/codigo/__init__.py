"""Semantic Code Sync (Fase 32) — código ↔ modelo, sem regex cega."""
from elixx.studio.codigo.gerador import (
    gerar_alteracao,
    validar_candidato,
)
from elixx.studio.codigo.localizacao import (
    LocalizacaoCodigo,
    RegiaoCodigo,
    localizar_entidade,
    localizar_propriedade,
)
from elixx.studio.codigo.mudanca import AlteracaoCodigo
from elixx.studio.codigo.sincronizador import (
    SincronizadorBidirecional,
    SincronizadorCodigo,
    aplicar_com_changeset,
    diff_textual,
    sincronizar_workspace,
)

__all__ = [
    "gerar_alteracao", "validar_candidato",
    "LocalizacaoCodigo", "RegiaoCodigo", "localizar_entidade",
    "localizar_propriedade",
    "AlteracaoCodigo",
    "SincronizadorBidirecional", "SincronizadorCodigo",
    "aplicar_com_changeset", "diff_textual",
    "sincronizar_workspace",
]
