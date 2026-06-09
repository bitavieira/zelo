from flask import Blueprint, request, jsonify
from bson import ObjectId
from bson.errors import InvalidId
from src.database import usuarios_col
from src.models.usuario import criar_usuario_doc, validar_usuario_payload
from src.middlewares.auth_middleware import requer_autenticacao

usuario_bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")

def serialize_usuario(usuario):
    return {
        "id": str(usuario["_id"]),
        "nome": usuario["nome"],
        "email": usuario["email"],
        "perfil": usuario["perfil"],
        "ativo": usuario.get("ativo", True),
        "criado_em": usuario.get("criado_em")
    }

@usuario_bp.route("/", methods=["GET"])
@requer_autenticacao("admin")
def listar_usuarios():
    usuarios = list(usuarios_col.find())
    return jsonify([serialize_usuario(u) for u in usuarios]), 200

@usuario_bp.route("/<string:id>", methods=["GET"])
@requer_autenticacao("admin")
def detalhar_usuario(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de usuário inválido."}), 400
        
    usuario = usuarios_col.find_one({"_id": obj_id})
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404
        
    return jsonify(serialize_usuario(usuario)), 200

@usuario_bp.route("/", methods=["POST"])
@requer_autenticacao("admin")
def cadastrar_usuario():
    data = request.get_json() or {}
    
    # Valida payload
    dados_validados, erro = validar_usuario_payload(data, is_update=False)
    if erro:
        return jsonify({"error": erro}), 400
        
    # Verifica duplicidade de E-mail
    email_existente = usuarios_col.find_one({"email": dados_validados["email"]})
    if email_existente:
        return jsonify({"error": "Já existe um usuário cadastrado com este e-mail."}), 400
        
    # Cria documento e insere
    usuario_doc = criar_usuario_doc(
        nome=dados_validados["nome"],
        email=dados_validados["email"],
        senha=data["senha"],  # passa a senha crua para criar_usuario_doc que hash ela
        perfil=dados_validados.get("perfil", "leitor")
    )
    
    usuarios_col.insert_one(usuario_doc)
    return jsonify(serialize_usuario(usuario_doc)), 201

@usuario_bp.route("/<string:id>", methods=["PUT"])
@requer_autenticacao("admin")
def atualizar_usuario(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de usuário inválido."}), 400
        
    usuario = usuarios_col.find_one({"_id": obj_id})
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404
        
    data = request.get_json() or {}
    
    # Valida payload
    dados_validados, erro = validar_usuario_payload(data, is_update=True)
    if erro:
        return jsonify({"error": erro}), 400
        
    # Se e-mail está sendo atualizado, verifica duplicidade
    if "email" in dados_validados and dados_validados["email"] != usuario["email"]:
        email_existente = usuarios_col.find_one({"email": dados_validados["email"]})
        if email_existente:
            return jsonify({"error": "Já existe outro usuário cadastrado com este e-mail."}), 400
            
    # Atualiza no banco
    usuarios_col.update_one({"_id": obj_id}, {"$set": dados_validados})
    
    usuario_atualizado = usuarios_col.find_one({"_id": obj_id})
    return jsonify(serialize_usuario(usuario_atualizado)), 200

@usuario_bp.route("/<string:id>", methods=["DELETE"])
@requer_autenticacao("admin")
def desativar_usuario(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de usuário inválido."}), 400
        
    usuario = usuarios_col.find_one({"_id": obj_id})
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404
        
    # Desativa usuário
    usuarios_col.update_one({"_id": obj_id}, {"$set": {"ativo": False}})
    
    return jsonify({"message": "Usuário desativado com sucesso."}), 200
