import functools
from flask import request, jsonify, g
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from bson import ObjectId
from src.config import Config
from src.database import usuarios_col

serializer = URLSafeTimedSerializer(Config.SECRET_KEY)

def gerar_token(usuario_id, perfil):
    """
    Gera um token assinado com validade configurável (verificada na decodificação).
    """
    return serializer.dumps({"usuario_id": str(usuario_id), "perfil": perfil})

def requer_autenticacao(perfil_requerido=None):
    """
    Decorator para proteger rotas Flask com autenticação baseada em Bearer Token.
    Se perfil_requerido for 'admin', apenas usuários com perfil 'admin' são autorizados.
    Se perfil_requerido for None, qualquer usuário autenticado e ativo ('leitor' ou 'admin') é autorizado.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return jsonify({"error": "Token de autenticação não fornecido."}), 401
                
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return jsonify({"error": "Formato de token inválido. Use 'Bearer <token>'."}), 401
                
            token = parts[1]
            try:
                # Token expira em 24 horas (86400 segundos)
                payload = serializer.loads(token, max_age=86400)
            except SignatureExpired:
                return jsonify({"error": "Token expirado. Por favor, faça login novamente."}), 401
            except BadSignature:
                return jsonify({"error": "Token inválido ou corrompido."}), 401
                
            usuario_id = payload.get("usuario_id")
            perfil_usuario = payload.get("perfil")
            
            if not usuario_id:
                return jsonify({"error": "Payload do token inválido."}), 401
                
            # Verifica se o usuário correspondente existe e está ativo no banco
            try:
                usuario = usuarios_col.find_one({"_id": ObjectId(usuario_id), "ativo": True})
                if not usuario:
                    return jsonify({"error": "Usuário inativo ou não cadastrado."}), 401
            except Exception:
                return jsonify({"error": "ID de usuário inválido."}), 401
                
            # Validação do perfil
            if perfil_requerido == "admin" and perfil_usuario != "admin":
                return jsonify({"error": "Acesso negado. Perfil de administrador requerido."}), 403
                
            # Anexa as variáveis úteis ao contexto global do Flask
            g.usuario_id = usuario_id
            g.perfil = perfil_usuario
            g.usuario = usuario
            
            return f(*args, **kwargs)
        return decorated
    return decorator
