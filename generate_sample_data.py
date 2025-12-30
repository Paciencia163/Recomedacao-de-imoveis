# generate_sample_data.py - Script para gerar dados de exemplo
import sqlite3
import random
from faker import Faker
import bcrypt

fake = Faker('pt_BR')

# Províncias de Angola
provincias_angola = [
    'Luanda', 'Benguela', 'Huíla', 'Cabinda', 'Huambo',
    'Cunene', 'Malanje', 'Uíge', 'Zaire', 'Lunda Norte',
    'Lunda Sul', 'Moxico', 'Bié', 'Cuando Cubango', 'Cuanza Norte',
    'Cuanza Sul', 'Namibe', 'Bengo'
]

# Municípios por província (exemplo)
municipios_por_provincia = {
    'Luanda': ['Belas', 'Cazenga', 'Ingombota', 'Kilamba Kiaxi', 'Maianga', 'Rangel', 'Samba', 'Viana'],
    'Benguela': ['Benguela', 'Baía Farta', 'Catumbela', 'Lobito', 'Bocoio'],
    'Huíla': ['Lubango', 'Humpata', 'Quilengues', 'Caconda', 'Caluquembe']
}

# Tipos de imóveis
tipos_imovel = ['casa', 'apartamento', 'terreno', 'comercial']

def create_sample_data():
    conn = sqlite3.connect('imobiliaria_angola.db')
    cursor = conn.cursor()
    
    # Limpar tabelas existentes
    cursor.execute("DELETE FROM interacoes")
    cursor.execute("DELETE FROM favoritos")
    cursor.execute("DELETE FROM imoveis")
    cursor.execute("DELETE FROM usuarios WHERE email != 'admin@imobiliaria.ao'")
    
    # Criar usuários de exemplo
    users = []
    
    # Admin já existe
    
    # 5 imobiliárias
    for i in range(5):
        nome = f"Imobiliária {fake.company()}"
        email = f"imobiliaria{i}@example.com"
        senha_hash = bcrypt.hashpw('123456'.encode(), bcrypt.gensalt()).decode()
        users.append((nome, email, senha_hash, 'imobiliaria'))
    
    # 20 usuários comuns
    for i in range(20):
        nome = fake.name()
        email = fake.email()
        senha_hash = bcrypt.hashpw('123456'.encode(), bcrypt.gensalt()).decode()
        users.append((nome, email, senha_hash, 'usuario'))
    
    cursor.executemany('''
        INSERT INTO usuarios (nome, email, senha_hash, role, status)
        VALUES (?, ?, ?, ?, 'ativo')
    ''', users)
    
    # Obter IDs dos usuários criados
    cursor.execute("SELECT id, role FROM usuarios")
    usuarios = cursor.fetchall()
    
    imobiliaria_ids = [u[0] for u in usuarios if u[1] == 'imobiliaria']
    usuario_ids = [u[0] for u in usuarios if u[1] == 'usuario']
    
    # Criar imóveis de exemplo
    imoveis = []
    for i in range(50):
        proprietario_id = random.choice(imobiliaria_ids)
        tipo = random.choice(tipos_imovel)
        provincia = random.choice(provincias_angola)
        
        if provincia in municipios_por_provincia:
            municipio = random.choice(municipios_por_provincia[provincia])
        else:
            municipio = fake.city()
        
        imoveis.append((
            f"{tipo.capitalize()} em {municipio}",
            fake.text(max_nb_chars=200),
            tipo,
            provincia,
            municipio,
            fake.city_suffix(),
            random.randint(5000000, 500000000),  # preço
            random.randint(1, 6),  # quartos
            random.randint(1, 4),  # banheiros
            random.randint(50, 500),  # área
            proprietario_id,
            random.choice(['aprovado', 'aprovado', 'aprovado', 'pendente'])  # status
        ))
    
    cursor.executemany('''
        INSERT INTO imoveis 
        (titulo, descricao, tipo, provincia, municipio, bairro, 
         preco, quartos, banheiros, area, proprietario_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', imoveis)
    
    # Obter IDs dos imóveis criados
    cursor.execute("SELECT id FROM imoveis WHERE status = 'aprovado'")
    imoveis_aprovados = [row[0] for row in cursor.fetchall()]
    
    # Criar interações de exemplo
    interacoes = []
    for user_id in usuario_ids:
        # Cada usuário interage com 3-10 imóveis
        for imovel_id in random.sample(imoveis_aprovados, random.randint(3, 10)):
            interacoes.append((
                user_id,
                imovel_id,
                random.choice(['view', 'view', 'view', 'click', 'contact'])
            ))
    
    cursor.executemany('''
        INSERT INTO interacoes (usuario_id, imovel_id, tipo)
        VALUES (?, ?, ?)
    ''', interacoes)
    
    # Criar favoritos de exemplo
    favoritos = []
    for user_id in usuario_ids:
        # Cada usuário favorita 1-5 imóveis
        for imovel_id in random.sample(imoveis_aprovados, random.randint(1, 5)):
            favoritos.append((user_id, imovel_id))
    
    cursor.executemany('''
        INSERT INTO favoritos (usuario_id, imovel_id)
        VALUES (?, ?)
    ''', favoritos)
    
    conn.commit()
    conn.close()
    
    print("✅ Dados de exemplo criados com sucesso!")
    print(f"👤 {len(users)} usuários criados")
    print(f"🏠 {len(imoveis)} imóveis criados")
    print(f"📊 {len(interacoes)} interações criadas")
    print(f"❤️ {len(favoritos)} favoritos criados")

if __name__ == "__main__":
    create_sample_data()