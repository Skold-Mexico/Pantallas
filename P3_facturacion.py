import streamlit as st
import pandas as pd
from datetime import timedelta
import gspread
from google.oauth2.service_account import Credentials
import json

# ==============================
# --- Configuración página ---
# ==============================
st.set_page_config(page_title="Pantalla Facturación", layout="wide")
st.markdown("<div style='margin-top:-0.5rem;'></div>", unsafe_allow_html=True)

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
# --- Cargar hojas ---
# ==============================
ws_log = sh.worksheet("Logistica")
data_log = ws_log.get_all_records()
df_log = pd.DataFrame(data_log)

ws_ped = sh.worksheet("Ped Pendientes")
data_ped = ws_ped.get_all_values()
data_ped = [row[:6] for row in data_ped]
headers = data_ped[0]
df_ped = pd.DataFrame(data_ped[1:], columns=headers)

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
# --- Filtrado Fecha Entrega y Factura ---
# ==============================
def es_fecha_valida(valor):
    if not valor or str(valor).strip() == "":
        return False
    try:
        pd.to_datetime(valor, dayfirst=True)
        return True
    except:
        return False

df_filtrado['Factura'] = df_filtrado['Factura'].astype(str).str.strip().fillna("").str.upper()

df_filtrado = df_filtrado[
    (~df_filtrado['Fecha Entrega'].apply(es_fecha_valida)) |
    (df_filtrado['Factura'] == "") |
    (df_filtrado['Factura'] == "N/A")
].reset_index(drop=True)

# ==============================
# --- Semáforo Tiempo Facturacion ---
# ==============================
if 'Tiempo facturacion' in df_filtrado.columns:
    df_filtrado['Tiempo facturacion'] = pd.to_timedelta(df_filtrado['Tiempo facturacion'], errors='coerce')

def semaforo_facturacion(x):
    if pd.isnull(x):
        return "⚪"  # color gris claro para datos faltantes
    if x <= pd.Timedelta(hours=3):
        return "🟢"
    elif x <= pd.Timedelta(hours=4):
        return "🟡"
    else:
        return "🔴"

df_filtrado['Semaforo'] = df_filtrado['Tiempo facturacion'].apply(semaforo_facturacion)

# ==============================
# --- Ordenar por semáforo (rojo, amarillo, verde, neutro) ---
# ==============================
orden = {"🔴": 0, "🟡": 1, "🟢": 2, "⚪": 3}
df_filtrado['orden_semaforo'] = df_filtrado['Semaforo'].map(orden)
df_filtrado = df_filtrado.sort_values(by="orden_semaforo").reset_index(drop=True)

# ==============================
# --- KPIs ---
# ==============================
total = len(df_filtrado)
verde_count = (df_filtrado['Semaforo'] == "🟢").sum()
amarillo_count = (df_filtrado['Semaforo'] == "🟡").sum()
rojo_count = (df_filtrado['Semaforo'] == "🔴").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total", total)
col2.metric("🟢 Verde (≤3h)", verde_count)
col3.metric("🟡 Amarillo (3–4h)", amarillo_count)
col4.metric("🔴 Rojo (>4h)", rojo_count)

st.markdown("---")

# ==============================
# --- Detectar remisiones completadas ---
# ==============================
ws_rem = sh.worksheet("remisiones_data")
data_rem = ws_rem.get_all_records()
df_rem = pd.DataFrame(data_rem)

df_rem['estado'] = df_rem['estado'].astype(str).str.strip().str.lower()
df_completadas = df_rem[df_rem['estado'] == "completado"]

if 'notificadas' not in st.session_state:
    st.session_state.notificadas = set()

nuevas_remisiones = [
    rem for rem in df_completadas['Remision']
    if rem not in st.session_state.notificadas
]

for rem in nuevas_remisiones:
    st.info(f"🟢 Pedido {rem} listo para facturación")

st.session_state.notificadas.update(nuevas_remisiones)

# ==============================
# --- Preparar tablero tipo grid con remisiones completadas ---
# ==============================
df_filtrado['Completado'] = df_filtrado['Remision'].isin(df_completadas['Remision'])

def color_tablero(row):
    if row['Completado']:
        return "#cce5ff"  # azul claro para remisiones completadas
    if row['Semaforo'] == "🟢":
        return "#d4edda"
    if row['Semaforo'] == "🟡":
        return "#fff3cd"
    if row['Semaforo'] == "🔴":
        return "#f8d7da"
    return "#e9ecef"

df_filtrado['color'] = df_filtrado.apply(color_tablero, axis=1)

# ==============================
# --- Renderizar tablero con icono de completado ---
# ==============================
cuadros_por_fila = 22
fila = []

for i, row in df_filtrado.iterrows():
    col_color = row['color']
    completado_label = "⚡ LISTO" if row['Completado'] else ""
    
    fila.append((row['Remision'], row['Semaforo'], col_color, completado_label))

    if len(fila) == cuadros_por_fila or i == df_filtrado.index[-1]:
        cols = st.columns(len(fila))
        for c, (rem, sem, color_fila, label) in zip(cols, fila):
            c.markdown(
                f"""
                <div style="
                    background-color:{color_fila};
                    border-radius:6px;
                    padding:6px;
                    text-align:center;
                    margin:2px;
                    color:black;
                    font-size:12px;
                    white-space:nowrap;
                ">
                    <strong>{rem}</strong><br>
                    {sem}<br>
                    <span style="font-size:10px; color:#004085;">{label}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        fila = []
