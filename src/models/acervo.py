from datetime import datetime, timezone
from bson import ObjectId

def criar_acervo_doc(nome, proprietario_id, descricao=None, visibilidade="publico", membros=None, configuracoes=None):
    """
    Retorna um dicionário representando o documento de acervo pronto para inserção no MongoDB.
    """
    prop_id = ObjectId(proprietario_id) if isinstance(proprietario_id, str) else proprietario_id
    
    lista_membros = []
    if membros:
        for m in membros:
            u_id = ObjectId(m["usuario_id"]) if isinstance(m["usuario_id"], str) else m["usuario_id"]
            lista_membros.append({
                "usuario_id": u_id,
                "papel": m.get("papel", "Leitor")
            })
    else:
        # Adiciona o próprio proprietário como administrador por padrão
        lista_membros.append({
            "usuario_id": prop_id,
            "papel": "Administrador"
        })
        
    config = {
        "prazo_devolucao_padrao": 14,
        "max_livros_por_emprestimo": 3,
        "notif_atraso": True,
        "notif_devolucao": True
    }
    if configuracoes:
        config.update(configuracoes)
        
    return {
        "nome": nome.strip(),
        "descricao": descricao.strip() if descricao else "",
        "visibilidade": visibilidade.strip() if visibilidade else "publico",
        "proprietario_id": prop_id,
        "membros": lista_membros,
        "configuracoes": config,
        "criado_em": datetime.now(timezone.utc)
    }

def validar_acervo_payload(payload, is_update=False):
    """
    Valida os dados recebidos para criação ou atualização de um acervo.
    Retorna (dados_validados, erro_mensagem).
    """
    erros = []
    
    nome = payload.get("nome")
    descricao = payload.get("descricao")
    visibilidade = payload.get("visibilidade")
    membros = payload.get("membros")
    configuracoes = payload.get("configuracoes")
    
    # Validações para Criação
    if not is_update:
        if not nome or not str(nome).strip():
            erros.append("O campo 'nome' é obrigatório.")
            
    if visibilidade is not None and visibilidade not in ["publico", "privado", "pub", "priv"]:
        erros.append("O campo 'visibilidade' deve ser 'publico' ou 'privado'.")
        
    if membros is not None:
        if not isinstance(membros, list):
            erros.append("O campo 'membros' deve ser uma lista.")
        else:
            for i, m in enumerate(membros):
                if not isinstance(m, dict) or "usuario_id" not in m:
                    erros.append(f"Membro no índice {i} deve ser um objeto contendo 'usuario_id'.")
                    
    if erros:
        return None, "; ".join(erros)
        
    # Formata dados validados
    dados_validados = {}
    if nome is not None:
        dados_validados["nome"] = str(nome).strip()
    if descricao is not None:
        dados_validados["descricao"] = str(descricao).strip()
    if visibilidade is not None:
        # Padroniza visibilidade conforme o formulário html
        vis = str(visibilidade).strip().lower()
        if vis in ["pub", "publico"]:
            dados_validados["visibilidade"] = "publico"
        else:
            dados_validados["visibilidade"] = "privado"
            
    if membros is not None:
        dados_validados["membros"] = membros
        
    if configuracoes is not None and isinstance(configuracoes, dict):
        dados_validados["configuracoes"] = configuracoes
        
    return dados_validados, None
