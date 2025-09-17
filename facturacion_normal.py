import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import timedelta, datetime
import re

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

    # Limpiar columna Remision
    if 'Remision' in df.columns:
        df = df[df['Remision'].notna() & (df['Remision'].str.strip() != "")]
        df['Remision'] = df['Remision'].astype(str).str.strip()
        df['Remision'] = df['Remision'].apply(lambda x: re.sub(r'[^\x20-\x7E]+', '', x))

    # Parsear fechas mixtas
    def parse_fecha(fecha_str):
        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(fecha_str, fmt)
            except:
                continue
        return pd.NaT

    if 'Fecha de entrega de la remision' in df.columns:
        df['Fecha de entrega de la remision'] = df['Fecha de entrega de la remision'].astype(str).str.strip()
        df['Fecha de entrega de la remision'] = df['Fecha de entrega de la remision'].apply(parse_fecha)

    # Tiempo de surtimiento
    def parse_tiempo(x):
        try:
            h, m, s = map(int, str(x).split(":"))
            return timedelta(hours=h, minutes=m, seconds=s)
        except:
            return pd.NaT

    if 'T. surtimiento' in df.columns:
        df['T. surtimiento'] = df['T. surtimiento'].apply(parse_tiempo)

    # Estado remision
    df['EstadoRemision'] = df['Fecha de entrega de la remision'].apply(
        lambda x: "Facturación" if pd.notnull(x) else "Surtimiento"
    )

    # Semáforo
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

    # Estado logística
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
    total = len(df)
    surtimiento_count = (df['EstadoRemision'] == "Surtimiento").sum()
    facturacion_count = (df['EstadoRemision'] == "Facturación").sum()
    verde_count = (df['Semaforo'] == "🟢").sum()
    amarillo_count = (df['Semaforo'] == "🟡").sum()
    rojo_count = (df['Semaforo'] == "🔴").sum()

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("📊 Total Remisiones", total)
    col2.metric("📌 Surtimiento", surtimiento_count)
    col3.metric("📌 Facturación", facturacion_count)
    col4.metric("🟢 Verde", verde_count)
    col5.metric("🟡 Amarillo", amarillo_count)
    col6.metric("🔴 Rojo", rojo_count)

    st.markdown("---")
    st.subheader("Estado de Remisiones")

    # -----------------------------
    # Mostrar los cuadritos en cuadrícula
    # -----------------------------
    # Número de cuadritos por fila
    cuadros_por_fila = 6
    fila = []

    for i, row in df.iterrows():
        if row['EstadoRemision'] == "Surtimiento":
            color = "#007bff"  # azul fuerte
        else:
            color = (
                "#d4edda" if row['Semaforo'] == "🟢" else
                "#fff3cd" if row['Semaforo'] == "🟡" else
                "#f8d7da" if row['Semaforo'] == "🔴" else "#e9ecef"
            )

        # Crear columna temporal para cada cuadro
        fila.append((row['Remision'], row['Semaforo'], color))

        # Cuando la fila llega a cuadros_por_fila o es el último elemento, se imprime
        if len(fila) == cuadros_por_fila or i == df.index[-1]:
            cols = st.columns(len(fila))
            for c, (rem, sem, col_color) in zip(cols, fila):
                c.markdown(
                    f'<div style="background-color:{col_color}; border-radius:6px; padding:10px; text-align:center; margin-bottom:5px; color:black;">'
                    f'<strong>{rem}</strong><br>{sem}</div>',
                    unsafe_allow_html=True
                )
            fila = []  # Reiniciar fila

    # Leyenda
    st.markdown("---")
    st.subheader("Leyenda de Estados")
    lc1, lc2, lc3, lc4, lc5 = st.columns(5)
    with lc1:
        st.markdown("🟢 **Verde**: Tiempo ≤ 2h 40m")
    with lc2:
        st.markdown("🟡 **Amarillo**: Tiempo ≤ 3h")
    with lc3:
        st.markdown("🔴 **Rojo**: Tiempo > 3h")
    with lc4:
        st.markdown("⚪ **Neutro**: Sin dato")
    with lc5:
        st.markdown("🔵 **Surtimiento**: Sin fecha de entrega")

except Exception as e:
    st.error(f"Se produjo un error: {str(e)}")
    st.info("Por favor, verifica la conexión con Google Sheets y los permisos de acceso.")

