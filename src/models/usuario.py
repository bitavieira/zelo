from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

def criar_usuario_doc(nome, email, senha, perfil="leitor"):
    """
    Retorna um dicionário representando o documento do usuário pronto para inserção no MongoDB.
    """
    return {
        "nome": nome.strip(),
        "email": email.strip().lower(),
        "senha_hash": generate_password_hash(senha),
        "perfil": perfil if perfil in ["admin", "leitor"] else "leitor",
        "ativo": True,
        "criado_em": datetime.now(timezone.utc)
    }

def validar_usuario_payload(payload, is_update=False):
    """
    Valida os dados recebidos para criação ou atualização de um usuário.
    Retorna (dados_validados, erro_mensagem).
    """
    erros = []
    
    nome = payload.get("nome")
    email = payload.get("email")
    senha = payload.get("senha")
    perfil = payload.get("perfil")
    
    # Validações para Criação
    if not is_update:
        if not nome or not str(nome).strip():
            erros.append("O campo 'nome' é obrigatório.")
        if not email or not str(email).strip():
            erros.append("O campo 'email' é obrigatório.")
        if not senha or not str(senha).strip():
            erros.append("O campo 'senha' é obrigatório.")
        elif len(str(senha)) < 6:
            erros.append("A senha deve ter pelo menos 6 caracteres.")
        if perfil and perfil not in ["admin", "leitor"]:
            erros.append("O campo 'perfil' deve ser 'admin' ou 'leitor'.")
    else:
        # Validações para Atualização
        if nome is not None and not str(nome).strip():
            erros.append("O campo 'nome' não pode ser vazio.")
        if email is not None and not str(email).strip():
            erros.append("O campo 'email' não pode ser vazio.")
        if senha is not None:
            if not str(senha).strip():
                erros.append("O campo 'senha' não pode ser vazio.")
            elif len(str(senha)) < 6:
                erros.append("A senha deve ter pelo menos 6 caracteres.")
        if perfil is not None and perfil not in ["admin", "leitor"]:
            erros.append("O campo 'perfil' deve ser 'admin' ou 'leitor'.")
            
    if erros:
        return None, "; ".join(erros)
        
    # Limpa e formata os dados validados
    dados_validados = {}
    if nome is not None:
        dados_validados["nome"] = str(nome).strip()
    if email is not None:
        dados_validados["email"] = str(email).strip().lower()
    if senha is not None:
        dados_validados["senha_hash"] = generate_password_hash(str(senha))
    if perfil is not None:
        dados_validados["perfil"] = perfil
        
    return dados_validados, None
