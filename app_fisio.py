import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES VISUAIS ---
st.set_page_config(page_title="Gestão Fisio PRO", page_icon="🩺", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    div.stButton > button:first-child { background-color: #28a745; color: white; border: none; }
    button[data-baseweb="tab"]:nth-child(1) { border-bottom: 4px solid #007bff !important; color: #007bff; }
    button[data-baseweb="tab"]:nth-child(2) { border-bottom: 4px solid #28a745 !important; color: #28a745; }
    button[data-baseweb="tab"]:nth-child(3) { border-bottom: 4px solid #ffc107 !important; color: #ffc107; }
    button[data-baseweb="tab"]:nth-child(4) { border-bottom: 4px solid #6f42c1 !important; color: #6f42c1; }
    button[data-baseweb="tab"]:nth-child(5) { border-bottom: 4px solid #fd7e14 !important; color: #fd7e14; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE CONEXÃO E DADOS ---
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except: return None

def carregar_dados(usuario):
    nome_planilha = st.secrets["spreadsheets"][usuario]
    client = conectar_google_sheets()
    try:
        sheet = client.open(nome_planilha).sheet1
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty: return pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
        for col in ["Valor Bruto", "Comissão (%)", "Valor Líquido"]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])

def salvar_dados(df, usuario):
    nome_planilha = st.secrets["spreadsheets"][usuario]
    client = conectar_google_sheets()
    try:
        sheet = client.open(nome_planilha).sheet1
        sheet.clear() 
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    except: return False

# --- FUNÇÃO PARA GERAR IMAGEM JPEG ---
def gerar_imagem_resumo(df_semana, titulo_semana, usuario):
    # Cria uma imagem em branco
    largura = 600
    altura = 150 + (len(df_semana) * 40)
    img = Image.new('RGB', (largura, altura), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Textos
    d.text((20, 20), f"🩺 RESUMO {titulo_semana.upper()}", fill=(0, 0, 0))
    d.text((20, 45), f"Profissional: {usuario} | Data: {datetime.now().strftime('%d/%m/%Y')}", fill=(100, 100, 100))
    d.line([(20, 70), (580, 70)], fill=(200, 200, 200), width=2)
    
    y = 90
    d.text((20, y), "DATA", fill=(0, 0, 0))
    d.text((150, y), "PACIENTE", fill=(0, 0, 0))
    d.text((450, y), "VALOR", fill=(0, 0, 0))
    
    y += 30
    total = 0
    for _, row in df_semana.iterrows():
        d.text((20, y), str(row['Data']), fill=(50, 50, 50))
        d.text((150, y), str(row['Paciente'])[:25], fill=(50, 50, 50))
        d.text((450, y), formatar_moeda(row['Valor Líquido']), fill=(50, 50, 50))
        total += row['Valor Líquido']
        y += 35
    
    d.line([(20, y), (580, y)], fill=(200, 200, 200), width=2)
    d.text((350, y + 20), f"TOTAL: {formatar_moeda(total)}", fill=(40, 167, 69))
    
    # Salva em buffer
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()

# --- LOGIN ---
if 'logado' not in st.session_state:
    st.session_state.logado, st.session_state.usuario_atual = False, ""

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🔐 Login Fisio</h1>", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Usuário:")
        s = st.text_input("Senha:", type="password")
        if st.form_submit_button("Entrar", use_container_width=True):
            if u in st.secrets["passwords"] and st.secrets["passwords"][u] == s:
                st.session_state.logado, st.session_state.usuario_atual = True, u
                st.rerun()
    st.stop()

if 'df' not in st.session_state:
    st.session_state.df = carregar_dados(st.session_state.usuario_atual)

comissao_fixa = 75 if st.session_state.usuario_atual.lower() == "brenda" else 50
lista_pacientes = sorted(st.session_state.df["Paciente"].unique().tolist()) if not st.session_state.df.empty else []

st.markdown(f"<h3 style='text-align: center;'>🩺 Olá, {st.session_state.usuario_atual}</h3>", unsafe_allow_html=True)

abas = st.tabs(["Semana 1", "Semana 2", "Semana 3", "Semana 4", "📊 Resumo"])

for i, sem in enumerate(["Semana 1", "Semana 2", "Semana 3", "Semana 4"]):
    with abas[i]:
        with st.container(border=True):
            c1, c2 = st.columns([2, 1])
            nome_digitado = c1.text_input("Paciente", key=f"in_{i}")
            valor = c2.number_input("Valor R$", step=5.0, key=f"v_{i}")
            paciente_sugerido = st.selectbox("Sugestões", [""] + lista_pacientes, key=f"sel_{i}")
            data_atend = st.date_input("Data", value=datetime.now(), key=f"d_{i}")
            
            nome_f = paciente_sugerido if paciente_sugerido != "" else nome_digitado
            if st.button("Confirmar Atendimento", key=f"btn_{i}", use_container_width=True):
                if nome_f and valor > 0:
                    liq = valor * (comissao_fixa / 100)
                    novo = {"Data": str(data_atend), "Semana": sem, "Paciente": nome_f, "Valor Bruto": valor, "Comissão (%)": comissao_fixa, "Valor Líquido": liq}
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                    salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                    st.rerun()

        df_sem = st.session_state.df[st.session_state.df["Semana"] == sem]
        if not df_sem.empty:
            st.dataframe(df_sem[["Data", "Paciente", "Valor Líquido"]], use_container_width=True, hide_index=True)
            
            # --- BOTÃO DE DOWNLOAD DA IMAGEM JPEG ---
            img_data = gerar_imagem_resumo(df_sem, sem, st.session_state.usuario_atual)
            st.download_button(
                label=f"📸 Baixar Imagem {sem}",
                data=img_data,
                file_name=f"Resumo_{sem.replace(' ', '')}.jpg",
                mime="image/jpeg",
                use_container_width=True
            )

            if st.button("Desfazer Último", key=f"del_{i}"):
                st.session_state.df = st.session_state.df.drop(df_sem.index[-1])
                salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                st.rerun()

# --- RESUMO MENSAL ---
with abas[4]:
    if not st.session_state.df.empty:
        st.subheader("📊 Fechamento Mensal")
        res = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(["Semana 1", "Semana 2", "Semana 3", "Semana 4"]).fillna(0).reset_index()
        st.dataframe(res.style.format({"Valor Líquido": lambda x: formatar_moeda(x)}), hide_index=True, use_container_width=True)
        st.metric("TOTAL MÊS", formatar_moeda(st.session_state.df["Valor Líquido"].sum()))
        
        if st.button("🔴 APAGAR MÊS", use_container_width=True, type="primary"):
            st.session_state.df = pd.DataFrame(columns=["Data", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df, st.session_state.usuario_atual)
            st.rerun()
