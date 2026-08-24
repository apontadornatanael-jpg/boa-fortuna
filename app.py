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
    ''', (furo, str(data_m), de, ate, avanco, recup, taxa, caixa, barrilete, h_inicio, h_fim, tempo_man, litologia, observacoes, operador, h_trab, h_parado, f"{h_inicio} - {h_fim}", motivo, data_atual, f1, f2, f3))  
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

def buscar_furos_cadastrados():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    c = conn.cursor()
    c.execute('SELECT DISTINCT furo_id FROM boletins_campo ORDER BY furo_id ASC')
    furos = [r[0] for r in c.fetchall()]
    conn.close()
    return furos

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
          
    title_style = ParagraphStyle(  
        'DocTitle', parent=styles['Heading1'], fontSize=16, leading=18, textColor=colors.HexColor('#1E3A8A'), alignment=1, fontName='Helvetica-Bold'  
    )  
    subtitle_style = ParagraphStyle(  
        'DocSubTitle', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.HexColor('#475569'), alignment=1, fontName='Helvetica-Bold'  
    )  
    section_heading = ParagraphStyle(  
        'SectionHeading', parent=styles['Heading2'], fontSize=12, leading=14, textColor=colors.HexColor('#1E3A8A'), spaceBefore=10, spaceAfter=5, fontName='Helvetica-Bold'  
    )  
    cell_style = ParagraphStyle(  
        'CellText', parent=styles['Normal'], fontSize=7, leading=9, textColor=colors.HexColor('#1E293B')  
    )  
    cell_header_style = ParagraphStyle(  
        'CellHeader', parent=styles['Normal'], fontSize=7, leading=9, textColor=colors.white, fontName='Helvetica-Bold', alignment=1  
    )  

    elements = []  
      
    empresa = st.session_state.get("empresa", "BOA FORTUNA PERFURAÇÕES E SONDAGENS")  
    elements.append(Paragraph(empresa.upper(), title_style))  
    elements.append(Paragraph(f"BOLETIM DIÁRIO DE SONDAGEM (BDS) - FURO: {furo_id}", subtitle_style))  
    elements.append(Spacer(1, 10))  
      
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
        [Paragraph(f"<b>Cliente/Obra:</b> {obra}", cell_style), Paragraph(f"<b>Cidade/UF:</b> {cidade}", cell_style), Paragraph(f"<b>Data:</b> {data_campo}", cell_style)],  
        [Paragraph(f"<b>Sondador Resp.:</b> {sondador}", cell_style), Paragraph(f"<b>Coordenador:</b> {coordenador}", cell_style), Paragraph(f"<b>Coordenadas GPS:</b> {coord_str}", cell_style)]  
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
      
    elements.append(Paragraph("Avanço de Perfuração e Recuperação de Testemunhos", section_heading))  
    manobras = buscar_manobras(furo_id)  
          
    manobras_headers = [  
        Paragraph("<b>Data</b>", cell_header_style),  
        Paragraph("<b>De (m)</b>", cell_header_style),  
        Paragraph("<b>Até (m)</b>", cell_header_style),  
        Paragraph("<b>Avanço</b>", cell_header_style),  
        Paragraph("<b>Recup.</b>", cell_header_style),  
        Paragraph("<b>Rec. %</b>", cell_header_style),  
        Paragraph("<b>Caixa</b>", cell_header_style),  
        Paragraph("<b>Barrilete</b>", cell_header_style),  
        Paragraph("<b>Litologia</b>", cell_header_style),  
        Paragraph("<b>Operador</b>", cell_header_style)  
    ]  
          
    manobras_rows = [manobras_headers]  
    total_avanco = 0  
    total_recup = 0  
      
    if manobras:  
        for m in manobras:  
            dt_m, de, ate, avanc, rec, rec_pct, caixa, barrilete, litologia, operador = m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[13], m[15]  
            total_avanco += (avanc or 0)  
            total_recup += (rec or 0)  
                          
            manobras_rows.append([  
                Paragraph(str(dt_m or "-"), cell_style),  
                Paragraph(f"{de:.2f}", cell_style),  
                Paragraph(f"{ate:.2f}", cell_style),  
                Paragraph(f"{avanc:.2f}", cell_style),  
                Paragraph(f"{rec:.2f}", cell_style),  
                Paragraph(f"<b>{rec_pct:.1f}%</b>", cell_style),  
                Paragraph(str(caixa or "-"), cell_style),  
                Paragraph(str(barrilete or "-"), cell_style),  
                Paragraph(str(litologia or "-"), cell_style),  
                Paragraph(str(operador or "-"), cell_style)  
            ])  
                  
        taxa_media_global = (total_recup / total_avanco * 100) if total_avanco > 0 else 0.0  
        manobras_rows.append([  
            Paragraph("<b>TOTAL</b>", cell_style),  
            Paragraph("-", cell_style),  
            Paragraph(f"<b>{manobras[-1][4]:.2f}m</b>", cell_style),  
            Paragraph(f"<b>{total_avanco:.2f}m</b>", cell_style),  
            Paragraph(f"<b>{total_recup:.2f}m</b>", cell_style),  
            Paragraph(f"<b>{taxa_media_global:.1f}%</b>", cell_style),  
            Paragraph("-", cell_style),  
            Paragraph("-", cell_style),  
            Paragraph("<b>Resumo Acumulado</b>", cell_style),  
            Paragraph("-", cell_style)  
        ])  
      
    table_manobras = Table(manobras_rows, colWidths=[50, 40, 40, 40, 40, 40, 40, 50, 140, 90])  
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
      
    imagens_relatorio = []  
    if manobras:  
        for m in manobras:  
            for blob in [m[16], m[17], m[18]]:  
                if blob:  
                    try:  
                        img_pil = Image.open(io.BytesIO(blob))  
                        img_buf = io.BytesIO()  
                        img_pil.save(img_buf, format='JPEG')  
                        img_buf.seek(0)  
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
        st.caption("Informações institucionais e georreferenciamento automático da praça de sondagem.")  
                  
        st.markdown("### 🗺️ Localização Geográfica da Praça (Automática)")  
        
        gps_json = obter_geolocalizacao_gps_auto()  
        if gps_json:  
            try:  
                coords = json.loads(gps_json)  
                st.session_state["latitude"] = float(coords["lat"])  
                st.session_state["longitude"] = float(coords["lng"])  
                st.session_state["precisao_gps"] = float(coords["precisao"])  
            except Exception:  
                pass  
          
        col_gps1, col_gps2, col_gps3 = st.columns(3)
        lat_val = st.session_state.get("latitude", "")  
        lng_val = st.session_state.get("longitude", "")  
        acc_val = st.session_state.get("precisao_gps", "")  
                      
        col_gps1.text_input("Latitude", value=str(lat_val) if lat_val else "Aguardando GPS...", key="lat_input", disabled=True)  
        col_gps2.text_input("Longitude", value=str(lng_val) if lng_val else "Aguardando GPS...", key="lng_input", disabled=True)  
        col_gps3.text_input("Precisão (m)", value=f"{acc_val} m" if acc_val else "Aguardando...", key="acc_input", disabled=True)  
          
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
        st.caption("Lançamento automatizado do avanço, recuperação, caixas e tempos operacionais.")  
                  
        furo_atual = st.text_input("Informação - Furo (Identificação)", value=st.session_state.get("furo_id", "SP-01"), key="input_furo_manobra")  
        st.session_state["furo_id"] = furo_atual  
          
        manobras_furo = buscar_manobras(furo_atual)  
        prox_de = manobras_furo[-1][4] if manobras_furo else 0.0  
        prox_ate = round(prox_de + 1.5, 2)  
                  
        st.info(f"📍 Profundidade Atual Perfurada para o Furo **{furo_atual}**: **{prox_de:.2f} m**")  
        
        hora_atual = datetime.now().time()
        hora_inicio_padrao = (datetime.now() - timedelta(hours=1, minutes=30)).time() if not manobras_furo else datetime.now().time()

        c1, c2, c3 = st.columns(3)
        with c1:
            data_manobra = st.date_input("Data", value=date.today())
        with c2:
            barrilete = st.text_input("Barrilete", value="HQ")
        with c3:
            operador_sonda = st.text_input("Operador Sonda", value=st.session_state.get("sondador", ""))

        c4, c5, c6, c7 = st.columns(4)  
        with c4:  
            de_m = st.number_input("Profundidade Inicial (m)", min_value=0.0, step=0.5, value=float(prox_de), format="%.2f")  
        with c5:  
            ate_m = st.number_input("Profundidade Final (m)", min_value=0.0, step=0.5, value=float(prox_ate), format="%.2f")  
        with c6:  
            recup_m = st.number_input("Recuperação (m)", min_value=0.0, step=0.1, value=round(max(0.0, ate_m - de_m), 2), format="%.2f")  
        with c7:  
            num_caixa = st.text_input("Caixa", value=manobras_furo[-1][8] if manobras_furo else "01")  

        avanco_calc = round(max(0.0, ate_m - de_m), 2)
        taxa_recup = min(100.0, round((recup_m / avanco_calc * 100), 1)) if avanco_calc > 0 else 0.0  

        st.caption(f"⚡ **Avanço Calculado:** {avanco_calc:.2f} m | **Taxa de Recuperação:** {taxa_recup:.1f}%")

        c8, c9, c10 = st.columns(3)
        with c8:
            horario_inicio = st.time_input("Horário Início", value=hora_inicio_padrao)
        with c9:
            horario_fim = st.time_input("Horário Fim (Auto)", value=hora_atual)
            
        dt_ini = datetime.combine(date.today(), horario_inicio)
        dt_fim = datetime.combine(date.today(), horario_fim)
        
        if dt_fim < dt_ini:
            dt_fim += timedelta(days=1)
            
        diferenca_segundos = (dt_fim - dt_ini).total_seconds()
        horas_trabalhadas = round(diferenca_segundos / 3600.0, 2)
        minutos_totais = int(diferenca_segundos // 60)
        horas_fmt = minutos_totais // 60
        mins_fmt = minutos_totais % 60
        tempo_manobra_auto = f"{horas_fmt:02d}h {mins_fmt:02d}m"

        with c10:
            st.text_input("Tempo de Manobra (Auto)", value=tempo_manobra_auto, disabled=True)

        c11, c12, c13 = st.columns(3)
        with c11:
            desc_litologica = st.text_input("Litologia", placeholder="Ex: Solo residual, rocha alterada...")  
        with c12:
            observacoes = st.text_input("Observações", placeholder="Ex: Perda de água, troca de coroa...")  
        with c13:
            horas_paradas = st.number_input("Horas Paradas / Interrupções", min_value=0.0, step=0.25, value=0.0)

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
          
        if st.button("Adicionar Manobra Automática", use_container_width=True):  
            salvar_manobra(
                furo=furo_atual,
                data_m=data_manobra,
                de=de_m,
                ate=ate_m,
                avanco=avanco_calc,
                recup=recup_m,
                taxa=taxa_recup,
                caixa=num_caixa,
                barrilete=barrilete,
                h_inicio=str(horario_inicio),
                h_fim=str(horario_fim),
                tempo_man=tempo_manobra_auto,
                litologia=desc_litologica,
                observacoes=observacoes,
                operador=operador_sonda,
                h_trab=horas_trabalhadas,
                h_parado=horas_paradas,
                fotos_pil=fotos_manobra_pil
            )
            st.success("Manobra salva e boletim sincronizado com sucesso!")
            st.rerun()

        st.divider()
        st.subheader(f"Histórico do Furo: {furo_atual}")
        if manobras_furo:
            for item in manobras_furo:
                m_id, f_id, dt_m, de, ate, avanc, rec, rec_pct, caixa, bar, h_ini, h_fim, t_man, lito, obs, op, f1, f2, f3, h_tr, h_pr = item
                with st.expander(f"📍 {de:.2f}m a {ate:.2f}m — Caixa {caixa} | Rec: {rec_pct:.1f}%"):
                    c_info, c_del = st.columns([5, 1])
                    with c_info:
                        st.write(f"**Data:** {dt_m} | **Horário:** {h_ini} - {h_fim} ({t_man}) | **Operador:** {op}")
                        st.write(f"**Avanço:** {avanc:.2f}m | **Recuperação:** {rec:.2f}m ({rec_pct:.1f}%) | **Barrilete:** {bar}")
                        st.write(f"**Litologia:** {lito or '-'}")
                        st.write(f"**Observações:** {obs or '-'}")
                    with c_del:
                        if st.button("🗑️ Excluir", key=f"del_{m_id}"):
                            deletar_manobra(m_id)
                            st.rerun()

                    imgs_pil = [bytes_para_pil(f1), bytes_para_pil(f2), bytes_para_pil(f3)]
                    imgs_validas = [i for i in imgs_pil if i is not None]
                    if imgs_validas:
                        cols_img = st.columns(len(imgs_validas))
                        for idx, img in enumerate(imgs_validas):
                            cols_img[idx].image(img, use_column_width=True)
        else:
            st.info("Nenhuma manobra cadastrada para este furo.")

    # ETAPA 4
    elif opcao == "4. Fechamento de Turno & Dashboard":
        st.title("4. Fechamento de Turno & Dashboard de Produção")
        furo_atual = st.session_state.get("furo_id", "SP-01")
        
        manobras = buscar_manobras(furo_atual)
        
        if not manobras:
            st.warning("Nenhuma manobra registrada para calcular métricas e gerar o relatório.")
        else:
            tot_avanco = sum([m[5] or 0 for m in manobras])
            tot_recup = sum([m[6] or 0 for m in manobras])
            taxa_media = (tot_recup / tot_avanco * 100) if tot_avanco > 0 else 0.0
            tot_h_trab = sum([m[19] or 0 for m in manobras])
            tot_h_parada = sum([m[20] or 0 for m in manobras])

            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            kpi1.metric("Avanço Total", f"{tot_avanco:.2f} m")
            kpi2.metric("Recuperação Total", f"{tot_recup:.2f} m")
            kpi3.metric("Taxa Média Rec.", f"{taxa_media:.1f}%")
            kpi4.metric("Horas Trabalhadas", f"{tot_h_trab:.2f} h")
            kpi5.metric("Horas Paradas", f"{tot_h_parada:.2f} h")

            st.divider()
            
            # Gráficos interativos
            df_m = pd.DataFrame(manobras, columns=[
                "id", "furo_id", "data_manobra", "de_m", "ate_m", "avanco_m", "recup_m",
                "taxa_recup_pct", "num_caixa", "barrilete", "horario_inicio", "horario_fim",
                "tempo_manobra", "descricao_litologica", "observacoes", "operador_sonda",
                "foto1", "foto2", "foto3", "horas_trab", "horas_parado"
            ])

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                fig_rec = px.bar(
                    df_m, x="ate_m", y="taxa_recup_pct",
                    title="Taxa de Recuperação por Profundidade Final (%)",
                    labels={"ate_m": "Profundidade (m)", "taxa_recup_pct": "Recuperação (%)"},
                    color="taxa_recup_pct", color_continuous_scale="Blues"
                )
                st.plotly_chart(fig_rec, use_container_width=True)

            with col_g2:
                fig_av = px.line(
                    df_m, x="ate_m", y="avanco_m", markers=True,
                    title="Avanço Perfurado por Manobra (m)",
                    labels={"ate_m": "Profundidade (m)", "avanco_m": "Avanço (m)"}
                )
                st.plotly_chart(fig_av, use_container_width=True)

            st.divider()
            st.subheader("📄 Emissão do Boletim Diário de Sondagem (PDF)")
            obs_fechamento = st.text_area("Observações Finais do Fechamento de Turno", placeholder="Ocorrências gerais do dia, problemas na sonda...")
            
            if st.button("Gerar Boletim em PDF", use_container_width=True):
                pdf_bytes = gerar_pdf_boletim(furo_atual, obs_fechamento)
                st.download_button(
                    label="📥 Baixar Boletim em PDF",
                    data=pdf_bytes,
                    file_name=f"Boletim_{furo_atual}_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    # ETAPA 5
    elif opcao == "5. Dados do Furo & Perfuração":
        st.title("5. Painel Consolidado de Dados e Registros")
        
        furos = buscar_furos_cadastrados()
        furo_sel = st.selectbox("Selecione o Furo:", furos if furos else [st.session_state.get("furo_id", "SP-01")])
        
        manobras = buscar_manobras(furo_sel)
        
        if manobras:
            data_tabela = []
            for m in manobras:
                data_tabela.append({
                    "ID": m[0],
                    "Data": m[2],
                    "De (m)": m[3],
                    "Até (m)": m[4],
                    "Avanço (m)": m[5],
                    "Recup (m)": m[6],
                    "Rec %": f"{m[7]:.1f}%",
                    "Caixa": m[8],
                    "Barrilete": m[9],
                    "Horário": f"{m[10]} - {m[11]}",
                    "Tempo": m[12],
                    "Litologia": m[13],
                    "Operador": m[15]
                })
            st.dataframe(pd.DataFrame(data_tabela), use_container_width=True)
        else:
            st.info("Nenhum registro encontrado para o furo selecionado.")
