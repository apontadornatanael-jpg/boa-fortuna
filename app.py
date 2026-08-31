import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

# ==========================================
# 1. CONFIGURAÇÃO E ESTILIZACÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="CoreLog Pro - Geotechnical Drilling System",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS para acabamento profissional
st.markdown("""
<style>
    /* Estilização Geral */
    .main { background-color: #F8FAFC; }
    
    /* Cards de Métricas Customizados */
    .metric-card {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 5px solid #2563EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 15px;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1E293B;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #94A3B8;
        margin-top: 2px;
    }
    
    /* Destaques em Tabelas e Botões */
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CAMADA DE BANCO DE DADOS (SQLITE)
# ==========================================
DB_NAME = "sondagem_geotecnica.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de Cadastro de Furos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS furos (
            furo_id TEXT PRIMARY KEY,
            projeto TEXT,
            sonda TEXT,
            sondador TEXT,
            diametro TEXT,
            coordenada_n REAL,
            coordenada_e REAL,
            cota REAL,
            inclinacao REAL,
            azimute REAL,
            data_inicio TEXT
        )
    """)
    
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
            caixa_num INTEGER,
            perda_agua TEXT,
            data_hora TEXT,
            FOREIGN KEY (furo_id) REFERENCES furos (furo_id)
        )
    """)
    
    # Tabela de Paradas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            furo_id TEXT,
            categoria TEXT,
            horas REAL,
            observacao TEXT,
            data_hora TEXT,
            FOREIGN KEY (furo_id) REFERENCES furos (furo_id)
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# --- OPERAÇÕES CRUD ---
def salvar_furo(furo_id, projeto, sonda, sondador, diametro, n, e, cota, inc, az, data_i):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO furos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (furo_id, projeto, sonda, sondador, diametro, n, e, cota, inc, az, str(data_i)))
    conn.commit()
    conn.close()

def salvar_manobra(furo, de, ate, avanco, recup, recup_pct, rqd, rqd_pct, qual_rqd, lito, caixa, fluido):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO manobras (furo_id, de_m, ate_m, avanco_m, recup_m, recup_pct, rqd_m, rqd_pct, qualidade_rqd, litologia, caixa_num, perda_agua, data_hora)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (furo, de, ate, avanco, recup, recup_pct, rqd, rqd_pct, qual_rqd, lito, caixa, fluido, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def salvar_parada(furo, categoria, horas, obs):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO paradas (furo_id, categoria, horas, observacao, data_hora)
        VALUES (?, ?, ?, ?, ?)
    """, (furo, categoria, horas, obs, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def carregar_furos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT furo_id FROM furos ORDER BY furo_id", conn)
    conn.close()
    return df['furo_id'].tolist()

def carregar_dados_furo(furo_id):
    conn = get_connection()
    furo = pd.read_sql_query("SELECT * FROM furos WHERE furo_id = ?", conn, params=(furo_id,))
    manobras = pd.read_sql_query("SELECT * FROM manobras WHERE furo_id = ? ORDER BY de_m ASC", conn, params=(furo_id,))
    paradas = pd.read_sql_query("SELECT * FROM paradas WHERE furo_id = ?", conn, params=(furo_id,))
    conn.close()
    return furo, manobras, paradas

def deletar_registro(tabela, record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {tabela} WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

# ==========================================
# 3. BARRA LATERAL (SIDEBAR) & NAVEGAÇÃO
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/mine-cart.png", width=64)
    st.title("CoreLog Pro v2.5")
    st.caption("Sistema de Controle de Sondagem Rotativa")
    st.markdown("---")
    
    lista_furos = carregar_furos()
    
    st.subheader("📌 Seleção de Trabalho")
    if not lista_furos:
        st.warning("Nenhum furo cadastrado. Cadastre o primeiro furo para começar.")
        furo_selecionado = None
    else:
        furo_selecionado = st.selectbox("Selecione o Furo Ativo:", lista_furos)

    st.markdown("---")
    with st.expander("➕ Cadastrar Novo Furo / Praça"):
        with st.form("form_novo_furo"):
            nf_id = st.text_input("ID do Furo *", value=f"FD-2026-00{len(lista_furos)+1}")
            nf_proj = st.text_input("Projeto", value="Projeto Alvo Sul")
            nf_sonda = st.text_input("Sonda", value="Sonda C4-02")
            nf_sondador = st.text_input("Sondador Responsável", value="Natanael Souza")
            nf_diam = st.selectbox("Diâmetro Inicial", ["HQ (63.5 mm)", "NQ (47.6 mm)", "BQ (36.5 mm)", "PQ (85.0 mm)"])
            nf_inc = st.number_input("Inclinação (°)", min_value=-90.0, max_value=90.0, value=-90.0)
            nf_az = st.number_input("Azimute (°)", min_value=0.0, max_value=360.0, value=0.0)
            btn_criar = st.form_submit_button("Criar Furo", use_container_width=True)
            
            if btn_criar:
                if nf_id:
                    salvar_furo(nf_id, nf_proj, nf_sonda, nf_sondador, nf_diam, 0, 0, 0, nf_inc, nf_az, datetime.now().date())
                    st.success(f"Furo {nf_id} criado!")
                    st.rerun()

# ==========================================
# 4. PAINEL PRINCIPAL
# ==========================================
if not furo_selecionado:
    st.info("👈 Utilize a barra lateral para cadastrar e selecionar um furo para gerenciamento.")
    st.stop()

# Carregamento dos dados do Furo
df_furo_info, df_manobras, df_paradas = carregar_dados_furo(furo_selecionado)

# CABEÇALHO DO FURO
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.title(f"📍 Furo: `{furo_selecionado}`")
    st.caption(f"**Projeto:** {df_furo_info['projeto'].iloc[0]} | **Sonda:** {df_furo_info['sonda'].iloc[0]} | **Sondador:** {df_furo_info['sondador'].iloc[0]}")
with col_head2:
    st.metric("Inclinação / Azimute", f"{df_furo_info['inclinacao'].iloc[0]}° / {df_furo_info['azimute'].iloc[0]}°")

# CÁLCULO DAS MÉTRICAS GERAIS (KPIs)
prof_max = df_manobras['ate_m'].max() if not df_manobras.empty else 0.0
recup_media = df_manobras['recup_pct'].mean() if not df_manobras.empty else 0.0
rqd_medio = df_manobras['rqd_pct'].mean() if not df_manobras.empty else 0.0
total_downtime = df_paradas['horas'].sum() if not df_paradas.empty else 0.0

# CARDS DE VISUALIZAÇÃO EXECUTIVA
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #2563EB;">
        <div class="metric-title">Profundidade Atual</div>
        <div class="metric-value">{prof_max:.2f} m</div>
        <div class="metric-sub">Total perfurado acumulado</div>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    color_rec = "#22C55E" if recup_media >= 85 else "#EF4444"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {color_rec};">
        <div class="metric-title">Recuperação Média</div>
        <div class="metric-value">{recup_media:.1f}%</div>
        <div class="metric-sub">Meta Operacional: &ge; 85%</div>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #8B5CF6;">
        <div class="metric-title">RQD Médio</div>
        <div class="metric-value">{rqd_medio:.1f}%</div>
        <div class="metric-sub">Qualidade do Maciço</div>
    </div>
    """, unsafe_allow_html=True)

with kpi4:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #F59E0B;">
        <div class="metric-title">Horas Imobilizadas</div>
        <div class="metric-value">{total_downtime:.1f} h</div>
        <div class="metric-sub">Tempo Total em Parada</div>
    </div>
    """, unsafe_allow_html=True)

# ABAS NAVEGÁVEIS DO SISTEMA
tab_log, tab_downtime, tab_perfil, tab_gestao = st.tabs([
    "🛠️ Apontamento de Manobra", 
    "⏱️ Registro de Downtime", 
    "📊 Perfil Geotécnico & Striplog",
    "🗃️ Gestão e Exportação"
])

# ==========================================
# ABA 1: APONTAMENTO DE MANOBRA
# ==========================================
with tab_log:
    st.subheader("Registro de Manobra de Sondagem")
    
    ult_prof = prof_max
    
    with st.form("form_manobra", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            de_input = st.number_input("De (m)", min_value=0.0, value=float(ult_prof), step=0.1, format="%.2f")
        with c2:
            ate_input = st.number_input("Até (m)", min_value=float(de_input), value=float(de_input + 1.50), step=0.1, format="%.2f")
        
        avanco_calc = round(max(0.0, ate_input - de_input), 2)
        
        with c3:
            recup_input = st.number_input("Recuperação (m)", min_value=0.0, max_value=float(avanco_calc) if avanco_calc > 0 else 0.01, value=float(avanco_calc), step=0.05, format="%.2f")
        with c4:
            rqd_input = st.number_input("RQD (m) [Pedaços ≥ 10cm]", min_value=0.0, max_value=float(recup_input) if recup_input > 0 else 0.01, value=float(recup_input), step=0.05, format="%.2f")
            
        # Cálculos de Percentuais Automáticos
        recup_pct_calc = round((recup_input / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0
        rqd_pct_calc = round((rqd_input / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0
        
        # Classificação Deere et al.
        if rqd_pct_calc < 25:
            qual_rqd, cor_tag = "Muito Má (<25%)", "#EF4444"
        elif rqd_pct_calc < 50:
            qual_rqd, cor_tag = "Má (25-50%)", "#F97316"
        elif rqd_pct_calc < 75:
            qual_rqd, cor_tag = "Regular (50-75%)", "#EAB308"
        elif rqd_pct_calc < 90:
            qual_rqd, cor_tag = "Boa (75-90%)", "#22C55E"
        else:
            qual_rqd, cor_tag = "Excelente (90-100%)", "#3B82F6"
            
        c5, c6, c7 = st.columns([2, 2, 1])
        with c5:
            litologia_input = st.selectbox("Litologia Predominante", [
                "Solo de Alteração", "Saprolito", "Basalto Alterado", "Basalto Sano", 
                "Arenito Fine", "Gneiss Milonitizado", "Quartzito", "Brecha Diaclasada"
            ])
        with c6:
            fluido_input = st.select_slider("💧 Retorno de Água / Fluido", options=["Nenhum (100% Perda)", "Baixo (10-40%)", "Médio (50-80%)", "Total (100% Retorno)"])
        with c7:
            num_caixa = st.number_input("Nº da Caixa", min_value=1, value=1, step=1)
            
        st.markdown(f"""
        <div style="background-color: #F1F5F9; padding: 10px; border-radius: 6px; margin-bottom: 15px;">
            <b>⚡ Avanço:</b> {avanco_calc:.2f} m &nbsp;|&nbsp; 
            <b>📊 Recuperação:</b> {recup_pct_calc:.1f}% &nbsp;|&nbsp; 
            <b>💎 RQD:</b> {rqd_pct_calc:.1f}% (<span style="color:{cor_tag}; font-weight:bold;">{qual_rqd}</span>)
        </div>
        """, unsafe_allow_html=True)
        
        btn_gravar_manobra = st.form_submit_button("💾 Gravar Manobra no Banco de Dados", use_container_width=True)
        
        if btn_gravar_manobra:
            if avanco_calc <= 0:
                st.error("Erro: A profundidade 'Até' deve ser estritamente maior que 'De'.")
            else:
                salvar_manobra(furo_selecionado, de_input, ate_input, avanco_calc, recup_input, recup_pct_calc, rqd_input, rqd_pct_calc, qual_rqd, litologia_input, num_caixa, fluido_input)
                st.success("Manobra registrada com sucesso!")
                st.rerun()

    # Tabela Visual de Manobras Registradas
    if not df_manobras.empty:
        st.markdown("### 📜 Registros de Manobras do Furo")
        
        # Formatação Visual da Tabela
        df_exibir = df_manobras.rename(columns={
            "de_m": "De (m)", "ate_m": "Até (m)", "avanco_m": "Avanço (m)",
            "recup_m": "Rec. (m)", "recup_pct": "Rec. (%)", "rqd_m": "RQD (m)",
            "rqd_pct": "RQD (%)", "qualidade_rqd": "Qualidade", "litologia": "Litologia",
            "caixa_num": "Caixa Nº", "perda_agua": "Retorno Fluido"
        })
        st.dataframe(df_exibir[["De (m)", "Até (m)", "Avanço (m)", "Rec. (m)", "Rec. (%)", "RQD (m)", "RQD (%)", "Qualidade", "Litologia", "Caixa Nº"]], use_container_width=True)

# ==========================================
# ABA 2: REGISTRO DE DOWNTIME
# ==========================================
with tab_downtime:
    st.subheader("Registro de Tempos Imobilizados (Downtime)")
    
    col_d1, col_d2 = st.columns([1, 2])
    
    with col_d1:
        with st.form("form_downtime"):
            cat_parada = st.selectbox("Motivo da Parada", [
                "Manutenção Corretiva (Quebra)", "Manutenção Preventiva", 
                "Troca de Coroa / Ferramental", "Aguardando Água / Abastecimento",
                "Mudança de Praça / Mudança de Furo", "Condições Climáticas (Chuva)",
                "Diálogo de Segurança / Treinamento", "Aguardando Geólogo / Orientação"
            ])
            horas_p = st.number_input("Tempo Parado (Horas)", min_value=0.1, max_value=24.0, value=0.5, step=0.1)
            obs_p = st.text_area("Observação do Ocorrido", value="Substituição de mola do barrilete.")
            btn_salvar_p = st.form_submit_button("Registrar Parada", use_container_width=True)
            
            if btn_salvar_p:
                salvar_parada(furo_selecionado, cat_parada, horas_p, obs_p)
                st.success("Parada lançada!")
                st.rerun()

    with col_d2:
        if not df_paradas.empty:
            fig_pie = px.pie(
                df_paradas, 
                names="categoria", 
                values="horas", 
                title="Horas Paradas por Categoria",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.dataframe(df_paradas[["categoria", "horas", "observacao", "data_hora"]].rename(columns={
                "categoria": "Categoria", "horas": "Duração (h)", "observacao": "Detalhes", "data_hora": "Data/Hora"
            }), use_container_width=True)

# ==========================================
# ABA 3: PERFIL GEOTÉCNICO & STRIPLOG
# ==========================================
with tab_perfil:
    st.subheader("Visualização do Perfil Geológico e Geotécnico Vertical")
    
    if df_manobras.empty:
        st.info("Registre manobras para gerar a coluna estratigráfica e o perfil de RQD.")
    else:
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            # Gráfico de Perfil Litológico
            fig_lito = px.bar(
                df_manobras,
                x="avanco_m",
                y="de_m",
                color="litologia",
                orientation='h',
                title="<b>Coluna Estratigráfica (Litologia)</b>",
                labels={"de_m": "Profundidade (m)", "avanco_m": "Espessura (m)"},
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_lito.update_layout(yaxis=dict(autorange="reversed"), height=450)
            st.plotly_chart(fig_lito, use_container_width=True)
            
        with col_p2:
            # Gráfico de Variação de Recuperação e RQD
            fig_rqd = go.Figure()
            fig_rqd.add_trace(go.Scatter(x=df_manobras['de_m'], y=df_manobras['recup_pct'], name="Recuperação (%)", mode='lines+markers', line=dict(color='#22C55E', width=2)))
            fig_rqd.add_trace(go.Scatter(x=df_manobras['de_m'], y=df_manobras['rqd_pct'], name="RQD (%)", mode='lines+markers', line=dict(color='#3B82F6', width=2)))
            
            fig_rqd.update_layout(
                title="<b>Perfil de Recuperação e RQD x Profundidade</b>",
                xaxis_title="Profundidade (m)",
                yaxis_title="Percentual (%)",
                yaxis=dict(range=[0, 105]),
                height=450
            )
            st.plotly_chart(fig_rqd, use_container_width=True)

# ==========================================
# ABA 4: GESTÃO DE DADOS E EXPORTAÇÃO
# ==========================================
with tab_gestao:
    st.subheader("Gerenciamento de Registros e Exportação de Relatórios")
    
    col_e1, col_e2 = st.columns(2)
    
    with col_e1:
        st.markdown("### 📥 Exportar Dados")
        st.write("Baixe a planilha consolidada para arquivamento ou envio ao cliente.")
        
        if not df_manobras.empty:
            csv_manobras = df_manobras.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Baixar Boletim de Manobras (CSV)",
                data=csv_manobras,
                file_name=f"boletim_sondagem_{furo_selecionado}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
    with col_e2:
        st.markdown("### 🗑️ Exclusão de Registros Incorretos")
        if not df_manobras.empty:
            manobra_del = st.selectbox("Selecione o ID da Manobra para Remover:", df_manobras['id'].tolist())
            if st.button("Remover Manobra Selecionada", type="primary"):
                deletar_registro("manobras", manobra_del)
                st.success(f"Manobra #{manobra_del} removida com sucesso.")
                st.rerun()
