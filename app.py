import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
from PIL import Image
import io
import json
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Boa Fortuna - Sistema de Sondagem",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
            furo_id TEXT UNIQUE,
            tipo_sondagem TEXT,
            profundidade_m REAL,
            latitude REAL,
            longitude REAL,
            precisao_gps_m REAL,
            observacao TEXT
        )
    ''')
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
    conn.commit()
    conn.close()

init_db()

# --- COMPONENTE DE GEOLOCALIZAÇÃO GPS VIA HTML5 ---
def obter_geolocalizacao_gps():
    """Renderiza um componente HTML/JS para acessar a API de Geolocalização do navegador."""
    componente_js = """
    <div style="font-family: Arial, sans-serif; text-align: center;">
        <button id="btnGps" type="button" style="
            background-color: #059669;
            color: white;
            border: none;
            padding: 10px 18px;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">📍 Capturar Localização Exata (GPS)</button>
        <p id="status" style="font-size: 12px; color: #64748b; margin-top: 6px; font-weight: 500;"></p>
    </div>

    <script>
    document.getElementById('btnGps').addEventListener('click', function() {
        var status = document.getElementById('status');
        if (!navigator.geolocation) {
            status.innerText = '❌ Geolocalização não é suportada pelo seu navegador.';
            return;
        }
        status.innerText = '⏳ Conectando aos satélites/GPS...';
        
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                var coords = {
                    lat: pos.coords.latitude.toFixed(6),
                    lng: pos.coords.longitude.toFixed(6),
                    precisao: pos.coords.accuracy.toFixed(1)
                };
                status.innerText = '✅ Coordenadas Obtidas com Sucesso!';
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: JSON.stringify(coords)
                }, '*');
            },
            function(err) {
                status.innerText = '⚠️ Erro ao obter GPS: ' + err.message;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    });
    </script>
    """
    return components.html(componente_js, height=85)

# --- AUXILIARES PARA TRATAMENTO DE IMAGEM ---
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

# --- MANIPULAÇÃO DE BANCO DE DADOS ---
def sincronizar_boletim_automatico(furo_id, prof_atingida):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    empresa = st.session_state.get("empresa", "Boa Fortuna Perfurações")
    obra = st.session_state.get("obra", "Não informada")
    cidade = st.session_state.get("cidade", "-")
    coordenador = st.session_state.get("coordenador", "-")
    supervisor = st.session_state.get("supervisor", "-")
    sondador = st.session_state.get("sondador", "-")
    auxiliares = st.session_state.get("auxiliares", "-")
    tipo_sondagem = st.session_state.get("tipo_sondagem", "Rotativa")
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
        ''', (data_atual, empresa, obra, cidade, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, prof_atingida, lat, lng, precisao, "Sincronizado via manobras"))
    
    conn.commit()
    conn.close()

def salvar_boletim(empresa, obra, cidade, coord, superv, sond, aux, furo, tipo, prof, lat, lng, prec, obs):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''
        INSERT INTO boletins_campo 
        (data_registro, empresa, obra_cliente, cidade_uf, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, profundidade_m, latitude, longitude, precisao_gps_m, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(furo_id) DO UPDATE SET
            empresa=excluded.empresa, obra_cliente=excluded.obra_cliente, cidade_uf=excluded.cidade_uf,
            coordenador=excluded.coordenador, supervisor=excluded.supervisor, sondador=excluded.sondador,
            auxiliares=excluded.auxiliares, tipo_sondagem=excluded.tipo_sondagem, profundidade_m=excluded.profundidade_m,
            latitude=COALESCE(excluded.latitude, latitude), longitude=COALESCE(excluded.longitude, longitude),
            precisao_gps_m=COALESCE(excluded.precisao_gps_m, precisao_gps_m),
            observacao=excluded.observacao, data_registro=excluded.data_registro
    ''', (data_atual, empresa, obra, cidade, coord, superv, sond, aux, furo, tipo, prof, lat, lng, prec, obs))
    conn.commit()
    conn.close()

def salvar_manobra(furo, de, ate, recup, taxa, caixa, h_trab, h_parado, horario, motivo, desc, fotos_pil=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    f1 = otimizar_e_converter_bytes(fotos_pil[0]) if fotos_pil and len(fotos_pil) > 0 else None
    f2 = otimizar_e_converter_bytes(fotos_pil[1]) if fotos_pil and len(fotos_pil) > 1 else None
    f3 = otimizar_e_converter_bytes(fotos_pil[2]) if fotos_pil and len(fotos_pil) > 2 else None

    c.execute('''
        INSERT INTO manobras_testemunho
        (furo_id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, horas_trab, horas_parado, horario, motivo_parada, descricao_litologica, data_registro, foto1, foto2, foto3)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (furo, de, ate, recup, taxa, caixa, h_trab, h_parado, horario, motivo, desc, data_atual, f1, f2, f3))
    conn.commit()
    conn.close()
    
    sincronizar_boletim_automatico(furo, ate)

def deletar_manobra(manobra_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM manobras_testemunho WHERE id = ?', (manobra_id,))
    conn.commit()
    conn.close()

def buscar_manobras(furo_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if furo_id:
        c.execute('SELECT id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, horas_trab, horas_parado, descricao_litologica, foto1, foto2, foto3 FROM manobras_testemunho WHERE furo_id = ? ORDER BY id ASC', (furo_id,))
    else:
        c.execute('SELECT id, furo_id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, descricao_litologica, data_registro FROM manobras_testemunho ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

def buscar_dados_furo(furo_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT latitude, longitude, precisao_gps_m FROM boletins_campo WHERE furo_id = ?', (furo_id,))
    res = c.fetchone()
    conn.close()
    return res if res else (None, None, None)

# --- GERADOR DE RELATÓRIO HTML IMPRESSÍVEL ---
def gerar_html_boletim(furo_id, obs_fechamento=""):
    empresa = st.session_state.get("empresa", "Boa Fortuna Perfurações e Sondagens")
    obra = st.session_state.get("obra", "-")
    cidade = st.session_state.get("cidade", "-")
    sondador = st.session_state.get("sondador", "-")
    coordenador = st.session_state.get("coordenador", "-")
    data_campo = str(st.session_state.get("data_campo", date.today()))
    
    lat_db, lng_db, prec_db = buscar_dados_furo(furo_id)
    lat = st.session_state.get("latitude", lat_db or "Não informada")
    lng = st.session_state.get("longitude", lng_db or "Não informada")
    
    coord_str = f"Lat: {lat} | Lng: {lng}" if lat != "Não informada" else "Não informada"
    
    manobras = buscar_manobras(furo_id)
    linhas_tabela = ""
    for m in manobras:
        de, ate, rec, rec_pct, caixa, desc = m[1], m[2], m[3], m[4], m[5], m[8]
        avanc = round(ate - de, 2)
        linhas_tabela += f"""
        <tr>
            <td>{de:.2f}</td>
            <td>{ate:.2f}</td>
            <td>{avanc:.2f}</td>
            <td>{rec:.2f}</td>
            <td><b>{rec_pct:.1f}%</b></td>
            <td>{caixa}</td>
            <td style='text-align:left;'>{desc or '-'}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Boletim Diário de Sondagem - {furo_id}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; color: #1e293b; }}
            .header {{ text-align: center; border-bottom: 3px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 20px; }}
            .header h2 {{ color: #1E3A8A; margin: 0; font-size: 24px; text-transform: uppercase; }}
            .header h4 {{ color: #64748b; margin: 5px 0 0 0; font-weight: 500; }}
            .box-info {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; background: #f8fafc; border-radius: 6px; overflow: hidden; }}
            .box-info td {{ padding: 10px 12px; border: 1px solid #e2e8f0; font-size: 13px; }}
            .tabela-dados {{ width: 100%; border-collapse: collapse; margin-top: 10px; text-align: center; }}
            .tabela-dados th {{ background: #1E3A8A; color: white; padding: 10px; font-size: 12px; text-transform: uppercase; }}
            .tabela-dados td {{ padding: 8px; border: 1px solid #e2e8f0; font-size: 12px; }}
            .tabela-dados tr:nth-child(even) {{ background-color: #f8fafc; }}
            .obs {{ margin-top: 20px; padding: 15px; border-left: 4px solid #1E3A8A; background: #f1f5f9; font-size: 13px; border-radius: 0 6px 6px 0; }}
            .footer {{ margin-top: 40px; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>{empresa}</h2>
            <h4>BOLETIM DIÁRIO DE SONDAGEM (BDS) • IDENTIFICAÇÃO: {furo_id}</h4>
        </div>
        
        <table class="box-info">
            <tr>
                <td><b>Cliente/Obra:</b> {obra}</td>
                <td><b>Cidade/UF:</b> {cidade}</td>
                <td><b>Data do Ensaio:</b> {data_campo}</td>
            </tr>
            <tr>
                <td><b>Sondador Resp.:</b> {sondador}</td>
                <td><b>Coordenador:</b> {coordenador}</td>
                <td><b>GPS:</b> {coord_str}</td>
            </tr>
        </table>

        <h3 style="color:#1E3A8A; font-size: 16px; margin-bottom: 8px;">Avanço e Recuperação de Testemunhos</h3>
        <table class="tabela-dados">
            <thead>
                <tr>
                    <th>De (m)</th>
                    <th>Até (m)</th>
                    <th>Avanço (m)</th>
                    <th>Recup. (m)</th>
                    <th>Recup. (%)</th>
                    <th>Caixa</th>
                    <th>Descrição Litológica</th>
                </tr>
            </thead>
            <tbody>
                {linhas_tabela}
            </tbody>
        </table>

        <div class="obs">
            <b>Observações de Fechamento de Turno:</b><br>{obs_fechamento or 'Nenhuma observação informada.'}
        </div>

        <div class="footer">
            Relatório gerado automaticamente via Sistema Boa Fortuna - Processado em {datetime.now().strftime("%d/%m/%Y às %H:%M")}
        </div>
    </body>
    </html>
    """
    return html

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
        st.markdown("<p style='text-align: center; color: #93C5FD; font-size: 12px; letter-spacing: 3px; margin-bottom: 30px; text-transform: uppercase;'>Perfurações e Sondagens Geotécnicas</p>", unsafe_allow_html=True)

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
    st.sidebar.markdown(f"<p style='font-size: 12px; color: #94A3B8 !important;'>Operador: <b>{USUARIO_CORRETO.upper()}</b></p>", unsafe_allow_html=True)
    
    st.sidebar.divider()
    st.sidebar.markdown("**Módulos do Sistema**")
    
    opcao = st.sidebar.radio(
        "Selecione a etapa:",
        [
            "1. Cabeçalho e Empresa",
            "2. Equipe de Campo",
            "3. Registro de Manobra e Testemunho",
            "4. Fechamento de Turno & Dashboard",
            "5. Dados do Furo & Perfuração"
        ],
        label_visibility="collapsed"
    )

    st.sidebar.divider()
    if st.sidebar.button("Sair da Conta", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

    # ETAPA 1
    if opcao == "1. Cabeçalho e Empresa":
        st.title("1. Cabeçalho de Identificação & Localização")
        st.caption("Informações institucionais e georreferenciamento do furo.")
        
        st.markdown("### 🗺️ Localização Geográfica do Furo (GPS)")
        col_gps1, col_gps2 = st.columns([1, 2])
        
        with col_gps1:
            gps_json = obter_geolocalizacao_gps()
            if gps_json:
                try:
                    coords = json.loads(gps_json)
                    st.session_state["latitude"] = float(coords["lat"])
                    st.session_state["longitude"] = float(coords["lng"])
                    st.session_state["precisao_gps"] = float(coords["precisao"])
                except Exception:
                    pass

        with col_gps2:
            c_lat, c_lng, c_acc = st.columns(3)
            lat_val = st.session_state.get("latitude", "")
            lng_val = st.session_state.get("longitude", "")
            acc_val = st.session_state.get("precisao_gps", "")
            
            c_lat.text_input("Latitude", value=str(lat_val) if lat_val else "", key="lat_input")
            c_lng.text_input("Longitude", value=str(lng_val) if lng_val else "", key="lng_input")
            c_acc.text_input("Precisão (m)", value=f"{acc_val} m" if acc_val else "", key="acc_input")

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
                st.success("Dados do cabeçalho e geolocalização salvos na sessão!")

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

    # ETAPA 3
    elif opcao == "3. Registro de Manobra e Testemunho":
        st.title("3. Registro de Manobra e Testemunho")
        st.caption("Lançamento do avanço, recuperação de amostra, caixas e registro fotográfico de campo.")
        
        furo_atual = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", "SP-01"), key="input_furo_manobra")
        st.session_state["furo_id"] = furo_atual

        manobras_furo = buscar_manobras(furo_atual)
        prox_de = manobras_furo[-1][2] if manobras_furo else 0.0
        prox_ate = round(prox_de + 1.5, 2)
        
        st.info(f"📍 Profundidade Atual Perfurada para o Furo **{furo_atual}**: **{prox_de:.2f} m**")

        with st.form("form_manobra"):
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                de_m = st.number_input("De (m)", min_value=0.0, step=0.5, value=float(prox_de), format="%.2f")
            with col2:
                ate_m = st.number_input("Até (m)", min_value=0.0, step=0.5, value=float(prox_ate), format="%.2f")
            with col3:
                recup_m = st.number_input("Recup. (m)", min_value=0.0, step=0.1, value=round(max(0.0, ate_m - de_m), 2), format="%.2f")
            with col4:
                num_caixa = st.text_input("Nº da Caixa", value=manobras_furo[-1][5] if manobras_furo else "01")
            with col5:
                horas_trab = st.number_input("Horas Trab.", min_value=0.0, step=0.5, value=1.0, format="%.1f")
            with col6:
                horas_parado = st.number_input("Horas Parado", min_value=0.0, step=0.5, value=0.0, format="%.1f")

            avancamento = round(ate_m - de_m, 2)
            taxa_recup = min(100.0, round((recup_m / avancamento * 100), 1)) if avancamento > 0 else 0.0
            
            st.caption(f"⚡ **Avanço Calculado:** {avancamento:.2f} m | **Taxa de Recuperação Esperada:** {taxa_recup:.1f}%")

            col7, col8, col9 = st.columns([1, 1, 2])
            with col7:
                horario = st.text_input("Horário", placeholder="Ex: 08:00 - 09:30")
            with col8:
                motivo_parada = st.text_input("Motivo Parada", value="Nenhuma")
            with col9:
                desc_litologica = st.text_input("Descrição Litológica", placeholder="Ex: Solo residual, rocha alterada...")

            st.markdown("---")
            st.subheader("Registro Fotográfico (Até 3 Fotos)")
            
            tab_galeria, tab_camera = st.tabs(["📁 Selecionar da Galeria", "📸 Câmera ao Vivo"])
            fotos_manobra_pil = []
            
            with tab_galeria:
                fotos_upload = st.file_uploader("Upload de imagens de campo", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                if fotos_upload:
                    for f in fotos_upload[:3]:
                        fotos_manobra_pil.append(Image.open(f))
            
            with tab_camera:
                foto_cam = st.camera_input("Capturar foto do testemunho/caixa")
                if foto_cam and len(fotos_manobra_pil) < 3:
                    fotos_manobra_pil.append(Image.open(foto_cam))

            btn_salvar_manobra = st.form_submit_button("Adicionar Manobra", use_container_width=True)

            if btn_salvar_manobra:
                if ate_m > de_m:
                    salvar_manobra(furo_atual, de_m, ate_m, recup_m, taxa_recup, num_caixa, horas_trab, horas_parado, horario, motivo_parada, desc_litologica, fotos_manobra_pil)
                    st.success(f"Manobra de {de_m:.2f}m a {ate_m:.2f}m salva com sucesso!")
                    st.rerun()
                else:
                    st.error("A profundidade final 'Até (m)' precisa ser obrigatoriamente maior que 'De (m)'.")

        st.divider()
        st.subheader(f"Histórico de Manobras: {furo_atual}")

        if manobras_furo:
            dados_tabela = []
            for row in manobras_furo:
                m_id, de, ate, rec, rec_pct, caixa, h_tr, h_par, desc = row[0], row[1] or 0.0, row[2] or 0.0, row[3] or 0.0, row[4] or 0.0, row[5], row[6] or 0.0, row[7] or 0.0, row[8]
                avanc = round(ate - de, 2)
                dados_tabela.append([m_id, de, ate, avanc, rec, f"{rec_pct:.1f}%", caixa, h_tr, h_par, desc])

            df_manobras = pd.DataFrame(
                dados_tabela, 
                columns=["ID", "De (m)", "Até (m)", "Avanço (m)", "Recup (m)", "Recup (%)", "Caixa", "H. Trab", "H. Parado", "Litologia"]
            )
            st.dataframe(df_manobras, use_container_width=True)

            col_excluir, col_btn = st.columns([3, 1])
            with col_excluir:
                opcoes_manobra = {f"ID #{row[0]} | De {row[1]:.2f}m até {row[2]:.2f}m": row[0] for row in manobras_furo}
                manobra_selecionada = st.selectbox("Selecione uma manobra para remover:", list(opcoes_manobra.keys()))
            
            with col_btn:
                st.write("<br>", unsafe_allow_html=True)
                if st.button("Excluir Manobra", use_container_width=True):
                    id_para_deletar = opcoes_manobra[manobra_selecionada]
                    deletar_manobra(id_para_deletar)
                    st.success("Manobra removida!")
                    st.rerun()
        else:
            st.info("Nenhuma manobra cadastrada para este furo até o momento.")

    # ETAPA 4 - DASHBOARD EXECUTIVO E PERFIL ESTRATIGRÁFICO
    elif opcao == "4. Fechamento de Turno & Dashboard":
        st.title("4. Dashboard Executivo & Perfil Geotécnico")
        st.caption("Análise estratigráfica vertical, indicadores de performance e emissão de boletim.")

        furo_fechamento = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", "SP-01"))
        manobras = buscar_manobras(furo_fechamento)

        if manobras:
            total_avanco = sum([m[2] - m[1] for m in manobras])
            total_recup = sum([m[3] for m in manobras])
            total_h_trab = sum([m[6] for m in manobras if m[6] is not None])
            total_h_parado = sum([m[7] for m in manobras if m[7] is not None])
            taxa_media = (total_recup / total_avanco * 100) if total_avanco > 0 else 0.0

            st.subheader("📊 Indicadores Principais (KPIs)")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Avanço Acumulado", f"{total_avanco:.2f} m")
            col_m2.metric("Recuperação Média", f"{taxa_media:.1f}%")
            col_m3.metric("Horas em Operação", f"{total_h_trab:.1f} h")
            col_m4.metric("Horas Improdutivas", f"{total_h_parado:.1f} h")

            st.divider()

            # --- ANÁLISE GRÁFICA & PERFIL ESTRATIGRÁFICO VERTICAL ---
            st.subheader("🔬 Perfil Geotécnico & Estratigrafia do Furo")

            dados_grafico = []
            for m in manobras:
                de, ate, rec, rec_pct, caixa, h_tr, h_par, desc = m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]
                avanc = round(ate - de, 2)
                intervalo = f"{de:.2f}m - {ate:.2f}m"
                dados_grafico.append({
                    "Intervalo": intervalo,
                    "De (m)": de,
                    "Até (m)": ate,
                    "Avanço (m)": avanc,
                    "Recuperação (m)": rec,
                    "Recuperação (%)": rec_pct,
                    "Caixa": caixa,
                    "Horas Trab": h_tr or 0,
                    "Horas Parado": h_par or 0,
                    "Litologia": desc or "Litologia não informada"
                })

            df_g = pd.DataFrame(dados_grafico)

            col_g1, col_g2 = st.columns([1.2, 1])

            with col_g1:
                # Perfil Litológico Vertical
                fig_perfil = go.Figure()
                for idx, row in df_g.iterrows():
                    fig_perfil.add_trace(go.Bar(
                        x=[row["Avanço (m)"]],
                        y=[f"{row['De (m)']:.1f}m a {row['Até (m)']:.1f}m"],
                        orientation='h',
                        name=row["Litologia"],
                        text=f"{row['Litologia']} (Rec: {row['Recuperação (%)']}%)",
                        textposition='inside',
                        hovertemplate=f"<b>{row['Litologia']}</b><br>Intervalo: {row['De (m)']}m - {row['Até (m)']}m<br>Recuperação: {row['Recuperação (%)']}%<extra></extra>"
                    ))

                fig_perfil.update_layout(
                    title="<b>Perfil Estratigráfico Vertical (Avanço & Litologia)</b>",
                    xaxis_title="Avanço Perfurado (m)",
                    yaxis_title="Profundidade do Furo",
                    yaxis=dict(autorange="reversed"),
                    barmode='stack',
                    showlegend=False,
                    height=450,
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig_perfil, use_container_width=True)

            with col_g2:
                # Gráfico de Rosca de Produtividade Operacional
                fig_horas = px.pie(
                    names=["Horas Trabalhadas", "Horas Paradas"],
                    values=[total_h_trab, total_h_parado],
                    title="<b>Distribuição do Tempo de Sondagem</b>",
                    hole=0.5,
                    color_discrete_sequence=["#1E3A8A", "#EF4444"]
                )
                fig_horas.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=450)
                st.plotly_chart(fig_horas, use_container_width=True)

            st.divider()

            # --- GALERIA FOTOGRÁFICA ---
            st.subheader("📸 Registros Fotográficos dos Testemunhos e Caixas")
            tem_fotos = False
            for m in manobras:
                f1_blob, f2_blob, f3_blob = m[9], m[10], m[11]
                fotos_lista = [bytes_para_pil(f) for f in [f1_blob, f2_blob, f3_blob] if f is not None]
                
                if fotos_lista:
                    tem_fotos = True
                    st.markdown(f"**Intervalo {m[1]:.2f}m a {m[2]:.2f}m (Caixa {m[5]})**")
                    cols_fotos = st.columns(len(fotos_lista))
                    for idx, img in enumerate(fotos_lista):
                        with cols_fotos[idx]:
                            st.image(img, use_column_width=True, caption=f"Foto {idx+1}")
            
            if not tem_fotos:
                st.info("Nenhuma imagem de campo cadastrada para as manobras deste furo.")

            st.divider()

            # --- EMISSÃO DE RELATÓRIO ---
            st.subheader("📄 Emissão de Boletim Diário de Sondagem")
            obs_fechamento = st.text_area("Observações Finais do Turno / Ocorrências de Campo", placeholder="Ex: Paralisação por chuva das 14h às 15h. Troca de coroa realizada.")

            html_conteudo = gerar_html_boletim(furo_fechamento, obs_fechamento)

            st.download_button(
                label="📥 Baixar Boletim Oficial de Sondagem (HTML / Imprimir em PDF)",
                data=html_conteudo,
                file_name=f"Boletim_{furo_fechamento}_{date.today().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )
        else:
            st.warning(f"Nenhuma manobra encontrada para o furo {furo_fechamento}. Registre manobras na Etapa 3 para ativar o dashboard.")

    # ETAPA 5
    elif opcao == "5. Dados do Furo & Perfuração":
        st.title("5. Dados Gerais e Configuração do Furo")
        st.caption("Ajuste manual de parâmetros e dados geotécnicos complementares.")
        
        with st.form("form_furo"):
            col1, col2, col3 = st.columns(3)
            with col1:
                furo = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", ""), placeholder="Ex: SP-01")
                st.session_state["furo_id"] = furo
            with col2:
                tipo_sondagem = st.selectbox("Tipo de Sondagem", ["Rotativa", "SPT (A Percussão)", "Mista", "Poço de Inspeção"])
                st.session_state["tipo_sondagem"] = tipo_sondagem
            with col3:
                manobras_existentes = buscar_manobras(furo)
                prof_sugerida = manobras_existentes[-1][2] if manobras_existentes else 0.0
                profundidade = st.number_input("Profundidade Final (m)", min_value=0.0, step=0.5, value=float(prof_sugerida))

            st.markdown("#### 🗺️ Coordenadas de GPS Registradas")
            col_gps_f1, col_gps_f2, col_gps_f3 = st.columns(3)
            
            lat_atual = st.session_state.get("latitude", None)
            lng_atual = st.session_state.get("longitude", None)
            prec_atual = st.session_state.get("precisao_gps", None)
            
            with col_gps_f1:
                lat_input = st.number_input("Latitude Decimal", value=float(lat_atual) if lat_atual else 0.0, format="%.6f")
            with col_gps_f2:
                lng_input = st.number_input("Longitude Decimal", value=float(lng_atual) if lng_atual else 0.0, format="%.6f")
            with col_gps_f3:
                prec_input = st.number_input("Precisão do GPS (m)", value=float(prec_atual) if prec_atual else 0.0, format="%.1f")

            obs = st.text_area("Observações Geotécnicas / Nível d'Água (N.A.)", placeholder="Registros do nível d'água, perda de água de circulação, etc...")

            btn_finalizar = st.form_submit_button("Salvar Ajustes do Boletim", use_container_width=True)

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
                        furo, tipo_sondagem, profundidade,
                        lat_input if lat_input != 0.0 else None,
                        lng_input if lng_input != 0.0 else None,
                        prec_input if prec_input != 0.0 else None,
                        obs
                    )
                    st.success(f"Boletim do furo {furo} atualizado com sucesso!")
                else:
                    st.warning("Por favor, informe a identificação do furo.")
