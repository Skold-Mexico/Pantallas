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
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
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
# --- Procesar columna Tiempo surtimiento y semáforo ---
# ==============================
if 'Tiempo surtimiento' in df.columns:
    # Convertir a timedelta desde formato h:mm:ss
    df['Tiempo surtimiento'] = pd.to_timedelta(df['Tiempo surtimiento'], errors='coerce')

def semaforo_tiempo(x):
    if pd.isnull(x):
        return "⚪"
    # Verde: hasta 2h40m
    if x <= pd.Timedelta(hours=2, minutes=40):
        return "🟢"
    # Amarillo: hasta 3h
    elif x <= pd.Timedelta(hours=3):
        return "🟡"
    # Rojo: más de 3h
    else:
        return "🔴"

df['Semaforo'] = df['Tiempo surtimiento'].apply(semaforo_tiempo) if 'Tiempo surtimiento' in df.columns else "⚪"

# ==============================
# --- Ordenar por semáforo (rojo, amarillo, verde) ---
# ==============================
orden = {"🔴": 0, "🟡": 1, "🟢": 2, "⚪": 3}
df['orden_semaforo'] = df['Semaforo'].map(orden)
df = df.sort_values(by="orden_semaforo").reset_index(drop=True)

# ==============================
# --- KPIs ---
# ==============================
total = len(df)
verde_count = (df['Semaforo'] == "🟢").sum()
amarillo_count = (df['Semaforo'] == "🟡").sum()
rojo_count = (df['Semaforo'] == "🔴").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total", total)
col2.metric("🟢 Verde (≤2h40m)", verde_count)
col3.metric("🟡 Amarillo (2h40–3h)", amarillo_count)
col4.metric("🔴 Rojo (>3h)", rojo_count)


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
import time

# ==============================
# --- Cronómetros por fila ---
# ==============================
st.markdown("## ⏱ Cronómetros por fila")

# Columnas auxiliares en Google Sheets
col_inicio = 16  # HoraInicioP (P)
col_pausa = 17   # HoraPausaP (Q)
col_total = 18   # TiempoTotalP (R)

placeholder = st.empty()  # para actualizar la tabla en vivo

# Loop de actualización en tiempo real (mientras la app esté abierta)
while True:
    for idx, row in df.iterrows():
        fila_hoja = idx + 2  # ajustar según encabezados de la hoja

        # Leer valores actuales de la hoja (por fila)
        valores = ws.row_values(fila_hoja)
        inicio_str = valores[col_inicio-1] if len(valores) >= col_inicio else ""
        pausa_str = valores[col_pausa-1] if len(valores) >= col_pausa else ""
        total_str = valores[col_total-1] if len(valores) >= col_total else ""

        # Parsear valores
        inicio = datetime.strptime(inicio_str, "%d/%m/%Y %H:%M:%S") if inicio_str else None
        pausa = datetime.strptime(pausa_str, "%d/%m/%Y %H:%M:%S") if pausa_str else None
        total = pd.to_timedelta(total_str) if total_str else pd.Timedelta(0)

        # Detectar inicio automático: si hay valor en A y no hay inicio
        if row['Remision'] and not inicio:
            inicio = datetime.now()
            ws.update_cell(fila_hoja, col_inicio, inicio.strftime("%d/%m/%Y %H:%M:%S"))
            ws.update_cell(fila_hoja, col_total, "0:00:00")

        # Detectar pausa automática: si hay valor en D y no estaba pausado
        if row['Fecha de SURTIMIENTO'] and not pausa:
            pausa = datetime.now()
            total += (pausa - inicio)
            inicio = None
            ws.update_cell(fila_hoja, col_pausa, pausa.strftime("%d/%m/%Y %H:%M:%S"))
            ws.update_cell(fila_hoja, col_total, str(total).split(".")[0])

        # Calcular tiempo transcurrido
        tiempo = total + ((datetime.now() - inicio) if inicio else pd.Timedelta(0))
        df.at[idx, 'TiempoP'] = str(tiempo).split(".")[0]

    # Mostrar cronómetros en Streamlit
    with placeholder.container():
        for _, row in df.iterrows():
            st.write(f"{row['Remision']} — Tiempo: {row['TiempoP']}")

    time.sleep(1)  # actualizar cada segundo
