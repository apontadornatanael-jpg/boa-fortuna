import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Diário de Sondagem - C4 Coring",
    page_icon="⛏️",
    layout="wide"
)

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO (PERSISTÊNCIA LOCAL) ---
# ✅ CÓDIGO CORRIGIDO:
if "manobras" not in st.session_state:
    st.session_state["manobras"] = []

if "paradas" not in st.session_state:
    st.session_state["paradas"] = []

st.title("⛏️ Diário de Campo - Sondagem C4 Coring")
st.markdown("Sistema Avançado de Gestão de Sondagem Rotativa e Geotecnia")

# --- ABAS DA APLICAÇÃO ---
aba_geral, aba_manobra, aba_downtime, aba_perfil = st.tabs([
    "📋 Dados Gerais", 
    "🛠️ Registro de Manobra", 
    "⏱️ Horas Paradas (Downtime)", 
    "📉 Perfil Litológico (Striplog)"
])

# ==========================================
# ABA 1: DADOS GERAIS DO FURO
# ==========================================
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

# ==========================================
# ABA 2: REGISTRO DE MANOBRA (COM RQD E VALIDAÇÃO)
# ==========================================
with aba_manobra:
    st.subheader("Lançamento de Manobras e Testemunhos")

    # Obter a última profundidade para continuidade automática
    if len(st.session_state["manobras"]) > 0:
        ult_ate = st.session_state["manobras"][-1]["Até (m)"]
    else:
        ult_ate = 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        de_m = st.number_input(
            "Profundidade Inicial 'De' (m)", 
            min_value=0.0, 
            value=float(ult_ate), 
            step=0.1, 
            format="%.2f"
        )
    with col2:
        ate_m = st.number_input(
            "Profundidade Final 'Até' (m)", 
            min_value=float(de_m), 
            value=float(de_m + 1.50), 
            step=0.1, 
            format="%.2f"
        )

    # Avanço Real
    avanco_calc = round(max(0.0, ate_m - de_m), 2)

    with col3:
        recup_m = st.number_input(
            "Recuperação Medida (m)", 
            min_value=0.0, 
            max_value=float(avanco_calc) if avanco_calc > 0 else 0.01, 
            value=float(avanco_calc), 
            step=0.05, 
            format="%.2f"
        )
    with col4:
        rqd_m = st.number_input(
            "Soma Pedaços ≥ 10cm (m)", 
            min_value=0.0, 
            max_value=float(recup_m) if recup_m > 0 else 0.01, 
            value=float(recup_m), 
            step=0.05, 
            format="%.2f"
        )

    # Cálculos Automáticos
    taxa_recup = round((recup_m / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0
    taxa_rqd = round((rqd_m / avanco_calc * 100), 1) if avanco_calc > 0 else 0.0

    # Classificação RQD
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

    # Indicadores
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
            "Solo de Alteração / Argila",
            "Basalto Alterado",
            "Basalto Sano",
            "Arenito",
            "Brecha Vulcânica",
            "Gneiss",
            "Quartzito"
        ])
    with c_geo2:
        perda_agua = st.select_slider(
            "💧 Circulação de Fluido / Perda de Água",
            options=["Nenhuma (100% Retorno)", "Parcial (50%-80%)", "Alta (10%-40%)", "Total (0% Retorno)"]
        )

    if st.button("➕ Adicionar Manobra", use_container_width=True):
        if avanco_calc <= 0:
            st.error("O valor de 'Até' deve ser superior ao valor de 'De'.")
        else:
            st.session_state["manobras"].append({
                "De (m)": de_m,
                "Até (m)": ate_m,
                "Avanço (m)": avanco_calc,
                "Recup. (m)": recup_m,
                "Recup. (%)": taxa_recup,
                "RQD (m)": rqd_m,
                "RQD (%)": taxa_rqd,
                "Qualidade RQD": class_rqd,
                "Litologia": litologia,
                "Fluido": perda_agua
            })
            st.success("Manobra registrada com sucesso!")
            st.rerun()

    # Tabela de Manobras Registradas
    if len(st.session_state["manobras"]) > 0:
        st.markdown("### Histórico de Manobras")
        df_manobras = pd.DataFrame(st.session_state["manobras"])
        st.dataframe(df_manobras, use_container_width=True)

# ==========================================
# ABA 3: APONTAMENTO DE DOWNTIME (HORAS PARADAS)
# ==========================================
with aba_downtime:
    st.subheader("Registro de Tempo Parado e Eficiência Operacional")

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        categoria_parada = st.selectbox("Motivo da Parada", [
            "Manutenção Preventiva",
            "Manutenção Corretiva (Quebra)",
            "Troca de Coroa / Widea",
            "Aguardando Água / Abastecimento",
            "Condições Climáticas (Chuva)",
            "Manobra de Hastes / Preparação",
            "Mudança de Praça"
        ])
    with col_d2:
        horas_paradas = st.number_input("Duração (Horas)", min_value=0.1, max_value=24.0, value=0.5, step=0.1)
    with col_d3:
        obs_parada = st.text_input("Observações / Detalhes", value="Troca preventiva do selo do barrilete")

    if st.button("⏱️ Registrar Parada", use_container_width=True):
        st.session_state["paradas"].append({
            "Categoria": categoria_parada,
            "Horas": horas_paradas,
            "Observação": obs_parada,
            "Horário": datetime.now().strftime("%H:%M")
        })
        st.success("Parada registrada!")
        st.rerun()

    if len(st.session_state["paradas"]) > 0:
        df_paradas = pd.DataFrame(st.session_state["paradas"])
        st.dataframe(df_paradas, use_container_width=True)

        # Gráfico de Distribuição de Paradas
        fig_paradas = px.pie(
            df_paradas, 
            names="Categoria", 
            values="Horas", 
            title="Distribuição do Tempo Parado (Horas)",
            hole=0.4
        )
        st.plotly_chart(fig_paradas, use_container_width=True)

# ==========================================
# ABA 4: PERFIL LITOLÓGICO GRÁFICO (STRIPLOG)
# ==========================================
with aba_perfil:
    st.subheader("Perfil Geológico Vertical e Qualidade do Testemunho")

    if len(st.session_state["manobras"]) > 0:
        df_striplog = pd.DataFrame(st.session_state["manobras"])

        # Gráfico Vertical (Invertido Y para simular profundidade)
        fig_striplog = px.bar(
            df_striplog,
            x="Avanço (m)",
            y="De (m)",
            color="Litologia",
            orientation='h',
            hover_data=["Até (m)", "Recup. (%)", "RQD (%)", "Fluido"],
            title=f"Coluna Estratigráfica - Furo: {furo_id}",
            labels={"De (m)": "Profundidade Inicial (m)", "Avanço (m)": "Espessura da Camada (m)"},
            color_discrete_sequence=px.colors.qualitative.Bold
        )

        # Inverter o eixo Y para indicar profundidade
        fig_striplog.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_striplog, use_container_width=True)

        # Gráfico comparativo de RQD vs Recuperação por profundidade
        fig_rqd = px.line(
            df_striplog,
            x="De (m)",
            y=["Recup. (%)", "RQD (%)"],
            markers=True,
            title="Variação de Recuperação e RQD ao longo da Profundidade",
            labels={"value": "Porcentagem (%)", "De (m)": "Profundidade (m)"}
        )
        st.plotly_chart(fig_rqd, use_container_width=True)
    else:
        st.info("Registre pelo menos uma manobra na aba 'Registro de Manobra' para gerar o perfil gráfico.")
