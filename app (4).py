import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Boa Fortuna Investimento", page_icon="📈", layout="centered")

# --- CREDENCIAIS DE ACESSO ---
USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"

# --- BANCO DE DADOS LOCAL (SQLITE) ---
DB_NAME = "boafortuna_dados.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_registro TEXT NOT NULL,
            cliente_id TEXT NOT NULL,
            valor REAL NOT NULL,
            observacao TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def salvar_registro(cliente, valor, obs):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''
        INSERT INTO registros (data_registro, cliente_id, valor, observacao)
        VALUES (?, ?, ?, ?)
    ''', (data_atual, cliente, valor, obs))
    conn.commit()
    conn.close()

def buscar_registros():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT cliente_id, valor, observacao, data_registro FROM registros ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

# --- ESTADO DA SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# --- TELA DE LOGIN (ESTILO MARROM CLARO & AZUL) ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        /* Fundo em Marrom Claro Suave */
        .stApp { 
            background-color: #D2B48C; 
        }
        
        /* Cartão Central Branco com Borda Azul */
        div[data-testid="stForm"] { 
            background-color: #ffffff; 
            padding: 35px; 
            border-radius: 12px; 
            border-top: 6px solid #1E3A8A;
            box-shadow: 0px 8px 16px rgba(0, 0, 0, 0.15);
        }
        
        /* Botão Principal em Azul Investimento */
        div[data-testid="stForm"] button { 
            background-color: #1E3A8A !important; 
            color: white !important; 
            font-weight: bold !important; 
            border-radius: 6px !important;
            width: 100% !important; 
            border: none !important;
            height: 45px !important;
        }
        
        div[data-testid="stForm"] button:hover {
            background-color: #2563EB !important;
        }

        #MainMenu, footer, header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #1E3A8A; margin-bottom: 0px;'>📈 Boa Fortuna</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: #8B5A2B; margin-top: -5px; margin-bottom: 25px; letter-spacing: 1px;'>INVESTIMENTO</h4>", unsafe_allow_html=True)

        with st.form("login_form"):
            user_input = st.text_input("Usuário", placeholder="Digite seu usuário", label_visibility="collapsed")
            pass_input = st.text_input("Senha", type="password", placeholder="Digite sua senha", label_visibility="collapsed")
            btn_entrar = st.form_submit_button("Acessar Conta")

            if btn_entrar:
                if user_input == USUARIO_CORRETO and pass_input == SENHA_CORRETA:
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

# --- PAINEL PRINCIPAL (APÓS LOGIN) ---
else:
    # Customização da barra lateral e página interna
    st.markdown("""
        <style>
        .stApp { background-color: #F5F2EB; }
        div[data-testid="stSidebar"] { background-color: #D2B48C; }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"👤 Usuário: **{USUARIO_CORRETO}**")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    st.title("💼 Boa Fortuna Investimento")
    st.markdown("Painel de controle e lançamento de registros.")

    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            cliente = st.text_input("Cliente / Operação", placeholder="Ex: Cliente A")
        with col2:
            valor = st.number_input("Valor (R$)", min_value=0.0, step=100.0)
            
        obs = st.text_area("Observações", placeholder="Detalhes da transação...")
        
        btn_salvar = st.form_submit_button("💾 Confirmar Lançamento")

        if btn_salvar:
            if cliente:
                salvar_registro(cliente, valor, obs)
                st.success(f"✅ Registro de **{cliente}** gravado com sucesso!")
            else:
                st.warning("⚠️ Informe o nome do cliente ou operação.")

    st.divider()
    st.subheader("📊 Histórico de Lançamentos")
    registros = buscar_registros()

    if registros:
        df = pd.DataFrame(registros, columns=["Cliente/Operação", "Valor (R$)", "Observação", "Data/Hora"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum lançamento registrado até o momento.")
