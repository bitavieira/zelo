from  pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

mongo_uri= os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)


try:
    client.admin.command("ping")
    print("✔ Conexão com MongoDB: OK")
except Exception as e:
    print(" Erro de conexão:", e)

# TESTE 2: listar bancos (opcional)
print("Bancos disponíveis:")
print(client.list_database_names())

db = client["zelo-tests"]
conexao = db.conexao