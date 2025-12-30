# setup.py - Script de configuração inicial
import sqlite3
import bcrypt

def setup_database():
    """Configuração inicial do banco de dados"""
    conn = sqlite3.connect('imobiliaria_angola.db')
    cursor = conn.cursor()
    
    # Criar tabelas (se não existirem)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'imobiliaria', 'usuario')),
            status TEXT DEFAULT 'ativo',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            preferencias TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imoveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            tipo TEXT NOT NULL,
            provincia TEXT NOT NULL,
            municipio TEXT NOT NULL,
            bairro TEXT,
            preco REAL NOT NULL,
            quartos INTEGER,
            banheiros INTEGER,
            area REAL,
            proprietario_id INTEGER,
            status TEXT DEFAULT 'pendente',
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fotos TEXT,
            FOREIGN KEY (proprietario_id) REFERENCES usuarios (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            imovel_id INTEGER,
            tipo TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (imovel_id) REFERENCES imoveis (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favoritos (
            usuario_id INTEGER,
            imovel_id INTEGER,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (usuario_id, imovel_id)
        )
    ''')
    
    # Criar admin padrão
    cursor.execute("SELECT * FROM usuarios WHERE email = 'admin@imobiliaria.ao'")
    if not cursor.fetchone():
        senha_hash = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        cursor.execute('''
            INSERT INTO usuarios (nome, email, senha_hash, role, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('Administrador', 'admin@imobiliaria.ao', senha_hash, 'admin', 'ativo'))
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados configurado com sucesso!")
    print("👑 Admin padrão criado:")
    print("   Email: admin@imobiliaria.ao")
    print("   Senha: admin123")

if __name__ == "__main__":
    setup_database()