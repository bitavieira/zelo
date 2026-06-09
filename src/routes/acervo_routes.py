from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from src.database import acervos_col
from src.models.acervo import criar_acervo_doc, validar_acervo_payload
from src.middlewares.auth_middleware import requer_autenticacao

acervo_bp = Blueprint("acervos", __name__, url_prefix="/api/acervos")

def serialize_acervo(acervo):
    return {
        "id": str(acervo["_id"]),
        "nome": acervo["nome"],
        "descricao": acervo.get("descricao", ""),
        "visibilidade": acervo.get("visibilidade", "publico"),
        "proprietario_id": str(acervo["proprietario_id"]),
        "membros": [
            {
                "usuario_id": str(m["usuario_id"]),
                "papel": m["papel"]
            }
            for m in acervo.get("membros", [])
        ],
        "configuracoes": acervo.get("configuracoes", {}),
        "criado_em": acervo.get("criado_em")
    }

@acervo_bp.route("/", methods=["POST"])
@requer_autenticacao()
def criar_acervo():
    data = request.get_json() or {}
    
    # Valida payload
    dados_validados, erro = validar_acervo_payload(data, is_update=False)
    if erro:
        return jsonify({"error": erro}), 400
        
    # Extrai dados adicionais
    proprietario_id = ObjectId(g.usuario_id)
    
    # Prepara documento
    acervo_doc = criar_acervo_doc(
        nome=dados_validados["nome"],
        proprietario_id=proprietario_id,
        descricao=dados_validados.get("descricao"),
        visibilidade=dados_validados.get("visibilidade", "publico"),
        membros=dados_validados.get("membros"),
        configuracoes=dados_validados.get("configuracoes")
    )
    
    acervos_col.insert_one(acervo_doc)
    return jsonify(serialize_acervo(acervo_doc)), 201

@acervo_bp.route("/", methods=["GET"])
@requer_autenticacao()
def listar_acervos():
    usuario_id = ObjectId(g.usuario_id)
    
    # Busca acervos do usuário logado (proprietário ou membro)
    query = {
        "$or": [
            {"proprietario_id": usuario_id},
            {"membros.usuario_id": usuario_id}
        ]
    }
    
    acervos = list(acervos_col.find(query))
    return jsonify([serialize_acervo(a) for a in acervos]), 200
