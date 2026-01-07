import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÕES VISUAIS ---
st.set_page_config(page_title="Gestão Fisio", page_icon="🩺", layout="centered")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Nome da Planilha
NOME_PLANILHA_GOOGLE = "Sistema Fisio DB"

# --- CONEXÃO GOOGLE SHEETS ---
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error("Erro de conexão com o Google. Verifique os Secrets.")
        return None

def carregar_dados():
    try:
        client = conectar_google_sheets()
        if client:
            sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            return df
        return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
    except:
        return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])

def salvar_dados(df):
    try:
        client = conectar_google_sheets()
        if client:
            sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- NOVA LÓGICA DE LOGIN ---
def verificar_login():
    if 'logado' not in st.session_state:
        st.session_state.logado = False
        st.session_state.usuario_atual = ""

    if not st.session_state.logado:
        st.markdown("<h1 style='text-align: center;'>🔐 Acesso Restrito</h1>", unsafe_allow_html=True)
        st.write("---")
        
        # Campos de Usuário e Senha
        usuario = st.text_input("Usuário:")
        senha = st.text_input("Senha:", type="password")
        
        if st.button("Entrar", use_container_width=True):
            # Tenta pegar a lista de usuários dos Segredos
            try:
                usuarios_cadastrados = st.secrets["passwords"]
                
                # Verifica se usuário existe e a senha bate
                if usuario in usuarios_cadastrados and usuarios_cadastrados[usuario] == senha:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = usuario
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
            except FileNotFoundError:
                st.error("Erro: Nenhum usuário configurado nos Secrets.")
        return False
    return True

# --- SISTEMA PRINCIPAL ---
if not verificar_login():
    st.stop()

# Carrega dados
if 'df' not in st.session_state:
    with st.spinner('Sincronizando...'):
        st.session_state.df = carregar_dados()

# Barra Lateral
with st.sidebar:
    st.info(f"👤 Logado como: **{st.session_state.usuario_atual}**")
    st.header("⚙️ Configurações")
    comissao_padrao = st.number_input("Comissão (%)", 0, 100, 75)
    
    st.divider()
    if st.button("Sair (Logout)", use_container_width=True):
        st.session_state.logado = False
        st.session_state.usuario_atual = ""
        st.rerun()

st.markdown("<h2 style='text-align: center;'>🩺 Controle Financeiro</h2>", unsafe_allow_html=True)

abas = st.tabs(["Semana 1", "Semana 2", "Semana 3", "Semana 4", "📊 Resumo"])
nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]

for i, semana_nome in enumerate(nomes_semanas):
    with abas[i]:
        st.subheader(f"📝 {semana_nome}")
        with st.container(border=True):
            col1, col2 = st.columns([2, 1])
            paciente = col1.text_input(f"Nome", key=f"n_{i}")
            valor = col2.number_input(f"Valor R$", min_value=0.0, step=10.0, key=f"v_{i}")
            
            if st.button(f"Salvar", key=f"b_{i}", use_container_width=True):
                if paciente and valor > 0:
                    with st.spinner('Salvando...'):
                        liquido = valor * (comissao_padrao / 100)
                        # Adicionamos quem fez o lançamento (opcional, mas bom pra controle)
                        novo = {
                            "Semana": semana_nome, 
                            "Paciente": paciente, 
                            "Valor Bruto": valor, 
                            "Comissão (%)": comissao_padrao, 
                            "Valor Líquido": liquido
                        }
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                        salvar_dados(st.session_state.df)
                        st.success("✅ Salvo!")
                        st.rerun()

        df_sem = st.session_state.df[st.session_state.df["Semana"] == semana_nome]
        if not df_sem.empty:
            st.dataframe(df_sem[["Paciente", "Valor Bruto", "Valor Líquido"]], hide_index=True, use_container_width=True)
            st.info(f"Total Semana: R$ {df_sem['Valor Líquido'].sum():,.2f}")
            
            if st.button("🗑️ Desfazer", key=f"d_{i}"):
                indices = df_sem.index
                if len(indices) > 0:
                    st.session_state.df = st.session_state.df.drop(indices[-1])
                    salvar_dados(st.session_state.df)
                    st.rerun()

with abas[4]:
    st.header("📊 Fechamento")
    if not st.session_state.df.empty:
        resumo = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.dataframe(resumo.style.format({"Valor Líquido": "R$ {:,.2f}"}), hide_index=True, use_container_width=True)
        st.metric("TOTAL MÊS", f"R$ {st.session_state.df['Valor Líquido'].sum():,.2f}")
        
        st.divider()
        if st.button("🔴 APAGAR MÊS", type="primary", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df)
            st.rerun()
