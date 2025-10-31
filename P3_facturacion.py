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
def cargar_hoja(nombre_hoja):
    ws = sh.worksheet(nombre_hoja)
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    # Normalizar nombres de columna: minúsculas, sin espacios, sin acentos
    df.columns = [c.strip().lower().replace("í","i") for c in df.columns]
    return df

df_log = cargar_hoja("Logistica")
df_ped = cargar_hoja("Ped Pendientes")
df_rem = cargar_hoja("remisiones_data")

# ==============================
# --- Limpieza ---
# ==============================
df_log['no. pedido'] = df_log['no. pedido'].astype(str).str.strip()
df_ped['no. pedido'] = df_ped['no. pedido'].astype(str).str.strip()
if 'estatus operativo' in df_ped.columns:
    df_ped['estatus operativo'] = df_ped['estatus operativo'].astype(str).str.strip()
else:
    st.error("No se encontró la columna 'Estatus operativo' en Ped Pendientes")

estatus_validos = ["FACTURACION/FISICO EMBARQUES", "EMBARQUES"]
df_ped_filtrado = df_ped[df_ped['estatus operativo'].isin(estatus_validos)]

# Detectar columna Remision
rem_col = None
for col in ['remision','Remision']:
    if col.lower() in df_log.columns:
        rem_col = col.lower()
        break

if rem_col is None:
    st.error("No se encontró la columna Remision en Logistica")
else:
    df_filtrado = df_log.merge(
        df_ped_filtrado[['no. pedido', 'estatus operativo']],
        on="no. pedido",
        how="inner"
    )
    df_filtrado = df_filtrado[df_filtrado[rem_col].notna() & (df_filtrado[rem_col] != "")]

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

df_filtrado['factura'] = df_filtrado.get('factura',"").astype(str).str.strip().fillna("").str.upper()
df_filtrado = df_filtrado[
    (~df_filtrado.get('fecha entrega', pd.Series()).apply(es_fecha_valida)) |
    (df_filtrado['factura'] == "") |
    (df_filtrado['factura'] == "N/A")
].reset_index(drop=True)

# ==============================
# --- Semáforo Tiempo Facturacion ---
# ==============================
if 'tiempo facturacion' in df_filtrado.columns:
    df_filtrado['tiempo facturacion'] = pd.to_timedelta(df_filtrado['tiempo facturacion'], errors='coerce')

def semaforo_facturacion(x):
    if pd.isnull(x):
        return "⚪"
    if x <= pd.Timedelta(hours=3):
        return "🟢"
    elif x <= pd.Timedelta(hours=4):
        return "🟡"
    else:
        return "🔴"

df_filtrado['semaforo'] = df_filtrado['tiempo facturacion'].apply(semaforo_facturacion)

# ==============================
# --- Ordenar por semáforo ---
# ==============================
orden = {"🔴":0, "🟡":1, "🟢":2, "⚪":3}
df_filtrado['orden_semaforo'] = df_filtrado['semaforo'].map(orden)
df_filtrado = df_filtrado.sort_values(by="orden_semaforo").reset_index(drop=True)

# ==============================
# --- KPIs ---
# ==============================
total = len(df_filtrado)
verde_count = (df_filtrado['semaforo']=="🟢").sum()
amarillo_count = (df_filtrado['semaforo']=="🟡").sum()
rojo_count = (df_filtrado['semaforo']=="🔴").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total", total)
col2.metric("🟢 Verde (≤3h)", verde_count)
col3.metric("🟡 Amarillo (3–4h)", amarillo_count)
col4.metric("🔴 Rojo (>4h)", rojo_count)

st.markdown("---")

# ==============================
# --- Detectar remisiones completadas y notificar ---
# ==============================
if 'estado' in df_rem.columns:
    df_rem['estado'] = df_rem['estado'].astype(str).str.strip().str.lower()
    # Detectar columna Remision en remisiones_data
    rem_col_rem = None
    for col in ['remision','Remision']:
        if col.lower() in df_rem.columns:
            rem_col_rem = col.lower()
            break
    if rem_col_rem:
        df_completadas = df_rem[df_rem['estado'] == "completado"]
        if 'notificadas' not in st.session_state:
            st.session_state.notificadas = set()
        nuevas_remisiones = [
            rem for rem in df_completadas[rem_col_rem]
            if rem not in st.session_state.notificadas
        ]
        for rem in nuevas_remisiones:
            st.info(f"🟢 Pedido {rem} listo para facturación")
        st.session_state.notificadas.update(nuevas_remisiones)

# ==============================
# --- Preparar tablero tipo grid ---
# ==============================
df_filtrado['completado'] = False
if rem_col_rem:
    df_filtrado['completado'] = df_filtrado[rem_col].isin(df_completadas[rem_col_rem])

def color_tablero(row):
    if row['completado']:
        return "#cce5ff"  # azul claro
    if row['semaforo']=="🟢":
        return "#d4edda"
    if row['semaforo']=="🟡":
        return "#fff3cd"
    if row['semaforo']=="🔴":
        return "#f8d7da"
    return "#e9ecef"

df_filtrado['color'] = df_filtrado.apply(color_tablero, axis=1)

# ==============================
# --- Renderizar tablero ---
# ==============================
cuadros_por_fila = 22
fila = []

for i, row in df_filtrado.iterrows():
    col_color = row['color']
    completado_label = "⚡ LISTO" if row['completado'] else ""
    
    fila.append((row[rem_col], row['semaforo'], col_color, completado_label))

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
