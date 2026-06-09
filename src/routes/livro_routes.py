from flask import Blueprint, request, jsonify
from bson import ObjectId
from bson.errors import InvalidId
from src.database import livros_col
from src.models.livro import criar_livro_doc, validar_livro_payload
from src.middlewares.auth_middleware import requer_autenticacao

livro_bp = Blueprint("livros", __name__, url_prefix="/api/livros")

def serialize_livro(livro):
    return {
        "id": str(livro["_id"]),
        "titulo": livro["titulo"],
        "autor": livro["autor"],
        "isbn": livro["isbn"],
        "quantidade_exemplares": livro["quantidade_exemplares"],
        "exemplares_disponiveis": livro["exemplares_disponiveis"],
        "editora": livro.get("editora"),
        "ano_publicacao": livro.get("ano_publicacao"),
        "genero": livro.get("genero"),
        "ativo": livro.get("ativo", True),
        "criado_em": livro.get("criado_em")
    }

@livro_bp.route("/", methods=["GET"])
@requer_autenticacao()
def listar_livros():
    disponiveis = request.args.get("disponiveis", "false").lower() == "true"
    
    query = {"ativo": {"$ne": False}}
    if disponiveis:
        query["exemplares_disponiveis"] = {"$gt": 0}
        
    livros = list(livros_col.find(query))
    return jsonify([serialize_livro(l) for l in livros]), 200

@livro_bp.route("/buscar", methods=["GET"])
@requer_autenticacao()
def buscar_livros():
    q = request.args.get("q", "").strip()
    if not q:
        livros = list(livros_col.find({"ativo": {"$ne": False}}))
    else:
        query = {
            "ativo": {"$ne": False},
            "$or": [
                {"titulo": {"$regex": q, "$options": "i"}},
                {"autor": {"$regex": q, "$options": "i"}},
                {"isbn": {"$regex": q, "$options": "i"}}
            ]
        }
        livros = list(livros_col.find(query))
        
    return jsonify([serialize_livro(l) for l in livros]), 200

@livro_bp.route("/<string:id>", methods=["GET"])
@requer_autenticacao()
def detalhar_livro(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de livro inválido."}), 400
        
    livro = livros_col.find_one({"_id": obj_id})
    if not livro:
        return jsonify({"error": "Livro não encontrado."}), 404
        
    return jsonify(serialize_livro(livro)), 200

@livro_bp.route("/", methods=["POST"])
@requer_autenticacao("admin")
def cadastrar_livro():
    data = request.get_json() or {}
    
    # Valida payload
    dados_validados, erro = validar_livro_payload(data, is_update=False)
    if erro:
        return jsonify({"error": erro}), 400
        
    # Verifica duplicidade de ISBN
    isbn_existente = livros_col.find_one({"isbn": dados_validados["isbn"]})
    if isbn_existente:
        return jsonify({"error": "Já existe um livro cadastrado com este ISBN."}), 400
        
    # Cria documento e insere
    livro_doc = criar_livro_doc(
        titulo=dados_validados["titulo"],
        autor=dados_validados["autor"],
        isbn=dados_validados["isbn"],
        quantidade_exemplares=dados_validados["quantidade_exemplares"],
        editora=dados_validados.get("editora"),
        ano_publicacao=dados_validados.get("ano_publicacao"),
        genero=dados_validados.get("genero")
    )
    
    livros_col.insert_one(livro_doc)
    return jsonify(serialize_livro(livro_doc)), 201

@livro_bp.route("/<string:id>", methods=["PUT"])
@requer_autenticacao("admin")
def atualizar_livro(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de livro inválido."}), 400
        
    livro = livros_col.find_one({"_id": obj_id})
    if not livro:
        return jsonify({"error": "Livro não encontrado."}), 404
        
    data = request.get_json() or {}
    
    # Valida payload
    dados_validados, erro = validar_livro_payload(data, is_update=True)
    if erro:
        return jsonify({"error": erro}), 400
        
    # Se ISBN está sendo atualizado, verifica duplicidade
    if "isbn" in dados_validados and dados_validados["isbn"] != livro["isbn"]:
        isbn_existente = livros_col.find_one({"isbn": dados_validados["isbn"]})
        if isbn_existente:
            return jsonify({"error": "Já existe outro livro cadastrado com este ISBN."}), 400
            
    # Se quantidade_exemplares está sendo atualizada, ajusta exemplares_disponiveis
    if "quantidade_exemplares" in dados_validados:
        nova_qtd = dados_validados["quantidade_exemplares"]
        velha_qtd = livro["quantidade_exemplares"]
        diferenca = nova_qtd - velha_qtd
        
        novos_disponiveis = livro["exemplares_disponiveis"] + diferenca
        if novos_disponiveis < 0:
            return jsonify({
                "error": f"Não é possível reduzir a quantidade de exemplares para {nova_qtd} "
                         f"pois há {livro['quantidade_exemplares'] - livro['exemplares_disponiveis']} exemplares atualmente emprestados."
            }), 400
            
        dados_validados["exemplares_disponiveis"] = novos_disponiveis
        
    # Atualiza no banco
    livros_col.update_one({"_id": obj_id}, {"$set": dados_validados})
    
    livro_atualizado = livros_col.find_one({"_id": obj_id})
    return jsonify(serialize_livro(livro_atualizado)), 200

@livro_bp.route("/<string:id>", methods=["DELETE"])
@requer_autenticacao("admin")
def remover_livro(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de livro inválido."}), 400
        
    livro = livros_col.find_one({"_id": obj_id})
    if not livro:
        return jsonify({"error": "Livro não encontrado."}), 404
        
    # Soft delete
    livros_col.update_one({"_id": obj_id}, {"$set": {"ativo": False}})
    
    return jsonify({"message": "Livro removido com sucesso."}), 200
