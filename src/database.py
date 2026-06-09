import logging
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from werkzeug.security import generate_password_hash
from src.config import Config

# Configurar logging simples
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = MongoClient(Config.MONGO_URI)
db = client[Config.MONGO_DB]

usuarios_col = db["usuarios"]
livros_col = db["livros"]
emprestimos_col = db["emprestimos"]
acervos_col = db["acervos"]


def setup_db():
    try:
        # Testa a conexão
        client.admin.command("ping")
        logger.info("✔ Conexão com MongoDB estabelecida com sucesso.")
        
        # 1. Índices para Coleção de Usuários
        # E-mail único
        usuarios_col.create_index([("email", ASCENDING)], unique=True)
        logger.info("✔ Índice único para 'email' criado na coleção 'usuarios'.")

        # 2. Índices para Coleção de Livros
        # ISBN único
        livros_col.create_index([("isbn", ASCENDING)], unique=True)
        logger.info("✔ Índice único para 'isbn' criado na coleção 'livros'.")
        
        # Índice de texto para buscas por título/autor/isbn
        livros_col.create_index([
            ("titulo", "text"),
            ("autor", "text"),
            ("isbn", "text")
        ], default_language="portuguese")
        logger.info("✔ Índice de busca textual criado na coleção 'livros'.")

        # 3. Seed de administrador padrão se não existir
        admin_email = "admin@bib.com"
        admin_exists = usuarios_col.find_one({"email": admin_email})
        
        if not admin_exists:
            senha_hash = generate_password_hash("123456")
            admin_doc = {
                "nome": "Administrador",
                "email": admin_email,
                "senha_hash": senha_hash,
                "perfil": "admin",
                "ativo": True,
                "criado_em": datetime.now(timezone.utc)
            }
            usuarios_col.insert_one(admin_doc)
            logger.info("✔ Administrador padrão ('admin@bib.com') semeado com sucesso.")
        else:
            logger.info("✔ Administrador padrão já existe no banco de dados.")
            
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        raise e
