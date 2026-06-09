import os
from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from bson import ObjectId
from datetime import datetime

from src.config import Config
from src.database import setup_db
from src.routes.auth_routes import auth_bp
from src.routes.livro_routes import livro_bp
from src.routes.usuario_routes import usuario_bp
from src.routes.emprestimo_routes import emprestimo_bp
from src.routes.page_routes import page_bp

class CustomJSONProvider(DefaultJSONProvider):
    """
    Provedor JSON customizado para serializar automaticamente ObjectId do MongoDB
    e objetos datetime do Python em respostas HTTP JSON do Flask.
    """
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def create_app():
    # Define a pasta de templates apontando para src/presentation/templates
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "presentation", "templates"))
    app = Flask(__name__, template_folder=template_dir)
    app.config.from_object(Config)
    
    # Define o provedor JSON customizado
    app.json = CustomJSONProvider(app)
    
    # Inicializa banco de dados, cria índices e semeia o administrador padrão
    setup_db()
    
    # Registra Blueprints das Rotas
    app.register_blueprint(auth_bp)
    app.register_blueprint(livro_bp)
    app.register_blueprint(usuario_bp)
    app.register_blueprint(emprestimo_bp)
    app.register_blueprint(page_bp)

    # Rota de status para a API
    @app.route("/api/status", methods=["GET"])
    def api_status():
        return jsonify({
            "nome": "Sistema de Biblioteca — API REST Backend",
            "status": "online",
            "documentacao": "Consulte o README do projeto para a lista completa de endpoints e regras."
        }), 200

    @app.errorhandler(404)
    def page_not_found(e):
        return jsonify({"error": "Recurso não encontrado."}), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"error": "Erro interno do servidor."}), 500
        
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
