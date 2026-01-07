import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime

# --- CONFIGURAÇÕES VISUAIS ---
st.set_page_config(page_title="Gestão Fisio PRO", page_icon="🩺", layout="centered")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- CONEXÃO GOOGLE SHEETS ---
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erro de conexão com o Google: {e}")
        return None

def obter_nome_planilha(usuario):
    try:
        return st.secrets["spreadsheets"][usuario]
    except:
        return None

def carregar_dados(usuario):
    nome_planilha = obter_nome_planilha(usuario)
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(nome_planilha).sheet1
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            
            cols_num = ["Valor Bruto", "Comissão (%)", "Valor Líquido"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except:
            return pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
    return None

def salvar_dados(df, usuario):
    nome_planilha = obter_nome_planilha(usuario)
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(nome_planilha).sheet1
            sheet.clear() 
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False
    return False

def arquivar_mes_google(df, usuario):
    nome_planilha = obter_nome_planilha(usuario)
    client = conectar_google_sheets()
    if client:
        try:
            spreadsheet = client.open(nome_planilha)
            nome_aba = datetime.now().strftime("%m_%Y_Historico")
            
            # Cria uma nova aba de histórico
            nova_aba = spreadsheet.add_worksheet(title=nome_aba, rows="100", cols="20")
            nova_aba.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Erro ao arquivar: {e}")
            return False

# --- TELA DE LOGIN ---
def verificar_login():
    if 'logado' not in st.session_state:
        st.session_state.logado = False
        st.session_state.usuario_atual = ""

    if not st.session_state.logado:
        st.markdown("<h1 style='text-align: center;'>🔐 Login Fisio</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            usuario = st.text_input("Usuário:")
            senha = st.text_input("Senha:", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                senhas = st.secrets["passwords"]
                if usuario in senhas and senhas[usuario] == senha:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = usuario
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return False
    return True

if not verificar_login():
    st.stop()

if 'df' not in st.session_state:
    st.session_state.df = carregar_dados(st.session_state.usuario_atual)

# --- LOGICA DE AUTOCOMPLETE ---
lista_pacientes = sorted(st.session_state.df["Paciente"].unique().tolist()) if not st.session_state.df.empty else []

# --- BARRA LATERAL ---
with st.sidebar:
    st.info(f"👤 **{st.session_state.usuario_atual}**")
    comissao_usuario = st.number_input("Comissão (%)", 0, 100, 75)
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()

st.markdown("<h2 style='text-align: center;'>🩺 Gestão de Atendimentos</h2>", unsafe_allow_html=True)

nomes_semanas = ["Semana 1", "Semana 2", "Sem
