"""ELiXX Semantic Project Model (Fase 27) — leitura e indexação.

"O Modelo Semântico não substitui o AST."

"O Modelo Semântico não executa o projeto."
"""
from elixx.studio.modelo.adaptador import (
    AdaptadorAST,
    analisar_projeto,
    analisar_texto,
    atualizar_arquivo,
    modelo_para_contexto,
    mutacao_para_changeset,
    resumo_para_inspetor,
)
from elixx.studio.modelo.consulta import ConsultaSemantica
from elixx.studio.modelo.indice import IndiceSemantico
from elixx.studio.modelo.modelo import (
    EntidadeSemantica,
    ModeloSemantico,
    MutacaoSemantica,
    RelacaoSemantica,
)
from elixx.studio.modelo.validacao import (
    SnapshotSemantico,
    comparar_snapshots,
    validar_modelo,
)

__all__ = [
    "AdaptadorAST", "analisar_projeto", "analisar_texto",
    "atualizar_arquivo", "modelo_para_contexto",
    "mutacao_para_changeset", "resumo_para_inspetor",
    "ConsultaSemantica",
    "IndiceSemantico",
    "EntidadeSemantica", "ModeloSemantico", "MutacaoSemantica",
    "RelacaoSemantica",
    "SnapshotSemantico", "comparar_snapshots", "validar_modelo",
]
