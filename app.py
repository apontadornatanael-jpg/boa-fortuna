import streamlit as st
import sqlite3
from datetime import datetime, date
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
        CREATE TABLE IF NOT EXISTS boletins_campo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_registro TEXT,
            empresa TEXT,
            obra_cliente TEXT,
            cidade_uf TEXT,
            coordenador TEXT,
            supervisor TEXT,
            sondador TEXT,
            auxiliares TEXT,
            furo_id TEXT,
            tipo_sondagem TEXT,
            profundidade_m REAL,
            observacao TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def salvar_boletim(empresa, obra, cidade, coord, superv, sond, aux, furo, tipo, prof, obs):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''
        INSERT INTO boletins_campo 
        (data_registro, empresa, obra_cliente, cidade_uf, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, profundidade_m, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data_atual, empresa, obra, cidade, coord, superv, sond, aux, furo, tipo, prof, obs))
    conn.commit()
    conn.close()

def buscar_registros():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT furo_id, obra_cliente, cidade_uf, sondador, profundidade_m, data_registro FROM boletins_campo ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

# --- JANELAS MODAIS (ST.DIALOG) ---

@st.dialog("📋 Novo Boletim de Campo", width="large")
def modal_novo_boletim():
    st.markdown("### 🏢 Cabeçalho de Identificação")
    
    with st.form("form_modal_boletim", clear_on_submit=True):
        # Linha 1: Dados Institucionais e Localização
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.text_input("Nome da Empresa Executora", value="Boa Fortuna Perfurações e Sondagens")
            obra = st.text_input("Cliente / Nome da Obra", placeholder="Ex: Parque Eólico - Fase 2")
        with col2:
            cidade = st.text_input("Cidade / UF", placeholder="Ex: Natal / RN")
            data_campo = st.date_input("Data do Ensaio", value=date.today())

        st.markdown("---")
        st.markdown("### 👥 Equipe Responsável")
        
        # Linha 2: Responsáveis Técnicos e Operacionais
        col3, col4 = st.columns(2)
        with col3:
            coordenador = st.text_input("Coordenador de Campo", placeholder="Nome do Engenheiro / Coordenador")
            supervisor = st.text_input("Supervisor / TST", placeholder="Nome do Supervisor")
        with col4:
            sondador = st.text_input("Sondador Principal", placeholder="Nome do Sondador")
            auxiliares = st.text_input("Auxiliares de Sondagem", placeholder="Ex: João Silva, Pedro Santos")

        st.markdown("---")
        st.markdown("### 📌 Dados do Furo e Perfuração")
        
        # Linha 3: Dados Técnicos do Furo
        col5, col6, col7 = st.columns(3)
        with col5:
            furo = st.text_input("Identificação do Furo", placeholder="Ex: SP-01 / SR-02")
        with col6:
            tipo_sondagem = st.selectbox("Tipo de Sondagem", ["SPT (A Percussão)", "Rotativa", "Mista", "Poço de Inspeção"])
        with col7:
            profundidade = st.number_input("Profundidade Final (m)", min_value=0.0, step=0.5)

        obs = st.text_area("Observações Gerais / Nível d'Água (NA)", placeholder="Registros de NA, paralisação ou anomalias do terreno...")
        
        btn_confirmar = st.form_submit_button("💾 Salvar Boletim de Campo", use_container_width=True)
        if btn_confirmar:
            if furo and obra:
                salvar_boletim(empresa, obra, cidade, coordenador, supervisor, sondador, auxiliares, furo, tipo_sondagem, profundidade, obs)
                st.success(f"✅ Boletim do furo **{furo}** salvo com sucesso!")
                st.rerun()
            else:
                st.warning("⚠️ Preencha os campos obrigatórios: Nome da Obra e Identificação do Furo.")

@st.dialog("📊 Histórico de Registros")
def modal_historico():
    st.write("Registros salvos no banco de dados:")
    registros = buscar_registros()
    if registros:
        df = pd.DataFrame(registros, columns=["Furo", "Obra", "Cidade/UF", "Sondador", "Prof. (m)", "Data/Hora"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum registro encontrado.")

# --- ESTADO DA SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        .stApp { background-color: #D2B48C; }
        div[data-testid="stForm"] { 
            background-color: #ffffff; padding: 35px; border-radius: 12px; 
            border-top: 6px solid #1E3A8A; box-shadow: 0px 8px 16px rgba(0, 0, 0, 0.15);
        }
        div[data-testid="stForm"] button { 
            background-color: #1E3A8A !important; color: white !important; 
            font-weight: bold !important; border-radius: 6px !important; width: 100% !important;
        }
        #MainMenu, footer, header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #1E3A8A; margin-bottom: 0px;'>📈 Boa Fortuna</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: #8B5A2B; margin-top: -5px; margin-bottom: 25px;'>INVESTIMENTO & SONDAREM</h4>", unsafe_allow_html=True)

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

# --- PAINEL PRINCIPAL ---
else:
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

    # Cabeçalho Principal da Tela Interna
    st.title("🚜 Boa Fortuna - Diário de Campo")
    st.markdown("Gerenciamento de boletins de sondagem geotécnica e perfuração.")

    st.divider()

    # Botões de Ação
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("📝 Preencher Novo Boletim", use_container_width=True):
            modal_novo_boletim()

    with col_btn2:
        if st.button("📊 Ver Histórico de Furos", use_container_width=True):
            modal_historico()

    st.divider()
    
    st.subheader("📌 Últimos Furos Registrados")
    registros = buscar_registros()
    if registros:
        df = pd.DataFrame(registros[:5], columns=["Furo", "Obra", "Cidade/UF", "Sondador", "Prof. (m)", "Data/Hora"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum furo registrado até o momento.")
