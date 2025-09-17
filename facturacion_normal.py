import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import timedelta, datetime
import re
import html

# =============================
# --- Google Sheets ---
# =============================
try:
    google_creds = st.secrets["google"]  # Carga los secretos que pusiste en Streamlit Cloud

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
        # Convertir a string, eliminar espacios al inicio/final
        df['Remision'] = df['Remision'].astype(str).str.strip()
        # Eliminar caracteres invisibles/no imprimibles
        df['Remision'] = df['Remision'].apply(lambda x: re.sub(r'[^\x20-\x7E]+', '', x))

    # ==============================
    # --- HTML/CSS para cuadritos ---
    # ==============================
    # Usamos html.escape() para asegurar que todos los caracteres sean válidos
    html_content = '''
    <style>
    .block-container {padding:0rem;}
    .grid-container {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
      gap: 2px;
    }
    .grid-item {
      border-radius: 6px;
      padding: 5px;
      text-align: center;
      font-size: 14px;
      font-weight: bold;
      color: black;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .verde { background-color: #d4edda; border: 1px solid #c3e6cb; }
    .amarillo { background-color: #fff3cd; border: 1px solid #ffeaa7; }
    .rojo { background-color: #f8d7da; border: 1px solid #f5c6cb; }
    .neutro { background-color: #e9ecef; border: 1px solid #dee2e6; }
    .grid-header {
        text-align: center;
        font-weight: bold;
        margin-bottom: 10px;
        color: #2c3e50;
    }
    </style>
    <div class="grid-header">Estado de Remisiones</div>
    <div class="grid-container">
    '''

    # Construir los cuadritos con escape adecuado
    for _, row in df.iterrows():
        rem = row['Remision']
        sem = row['Semaforo']
        
        # Selección de color
        if sem == "🟢":
            color_class = "verde"
        elif sem == "🟡":
            color_class = "amarillo"
        elif sem == "🔴":
            color_class = "rojo"
        else:
            color_class = "neutro"
        
        # Escapar remisión usando html.escape() para evitar problemas de codificación
        rem_safe = html.escape(rem)
        
        html_content += f'<div class="grid-item {color_class}">{rem_safe}<br>{sem}</div>'

    html_content += '</div>'

    st.markdown(html_content, unsafe_allow_html=True)

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

except Exception as e:
    st.error(f"Se produjo un error: {str(e)}")
    st.info("Por favor, verifica la conexión con Google Sheets y los permisos de acceso.")
    