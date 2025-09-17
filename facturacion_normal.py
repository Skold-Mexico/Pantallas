import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import timedelta, datetime
import re

# =============================
# --- Google Sheets ---
# =============================
try:
    google_creds = st.secrets["google"]

    credenciales = Credentials.from_service_account_info(
        google_creds,
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
        fecha = str(row.get('Fecha de entrega de la remision', '')).strip()
        if not fecha:
            return "Surtimiento"
        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                datetime.strptime(fecha, fmt)
                return "Facturación"
            except ValueError:
                continue
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
    st.title("📦 Remisiones en Surtimiento")

    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Total Remisiones", len(df))
    col2.metric("🟢 En Verde", (df['Semaforo'] == "🟢").sum())
    col3.metric("🟡 En Amarillo", (df['Semaforo'] == "🟡").sum())
    col4.metric("🔴 En Rojo", (df['Semaforo'] == "🔴").sum())

    st.markdown("---")

    # ==============================
    # --- Limpiar columna Remision ---
    # ==============================
    if 'Remision' in df.columns:
        df['Remision'] = df['Remision'].astype(str).str.strip()
        df['Remision'] = df['Remision'].apply(lambda x: re.sub(r'[^\x20-\x7E]+', '', x))

    # ==============================
    # --- Visualización usando columnas de Streamlit ---
    # ==============================
    st.subheader("Estado de Remisiones")
    
    # Definir el número de columnas para la cuadrícula
    num_columns = 8
    columns = st.columns(num_columns)
    
    # Función para obtener el color según el semáforo
    def get_color_class(semaforo):
        if semaforo == "🟢":
            return "background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 6px; padding: 10px; text-align: center;"
        elif semaforo == "🟡":
            return "background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; padding: 10px; text-align: center;"
        elif semaforo == "🔴":
            return "background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 6px; padding: 10px; text-align: center;"
        else:
            return "background-color: #e9ecef; border: 1px solid #dee2e6; border-radius: 6px; padding: 10px; text-align: center;"
    
    # Mostrar las remisiones en una cuadrícula
    for i, (_, row) in enumerate(df.iterrows()):
        rem = row['Remision']
        sem = row['Semaforo']
        
        # Determinar en qué columna colocar este elemento
        col_index = i % num_columns
        
        # Usar markdown con estilo en lugar de HTML crudo
        with columns[col_index]:
            st.markdown(
                f'<div style="{get_color_class(sem)}">'
                f'<strong>{rem}</strong><br>{sem}'
                f'</div>',
                unsafe_allow_html=True
            )

    # Añadir información adicional
    st.markdown("---")
    st.subheader("Leyenda de Estados")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("🟢 **Verde**: Tiempo ≤ 2h 40m")
    with col2:
        st.markdown("🟡 **Amarillo**: Tiempo ≤ 3h")
    with col3:
        st.markdown("🔴 **Rojo**: Tiempo > 3h")
    with col4:
        st.markdown("⚪ **Neutro**: Sin dato")

    # También mostrar los datos en forma de tabla como alternativa
    st.markdown("---")
    st.subheader("Vista detallada")
    st.dataframe(df[['Remision', 'Semaforo', 'T. surtimiento', 'EstadoRemision']].head(20))

except Exception as e:
    st.error(f"Se produjo un error: {str(e)}")
    st.info("Por favor, verifica la conexión con Google Sheets y los permisos de acceso.")