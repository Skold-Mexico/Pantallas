import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import json

# ==============================
# --- Configuración página ---
# ==============================
st.set_page_config(page_title="Dashboard Global", layout="wide")
st.title("📊 Dashboard Global de Remisiones")

# ==============================
# --- Conexión Google Sheets ---
# ==============================
try:
    google_creds = st.secrets["google"]
except Exception:
    with open("secrets.json", "r", encoding="utf-8") as f:
        google_creds = json.load(f)

credenciales = Credentials.from_service_account_info(
    google_creds,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credenciales)
sh = gc.open_by_key("1UTPaPqfVZ5Z6dmlz9OMPp4W1mMcot9_piz7Bctr5S-I")

# ==============================
# --- Funciones de filtrado ---
# ==============================
def es_fecha_valida(valor):
    if not valor or str(valor).strip() == "":
        return False
    try:
        datetime.strptime(str(valor).strip(), "%d/%m/%Y")
        return True
    except:
        return False

def limpiar_remisiones(df, col='Remision'):
    if col in df.columns:
        df = df[df[col].notna() & (df[col].str.strip() != "")]
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].apply(lambda x: re.sub(r'[^\x20-\x7E]+', '', x))
    return df

# ==============================
# --- Surtimiento ---
# ==============================
ws_log = sh.worksheet("Logistica")
data_log = ws_log.get_all_values()
headers_log = data_log[0]
df_surt = pd.DataFrame(data_log[1:], columns=[c.strip() for c in headers_log])
df_surt = limpiar_remisiones(df_surt)

if 'Factura' in df_surt.columns and 'Fecha fact' in df_surt.columns:
    condiciones = ((df_surt['Factura'].isna()) | (df_surt['Factura'].str.strip() == "") | (df_surt['Factura'].str.upper() == "N/A")) & \
                  (~df_surt['Fecha fact'].apply(es_fecha_valida))
    if 'Fecha entrega' in df_surt.columns:
        condiciones &= (df_surt['Fecha entrega'].isna() | (df_surt['Fecha entrega'].str.strip() == ""))
    if 'Fecha de SURTIMIENTO' in df_surt.columns:
        condiciones &= (~df_surt['Fecha de SURTIMIENTO'].apply(es_fecha_valida))
    df_surt = df_surt[condiciones]

total_surtimiento = len(df_surt)

# ==============================
# --- Embarques ---
# ==============================
df_emb = limpiar_remisiones(pd.DataFrame(data_log[1:], columns=[c.strip() for c in headers_log]))
if 'Fecha Entrega' in df_emb.columns and 'T. Servicio' in df_emb.columns:
    df_emb = df_emb[
        ~df_emb['Fecha Entrega'].apply(es_fecha_valida) &
        df_emb['T. Servicio'].notna() &
        (df_emb['T. Servicio'].str.strip() != "") &
        (df_emb['T. Servicio'].str.upper() != "N/A")
    ]
total_embarques = len(df_emb)

# ==============================
# --- Facturación ---
# ==============================
ws_ped = sh.worksheet("Ped Pendientes")
data_ped = ws_ped.get_all_values()
data_ped = [row[:6] for row in data_ped]
headers_ped = data_ped[0]
df_ped = pd.DataFrame(data_ped[1:], columns=headers_ped)

df_log2 = pd.DataFrame(data_log[1:], columns=[c.strip() for c in headers_log])
df_log2['no. pedido'] = df_log2['no. pedido'].astype(str).str.strip()
df_ped['no. pedido'] = df_ped['no. pedido'].astype(str).str.strip()
df_ped['Estatus operativo'] = df_ped['Estatus operativo'].astype(str).str.strip()

estatus_validos = ["FACTURACION/FISICO EMBARQUES", "EMBARQUES"]
df_ped_filtrado = df_ped[df_ped['Estatus operativo'].isin(estatus_validos)]
df_fact = df_log2.merge(df_ped_filtrado[['no. pedido', 'Estatus operativo']], on='no. pedido', how='inner')
df_fact = limpiar_remisiones(df_fact)

if 'Factura' in df_fact.columns and 'Fecha Entrega' in df_fact.columns:
    df_fact = df_fact[
        (~df_fact['Fecha Entrega'].apply(es_fecha_valida)) |
        (df_fact['Factura'].isna()) |
        (df_fact['Factura'].str.strip() == "") |
        (df_fact['Factura'].str.upper() == "N/A")
    ]

total_facturacion = len(df_fact)

# ==============================
# --- Mostrar Totales ---
# ==============================
col1, col2, col3 = st.columns(3)
col1.metric("📦 Surtimiento", total_surtimiento)
col2.metric("🚚 Embarques", total_embarques)
col3.metric("📑 Facturación", total_facturacion)
