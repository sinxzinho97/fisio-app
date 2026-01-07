import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

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

# --- CONEXÃO GOOGLE SHEETS (USANDO ID) ---
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

def obter_id_planilha(usuario):
    # Busca o ID configurado nos secrets
    try:
        return st.secrets["spreadsheets"][usuario]
    except:
        return None

def carregar_dados(usuario):
    id_planilha = obter_id_planilha(usuario)
    if not id_planilha:
        st.error(f"Erro: Não existe ID de planilha configurado para o usuário '{usuario}'.")
        return None

    client = conectar_google_sheets()
    if client:
        try:
            # --- MUDANÇA CRÍTICA: USA ID DIRETO (open_by_key) ---
            sheet = client.open_by_key(id_planilha).sheet1
            
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            if df.empty:
                return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            
            # Converte números
            cols_num = ["Valor Bruto", "Comissão (%)", "Valor Líquido"]
            for col in cols_num:
                if col in df.columns:
                    df[col
