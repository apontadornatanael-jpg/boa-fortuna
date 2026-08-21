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

def pil_para_bytes(img_pil):
    if img_pil is None:
        return None
    buffer = io.BytesIO()
    img_pil.save(buffer, format="JPEG")
    return buffer.getvalue()

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
            prof_atingida, empresa, empresa, obra, obra, cidade, cidade,
            sondador, sondador, coordenador, coordenador, supervisor, supervisor,
            auxiliares, auxiliares, data_atual, furo_id
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

# --- GERADOR DE RELATÓRIO HTML ---
def gerar_html_boletim(furo_id, obs_fechamento=""):
    empresa = st.session_state.get("empresa", "Boa Fortuna Perfurações e Sondagens")
    obra = st.session_state.get("obra", "-")
    cidade = st.session_state.get("cidade", "-")
    sondador = st.session_state.get("sondador", "-")
    coordenador = st.session_state.get("coordenador", "-")
    data_campo = str(st.session_state.get("data_campo", date.today()))
    
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
            <td>{rec_pct:.1f}%</td>
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
            body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
            h2 {{ color: #1E3A8A; margin-bottom: 2px; text-align: center; }}
            h4 {{ color: #555; margin-top: 0; text-align: center; }}
            .box-info {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; background: #f9f9f9; }}
            .box-info td {{ padding: 8px; border: 1px solid #ccc; font-size: 13px; }}
            .tabela-dados {{ width: 100%; border-collapse: collapse; margin-top: 10px; text-align: center; }}
            .tabela-dados th {{ background: #1E3A8A; color: white; padding: 8px; font-size: 12px; }}
            .tabela-dados td {{ padding: 6px; border: 1px solid #ddd; font-size: 12px; }}
            .obs {{ margin-top: 20px; padding: 10px; border: 1px solid #ccc; background: #fff8e1; font-size: 12px; }}
        </style>
    </head>
    <body>
        <h2>{empresa.upper()}</h2>
        <h4>BOLETIM DIÁRIO DE SONDAGEM (BDS) - FURO: {furo_id}</h4>
        
        <table class="box-info">
            <tr>
                <td><b>Cliente/Obra:</b> {obra}</td>
                <td><b>Cidade/UF:</b> {cidade}</td>
                <td><b>Data:</b> {data_campo}</td>
            </tr>
            <tr>
                <td><b>Sondador:</b> {sondador}</td>
                <td><b>Coordenador:</b> {coordenador}</td>
                <td><b>Identificação Furo:</b> {furo_id}</td>
            </tr>
        </table>

        <h3>Avanço e Recuperação de Testemunhos</h3>
        <table class="tabela-dados">
            <thead>
                <tr>
                    <th>De (m)</th>
                    <th>Até (m)</th>
                    <th>Avanço (m)</th>
                    <th>Recup (m)</th>
                    <th>Recup (%)</th>
                    <th>Caixa</th>
                    <th>Descrição Litológica</th>
                </tr>
            </thead>
            <tbody>
                {linhas_tabela}
            </tbody>
        </table>

        <div class="obs">
            <b>Observações de Fechamento:</b><br>{obs_fechamento or 'Nenhuma observação informada.'}
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
            "4. Fechamento de Turno & Relatório",
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

      if manobras_furo:
            dados_tabela = []
            for row in manobras_furo:
                m_id = row[0]
                de = row[1] if row[1] is not None else 0.0
                ate = row[2] if row[2] is not None else 0.0
                rec = row[3] if row[3] is not None else 0.0
                rec_pct = row[4] if row[4] is not None else 0.0
                caixa = row[5]
                h_tr = row[6] if row[6] is not None else 0.0
                h_par = row[7] if row[7] is not None else 0.0
                desc = row[8]
                
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

    # ETAPA 4 - FECHAMENTO & RELATÓRIO
    elif opcao == "4. Fechamento de Turno & Relatório":
        st.title("4. Fechamento de Turno e Relatório de Campo")
        st.caption("Consolidação dos dados do dia, métricas de avanço e emissão do boletim.")

        furo_fechamento = st.text_input("Identificação do Furo", value=st.session_state.get("furo_id", "SP-01"))
        manobras = buscar_manobras(furo_fechamento)

        if manobras:
            total_avanco = sum([m[2] - m[1] for m in manobras])
            total_recup = sum([m[3] for m in manobras])
            total_h_trab = sum([m[6] for m in manobras if m[6] is not None])
            total_h_parado = sum([m[7] for m in manobras if m[7] is not None])
            taxa_media = (total_recup / total_avanco * 100) if total_avanco > 0 else 0.0

            st.subheader("📊 Resumo do Turno")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Avanço Total", f"{total_avanco:.2f} m")
            col_m2.metric("Recuperação Média", f"{taxa_media:.1f}%")
            col_m3.metric("Horas Trabalhadas", f"{total_h_trab:.1f} h")
            col_m4.metric("Horas Paradas", f"{total_h_parado:.1f} h")

            st.divider()
            
            obs_fechamento = st.text_area("Observações Finais do Turno / Ocorrências de Campo", placeholder="Ex: Paralisação por chuva das 14h às 15h. Troca de coroa realizada.")

            html_conteudo = gerar_html_boletim(furo_fechamento, obs_fechamento)

            st.download_button(
                label="🌐 Baixar Boletim de Sondagem (HTML / Para Impressão PDF)",
                data=html_conteudo,
                file_name=f"Boletim_{furo_fechamento}_{date.today().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )
        else:
            st.warning(f"Nenhuma manobra encontrada para o furo {furo_fechamento}. Registre manobras na Etapa 3 antes de fechar o turno.")

    # ETAPA 5
    elif opcao == "5. Dados do Furo & Perfuração":
        st.title("5. Dados do Furo e Perfuração")
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
