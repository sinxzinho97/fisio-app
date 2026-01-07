import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime

# --- CONFIGURAÇÕES VISUAIS ---
st.set_page_config(page_title="Gestão Fisio PRO", page_icon="🩺", layout="centered")

# CSS para customizar o botão de confirmação para Verde
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #28a745;
        color: white;
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #218838;
        color: white;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def obter_nome_planilha(usuario):
    try: return st.secrets["spreadsheets"][usuario]
    except: return None

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
            nova_aba = spreadsheet.add_worksheet(title=nome_aba, rows="100", cols="20")
            nova_aba.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Erro ao arquivar: {e}")
            return False

# --- LOGIN ---
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

# --- CONFIGURAÇÃO DE COMISSÃO ---
usuario_logado = st.session_state.usuario_atual.lower()
comissao_fixa = 75 if usuario_logado == "brenda" else 50
lista_pacientes = sorted(st.session_state.df["Paciente"].unique().tolist()) if not st.session_state.df.empty else []

# --- BARRA LATERAL ---
with st.sidebar:
    st.info(f"👤 **{st.session_state.usuario_atual}**")
    st.number_input("Sua Comissão (%)", value=comissao_fixa, disabled=True)
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()

st.markdown("<h2 style='text-align: center;'>🩺 Gestão de Atendimentos</h2>", unsafe_allow_html=True)

nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
abas = st.tabs(nomes_semanas + ["📊 Resumo Mensal"])

for i, semana_nome in enumerate(nomes_semanas):
    with abas[i]:
        with st.container(border=True):
            # 1. NOME E VALOR (PRIORIDADE)
            c_nome, c_valor = st.columns([2, 1])
            nome_digitado = c_nome.text_input("Nome do Paciente", key=f"input_{i}", placeholder="Digite o nome...")
            valor = c_valor.number_input("Valor R$", min_value=0.0, step=5.0, key=f"v_{i}")
            
            # 2. SUGESTÃO E DATA (AUXILIARES)
            c_sug, c_data = st.columns([2, 1])
            paciente_sugerido = c_sug.selectbox("Sugestões (Opcional)", [""] + lista_pacientes, key=f"sel_{i}")
            data_atend = c_data.date_input("Data", value=datetime.now(), key=f"d_{i}")
            
            nome_final = paciente_sugerido if paciente_sugerido != "" else nome_digitado

            if st.button("Confirmar Atendimento", key=f"btn_{i}", use_container_width=True):
                if nome_final and valor > 0:
                    liquido = valor * (comissao_fixa / 100)
                    novo = {"Data": str(data_atend), "Semana": semana_nome, "Paciente": nome_final, "Valor Bruto": valor, "Comissão (%)": comissao_fixa, "Valor Líquido": liquido}
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                    salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                    st.success(f"Atendimento de {nome_final} confirmado!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Preencha o nome e o valor.")

        df_sem = st.session_state.df[st.session_state.df["Semana"] == semana_nome]
        if not df_sem.empty:
            df_display = df_sem[["Data", "Paciente", "Valor Bruto", "Valor Líquido"]].copy()
            st.dataframe(df_display.style.format({"Valor Bruto": "R$ {:,.2f}", "Valor Líquido": "R$ {:,.2f}"}), hide_index=True, use_container_width=True)
            st.info(f"💰 **Total na semana:** {formatar_moeda(df_sem['Valor Líquido'].sum())}")
            if st.button("Desfazer Último", key=f"del_{i}"):
                st.session_state.df = st.session_state.df.drop(df_sem.index[-1])
                salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                st.rerun()

# --- RESUMO MENSAL ---
with abas[4]:
    if not st.session_state.df.empty:
        st.subheader("📊 Consolidado Mensal")
        resumo = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.dataframe(resumo.style.format({"Valor Líquido": lambda x: formatar_moeda(x)}), hide_index=True, use_container_width=True)
        st.metric("TOTAL LÍQUIDO A RECEBER", formatar_moeda(st.session_state.df["Valor Líquido"].sum()))
        st.divider()
        c1, c2 = st.columns(2)
        if c1.button("📦 ARQUIVAR MÊS", use_container_width=True):
            if arquivar_mes_google(st.session_state.df, st.session_state.usuario_atual):
                st.session_state.df = pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
                salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                st.rerun()
        if c2.button("🔴 APAGAR MÊS", use_container_width=True, type="primary"):
            st.session_state.df = pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df, st.session_state.usuario_atual)
            st.rerun()
