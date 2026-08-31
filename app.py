import streamlit as st 
import sqlite3 
from datetime import datetime, date, time, timedelta
import pandas as pd 
from PIL import Image 
import io 
import json 
import streamlit.components.v1 as components 
import plotly.express as px 
import plotly.graph_objects as go   

# --- IMPORTAÇÕES PARA GERAÇÃO NATIVA DE PDF (REPORTLAB) --- 
from reportlab.lib.pagesizes import letter 
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether 
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle 
from reportlab.lib import colors   

# --- CONFIGURAÇÃO DA PÁGINA --- 
st.set_page_config(  
    page_title="Boa Fortuna - Sistema de Sondagem C4 Coring",  
    page_icon="⛏️",  
    layout="wide",  
    initial_sidebar_state="expanded" 
)  

USUARIO_CORRETO = "admin" 
SENHA_CORRETA = "1234" 
DB_NAME = "boafortuna_dados.db"  

# --- ESPECIFICAÇÕES TÉCNICAS DA SONDA C4 CORING ---
BARRILETES_C4_CONFIG = {
    "HQ (Wireline 3.0m)": {"comprimento_m": 3.00, "diametro_mm": 63.5},
    "HQ (Wireline 1.5m)": {"comprimento_m": 1.50, "diametro_mm": 63.5},
    "NQ (Wireline 3.0m)": {"comprimento_m": 3.00, "diametro_mm": 47.6},
    "NQ (Wireline 1.5m)": {"comprimento_m": 1.50, "diametro_mm": 47.6},
    "BQ (Wireline 3.0m)": {"comprimento_m": 3.00, "diametro_mm": 36.5},
    "PQ (Wireline 3.0m)": {"comprimento_m": 3.00, "diametro_mm": 85.0},
    "Convencional HW (1.5m)": {"comprimento_m": 1.50, "diametro_mm": 100.0},
    "Convencional NW (1.5m)": {"comprimento_m": 1.50, "diametro_mm": 75.0}
}

# --- BANCO DE DADOS LOCAL (COM MIGRAÇÃO AUTOMÁTICA) --- 
def init_db():  
    conn = sqlite3.connect(DB_NAME, timeout=10)  
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
            furo_id TEXT UNIQUE,  
            tipo_sondagem TEXT,  
            profundidade_m REAL,  
            observacao TEXT  
        )  
    ''')  
          
    c.execute("PRAGMA table_info(boletins_campo)")  
    colunas_existentes_b = [coluna[1] for coluna in c.fetchall()]  
          
    if "latitude" not in colunas_existentes_b:  
        c.execute("ALTER TABLE boletins_campo ADD COLUMN latitude REAL")  
    if "longitude" not in colunas_existentes_b:  
        c.execute("ALTER TABLE boletins_campo ADD COLUMN longitude REAL")  
    if "precisao_gps_m" not in colunas_existentes_b:  
        c.execute("ALTER TABLE boletins_campo ADD COLUMN precisao_gps_m REAL")  

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
            data_registro TEXT,  
            foto1 BLOB,  
            foto2 BLOB,  
            foto3 BLOB  
        )  
    ''')  

    c.execute("PRAGMA table_info(manobras_testemunho)")
    colunas_existentes_m = [coluna[1] for coluna in c.fetchall()]

    novas_colunas = {
        "data_manobra": "TEXT",
        "avanco_m": "REAL",
        "barrilete": "TEXT",
        "horario_inicio": "TEXT",
        "horario_fim": "TEXT",
        "tempo_manobra": "TEXT",
        "observacoes": "TEXT",
        "operador_sonda": "TEXT"
    }

    for col, tipo in novas_colunas.items():
        if col not in colunas_existentes_m:
            c.execute(f"ALTER TABLE manobras_testemunho ADD COLUMN {col} {tipo}")

    conn.commit()  
    conn.close()  

init_db()  

# --- COMPONENTE DE GEOLOCALIZAÇÃO GPS AUTOMÁTICA VIA BROWSER --- 
def obter_geolocalizacao_gps_auto():  
    componente_js = """  
    <div style="font-family: Arial, sans-serif; text-align: center; padding: 5px;">  
        <p id="status" style="font-size: 13px; color: #0284c7; margin: 0; font-weight: 600;">📡 Buscando sinal GPS automaticamente...</p>  
    </div>  
      
    <script>  
    function capturarGPS() {
        var status = document.getElementById('status');  
        if (!navigator.geolocation) {  
            status.innerText = '❌ Geolocalização não é suportada pelo navegador.';  
            return;  
        }  
        navigator.geolocation.getCurrentPosition(  
            function(pos) {  
                var coords = {  
                    lat: pos.coords.latitude.toFixed(6),  
                    lng: pos.coords.longitude.toFixed(6),  
                    precisao: pos.coords.accuracy.toFixed(1)  
                };  
                status.innerText = '✅ GPS Capturado: ' + coords.lat + ', ' + coords.lng + ' (±' + coords.precisao + 'm)';  
                window.parent.postMessage({  
                    type: 'streamlit:setComponentValue',  
                    value: JSON.stringify(coords)  
                }, '*');  
            },  
            function(err) {  
                status.innerText = '⚠️ Erro ao obter GPS: ' + err.message;  
            },  
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }  
        );  
    }
    
    window.onload = capturarGPS;
    </script>  
    """  
    return components.html(componente_js, height=45)  

# --- AUXILIARES DE IMAGEM --- 
def otimizar_e_converter_bytes(img_pil, max_size=(1024, 1024), quality=80):  
    if img_pil is None:  
        return None  
    img = img_pil.copy()  
    img.thumbnail(max_size, Image.Resampling.LANCZOS)  
    if img.mode in ("RGBA", "P"):  
        img = img.convert("RGB")  
    buffer = io.BytesIO()  
    img.save(buffer, format="JPEG", quality=quality, optimize=True)  
    return buffer.getvalue()  

def bytes_para_pil(dados_blob):  
    if dados_blob is None:  
        return None  
    try:  
        return Image.open(io.BytesIO(dados_blob))  
    except Exception:  
        return None  

# --- MANIPULAÇÃO DO BANCO DE DADOS --- 
def sincronizar_boletim_automatico(furo_id, prof_atingida):  
    conn = sqlite3.connect(DB_NAME, timeout=10)  
    c = conn.cursor()  
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")  
          
    empresa = st.session_state.get("empresa", "Boa Fortuna Perfurações")  
    obra = st.session_state.get("obra", "Não informada")  
    cidade = st.session_state.get("cidade", "-")  
    coordenador = st.session_state.get("coordenador", "-")  
    supervisor = st.session_state.get("supervisor", "-")  
    sondador = st.session_state.get("sondador", "-")  
    auxiliares = st.session_state.get("auxiliares", "-")  
    tipo_sondagem = st.session_state.get("tipo_sondagem", "Rotativa C4 Coring")  
    lat = st.session_state.get("latitude", None)  
    lng = st.session_state.get("longitude", None)  
    precisao = st.session_state.get("precisao_gps", None)  
          
    c.execute('SELECT id, profundidade_m FROM boletins_campo WHERE furo_id = ?', (furo_id,))  
    existe = c.fetchone()  
          
    if existe:  
        c.execute('''  
            UPDATE boletins_campo  
            SET profundidade_m = max(profundidade_m, ?),  
                empresa = CASE WHEN ? != 'Boa Fortuna Perfurações' THEN ? ELSE empresa END,  
                obra_cliente = CASE WHEN ? != 'Não informada' THEN ? ELSE obra_cliente END,  
                cidade_uf = CASE WHEN ? != '-' THEN ? ELSE cidade_uf END,  
                sondador = CASE WHEN ? != '-' THEN ? ELSE sondador END,  
                coordenador = CASE WHEN ? != '-' THEN ? ELSE coordenador END,  
                supervisor = CASE WHEN ? != '-' THEN ? ELSE supervisor END,  
                auxiliares = CASE WHEN ? != '-' THEN ? ELSE auxiliares END,  
                latitude = COALESCE(?, latitude),  
                longitude = COALESCE(?, longitude),  
                precisao_gps_m = COALESCE(?, precisao_gps_m),  
                data_registro = ?  
            WHERE furo_id = ?  
        ''', (  
            prof_atingida, empresa, empresa, obra, obra, cidade, cidade,  
            sondador, sondador, coordenador, coordenador, supervisor, supervisor,  
            auxiliares, auxiliares, lat, lng, precisao, data_atual, furo_id  
        ))  
    else:  
        c.execute('''  
            INSERT INTO boletins_campo  
            (data_registro, empresa, obra_cliente, cidade_uf, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, profundidade_m, latitude, longitude, precisao_gps_m, observacao)  
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  
        ''', (data_atual, empresa, obra, cidade, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, prof_atingida, lat, lng, precisao, "Sincronizado via C4 Coring"))  
          
    conn.commit()  
    conn.close()  

def salvar_manobra(furo, data_m, de, ate, avanco, recup, taxa, caixa, barrilete, h_inicio, h_fim, tempo_man, litologia, observacoes, operador, h_trab=1.0, h_parado=0.0, motivo="Nenhum", fotos_pil=None):  
    conn = sqlite3.connect(DB_NAME, timeout=10)  
    c = conn.cursor()  
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")  
          
    f1 = otimizar_e_converter_bytes(fotos_pil[0]) if fotos_pil and len(fotos_pil) > 0 else None  
    f2 = otimizar_e_converter_bytes(fotos_pil[1]) if fotos_pil and len(fotos_pil) > 1 else None  
    f3 = otimizar_e_converter_bytes(fotos_pil[2]) if fotos_pil and len(fotos_pil) > 2 else None  
      
    c.execute('''  
        INSERT INTO manobras_testemunho  
        (furo_id, data_manobra, de_m, ate_m, avanco_m, recup_m, taxa_recup_pct, num_caixa, barrilete, horario_inicio, horario_fim, tempo_manobra, descricao_litologica, observacoes, operador_sonda, horas_trab, horas_parado, horario, motivo_parada, data_registro, foto1, foto2, foto3)  
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  
    ''', (furo, str(data_m), de, ate, avanco, recup, taxa, caixa, barrilete, str(h_inicio), str(h_fim), tempo_man, litologia, observacoes, operador, h_trab, h_parado, f"{h_inicio} - {h_fim}", motivo, data_atual, f1, f2, f3))  
    conn.commit()  
    conn.close()  
    sincronizar_boletim_automatico(furo, ate)  

def deletar_manobra(manobra_id):  
    conn = sqlite3.connect(DB_NAME, timeout=10)  
    c = conn.cursor()  
    c.execute('DELETE FROM manobras_testemunho WHERE id = ?', (manobra_id,))  
    conn.commit()  
    conn.close()  

def buscar_manobras(furo_id=None):  
    conn = sqlite3.connect(DB_NAME, timeout=10)  
    c = conn.cursor()  
    if furo_id:  
        c.execute('''
            SELECT id, furo_id, data_manobra, de_m, ate_m, avanco_m, recup_m, taxa_recup_pct, 
                   num_caixa, barrilete, horario_inicio, horario_fim, tempo_manobra, 
                   descricao_litologica, observacoes, operador_sonda, foto1, foto2, foto3, horas_trab, horas_parado
            FROM manobras_testemunho 
            WHERE furo_id = ? ORDER BY id ASC
        ''', (furo_id,))  
    else:  
        c.execute('''
            SELECT id, furo_id, data_manobra, de_m, ate_m, avanco_m, recup_m, taxa_recup_pct, 
                   num_caixa, barrilete, horario_inicio, horario_fim, tempo_manobra, 
                   descricao_litologica, observacoes, operador_sonda, data_registro, horas_trab, horas_parado
            FROM manobras_testemunho ORDER BY id DESC
        ''')  
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
        .stApp { background: linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%); }  
        div[data-testid="stForm"] {  
            background-color: #ffffff; padding: 40px; border-radius: 12px;  
            box-shadow: 0px 10px 25px rgba(0, 0, 0, 0.3); border: none;  
        }  
        div[data-testid="stForm"] button {  
            background-color: #1E3A8A !important; color: white !important;  
            font-weight: 600 !important; border-radius: 6px !important; width: 100% !important;  
            height: 45px !important; border: none !important; font-size: 15px !important;  
        }  
        #MainMenu, footer, header { visibility: hidden; }  
        </style>  
    """, unsafe_allow_html=True)  
      
    col1, col2, col3 = st.columns([1, 1.2, 1])  
    with col2:  
        st.write("<br><br>", unsafe_allow_html=True)  
        st.markdown("<h1 style='text-align: center; color: #ffffff; margin-bottom: 0px; font-weight: 800; font-size: 38px;'>BOA FORTUNA</h1>", unsafe_allow_html=True)  
        st.markdown("<p style='text-align: center; color: #93C5FD; font-size: 12px; letter-spacing: 3px; margin-bottom: 30px; text-transform: uppercase;'>Perfurações C4 Coring & Geotécnica</p>", unsafe_allow_html=True)  
          
        with st.form("login_form"):  
            st.markdown("<h4 style='text-align: center; color: #1E3A8A;'>Acesso Restrito</h4>", unsafe_allow_html=True)  
            user_input = st.text_input("Usuário", placeholder="Digite seu usuário")  
            pass_input = st.text_input("Senha", type="password", placeholder="Digite sua senha")  
            btn_entrar = st.form_submit_button("Acessar Painel")  
              
            if btn_entrar:  
                if user_input == USUARIO_CORRETO and pass_input == SENHA_CORRETA:  
                    st.session_state.logado = True  
                    st.rerun()  
                else:  
                    st.error("Credenciais inválidas. Tente novamente.")  

# --- PAINEL PRINCIPAL --- 
else:  
    st.markdown("""  
        <style>  
        .stApp { background-color: #F8FAFC; }  
        div[data-testid="stSidebar"] { background-color: #0F172A; }  
        div[data-testid="stSidebar"] * { color: #F8FAFC !important; }  
        h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #1E3A8A; font-weight: 700; }  
        div.stButton > button {  
            background-color: #1E3A8A !important; color: #ffffff !important;  
            border-radius: 6px !important; border: none !important; font-weight: 600 !important;  
        }  
        div.stButton > button:hover { background-color: #2563EB !important; }  
        #MainMenu, footer, header { visibility: hidden; }  
        </style>  
    """, unsafe_allow_html=True)  
      
    st.sidebar.markdown("<h2 style='color: #60A5FA !important; margin-bottom: 0px;'>BOA FORTUNA</h2>", unsafe_allow_html=True)  
    st.sidebar.markdown(f"<p style='font-size: 12px; color: #94A3B8 !important;'>Sonda: <b>C4 CORING</b> | Operador: <b>{USUARIO_CORRETO.upper()}</b></p>", unsafe_allow_html=True)  
          
    st.sidebar.divider()  
    st.sidebar.markdown("**Módulos do Sistema**")  
          
    opcao = st.sidebar.radio(  
        "Selecione a etapa:",  
        [  
            "1. Cabeçalho e Empresa",  
            "2. Equipe de Campo",  
            "3. Registro de Manobra e Testemunho (C4 Coring)",  
            "4. Fechamento de Turno & Dashboard"  
        ],  
        label_visibility="collapsed"  
    )  
      
    st.sidebar.divider()  
    if st.sidebar.button("Sair da Conta", use_container_width=True):  
        st.session_state.logado = False  
        st.rerun()  

    # ETAPA 1  
    if opcao == "1. Cabeçalho e Empresa":  
        st.title("1. Cabeçalho de Identificação & GPS da Praça")  
        st.caption("Informações institucionais e georreferenciamento automático da praça de sondagem.")  
                  
        st.markdown("### 🗺️ Localização Geográfica da Praça (Automática)")  
        
        gps_json = obter_geolocalizacao_gps_auto()  
        if gps_json:  
            try:  
                coords = json.loads(gps_json)  
                lat_nova = float(coords["lat"])
                lng_nova = float(coords["lng"])
                prec_nova = float(coords["precisao"])

                if st.session_state.get("latitude") != lat_nova:
                    st.session_state["latitude"] = lat_nova
                    st.session_state["longitude"] = lng_nova
                    st.session_state["precisao_gps"] = prec_nova
                    st.rerun()
            except Exception:  
                pass  
          
        col_gps1, col_gps2, col_gps3 = st.columns(3)  
        lat_val = st.session_state.get("latitude", "")  
        lng_val = st.session_state.get("longitude", "")  
        acc_val = st.session_state.get("precisao_gps", "")  
                      
        col_gps1.text_input("Latitude", value=str(lat_val) if lat_val != "" else "Aguardando GPS...", key="lat_input", disabled=True)  
        col_gps2.text_input("Longitude", value=str(lng_val) if lng_val != "" else "Aguardando GPS...", key="lng_input", disabled=True)  
        col_gps3.text_input("Precisão (m)", value=f"{acc_val} m" if acc_val != "" else "Aguardando...", key="acc_input", disabled=True)  
          
        st.divider()  
          
        with st.form("form_cabecalho"):  
            col1, col2 = st.columns(2)  
            with col1:  
                st.session_state["empresa"] = st.text_input("Empresa Executora", value=st.session_state.get("empresa", "Boa Fortuna Perfurações e Sondagens"))  
                st.session_state["obra"] = st.text_input("Cliente / Nome da Obra", value=st.session_state.get("obra", ""))  
            with col2:  
                st.session_state["cidade"] = st.text_input("Cidade / UF", value=st.session_state.get("cidade", ""))  
                st.session_state["data_campo"] = st.date_input("Data do Ensaio", value=st.session_state.get("data_campo", date.today()))  
                          
            if st.form_submit_button("Salvar Identificação"):  
                st.success("Dados do cabeçalho salvos com sucesso!")  

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
              
            if st.form_submit_button("Salvar Equipe"):  
                st.success("Dados da equipe salvos com sucesso!")  

    # ETAPA 3 - AUTOMAÇÃO C4 CORING
    elif opcao == "3. Registro de Manobra e Testemunho (C4 Coring)":  
        st.title("3. Registro Automatizado de Manobra - Sonda C4 Coring")  
        st.caption("Automação baseada na extensão das hastes e barrilete da C4 Coring.")  
                  
        furo_atual = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", "F-01"), key="input_furo_manobra")  
        st.session_state["furo_id"] = furo_atual  
          
        manobras_furo = buscar_manobras(furo_atual)  
        
        # 1. AUTOMAÇÃO DA PROFUNDIDADE INICIAL (DE)
        prox_de = round(manobras_furo[-1][4], 2) if manobras_furo else 0.0  
        
        c1, c2, c3 = st.columns(3)
        with c1:
            data_manobra = st.date_input("Data", value=date.today())
        with c2:
            # Seleção técnica do barrilete da C4 Coring
            barrilete_sel = st.selectbox("Barrilete / Hastes C4 Coring", list(BARRILETES_C4_CONFIG.keys()), index=0)
            comprimento_barrilete = BARRILETES_C4_CONFIG[barrilete_sel]["comprimento_m"]
        with c3:
            operador_sonda = st.text_input("Sondador Operador", value=st.session_state.get("sondador", "Sondador C4"))

        # 2. AUTOMAÇÃO DA PROFUNDIDADE FINAL (ATÉ) BASEADA NO COMPRIMENTO DA HASTE/BARRILETE
        prox_ate = round(prox_de + comprimento_barrilete, 2)

        st.info(f"📍 **Profundidade Atual (De):** `{prox_de:.2f} m` | **Avanço Teórico da Manobra:** `{comprimento_barrilete:.2f} m` | **Previsão Final (Até):** `{prox_ate:.2f} m`")

        c4, c5, c6, c7 = st.columns(4)  
        with c4:  
            de_m = st.number_input("Profundidade Inicial 'De' (m)", min_value=0.0, step=0.1, value=float(prox_de), format="%.2f")  
        with c5:  
            ate_m = st.number_input("Profundidade Final 'Até' (m)", min_value=float(de_m), step=0.1, value=float(prox_ate), format="%.2f")  
        
        # CÁLCULO AUTOMÁTICO DO AVANÇO REAL
        avanco_calc = round(max(0.0, ate_m - de_m), 2)

        with c6:  
            # Recuperação limitada dinamicamente ao avanco_calc
            recup_m = st.number_input("Recuperação Medida (m)", min_value=0.0, max_value=float(avanco_calc) if avanco_calc > 0 else 0.01, step=0.05, value=float(avanco_calc), format="%.2f")  
        with c7:  
            num_caixa = st.text_input("Caixa Nº", value=manobras_furo[-1][8] if manobras_furo else "CX-01")  

        # CÁLCULO AUTOMÁTICO DA TAXA DE RECUPERAÇÃO %
        taxa_recup = round((recup_m / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0  

        # Exibição dos indicadores
        st.markdown(f"""
        <div style="background-color: #EFF6FF; padding: 12px; border-radius: 8px; border-left: 5px solid #1E3A8A; margin-bottom: 15px;">
            <span style="font-size: 16px; color: #1E3A8A; font-weight: bold;">⚡ Avanço Real Calculado: {avanco_calc:.2f} m</span> &nbsp;|&nbsp; 
            <span style="font-size: 16px; color: {'#16A34A' if taxa_recup >= 85 else '#D97706'}; font-weight: bold;">📊 Taxa de Recuperação: {taxa_recup:.1f}%</span>
        </div>
        """, unsafe_allow_html=True)

        # AUTOMAÇÃO DE TEMPOS E HORÁRIOS
        hora_atual = datetime.now().time()
        hora_inicio_padrao = (datetime.now() - timedelta(minutes=45)).time() if not manobras_furo else datetime.now().time()

        c8, c9, c10 = st.columns(3)
        with c8:
            horario_inicio = st.time_input("Horário Início", value=hora_inicio_padrao)
        with c9:
            horario_fim = st.time_input("Horário Fim", value=hora_atual)
            
        dt_ini = datetime.combine(date.today(), horario_inicio)
        dt_fim = datetime.combine(date.today(), horario_fim)
        
        if dt_fim < dt_ini:
            dt_fim += timedelta(days=1)
            
        diferenca_segundos = (dt_fim - dt_ini).total_seconds()
        horas_trabalhadas = round(diferenca_segundos / 3600.0, 2)
        minutos_totais = int(diferenca_segundos // 60)
        tempo_manobra_auto = f"{minutos_totais // 60:02d}h {minutos_totais % 60:02d}m"

        with c10:
            st.text_input("Duração da Manobra", value=tempo_manobra_auto, disabled=True)

        c11, c12, c13 = st.columns(3)
        with c11:
            desc_litologica = st.text_input("Litologia / ROCHA", placeholder="Ex: Basalto, Filito, Alteração de rocha...")  
        with c12:
            observacoes = st.text_input("Observações de Operação", placeholder="Ex: Queda de pressão de água, manobra livre...")  
        with c13:
            horas_paradas = st.number_input("Horas Paradas (Interrupções)", min_value=0.0, step=0.25, value=0.0)

        st.markdown("---")  
        st.subheader("📷 Registro Fotográfico da Caixa / Testemunho")  
                    
        tab_galeria, tab_camera = st.tabs(["📁 Selecionar da Galeria", "📸 Câmera ao Vivo"])  
        fotos_manobra_pil = []  
                    
        with tab_galeria:  
            fotos_upload = st.file_uploader("Upload de fotos da manobra", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="upl_manobra")
