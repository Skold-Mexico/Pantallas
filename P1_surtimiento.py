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
st.set_page_config(page_title="Surtimiento", layout="wide")
st.subheader("Surtimiento")

# ==============================
# --- Conexión Google Sheets ---
# ==============================
try:
    # Cloud
    google_creds = st.secrets["google"]
except Exception:
    # Local
    with open("secrets.json", "r", encoding="utf-8") as f:
        google_creds = json.load(f)

credenciales = Credentials.from_service_account_info(
    google_creds,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credenciales)
sh = gc.open_by_key("1UTPaPqfVZ5Z6dmlz9OMPp4W1mMcot9_piz7Bctr5S-I")
ws = sh.worksheet("Logistica")

# ==============================
# --- Cargar datos ---
# ==============================
data = ws.get_all_values()
headers = data[0]
data_recortada = data[1:]
df = pd.DataFrame(data_recortada, columns=[c.strip() for c in headers])

# ==============================
# --- Limpieza ---
# ==============================
if 'Remision' in df.columns:
    df = df[df['Remision'].notna() & (df['Remision'].str.strip() != "")]
    df['Remision'] = df['Remision'].astype(str).str.strip()
    df['Remision'] = df['Remision'].apply(lambda x: re.sub(r'[^\x20-\x7E]+', '', x))

# ==============================
# --- Validación de fechas ---
# ==============================
def es_fecha_valida(valor):
    if not valor or str(valor).strip() == "":
        return False
    valor = str(valor).strip()
    try:
        datetime.strptime(valor, "%d/%m/%Y")
        return True
    except ValueError:
        pass
    try:
        partes = [p.strip() for p in valor.split("-")]
        if len(partes) == 2:
            datetime.strptime(partes[0], "%d/%m/%Y")
            datetime.strptime(partes[1], "%d/%m/%Y")
            return True
    except ValueError:
        pass
    return False

if 'Factura' in df.columns and 'Fecha fact' in df.columns:
    condiciones = ((df['Factura'].isna()) | (df['Factura'].str.strip() == "") | (df['Factura'].str.upper() == "N/A")) & \
                  (~df['Fecha fact'].apply(es_fecha_valida))

    if 'Fecha entrega' in df.columns:
        condiciones &= (df['Fecha entrega'].isna() | (df['Fecha entrega'].str.strip() == ""))
    if 'Fecha de SURTIMIENTO' in df.columns:
        condiciones &= (~df['Fecha de SURTIMIENTO'].apply(es_fecha_valida))

    df = df[condiciones]

# ==============================
# --- Procesar columna Demora y semáforo ---
# ==============================
if 'Demora' in df.columns:
    df['Demora'] = pd.to_numeric(df['Demora'], errors='coerce')

def semaforo_demora(x):
    if pd.isnull(x):
        return "⚪"
    if x < 1:
        return "🟢"
    elif x == 1:
        return "🟡"
    else:
        return "🔴"

df['Semaforo'] = df['Demora'].apply(semaforo_demora) if 'Demora' in df.columns else "⚪"

# ==============================
# --- KPIs ---
# ==============================
total = len(df)
verde_count = (df['Semaforo'] == "🟢").sum()
amarillo_count = (df['Semaforo'] == "🟡").sum()
rojo_count = (df['Semaforo'] == "🔴").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total", total)
col2.metric("🟢 Verde (<1)", verde_count)
col3.metric("🟡 Amarillo (=1)", amarillo_count)
col4.metric("🔴 Rojo (>1)", rojo_count)

st.markdown("---")

# ==============================
# --- Tablero tipo grid ---
# ==============================
cuadros_por_fila = 22
fila = []

for i, row in df.iterrows():
    color = (
        "#d4edda" if row['Semaforo'] == "🟢" else
        "#fff3cd" if row['Semaforo'] == "🟡" else
        "#f8d7da" if row['Semaforo'] == "🔴" else "#e9ecef"
    )

    fila.append((row['Remision'], row['Semaforo'], color))

    if len(fila) == cuadros_por_fila or i == df.index[-1]:
        cols = st.columns(len(fila))
        for c, (rem, sem, col_color) in zip(cols, fila):
            c.markdown(
                f"""
                <div style="
                    background-color:{col_color};
                    border-radius:6px;
                    padding:6px;
                    text-align:center;
                    margin:2px;
                    color:black;
                    font-size:12px;
                    white-space:nowrap;
                ">
                    <strong>{rem}</strong><br>{sem}
                </div>
                """,
                unsafe_allow_html=True
            )
        fila = []
