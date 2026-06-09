from flask import Blueprint, request, jsonify, g
from werkzeug.security import check_password_hash
from src.database import usuarios_col
from src.middlewares.auth_middleware import gerar_token, requer_autenticacao
from src.models.usuario import criar_usuario_doc

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

def serialize_usuario(usuario):
    return {
        "id": str(usuario["_id"]),
        "nome": usuario["nome"],
        "email": usuario["email"],
        "perfil": usuario["perfil"],
        "ativo": usuario.get("ativo", True),
        "criado_em": usuario.get("criado_em")
    }

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    senha = data.get("senha")
    
    if not email or not senha:
        return jsonify({"error": "E-mail e senha são obrigatórios."}), 400
        
    # Busca usuário ativo no banco
    usuario = usuarios_col.find_one({"email": email.strip().lower(), "ativo": True})
    
    if not usuario or not check_password_hash(usuario["senha_hash"], senha):
        return jsonify({"error": "Credenciais inválidas ou conta desativada."}), 401
        
    # Gera o Bearer token
    token = gerar_token(usuario["_id"], usuario["perfil"])
    
    return jsonify({
        "token": token,
        "usuario": serialize_usuario(usuario)
    }), 200

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    nome = data.get("nome")
    email = data.get("email")
    senha = data.get("senha")
    
    if not nome or not email or not senha:
        return jsonify({"error": "Nome, e-mail e senha são obrigatórios."}), 400
        
    email_existente = usuarios_col.find_one({"email": email.strip().lower()})
    if email_existente:
        return jsonify({"error": "Já existe um usuário cadastrado com este e-mail."}), 400
        
    perfil = data.get("perfil", "leitor")
    if perfil not in ["admin", "leitor"]:
        perfil = "leitor"
    usuario_doc = criar_usuario_doc(nome, email, senha, perfil=perfil)
    usuarios_col.insert_one(usuario_doc)

    
    token = gerar_token(usuario_doc["_id"], usuario_doc["perfil"])
    
    return jsonify({
        "token": token,
        "usuario": serialize_usuario(usuario_doc)
    }), 201

@auth_bp.route("/logout", methods=["POST"])
@requer_autenticacao()
def logout():
    # Logout em API REST stateless é primariamente controlado pelo cliente descatando o token,
    # mas confirmamos o sucesso da requisição.
    return jsonify({"message": "Logout realizado com sucesso."}), 200

@auth_bp.route("/me", methods=["GET"])
@requer_autenticacao()
def me():
    # Retorna o usuário carregado pelo middleware
    return jsonify(serialize_usuario(g.usuario)), 200
