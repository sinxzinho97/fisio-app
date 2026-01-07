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
            # --- TENTA ABRIR PELO ID ---
            sheet = client.open_by_key(id_planilha).sheet1
            
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            if df.empty:
                return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            
            # Converte números (garante que não quebre o cálculo)
            cols_num = ["Valor Bruto", "Comissão (%)", "Valor Líquido"]
            for col in cols_num:
                if col in df.columns:
                    # A LINHA QUE DEU ERRO ANTES É ESTA ABAIXO:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            return df
        except gspread.exceptions.APIError:
            st.error("Erro de Permissão: O robô não conseguiu acessar a planilha pelo ID.")
            st.warning("Verifique se o e-mail do robô está adicionado como EDITOR na planilha.")
            return None
        except Exception as e:
            st.error(f"Erro ao abrir planilha (ID incorreto?): {e}")
            return None
    return None

def salvar_dados(df, usuario):
    id_planilha = obter_id_planilha(usuario)
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open_by_key(id_planilha).sheet1
            sheet.clear() 
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")
            return False
    return False

# --- TELA DE LOGIN ---
def verificar_login():
    if 'logado' not in st.session_state:
        st.session_state.logado = False
        st.session_state.usuario_atual = ""

    if not st.session_state.logado:
        st.markdown("<h1 style='text-align: center;'>🔐 Acesso Restrito</h1>", unsafe_allow_html=True)
        st.write("---")
        
        with st.form("login_form"):
            usuario = st.text_input("Usuário:")
            senha = st.text_input("Senha:", type="password")
            submit_button = st.form_submit_button("Entrar", use_container_width=True)

            if submit_button:
                try:
                    senhas_cadastradas = st.secrets["passwords"]
                    if usuario in senhas_cadastradas and senhas_cadastradas[usuario] == senha:
                        st.session_state.logado = True
                        st.session_state.usuario_atual = usuario
                        st.success("Login realizado!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")
                except Exception as e:
                    st.error(f"Erro nos Secrets: {e}")
        return False
    return True

# --- SISTEMA PRINCIPAL ---
if not verificar_login():
    st.stop()

# Carrega dados
if 'df' not in st.session_state or st.session_state.df is None:
    with st.spinner(f'Carregando planilha...'):
        dados_nuvem = carregar_dados(st.session_state.usuario_atual)
        if dados_nuvem is not None:
            st.session_state.df = dados_nuvem
        else:
            st.stop() 

# Define comissão padrão
ultima_comissao = 75
if not st.session_state.df.empty and "Comissão (%)" in st.session_state.df.columns:
    try:
        ultima_comissao = int(st.session_state.df.iloc[-1]["Comissão (%)"])
    except:
        pass

# --- BARRA LATERAL ---
with st.sidebar:
    st.info(f"👤 **{st.session_state.usuario_atual}**")
    
    st.header("⚙️ Configuração")
    comissao_usuario = st.number_input("Sua Comissão (%)", 0, 100, value=ultima_comissao)
    
    st.divider()
    if st.button("Sair (Logout)", use_container_width=True):
        st.session_state.logado = False
        st.session_state.usuario_atual = ""
        if 'df' in st.session_state:
            del st.session_state['df']
        st.rerun()

# --- INTERFACE ---
st.markdown("<h2 style='text-align: center;'>🩺 Controle Financeiro</h2>", unsafe_allow_html=True)

nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
abas = st.tabs(nomes_semanas + ["📊 Resumo"])

# Loop Semanas
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
                        liquido = valor * (comissao_usuario / 100)
                        novo = {
                            "Semana": semana_nome, 
                            "Paciente": paciente, 
                            "Valor Bruto": valor, 
                            "Comissão (%)": comissao_usuario, 
                            "Valor Líquido": liquido
                        }
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                        salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                        st.success("✅ Salvo!")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.warning("Preencha os campos.")

        df_sem = st.session_state.df[st.session_state.df["Semana"] == semana_nome]
        if not df_sem.empty:
            st.dataframe(df_sem[["Paciente", "Valor Bruto", "Valor Líquido"]], hide_index=True, use_container_width=True)
            st.info(f"Total: R$ {df_sem['Valor Líquido'].sum():,.2f}")
            
            if st.button("🗑️ Desfazer Último", key=f"d_{i}"):
                with st.spinner('Apagando...'):
                    indices = df_sem.index
                    if len(indices) > 0:
                        st.session_state.df = st.session_state.df.drop(indices[-1])
                        salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                        st.rerun()

# Resumo
with abas[4]:
    st.header("📊 Fechamento")
    if not st.session_state.df.empty:
        resumo = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.dataframe(resumo.style.format({"Valor Líquido": "R$ {:,.2f}"}), hide_index=True, use_container_width=True)
        st.metric("TOTAL MÊS", f"R$ {st.session_state.df['Valor Líquido'].sum():,.2f}")
        
        st.divider()
        if st.button("🔴 APAGAR MÊS", type="primary", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df, st.session_state.usuario_atual)
            st.rerun()
