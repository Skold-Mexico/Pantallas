import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import timedelta

# =============================
# --- Autenticación Google Sheets ---
# =============================
credenciales = Credentials.from_service_account_file(
    "secrets.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credenciales)
sh = gc.open_by_key("1UTPaPqfVZ5Z6dmlz9OMPp4W1mMcot9_piz7Bctr5S-I")
worksheet = sh.worksheet("Surtimiento")

# =============================
# --- Cargar datos ---
# =============================
data = worksheet.get_all_values()

# =============================
# --- Usar encabezados de la hoja ---
# =============================
headers = data[0]  # primera fila como headers
data_recortada = data[1:]  # resto de filas
df = pd.DataFrame(data_recortada, columns=headers)

# =============================
# --- Limpiar nombres de columnas ---
# =============================
df.columns = [c.strip() for c in df.columns]
# =============================
# --- Filtrar filas sin Remision ---
# =============================
if 'Remision' in df.columns:
    df = df[df['Remision'].notna() & (df['Remision'].str.strip() != "")]

# =============================
# --- Conversión de columnas ---
# =============================
if 'Fecha de elab de la remision' in df.columns:
    df['Fecha de elab de la remision'] = pd.to_datetime(df['Fecha de elab de la remision'], errors='coerce')
if 'Fecha de entrega de la remision' in df.columns:
    df['Fecha de entrega de la remision'] = pd.to_datetime(df['Fecha de entrega de la remision'], errors='coerce')

# Parsear T. surtimiento como timedelta
def parse_tiempo(x):
    try:
        # Separar horas, minutos y segundos
        h, m, s = map(int, str(x).split(":"))
        return timedelta(hours=h, minutes=m, seconds=s)
    except:
        return pd.NaT


if 'T. surtimiento' in df.columns:
    df['T. surtimiento'] = df['T. surtimiento'].apply(parse_tiempo)

# =============================
# --- Clasificación facturación vs surtimiento ---
# =============================
from datetime import datetime

def estado_remision(row):
    fecha = str(row.get('Fecha de entrega de la remision', '')).strip()
    if not fecha:  # vacío
        return "Surtimiento"
    
    # Intentar parsear fecha con formatos válidos
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            datetime.strptime(fecha, fmt)
            return "Facturación"
        except ValueError:
            continue
    
    # Si no coincide con los formatos, sigue en Surtimiento
    return "Surtimiento"




df['EstadoRemision'] = df.apply(estado_remision, axis=1)

# =============================
# --- Semáforo ---
# =============================
def semaforo(tiempo):
    if pd.isnull(tiempo):
        return "⚪"
    if tiempo <= timedelta(hours=2, minutes=40):
        return "🟢"
    elif tiempo <= timedelta(hours=3):
        return "🟡"
    else:
        return "🔴"

if 'T. surtimiento' in df.columns:
    df['Semaforo'] = df['T. surtimiento'].apply(semaforo)
else:
    df['Semaforo'] = "⚪"

# =============================
# --- Estado de Liberación ---
# =============================
def estado_liberacion(x):
    if isinstance(x, str):
        if x.strip().lower() == "liberado":
            return "Liberado"
        elif x.strip().lower() == "detenido":
            return "Detenido"
    return "Pendiente"

if 'Liberacion' in df.columns:
    df['EstadoLogistica'] = df['Liberacion'].apply(estado_liberacion)
else:
    df['EstadoLogistica'] = "Pendiente"

# =============================
# --- Dashboard ---
# =============================
st.set_page_config(page_title="Remisiones en surtimiento", layout="wide")
st.title("📦 Remisiones en surtimiento")

# --- Métricas principales ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total Remisiones", len(df))
col2.metric("🟢 En Verde", (df['Semaforo'] == "🟢").sum())
col3.metric("🟡 En Amarillo", (df['Semaforo'] == "🟡").sum())
col4.metric("🔴 En Rojo", (df['Semaforo'] == "🔴").sum())

# --- Métricas extra ---
col5, col6, col7 = st.columns(3)
col5.metric("📝 En Surtimiento", (df['EstadoRemision'] == "Surtimiento").sum())
col6.metric("📑 En Facturación", (df['EstadoRemision'] == "Facturación").sum())
col7.metric("⚙️ Liberadas", (df['EstadoLogistica'] == "Liberado").sum())

col8, col9 = st.columns(2)
col8.metric("⛔ Detenidas", (df['EstadoLogistica'] == "Detenido").sum())
col9.metric("⏳ Pendientes", (df['EstadoLogistica'] == "Pendiente").sum())

st.markdown("---")

# =============================
# --- Tablas separadas ---
# =============================
def color_filas(row):
    if row["Semaforo"] == "🟢":
        return ["background-color: #d4edda"] * len(row)
    elif row["Semaforo"] == "🟡":
        return ["background-color: #fff3cd"] * len(row)
    elif row["Semaforo"] == "🔴":
        return ["background-color: #f8d7da"] * len(row)
    else:
        return [""] * len(row)

st.subheader("📝 Remisiones en Surtimiento")
cols_surt = ['Remision', 'Cliente', 'Nombre', 'Pedido', 'Fecha de elab de la remision',
             'T. surtimiento', 'Hora de la entrega de la remision', 'Fecha Surtido', 'Hora Surtido',
             'Almacenista', 'Tipo Prod (de la remision)', 'Comentarios', 'Liberacion', 'Semaforo', 'EstadoLogistica']
cols_surt = [c for c in cols_surt if c in df.columns]
df_surt = df[df['EstadoRemision'] == "Surtimiento"]
st.dataframe(df_surt[cols_surt].style.apply(color_filas, axis=1), use_container_width=True)

st.subheader("📑 Remisiones en Facturación")
cols_fact = ['Remision', 'Cliente', 'Nombre', 'Pedido', 'Fecha de elab de la remision',
             'Fecha de entrega de la remision', 'Hora de la entrega de la remision', 'T. surtimiento',
             'Fecha Surtido', 'Hora Surtido', 'Almacenista', 'Tipo Prod (de la remision)', 'Comentarios', 'Liberacion',
             'Semaforo', 'EstadoLogistica']
cols_fact = [c for c in cols_fact if c in df.columns]
df_fact = df[df['EstadoRemision'] == "Facturación"]
st.dataframe(df_fact[cols_fact].style.apply(color_filas, axis=1), use_container_width=True)

st.markdown("---")

# =============================
# --- Gráficos ---
# =============================
st.subheader("📊 Distribución por Semáforo")
semaforo_count = df['Semaforo'].value_counts().reset_index()
semaforo_count.columns = ["Semaforo", "Cantidad"]

fig1 = px.bar(
    semaforo_count,
    x="Semaforo", y="Cantidad", text="Cantidad", color="Semaforo",
    color_discrete_map={"🟢": "green", "🟡": "yellow", "🔴": "red", "⚪": "lightgray"}
)
fig1.update_traces(textposition="outside")
st.plotly_chart(fig1, use_container_width=True)

colg1, colg2 = st.columns(2)

with colg1:
    st.subheader("📊 Estado de Remisiones")
    estado_count = df['EstadoRemision'].value_counts().reset_index()
    estado_count.columns = ["Estado", "Cantidad"]
    fig2 = px.pie(estado_count, names="Estado", values="Cantidad", hole=0.4, color="Estado",
                  color_discrete_map={"Surtimiento": "orange", "Facturación": "blue"})
    st.plotly_chart(fig2, use_container_width=True)

with colg2:
    st.subheader("📦 Estado Logístico")
    log_count = df['EstadoLogistica'].value_counts().reset_index()
    log_count.columns = ["Estado", "Cantidad"]
    fig3 = px.pie(log_count, names="Estado", values="Cantidad", hole=0.4, color="Estado",
                  color_discrete_map={"Liberado": "green", "Detenido": "red", "Pendiente": "gray"})
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# =============================
# --- Filtro por Cliente ---
# =============================
cliente_col = 'Nombre' if 'Nombre' in df.columns else df.columns[1]
st.subheader("🔍 Filtrar Remisiones por Cliente")
clientes_unicos = df[cliente_col].dropna().unique()
filtro_cliente = st.selectbox("Selecciona un cliente:", [""] + list(clientes_unicos))

if filtro_cliente:
    df_filtrado = df[df[cliente_col] == filtro_cliente]
    cols_filter = ['Remision', 'Nombre', 'Pedido', 'EstadoRemision', 'EstadoLogistica', 'T. surtimiento', 'Semaforo']
    cols_filter = [c for c in cols_filter if c in df.columns]
    st.dataframe(df_filtrado[cols_filter], use_container_width=True)
