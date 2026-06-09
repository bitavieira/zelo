from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone
from src.database import emprestimos_col, livros_col, usuarios_col
from src.models.emprestimo import criar_emprestimo_doc
from src.middlewares.auth_middleware import requer_autenticacao

emprestimo_bp = Blueprint("emprestimos", __name__, url_prefix="/api/emprestimos")

def serialize_emprestimo(emp):
    """
    Serializa o documento de empréstimo e popula dados básicos de livro e usuário.
    """
    res = {
        "id": str(emp["_id"]),
        "livro_id": str(emp["livro_id"]),
        "usuario_id": str(emp["usuario_id"]),
        "data_emprestimo": emp["data_emprestimo"],
        "data_devolucao_prevista": emp["data_devolucao_prevista"],
        "data_devolucao_real": emp.get("data_devolucao_real"),
        "status": emp["status"]
    }
    
    # Popula livro
    try:
        livro = livros_col.find_one({"_id": emp["livro_id"]})
        if livro:
            res["livro"] = {
                "titulo": livro["titulo"],
                "autor": livro["autor"],
                "isbn": livro["isbn"]
            }
        else:
            res["livro"] = None
    except Exception:
        res["livro"] = None
        
    # Popula usuário
    try:
        usuario = usuarios_col.find_one({"_id": emp["usuario_id"]})
        if usuario:
            res["usuario"] = {
                "nome": usuario["nome"],
                "email": usuario["email"]
            }
        else:
            res["usuario"] = None
    except Exception:
        res["usuario"] = None
        
    return res

@emprestimo_bp.route("/", methods=["POST"])
@requer_autenticacao("admin")
def registrar_emprestimo():
    data = request.get_json() or {}
    livro_id_str = data.get("livro_id")
    usuario_id_str = data.get("usuario_id")
    
    if not livro_id_str or not usuario_id_str:
        return jsonify({"error": "Os campos 'livro_id' e 'usuario_id' são obrigatórios."}), 400
        
    try:
        livro_id = ObjectId(livro_id_str)
        usuario_id = ObjectId(usuario_id_str)
    except InvalidId:
        return jsonify({"error": "Formato de ID inválido."}), 400
        
    # Verifica usuário ativo
    usuario = usuarios_col.find_one({"_id": usuario_id, "ativo": True})
    if not usuario:
        return jsonify({"error": "Usuário não encontrado ou está inativo."}), 404
        
    # Verifica livro ativo e disponível
    livro = livros_col.find_one({"_id": livro_id, "ativo": {"$ne": False}})
    if not livro:
        return jsonify({"error": "Livro não encontrado ou foi removido."}), 404
        
    if livro["exemplares_disponiveis"] <= 0:
        return jsonify({"error": "Não há exemplares disponíveis deste livro para empréstimo."}), 400
        
    # Registra o empréstimo com datas opcionais
    data_emprestimo_str = data.get("data_emprestimo")
    data_devolucao_prevista_str = data.get("data_devolucao_prevista")
    
    data_emprestimo = None
    if data_emprestimo_str:
        try:
            if len(data_emprestimo_str) == 10:
                data_emprestimo_str += "T12:00:00"
            data_emprestimo = datetime.fromisoformat(data_emprestimo_str).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
            
    data_devolucao_prevista = None
    if data_devolucao_prevista_str:
        try:
            if len(data_devolucao_prevista_str) == 10:
                data_devolucao_prevista_str += "T12:00:00"
            data_devolucao_prevista = datetime.fromisoformat(data_devolucao_prevista_str).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    emprestimo_doc = criar_emprestimo_doc(
        livro_id, 
        usuario_id, 
        data_emprestimo=data_emprestimo, 
        data_devolucao_prevista=data_devolucao_prevista
    )
    emprestimos_col.insert_one(emprestimo_doc)

    
    # Decrementa exemplares disponíveis
    livros_col.update_one(
        {"_id": livro_id},
        {"$inc": {"exemplares_disponiveis": -1}}
    )
    
    return jsonify(serialize_emprestimo(emprestimo_doc)), 201

@emprestimo_bp.route("/<string:id>/devolver", methods=["POST"])
@requer_autenticacao("admin")
def registrar_devolucao(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de empréstimo inválido."}), 400
        
    emprestimo = emprestimos_col.find_one({"_id": obj_id})
    if not emprestimo:
        return jsonify({"error": "Empréstimo não encontrado."}), 404
        
    if emprestimo["data_devolucao_real"] is not None or emprestimo["status"] == "devolvido":
        return jsonify({"error": "Este empréstimo já foi devolvido anteriormente."}), 400
        
    # Registra devolução
    agora = datetime.now(timezone.utc)
    emprestimos_col.update_one(
        {"_id": obj_id},
        {
            "$set": {
                "data_devolucao_real": agora,
                "status": "devolvido"
            }
        }
    )
    
    # Incrementa exemplares disponíveis
    livros_col.update_one(
        {"_id": emprestimo["livro_id"]},
        {"$inc": {"exemplares_disponiveis": 1}}
    )
    
    emprestimo_atualizado = emprestimos_col.find_one({"_id": obj_id})
    return jsonify(serialize_emprestimo(emprestimo_atualizado)), 200

@emprestimo_bp.route("/abertos", methods=["GET"])
@requer_autenticacao("admin")
def listar_abertos():
    # Empréstimos abertos: ativo ou atrasado (ou seja, data_devolucao_real nula)
    abertos = list(emprestimos_col.find({"data_devolucao_real": None}))
    return jsonify([serialize_emprestimo(e) for e in abertos]), 200

@emprestimo_bp.route("/atrasados", methods=["GET"])
@requer_autenticacao("admin")
def listar_atrasados():
    agora = datetime.now(timezone.utc)
    
    # 1. Atualiza o status para "atrasado" se a data prevista passou e ainda não foi devolvido
    query_atualizar = {
        "status": "ativo",
        "data_devolucao_real": None,
        "data_devolucao_prevista": {"$lt": agora}
    }
    emprestimos_col.update_many(query_atualizar, {"$set": {"status": "atrasado"}})
    
    # 2. Retorna todos os atrasados
    atrasados = list(emprestimos_col.find({"status": "atrasado"}))
    return jsonify([serialize_emprestimo(e) for e in atrasados]), 200

@emprestimo_bp.route("/meus", methods=["GET"])
@requer_autenticacao()
def listar_meus_emprestimos():
    # Retorna o histórico do usuário logado
    usuario_id = ObjectId(g.usuario_id)
    meus = list(emprestimos_col.find({"usuario_id": usuario_id}))
    return jsonify([serialize_emprestimo(e) for e in meus]), 200

@emprestimo_bp.route("/usuario/<string:usuario_id>", methods=["GET"])
@requer_autenticacao("admin")
def listar_emprestimos_usuario(usuario_id):
    try:
        obj_usuario_id = ObjectId(usuario_id)
    except InvalidId:
        return jsonify({"error": "ID de usuário inválido."}), 400
        
    emprestimos = list(emprestimos_col.find({"usuario_id": obj_usuario_id}))
    return jsonify([serialize_emprestimo(e) for e in emprestimos]), 200

@emprestimo_bp.route("/<string:id>", methods=["GET"])
@requer_autenticacao()
def detalhar_emprestimo(id):
    try:
        obj_id = ObjectId(id)
    except InvalidId:
        return jsonify({"error": "ID de empréstimo inválido."}), 400
        
    emprestimo = emprestimos_col.find_one({"_id": obj_id})
    if not emprestimo:
        return jsonify({"error": "Empréstimo não encontrado."}), 404
        
    # Se o perfil do usuário logado for "leitor", ele só pode detalhar seus próprios empréstimos
    if g.perfil != "admin" and str(emprestimo["usuario_id"]) != g.usuario_id:
        return jsonify({"error": "Acesso negado. Você só pode visualizar seus próprios empréstimos."}), 403
        
    return jsonify(serialize_emprestimo(emprestimo)), 200
