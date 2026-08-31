import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Diário de Sondagem - C4 Coring",
    page_icon="⛏️",
    layout="wide"
)

# ==========================================
# FUNÇÕES BANCO DE DADOS (SQLITE)
# ==========================================
DB_NAME = "sondagem.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de Manobras
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manobras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            furo_id TEXT,
            de_m REAL,
            ate_m REAL,
            avanco_m REAL,
            recup_m REAL,
            recup_pct REAL,
            rqd_m REAL,
            rqd_pct REAL,
            qualidade_rqd TEXT,
            litologia TEXT,
            fluido TEXT,
            data_registro TEXT
        )
    """)
    
    # Tabela de Paradas (Downtime)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            furo_id TEXT,
            categoria TEXT,
            horas REAL,
            observacao TEXT,
            horario TEXT
        )
    """)
    
    conn.commit()
    conn.close()

# Inicializa o banco ao carregar o app
init_db()

def salvar_manobra(furo, de, ate, avanco, recup, recup_pct, rqd, rqd_pct, qual_rqd, lito, fluido):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO manobras (furo_id, de_m, ate_m, avanco_m, recup_m, recup_pct, rqd_m, rqd_pct, qualidade_rqd, litologia, fluido, data_registro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (furo, de, ate, avanco, recup, recup_pct, rqd, rqd_pct, qual_rqd, lito, fluido, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def salvar_parada(furo, categoria, horas, obs):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO paradas (furo_id, categoria, horas, observacao, horario)
        VALUES (?, ?, ?, ?, ?)
    """, (furo, categoria, horas, obs, datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()

def carregar_manobras(furo):
    conn = get_connection()
    df = pd.read_sql_query("SELECT de_m AS 'De (m)', ate_m AS 'Até (m)', avanco_m AS 'Avanço (m)', recup_m AS 'Recup. (m)', recup_pct AS 'Recup. (%)', rqd_m AS 'RQD (m)', rqd_pct AS 'RQD (%)', qualidade_rqd AS 'Qualidade RQD', litologia AS 'Litologia', fluido AS 'Fluido' FROM manobras WHERE furo_id = ? ORDER BY de_m ASC", conn, params=(furo,))
    conn.close()
    return df

def carregar_paradas(furo):
    conn = get_connection()
    df = pd.read_sql_query("SELECT categoria AS 'Categoria', horas AS 'Horas', observacao AS 'Observação', horario AS 'Horário' FROM paradas WHERE furo_id = ?", conn, params=(furo,))
    conn.close()
    return df

# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================
st.title("⛏️ Diário de Campo - Sondagem C4 Coring")
st.markdown("Sistema Avançado com Persistência em Banco de Dados **SQLite**")

aba_geral, aba_manobra, aba_downtime, aba_perfil = st.tabs([
    "📋 Dados Gerais", 
    "🛠️ Registro de Manobra", 
    "⏱️ Horas Paradas (Downtime)", 
    "📉 Perfil Litológico (Striplog)"
])

# ABA 1: DADOS GERAIS
with aba_geral:
    st.subheader("Identificação do Furo e Projeto")
    c1, c2, c3 = st.columns(3)
    with c1:
        projeto = st.text_input("Projeto / Mina", value="Mina Alpha")
        furo_id = st.text_input("Identificação do Furo (ID)", value="FD-2026-001")
    with c2:
        sonda = st.text_input("Equipamento / Sonda", value="C4 Coring #02")
        operador = st.text_input("Sondador / Operador", value="Natanael Souza")
    with c3:
        data_sondagem = st.date_input("Data do Boletim", value=datetime.now())
        diametro = st.selectbox("Diâmetro de Perfuração", ["HQ (63.5 mm)", "NQ (47.6 mm)", "BQ (36.5 mm)", "PQ (85.0 mm)"])

# ABA 2: REGISTRO DE MANOBRA
with aba_manobra:
    st.subheader("Lançamento de Manobras e Testemunhos")

    df_existente = carregar_manobras(furo_id)
    if not df_existente.empty:
        ult_ate = df_existente.iloc[-1]["Até (m)"]
    else:
        ult_ate = 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        de_m = st.number_input("Profundidade Inicial 'De' (m)", min_value=0.0, value=float(ult_ate), step=0.1, format="%.2f")
    with col2:
        ate_m = st.number_input("Profundidade Final 'Até' (m)", min_value=float(de_m), value=float(de_m + 1.50), step=0.1, format="%.2f")

    avanco_calc = round(max(0.0, ate_m - de_m), 2)

    with col3:
        recup_m = st.number_input("Recuperação Medida (m)", min_value=0.0, max_value=float(avanco_calc) if avanco_calc > 0 else 0.01, value=float(avanco_calc), step=0.05, format="%.2f")
    with col4:
        rqd_m = st.number_input("Soma Pedaços ≥ 10cm (m)", min_value=0.0, max_value=float(recup_m) if recup_m > 0 else 0.01, value=float(recup_m), step=0.05, format="%.2f")

    taxa_recup = round((recup_m / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0
    taxa_rqd = round((rqd_m / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0

    if taxa_rqd < 25:
        class_rqd, cor_rqd = "Muito Má 🔴", "#EF4444"
    elif taxa_rqd < 50:
        class_rqd, cor_rqd = "Má 🟠", "#F97316"
    elif taxa_rqd < 75:
        class_rqd, cor_rqd = "Regular 🟡", "#EAB308"
    elif taxa_rqd < 90:
        class_rqd, cor_rqd = "Boa 🟢", "#22C55E"
    else:
        class_rqd, cor_rqd = "Excelente 🔵", "#3B82F6"

    st.markdown(f"""
    <div style="background-color: #F8FAFC; padding: 12px; border-radius: 8px; border: 1px solid #E2E8F0; margin: 10px 0px;">
        <b>⚡ Avanço:</b> {avanco_calc:.2f} m &nbsp;|&nbsp; 
        <b>📊 Recuperação:</b> {taxa_recup:.1f}% &nbsp;|&nbsp; 
        <b>💎 RQD:</b> {taxa_rqd:.1f}% (<span style="color:{cor_rqd}; font-weight:bold;">{class_rqd}</span>)
    </div>
    """, unsafe_allow_html=True)

    c_geo1, c_geo2 = st.columns(2)
    with c_geo1:
        litologia = st.selectbox("Descrição Litológica", [
            "Solo de Alteração / Argila", "Basalto Alterado", "Basalto Sano", 
            "Arenito", "Brecha Vulcânica", "Gneiss", "Quartzito"
        ])
    with c_geo2:
        perda_agua = st.select_slider("💧 Circulação de Fluido / Perda de Água", options=["Nenhuma (100% Retorno)", "Parcial (50%-80%)", "Alta (10%-40%)", "Total (0% Retorno)"])

    if st.button("💾 Salvar Manobra no SQLite", use_container_width=True):
        if avanco_calc <= 0:
            st.error("O valor de 'Até' deve ser superior ao valor de 'De'.")
        else:
            salvar_manobra(furo_id, de_m, ate_m, avanco_calc, recup_m, taxa_recup, rqd_m, taxa_rqd, class_rqd, litologia, perda_agua)
            st.success("Manobra gravada no banco de dados SQLite com sucesso!")
            st.rerun()

    # Tabela
    df_manobras = carregar_manobras(furo_id)
    if not df_manobras.empty:
        st.markdown(f"### Histórico de Manobras - Furo `{furo_id}`")
        st.dataframe(df_manobras, use_container_width=True)

# ABA 3: APONTAMENTO DE DOWNTIME
with aba_downtime:
    st.subheader("Registro de Tempo Parado (Downtime)")

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        categoria_parada = st.selectbox("Motivo da Parada", [
            "Manutenção Preventiva", "Manutenção Corretiva (Quebra)", "Troca de Coroa / Widea",
            "Aguardando Água / Abastecimento", "Condições Climáticas (Chuva)", "Manobra de Hastes / Preparação", "Mudança de Praça"
        ])
    with col_d2:
        horas_paradas = st.number_input("Duração (Horas)", min_value=0.1, max_value=24.0, value=0.5, step=0.1)
    with col_d3:
        obs_parada = st.text_input("Observações / Detalhes", value="Ajustes de rotina")

    if st.button("💾 Registrar Parada no SQLite", use_container_width=True):
        salvar_parada(furo_id, categoria_parada, horas_paradas, obs_parada)
        st.success("Parada gravada com sucesso!")
        st.rerun()

    df_paradas = carregar_paradas(furo_id)
    if not df_paradas.empty:
        st.dataframe(df_paradas, use_container_width=True)
        fig_paradas = px.pie(df_paradas, names="Categoria", values="Horas", title="Distribuição de Horas Paradas", hole=0.4)
        st.plotly_chart(fig_paradas, use_container_width=True)

# ABA 4: PERFIL LITOLÓGICO
with aba_perfil:
    st.subheader("Perfil Geológico Vertical e RQD")

    df_striplog = carregar_manobras(furo_id)
    if not df_striplog.empty:
        fig_striplog = px.bar(
            df_striplog,
            x="Avanço (m)",
            y="De (m)",
            color="Litologia",
            orientation='h',
            hover_data=["Até (m)", "Recup. (%)", "RQD (%)", "Fluido"],
            title=f"Coluna Estratigráfica - Furo: {furo_id}",
            labels={"De (m)": "Profundidade Inicial (m)", "Avanço (m)": "Espessura (m)"},
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_striplog.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_striplog, use_container_width=True)

        fig_rqd = px.line(
            df_striplog,
            x="De (m)",
            y=["Recup. (%)", "RQD (%)"],
            markers=True,
            title="Variação de Recuperação e RQD ao longo da Profundidade"
        )
        st.plotly_chart(fig_rqd, use_container_width=True)
    else:
        st.info("Registre pelo menos uma manobra para visualizar o perfil gráfico.")
