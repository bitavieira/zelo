import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB = os.getenv("MONGO_DB", "zelo")
    SECRET_KEY = os.getenv("SECRET_KEY", "chave_secreta_padrao_zelo_biblioteca_123456")
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
