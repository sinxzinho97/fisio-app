import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime
import streamlit.components.v1 as components

# --- CONFIGURAÇÕES VISUAIS E CORES DAS ABAS ---
st.set_page_config(page_title="Gestão Fisio PRO", page_icon="🩺", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Botão de Confirmação Verde */
    div.stButton > button:first-child {
        background-color: #28a745;
        color: white;
        border: none;
    }
    
    /* Cores das Abas */
    button[data-baseweb="tab"]:nth-child(1) { border-bottom: 4px solid #007bff !important; color: #007bff; }
    button[data-baseweb="tab"]:nth-child(2) { border-bottom: 4px solid #28a745 !important; color: #28a745; }
    button[data-baseweb="tab"]:nth-child(3) { border-bottom: 4px solid #ffc107 !important; color: #ffc107; }
    button[data-baseweb="tab"]:nth-child(4) { border-bottom: 4px solid #6f42c1 !important; color: #6f42c1; }
    button[data-baseweb="tab"]:nth-child(5) { border-bottom: 4px solid #fd7e14 !important; color: #fd7e14; font-weight: bold; }
    
    /* Estilo do Card de Captura (PNG) */
    .screenshot-target {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #eee;
        color: black;
    }
    </style>
    
    <script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
    <script>
    function downloadScreenshot(elementId, fileName) {
        const element = document.getElementById(elementId);
        html2canvas(element, { scale: 2 }).then(canvas => {
            const link = document.createElement('a');
            link.download = fileName;
            link.href = canvas.toDataURL("image/png");
            link.click();
        });
    }
    </script>
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

# --- CONFIGURAÇÃO ---
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
            # --- ÁREA PARA CAPTURA PNG ---
            area_id = f"capture_{i}"
            total_sem = df_sem['Valor Líquido'].sum()
            
            st.markdown(f"""
            <div id="{area_id}" class="screenshot-target">
                <h3 style="color: #333; margin-bottom: 5px;">🩺 Resumo {sem}</h3>
                <p style="color: #666; font-size: 12px;">Profissional: {st.session_state.usuario_atual}</p>
                <hr>
                <table style="width:100%; text-align: left; font-size: 14px;">
                    <tr style="border-bottom: 1px solid #ddd;">
                        <th>Data</th><th>Paciente</th><th>Valor</th>
                    </tr>
                    {"".join([f"<tr><td>{r['Data']}</td><td>{r['Paciente']}</td><td>{formatar_moeda(r['Valor Líquido'])}</td></tr>" for _, r in df_sem.iterrows()])}
                </table>
                <hr>
                <h4 style="text-align: right; color: #28a745;">TOTAL: {formatar_moeda(total_sem)}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"📸 Baixar Imagem {sem}", key=f"png_{i}"):
                components.html(f"""
                    <script>
                    window.parent.downloadScreenshot('{area_id}', 'Resumo_{sem.replace(" ", "")}.png');
                    </script>
                """, height=0)

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
