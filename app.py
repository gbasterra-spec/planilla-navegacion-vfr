import streamlit as st
import math
from io import BytesIO
import json
import os  # <--- Para verificar si el archivo existe en el disco

# --- IMPORTACIONES PARA REPORTLAB ---
import reportlab.lib.pagesizes as pdf_sizes
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape

# RUTA DEL ARCHIVO DE BASE DE DATOS LOCAL
DB_FILE = "waypoints_db.json"

AERODROMOS_INICIALES = {
    "SADM": {"nombre": "Morón", "lat": -34.6761, "lon": -58.6436, "frec": "118.5"},
    "SAEZ": {"nombre": "Ezeiza Intl", "lat": -34.8222, "lon": -58.5358, "frec": "118.6"},
    "SADZ": {"nombre": "Matanza", "lat": -34.7292, "lon": -58.6017, "frec": "123.4"},
    "SADF": {"nombre": "San Fernando", "lat": -34.4514, "lon": -58.5894, "frec": "120.4"},
    "SADP": {"nombre": "El Palomar", "lat": -34.6097, "lon": -58.6047, "frec": "119.9"},
    "SABE": {"nombre": "Aeroparque", "lat": -34.5589, "lon": -58.4156, "frec": "119.4"},
    "LA_PLATA": {"nombre": "La Plata", "lat": -34.9722, "lon": -57.8944, "frec": "118.9"},
    "VOR_POBRES": {"nombre": "VOR de los Pobres (Brandsen)", "lat": -35.1689, "lon": -58.2344, "frec": "125.1"},
    "PUENTE_HIERRO": {"nombre": "Puente de Hierro (R205)", "lat": -35.6514, "lon": -59.5647, "frec": "123.5"},
    "LONGCHAMPS": {"nombre": "Punto Longchamps (Pasaje)", "lat": -34.8436, "lon": -58.3858, "frec": "125.1"},
    "SAN_VICENTE": {"nombre": "Punto San Vicente", "lat": -35.0253, "lon": -58.4231, "frec": "125.1"},
    "ROTONDA_CAÑUELAS": {"nombre": "Cruce Rutas 3 y 205", "lat": -35.0564, "lon": -58.7194, "frec": "123.5"},
    "SAZQ": {"nombre": "Cañuelas", "lat": -35.0111, "lon": -58.7417, "frec": "123.5"},
    "SADK": {"nombre": "Chascomús", "lat": -35.5661, "lon": -58.0531, "frec": "123.5"},
    "SADQ": {"nombre": "Dolores", "lat": -36.3214, "lon": -57.7214, "frec": "123.5"}
}

# LÓGICA DE PERSISTENCIA: Cargar del archivo o crearlo si no existe
if "aerodromos" not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                st.session_state.aerodromos = json.load(f)
        except Exception:
            st.session_state.aerodromos = AERODROMOS_INICIALES.copy()
    else:
        # Si no existe, creamos el archivo JSON por primera vez
        st.session_state.aerodromos = AERODROMOS_INICIALES.copy()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(AERODROMOS_INICIALES, f, indent=4, ensure_ascii=False)

AERODROMOS = st.session_state.aerodromos

AVIONES = {
    "Cessna 150": {"tas": 70, "lph": 21.0},
    "Cessna 172": {"tas": 110, "lph": 32.0},
    "Piper Archer": {"tas": 120, "lph": 34.0}
}

# --- FUNCIONES DE CÁLCULO ---
def calcular_distancia_y_rumbo(lat1, lon1, lat2, lon2):
    R = 3440.065
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distancia = R * c
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    tc = (math.degrees(math.atan2(y, x)) + 360) % 360
    return round(distancia, 1), round(tc, 0)

def resolver_triangulo_vientos(mc, tas, dir_viento, vel_viento):
    if vel_viento == 0:
        return 0.0, tas
    mc_rad = math.radians(mc)
    dir_v_rad = math.radians(dir_viento)
    angulo_viento = dir_v_rad - mc_rad
    val_sin = (vel_viento * math.sin(angulo_viento)) / tas
    val_sin = max(-1.0, min(1.0, val_sin))
    wca_rad = math.asin(val_sin)
    wca = math.degrees(wca_rad)
    gs = (tas * math.cos(wca_rad)) - (vel_viento * math.cos(angulo_viento))
    return round(wca, 0), round(gs, 1)

def generar_pdf_a4_apaisado(tabla_datos, dist_t, tiempo_t, comb_t, avion, var, v_dir, v_vel):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(pdf_sizes.A4), rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('PdfTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'), alignment=1, spaceAfter=12)
    normal_style = ParagraphStyle('PdfNormal', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.black)
    header_style = ParagraphStyle('PdfHeader', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)
    cell_style = ParagraphStyle('PdfCell', parent=styles['Normal'], fontSize=8.5, leading=11, alignment=1)
    
    story = []
    story.append(Paragraph("PLANILLA DE NAVEGACIÓN OPERATIVA - OPERACIONES VFR", title_style))
    
    meta_data = [
        [Paragraph(f"<b>Aeronave:</b> {avion}", normal_style), Paragraph(f"<b>Viento Seteado:</b> {v_dir}° / {v_vel} KT", normal_style)],
        [Paragraph(f"<b>Declinación Magnética (VAR):</b> {var}°W", normal_style), Paragraph(f"<b>Unidades Combustible:</b> Litros (L / LPH)", normal_style)]
    ]
    meta_table = Table(meta_data, colWidths=[380, 380])
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    headers = [
        Paragraph("<b>Tramo</b>", header_style), Paragraph("<b>Ruta</b>", header_style), Paragraph("<b>Frecuencias</b>", header_style),
        Paragraph("<b>Altitud</b>", header_style), Paragraph("<b>TC</b>", header_style), Paragraph("<b>MC</b>", header_style),
        Paragraph("<b>WCA</b>", header_style), Paragraph("<b>MH</b>", header_style), Paragraph("<b>GS (KT)</b>", header_style),
        Paragraph("<b>Dist. (NM)</b>", header_style), Paragraph("<b>Tiempo</b>", header_style), Paragraph("<b>Comb.</b>", header_style),
    ]
    pdf_rows = [headers]
    for row in tabla_datos:
        pdf_rows.append([
            Paragraph(row["Tramo"], cell_style), Paragraph(row["Ruta"], cell_style), Paragraph(row["Frecuencias"], cell_style),
            Paragraph(row["Altitud"], cell_style), Paragraph(row["True Course (TC)"], cell_style), Paragraph(row["Magnetic Course (MC)"], cell_style),
            Paragraph(row["WCA"], cell_style), Paragraph(f"<b>{row['Magnetic Heading (MH)']}</b>", cell_style), Paragraph(row["GS (KT)"], cell_style),
            Paragraph(row["Distancia (NM)"], cell_style), Paragraph(row["Tiempo"], cell_style), Paragraph(row["Combustible"], cell_style),
        ])
    total_style = ParagraphStyle('PdfTotal', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', alignment=1)
    pdf_rows.append([
        Paragraph("TOTAL", total_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style),
        Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style),
        Paragraph(f"<b>{round(dist_t, 1)} NM</b>", total_style), Paragraph(f"<b>{tiempo_t} min</b>", total_style), Paragraph(f"<b>{round(comb_t, 1)} L</b>", total_style),
    ])
    tabla_tramos = Table(pdf_rows, colWidths=[45, 95, 100, 55, 35, 35, 35, 40, 45, 55, 55, 65])
    tabla_tramos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tabla_tramos)
    doc.build(story)
    buffer.seek(0)
    return buffer

# 5. CONFIGURACIÓN DE STREAMLIT
st.set_page_config(page_title="Planilla de Navegación", page_icon="📋", layout="wide")

st.title("📋 Planilla de Navegación Operativa (Cálculo Magnético)")
st.write("Planilla corregida por Declinación Magnética e Intensidad de Viento manual para operaciones de vuelo.")
st.markdown("---")

lista_oaci = list(AERODROMOS.keys())

p_ini = lista_oaci[0] if lista_oaci else ""
p_dest_def = lista_oaci[1] if len(lista_oaci) > 1 else p_ini

if "ruta" not in st.session_state or not all(p in lista_oaci for p in st.session_state.ruta):
    st.session_state.ruta = [p_ini, p_dest_def]
if "altitudes" not in st.session_state:
    st.session_state.altitudes = [2500]

# --- SIDEBAR DE CONFIGURACIÓN GENERAL ---
st.sidebar.header("⚙️ Configuración General")
avión_sel = st.sidebar.selectbox("Aeronave", list(AVIONES.keys()))
tas = AVIONES[avión_sel]["tas"]
lph = AVIONES[avión_sel]["lph"]

st.sidebar.subheader("🧭 Declinación Magnética (VAR)")
var_mag = st.sidebar.slider("Variación/Declinación (°W)", 0, 20, 8, step=1)

st.sidebar.subheader("💨 Datos del Viento")
dir_viento = st.sidebar.slider("Dirección del Viento (°)", 0, 360, 0, step=10)
vel_viento = st.sidebar.slider("Intensidad (KT)", 0, 40, 0, step=1)

# --- BOTÓN GENERAL PARA AÑADIR TRAMO ---
if st.button("➕ Añadir Tramo al Final") and len(st.session_state.ruta) < 11:
    st.session_state.ruta.append(lista_oaci[0] if lista_oaci else "")
    st.session_state.altitudes.append(2500)
    st.rerun()

st.write("")

if not lista_oaci:
    st.warning("No hay waypoints en la base de datos. Por favor ve a la página de Waypoints y agrega uno.")
else:
    # Encabezados de la grilla
    cols_header = st.columns([0.8, 1.8, 1.8, 1.1, 1.1, 1.1, 1.0, 1.0, 0.5])
    cols_header[0].markdown("**Tramo**")
    cols_header[1].markdown("**Origen**")
    cols_header[2].markdown("**Destino**")
    cols_header[3].markdown("**Altitud (FT)**")
    cols_header[4].markdown("**Curso (MC)**")
    cols_header[5].markdown("**Rumbo (MH)**")
    cols_header[6].markdown("**Tiempo**")
    cols_header[7].markdown("**Comb. (L)**")
    cols_header[8].markdown("**Acción**")

    tabla_navegacion = []
    total_distancia = 0.0
    total_tiempo = 0
    total_combustible = 0.0

    num_tramos = len(st.session_state.ruta) - 1

    for i in range(num_tramos):
        cols = st.columns([0.8, 1.8, 1.8, 1.1, 1.1, 1.1, 1.0, 1.0, 0.5])
        cols[0].write(f"**# {i+1}**")
        
        # Origen
        if i == 0:
            def cambiar_origen_inicial():
                st.session_state.ruta[0] = st.session_state.origen_raiz
            origen_sel = cols[1].selectbox(
                f"Origen inicial", lista_oaci, index=lista_oaci.index(st.session_state.ruta[0]) if st.session_state.ruta[0] in lista_oaci else 0,
                key="origen_raiz", on_change=cambiar_origen_inicial, label_visibility="collapsed"
            )
        else:
            origen_sel = st.session_state.ruta[i]
            cols[1].info(f"📍 {origen_sel} ({AERODROMOS[origen_sel]['nombre']})")
            
        # Destino
        def cambiar_destino(indice=i):
            st.session_state.ruta[indice+1] = st.session_state[f"dest_sel_{indice}"]
        destino_sel = cols[2].selectbox(
            f"Destino pierna {i+1}", lista_oaci, index=lista_oaci.index(st.session_state.ruta[i+1]) if st.session_state.ruta[i+1] in lista_oaci else 0,
            key=f"dest_sel_{i}", on_change=cambiar_destino, label_visibility="collapsed"
        )
        
        # Altitud
        def cambiar_altitud(indice=i):
            st.session_state.altitudes[indice] = st.session_state[f"alt_sel_{indice}"]
        altitud_sel = cols[3].number_input(
            f"Altitud pierna {i+1}", value=st.session_state.altitudes[i], step=500, 
            key=f"alt_sel_{i}", on_change=cambiar_altitud, label_visibility="collapsed"
        )
        
        p_orig = AERODROMOS[origen_sel]
        p_dest = AERODROMOS[destino_sel]
        
        if origen_sel == destino_sel:
            cols[4].write("❌ Revisa")
            cols[5].write("-")
            cols[6].write("-")
            cols[7].write("-")
        else:
            distancia, tc = calcular_distancia_y_rumbo(p_orig["lat"], p_orig["lon"], p_dest["lat"], p_dest["lon"])
            mc = int((tc + var_mag) % 360)
            wca, gs = resolver_triangulo_vientos(mc, tas, dir_viento, vel_viento)
            mh = int((mc + wca) % 360)
            
            ete_minutos = round((distancia / gs) * 60)
            comb_tramo = round((ete_minutos / 60) * lph, 1)
            
            cols[4].write(f"{mc}°")
            cols[5].write(f"**{mh}°**")
            cols[6].write(f"{ete_minutos} min")
            cols[7].write(f"{comb_tramo} L")
            
            total_distancia += distancia
            total_tiempo += ete_minutos
            total_combustible += comb_tramo
            
            tabla_navegacion.append({
                "Tramo": f"Pierna {i+1}",
                "Ruta": f"{origen_sel} ➔ {destino_sel}",
                "Frecuencias": f"O: {p_orig['frec']} / D: {p_dest['frec']}",
                "Altitud": f"{altitud_sel} FT",
                "True Course (TC)": f"{tc}°",
                "Magnetic Course (MC)": f"{mc}°",
                "WCA": f"{'+' if wca >= 0 else ''}{int(wca)}°",
                "Magnetic Heading (MH)": f"{mh}°",
                "GS (KT)": f"{gs}",
                "Distancia (NM)": f"{distancia}",
                "Tiempo": f"{ete_minutos} min",
                "Combustible": f"{comb_tramo} L"
            })

        if num_tramos > 1:
            if cols[8].button("🗑️", key=f"btn_borrar_{i}"):
                st.session_state.ruta.pop(i + 1)
                st.session_state.altitudes.pop(i)
                st.rerun()
        else:
            cols[8].write("")

    # --- BLOQUE DE TOTALES Y EXPORTACIÓN ---
    st.markdown("---")
    st.subheader("📊 Resumen General de la Travesía")

    if total_distancia > 0:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Distancia Total", f"{round(total_distancia, 1)} NM")
        c2.metric("Tiempo Estimado (ETE)", f"{total_tiempo} min")
        c3.metric("Combustible Total", f"{round(total_combustible, 1)} L")
        c4.metric("VAR / Avión", f"{var_mag}°W / {avión_sel}")
        
        st.markdown("### ✈️ Planilla Precomputada Consolidada (Brújula)")
        st.table(tabla_navegacion)
        
        st.markdown("### 📄 Exportar Documento de Vuelo")
        pdf_data = generar_pdf_a4_apaisado(
            tabla_navegacion, total_distancia, total_tiempo, total_combustible, 
            avión_sel, var_mag, dir_viento, vel_viento
        )
        
        st.download_button(
            label="📥 Descargar Planilla de Navegación en PDF (A4)",
            data=pdf_data,
            file_name="Planilla_Navegacion_VFR.pdf",
            mime="application/pdf"
        )