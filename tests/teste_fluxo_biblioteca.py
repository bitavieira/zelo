import sys
import unittest
from datetime import datetime, timedelta, timezone

# 1. Patch do MongoClient usando mongomock antes de importar o app
import pymongo
import mongomock
pymongo.MongoClient = mongomock.MongoClient

from bson import ObjectId
from src.app import create_app
from src.database import db, usuarios_col, livros_col, emprestimos_col

class TestBibliotecaREST(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Cria a aplicação Flask configurada
        cls.app = create_app()
        cls.client = cls.app.test_client()
        
    def setUp(self):
        # Limpa as coleções fictícias antes de cada teste
        usuarios_col.delete_many({})
        livros_col.delete_many({})
        emprestimos_col.delete_many({})
        
        # Roda o setup_db novamente para semear o admin
        from src.database import setup_db
        setup_db()

    def get_admin_token(self):
        # Efetua login para obter token de admin
        res = self.client.post("/api/auth/login", json={
            "email": "admin@bib.com",
            "senha": "123456"
        })
        return res.json["token"]

    def test_admin_seeding_and_login(self):
        # Verifica se admin foi semeado
        admin = usuarios_col.find_one({"email": "admin@bib.com"})
        self.assertIsNotNone(admin)
        self.assertEqual(admin["perfil"], "admin")
        
        # Testa login de sucesso
        res = self.client.post("/api/auth/login", json={
            "email": "admin@bib.com",
            "senha": "123456"
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json)
        self.assertEqual(res.json["usuario"]["email"], "admin@bib.com")
        self.assertEqual(res.json["usuario"]["perfil"], "admin")

        # Testa login com credenciais incorretas
        res = self.client.post("/api/auth/login", json={
            "email": "admin@bib.com",
            "senha": "senha-errada"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("error", res.json)

    def test_auth_middleware_protections(self):
        # Tenta acessar rota restrita sem token
        res = self.client.get("/api/usuarios/")
        self.assertEqual(res.status_code, 401)
        self.assertIn("error", res.json)

        # Tenta acessar rota restrita com token inválido
        res = self.client.get("/api/usuarios/", headers={"Authorization": "Bearer token_falso"})
        self.assertEqual(res.status_code, 401)

    def test_usuario_crud_by_admin(self):
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Cadastra Usuário Leitor
        res = self.client.post("/api/usuarios/", json={
            "nome": "Leitor Teste",
            "email": "leitor@teste.com",
            "senha": "senha123",
            "perfil": "leitor"
        }, headers=headers)
        self.assertEqual(res.status_code, 201)
        usuario_id = res.json["id"]
        self.assertEqual(res.json["nome"], "Leitor Teste")
        self.assertEqual(res.json["perfil"], "leitor")

        # Verifica no banco
        usuario_db = usuarios_col.find_one({"_id": ObjectId(usuario_id)})
        self.assertIsNotNone(usuario_db)
        self.assertEqual(usuario_db["nome"], "Leitor Teste")

        # 2. Lista Usuários
        res = self.client.get("/api/usuarios/", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.json) >= 2) # Admin + Leitor cadastrado

        # 3. Detalha Usuário
        res = self.client.get(f"/api/usuarios/{usuario_id}", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["email"], "leitor@teste.com")

        # 4. Atualiza Usuário
        res = self.client.put(f"/api/usuarios/{usuario_id}", json={
            "nome": "Leitor Teste Atualizado"
        }, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["nome"], "Leitor Teste Atualizado")

        # 5. Desativa Usuário (DELETE)
        res = self.client.delete(f"/api/usuarios/{usuario_id}", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["message"], "Usuário desativado com sucesso.")

        # Verifica desativação no banco
        usuario_desativado = usuarios_col.find_one({"_id": ObjectId(usuario_id)})
        self.assertFalse(usuario_desativado["ativo"])

    def test_livro_crud(self):
        token_admin = self.get_admin_token()
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # 1. Cadastra Livro
        res = self.client.post("/api/livros/", json={
            "titulo": "O Senhor dos Anéis",
            "autor": "J.R.R. Tolkien",
            "isbn": "978-8533613379",
            "quantidade_exemplares": 3,
            "editora": "Martins Fontes",
            "ano_publicacao": 2001,
            "genero": "Fantasia"
        }, headers=headers_admin)
        self.assertEqual(res.status_code, 201)
        livro_id = res.json["id"]
        self.assertEqual(res.json["titulo"], "O Senhor dos Anéis")
        self.assertEqual(res.json["exemplares_disponiveis"], 3)

        # 2. Lista Livros (Leitor+)
        res = self.client.get("/api/livros/", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)

        # 3. Busca Livros por termo (busca textual simulada por regex)
        res = self.client.get("/api/livros/buscar?q=Senhor", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        
        res = self.client.get("/api/livros/buscar?q=Inexistente", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 0)

        # 4. Atualiza Livro (quantidade de exemplares)
        res = self.client.put(f"/api/livros/{livro_id}", json={
            "quantidade_exemplares": 5
        }, headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["quantidade_exemplares"], 5)
        self.assertEqual(res.json["exemplares_disponiveis"], 5)

        # 5. Remove Livro (Soft Delete)
        res = self.client.delete(f"/api/livros/{livro_id}", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        
        # Verifica se está inativo
        livro_db = livros_col.find_one({"_id": ObjectId(livro_id)})
        self.assertFalse(livro_db["ativo"])

    def test_emprestimos_fluxo(self):
        token_admin = self.get_admin_token()
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # Cadastra um leitor
        res = self.client.post("/api/usuarios/", json={
            "nome": "Maria Silva",
            "email": "maria@silva.com",
            "senha": "senha123",
            "perfil": "leitor"
        }, headers=headers_admin)
        usuario_id = res.json["id"]

        # Cadastra um livro
        res = self.client.post("/api/livros/", json={
            "titulo": "Dom Casmurro",
            "autor": "Machado de Assis",
            "isbn": "978-8542215861",
            "quantidade_exemplares": 1
        }, headers=headers_admin)
        livro_id = res.json["id"]

        # 1. Registra empréstimo
        res = self.client.post("/api/emprestimos/", json={
            "livro_id": livro_id,
            "usuario_id": usuario_id
        }, headers=headers_admin)
        self.assertEqual(res.status_code, 201)
        emprestimo_id = res.json["id"]
        self.assertEqual(res.json["status"], "ativo")

        # Verifica exemplares_disponiveis decrementado para 0
        livro_db = livros_col.find_one({"_id": ObjectId(livro_id)})
        self.assertEqual(livro_db["exemplares_disponiveis"], 0)

        # 2. Tenta fazer outro empréstimo do mesmo livro (sem exemplares disponíveis)
        res = self.client.post("/api/emprestimos/", json={
            "livro_id": livro_id,
            "usuario_id": usuario_id
        }, headers=headers_admin)
        self.assertEqual(res.status_code, 400) # Erro, sem exemplares disponíveis

        # 3. Lista abertos
        res = self.client.get("/api/emprestimos/abertos", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]["id"], emprestimo_id)

        # 4. Histórico do leitor logado (obter token da Maria)
        res_login = self.client.post("/api/auth/login", json={
            "email": "maria@silva.com",
            "senha": "senha123"
        })
        token_maria = res_login.json["token"]
        headers_maria = {"Authorization": f"Bearer {token_maria}"}

        res = self.client.get("/api/emprestimos/meus", headers=headers_maria)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]["id"], emprestimo_id)
        self.assertEqual(res.json[0]["livro"]["titulo"], "Dom Casmurro")

        # 5. Registra devolução
        res = self.client.post(f"/api/emprestimos/{emprestimo_id}/devolver", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["status"], "devolvido")
        self.assertIsNotNone(res.json["data_devolucao_real"])

        # Verifica exemplares_disponiveis incrementado para 1
        livro_db = livros_col.find_one({"_id": ObjectId(livro_id)})
        self.assertEqual(livro_db["exemplares_disponiveis"], 1)

    def test_emprestimos_atrasados(self):
        token_admin = self.get_admin_token()
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # Cria usuário e livro
        res_user = self.client.post("/api/usuarios/", json={
            "nome": "Atrasado Silva",
            "email": "atrasado@silva.com",
            "senha": "senha123",
            "perfil": "leitor"
        }, headers=headers_admin)
        
        res_book = self.client.post("/api/livros/", json={
            "titulo": "Livro Atrasado",
            "autor": "Autor Atrasado",
            "isbn": "000-0000000000",
            "quantidade_exemplares": 1
        }, headers=headers_admin)

        user_id = res_user.json["id"]
        book_id = res_book.json["id"]

        # Insere empréstimo com data_devolucao_prevista no passado manualmente no banco
        passado = datetime.now(timezone.utc) - timedelta(days=2)
        emprestimo_doc = {
            "livro_id": ObjectId(book_id),
            "usuario_id": ObjectId(user_id),
            "data_emprestimo": passado - timedelta(days=14),
            "data_devolucao_prevista": passado,
            "data_devolucao_real": None,
            "status": "ativo"
        }
        emprestimos_col.insert_one(emprestimo_doc)

        # Chama endpoint de atrasados
        res = self.client.get("/api/emprestimos/atrasados", headers=headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0]["status"], "atrasado")
        self.assertEqual(res.json[0]["livro"]["titulo"], "Livro Atrasado")

    def test_acervo_crud(self):
        # 1. Cria usuário leitor e obtém token
        res_user = self.client.post("/api/usuarios/", json={
            "nome": "Leitor Acervo",
            "email": "leitor_acervo@teste.com",
            "senha": "senha123",
            "perfil": "leitor"
        }, headers={"Authorization": f"Bearer {self.get_admin_token()}"})
        self.assertEqual(res_user.status_code, 201)
        
        # Faz login do leitor
        res_login = self.client.post("/api/auth/login", json={
            "email": "leitor_acervo@teste.com",
            "senha": "senha123"
        })
        token_leitor = res_login.json["token"]
        headers_leitor = {"Authorization": f"Bearer {token_leitor}"}
        
        # 2. Cria acervo para o leitor
        res = self.client.post("/api/acervos/", json={
            "nome": "Meu Acervo Tematico",
            "descricao": "Um acervo para testes",
            "visibilidade": "publico"
        }, headers=headers_leitor)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json["nome"], "Meu Acervo Tematico")
        self.assertEqual(res.json["descricao"], "Um acervo para testes")
        self.assertEqual(res.json["visibilidade"], "publico")
        
        acervo_id = res.json["id"]
        
        # 3. Lista acervos do leitor
        res_list = self.client.get("/api/acervos/", headers=headers_leitor)
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json), 1)
        self.assertEqual(res_list.json[0]["id"], acervo_id)

if __name__ == "__main__":
    unittest.main()

