# app.py - Arquivo principal da aplicação (VERSÃO CORRIGIDA)
import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import hashlib
import os
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import plotly.express as px
import plotly.graph_objects as go
import json
import bcrypt

# Configuração da página
st.set_page_config(
    page_title="Imobiliária Angola",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== BANCO DE DADOS ====================
class Database:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """Inicializa o banco de dados SQLite"""
        conn = sqlite3.connect('imobiliaria_angola.db')
        cursor = conn.cursor()
        
        # Tabela de usuários
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
        
        # Tabela de imóveis
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
        
        # Tabela de interações
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
        
        # Tabela de favoritos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favoritos (
                usuario_id INTEGER,
                imovel_id INTEGER,
                data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (usuario_id, imovel_id)
            )
        ''')
        
        # Inserir admin padrão se não existir
        cursor.execute("SELECT * FROM usuarios WHERE email = 'admin@imobiliaria.ao'")
        if not cursor.fetchone():
            senha_hash = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
            cursor.execute('''
                INSERT INTO usuarios (nome, email, senha_hash, role, status)
                VALUES (?, ?, ?, ?, ?)
            ''', ('Administrador', 'admin@imobiliaria.ao', senha_hash, 'admin', 'ativo'))
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect('imobiliaria_angola.db')

# ==================== SISTEMA DE AUTENTICAÇÃO ====================
class AuthSystem:
    def __init__(self):
        self.db = Database()
    
    def hash_password(self, password):
        """Gera hash da senha usando bcrypt"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    def verify_password(self, password, hashed):
        """Verifica se a senha corresponde ao hash"""
        return bcrypt.checkpw(password.encode(), hashed.encode())
    
    def register_user(self, nome, email, senha, role='usuario'):
        """Registra novo usuário"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            senha_hash = self.hash_password(senha)
            
            cursor.execute('''
                INSERT INTO usuarios (nome, email, senha_hash, role, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (nome, email, senha_hash, role, 'ativo'))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Erro ao registrar: {str(e)}")
            return False
    
    def login(self, email, senha):
        """Autentica usuário"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, nome, email, senha_hash, role, status, preferencias 
            FROM usuarios WHERE email = ?
        ''', (email,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user and self.verify_password(senha, user[3]):
            if user[5] == 'inativo':
                return None, "Usuário inativo"
            return {
                'id': user[0],
                'nome': user[1],
                'email': user[2],
                'role': user[4],
                'status': user[5],
                'preferencias': user[6]
            }, None
        return None, "Credenciais inválidas"
    
    def update_user(self, user_id, updates):
        """Atualiza informações do usuário"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        for key, value in updates.items():
            if key == 'senha' and value:
                value = self.hash_password(value)
                cursor.execute('UPDATE usuarios SET senha_hash = ? WHERE id = ?', (value, user_id))
            elif key == 'preferencias':
                cursor.execute('UPDATE usuarios SET preferencias = ? WHERE id = ?', (json.dumps(value), user_id))
            elif value:
                cursor.execute(f'UPDATE usuarios SET {key} = ? WHERE id = ?', (value, user_id))
        
        conn.commit()
        conn.close()

# ==================== SISTEMA DE RECOMENDAÇÃO ====================
class RecommendationSystem:
    def __init__(self):
        self.db = Database()
    
    def get_content_based_recommendations(self, user_id, n_recommendations=10):
        """Recomendações baseadas em conteúdo"""
        conn = self.db.get_connection()
        
        # Obter preferências do usuário
        user_df = pd.read_sql_query(
            "SELECT preferencias FROM usuarios WHERE id = ?", 
            conn, params=(user_id,)
        )
        
        # Obter imóveis
        imoveis_df = pd.read_sql_query(
            "SELECT * FROM imoveis WHERE status = 'aprovado'", 
            conn
        )
        
        conn.close()
        
        if imoveis_df.empty:
            return pd.DataFrame()
        
        # Processar preferências do usuário
        if not user_df.empty and user_df['preferencias'].iloc[0]:
            user_prefs = json.loads(user_df['preferencias'].iloc[0])
        else:
            user_prefs = {'tipo': 'casa', 'provincia': 'Luanda', 'preco_max': 50000000}
        
        # Calcular similaridade
        features = ['preco', 'quartos', 'banheiros', 'area']
        imoveis_features = imoveis_df[features].fillna(0)
        
        # Normalizar features
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(imoveis_features)
        
        # Criar vetor de preferências do usuário
        user_vector = np.zeros(len(features))
        for i, feature in enumerate(features):
            if feature == 'preco' and 'preco_max' in user_prefs:
                user_vector[i] = user_prefs['preco_max']
            elif feature == 'quartos' and 'quartos_min' in user_prefs:
                user_vector[i] = user_prefs['quartos_min']
        
        user_vector = scaler.transform([user_vector])
        
        # Calcular similaridade
        similarities = cosine_similarity(user_vector, normalized_features)[0]
        imoveis_df['similaridade'] = similarities
        
        # Filtrar por preferências
        if 'tipo' in user_prefs:
            imoveis_df = imoveis_df[imoveis_df['tipo'] == user_prefs['tipo']]
        if 'provincia' in user_prefs:
            imoveis_df = imoveis_df[imoveis_df['provincia'] == user_prefs['provincia']]
        
        return imoveis_df.nlargest(n_recommendations, 'similaridade')
    
    def get_collaborative_recommendations(self, user_id, n_recommendations=10):
        """Recomendações baseadas em colaboração"""
        conn = self.db.get_connection()
        
        # Obter interações dos usuários
        interacoes_df = pd.read_sql_query('''
            SELECT usuario_id, imovel_id, tipo 
            FROM interacoes
        ''', conn)
        
        imoveis_df = pd.read_sql_query(
            "SELECT * FROM imoveis WHERE status = 'aprovado'", 
            conn
        )
        
        conn.close()
        
        if interacoes_df.empty or imoveis_df.empty:
            return pd.DataFrame()
        
        # Criar matriz usuário-item
        user_item_matrix = pd.pivot_table(
            interacoes_df,
            values='tipo',
            index='usuario_id',
            columns='imovel_id',
            aggfunc='count',
            fill_value=0
        )
        
        if user_id not in user_item_matrix.index:
            return pd.DataFrame()
        
        # Calcular similaridade entre usuários
        user_similarity = cosine_similarity(user_item_matrix)
        user_sim_df = pd.DataFrame(
            user_similarity,
            index=user_item_matrix.index,
            columns=user_item_matrix.index
        )
        
        # Encontrar usuários similares
        similar_users = user_sim_df[user_id].sort_values(ascending=False)[1:11]
        
        # Recomendar imóveis que usuários similares visualizaram
        similar_users_interactions = interacoes_df[
            interacoes_df['usuario_id'].isin(similar_users.index)
        ]
        
        recommended_imoveis = similar_users_interactions['imovel_id'].value_counts().head(n_recommendations)
        
        return imoveis_df[imoveis_df['id'].isin(recommended_imoveis.index)]
    
    def get_hybrid_recommendations(self, user_id, n_recommendations=10):
        """Recomendações híbridas"""
        content_recs = self.get_content_based_recommendations(user_id, n_recommendations)
        collab_recs = self.get_collaborative_recommendations(user_id, n_recommendations)
        
        if content_recs.empty and collab_recs.empty:
            return pd.DataFrame()
        elif content_recs.empty:
            return collab_recs
        elif collab_recs.empty:
            return content_recs
        
        # Combinar recomendações
        combined = pd.concat([content_recs, collab_recs]).drop_duplicates(subset=['id'])
        return combined.head(n_recommendations)

# ==================== INTERFACES POR ROLE ====================
class AdminInterface:
    def __init__(self, auth_system):
        self.auth = auth_system
        self.db = Database()
    
    def show_dashboard(self):
        """Dashboard do administrador"""
        st.title("👑 Dashboard Administrativo")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            conn = self.db.get_connection()
            total_users = pd.read_sql_query("SELECT COUNT(*) FROM usuarios", conn).iloc[0,0]
            conn.close()
            st.metric("Total de Usuários", total_users)
        
        with col2:
            conn = self.db.get_connection()
            total_imoveis = pd.read_sql_query("SELECT COUNT(*) FROM imoveis", conn).iloc[0,0]
            conn.close()
            st.metric("Total de Imóveis", total_imoveis)
        
        with col3:
            conn = self.db.get_connection()
            pendentes = pd.read_sql_query(
                "SELECT COUNT(*) FROM imoveis WHERE status = 'pendente'", 
                conn
            ).iloc[0,0]
            conn.close()
            st.metric("Imóveis Pendentes", pendentes)
        
        # Gestão de usuários
        st.subheader("👥 Gestão de Usuários")
        self.manage_users()
        
        # Gestão de imóveis
        st.subheader("🏠 Aprovação de Imóveis")
        self.approve_properties()
        
        # Estatísticas
        st.subheader("📊 Estatísticas do Sistema")
        self.show_statistics()
    
    def manage_users(self):
        """Interface de gestão de usuários"""
        conn = self.db.get_connection()
        users_df = pd.read_sql_query(
            "SELECT id, nome, email, role, status, data_criacao FROM usuarios", 
            conn
        )
        conn.close()
        
        st.dataframe(users_df, use_container_width=True)
        
        with st.expander("Adicionar/Editar Usuário"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome")
                email = st.text_input("Email")
                senha = st.text_input("Senha", type="password")
            
            with col2:
                role = st.selectbox("Role", ['admin', 'imobiliaria', 'usuario'])
                status = st.selectbox("Status", ['ativo', 'inativo'])
            
            if st.button("Salvar Usuário"):
                if nome and email:
                    if senha:
                        self.auth.register_user(nome, email, senha, role)
                        st.success("Usuário criado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Digite uma senha para novo usuário")
    
    def approve_properties(self):
        """Aprovação de imóveis pendentes"""
        conn = self.db.get_connection()
        pendentes_df = pd.read_sql_query('''
            SELECT i.*, u.nome as proprietario_nome 
            FROM imoveis i 
            JOIN usuarios u ON i.proprietario_id = u.id 
            WHERE i.status = 'pendente'
        ''', conn)
        conn.close()
        
        if pendentes_df.empty:
            st.info("Nenhum imóvel pendente para aprovação")
            return
        
        for idx, imovel in pendentes_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{imovel['titulo']}**")
                    st.write(f"📍 {imovel['bairro']}, {imovel['municipio']}, {imovel['provincia']}")
                    st.write(f"💰 {imovel['preco']:,.0f} Kz")
                    st.write(f"👤 Proprietário: {imovel['proprietario_nome']}")
                
                with col2:
                    st.write(f"🛏️ Quartos: {imovel['quartos']}")
                    st.write(f"🚿 Banheiros: {imovel['banheiros']}")
                    st.write(f"📐 Área: {imovel['area']} m²")
                
                with col3:
                    if st.button("✅ Aprovar", key=f"ap_{imovel['id']}"):
                        self.update_property_status(imovel['id'], 'aprovado')
                        st.rerun()
                    
                    if st.button("❌ Rejeitar", key=f"rj_{imovel['id']}"):
                        self.update_property_status(imovel['id'], 'rejeitado')
                        st.rerun()
                
                st.divider()
    
    def update_property_status(self, imovel_id, status):
        """Atualiza status do imóvel"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE imoveis SET status = ? WHERE id = ?",
            (status, imovel_id)
        )
        conn.commit()
        conn.close()
    
    def show_statistics(self):
        """Mostra estatísticas do sistema"""
        conn = self.db.get_connection()
        
        # Gráfico de imóveis por província
        imoveis_df = pd.read_sql_query(
            "SELECT provincia, COUNT(*) as count FROM imoveis WHERE status = 'aprovado' GROUP BY provincia", 
            conn
        )
        
        if not imoveis_df.empty:
            fig = px.bar(imoveis_df, x='provincia', y='count', 
                        title="Imóveis por Província")
            st.plotly_chart(fig, use_container_width=True)
        
        # Gráfico de usuários por role
        users_df = pd.read_sql_query(
            "SELECT role, COUNT(*) as count FROM usuarios GROUP BY role", 
            conn
        )
        
        if not users_df.empty:
            fig = px.pie(users_df, values='count', names='role', 
                        title="Distribuição de Usuários por Role")
            st.plotly_chart(fig, use_container_width=True)
        
        conn.close()

class ImobiliariaInterface:
    def __init__(self, user_id, auth_system):
        self.user_id = user_id
        self.auth = auth_system
        self.db = Database()
    
    def show_dashboard(self):
        """Dashboard da imobiliária/agente"""
        st.title("🏢 Dashboard da Imobiliária")
        
        # Métricas rápidas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            conn = self.db.get_connection()
            meus_imoveis = pd.read_sql_query(
                "SELECT COUNT(*) FROM imoveis WHERE proprietario_id = ?", 
                conn, params=(self.user_id,)
            ).iloc[0,0]
            conn.close()
            st.metric("Meus Imóveis", meus_imoveis)
        
        with col2:
            conn = self.db.get_connection()
            aprovados = pd.read_sql_query(
                "SELECT COUNT(*) FROM imoveis WHERE proprietario_id = ? AND status = 'aprovado'", 
                conn, params=(self.user_id,)
            ).iloc[0,0]
            conn.close()
            st.metric("Imóveis Aprovados", aprovados)
        
        with col3:
            conn = self.db.get_connection()
            leads = pd.read_sql_query('''
                SELECT COUNT(DISTINCT usuario_id) 
                FROM interacoes i 
                JOIN imoveis im ON i.imovel_id = im.id 
                WHERE im.proprietario_id = ?
            ''', conn, params=(self.user_id,)).iloc[0,0]
            conn.close()
            st.metric("Leads Gerados", leads)
        
        # Cadastro de imóveis
        st.subheader("📝 Cadastrar Novo Imóvel")
        self.register_property()
        
        # Meus imóveis
        st.subheader("🏠 Meus Imóveis")
        self.show_my_properties()
        
        # Leads
        st.subheader("📈 Leads e Interações")
        self.show_leads()
    
    def register_property(self):
        """Formulário de cadastro de imóvel"""
        with st.form("form_imovel"):
            col1, col2 = st.columns(2)
            
            with col1:
                titulo = st.text_input("Título do Imóvel")
                tipo = st.selectbox("Tipo", ['casa', 'apartamento', 'terreno', 'comercial'])
                provincia = st.selectbox("Província", [
                    'Luanda', 'Benguela', 'Huíla', 'Cabinda', 'Huambo',
                    'Cunene', 'Malanje', 'Uíge', 'Zaire', 'Lunda Norte'
                ])
                municipio = st.text_input("Município")
                bairro = st.text_input("Bairro")
            
            with col2:
                preco = st.number_input("Preço (Kz)", min_value=0, step=1000)
                quartos = st.number_input("Quartos", min_value=0, step=1)
                banheiros = st.number_input("Banheiros", min_value=0, step=1)
                area = st.number_input("Área (m²)", min_value=0, step=1)
                descricao = st.text_area("Descrição")
            
            if st.form_submit_button("Cadastrar Imóvel"):
                if titulo and provincia and preco > 0:
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO imoveis 
                        (titulo, descricao, tipo, provincia, municipio, bairro, 
                         preco, quartos, banheiros, area, proprietario_id, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente')
                    ''', (titulo, descricao, tipo, provincia, municipio, bairro,
                          preco, quartos, banheiros, area, self.user_id))
                    
                    conn.commit()
                    conn.close()
                    st.success("Imóvel cadastrado! Aguarde aprovação.")
                else:
                    st.error("Preencha os campos obrigatórios (Título, Província e Preço)")
    
    def show_my_properties(self):
        """Mostra imóveis do agente"""
        conn = self.db.get_connection()
        imoveis_df = pd.read_sql_query(
            "SELECT * FROM imoveis WHERE proprietario_id = ? ORDER BY data_cadastro DESC", 
            conn, params=(self.user_id,)
        )
        conn.close()
        
        if imoveis_df.empty:
            st.info("Você ainda não cadastrou imóveis")
            return
        
        for idx, imovel in imoveis_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    status_color = {
                        'aprovado': '🟢',
                        'pendente': '🟡',
                        'rejeitado': '🔴'
                    }
                    st.write(f"{status_color.get(imovel['status'], '⚪')} **{imovel['titulo']}**")
                    st.write(f"📍 {imovel['bairro']}, {imovel['municipio']}, {imovel['provincia']}")
                    st.write(f"💰 {imovel['preco']:,.0f} Kz")
                
                with col2:
                    st.write(f"🛏️ {imovel['quartos']} quartos")
                    st.write(f"🚿 {imovel['banheiros']} banheiros")
                    st.write(f"📐 {imovel['area']} m²")
                
                with col3:
                    st.write(f"**Status:** {imovel['status']}")
                    if st.button("📊 Estatísticas", key=f"stat_{imovel['id']}"):
                        self.show_property_stats(imovel['id'])
                
                st.divider()
    
    def show_property_stats(self, imovel_id):
        """Mostra estatísticas de um imóvel"""
        conn = self.db.get_connection()
        
        # Contar visualizações
        views = pd.read_sql_query(
            "SELECT COUNT(*) FROM interacoes WHERE imovel_id = ? AND tipo = 'view'",
            conn, params=(imovel_id,)
        ).iloc[0,0]
        
        # Contar favoritos
        favorites = pd.read_sql_query(
            "SELECT COUNT(*) FROM favoritos WHERE imovel_id = ?",
            conn, params=(imovel_id,)
        ).iloc[0,0]
        
        conn.close()
        
        st.info(f"👁️ **Visualizações:** {views} | ❤️ **Favoritos:** {favorites}")
    
    def show_leads(self):
        """Mostra leads gerados"""
        conn = self.db.get_connection()
        
        leads_df = pd.read_sql_query('''
            SELECT DISTINCT u.nome, u.email, i.tipo, i.timestamp
            FROM interacoes i
            JOIN usuarios u ON i.usuario_id = u.id
            JOIN imoveis im ON i.imovel_id = im.id
            WHERE im.proprietario_id = ?
            ORDER BY i.timestamp DESC
            LIMIT 50
        ''', conn, params=(self.user_id,))
        
        conn.close()
        
        if leads_df.empty:
            st.info("Nenhum lead gerado ainda")
            return
        
        st.dataframe(leads_df, use_container_width=True)

class UsuarioInterface:
    def __init__(self, user_id, auth_system, rec_system):
        self.user_id = user_id
        self.auth = auth_system
        self.rec_system = rec_system
        self.db = Database()
    
    def show_dashboard(self):
        """Dashboard do usuário comum"""
        st.title(f"👤 Bem-vindo, {st.session_state.user['nome']}!")
        
        # Preferências do usuário
        st.subheader("⚙️ Minhas Preferências")
        self.update_preferences()
        
        # Recomendações
        st.subheader("🎯 Recomendações para Você")
        recommendations = self.rec_system.get_hybrid_recommendations(self.user_id, 5)
        
        if recommendations.empty:
            st.info("Complete suas preferências para receber recomendações personalizadas")
            # Mostrar alguns imóveis populares
            self.show_properties()
        else:
            self.display_properties(recommendations, is_recommendations=True)
        
        # Todos os imóveis
        st.subheader("🏘️ Todos os Imóveis Disponíveis")
        self.show_properties()
        
        # Favoritos
        st.subheader("❤️ Meus Favoritos")
        self.show_favorites()
    
    def update_preferences(self):
        """Atualiza preferências do usuário"""
        current_prefs = {}
        if st.session_state.user.get('preferencias'):
            current_prefs = json.loads(st.session_state.user['preferencias'])
        
        with st.form("preferences_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                tipo_preferido = st.selectbox(
                    "Tipo de Imóvel Preferido",
                    ['qualquer', 'casa', 'apartamento', 'terreno'],
                    index=['qualquer', 'casa', 'apartamento', 'terreno'].index(
                        current_prefs.get('tipo', 'qualquer')
                    )
                )
                
                provincia_preferida = st.selectbox(
                    "Província Preferida",
                    ['qualquer', 'Luanda', 'Benguela', 'Huíla', 'Cabinda', 'Huambo'],
                    index=['qualquer', 'Luanda', 'Benguela', 'Huíla', 'Cabinda', 'Huambo'].index(
                        current_prefs.get('provincia', 'qualquer')
                    )
                )
            
            with col2:
                preco_max = st.number_input(
                    "Preço Máximo (Kz)",
                    min_value=0,
                    value=int(current_prefs.get('preco_max', 100000000)),
                    step=1000000
                )
                
                quartos_min = st.number_input(
                    "Mínimo de Quartos",
                    min_value=0,
                    value=int(current_prefs.get('quartos_min', 1)),
                    step=1
                )
            
            if st.form_submit_button("Salvar Preferências"):
                novas_prefs = {
                    'tipo': tipo_preferido if tipo_preferido != 'qualquer' else None,
                    'provincia': provincia_preferida if provincia_preferida != 'qualquer' else None,
                    'preco_max': preco_max,
                    'quartos_min': quartos_min
                }
                
                self.auth.update_user(self.user_id, {'preferencias': novas_prefs})
                st.session_state.user['preferencias'] = json.dumps(novas_prefs)
                st.success("Preferências atualizadas!")
    
    def show_properties(self, filters=None):
        """Mostra imóveis com filtros"""
        conn = self.db.get_connection()
        
        # Construir query com filtros
        query = "SELECT * FROM imoveis WHERE status = 'aprovado'"
        params = []
        
        if filters:
            if filters.get('tipo'):
                query += " AND tipo = ?"
                params.append(filters['tipo'])
            if filters.get('provincia'):
                query += " AND provincia = ?"
                params.append(filters['provincia'])
            if filters.get('preco_max'):
                query += " AND preco <= ?"
                params.append(filters['preco_max'])
        
        query += " ORDER BY data_cadastro DESC LIMIT 50"
        
        imoveis_df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        self.display_properties(imoveis_df)
    
    def display_properties(self, imoveis_df, is_recommendations=False):
        """Exibe lista de imóveis"""
        if imoveis_df.empty:
            st.info("Nenhum imóvel encontrado")
            return
        
        # Filtros
        if not is_recommendations:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                filter_tipo = st.selectbox(
                    "Filtrar por tipo",
                    ['todos', 'casa', 'apartamento', 'terreno'],
                    key="filter_tipo"
                )
            
            with col2:
                filter_provincia = st.selectbox(
                    "Filtrar por província",
                    ['todas', 'Luanda', 'Benguela', 'Huíla', 'Cabinda'],
                    key="filter_provincia"
                )
            
            with col3:
                filter_preco_max = st.number_input(
                    "Preço máximo (Kz)",
                    min_value=0,
                    value=100000000,
                    step=1000000,
                    key="filter_preco"
                )
            
            with col4:
                if st.button("Aplicar Filtros", key="apply_filters"):
                    filters = {}
                    if filter_tipo != 'todos':
                        filters['tipo'] = filter_tipo
                    if filter_provincia != 'todas':
                        filters['provincia'] = filter_provincia
                    filters['preco_max'] = filter_preco_max
                    
                    self.show_properties(filters)
                    return
        
        # Mostrar imóveis
        for idx, imovel in imoveis_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    if is_recommendations:
                        st.markdown("⭐ **RECOMENDADO**")
                    st.write(f"### {imovel['titulo']}")
                    st.write(f"📍 {imovel['bairro']}, {imovel['municipio']}, {imovel['provincia']}")
                    st.write(f"💰 **{imovel['preco']:,.0f} Kz**")
                    if imovel['descricao']:
                        st.write(imovel['descricao'][:100] + "...")
                
                with col2:
                    st.write(f"**Tipo:** {imovel['tipo'].capitalize()}")
                    st.write(f"🛏️ **Quartos:** {imovel['quartos']}")
                    st.write(f"🚿 **Banheiros:** {imovel['banheiros']}")
                    st.write(f"📐 **Área:** {imovel['area']} m²")
                
                with col3:
                    # Registrar visualização
                    self.record_interaction(self.user_id, imovel['id'], 'view')
                    
                    if st.button("👁️ Ver Detalhes", key=f"view_{imovel['id']}"):
                        st.session_state.selected_property = imovel['id']
                    
                    # Botão de favorito
                    is_favorited = self.is_favorited(self.user_id, imovel['id'])
                    favorite_text = "💔 Remover" if is_favorited else "❤️ Favoritar"
                    
                    if st.button(favorite_text, key=f"fav_{imovel['id']}"):
                        if is_favorited:
                            self.remove_favorite(self.user_id, imovel['id'])
                        else:
                            self.add_favorite(self.user_id, imovel['id'])
                        st.rerun()
                
                st.divider()
    
    def show_favorites(self):
        """Mostra imóveis favoritados pelo usuário"""
        conn = self.db.get_connection()
        
        favorites_df = pd.read_sql_query('''
            SELECT i.* 
            FROM imoveis i
            JOIN favoritos f ON i.id = f.imovel_id
            WHERE f.usuario_id = ? AND i.status = 'aprovado'
        ''', conn, params=(self.user_id,))
        
        conn.close()
        
        if favorites_df.empty:
            st.info("Você ainda não favoritou nenhum imóvel")
            return
        
        self.display_properties(favorites_df)
    
    def record_interaction(self, usuario_id, imovel_id, tipo):
        """Registra interação do usuário"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interacoes (usuario_id, imovel_id, tipo)
            VALUES (?, ?, ?)
        ''', (usuario_id, imovel_id, tipo))
        
        conn.commit()
        conn.close()
    
    def add_favorite(self, usuario_id, imovel_id):
        """Adiciona imóvel aos favoritos"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO favoritos (usuario_id, imovel_id)
                VALUES (?, ?)
            ''', (usuario_id, imovel_id))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Já está nos favoritos
        finally:
            conn.close()
    
    def remove_favorite(self, usuario_id, imovel_id):
        """Remove imóvel dos favoritos"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM favoritos 
            WHERE usuario_id = ? AND imovel_id = ?
        ''', (usuario_id, imovel_id))
        
        conn.commit()
        conn.close()
    
    def is_favorited(self, usuario_id, imovel_id):
        """Verifica se imóvel está nos favoritos"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 1 FROM favoritos 
            WHERE usuario_id = ? AND imovel_id = ?
        ''', (usuario_id, imovel_id))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None

# ==================== APLICAÇÃO PRINCIPAL (CORRIGIDA) ====================
def main():
    # Inicializar sistemas
    if 'auth' not in st.session_state:
        st.session_state.auth = AuthSystem()
    if 'rec_system' not in st.session_state:
        st.session_state.rec_system = RecommendationSystem()
    
    # Verificar se usuário está logado
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    # Sidebar para login/cadastro
    with st.sidebar:
        # CORREÇÃO: Substituído use_column_width por width
        st.markdown("<h3 style='text-align: center;'>🏠 Imobiliária Angola</h3>", 
                   unsafe_allow_html=True)
        
        if st.session_state.user is None:
            # Página de login/cadastro
            tab1, tab2 = st.tabs(["Login", "Cadastro"])
            
            with tab1:
                st.subheader("Login")
                email = st.text_input("Email", key="login_email")
                senha = st.text_input("Senha", type="password", key="login_senha")
                
                if st.button("Entrar"):
                    user, error = st.session_state.auth.login(email, senha)
                    if user:
                        st.session_state.user = user
                        st.success(f"Bem-vindo, {user['nome']}!")
                        st.rerun()
                    else:
                        st.error(error)
            
            with tab2:
                st.subheader("Cadastro")
                nome = st.text_input("Nome Completo", key="reg_nome")
                email = st.text_input("Email", key="reg_email")
                senha = st.text_input("Senha", type="password", key="reg_senha")
                confirm_senha = st.text_input("Confirmar Senha", type="password", key="reg_confirm")
                
                role = st.selectbox(
                    "Tipo de Conta",
                    ['usuario', 'imobiliaria'],
                    key="reg_role"
                )
                
                if st.button("Cadastrar"):
                    if senha != confirm_senha:
                        st.error("As senhas não coincidem!")
                    elif nome and email and senha:
                        if st.session_state.auth.register_user(nome, email, senha, role):
                            st.success("Cadastro realizado! Faça login.")
                        else:
                            st.error("Erro no cadastro. Tente outro email.")
                    else:
                        st.error("Preencha todos os campos!")
        
        else:
            # Usuário logado
            st.success(f"👋 Olá, {st.session_state.user['nome']}!")
            st.write(f"**Role:** {st.session_state.user['role'].capitalize()}")
            
            if st.button("🚪 Sair"):
                st.session_state.user = None
                st.rerun()
            
            # Navegação por role - CORREÇÃO: Substituído st.page_link por botões
            st.divider()
            st.subheader("Navegação")
            
            role = st.session_state.user['role']
            
            # Criar um container para navegação
            nav_container = st.container()
            with nav_container:
                if role == 'admin':
                    if st.button("📊 Dashboard Admin", use_container_width=True):
                        st.session_state.current_page = 'admin_dashboard'
                        st.rerun()
                elif role == 'imobiliaria':
                    if st.button("🏢 Dashboard Imobiliária", use_container_width=True):
                        st.session_state.current_page = 'imobiliaria_dashboard'
                        st.rerun()
                elif role == 'usuario':
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("👤 Perfil", use_container_width=True):
                            st.session_state.current_page = 'usuario_dashboard'
                            st.rerun()
                        if st.button("❤️ Favoritos", use_container_width=True):
                            st.session_state.current_page = 'favoritos'
                            st.rerun()
                    with col2:
                        if st.button("🏘️ Imóveis", use_container_width=True):
                            st.session_state.current_page = 'explorar'
                            st.rerun()
    
    # Conteúdo principal baseado no role
    if st.session_state.user is None:
        # Página inicial pública
        show_public_home()
    
    else:
        # Conteúdo baseado no role
        role = st.session_state.user['role']
        
        # Determinar qual página mostrar
        if 'current_page' not in st.session_state:
            # Página padrão baseada no role
            if role == 'admin':
                st.session_state.current_page = 'admin_dashboard'
            elif role == 'imobiliaria':
                st.session_state.current_page = 'imobiliaria_dashboard'
            else:
                st.session_state.current_page = 'usuario_dashboard'
        
        # Mostrar a página atual
        show_current_page(role)

def show_public_home():
    """Mostra página inicial pública"""
    st.title("🏠 Imobiliária Inteligente de Angola")
    st.markdown("""
    ### Encontre o imóvel dos seus sonhos em Angola!
    
    **Características do sistema:**
    - 🎯 **Recomendações personalizadas** baseadas em seu perfil
    - 🔐 **Segurança total** com controle de acesso por níveis
    - 📊 **Dashboard completo** para cada tipo de usuário
    - 📱 **Interface intuitiva** e responsiva
    
    **Faça login ou cadastre-se para começar!**
    """)
    
    # Estatísticas públicas
    db = Database()
    conn = db.get_connection()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_imoveis = pd.read_sql_query(
            "SELECT COUNT(*) FROM imoveis WHERE status = 'aprovado'", 
            conn
        ).iloc[0,0]
        st.metric("Imóveis Disponíveis", total_imoveis)
    
    with col2:
        total_users = pd.read_sql_query("SELECT COUNT(*) FROM usuarios", conn).iloc[0,0]
        st.metric("Usuários Cadastrados", total_users)
    
    with col3:
        provincias = pd.read_sql_query(
            "SELECT COUNT(DISTINCT provincia) FROM imoveis WHERE status = 'aprovado'", 
            conn
        ).iloc[0,0]
        st.metric("Províncias Atendidas", provincias)
    
    conn.close()
    
    # Mostrar alguns imóveis aprovados - CORREÇÃO: st.card() substituído por st.container() com estilo
    st.subheader("📌 Destaques")
    db = Database()
    conn = db.get_connection()
    destaques = pd.read_sql_query(
        "SELECT * FROM imoveis WHERE status = 'aprovado' ORDER BY data_cadastro DESC LIMIT 3", 
        conn
    )
    conn.close()
    
    if not destaques.empty:
        cols = st.columns(3)
        for idx, imovel in destaques.iterrows():
            with cols[idx % 3]:
                # CORREÇÃO: Substituído st.card() por container com estilo
                with st.container():
                    st.markdown(f"""
                    <div style='padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px;'>
                        <h4>{imovel['titulo']}</h4>
                        <p>📍 {imovel['provincia']}</p>
                        <p>💰 {imovel['preco']:,.0f} Kz</p>
                        <p>🛏️ {imovel['quartos']} quartos</p>
                    </div>
                    """, unsafe_allow_html=True)

def show_current_page(role):
    """Mostra a página atual baseada no estado"""
    current_page = st.session_state.get('current_page', 'dashboard')
    
    if role == 'admin':
        admin_ui = AdminInterface(st.session_state.auth)
        admin_ui.show_dashboard()
    
    elif role == 'imobiliaria':
        imob_ui = ImobiliariaInterface(st.session_state.user['id'], st.session_state.auth)
        imob_ui.show_dashboard()
    
    elif role == 'usuario':
        user_ui = UsuarioInterface(
            st.session_state.user['id'], 
            st.session_state.auth,
            st.session_state.rec_system
        )
        
        if current_page == 'usuario_dashboard':
            user_ui.show_dashboard()
        elif current_page == 'favoritos':
            st.title("❤️ Meus Favoritos")
            user_ui.show_favorites()
        elif current_page == 'explorar':
            st.title("🏘️ Explorar Imóveis")
            user_ui.show_properties()
        else:
            user_ui.show_dashboard()

if __name__ == "__main__":
    main()