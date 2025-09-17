import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import timedelta, datetime

# =============================
# --- Google Sheets ---
# =============================
credenciales = Credentials.from_service_account_file(
    "secrets.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credenciales)
sh = gc.open_by_key("1UTPaPqfVZ5Z6dmlz9OMPp4W1mMcot9_piz7Bctr5S-I")
worksheet = sh.worksheet("Surtimiento")

data = worksheet.get_all_values()
headers = data[0]
data_recortada = data[1:]
df = pd.DataFrame(data_recortada, columns=headers)
df.columns = [c.strip() for c in df.columns]

if 'Remision' in df.columns:
    df = df[df['Remision'].notna() & (df['Remision'].str.strip() != "")]

if 'Fecha de elab de la remision' in df.columns:
    df['Fecha de elab de la remision'] = pd.to_datetime(df['Fecha de elab de la remision'], errors='coerce')
if 'Fecha de entrega de la remision' in df.columns:
    df['Fecha de entrega de la remision'] = pd.to_datetime(df['Fecha de entrega de la remision'], errors='coerce')

def parse_tiempo(x):
    try:
        h, m, s = map(int, str(x).split(":"))
        return timedelta(hours=h, minutes=m, seconds=s)
    except:
        return pd.NaT

if 'T. surtimiento' in df.columns:
    df['T. surtimiento'] = df['T. surtimiento'].apply(parse_tiempo)

def estado_remision(row):
    fecha = row.get('Fecha de entrega de la remision')
    if pd.isna(fecha) or fecha == "":
        return "Surtimiento"
    try:
        # Parse flexible
        fecha_dt = pd.to_datetime(fecha, dayfirst=True, errors='coerce')
        if pd.notna(fecha_dt):
            return "Facturación"
    except:
        pass
    return "Surtimiento"


df['EstadoRemision'] = df.apply(estado_remision, axis=1)

def semaforo(tiempo):
    if pd.isnull(tiempo):
        return "⚪"
    if tiempo <= timedelta(hours=2, minutes=40):
        return "🟢"
    elif tiempo <= timedelta(hours=3):
        return "🟡"
    else:
        return "🔴"

df['Semaforo'] = df['T. surtimiento'].apply(semaforo) if 'T. surtimiento' in df.columns else "⚪"

def estado_liberacion(x):
    if isinstance(x, str):
        if x.strip().lower() == "liberado":
            return "Liberado"
        elif x.strip().lower() == "detenido":
            return "Detenido"
    return "Pendiente"

df['EstadoLogistica'] = df['Liberacion'].apply(estado_liberacion) if 'Liberacion' in df.columns else "Pendiente"

# =============================
# --- Dashboard ---
# =============================
st.set_page_config(page_title="Remisiones en Surtimiento", layout="wide")
st.title(" ")

# --- KPIs Generales ---
total_rem = len(df)
total_verde = (df['Semaforo'] == "🟢").sum()
total_amarillo = (df['Semaforo'] == "🟡").sum()
total_rojo = (df['Semaforo'] == "🔴").sum()

total_surt = (df['EstadoRemision'] == "Surtimiento").sum()
total_fact = (df['EstadoRemision'] == "Facturación").sum()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("📊 Total Remisiones", total_rem)
col2.metric("🟢 Total Verde", total_verde)
col3.metric("🟡 Total Amarillo", total_amarillo)
col4.metric("🔴 Total Rojo", total_rojo)
col5.metric("🟠 En Surtimiento", total_surt)
col6.metric("🔵 En Facturación", total_fact)

st.markdown("---")

# =============================
# --- Función para generar grid HTML ---
# =============================
def generar_grid(df_sub):
    html = """
    <style>
    .block-container {padding:0rem;}
    .grid-container {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(50px, 1fr));
      gap: 2px;
      margin-top: 0;
    }
    .grid-item {
      border-radius: 6px;
      padding: 5px;
      text-align: center;
      font-size: 12px;
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
    for _, row in df_sub.iterrows():
        rem = row['Remision']
        sem = row['Semaforo']
        if sem == "🟢":
            color_class = "verde"
        elif sem == "🟡":
            color_class = "amarillo"
        elif sem == "🔴":
            color_class = "rojo"
        else:
            color_class = "neutro"
        html += f'<div class="grid-item {color_class}">{rem}<br>{sem}</div>'
    html += "</div>"
    return html

# =============================
# --- Dividir pantalla en izquierda/derecha ---
# =============================
col_surt, col_fact = st.columns(2)

with col_surt:
    st.subheader("🟠 Surtimiento")
    df_surt = df[df['EstadoRemision'] == "Surtimiento"]
    st.markdown(generar_grid(df_surt), unsafe_allow_html=True)

with col_fact:
    st.subheader("🔵 Facturación")
    df_fact = df[df['EstadoRemision'] == "Facturación"]
    st.markdown(generar_grid(df_fact), unsafe_allow_html=True)
