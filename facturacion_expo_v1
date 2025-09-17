import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

credenciales = Credentials.from_service_account_file(
    "secrets.json",  
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)

gc = gspread.authorize(credenciales)
sh = gc.open_by_key("1UTPaPqfVZ5Z6dmlz9OMPp4W1mMcot9_piz7Bctr5S-I")
worksheet = sh.worksheet("Logistica")

data = worksheet.get_all_records()
df = pd.DataFrame(data)

df['Fecha fact'] = pd.to_datetime(df['Fecha fact'], errors='coerce')

def parse_hora(x):
    try:
        return pd.to_timedelta(x + ":00")
    except:
        return pd.NaT

df['Hora factura'] = df['Hora factura'].astype(str).apply(parse_hora)
df['FechaHoraFact'] = df['Fecha fact'] + df['Hora factura'].fillna(pd.Timedelta(0))

df['Fecha de SURTIMIENTO'] = pd.to_datetime(df['Fecha de SURTIMIENTO'], errors='coerce')
df['FechaHoraGuia'] = df['Fecha de SURTIMIENTO']

def calcular_horas(row):
    if pd.isnull(row['FechaHoraFact']) or pd.isnull(row['FechaHoraGuia']):
        return None
    return (row['FechaHoraFact'] - row['FechaHoraGuia']).total_seconds() / 3600

df['HorasTranscurridas'] = df.apply(calcular_horas, axis=1)

def semaforo(horas):
    if pd.isnull(horas):
        return "⚪"
    elif horas < 3:
        return "🟢"
    elif horas < 4:
        return "🟡"
    else:
        return "🔴"

df['Semaforo'] = df['HorasTranscurridas'].apply(semaforo)

st.set_page_config(page_title="Dashboard de logística", layout="wide")
st.title("📦 Dashboard de Pedidos Logística")

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total Pedidos", len(df))
col2.metric("🟢 Pedidos en Verde", (df['Semaforo'] == "🟢").sum())
col3.metric("🟡 Pedidos en Amarillo", (df['Semaforo'] == "🟡").sum())
col4.metric("🔴 Pedidos en Rojo", (df['Semaforo'] == "🔴").sum())

st.markdown("---")

def color_filas(row):
    if row["Semaforo"] == "🟢":
        return ["background-color: #d4edda"] * len(row)  # Verde claro
    elif row["Semaforo"] == "🟡":
        return ["background-color: #fff3cd"] * len(row)  # Amarillo claro
    elif row["Semaforo"] == "🔴":
        return ["background-color: #f8d7da"] * len(row)  # Rojo claro
    else:
        return [""] * len(row)

st.subheader("📝 Tabla de Pedidos")
df_tabla = df[['Pedido', 'Factura', 'Cliente', 'FechaHoraGuia', 'FechaHoraFact', 'HorasTranscurridas', 'Semaforo']]

st.dataframe(
    df_tabla.style.apply(color_filas, axis=1),
    use_container_width=True
)

st.markdown("---")

# --- Gráfico ---
st.subheader("📊 Distribución por Semáforo")
semaforo_count = df['Semaforo'].value_counts().reset_index()
semaforo_count.columns = ["Semaforo", "Cantidad"]

fig = px.bar(
    semaforo_count,
    x="Semaforo",
    y="Cantidad",
    text="Cantidad",
    color="Semaforo",
    color_discrete_map={
        "🟢": "green",
        "🟡": "yellow",
        "🔴": "red",
        "⚪": "lightgray"
    }
)
fig.update_traces(textposition="outside")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- Filtro por Cliente ---
st.subheader("🔍 Filtrar Pedidos por Cliente")
filtro_cliente = st.text_input("Escribe el nombre del cliente:")

if filtro_cliente:
    df_filtrado = df_tabla[df_tabla['Cliente'].str.contains(filtro_cliente, case=False, na=False)]
    st.dataframe(df_filtrado, use_container_width=True)