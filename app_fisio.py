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

nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
abas = st.tabs(nomes_semanas + ["📊 Resumo Mensal"])

for i, semana_nome in enumerate(nomes_semanas):
    with abas[i]:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            data_atend = c1.date_input("Data", key=f"d_{i}")
            
            # Sugestão Inteligente (Autocomplete)
            paciente = c2.selectbox("Paciente (Sugestões)", [""] + lista_pacientes + ["-- NOVO --"], key=f"sel_{i}")
            if paciente == "-- NOVO --" or paciente == "":
                paciente = c2.text_input("Nome do Paciente", key=f"input_{i}")
            
            valor = c3.number_input("Valor R$", min_value=0.0, step=10.0, key=f"v_{i}")
            
            if st.button(f"Salvar na {semana_nome}", key=f"b_{i}", use_container_width=True):
                if paciente and valor > 0:
                    liquido = valor * (comissao_usuario / 100)
                    novo = {"Data": str(data_atend), "Semana": semana_nome, "Paciente": paciente, "Valor Bruto": valor, "Comissão (%)": comissao_usuario, "Valor Líquido": liquido}
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                    salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                    st.rerun()

        df_sem = st.session_state.df[st.session_state.df["Semana"] == semana_nome]
        if not df_sem.empty:
            st.dataframe(df_sem[["Data", "Paciente", "Valor Bruto", "Valor Líquido"]], hide_index=True, use_container_width=True)
            if st.button("Desfazer Último", key=f"del_{i}"):
                st.session_state.df = st.session_state.df.drop(df_sem.index[-1])
                salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                st.rerun()

# --- RESUMO MENSAL ---
with abas[4]:
    if not st.session_state.df.empty:
        st.subheader("📊 Consolidado")
        resumo = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.table(resumo.set_index("Semana"))
        
        total_mês = st.session_state.df["Valor Líquido"].sum()
        st.metric("TOTAL LÍQUIDO NO MÊS", f"R$ {total_mês:,.2f}")

        st.divider()
        col_res1, col_res2 = st.columns(2)
        
        if col_res1.button("📦 FECHAR E ARQUIVAR MÊS", use_container_width=True, type="secondary"):
            if arquivar_mes_google(st.session_state.df, st.session_state.usuario_atual):
                st.session_state.df = pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
                salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                st.success("Mês arquivado em uma nova aba e painel limpo!")
                time.sleep(2)
                st.rerun()
        
        if col_res2.button("🔴 APAGAR TUDO (SEM SALVAR)", use_container_width=True, type="primary"):
            st.session_state.df = pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df, st.session_state.usuario_atual)
            st.rerun()
