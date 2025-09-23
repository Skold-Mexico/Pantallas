import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# ==============================
# --- Conexión Google Sheets ---
# ==============================
google_creds = st.secrets["google"]

credenciales = Credentials.from_service_account_info(
    google_creds,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credenciales)
sh = gc.open_by_key("1UTPaPqfVZ5Z6dmlz9OMPp4W1mMcot9_piz7Bctr5S-I")

st.set_page_config(page_title="Global Remisiones", layout="wide")
st.title("📊 Tablero Global de Remisiones")

# ==============================
# --- TABLERO 1: Logística ---
# ==============================
try:
    ws = sh.worksheet("Logistica")
    data = ws.get_all_values()
    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)

    if 'Remision' in df.columns:
        df = df[df['Remision'].notna() & (df['Remision'].str.strip() != "")]
        total_logistica = len(df)
    else:
        total_logistica = 0
except:
    total_logistica = 0

# ==============================
# --- TABLERO 2: Embarques ---
# ==============================
try:
    ws = sh.worksheet("Logistica")
    data = ws.get_all_values()
    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)

    if 'Remision' in df.columns:
        df = df[df['Remision'].notna() & (df['Remision'].str.strip() != "")]
        total_embarques = len(df)
    else:
        total_embarques = 0
except:
    total_embarques = 0

# ==============================
# --- TABLERO 3: Pedidos Pendientes ---
# ==============================
try:
    ws_log = sh.worksheet("Logistica")
    df_log = pd.DataFrame(ws_log.get_all_records())

    ws_ped = sh.worksheet("Ped Pendientes")
    data_ped = ws_ped.get_all_values()
    data_ped = [row[:6] for row in data_ped]
    headers = data_ped[0]
    df_ped = pd.DataFrame(data_ped[1:], columns=headers)

    df_log['Pedido'] = df_log['Pedido'].astype(str).str.strip()
    df_ped['Pedido'] = df_ped['Pedido'].astype(str).str.strip()
    df_ped['Estatus operativo'] = df_ped['Estatus operativo'].astype(str).str.strip()

    estatus_validos = ["FACTURACION/FISICO EMBARQUES", "EMBARQUES"]
    df_ped_filtrado = df_ped[df_ped['Estatus operativo'].isin(estatus_validos)]

    df_filtrado = df_log.merge(
        df_ped_filtrado[['Pedido', 'Estatus operativo']],
        on="Pedido",
        how="inner"
    )
    df_filtrado = df_filtrado[df_filtrado['Remision'].notna() & (df_filtrado['Remision'] != "")]
    total_pedidos = len(df_filtrado)
except:
    total_pedidos = 0

# ==============================
# --- TABLERO 4: (pendiente que me pases) ---
# ==============================
total_otro = 0  # aquí lo conectamos igual que los demás cuando me des el código

# ==============================
# --- Dashboard Global ---
# ==============================
col1, col2, col3, col4 = st.columns(4)
col1.metric("📦 Logística", total_logistica)
col2.metric("🚚 Embarques", total_embarques)
col3.metric("📑 Pedidos Pendientes", total_pedidos)
col4.metric("🗂 Otro Tablero", total_otro)
