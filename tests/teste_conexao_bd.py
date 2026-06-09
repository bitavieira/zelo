import sys
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Carrega as variáveis de ambiente
load_dotenv()

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
mongo_db = os.getenv("MONGO_DB", "zelo")

print(f"Tentando estabelecer conexão em: {mongo_uri}")
print(f"Banco de dados alvo: {mongo_db}")

try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
    # Ping o servidor
    client.admin.command("ping")
    print("✔ Conexão com MongoDB: OK")
    
    # Mostra bancos de dados disponíveis
    dbs = client.list_database_names()
    print("Bancos de dados disponíveis no servidor:")
    for d in dbs:
        print(f" - {d}")
        
except Exception as e:
    print(f"❌ Erro de conexão com o MongoDB: {e}")
    sys.exit(1)
