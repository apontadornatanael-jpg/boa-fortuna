import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
from PIL import Image
import io

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
            furo_id TEXT UNIQUE,
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
            data_registro TEXT,
            foto1 BLOB,
            foto2 BLOB,
            foto3 BLOB
        )
    ''')
    
    # Migração para garantir suporte às fotos
    c.execute("PRAGMA table_info(manobras_testemunho)")
    colunas = [col[1] for col in c.fetchall()]
    for col_foto in ["foto1", "foto2", "foto3"]:
        if col_foto not in colunas:
            c.execute(f"ALTER TABLE manobras_testemunho ADD COLUMN {col_foto} BLOB")
            
    conn.commit()
    conn.close()

init_db()

def pil_para_bytes(img_pil):
    """Converte imagem PIL para bytes BLOB."""
    if img_pil is None:
        return None
    buffer = io.BytesIO()
    img_pil.save(buffer, format="JPEG")
    return buffer.getvalue()

def sincronizar_boletim_automatico(furo_id, prof_atingida):
    """Atualiza/Cria o boletim com as informações da sessão automaticamente."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Resgata os dados gravados nas Etapas 1 e 2 via Session State
    empresa = st.session_state.get("empresa", "Boa Fortuna Perfurações")
    obra = st.session_state.get("obra", "Não informada")
    cidade = st.session_state.get("cidade", "-")
    coordenador = st.session_state.get("coordenador", "-")
    supervisor = st.session_state.get("supervisor", "-")
    sondador = st.session_state.get("sondador", "-")
    auxiliares = st.session_state.get("auxiliares", "-")
    tipo_sondagem = st.session_state.get("tipo_sondagem", "Rotativa")
    
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
                data_registro = ?
            WHERE furo_id = ?
        ''', (
            prof_atingida,
            empresa, empresa,
            obra, obra,
            cidade, cidade,
            sondador, sondador,
            coordenador, coordenador,
            supervisor, supervisor,
            auxiliares, auxiliares,
            data_atual, furo_id
        ))
    else:
        c.execute('''
            INSERT INTO boletins_campo 
            (data_registro, empresa, obra_cliente, cidade_uf, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, profundidade_m, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data_atual, empresa, obra, cidade, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, prof_atingida, "Sincronizado via manobras"))
    
    conn.commit()
    conn.close()

def salvar_boletim(empresa, obra, cidade, coord, superv, sond, aux, furo, tipo, prof, obs):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute('''
        INSERT INTO boletins_campo 
        (data_registro, empresa, obra_cliente, cidade_uf, coordenador, supervisor, sondador, auxiliares, furo_id, tipo_sondagem, profundidade_m, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(furo_id) DO UPDATE SET
            empresa=excluded.empresa, obra_cliente=excluded.obra_cliente, cidade_uf=excluded.cidade_uf,
            coordenador=excluded.coordenador, supervisor=excluded.supervisor, sondador=excluded.sondador,
            auxiliares=excluded.auxiliares, tipo_sondagem=excluded.tipo_sondagem, profundidade_m=excluded.profundidade_m,
            observacao=excluded.observacao, data_registro=excluded.data_registro
    ''', (data_atual, empresa, obra, cidade, coord, superv, sond, aux, furo, tipo, prof, obs))
    conn.commit()
    conn.close()

def salvar_manobra(furo, de, ate, recup, taxa, caixa, h_trab, h_parado, horario, motivo, desc, fotos_pil=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    f1 = pil_para_bytes(fotos_pil[0]) if fotos_pil and len(fotos_pil) > 0 else None
    f2 = pil_para_bytes(fotos_pil[1]) if fotos_pil and len(fotos_pil) > 1 else None
    f3 = pil_para_bytes(fotos_pil[2]) if fotos_pil and len(fotos_pil) > 2 else None

    c.execute('''
        INSERT INTO manobras_testemunho
        (furo_id, de_m, ate_m, recup_m, taxa_recup_pct, num_caixa, horas_trab, horas_parado, horario, motivo_parada, descricao_litologica, data_registro, foto1, foto2, foto3)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (furo, de, ate, recup, taxa, caixa, h_trab, h_parado, horario, motivo, desc, data_atual, f1, f2, f3))
    conn.commit()
    conn.close()
    
    # Dispara a sincronização automática com a tabela master do boletim
    sincronizar_boletim_automatico(furo, ate)

def deletar_manobra(manobra_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM manobras_testemunho WHERE id = ?', (manobra_id,))
    conn.commit()
    conn.close()

def buscar_registros():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, furo_id, obra_cliente, cidade_uf, sondador, profundidade_m, tipo_sondagem, empresa, coordenador, supervisor, auxiliares, observacao, data_registro FROM boletins_campo ORDER BY id DESC')
    dados = c.fetchall()
    conn.close()
    return dados

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

    # ETAPA 3
    elif opcao == "3. Registro de Manobra e Testemunho":
        st.title("3. Registro de Manobra e Testemunho")
        st.caption("Lançamento do avanço, recuperação da amostra, caixas e registro fotográfico.")
        
        furo_atual = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", "SP-01"), key="input_furo_manobra")
        st.session_state["furo_id"] = furo_atual

        manobras_existentes = buscar_manobras(furo_atual)
        prox_de = manobras_existentes[-1][2] if manobras_existentes else 0.0
        prox_ate = round(prox_de + 1.5, 2)
        
        st.markdown(f"#### 📐 Profundidade Atual Perfurada: **{prox_de:.2f} m**")

        with st.form("form_manobra"):
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                de_m = st.number_input("De (m)", min_value=0.0, step=0.5, value=float(prox_de), format="%.2f")
            with col2:
                ate_m = st.number_input("Até (m)", min_value=0.0, step=0.5, value=float(prox_ate), format="%.2f")
            with col3:
                recup_m = st.number_input("Recup. (m)", min_value=0.0, step=0.1, value=round(max(0.0, ate_m - de_m), 2), format="%.2f")
            with col4:
                num_caixa = st.text_input("Nº da Caixa", value=manobras_existentes[-1][5] if manobras_existentes else "01")
            with col5:
                horas_trab = st.number_input("Horas Trab. (h)", min_value=0.0, step=0.5, value=1.0, format="%.1f")
            with col6:
                horas_parado = st.number_input("Horas Parado (h)", min_value=0.0, step=0.5, value=0.0, format="%.1f")

            avancamento = round(ate_m - de_m, 2)
            taxa_recup = min(100.0, round((recup_m / avancamento * 100), 1)) if avancamento > 0 else 0.0
            
            st.info(f"**Avanço Calculado nesta Manobra:** {avancamento:.2f} m | **Taxa de Recuperação:** {taxa_recup:.1f}%")

            col7, col8, col9 = st.columns([1, 1, 2])
            with col7:
                horario = st.text_input("Horário", placeholder="Ex: 08:00 - 09:30")
            with col8:
                motivo_parada = st.text_input("Motivo Parada", value="Nenhuma")
            with col9:
                desc_litologica = st.text_input("Descrição Litológica / Observações", placeholder="Ex: Solo residual, rocha alterada...")

            st.markdown("---")
            st.subheader("Registro Fotográfico da Manobra (Até 3 fotos)")
            
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
                    salvar_manobra(furo_atual, de_m, ate_m, recup_m, taxa_recup, num_caixa, horas_trab, horas_parado, horario, motivo_parada, desc_litologica, fotos_manobra_pil)
                    st.success(f"Manobra de {de_m:.2f}m a {ate_m:.2f}m salva e sincronizada automaticamente!")
                    st.rerun()
                else:
                    st.error("O valor final 'Até (m)' deve ser maior que o valor inicial 'De (m)'.")

        st.divider()
        st.subheader(f"Manobras Salvas para o Furo: {furo_atual}")
        manobras_furo = buscar_manobras(furo_atual)
        
        if manobras_furo:
            dados_tabela = []
            for row in manobras_furo:
                m_id, de, ate, rec, rec_pct, caixa, h_tr, h_par, desc = row[:9]
                avanc = round(ate - de, 2)
                dados_tabela.append([m_id, de, ate, avanc, rec, rec_pct, caixa, h_tr, h_par, desc])

            df_manobras = pd.DataFrame(
                dados_tabela, 
                columns=["ID", "De (m)", "Até (m)", "Avanço (m)", "Recup (m)", "Recup (%)", "Caixa", "H. Trab", "H. Parado", "Descrição Litológica"]
            )
            st.dataframe(df_manobras, use_container_width=True)

            col_excluir, col_btn = st.columns([3, 1])
            with col_excluir:
                opcoes_manobra = {f"ID #{row[0]} | De {row[1]:.2f}m até {row[2]:.2f}m (Avanço: {row[2]-row[1]:.2f}m)": row[0] for row in manobras_furo}
                manobra_selecionada = st.selectbox("Selecione a manobra que deseja apagar:", list(opcoes_manobra.keys()))
            
            with col_btn:
                st.write("")
                st.write("")
                if st.button("Excluir Manobra", use_container_width=True):
                    id_para_deletar = opcoes_manobra[manobra_selecionada]
                    deletar_manobra(id_para_deletar)
                    st.success("Manobra removida!")
                    st.rerun()
        else:
            st.info("Nenhuma manobra cadastrada para este furo.")

    # ETAPA 4
    elif opcao == "4. Dados do Furo & Perfuração":
        st.title("4. Dados do Furo e Perfuração")
        st.caption("Ajuste manual e dados complementares da perfuração.")
        
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

            obs = st.text_area("Observações Gerais / Nível d'Água (NA)", placeholder="Registros de NA, paralisações ou anomalias do terreno...")

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
                        furo, tipo_sondagem, profundidade, obs
                    )
                    st.success(f"Boletim {furo} atualizado.")
                else:
                    st.warning("Informe o ID do furo.")

    # ETAPA 5
    elif opcao == "5. Histórico de Boletins":
        st.title("5. Painel Integrado de Boletins e Perfurações")
        st.caption("Conexão direta entre cadastros do boletim, avanço físico e galeria de fotos de testemunho.")

        registros = buscar_registros()

        if registros:
            cols_boletim = ["ID", "Furo", "Obra", "Cidade/UF", "Sondador", "Prof. Final (m)", "Tipo", "Empresa", "Coordenador", "Supervisor", "Auxiliares", "Observações", "Data/Hora"]
            df_boletins = pd.DataFrame(registros, columns=cols_boletim)

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total de Furos Registrados", len(df_boletins))
            col_m2.metric("Metragem Total Perfurada", f"{df_boletins['Prof. Final (m)'].sum():.2f} m")
            col_m3.metric("Média de Profundidade", f"{df_boletins['Prof. Final (m)'].mean():.2f} m")

            st.divider()

            st.subheader("Boletins Salvos e Sincronizados")
            st.dataframe(
                df_boletins[["Furo", "Obra", "Cidade/UF", "Sondador", "Tipo", "Prof. Final (m)", "Data/Hora"]],
                use_container_width=True
            )

            st.divider()

            st.subheader("🔗 Visão Integrada do Furo")
            furo_selecionado = st.selectbox("Selecione um furo para carregar o histórico completo de manobras e fotos:", df_boletins['Furo'].unique())

            if furo_selecionado:
                info_furo = df_boletins[df_boletins['Furo'] == furo_selecionado].iloc[0]
                manobras_furo = buscar_manobras(furo_selecionado)

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Empresa:** {info_furo['Empresa']}")
                    st.write(f"**Cliente/Obra:** {info_furo['Obra']}")
                    st.write(f"**Cidade/UF:** {info_furo['Cidade/UF']}")
                with c2:
                    st.write(f"**Sondador:** {info_furo['Sondador']}")
                    st.write(f"**Coordenador:** {info_furo['Coordenador']}")
                    st.write(f"**Supervisor:** {info_furo['Supervisor']}")
                with c3:
                    st.write(f"**Tipo de Sondagem:** {info_furo['Tipo']}")
                    st.write(f"**Profundidade do Furo:** {info_furo['Prof. Final (m)']} m")
                    st.write(f"**Total de Manobras:** {len(manobras_furo)}")

                if info_furo['Observações']:
                    st.info(f"**Observações de Campo:** {info_furo['Observações']}")

                if manobras_furo:
                    dados_m = []
                    total_recup = 0
                    total_avanc = 0

                    for row in manobras_furo:
                        m_id, de, ate, rec, rec_pct, caixa, h_tr, h_par, desc = row[:9]
                        avanc = round(ate - de, 2)
                        total_recup += rec
                        total_avanc += avanc
                        dados_m.append([m_id, f"{de:.2f}", f"{ate:.2f}", f"{avanc:.2f}", f"{rec:.2f}", f"{rec_pct:.1f}%", caixa, h_tr, h_par, desc])

                    df_m_furo = pd.DataFrame(
                        dados_m, 
                        columns=["ID", "De (m)", "Até (m)", "Avanço (m)", "Recup (m)", "Recup (%)", "Caixa", "H. Trab", "H. Parado", "Descrição Litológica"]
                    )
                    
                    st.markdown(f"##### Tabela de Manobras e Testemunhos ({furo_selecionado})")
                    st.dataframe(df_m_furo, use_container_width=True)

                    taxa_media_rec = (total_recup / total_avanc * 100) if total_avanc > 0 else 0
                    st.success(f"**Resumo do Furo {furo_selecionado}:** Avanço Total de **{total_avanc:.2f} m** | Amostra Recuperada: **{total_recup:.2f} m** ({taxa_media_rec:.1f}% de taxa média)")
                    
                    csv_furo = df_m_furo.to_csv(index=False).encode('utf-8')
                    st.download_button(f"📥 Exportar Manobras do Furo {furo_selecionado} (CSV)", data=csv_furo, file_name=f"manobras_{furo_selecionado}.csv", mime="text/csv")
                    
                    st.divider()

                    st.subheader("📷 Galeria Fotográfica das Manobras")
                    tem_foto = False

                    for row in manobras_furo:
                        m_id, de, ate = row[0], row[1], row[2]
                        fotos_blobs = [row[9], row[10], row[11]]
                        fotos_blobs = [f for f in fotos_blobs if f is not None]

                        if fotos_blobs:
                            tem_foto = True
                            st.markdown(f"**Manobra ID #{m_id}** — De **{de:.2f}m** até **{ate:.2f}m**")
                            cols_foto = st.columns(len(fotos_blobs))
                            for idx, f_blob in enumerate(fotos_blobs):
                                img = Image.open(io.BytesIO(f_blob))
                                cols_foto[idx].image(img, caption=f"Foto {idx+1} (Manobra {de:.2f}m-{ate:.2f}m)", use_container_width=True)

                    if not tem_foto:
                        st.info("Nenhuma foto cadastrada para as manobras deste furo.")

                else:
                    st.warning("Este furo não possui manobras detalhadas cadastradas.")
        else:
            st.info("Nenhum boletim registrado no banco de dados.")
