import streamlit as st
import pandas as pd
import sqlite3
from fpdf import FPDF
import base64
from datetime import datetime

# --- CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="Gestión Básquet Pico Truncado", layout="wide")

def init_db():
    conn = sqlite3.connect('torneo.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS equipos 
                 (id INTEGER PRIMARY KEY, nombre TEXT, rama TEXT, categoria TEXT, logo BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS estadisticas 
                 (id INTEGER PRIMARY KEY, partido_id TEXT, jugador TEXT, equipo TEXT, 
                  pts INTEGER, reb INTEGER, rec INTEGER, asist INTEGER, perd INTEGER, faltas INTEGER)''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNCIONES DE SOPORTE ---
def generar_pdf(eq_local, eq_vis, pts_l, pts_v, stats_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="ACTA DIGITAL DE GES DEPORTIVA", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=f"{eq_local} {pts_l} - {pts_v} {eq_vis}", ln=True, align='C')
    pdf.ln(10)
    
    # Tabla de Stats
    pdf.set_font("Arial", 'B', 10)
    cols = ["Jugador", "Equipo", "Pts", "Reb", "Rec", "Ast", "Fal"]
    for col in cols:
        pdf.cell(28, 8, col, 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 10)
    for _, row in stats_df.iterrows():
        pdf.cell(28, 8, str(row['jugador']), 1)
        pdf.cell(28, 8, str(row['equipo']), 1)
        pdf.cell(28, 8, str(row['pts']), 1)
        pdf.cell(28, 8, str(row['reb']), 1)
        pdf.cell(28, 8, str(row['rec']), 1)
        pdf.cell(28, 8, str(row['asist']), 1)
        pdf.cell(28, 8, str(row['faltas']), 1)
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ PRINCIPAL ---
st.sidebar.title("🏀 Club Escuela de Básquet")
menu = st.sidebar.radio("Navegación", ["Inscripción", "Mesa de Control", "Posiciones"])

# 1. INSCRIPCIÓN
if menu == "Inscripción":
    st.header("📝 Registro de Equipos")
    with st.form("registro"):
        nombre = st.text_input("Nombre del Equipo")
        rama = st.selectbox("Rama", ["Masculino", "Femenino"])
        cat = st.selectbox("Categoría", ["U13", "U15", "U17", "Primera"])
        foto = st.file_uploader("Logo del Equipo", type=['png', 'jpg'])
        if st.form_submit_button("Guardar Equipo"):
            conn.execute("INSERT INTO equipos (nombre, rama, categoria) VALUES (?, ?, ?)", (nombre, rama, cat))
            conn.commit()
            st.success(f"Equipo {nombre} registrado con éxito.")

# 2. MESA DE CONTROL
elif menu == "Mesa de Control":
    st.header("⏱️ Tablero de Estadísticas en Vivo")
    
    equipos_db = pd.read_sql("SELECT nombre FROM equipos", conn)
    if equipos_db.empty:
        st.warning("No hay equipos registrados.")
    else:
        c1, c2 = st.columns(2)
        loc = c1.selectbox("Local", equipos_db['nombre'])
        vis = c2.selectbox("Visitante", equipos_db['nombre'])
        
        # Inicializar stats en sesión para no perder datos al recargar
        if 'partido_stats' not in st.session_state:
            st.session_state.partido_stats = []

        def track(jugador, equipo, accion):
            st.session_state.partido_stats.append({
                "jugador": jugador, "equipo": equipo, "accion": accion, "tiempo": datetime.now()
            })

        # Mostrar interfaz de carga para 5 jugadores por equipo (ejemplo)
        for eq in [loc, vis]:
            st.subheader(f"Equipo: {eq}")
            for i in range(1, 6):
                jugador_nombre = f"Jugador #{i}"
                cols = st.columns([2, 1, 1, 1, 1, 1])
                cols[0].write(f"**{jugador_nombre}**")
                if cols[1].button(f"+2", key=f"2p_{eq}_{i}"): track(jugador_nombre, eq, "PTS2")
                if cols[2].button(f"Reb", key=f"rb_{eq}_{i}"): track(jugador_nombre, eq, "REB")
                if cols[3].button(f"Rec", key=f"rc_{eq}_{i}"): track(jugador_nombre, eq, "REC")
                if cols[4].button(f"Ast", key=f"as_{eq}_{i}"): track(jugador_nombre, eq, "AST")
                if cols[5].button(f"F", key=f"fl_{eq}_{i}"): track(jugador_nombre, eq, "FAL")

        # CIERRE DE PARTIDO
        if st.button("🔴 FINALIZAR PARTIDO Y GENERAR ACTA"):
            df_game = pd.DataFrame(st.session_state.partido_stats)
            # Procesar totales
            resumen = []
            for j in df_game['jugador'].unique():
                for e in [loc, vis]:
                    d = df_game[(df_game['jugador']==j) & (df_game['equipo']==e)]
                    if not d.empty:
                        resumen.append({
                            "jugador": j, "equipo": e,
                            "pts": len(d[d['accion']=="PTS2"])*2,
                            "reb": len(d[d['accion']=="REB"]),
                            "rec": len(d[d['accion']=="REC"]),
                            "asist": len(d[d['accion']=="AST"]),
                            "faltas": len(d[d['accion']=="FAL"])
                        })
            
            res_df = pd.DataFrame(resumen)
            pts_l = res_df[res_df['equipo']==loc]['pts'].sum()
            pts_v = res_df[res_df['equipo']==vis]['pts'].sum()
            
            # PDF y WhatsApp
            pdf_bytes = generar_pdf(loc, vis, pts_l, pts_v, res_df)
            st.download_button("📩 Descargar Acta PDF", data=pdf_bytes, file_name="acta.pdf")
            
            msg = f"Final {loc} {pts_l} - {pts_v} {vis}. ¡Acta generada!"
            wa_link = f"https://api.whatsapp.com/send?text={msg.replace(' ', '%20')}"
            st.markdown(f"[📲 Compartir en WhatsApp]({wa_link})")

# 3. POSICIONES
elif menu == "Posiciones":
    st.header("📊 Tabla de Posiciones")
    st.info("Aquí se mostrarán los puntos acumulados (2 por victoria, 1 por derrota).")
    # Lógica de tabla basada en base de datos de partidos finalizados
