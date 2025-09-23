import streamlit as st
import pandas as pd
from datetime import timedelta
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
import json

# ==============================
# --- Autorefresh cada minuto ---
# ==============================
st_autorefresh(interval=5*60*1000, limit=None, key="refresh")  # 5 minutos

# ==============================
# --- Configuración página ---
# ==============================
st.set_page_config(page_title="Pantalla Embarques", layout="wide")
st.markdown("<div style='margin-top:-0.5rem;'></div>", unsafe_allow_html=True)

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

# --- Cargar hoja Logistica ---
ws_log = sh.worksheet("Logistica")
data_log = ws_log.get_all_records()
df_log = pd.DataFrame(data_log)
print("Columnas df_log:", df_log.columns.tolist())
# --- Cargar hoja Ped Pendientes ---
ws_ped = sh.worksheet("Ped Pendientes")
data_ped = ws_ped.get_all_values()
data_ped = [row[:6] for row in data_ped]
headers = data_ped[0]
df_ped = pd.DataFrame(data_ped[1:], columns=headers)
print("Columnas df_ped:", df_ped.columns.tolist())
# ==============================
# --- Limpieza ---
# ==============================
df_log['no. pedido'] = df_log['no. pedido'].astype(str).str.strip()
df_ped['no. pedido'] = df_ped['no. pedido'].astype(str).str.strip()
df_ped['Estatus operativo'] = df_ped['Estatus operativo'].astype(str).str.strip()

estatus_validos = ["FACTURACION/FISICO EMBARQUES", "EMBARQUES"]
df_ped_filtrado = df_ped[df_ped['Estatus operativo'].isin(estatus_validos)]

df_filtrado = df_log.merge(
    df_ped_filtrado[['no. pedido', 'Estatus operativo']],
    on="no. pedido",
    how="inner"
)
df_filtrado = df_filtrado[df_filtrado['Remision'].notna() & (df_filtrado['Remision'] != "")]

# ==============================
# --- Fechas y horas ---
# ==============================
df_filtrado['Fecha fact'] = pd.to_datetime(df_filtrado['Fecha fact'], errors='coerce')
df_filtrado['Hora facturacion'] = pd.to_timedelta(df_filtrado['Hora facturacion'].astype(str), errors="coerce")
df_filtrado['FechaHoraFact'] = df_filtrado['Fecha fact'] + df_filtrado['Hora facturacion'].fillna(pd.Timedelta(0))

df_filtrado['Fecha de SURTIMIENTO'] = pd.to_datetime(df_filtrado['Fecha de SURTIMIENTO'], errors='coerce', dayfirst=True)
df_filtrado['FechaHoraGuia'] = df_filtrado['Fecha de SURTIMIENTO']

def calcular_horas(row):
    if pd.isnull(row['FechaHoraFact']) or pd.isnull(row['FechaHoraGuia']):
        return None
    return (row['FechaHoraFact'] - row['FechaHoraGuia']).total_seconds() / 3600

df_filtrado['HorasTranscurridas'] = df_filtrado.apply(calcular_horas, axis=1)

def semaforo(horas):
    if pd.isnull(horas):
        return "⚪"
    elif horas < 3:
        return "🟢"
    elif 3 <= horas < 6:
        return "🟡"
    else:
        return "🔴"

df_filtrado['Semaforo'] = df_filtrado['HorasTranscurridas'].apply(semaforo)

# ==============================
# --- KPIs arriba ---
# ==============================
col1, col2, col3, col4 = st.columns(4)
col1.metric("Remisiones totales", len(df_filtrado))
col2.metric("🟢 En Verde", (df_filtrado['Semaforo'] == "🟢").sum())
col3.metric("🟡 En Amarillo", (df_filtrado['Semaforo'] == "🟡").sum())
col4.metric("🔴 En Rojo", (df_filtrado['Semaforo'] == "🔴").sum())

st.markdown("<div style='margin-top:-50px'></div>", unsafe_allow_html=True)

# ==============================
# --- Tablero compacto tipo grid ---
# ==============================
df_tablero = df_filtrado[['Remision', 'Semaforo']].dropna()

html = """
<style>
.block-container { padding:0; }
.css-1vq4p4l { margin-bottom:0; padding-bottom:0; }
.css-1v3fvcr { font-size:0rem; line-height:1.1; }

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(45px, 0.5fr));
  gap: 1px;
  margin-top: 0;
}
.grid-item {
  border-radius: 8px;
  padding: 5px;
  text-align: center;
  font-size: 15px;
  font-weight: bold;
  color: black;
}
.verde { background-color: #d4edda; }
.amarillo { background-color: #fff3cd; }
.rojo { background-color: #f8d7da; }
.neutro { background-color: #e9ecef; }
</style>
<div class="grid-container">
"""

for row in df_tablero.itertuples():
    clase = "neutro"
    if row.Semaforo == "🟢":
        clase = "verde"
    elif row.Semaforo == "🟡":
        clase = "amarillo"
    elif row.Semaforo == "🔴":
        clase = "rojo"
    html += f'<div class="grid-item {clase}">{row.Remision}<br>{row.Semaforo}</div>'

html += "</div>"

st.markdown(html, unsafe_allow_html=True)
