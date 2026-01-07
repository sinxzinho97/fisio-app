import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime, time as dt_time
from PIL import Image, ImageDraw
import io

# --- CONFIGURAÇÕES VISUAIS ---
st.set_page_config(page_title="Gestão Fisio PRO", page_icon="🩺", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    div.stButton > button:first-child { background-color: #28a745; color: white; border: none; }
    
    /* Cores das Abas */
    button[data-baseweb="tab"]:nth-child(1) { border-bottom: 4px solid #007bff !important; color: #007bff; }
    button[data-baseweb="tab"]:nth-child(2) { border-bottom: 4px solid #28a745 !important; color: #28a745; }
    button[data-baseweb="tab"]:nth-child(3) { border-bottom: 4px solid #ffc107 !important; color: #ffc107; }
    button[data-baseweb="tab"]:nth-child(4) { border-bottom: 4px solid #6f42c1 !important; color: #6f42c1; }
    button[data-baseweb="tab"]:nth-child(5) { border-bottom: 4px solid #fd7e14 !important; color: #fd7e14; font-weight: bold; }
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
        return gspread.authorize(creds)
    except: return None

def carregar_dados(usuario):
    nome_planilha = st.secrets["spreadsheets"][usuario]
    client = conectar_google_sheets()
    try:
        sheet = client.open(nome_planilha).sheet1
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty: 
            return pd.DataFrame(columns=["Data", "Hora", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
        for col in ["Valor Bruto", "Comissão (%)", "Valor Líquido"]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: 
        return pd.DataFrame(columns=["Data", "Hora", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])

def salvar_dados(df, usuario):
    nome_planilha = st.secrets["spreadsheets"][usuario]
    client = conectar_google_sheets()
    try:
        sheet = client.open(nome_planilha).sheet1
        sheet.clear() 
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    except: return False

# --- GERAR IMAGEM JPEG ---
def gerar_imagem_jpeg(df_dados, titulo, usuario, tipo="semanal"):
    largura = 650
    altura = 180 + (len(df_dados) * 45)
    img = Image.new('RGB', (largura, altura), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    d.text((20, 20), f"🩺 {titulo.upper()}", fill=(0, 0, 0))
    d.text((20, 45), f"Profissional: {usuario} | Gerado em: {datetime.now().strftime('%d/%m/%Y')}", fill=(100, 100, 100))
    d.line([(20, 75), (630, 75)], fill=(200, 200, 200), width=2)
    
    y = 100
    if tipo == "semanal":
        d.text((20, y), "DATA/HORA", fill=(0, 0, 0))
        d.text((200, y), "PACIENTE", fill=(0, 0, 0))
        d.text((500, y), "VALOR", fill=(0, 0, 0))
        y += 40
        for _, row in df_dados.iterrows():
            d.text((20, y), f"{row['Data']} {row.get('Hora', '')}", fill=(50, 50, 50))
            d.text((200, y), str(row['Paciente'])[:25], fill=(50, 50, 50))
            d.text((500, y), formatar_moeda(row['Valor Líquido']), fill=(50, 50, 50))
            y += 35
        total = df_dados['Valor Líquido'].sum()
    else:
        d.text((20, y), "PERÍODO", fill=(0, 0, 0))
        d.text((500, y), "VALOR", fill=(0, 0, 0))
        y += 40
        for _, row in df_dados.iterrows():
            d.text((20, y), str(row['Semana']), fill=(50, 50, 50))
            d.text((500, y), formatar_moeda(row['Valor Líquido']), fill=(50, 50, 50))
            y += 35
        total = df_dados['Valor Líquido'].sum()

    d.line([(20, y+10), (630, y+10)], fill=(200, 200, 200), width=2)
    d.text((320, y + 30), f"TOTAL A RECEBER: {formatar_moeda(total)}", fill=(40, 167, 69))
    
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

# --- CONFIGURAÇÕES DE TEMPO ---
# Cria lista de horários de 06:00 até 21:00 (intervalos de 15 min)
lista_horarios = []
for h in range(6, 22):
    for m in [0, 15, 30, 45]:
        if h == 21 and m > 0: continue
        lista_horarios.append(f"{h:02d}:{m:02d}")

# --- LÓGICA DE COMISSÃO ---
usuario_logado = st.session_state.usuario_atual.lower()
comissao_padrao = 75 if usuario_logado == "brenda" else 50
lista_pacientes = sorted(st.session_state.df["Paciente"].unique().tolist()) if not st.session_state.df.empty else []

def get_total_sem(sem_nome):
    return st.session_state.df[st.session_state.df["Semana"] == sem_nome]["Valor Líquido"].sum()

st.markdown(f"<h3 style='text-align: center;'>🩺 Olá, {st.session_state.usuario_atual}</h3>", unsafe_allow_html=True)

nomes_semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
labels = [f"{s} ({formatar_moeda(get_total_sem(s))})" for s in nomes_semanas]
abas = st.tabs(labels + ["📊 Resumo Mensal"])

for i, sem in enumerate(nomes_semanas):
    with abas[i]:
        with st.container(border=True):
            c1, c2 = st.columns([2, 1])
            nome_digitado = c1.text_input("Paciente", key=f"in_{i}")
            valor = c2.number_input("Valor R$", step=5.0, key=f"v_{i}")
            
            c_sug, c_data, c_hora = st.columns([2, 1, 1])
            paciente_sugerido = c_sug.selectbox("Sugestões", [""] + lista_pacientes, key=f"sel_{i}")
            data_atend = c_data.date_input("Data", value=datetime.now(), key=f"d_{i}")
            
            # NOVO: Seletor de Horário Limitado (06:00 - 21:00)
            hora_selecionada = c_hora.selectbox("Horário", lista_horarios, index=28, key=f"h_{i}") # index 28 aproxima das 13:00 como padrão
            
            meio_a_meio = False
            if usuario_logado == "brenda":
                meio_a_meio = st.checkbox("Atendimento Meio a Meio (50%)", key=f"check_{i}")
            
            nome_f = paciente_sugerido if paciente_sugerido != "" else nome_digitado
            if st.button("Confirmar Atendimento", key=f"btn_{i}", use_container_width=True):
                if nome_f and valor > 0:
                    comissao_final = 50 if meio_a_meio else comissao_padrao
                    liq = valor * (comissao_final / 100)
                    novo = {
                        "Data": str(data_atend), 
                        "Hora": hora_selecionada,
                        "Semana": sem, 
                        "Paciente": nome_f, 
                        "Valor Bruto": valor, 
                        "Comissão (%)": comissao_final, 
                        "Valor Líquido": liq
                    }
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo])], ignore_index=True)
                    salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                    st.rerun()

        df_sem = st.session_state.df[st.session_state.df["Semana"] == sem]
        if not df_sem.empty:
            st.dataframe(df_sem[["Data", "Hora", "Paciente", "Valor Líquido"]], use_container_width=True, hide_index=True)
            img_sem = gerar_imagem_jpeg(df_sem, f"Resumo {sem}", st.session_state.usuario_atual, "semanal")
            st.download_button(label=f"📸 Baixar Imagem {sem}", data=img_sem, file_name=f"Resumo_{sem.replace(' ', '')}.jpg", mime="image/jpeg", use_container_width=True)

            if st.button("Desfazer Último", key=f"del_{i}"):
                st.session_state.df = st.session_state.df.drop(df_sem.index[-1])
                salvar_dados(st.session_state.df, st.session_state.usuario_atual)
                st.rerun()

# --- RESUMO MENSAL ---
with abas[4]:
    if not st.session_state.df.empty:
        st.subheader("📊 Consolidado Mensal")
        res = st.session_state.df.groupby("Semana")["Valor Líquido"].sum().reindex(nomes_semanas).fillna(0).reset_index()
        st.dataframe(res.style.format({"Valor Líquido": lambda x: formatar_moeda(x)}), hide_index=True, use_container_width=True)
        st.metric("TOTAL MÊS", formatar_moeda(st.session_state.df["Valor Líquido"].sum()))
        img_mes = gerar_imagem_jpeg(res, "Resumo Mensal Consolidado", st.session_state.usuario_atual, "mensal")
        st.download_button(label="📸 Baixar Imagem Resumo Mensal", data=img_mes, file_name="Resumo_Mensal.jpg", mime="image/jpeg", use_container_width=True)
        st.divider()
        if st.button("🔴 APAGAR TUDO (NOVO MÊS)", use_container_width=True, type="primary"):
            st.session_state.df = pd.DataFrame(columns=["Data", "Hora", "Semana", "Paciente", "Valor Bruto", "Comissão (%)", "Valor Líquido"])
            salvar_dados(st.session_state.df, st.session_state.usuario_atual)
            st.rerun()
