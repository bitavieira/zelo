import os
import secrets
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId
from werkzeug.security import generate_password_hash, check_password_hash
import hmac, hashlib, base64, json

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")

MONGO_URI   = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
SECRET_KEY  = os.environ.get("SECRET_KEY", secrets.token_hex(32))
TOKEN_HOURS = int(os.environ.get("TOKEN_HOURS", 72))

# ─────────────────────────────────────────
# BANCO DE DADOS  (padrão conexao_mongo.py)
# ─────────────────────────────────────────
client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("✔ Conexão com MongoDB: OK")
    print("Bancos disponíveis:", client.list_database_names())
except Exception as e:
    print("✘ Erro de conexão:", e)

db = client["zelo-tests"]

usuarios_col    = db["usuarios"]
acervos_col     = db["acervos"]
obras_col       = db["obras"]
emprestimos_col = db["emprestimos"]

# Índice único no email
usuarios_col.create_index("email", unique=True)


# ─────────────────────────────────────────
# JWT SIMPLES (sem dependência extra)
# ─────────────────────────────────────────
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)

def gerar_token(user_id: str) -> str:
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    exp     = (datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)).timestamp()
    payload = _b64url(json.dumps({"sub": user_id, "exp": exp}).encode())
    sig     = _b64url(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"

def verificar_token(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        expected = _b64url(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not secrets.compare_digest(sig, expected):
            return None
        data = json.loads(_b64url_decode(payload))
        if data.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return data.get("sub")
    except Exception:
        return None


# ─────────────────────────────────────────
# DECORADOR DE AUTENTICAÇÃO
# ─────────────────────────────────────────
def requer_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        user_id = verificar_token(token)
        if not user_id:
            return jsonify({"erro": "Não autorizado"}), 401
        try:
            request.user_id = str(user_id)
            request.usuario = usuarios_col.find_one({"_id": ObjectId(user_id)})
        except (InvalidId, Exception):
            return jsonify({"erro": "Token inválido"}), 401
        if not request.usuario:
            return jsonify({"erro": "Usuário não encontrado"}), 401
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def serializar(doc: dict) -> dict:
    """Converte ObjectId para string recursivamente."""
    if doc is None:
        return {}
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [serializar(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        elif isinstance(v, dict):
            result[k] = serializar(v)
        else:
            result[k] = v
    return result


# ─────────────────────────────────────────
# FRONTEND (arquivos estáticos)
# ─────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)


# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────
@app.route("/auth/register", methods=["POST"])
def registrar():
    data = request.get_json(silent=True) or {}
    nome  = (data.get("nome") or "").strip()
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not nome or not email or not senha:
        return jsonify({"erro": "Nome, e-mail e senha são obrigatórios"}), 400
    if len(senha) < 6:
        return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres"}), 400

    novo = {
        "nome":        nome,
        "email":       email,
        "senha_hash":  generate_password_hash(senha),
        "criado_em":   datetime.now(timezone.utc)
    }
    try:
        result = usuarios_col.insert_one(novo)
    except DuplicateKeyError:
        return jsonify({"erro": "E-mail já cadastrado"}), 409

    user_id = str(result.inserted_id)
    token   = gerar_token(user_id)
    return jsonify({
        "token":   token,
        "usuario": {"_id": user_id, "nome": nome, "email": email}
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not email or not senha:
        return jsonify({"erro": "E-mail e senha são obrigatórios"}), 400

    usuario = usuarios_col.find_one({"email": email})
    if not usuario or not check_password_hash(usuario["senha_hash"], senha):
        return jsonify({"erro": "E-mail ou senha incorretos"}), 401

    user_id = str(usuario["_id"])
    token   = gerar_token(user_id)
    return jsonify({
        "token":   token,
        "usuario": {"_id": user_id, "nome": usuario["nome"], "email": usuario["email"]}
    }), 200


# ─────────────────────────────────────────
# ACERVOS
# ─────────────────────────────────────────
@app.route("/acervos", methods=["GET"])
@requer_auth
def listar_acervos():
    user_id = request.user_id
    # Acervos do usuário + acervos onde é membro
    query = {
        "$or": [
            {"proprietario_id": user_id},
            {"membros.usuario_id": user_id}
        ]
    }
    acervos = [serializar(a) for a in acervos_col.find(query)]
    return jsonify({"acervos": acervos}), 200


@app.route("/acervos", methods=["POST"])
@requer_auth
def criar_acervo():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()

    if not nome:
        return jsonify({"erro": "O nome do acervo é obrigatório"}), 400

    visibilidade = data.get("visibilidade", "publico")
    if visibilidade not in ("publico", "privado"):
        visibilidade = "publico"

    novo = {
        "nome":                nome,
        "descricao":           (data.get("descricao") or "").strip(),
        "visibilidade":        visibilidade,
        "categoria":           data.get("categoria"),
        "prazo_padrao":        int(data.get("prazo_padrao") or 14),
        "max_por_emprestimo":  int(data.get("max_por_emprestimo") or 3),
        "proprietario_id":     request.user_id,
        "membros":             data.get("membros", []),
        "criado_em":           datetime.now(timezone.utc)
    }

    result  = acervos_col.insert_one(novo)
    novo["_id"] = result.inserted_id
    return jsonify({"acervo": serializar(novo)}), 201


@app.route("/acervos/<acervo_id>", methods=["GET"])
@requer_auth
def obter_acervo(acervo_id):
    try:
        oid = ObjectId(acervo_id)
    except InvalidId:
        return jsonify({"erro": "ID inválido"}), 400

    acervo = acervos_col.find_one({"_id": oid})
    if not acervo:
        return jsonify({"erro": "Acervo não encontrado"}), 404

    # Verificar acesso
    uid = request.user_id
    eh_prop   = acervo.get("proprietario_id") == uid
    eh_membro = any(m.get("usuario_id") == uid for m in acervo.get("membros", []))
    eh_pub    = acervo.get("visibilidade") == "publico"

    if not (eh_prop or eh_membro or eh_pub):
        return jsonify({"erro": "Acesso negado"}), 403

    obras = [serializar(o) for o in obras_col.find({"acervo_id": acervo_id})]
    return jsonify({"acervo": serializar(acervo), "obras": obras}), 200


@app.route("/acervos/<acervo_id>", methods=["PUT"])
@requer_auth
def editar_acervo(acervo_id):
    try:
        oid = ObjectId(acervo_id)
    except InvalidId:
        return jsonify({"erro": "ID inválido"}), 400

    acervo = acervos_col.find_one({"_id": oid})
    if not acervo:
        return jsonify({"erro": "Acervo não encontrado"}), 404
    if acervo.get("proprietario_id") != request.user_id:
        return jsonify({"erro": "Apenas o proprietário pode editar"}), 403

    data = request.get_json(silent=True) or {}
    campos = {}
    for campo in ("nome", "descricao", "visibilidade", "categoria", "prazo_padrao", "max_por_emprestimo", "membros"):
        if campo in data:
            campos[campo] = data[campo]

    acervos_col.update_one({"_id": oid}, {"$set": campos})
    acervo.update(campos)
    return jsonify({"acervo": serializar(acervo)}), 200


@app.route("/acervos/<acervo_id>", methods=["DELETE"])
@requer_auth
def deletar_acervo(acervo_id):
    try:
        oid = ObjectId(acervo_id)
    except InvalidId:
        return jsonify({"erro": "ID inválido"}), 400

    acervo = acervos_col.find_one({"_id": oid})
    if not acervo:
        return jsonify({"erro": "Acervo não encontrado"}), 404
    if acervo.get("proprietario_id") != request.user_id:
        return jsonify({"erro": "Apenas o proprietário pode excluir"}), 403

    acervos_col.delete_one({"_id": oid})
    obras_col.delete_many({"acervo_id": acervo_id})
    return jsonify({"mensagem": "Acervo excluído com sucesso"}), 200


# ─────────────────────────────────────────
# OBRAS (livros dentro de um acervo)
# ─────────────────────────────────────────
@app.route("/acervos/<acervo_id>/obras", methods=["POST"])
@requer_auth
def adicionar_obra(acervo_id):
    data = request.get_json(silent=True) or {}
    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"erro": "Título é obrigatório"}), 400

    nova = {
        "acervo_id": acervo_id,
        "titulo":    titulo,
        "autores":   data.get("autores", []),
        "generos":   data.get("generos", []),
        "exemplares": [],
        "criado_em": datetime.now(timezone.utc)
    }
    result = obras_col.insert_one(nova)
    nova["_id"] = result.inserted_id
    return jsonify({"obra": serializar(nova)}), 201


# ─────────────────────────────────────────
# EMPRÉSTIMOS
# ─────────────────────────────────────────
@app.route("/emprestimos", methods=["GET"])
@requer_auth
def listar_emprestimos():
    acervo_ids = [
        str(a["_id"]) for a in acervos_col.find({"proprietario_id": request.user_id})
    ]
    emprestimos = [serializar(e) for e in emprestimos_col.find({"acervo_id": {"$in": acervo_ids}})]
    return jsonify({"emprestimos": emprestimos}), 200


@app.route("/emprestimos", methods=["POST"])
@requer_auth
def registrar_emprestimo():
    data = request.get_json(silent=True) or {}
    campos_req = ("acervo_id", "obra_id", "exemplar_id", "usuario_id")
    for c in campos_req:
        if not data.get(c):
            return jsonify({"erro": f"Campo '{c}' é obrigatório"}), 400

    novo = {
        "acervo_id":        data["acervo_id"],
        "obra_id":          data["obra_id"],
        "exemplar_id":      data["exemplar_id"],
        "usuario_id":       data["usuario_id"],
        "snapshot":         data.get("snapshot", {}),
        "data_emprestimo":  datetime.now(timezone.utc),
        "data_devolucao":   data.get("data_devolucao"),
        "status":           "ativo",
        "criado_em":        datetime.now(timezone.utc)
    }
    result = emprestimos_col.insert_one(novo)
    # Atualizar status do exemplar
    obras_col.update_one(
        {"_id": ObjectId(data["obra_id"]), "exemplares._id": ObjectId(data["exemplar_id"])},
        {"$set": {"exemplares.$.status": "emprestado"}}
    )
    novo["_id"] = result.inserted_id
    return jsonify({"emprestimo": serializar(novo)}), 201


@app.route("/emprestimos/<emp_id>/devolver", methods=["POST"])
@requer_auth
def registrar_devolucao(emp_id):
    try:
        oid = ObjectId(emp_id)
    except InvalidId:
        return jsonify({"erro": "ID inválido"}), 400

    emp = emprestimos_col.find_one({"_id": oid})
    if not emp:
        return jsonify({"erro": "Empréstimo não encontrado"}), 404

    emprestimos_col.update_one({"_id": oid}, {
        "$set": {"status": "devolvido", "data_devolucao_real": datetime.now(timezone.utc)}
    })
    obras_col.update_one(
        {"_id": ObjectId(emp["obra_id"]), "exemplares._id": ObjectId(emp["exemplar_id"])},
        {"$set": {"exemplares.$.status": "disponivel"}}
    )
    return jsonify({"mensagem": "Devolução registrada com sucesso"}), 200


# ─────────────────────────────────────────
# BUSCA PÚBLICA
# ─────────────────────────────────────────
@app.route("/busca", methods=["GET"])
def busca_publica():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"resultados": []}), 200

    regex = {"$regex": q, "$options": "i"}
    obras = obras_col.find({
        "$and": [
            {"$or": [{"titulo": regex}, {"autores": regex}, {"generos": regex}]},
        ]
    }).limit(20)

    resultados = []
    for o in obras:
        acervo = acervos_col.find_one({"_id": ObjectId(o["acervo_id"])}) if o.get("acervo_id") else None
        if acervo and acervo.get("visibilidade") == "publico":
            resultados.append(serializar(o))

    return jsonify({"resultados": resultados}), 200


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
