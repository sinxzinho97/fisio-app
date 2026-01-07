import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Gestão Fisio", page_icon="🩺", layout="centered")

# Nome da planilha que você criou no Google Sheets
NOME_PLANILHA_GOOGLE = "Sistema Fisio DB"

# Senha do Site
SENHA_ACESSO = "fisio123"

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_google_sheets():
    # Pega as credenciais dos "Segredos" do Streamlit (vamos configurar isso no site)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def carregar_dados():
    try:
        client = conectar_google_sheets()
        sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Se a planilha estiver vazia, cria a estrutura
        if df.empty:
            return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
        return df
    except Exception as e:
        # Se der erro (ex: planilha nova), retorna vazio
        return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])

def salvar_dados(df):
    client = conectar_google_sheets()
    sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
    # Limpa e reescreve tudo (para garantir sincronia)
    sheet.clear()
    # Adiciona cabeçalhos e dados
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- LOGIN ---
def verificar_login():
    if 'logado' not in st.session_state:
        st.session_state.logado = False

    if not st.session_state.logado:
        st.header("🔒 Área Restrita")
        senha = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar"):
            if senha == SENHA_ACESSO:
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
        return False
    return True

# --- APP PRINCIPAL ---
if not verificar_login():
    st.stop()

# Carrega dados
if 'df' not in st.session_state:
    with st.spinner('Carregando dados da nuvem...'):
        st.session_state.df = carregar_dados()

# Barra Lateral
with st.sidebar:
    st.header("⚙️ Ajustes")
    comissao_padrao = st.number_input("Sua Comissão (%)", 0, 100, 75)
    st.divider()
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()

st.title("🩺 Controle Online")
abas = st.tabs(["Semana 1", "Semana 2", "Semana 3", "Semana 4", "📊 Resumo Mensal"])
nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]

# Loop das Semanas
for i, semana_nome in enumerate(nomes_semanas):
    with abas[i]:
        st.subheader(f"Lançamentos da {semana_nome}")
        with st.container(border=True):
            col1, col2 = st.columns([2, 1])
            paciente = col1.text_input(f"Nome", key=f"n_{i}")
            valor = col2.number_input(f"Valor R$", min_value=0.0, step=10.0, key=f"v_{i}")
            
            if st.button(f"Salvar", key=f"b_{i}", use_container_width=True):
                if paciente and valor > 0:
                    liquido = valor * (comissao_padrao / 100)
                    novo = {"Semana": semana_nome, "Paciente": paciente, "Valor Bruto": valor, "Comissão (%)": comissao_padrao, "Valor Líquido": liquido}
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                    salvar_dados(st.session_state.df)
                    st.success("Salvo na nuvem!")
                    st.rerun()

        df_sem = st.session_state.df[st.session_state.df["Semana"] == semana_nome]
        if not df_sem.empty:
            st.dataframe(df_sem[["Paciente", "Valor Bruto", "Valor Líquido"]], hide_index=True, use_container_width=True)
            st.info(f"Total Semana: R$ {df_sem['Valor Líquido'].sum():,.2f}")
            
            if st.button("Desfazer último", key=f"d_{i}"):
                indices = df_sem.index
                if len(indices) > 0:
                    st.session_state.df = st.session_state.df.drop(indices[-1])
                    salvar_dados(st.session_state.df)
                    st.rerun()

# Resumo
with abas[4]:
    st.header("📊 Fechamento")
    if not st.session_state.df.empty:
        resumo = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.dataframe(resumo.style.format({"Valor Líquido": "R$ {:,.2f}"}), hide_index=True, use_container_width=True)
        st.metric("TOTAL MÊS", f"R$ {st.session_state.df['Valor Líquido'].sum():,.2f}")
        
        st.divider()
        if st.button("🔴 RESETAR MÊS (Apaga Planilha)", type="primary"):
            st.session_state.df = pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df)
            st.rerun()