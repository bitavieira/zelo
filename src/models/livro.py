from datetime import datetime, timezone

def criar_livro_doc(titulo, autor, isbn, quantidade_exemplares, editora=None, ano_publicacao=None, genero=None):
    """
    Retorna um dicionário representando o documento do livro pronto para inserção no MongoDB.
    """
    qtd = int(quantidade_exemplares)
    return {
        "titulo": titulo.strip(),
        "autor": autor.strip(),
        "isbn": isbn.strip(),
        "quantidade_exemplares": qtd,
        "exemplares_disponiveis": qtd,
        "editora": editora.strip() if editora else None,
        "ano_publicacao": int(ano_publicacao) if ano_publicacao else None,
        "genero": genero.strip() if genero else None,
        "ativo": True,
        "criado_em": datetime.now(timezone.utc)
    }

def validar_livro_payload(payload, is_update=False):
    """
    Valida os dados recebidos para criação ou atualização de um livro.
    Retorna (dados_validados, erro_mensagem).
    """
    erros = []
    
    titulo = payload.get("titulo")
    autor = payload.get("autor")
    isbn = payload.get("isbn")
    quantidade_exemplares = payload.get("quantidade_exemplares")
    editora = payload.get("editora")
    ano_publicacao = payload.get("ano_publicacao")
    genero = payload.get("genero")
    
    # Validações para Criação
    if not is_update:
        if not titulo or not str(titulo).strip():
            erros.append("O campo 'titulo' é obrigatório.")
        if not autor or not str(autor).strip():
            erros.append("O campo 'autor' é obrigatório.")
        if not isbn or not str(isbn).strip():
            erros.append("O campo 'isbn' é obrigatório.")
        if quantidade_exemplares is None:
            erros.append("O campo 'quantidade_exemplares' é obrigatório.")
        else:
            try:
                qtd = int(quantidade_exemplares)
                if qtd < 0:
                    erros.append("A 'quantidade_exemplares' não pode ser negativa.")
            except (ValueError, TypeError):
                erros.append("A 'quantidade_exemplares' deve ser um número inteiro válido.")
    else:
        # Validações para Atualização
        if titulo is not None and not str(titulo).strip():
            erros.append("O campo 'titulo' não pode ser vazio.")
        if autor is not None and not str(autor).strip():
            erros.append("O campo 'autor' não pode ser vazio.")
        if isbn is not None and not str(isbn).strip():
            erros.append("O campo 'isbn' não pode ser vazio.")
        if quantidade_exemplares is not None:
            try:
                qtd = int(quantidade_exemplares)
                if qtd < 0:
                    erros.append("A 'quantidade_exemplares' não pode ser negativa.")
            except (ValueError, TypeError):
                erros.append("A 'quantidade_exemplares' deve ser um número inteiro válido.")
                
    if ano_publicacao is not None:
        try:
            int(ano_publicacao)
        except (ValueError, TypeError):
            erros.append("O 'ano_publicacao' deve ser um número inteiro válido.")

    if erros:
        return None, "; ".join(erros)
        
    # Limpa e formata os dados validados
    dados_validados = {}
    if titulo is not None:
        dados_validados["titulo"] = str(titulo).strip()
    if autor is not None:
        dados_validados["autor"] = str(autor).strip()
    if isbn is not None:
        dados_validados["isbn"] = str(isbn).strip()
    if quantidade_exemplares is not None:
        dados_validados["quantidade_exemplares"] = int(quantidade_exemplares)
    if editora is not None:
        dados_validados["editora"] = str(editora).strip() if editora else None
    if ano_publicacao is not None:
        dados_validados["ano_publicacao"] = int(ano_publicacao) if ano_publicacao else None
    if genero is not None:
        dados_validados["genero"] = str(genero).strip() if genero else None
        
    return dados_validados, None
