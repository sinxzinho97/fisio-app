import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("🕵️ Teste de Diagnóstico Google Sheets")

# 1. Tenta conectar com o Google
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    st.success("✅ Conexão com a API do Google: SUCESSO")
    st.write(f"E-mail do Robô (copie e adicione na planilha): `{creds.service_account_email}`")
except Exception as e:
    st.error(f"❌ Falha na Autenticação (Secrets errados): {e}")
    st.stop()

# 2. Tenta abrir a planilha pelo ID
st.write("---")
usuario_teste = st.text_input("Digite o nome do usuário para testar (ex: admin):")

if st.button("Testar Acesso à Planilha"):
    try:
        # Pega o ID dos secrets
        id_planilha = st.secrets["spreadsheets"][usuario_teste]
        st.write(f"Tentando abrir ID: `{id_planilha}`")
        
        # Tenta abrir
        sh = client.open_by_key(id_planilha)
        st.success(f"✅ SUCESSO! Planilha encontrada: '{sh.title}'")
        st.balloons()
        
    except KeyError:
        st.error(f"Usuário '{usuario_teste}' não encontrado nos Secrets [spreadsheets].")
    except gspread.exceptions.APIError as e:
        st.error("❌ ERRO DE API (Provavelmente Permissão):")
        st.warning("O robô conectou no Google, mas o Google disse 'Não deixo você ver esse arquivo'.")
        st.info("Solução: Copie o e-mail do robô acima, vá na planilha > Compartilhar > Colar E-mail > Editor.")
    except Exception as e:
        st.error(f"❌ Erro genérico: {e}")
