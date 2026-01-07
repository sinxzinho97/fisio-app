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
    if not nome_planilha:
        st.error(f"Erro: Não existe planilha configurada para o usuário '{usuario}' nos Secrets.")
        return None

    client = conectar_google_sheets()
    if client:
        try:
            # Tenta abrir a planilha
            sheet = client.open(nome_planilha).sheet1
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            # Se a planilha estiver vazia, retorna estrutura padrão
            if df.empty:
                return pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            
            # Garante que colunas numéricas sejam números (evita erro de cálculo)
            cols_num = ["Valor Bruto", "Comissão (%)", "Valor Líquido"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            return df
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"A planilha '{nome_planilha}' não foi encontrada no Google. Verifique o nome ou compartilhe com o e-mail do robô.")
            return None
    return None

def salvar_dados(df, usuario):
    nome_planilha = obter_nome_planilha(usuario)
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(nome_planilha).sheet1
            sheet.clear() # Limpa tudo antes de escrever
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Erro ao salvar no Google: {e}")
            return False
    return False

# --- TELA DE LOGIN (CORRIGIDA COM FORMULÁRIO) ---
def verificar_login():
    if 'logado' not in st.session_state:
        st.session_state.logado = False
        st.session_state.usuario_atual = ""

    if not st.session_state.logado:
        st.markdown("<h1 style='text-align: center;'>🔐 Acesso Restrito</h1>", unsafe_allow_html=True)
        st.write("---")
        
        # AQUI ESTÁ A CORREÇÃO: Usar st.form evita o erro da "primeira tentativa"
        with st.form("login_form"):
            usuario = st.text_input("Usuário:")
            senha = st.text_input("Senha:", type="password")
            submit_button = st.form_submit_button("Entrar", use_container_width=True)

            if submit_button:
                try:
                    senhas_cadastradas = st.secrets["passwords"]
                    # Verifica se usuário existe e senha bate
                    if usuario in senhas_cadastradas and senhas_cadastradas[usuario] == senha:
                        st.session_state.logado = True
                        st.session_state.usuario_atual = usuario
                        st.success("Login realizado! Carregando...")
                        time.sleep(1) # Pequena pausa para garantir
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

# Tenta carregar os dados SE eles ainda não estiverem na memória
if 'df' not in st.session_state or st.session_state.df is None:
    with st.spinner(f'Baixando dados de {st.session_state.usuario_atual} da nuvem...'):
        dados_nuvem = carregar_dados(st.session_state.usuario_atual)
        if dados_nuvem is not None:
            st.session_state.df = dados_nuvem
        else:
            st.stop() # Para se não conseguir carregar

# Define comissão padrão baseada no último registro ou 75%
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
    # Botão de Sair com limpeza total de memória
    if st.button("Sair (Logout)", use_container_width=True):
        st.session_state.logado = False
        st.session_state.usuario_atual = ""
        if 'df' in st.session_state:
            del st.session_state['df'] # Apaga os dados da memória local
        st.rerun()

# --- TÍTULO E ABAS ---
st.markdown("<h2 style='text-align: center;'>🩺 Controle Financeiro</h2>", unsafe_allow_html=True)

nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
abas = st.tabs(nomes_semanas + ["📊 Resumo"])

# --- LÓGICA DAS SEMANAS ---
for i, semana_nome in enumerate(nomes_semanas):
    with abas[i]:
        st.subheader(f"📝 {semana_nome}")
        
        with st.container(border=True):
            col1, col2 = st.columns([2, 1])
            paciente = col1.text_input(f"Nome", key=f"n_{i}")
            valor = col2.number_input(f"Valor R$", min_value=0.0, step=10.0, key=f"v_{i}")
            
            if st.button(f"Salvar", key=f"b_{i}", use_container_width=True):
                if paciente and valor > 0:
                    with st.spinner('Enviando para o Google Sheets...'):
                        liquido = valor * (comissao_usuario / 100)
                        novo = {
                            "Semana": semana_nome, 
                            "Paciente": paciente, 
                            "Valor Bruto": valor, 
                            "Comissão (%)": comissao_usuario, 
                            "Valor Líquido": liquido
                        }
                        # Adiciona na memória local
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                        # Salva na nuvem imediatamente
                        sucesso = salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                        if sucesso:
                            st.success("✅ Salvo na nuvem!")
                            time.sleep(0.5)
                            st.rerun()
                else:
                    st.warning("Preencha o nome e o valor.")

        # Tabela de visualização
        df_sem = st.session_state.df[st.session_state.df["Semana"] == semana_nome]
        if not df_sem.empty:
            st.dataframe(df_sem[["Paciente", "Valor Bruto", "Valor Líquido"]], hide_index=True, use_container_width=True)
            st.info(f"Total Semana: R$ {df_sem['Valor Líquido'].sum():,.2f}")
            
            if st.button("🗑️ Desfazer Último", key=f"d_{i}"):
                with st.spinner('Apagando...'):
                    indices = df_sem.index
                    if len(indices) > 0:
                        st.session_state.df = st.session_state.df.drop(indices[-1])
                        salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                        st.rerun()

# --- ABA DE RESUMO ---
with abas[4]:
    st.header("📊 Fechamento")
    if not st.session_state.df.empty:
        resumo = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.dataframe(resumo.style.format({"Valor Líquido": "R$ {:,.2f}"}), hide_index=True, use_container_width=True)
        st.metric("SEU TOTAL MÊS", f"R$ {st.session_state.df['Valor Líquido'].sum():,.2f}")
        
        st.divider()
        if st.button("🔴 APAGAR MÊS INTEIRO", type="primary", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns=["Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df, st.session_state.usuario_atual)
            st.rerun()
