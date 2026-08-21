import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Boa Fortuna - Sistema de Sondagem", layout="wide")

# --- CREDENCIAIS DE ACESSO ---
USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"

# --- BANCO DE DADOS LOCAL (SQLITE) ---
DB_NAME = "boafortuna_dados.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabela de Boletins
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
    # Tabela de Manobras e Testemunhos
    c.execute('''
        CREATE TABLE IF NOT EXISTS manobras_testemunho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            furo_id TEXT NOT NULL,
            de_m REAL,
            ate_m REAL,
            recup_m REAL,
            taxa_recup_pct REAL,
            num_caixa TEXT,
            horas_trab REAL,
            horas_parado REAL,
            horario TEXT,
            motivo_parada TEXT,
            descricao_litologica TEXT,
            data_registro TEXT
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

def salvar_manobra(furo, de, ate, recup, taxa, caixa, h_trab, h_parado, horario, motivo, desc):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''
        INSERT INTO manobras_testemunho
        (furo_id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, horas_trab, horas_parado, horario, motivo_parada, descricao_litologica, data_registro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (furo, de, ate, recup, taxa, caixa, h_trab, h_parado, horario, motivo, desc, data_atual))
    conn.commit()
    conn.close()

def buscar_registros():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT furo_id, obra_cliente, cidade_uf, sondador, profundidade_m, tipo_sondagem, data_registro FROM boletins_campo ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

def buscar_manobras(furo_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if furo_id:
        c.execute('SELECT de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, horas_trab, horas_parado, descricao_litologica FROM manobras_testemunho WHERE furo_id = ? ORDER BY id ASC', (furo_id,))
    else:
        c.execute('SELECT furo_id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, descricao_litologica, data_registro FROM manobras_testemunho ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

# --- ESTADO DA SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        .stApp { background-color: #EFECE6; }
        div[data-testid="stForm"] { 
            background-color: #ffffff; padding: 40px; border-radius: 8px; 
            border-top: 5px solid #1E3A8A; box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.08);
        }
        div[data-testid="stForm"] button { 
            background-color: #1E3A8A !important; color: white !important; 
            font-weight: 600 !important; border-radius: 4px !important; width: 100% !important;
            height: 42px !important; border: none !important;
        }
        #MainMenu, footer, header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #1E3A8A; margin-bottom: 0px; font-weight: 700;'>BOA FORTUNA</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #555555; font-size: 13px; letter-spacing: 2px; margin-bottom: 25px;'>PERFURAÇÕES E SONDAGENS</p>", unsafe_allow_html=True)

        with st.form("login_form"):
            user_input = st.text_input("Usuário", placeholder="Digite seu usuário", label_visibility="collapsed")
            pass_input = st.text_input("Senha", type="password", placeholder="Digite sua senha", label_visibility="collapsed")
            btn_entrar = st.form_submit_button("Acessar Sistema")

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
        .stApp { background-color: #F8F9FA; }
        div[data-testid="stSidebar"] { background-color: #D2B48C; }
        h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #1E3A8A; font-weight: 600; }
        div.stButton > button {
            background-color: #1E3A8A !important; color: #ffffff !important;
            border-radius: 4px !important; border: none !important; font-weight: 500 !important;
        }
        div.stButton > button:hover { background-color: #2563EB !important; }
        #MainMenu, footer, header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

    # --- BARRA LATERAL ---
    st.sidebar.markdown("<h3 style='color: #1E3A8A; margin-bottom: 0px;'>BOA FORTUNA</h3>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='font-size: 12px; color: #333;'>Usuário: <b>{USUARIO_CORRETO}</b></p>", unsafe_allow_html=True)
    
    st.sidebar.divider()
    st.sidebar.markdown("**Menu de Navegação**")
    
    opcao = st.sidebar.radio(
        "Selecione a etapa:",
        [
            "1. Cabeçalho e Empresa",
            "2. Equipe de Campo",
            "3. Registro de Manobra e Testemunho",
            "4. Dados do Furo & Perfuração",
            "5. Histórico de Boletins"
        ],
        label_visibility="collapsed"
    )

    st.sidebar.divider()
    if st.sidebar.button("Sair da Conta", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

    # --- ÁREA CENTRAL ---
    
    # ETAPA 1
    if opcao == "1. Cabeçalho e Empresa":
        st.title("1. Cabeçalho de Identificação")
        st.caption("Informações institucionais e de localização do projeto.")
        
        with st.form("form_cabecalho"):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state["empresa"] = st.text_input("Nome da Empresa Executora", value=st.session_state.get("empresa", "Boa Fortuna Perfurações e Sondagens"))
                st.session_state["obra"] = st.text_input("Cliente / Nome da Obra", value=st.session_state.get("obra", ""))
            with col2:
                st.session_state["cidade"] = st.text_input("Cidade / UF", value=st.session_state.get("cidade", ""))
                st.session_state["data_campo"] = st.date_input("Data do Ensaio", value=st.session_state.get("data_campo", date.today()))
            
            st.form_submit_button("Salvar Etapa 1")

    # ETAPA 2
    elif opcao == "2. Equipe de Campo":
        st.title("2. Equipe Responsável")
        st.caption("Cadastro dos profissionais e responsáveis técnicos da operação.")
        
        with st.form("form_equipe"):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state["coordenador"] = st.text_input("Coordenador de Campo", value=st.session_state.get("coordenador", ""))
                st.session_state["supervisor"] = st.text_input("Supervisor / TST", value=st.session_state.get("supervisor", ""))
            with col2:
                st.session_state["sondador"] = st.text_input("Sondador Principal", value=st.session_state.get("sondador", ""))
                st.session_state["auxiliares"] = st.text_input("Auxiliares de Sondagem", value=st.session_state.get("auxiliares", ""))

            st.form_submit_button("Salvar Etapa 2")

    # ETAPA 3: REGISTRO DE MANOBRA E TESTEMUNHO
    elif opcao == "3. Registro de Manobra e Testemunho":
        st.title("3. Registro de Manobra e Testemunho")
        st.caption("Lançamento do avanço, recuperação da amostra, caixas e registro fotográfico.")
        
        # Pega dinamicamente o furo_id armazenado na sessão ou utiliza 'SP-01' por padrão
        furo_atual = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", "SP-01"), key="input_furo_manobra")
        st.session_state["furo_id"] = furo_atual

        manobras_existentes = buscar_manobras(furo_atual)
        prox_de = manobras_existentes[-1][1] if manobras_existentes else 0.0
        prox_ate = round(prox_de + 1.5, 2)

        with st.form("form_manobra"):
            # Linha 1: Métricas de Perfuração
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                de_m = st.number_input("De (m)", min_value=0.0, step=0.5, value=float(prox_de), format="%.2f")
            with col2:
                ate_m = st.number_input("Até (m)", min_value=0.0, step=0.5, value=float(prox_ate), format="%.2f")
            with col3:
                recup_m = st.number_input("Recup. (m)", min_value=0.0, step=0.1, value=round(max(0.0, ate_m - de_m), 2), format="%.2f")
            with col4:
                num_caixa = st.text_input("Nº da Caixa", value=manobras_existentes[-1][4] if manobras_existentes else "01")
            with col5:
                horas_trab = st.number_input("Horas Trab. (h)", min_value=0.0, step=0.5, value=1.0, format="%.1f")
            with col6:
                horas_parado = st.number_input("Horas Parado (h)", min_value=0.0, step=0.5, value=0.0, format="%.1f")

            # Cálculo automático de avanço e taxa de recuperação
            avancamento = round(ate_m - de_m, 2)
            taxa_recup = min(100.0, round((recup_m / avancamento * 100), 1)) if avancamento > 0 else 0.0
            
            st.info(f"**Avanço da Manobra:** {avancamento:.2f} m | **Taxa de Recuperação:** {taxa_recup:.1f}%")

            # Linha 2: Horários e Detalhes Litológicos
            col7, col8, col9 = st.columns([1, 1, 2])
            with col7:
                horario = st.text_input("Horário", placeholder="Ex: 08:00 - 09:30")
            with col8:
                motivo_parada = st.text_input("Motivo Parada", value="Nenhuma")
            with col9:
                desc_litologica = st.text_input("Descrição Litológica / Observações", placeholder="Ex: Solo residual, rocha alterada...")

            st.markdown("---")
            st.subheader("Registro Fotográfico da Manobra (Até 3 fotos)")
            
            # Abas para Upload ou Captura pela Câmera
            tab_galeria, tab_camera = st.tabs(["Galeria", "Câmera"])
            fotos_manobra_pil = []
            
            with tab_galeria:
                fotos_upload = st.file_uploader("Selecione até 3 imagens", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                if fotos_upload:
                    for f in fotos_upload[:3]:
                        fotos_manobra_pil.append(Image.open(f))
            
            with tab_camera:
                foto_cam = st.camera_input("Tirar foto da caixa/testemunho")
                if foto_cam and len(fotos_manobra_pil) < 3:
                    fotos_manobra_pil.append(Image.open(foto_cam))

            btn_salvar_manobra = st.form_submit_button("Adicionar Manobra", use_container_width=True)

            if btn_salvar_manobra:
                if ate_m > de_m:
                    salvar_manobra(furo_atual, de_m, ate_m, recup_m, taxa_recup, num_caixa, horas_trab, horas_parado, horario, motivo_parada, desc_litologica)
                    st.success(f"Manobra de {de_m:.2f}m a {ate_m:.2f}m salva com sucesso para o furo **{furo_atual}**!")
                    st.rerun()
                else:
                    st.error("O valor final 'Até (m)' deve ser maior que o valor inicial 'De (m)'.")

        st.divider()
        st.subheader(f"Manobras Salvas para o Furo: {furo_atual}")
        manobras_furo = buscar_manobras(furo_atual)
        if manobras_furo:
            df_manobras = pd.DataFrame(manobras_furo, columns=["De (m)", "Até (m)", "Recup (m)", "Recup (%)", "Caixa", "H. Trab", "H. Parado", "Descrição Litológica"])
            st.dataframe(df_manobras, use_container_width=True)
        else:
            st.info("Nenhuma manobra cadastrada para este furo.")

    # ETAPA 4
    elif opcao == "4. Dados do Furo & Perfuração":
        st.title("4. Dados do Furo e Perfuração")
        st.caption("Inserção dos dados técnicos e consolidação do boletim.")
        
        with st.form("form_furo"):
            col1, col2, col3 = st.columns(3)
            with col1:
                furo = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", ""), placeholder="Ex: SP-01")
                st.session_state["furo_id"] = furo
            with col2:
                tipo_sondagem = st.selectbox("Tipo de Sondagem", ["SPT (A Percussão)", "Rotativa", "Mista", "Poço de Inspeção"])
            with col3:
                profundidade = st.number_input("Profundidade Final (m)", min_value=0.0, step=0.5)

            obs = st.text_area("Observações Gerais / Nível d'Água (NA)", placeholder="Registros de NA, paralisações ou anomalias do terreno...")

            btn_finalizar = st.form_submit_button("Finalizar e Gravar Boletim", use_container_width=True)

            if btn_finalizar:
                if furo:
                    salvar_boletim(
                        st.session_state.get("empresa", "Boa Fortuna"),
                        st.session_state.get("obra", "Não informada"),
                        st.session_state.get("cidade", "-"),
                        st.session_state.get("coordenador", "-"),
                        st.session_state.get("supervisor", "-"),
                        st.session_state.get("sondador", "-"),
                        st.session_state.get("auxiliares", "-"),
                        furo, tipo_sondagem, profundidade, obs
                    )
                    st.success(f"Boletim do furo {furo} gravado com sucesso.")
                else:
                    st.warning("Informe a identificação do furo antes de gravar.")

    # ETAPA 5
    elif opcao == "5. Histórico de Boletins":
        st.title("5. Histórico de Boletins Registrados")
        st.caption("Relação de furos salvos no banco de dados.")
        
        registros = buscar_registros()
        if registros:
            df = pd.DataFrame(registros, columns=["Furo", "Obra", "Cidade/UF", "Sondador", "Prof. (m)", "Tipo", "Data/Hora"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenum registro encontrado no banco de dados.")
