from datetime import datetime, timedelta, timezone
from bson import ObjectId

def criar_emprestimo_doc(livro_id, usuario_id, dias_duracao=14, data_emprestimo=None, data_devolucao_prevista=None):
    """
    Retorna um dicionário representando o documento do empréstimo pronto para inserção no MongoDB.
    """
    agora = data_emprestimo or datetime.now(timezone.utc)
    devolucao_prevista = data_devolucao_prevista or (agora + timedelta(days=dias_duracao))
    
    return {
        "livro_id": ObjectId(livro_id) if isinstance(livro_id, str) else livro_id,
        "usuario_id": ObjectId(usuario_id) if isinstance(usuario_id, str) else usuario_id,
        "data_emprestimo": agora,
        "data_devolucao_prevista": devolucao_prevista,
        "data_devolucao_real": None,
        "status": "ativo"  # ativo | atrasado | devolvido
    }

