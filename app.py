import io
import sqlite3
from datetime import datetime, date, time
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image
import plotly.express as px

# PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak
)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Boa Fortuna | Sistema Digital de Sondagem",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_NAME = "boafortuna_dados.db"
APP_NAME = "BOA FORTUNA"
USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"

# ============================================================
# ESTILO
# ============================================================

st.markdown("""
<style>
.stApp { background: #F8FAFC; }
[data-testid="stSidebar"] { background: #0F172A; }
[data-testid="stSidebar"] * { color: #F8FAFC !important; }
h1,h2,h3 { color:#1E3A8A !important; }
div[data-testid="stMetric"] {
    background:white;
    border:1px solid #E2E8F0;
    border-radius:12px;
    padding:12px;
}
div.stButton > button {
    border-radius:8px;
    font-weight:600;
}
.small-note { color:#64748B; font-size:0.85rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# BANCO
# ============================================================

def get_conn():
    return sqlite3.connect(DB_NAME, timeout=20)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS furos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        furo_id TEXT UNIQUE NOT NULL,
        projeto TEXT,
        empresa TEXT,
        obra_cliente TEXT,
        cidade_uf TEXT,
        sonda TEXT,
        tipo_sondagem TEXT DEFAULT 'Rotativa',
        operador TEXT,
        auxiliares TEXT,
        coordenador TEXT,
        supervisor TEXT,
        latitude REAL,
        longitude REAL,
        precisao_gps_m REAL,
        datum TEXT DEFAULT 'SIRGAS 2000',
        azimute REAL DEFAULT 0,
        inclinacao REAL DEFAULT -90,
        diametro TEXT,
        data_inicio TEXT,
        data_fim TEXT,
        profundidade_final REAL DEFAULT 0,
        observacao TEXT,
        atualizado_em TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS manobras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        furo_id TEXT NOT NULL,
        data_manobra TEXT,
        de_m REAL,
        ate_m REAL,
        avanco_m REAL,
        recup_m REAL,
        taxa_recup_pct REAL,
        caixa TEXT,
        barrilete TEXT,
        horario_inicio TEXT,
        horario_fim TEXT,
        tempo_manobra_min REAL,
        horas_trab REAL,
        horas_parado REAL,
        motivo_parada TEXT,
        litologia TEXT,
        alteracao TEXT,
        mineralizacao TEXT,
        estruturas TEXT,
        observacoes TEXT,
        operador TEXT,
        foto1 BLOB,
        foto2 BLOB,
        foto3 BLOB,
        criado_em TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS geologia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        furo_id TEXT NOT NULL,
        de_m REAL,
        ate_m REAL,
        litologia TEXT,
        alteracao TEXT,
        mineralizacao TEXT,
        estruturas TEXT,
        observacoes TEXT,
        criado_em TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS configuracoes (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def otimizar_imagem(upload):
    if upload is None:
        return None
    img = Image.open(upload).convert("RGB")
    img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return buf.getvalue()

def blob_to_image(blob):
    if not blob:
        return None
    try:
        return Image.open(io.BytesIO(blob))
    except Exception:
        return None

def calcular_tempo_min(inicio, fim):
    """Calcula duração mesmo quando a manobra passa da meia-noite."""
    if inicio is None or fim is None:
        return 0
    a = datetime.combine(date.today(), inicio)
    b = datetime.combine(date.today(), fim)
    if b < a:
        b += pd.Timedelta(days=1)
    return max(0, int((b - a).total_seconds() / 60))

def calcular_horas(inicio, fim):
    return calcular_tempo_min(inicio, fim) / 60

def get_furos():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM furos ORDER BY furo_id", conn
    )
    conn.close()
    return df

def get_furo(furo_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM furos WHERE furo_id=?", (furo_id,)
    ).fetchone()
    cols = [d[0] for d in conn.execute("SELECT * FROM furos LIMIT 0").description]
    conn.close()
    return dict(zip(cols, row)) if row else None

def get_manobras(furo_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM manobras WHERE furo_id=? ORDER BY de_m, id",
        conn, params=(furo_id,)
    )
    conn.close()
    return df

def get_geologia(furo_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM geologia WHERE furo_id=? ORDER BY de_m, id",
        conn, params=(furo_id,)
    )
    conn.close()
    return df

def salvar_furo(d):
    conn = get_conn()
    conn.execute("""
    INSERT INTO furos (
        furo_id, projeto, empresa, obra_cliente, cidade_uf, sonda,
        tipo_sondagem, operador, auxiliares, coordenador, supervisor,
        latitude, longitude, precisao_gps_m, datum, azimute, inclinacao,
        diametro, data_inicio, data_fim, profundidade_final, observacao,
        atualizado_em
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(furo_id) DO UPDATE SET
        projeto=excluded.projeto,
        empresa=excluded.empresa,
        obra_cliente=excluded.obra_cliente,
        cidade_uf=excluded.cidade_uf,
        sonda=excluded.sonda,
        tipo_sondagem=excluded.tipo_sondagem,
        operador=excluded.operador,
        auxiliares=excluded.auxiliares,
        coordenador=excluded.coordenador,
        supervisor=excluded.supervisor,
        latitude=excluded.latitude,
        longitude=excluded.longitude,
        precisao_gps_m=excluded.precisao_gps_m,
        datum=excluded.datum,
        azimute=excluded.azimute,
        inclinacao=excluded.inclinacao,
        diametro=excluded.diametro,
        data_inicio=excluded.data_inicio,
        data_fim=excluded.data_fim,
        profundidade_final=excluded.profundidade_final,
        observacao=excluded.observacao,
        atualizado_em=excluded.atualizado_em
    """, (
        d["furo_id"], d["projeto"], d["empresa"], d["obra_cliente"],
        d["cidade_uf"], d["sonda"], d["tipo_sondagem"], d["operador"],
        d["auxiliares"], d["coordenador"], d["supervisor"],
        d["latitude"], d["longitude"], d["precisao_gps_m"], d["datum"],
        d["azimute"], d["inclinacao"], d["diametro"], d["data_inicio"],
        d["data_fim"], d["profundidade_final"], d["observacao"], agora()
    ))
    conn.commit()
    conn.close()

def atualizar_profundidade(furo_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(MAX(ate_m),0) FROM manobras WHERE furo_id=?",
        (furo_id,)
    ).fetchone()
    profundidade = float(row[0] or 0)
    conn.execute(
        "UPDATE furos SET profundidade_final=?, atualizado_em=? WHERE furo_id=?",
        (profundidade, agora(), furo_id)
    )
    conn.commit()
    conn.close()
    return profundidade

def salvar_manobra(d):
    conn = get_conn()
    conn.execute("""
    INSERT INTO manobras (
        furo_id,data_manobra,de_m,ate_m,avanco_m,recup_m,taxa_recup_pct,
        caixa,barrilete,horario_inicio,horario_fim,tempo_manobra_min,
        horas_trab,horas_parado,motivo_parada,litologia,alteracao,
        mineralizacao,estruturas,observacoes,operador,
        foto1,foto2,foto3,criado_em
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d["furo_id"], d["data_manobra"], d["de_m"], d["ate_m"],
        d["avanco_m"], d["recup_m"], d["taxa_recup_pct"], d["caixa"],
        d["barrilete"], d["horario_inicio"], d["horario_fim"],
        d["tempo_manobra_min"], d["horas_trab"], d["horas_parado"],
        d["motivo_parada"], d["litologia"], d["alteracao"],
        d["mineralizacao"], d["estruturas"], d["observacoes"],
        d["operador"], d["foto1"], d["foto2"], d["foto3"], agora()
    ))
    conn.commit()
    conn.close()
    atualizar_profundidade(d["furo_id"])

def excluir_manobra(id_manobra):
    conn = get_conn()
    row = conn.execute(
        "SELECT furo_id FROM manobras WHERE id=?", (id_manobra,)
    ).fetchone()
    conn.execute("DELETE FROM manobras WHERE id=?", (id_manobra,))
    conn.commit()
    conn.close()
    if row:
        atualizar_profundidade(row[0])

def salvar_geologia(d):
    conn = get_conn()
    conn.execute("""
    INSERT INTO geologia (
        furo_id,de_m,ate_m,litologia,alteracao,mineralizacao,
        estruturas,observacoes,criado_em
    ) VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        d["furo_id"], d["de_m"], d["ate_m"], d["litologia"],
        d["alteracao"], d["mineralizacao"], d["estruturas"],
        d["observacoes"], agora()
    ))
    conn.commit()
    conn.close()

def excluir_geologia(id_geo):
    conn = get_conn()
    conn.execute("DELETE FROM geologia WHERE id=?", (id_geo,))
    conn.commit()
    conn.close()

def proximo_intervalo(furo_id):
    df = get_manobras(furo_id)
    if df.empty:
        return 0.0
    return float(df["ate_m"].max())

def estatisticas_furo(furo_id):
    df = get_manobras(furo_id)
    if df.empty:
        return {
            "metros": 0, "recuperados": 0, "rec_pct": 0,
            "h_trab": 0, "h_parado": 0, "prod_h": 0,
            "manobras": 0
        }
    metros = float(df["avanco_m"].fillna(0).sum())
    recuperados = float(df["recup_m"].fillna(0).sum())
    h_trab = float(df["horas_trab"].fillna(0).sum())
    h_parado = float(df["horas_parado"].fillna(0).sum())
    return {
        "metros": metros,
        "recuperados": recuperados,
        "rec_pct": (recuperados / metros * 100) if metros else 0,
        "h_trab": h_trab,
        "h_parado": h_parado,
        "prod_h": metros / h_trab if h_trab else 0,
        "manobras": len(df)
    }

# ============================================================
# GPS OPCIONAL
# ============================================================

try:
    from streamlit_geolocation import streamlit_geolocation
    GPS_DISPONIVEL = True
except Exception:
    GPS_DISPONIVEL = False

def capturar_gps():
    if not GPS_DISPONIVEL:
        st.warning(
            "GPS automático não instalado. No Colab, execute: "
            "`!pip install streamlit-geolocation` e reinicie o app."
        )
        return
    loc = streamlit_geolocation()
    if loc and loc.get("latitude") is not None:
        st.session_state.latitude = float(loc["latitude"])
        st.session_state.longitude = float(loc["longitude"])
        st.session_state.precisao_gps = float(loc.get("accuracy") or 0)
        st.success(
            f"GPS capturado: {st.session_state.latitude:.6f}, "
            f"{st.session_state.longitude:.6f}"
        )

# ============================================================
# PDF
# ============================================================

def gerar_pdf(furo_id):
    furo = get_furo(furo_id)
    man = get_manobras(furo_id)
    geo = get_geologia(furo_id)
    stats = estatisticas_furo(furo_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=17,
        textColor=colors.HexColor("#1E3A8A"), alignment=1
    )
    heading = ParagraphStyle(
        "heading", parent=styles["Heading2"], fontSize=11,
        textColor=colors.HexColor("#1E3A8A"), spaceBefore=8
    )
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7)
    elements = []

    elements.append(Paragraph(
        f"{APP_NAME} — BOLETIM DIGITAL DE SONDAGEM — {furo_id}", title
    ))
    elements.append(Spacer(1, 8))

    info = [
        [
            f"Projeto: {furo.get('projeto','-')}",
            f"Empresa: {furo.get('empresa','-')}",
            f"Obra/Cliente: {furo.get('obra_cliente','-')}",
            f"Cidade/UF: {furo.get('cidade_uf','-')}",
        ],
        [
            f"Sonda: {furo.get('sonda','-')}",
            f"Operador: {furo.get('operador','-')}",
            f"Azimute: {furo.get('azimute',0):.1f}°",
            f"Inclinação: {furo.get('inclinacao',0):.1f}°",
        ],
        [
            f"Latitude: {furo.get('latitude','-')}",
            f"Longitude: {furo.get('longitude','-')}",
            f"Datum: {furo.get('datum','-')}",
            f"Profundidade: {stats['metros']:.2f} m",
        ],
    ]
    t = Table(info, colWidths=[185]*4)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F8FAFC")),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#CBD5E1")),
        ("PADDING",(0,0),(-1,-1),6),
    ]))
    elements.append(t)

    elements.append(Paragraph("Indicadores", heading))
    ind = [[
        "Metros perfurados", "Metros recuperados", "Recuperação",
        "Horas trabalhadas", "Horas paradas", "Produtividade"
    ], [
        f"{stats['metros']:.2f} m", f"{stats['recuperados']:.2f} m",
        f"{stats['rec_pct']:.1f}%", f"{stats['h_trab']:.2f} h",
        f"{stats['h_parado']:.2f} h", f"{stats['prod_h']:.2f} m/h"
    ]]
    ti = Table(ind, colWidths=[115]*6)
    ti.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1E3A8A")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#CBD5E1")),
        ("PADDING",(0,0),(-1,-1),6),
    ]))
    elements.append(ti)

    elements.append(Paragraph("Manobras", heading))
    rows = [[
        Paragraph(x, cell) for x in
        ["Data","De","Até","Avanço","Recup.","Rec. %","Caixa",
         "Barrilete","Início","Fim","H.Trab.","H.Parado","Litologia"]
    ]]
    for _, r in man.iterrows():
        rows.append([
            str(r["data_manobra"] or "-"),
            f"{r['de_m']:.2f}",
            f"{r['ate_m']:.2f}",
            f"{r['avanco_m']:.2f}",
            f"{r['recup_m']:.2f}",
            f"{r['taxa_recup_pct']:.1f}%",
            str(r["caixa"] or "-"),
            str(r["barrilete"] or "-"),
            str(r["horario_inicio"] or "-"),
            str(r["horario_fim"] or "-"),
            f"{r['horas_trab']:.2f}",
            f"{r['horas_parado']:.2f}",
            str(r["litologia"] or "-"),
        ])
    if len(rows) == 1:
        rows.append(["Sem registros"] + [""] * 12)
    tm = Table(rows, repeatRows=1, colWidths=[
        55,38,38,45,45,45,45,55,45,45,45,45,100
    ])
    tm.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1E3A8A")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#CBD5E1")),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("ALIGN",(1,1),(-2,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    elements.append(tm)

    if not geo.empty:
        elements.append(Paragraph("Geologia", heading))
        gr = [["De","Até","Litologia","Alteração","Mineralização","Estruturas","Observações"]]
        for _, r in geo.iterrows():
            gr.append([
                f"{r['de_m']:.2f}", f"{r['ate_m']:.2f}",
                str(r["litologia"] or "-"), str(r["alteracao"] or "-"),
                str(r["mineralizacao"] or "-"), str(r["estruturas"] or "-"),
                str(r["observacoes"] or "-")
            ])
        tg = Table(gr, repeatRows=1, colWidths=[40,40,100,100,100,100,120])
        tg.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#334155")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#CBD5E1")),
            ("FONTSIZE",(0,0),(-1,-1),7),
        ]))
        elements.append(tg)

    # Fotos
    fotos = []
    for _, r in man.iterrows():
        for col in ["foto1","foto2","foto3"]:
            img = blob_to_image(r[col])
            if img:
                b = io.BytesIO()
                img.thumbnail((500, 350))
                img.save(b, "JPEG")
                b.seek(0)
                fotos.append(RLImage(b, width=180, height=125))
    if fotos:
        elements.append(PageBreak())
        elements.append(Paragraph("Anexo Fotográfico", heading))
        grid = []
        for i in range(0, len(fotos), 3):
            linha = fotos[i:i+3]
            while len(linha) < 3:
                linha.append("")
            grid.append(linha)
        tf = Table(grid, colWidths=[250]*3)
        tf.setStyle(TableStyle([
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ]))
        elements.append(tf)

    doc.build(elements)
    return buffer.getvalue()

# ============================================================
# LOGIN
# ============================================================

if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("""
    <style>
    .stApp {
        background:linear-gradient(135deg,#1E3A8A 0%,#0F172A 100%);
    }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1,1.2,1])
    with col:
        st.write("")
        st.markdown(
            "<h1 style='text-align:center;color:white'>BOA FORTUNA</h1>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='text-align:center;color:#93C5FD'>"
            "SISTEMA DIGITAL DE SONDAGEM</p>",
            unsafe_allow_html=True
        )
        with st.form("login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Acessar", use_container_width=True)
            if entrar:
                if usuario == USUARIO_CORRETO and senha == SENHA_CORRETA:
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
    st.stop()

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⛏️ BOA FORTUNA")
st.sidebar.caption("Sistema Digital de Sondagem")
st.sidebar.divider()

furos_df = get_furos()
if not furos_df.empty:
    lista_furos = furos_df["furo_id"].tolist()
else:
    lista_furos = []

if "furo_atual" not in st.session_state:
    st.session_state.furo_atual = lista_furos[0] if lista_furos else "BF-001"

if lista_furos:
    escolhido = st.sidebar.selectbox(
        "Furo ativo",
        lista_furos,
        index=lista_furos.index(st.session_state.furo_atual)
        if st.session_state.furo_atual in lista_furos else 0
    )
    st.session_state.furo_atual = escolhido
else:
    st.sidebar.info("Nenhum furo cadastrado. Crie o primeiro.")

menu = st.sidebar.radio(
    "Módulo",
    [
        "🏠 Dashboard",
        "📋 Dados do Furo",
        "🔩 Manobras",
        "🪨 Testemunho / Fotos",
        "🧱 Geologia",
        "📄 Relatório PDF",
        "🗃️ Banco de Dados",
    ]
)

if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.logado = False
    st.rerun()

# ============================================================
# DASHBOARD
# ============================================================

if menu == "🏠 Dashboard":
    st.title("🏠 Dashboard de Sondagem")

    if not lista_furos:
        st.info("Cadastre o primeiro furo em **Dados do Furo**.")
        st.stop()

    furo_id = st.session_state.furo_atual
    furo = get_furo(furo_id)
    s = estatisticas_furo(furo_id)

    st.subheader(f"Furo {furo_id}")
    st.caption(
        f"Projeto: {furo.get('projeto') or '-'} | "
        f"Sonda: {furo.get('sonda') or '-'} | "
        f"Operador: {furo.get('operador') or '-'}"
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("⛏️ Metros perfurados", f"{s['metros']:.2f} m")
    c2.metric("🪨 Recuperação", f"{s['rec_pct']:.1f}%")
    c3.metric("⏱️ Horas trabalhadas", f"{s['h_trab']:.2f} h")
    c4.metric("🛑 Horas paradas", f"{s['h_parado']:.2f} h")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📈 Produtividade", f"{s['prod_h']:.2f} m/h")
    c2.metric("📦 Metros recuperados", f"{s['recuperados']:.2f} m")
    c3.metric("🔩 Manobras", s["manobras"])
    c4.metric("📍 Profundidade atual", f"{proximo_intervalo(furo_id):.2f} m")

    df = get_manobras(furo_id)
    if not df.empty:
        st.divider()
        a,b = st.columns(2)

        with a:
            fig = px.bar(
                df, x="id", y=["avanco_m","recup_m"],
                barmode="group",
                labels={"value":"Metros","id":"Manobra"},
                title="Avanço x Recuperação"
            )
            st.plotly_chart(fig, use_container_width=True)

        with b:
            fig2 = px.line(
                df, x="ate_m", y="taxa_recup_pct",
                markers=True,
                labels={"ate_m":"Profundidade (m)","taxa_recup_pct":"Recuperação (%)"},
                title="Recuperação em Profundidade"
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Últimas manobras")
        cols = ["id","de_m","ate_m","avanco_m","recup_m",
                "taxa_recup_pct","caixa","barrilete","horas_trab","horas_parado"]
        st.dataframe(df[cols].tail(10), use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não existem manobras para este furo.")

# ============================================================
# DADOS DO FURO
# ============================================================

elif menu == "📋 Dados do Furo":
    st.title("📋 Dados do Furo")
    st.caption("Cadastro completo. O sistema salva e atualiza automaticamente.")

    furo_id = st.text_input(
        "ID do Furo",
        value=st.session_state.furo_atual,
        placeholder="BF-001"
    ).strip().upper()

    existente = get_furo(furo_id) if furo_id else None

    if existente:
        st.success(f"Furo {furo_id} encontrado. Você está editando o cadastro.")
        d = existente
    else:
        d = {
            "furo_id": furo_id, "projeto": "", "empresa": "Boa Fortuna Perfurações e Sondagens",
            "obra_cliente": "", "cidade_uf": "", "sonda": "", "tipo_sondagem": "Rotativa",
            "operador": "", "auxiliares": "", "coordenador": "", "supervisor": "",
            "latitude": None, "longitude": None, "precisao_gps_m": None,
            "datum": "SIRGAS 2000", "azimute": 0.0, "inclinacao": -90.0,
            "diametro": "", "data_inicio": str(date.today()), "data_fim": "",
            "profundidade_final": 0, "observacao": ""
        }

    with st.form("form_furo"):
        st.subheader("Identificação")
        c1,c2,c3 = st.columns(3)
        projeto = c1.text_input("Projeto", value=d.get("projeto") or "")
        empresa = c2.text_input("Empresa", value=d.get("empresa") or "")
        obra = c3.text_input("Cliente / Obra", value=d.get("obra_cliente") or "")

        c1,c2,c3 = st.columns(3)
        cidade = c1.text_input("Cidade / UF", value=d.get("cidade_uf") or "")
        sonda = c2.text_input("Sonda", value=d.get("sonda") or "")
        tipo = c3.selectbox(
            "Tipo de sondagem",
            ["Rotativa","Circulação reversa","Percussão","Geotécnica","Outro"],
            index=["Rotativa","Circulação reversa","Percussão","Geotécnica","Outro"].index(
                d.get("tipo_sondagem") if d.get("tipo_sondagem") in
                ["Rotativa","Circulação reversa","Percussão","Geotécnica","Outro"]
                else "Rotativa"
            )
        )

        st.subheader("Equipe")
        c1,c2,c3,c4 = st.columns(4)
        operador = c1.text_input("Operador", value=d.get("operador") or "")
        auxiliares = c2.text_input("Auxiliar(es)", value=d.get("auxiliares") or "")
        coordenador = c3.text_input("Coordenador", value=d.get("coordenador") or "")
        supervisor = c4.text_input("Supervisor / TST", value=d.get("supervisor") or "")

        st.subheader("Localização e orientação")
        c1,c2,c3 = st.columns(3)
        latitude = c1.number_input(
            "Latitude", value=float(d["latitude"]) if d.get("latitude") is not None else 0.0,
            format="%.7f"
        )
        longitude = c2.number_input(
            "Longitude", value=float(d["longitude"]) if d.get("longitude") is not None else 0.0,
            format="%.7f"
        )
        datum = c3.selectbox("Datum", ["SIRGAS 2000","WGS 84"],
                             index=0 if d.get("datum") != "WGS 84" else 1)

        c1,c2,c3,c4 = st.columns(4)
        precisao = c1.number_input(
            "Precisão GPS (m)", min_value=0.0,
            value=float(d["precisao_gps_m"] or 0)
        )
        azimute = c2.number_input("Azimute (°)", 0.0, 360.0,
                                  float(d.get("azimute") or 0), step=1.0)
        inclinacao = c3.number_input("Inclinação (°)", -90.0, 90.0,
                                      float(d.get("inclinacao") or -90), step=1.0)
        diametro = c4.text_input("Diâmetro", value=d.get("diametro") or "")

        c1,c2 = st.columns(2)
        data_inicio = c1.date_input(
            "Data de início",
            value=datetime.strptime(d["data_inicio"], "%Y-%m-%d").date()
            if d.get("data_inicio") else date.today()
        )
        data_fim = c2.date_input(
            "Data de término",
            value=datetime.strptime(d["data_fim"], "%Y-%m-%d").date()
            if d.get("data_fim") else date.today()
        )

        obs = st.text_area("Observações", value=d.get("observacao") or "")

        salvar = st.form_submit_button(
            "💾 Salvar / Atualizar Furo", use_container_width=True
        )

    colgps,_ = st.columns([1,3])
    with colgps:
        if st.button("📍 Capturar GPS automático", use_container_width=True):
            capturar_gps()

    if salvar:
        if not furo_id:
            st.error("Informe o ID do furo.")
        else:
            # Se GPS automático foi capturado, ele tem prioridade.
            lat_final = st.session_state.get("latitude", latitude)
            lng_final = st.session_state.get("longitude", longitude)
            prec_final = st.session_state.get("precisao_gps", precisao)

            salvar_furo({
                "furo_id": furo_id,
                "projeto": projeto,
                "empresa": empresa,
                "obra_cliente": obra,
                "cidade_uf": cidade,
                "sonda": sonda,
                "tipo_sondagem": tipo,
                "operador": operador,
                "auxiliares": auxiliares,
                "coordenador": coordenador,
                "supervisor": supervisor,
                "latitude": lat_final if lat_final != 0 else None,
                "longitude": lng_final if lng_final != 0 else None,
                "precisao_gps_m": prec_final if prec_final != 0 else None,
                "datum": datum,
                "azimute": azimute,
                "inclinacao": inclinacao,
                "diametro": diametro,
                "data_inicio": data_inicio.isoformat(),
                "data_fim": data_fim.isoformat(),
                "profundidade_final": proximo_intervalo(furo_id),
                "observacao": obs,
            })
            st.session_state.furo_atual = furo_id
            st.success(f"Furo {furo_id} salvo com sucesso.")
            st.rerun()

# ============================================================
# MANOBRAS
# ============================================================

elif menu == "🔩 Manobras":
    st.title("🔩 Registro de Manobras")
    furo_id = st.session_state.furo_atual

    if not get_furo(furo_id):
        st.warning("Cadastre o furo primeiro.")
        st.stop()

    atual = proximo_intervalo(furo_id)
    st.info(f"Furo **{furo_id}** | Profundidade automática atual: **{atual:.2f} m**")

    with st.form("nova_manobra"):
        c1,c2,c3 = st.columns(3)
        data_m = c1.date_input("Data", date.today())
        barrilete = c2.text_input("Barrilete", "HQ")
        operador = c3.text_input(
            "Operador",
            get_furo(furo_id).get("operador") or ""
        )

        c1,c2,c3,c4 = st.columns(4)
        de = c1.number_input("De (m)", min_value=0.0,
                             value=float(atual), step=0.5, format="%.2f")
        ate = c2.number_input("Até (m)", min_value=0.0,
                              value=float(atual+1.5), step=0.5, format="%.2f")
        avanco = round(max(0, ate-de), 2)
        recup = c3.number_input(
            "Recuperação (m)", min_value=0.0,
            value=float(avanco), step=0.1, format="%.2f"
        )
        caixa = c4.text_input("Caixa", "01")

        taxa = (recup/avanco*100) if avanco > 0 else 0
        taxa = min(taxa, 100)
        st.metric("Recuperação calculada", f"{taxa:.1f}%")

        c1,c2,c3,c4 = st.columns(4)
        inicio = c1.time_input("Horário início", time(8,0))
        fim = c2.time_input("Horário fim", time(9,30))
        tempo_min = calcular_tempo_min(inicio, fim)
        h_trab = c3.number_input(
            "Horas trabalhadas",
            min_value=0.0, value=round(tempo_min/60,2), step=0.25
        )
        h_parado = c4.number_input(
            "Horas paradas", min_value=0.0, value=0.0, step=0.25
        )

        c1,c2 = st.columns(2)
        motivo = c1.text_input("Motivo da paralisação", "Nenhum")
        litologia = c2.text_input("Litologia")

        c1,c2,c3 = st.columns(3)
        alteracao = c1.text_input("Alteração")
        mineralizacao = c2.text_input("Mineralização")
        estruturas = c3.text_input("Estruturas")

        observacoes = st.text_area("Observações")

        st.markdown("### 📸 Fotos da manobra")
        uploads = st.file_uploader(
            "Selecione até 3 fotos",
            type=["jpg","jpeg","png"],
            accept_multiple_files=True
        )

        salvar = st.form_submit_button(
            "➕ Salvar Manobra", use_container_width=True
        )

    if salvar:
        if ate <= de:
            st.error("A profundidade final deve ser maior que a inicial.")
        elif recup > avanco and avanco > 0:
            st.error("A recuperação não pode ser maior que o avanço.")
        else:
            fotos = [otimizar_imagem(x) for x in (uploads or [])[:3]]
            while len(fotos) < 3:
                fotos.append(None)

            salvar_manobra({
                "furo_id": furo_id,
                "data_manobra": data_m.isoformat(),
                "de_m": de,
                "ate_m": ate,
                "avanco_m": avanco,
                "recup_m": recup,
                "taxa_recup_pct": taxa,
                "caixa": caixa,
                "barrilete": barrilete,
                "horario_inicio": inicio.strftime("%H:%M"),
                "horario_fim": fim.strftime("%H:%M"),
                "tempo_manobra_min": tempo_min,
                "horas_trab": h_trab,
                "horas_parado": h_parado,
                "motivo_parada": motivo,
                "litologia": litologia,
                "alteracao": alteracao,
                "mineralizacao": mineralizacao,
                "estruturas": estruturas,
                "observacoes": observacoes,
                "operador": operador,
                "foto1": fotos[0],
                "foto2": fotos[1],
                "foto3": fotos[2],
            })
            st.success(f"Manobra {de:.2f} → {ate:.2f} m salva.")
            st.rerun()

    df = get_manobras(furo_id)
    st.divider()
    st.subheader(f"Histórico — {furo_id}")

    if df.empty:
        st.info("Nenhuma manobra registrada.")
    else:
        view = df[[
            "id","data_manobra","de_m","ate_m","avanco_m",
            "recup_m","taxa_recup_pct","caixa","barrilete",
            "horario_inicio","horario_fim","horas_trab","horas_parado",
            "motivo_parada","litologia"
        ]].copy()
        st.dataframe(view, use_container_width=True, hide_index=True)

        opcoes = {
            f"#{int(r.id)} — {r.de_m:.2f} → {r.ate_m:.2f} m":
            int(r.id)
            for _, r in df.iterrows()
        }
        c1,c2 = st.columns([3,1])
        escolha = c1.selectbox("Manobra", list(opcoes.keys()))
        if c2.button("🗑️ Excluir", use_container_width=True):
            excluir_manobra(opcoes[escolha])
            st.success("Manobra excluída.")
            st.rerun()

# ============================================================
# TESTEMUNHO / FOTOS
# ============================================================

elif menu == "🪨 Testemunho / Fotos":
    st.title("🪨 Testemunho e Registro Fotográfico")
    furo_id = st.session_state.furo_atual
    df = get_manobras(furo_id)

    if df.empty:
        st.info("Registre manobras com fotos primeiro.")
    else:
        for _, r in df.iterrows():
            fotos = [blob_to_image(r[c]) for c in ["foto1","foto2","foto3"]]
            fotos = [x for x in fotos if x is not None]
            if fotos:
                with st.expander(
                    f"📦 Caixa {r['caixa']} | {r['de_m']:.2f} → {r['ate_m']:.2f} m"
                ):
                    st.write(
                        f"Recuperação: **{r['taxa_recup_pct']:.1f}%** | "
                        f"Litologia: **{r['litologia'] or '-'}**"
                    )
                    cols = st.columns(len(fotos))
                    for col, img in zip(cols, fotos):
                        col.image(img, use_container_width=True)

# ============================================================
# GEOLOGIA
# ============================================================

elif menu == "🧱 Geologia":
    st.title("🧱 Geologia")
    furo_id = st.session_state.furo_atual

    atual = proximo_intervalo(furo_id)
    with st.form("form_geo"):
        c1,c2 = st.columns(2)
        de = c1.number_input("De (m)", min_value=0.0, value=0.0, step=0.5)
        ate = c2.number_input("Até (m)", min_value=0.0,
                              value=max(1.0, atual), step=0.5)

        c1,c2 = st.columns(2)
        litologia = c1.text_input("Litologia")
        alteracao = c2.text_input("Alteração")

        c1,c2 = st.columns(2)
        mineralizacao = c1.text_input("Mineralização")
        estruturas = c2.text_input("Estruturas")

        observacoes = st.text_area("Observações")
        salvar = st.form_submit_button(
            "➕ Salvar Intervalo Geológico", use_container_width=True
        )

    if salvar:
        if ate <= de:
            st.error("Até deve ser maior que De.")
        else:
            salvar_geologia({
                "furo_id": furo_id,
                "de_m": de, "ate_m": ate,
                "litologia": litologia,
                "alteracao": alteracao,
                "mineralizacao": mineralizacao,
                "estruturas": estruturas,
                "observacoes": observacoes
            })
            st.success("Intervalo geológico salvo.")
            st.rerun()

    df = get_geologia(furo_id)
    if not df.empty:
        st.subheader("Perfil geológico registrado")
        st.dataframe(
            df[["id","de_m","ate_m","litologia","alteracao",
                "mineralizacao","estruturas","observacoes"]],
            use_container_width=True, hide_index=True
        )

        opcoes = {
            f"#{int(r.id)} — {r.de_m:.2f} → {r.ate_m:.2f} m":
            int(r.id)
            for _, r in df.iterrows()
        }
        escolha = st.selectbox("Intervalo", list(opcoes.keys()))
        if st.button("🗑️ Excluir intervalo geológico"):
            excluir_geologia(opcoes[escolha])
            st.rerun()

# ============================================================
# PDF
# ============================================================

elif menu == "📄 Relatório PDF":
    st.title("📄 Relatório de Sondagem")
    furo_id = st.session_state.furo_atual
    s = estatisticas_furo(furo_id)

    st.write(
        f"Furo **{furo_id}** — {s['metros']:.2f} m perfurados — "
        f"{s['rec_pct']:.1f}% de recuperação"
    )

    if st.button("📄 Gerar Boletim PDF", use_container_width=True):
        pdf = gerar_pdf(furo_id)
        st.download_button(
            "📥 Baixar PDF",
            data=pdf,
            file_name=f"BDS_{furo_id}_{date.today().isoformat()}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ============================================================
# BANCO
# ============================================================

elif menu == "🗃️ Banco de Dados":
    st.title("🗃️ Banco de Dados")
    st.caption("Visão administrativa dos dados gravados no SQLite.")

    furos = get_furos()
    st.subheader("Furos")
    if furos.empty:
        st.info("Nenhum furo cadastrado.")
    else:
        st.dataframe(furos, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Exportação")

        csv = furos.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Exportar cadastro dos furos — CSV",
            csv,
            "furos.csv",
            "text/csv"
        )

    conn = get_conn()
    man = pd.read_sql_query("SELECT * FROM manobras ORDER BY id DESC", conn)
    geo = pd.read_sql_query("SELECT * FROM geologia ORDER BY id DESC", conn)
    conn.close()

    st.subheader("Manobras")
    st.dataframe(man.drop(columns=["foto1","foto2","foto3"], errors="ignore"),
                 use_container_width=True, hide_index=True)

    if not man.empty:
        st.download_button(
            "📥 Exportar manobras — CSV",
            man.drop(columns=["foto1","foto2","foto3"], errors="ignore")
            .to_csv(index=False).encode("utf-8-sig"),
            "manobras.csv",
            "text/csv"
        )

    st.subheader("Geologia")
    st.dataframe(geo, use_container_width=True, hide_index=True)

    if not geo.empty:
        st.download_button(
            "📥 Exportar geologia — CSV",
            geo.to_csv(index=False).encode("utf-8-sig"),
            "geologia.csv",
            "text/csv"
        )
