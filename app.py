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

# --- IMPORTAÇÕES PARA GERAÇÃO NATIVA DE PDF (REPORTLAB) ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Boa Fortuna - Sistema de Sondagem",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded"
)

USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"
DB_NAME = "boafortuna_dados.db"

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
    colunas_existentes = [coluna[1] for coluna in c.fetchall()]
    
    if "latitude" not in colunas_existentes:
        c.execute("ALTER TABLE boletins_campo ADD COLUMN latitude REAL")
    if "longitude" not in colunas_existentes:
        c.execute("ALTER TABLE boletins_campo ADD COLUMN longitude REAL")
    if "precisao_gps_m" not in colunas_existentes:
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
    conn.commit()
    conn.close()

init_db()

# --- COMPONENTE DE GEOLOCALIZAÇÃO GPS VIA BROWSER ---
def obter_geolocalizacao_gps():
    componente_js = """
    <div style="font-family: Arial, sans-serif; text-align: center;">
        <button id="btnGps" type="button" style="
            background-color: #059669; color: white; border: none; padding: 10px 18px;
            font-weight: 600; border-radius: 6px; cursor: pointer; width: 100%; font-size: 14px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">📍 Capturar Localização da Praça (GPS)</button>
        <p id="status" style="font-size: 12px; color: #64748b; margin-top: 6px; font-weight: 500;"></p>
    </div>

    <script>
    document.getElementById('btnGps').addEventListener('click', function() {
        var status = document.getElementById('status');
        if (!navigator.geolocation) {
            status.innerText = '❌ Geolocalização não é suportada pelo dispositivo.';
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
                status.innerText = '✅ Coordenadas da Praça Obtidas com Sucesso!';
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: JSON.stringify(coords)
                }, '*');
            },
            function(err) { status.innerText = '⚠️ Erro ao obter GPS: ' + err.message; },
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
        );
    });
    </script>
    """
    return components.html(componente_js, height=85)

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
    conn = sqlite3.connect(DB_NAME, timeout=10)
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
    conn = sqlite3.connect(DB_NAME, timeout=10)
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
    conn = sqlite3.connect(DB_NAME, timeout=10)
    c = conn.cursor()
    c.execute('DELETE FROM manobras_testemunho WHERE id = ?', (manobra_id,))
    conn.commit()
    conn.close()

def buscar_manobras(furo_id=None):
    conn = sqlite3.connect(DB_NAME, timeout=10)
    c = conn.cursor()
    if furo_id:
        c.execute('SELECT id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, horas_trab, horas_parado, descricao_litologica, foto1, foto2, foto3 FROM manobras_testemunho WHERE furo_id = ? ORDER BY id ASC', (furo_id,))
    else:
        c.execute('SELECT id, furo_id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, descricao_litologica, data_registro FROM manobras_testemunho ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

def buscar_dados_furo(furo_id):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        c = conn.cursor()
        c.execute('SELECT latitude, longitude, precisao_gps_m FROM boletins_campo WHERE furo_id = ?', (furo_id,))
        res = c.fetchone()
        conn.close()
        return res if res else (None, None, None)
    except Exception:
        return (None, None, None)

# --- GERADOR NATIVO DE PDF PROFISSIONAL (REPORTLAB) ---
def gerar_pdf_boletim(furo_id, obs_fechamento=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos customizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#475569'),
        alignment=1,
        fontName='Helvetica-Bold'
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=5,
        fontName='Helvetica-Bold'
    )
    
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )
    
    cell_header_style = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.white,
        fontName='Helvetica-Bold',
        alignment=1
    )

    elements = []

    # 1. Cabeçalho Principal
    empresa = st.session_state.get("empresa", "BOA FORTUNA PERFURAÇÕES E SONDAGENS")
    elements.append(Paragraph(empresa.upper(), title_style))
    elements.append(Paragraph(f"BOLETIM DIÁRIO DE SONDAGEM (BDS) - IDENTIFICAÇÃO DO FURO: {furo_id}", subtitle_style))
    elements.append(Spacer(1, 10))

    # 2. Tabela de Informações da Praça e Equipe
    obra = st.session_state.get("obra", "-")
    cidade = st.session_state.get("cidade", "-")
    sondador = st.session_state.get("sondador", "-")
    coordenador = st.session_state.get("coordenador", "-")
    data_campo = str(st.session_state.get("data_campo", date.today()))
    
    lat_db, lng_db, prec_db = buscar_dados_furo(furo_id)
    lat = st.session_state.get("latitude", lat_db)
    lng = st.session_state.get("longitude", lng_db)
    coord_str = f"Lat: {lat:.6f} | Lng: {lng:.6f}" if lat and lng else "Não Informada"

    info_data = [
        [
            Paragraph(f"<b>Cliente/Obra:</b> {obra}", cell_style),
            Paragraph(f"<b>Cidade/UF:</b> {cidade}", cell_style),
            Paragraph(f"<b>Data:</b> {data_campo}", cell_style)
        ],
        [
            Paragraph(f"<b>Sondador Resp.:</b> {sondador}", cell_style),
            Paragraph(f"<b>Coordenador:</b> {coordenador}", cell_style),
            Paragraph(f"<b>Coordenadas GPS:</b> {coord_str}", cell_style)
        ]
    ]

    table_info = Table(info_data, colWidths=[180, 180, 180])
    table_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(table_info)
    elements.append(Spacer(1, 12))

    # 3. Tabela de Manobras e Avanço
    elements.append(Paragraph("Avanço de Perfuração e Recuperação de Testemunhos", section_heading))
    manobras = buscar_manobras(furo_id)
    
    manobras_headers = [
        Paragraph("<b>De (m)</b>", cell_header_style),
        Paragraph("<b>Até (m)</b>", cell_header_style),
        Paragraph("<b>Avanço (m)</b>", cell_header_style),
        Paragraph("<b>Rec. (m)</b>", cell_header_style),
        Paragraph("<b>Rec. (%)</b>", cell_header_style),
        Paragraph("<b>Caixa</b>", cell_header_style),
        Paragraph("<b>Descrição Litológica</b>", cell_header_style)
    ]
    
    manobras_rows = [manobras_headers]
    
    total_avanco = 0
    total_recup = 0

    if manobras:
        for m in manobras:
            de, ate, rec, rec_pct, caixa, desc = m[1], m[2], m[3], m[4], m[5], m[8]
            avanc = round(ate - de, 2)
            total_avanco += avanc
            total_recup += rec
            
            manobras_rows.append([
                Paragraph(f"{de:.2f}", cell_style),
                Paragraph(f"{ate:.2f}", cell_style),
                Paragraph(f"{avanc:.2f}", cell_style),
                Paragraph(f"{rec:.2f}", cell_style),
                Paragraph(f"<b>{rec_pct:.1f}%</b>", cell_style),
                Paragraph(str(caixa), cell_style),
                Paragraph(desc or "-", cell_style)
            ])
            
        taxa_media_global = (total_recup / total_avanco * 100) if total_avanco > 0 else 0.0
        manobras_rows.append([
            Paragraph("<b>TOTAL</b>", cell_style),
            Paragraph(f"<b>{manobras[-1][2]:.2f}m</b>", cell_style),
            Paragraph(f"<b>{total_avanco:.2f}m</b>", cell_style),
            Paragraph(f"<b>{total_recup:.2f}m</b>", cell_style),
            Paragraph(f"<b>{taxa_media_global:.1f}%</b>", cell_style),
            Paragraph("-", cell_style),
            Paragraph("<b>Resumo Acumulado do Turno</b>", cell_style)
        ])

    table_manobras = Table(manobras_rows, colWidths=[45, 45, 55, 50, 50, 45, 250])
    table_manobras.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(table_manobras)
    elements.append(Spacer(1, 10))

    # 4. Observações de Campo
    if obs_fechamento:
        elements.append(Paragraph("Observações / Ocorrências de Campo", section_heading))
        obs_table = Table([[Paragraph(obs_fechamento, cell_style)]], colWidths=[540])
        obs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(obs_table)
        elements.append(Spacer(1, 10))

    # 5. Anexo Fotográfico (Testemunhos de Campo)
    imagens_relatorio = []
    if manobras:
        for m in manobras:
            for blob in [m[9], m[10], m[11]]:
                if blob:
                    try:
                        img_pil = Image.open(io.BytesIO(blob))
                        img_buf = io.BytesIO()
                        img_pil.save(img_buf, format='JPEG')
                        img_buf.seek(0)
                        # Redimensiona mantendo a proporção para caber em grid no PDF
                        rl_img = RLImage(img_buf, width=165, height=120)
                        imagens_relatorio.append(rl_img)
                    except Exception:
                        pass

    if imagens_relatorio:
        elements.append(Paragraph("Anexo Fotográfico de Testemunhos", section_heading))
        grid_fotos = []
        row_temp = []
        for img in imagens_relatorio:
            row_temp.append(img)
            if len(row_temp) == 3:
                grid_fotos.append(row_temp)
                row_temp = []
        if row_temp:
            while len(row_temp) < 3:
                row_temp.append(Paragraph("", cell_style))
            grid_fotos.append(row_temp)

        table_fotos = Table(grid_fotos, colWidths=[180, 180, 180])
        table_fotos.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(KeepTogether([table_fotos]))

    # Constrói o PDF completo
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

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
        st.title("1. Cabeçalho de Identificação & GPS da Praça")
        st.caption("Informações institucionais e georreferenciamento exato da praça de sondagem.")
        
        st.markdown("### 🗺️ Localização Geográfica da Praça de Sondagem")
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
                st.success("Dados do cabeçalho e GPS da praça salvos com sucesso!")

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

    # ETAPA 4 - DASHBOARD EXECUTIVO
    elif opcao == "4. Fechamento de Turno & Dashboard":
        st.title("4. Dashboard Executivo & Perfil Geotécnico")
        st.caption("Análise estratigráfica vertical, indicadores de performance e emissão de boletim em PDF.")

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
                dados_grafico.append({
                    "Intervalo": f"{de:.2f}m - {ate:.2f}m",
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

            # --- EMISSÃO DO BOLETIM EM PDF ---
            st.subheader("📄 Emissão do Boletim Oficial em PDF")
            obs_fechamento = st.text_area("Observações Finais do Turno / Ocorrências de Campo", placeholder="Ex: Paralisação por chuva das 14h às 15h. Troca de coroa realizada.")

            # Gera o PDF via ReportLab em memória
            pdf_bytes = gerar_pdf_boletim(furo_fechamento, obs_fechamento)

            st.download_button(
                label="📥 Baixar Boletim Oficial de Sondagem em PDF",
                data=pdf_bytes,
                file_name=f"Boletim_{furo_fechamento}_{date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
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

            st.markdown("#### 🗺️ Coordenadas da Praça de Sondagem (GPS)")
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
