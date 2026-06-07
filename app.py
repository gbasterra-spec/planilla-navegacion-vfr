import streamlit as st
import math
from io import BytesIO
import json
import os
import pandas as pd  # <--- Agregamos pandas para manejar los datos del mapa fácilmente

# --- IMPORTACIONES PARA REPORTLAB ---
import reportlab.lib.pagesizes as pdf_sizes
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape

# RUTA DEL ARCHIVO DE BASE DE DATOS LOCAL
DB_FILE = "waypoints_db.json"

# LÓGICA DE PERSISTENCIA ULTRA-ROBUSTA:
# Forzamos a la aplicación a leer ÚNICAMENTE el archivo físico JSON de GitHub.
if "aerodromos" not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                st.session_state.aerodromos = json.load(f)
        except Exception as e:
            st.error(f"❌ Error crítico al leer el archivo de base de datos JSON: {e}")
            st.stop()  # Detiene la ejecución para no operar con datos corruptos o vacíos
    else:
        # Alerta en pantalla si el archivo falta en el despliegue de GitHub
        st.error(f"❌ No se encontró el archivo '{DB_FILE}' en el repositorio de GitHub. Asegúrate de haberlo subido.")
        st.stop()

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
    
    # Ángulo entre el curso y de dónde viene el viento
    angulo_viento = dir_v_rad - mc_rad
    
    # 1. Componente de viento de frente (Headwind)
    headwind = vel_viento * math.cos(angulo_viento)
    
    # 2. Componente de viento cruzado (Crosswind)
    crosswind = vel_viento * math.sin(angulo_viento)
    
    # Validar si el viento cruzado supera la velocidad del avión (Imposible volar)
    if abs(crosswind) >= tas:
        return 0.0, 0.0
        
    # 3. Cálculo exacto del WCA
    wca_rad = math.asin(crosswind / tas)
    wca = math.degrees(wca_rad)
    
    # 4. Cálculo de GS usando Pitágoras/Trigonometría pura sin deformación
    gs = math.sqrt(tas**2 - crosswind**2) - headwind
    
    return round(wca, 0), round(max(0.0, gs), 1)

# NUEVA CONFIGURACIÓN: CAMBIO A FORMATO A5 PARA PERNERA (KNEEBOARD)
def generar_pdf_a5_apaisado(tabla_datos, dist_t, tiempo_t, comb_t, avion, var, v_dir, v_vel):
    buffer = BytesIO()
    
    # Tamaño A5 apaisado con márgenes optimizados de 20pt
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(pdf_sizes.A5), 
        rightMargin=20, leftMargin=20, 
        topMargin=20, bottomMargin=20
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('PdfTitle', parent=styles['Heading1'], fontSize=11, leading=13, textColor=colors.HexColor('#1E3A8A'), alignment=1, spaceAfter=4)
    normal_style = ParagraphStyle('PdfNormal', parent=styles['Normal'], fontSize=7.5, leading=10, textColor=colors.black)
    header_style = ParagraphStyle('PdfHeader', parent=styles['Normal'], fontSize=7.5, leading=9, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)
    cell_style = ParagraphStyle('PdfCell', parent=styles['Normal'], fontSize=7.5, leading=9, alignment=1)
    frec_style = ParagraphStyle('PdfFrec', parent=styles['Normal'], fontSize=7, leading=9, textColor=colors.HexColor('#334155'))
    
    story = []
    story.append(Paragraph("<b>PLANILLA DE NAVEGACIÓN VFR (KNEEBOARD A5)</b>", title_style))
    
    # Bloque de Metadatos superior
    meta_data = [
        [Paragraph(f"<b>Avión:</b> {avion} | <b>VAR:</b> {var}°W", normal_style), 
         Paragraph(f"<b>Viento:</b> {v_dir}° / {v_vel} KT | <b>Combustible:</b> Litros (L)", normal_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    story.append(meta_table)
    story.append(Spacer(1, 4))
    
    # Eliminamos la columna de frecuencias de la tabla principal
    headers = [
        Paragraph("<b>Tramo</b>", header_style), Paragraph("<b>Ruta</b>", header_style),
        Paragraph("<b>Alt</b>", header_style), Paragraph("<b>TC</b>", header_style), Paragraph("<b>MC</b>", header_style),
        Paragraph("<b>WCA</b>", header_style), Paragraph("<b>MH</b>", header_style), Paragraph("<b>GS</b>", header_style),
        Paragraph("<b>Dist</b>", header_style), Paragraph("<b>Min</b>", header_style), Paragraph("<b>Comb</b>", header_style),
    ]
    pdf_rows = [headers]
    
    # Recolectamos las frecuencias de los puntos usados de forma única para el final
    frecuencias_utilizadas = {}
    
    for row in tabla_datos:
        pdf_rows.append([
            Paragraph(row["Tramo"], cell_style), Paragraph(row["Ruta"], cell_style),
            Paragraph(row["Altitud"].replace(" FT", ""), cell_style), Paragraph(row["True Course (TC)"], cell_style), Paragraph(row["Magnetic Course (MC)"], cell_style),
            Paragraph(row["WCA"], cell_style), Paragraph(f"<b>{row['Magnetic Heading (MH)']}</b>", cell_style), Paragraph(row["GS (KT)"], cell_style),
            Paragraph(row["Distancia (NM)"], cell_style), Paragraph(row["Tiempo"].replace(" min", ""), cell_style), Paragraph(row["Combustible"].replace(" L", ""), cell_style),
        ])
        
        # Parseamos el string de frecuencias del tramo para extraerlas limpias
        # Ejemplo de formato original: "O: 118.5 / D: 123.4"
        try:
            partes_ruta = row["Ruta"].split(" ➔ ")
            orig_id, dest_id = partes_ruta[0], partes_ruta[1]
            partes_frec = row["Frecuencias"].split(" / ")
            frec_o = partes_frec[0].replace("O:", "").strip()
            frec_d = partes_frec[1].replace("D:", "").strip()
            
            frecuencias_utilizadas[orig_id] = frec_o
            frecuencias_utilizadas[dest_id] = frec_d
        except:
            pass
        
    total_style = ParagraphStyle('PdfTotal', parent=styles['Normal'], fontSize=7.5, fontName='Helvetica-Bold', alignment=1)
    pdf_rows.append([
        Paragraph("TOTAL", total_style), Paragraph("-", cell_style), Paragraph("-", cell_style),
        Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style),
        Paragraph(f"<b>{round(dist_t, 1)}</b>", total_style), Paragraph(f"<b>{tiempo_t}m</b>", total_style), Paragraph(f"<b>{round(comb_t, 1)}L</b>", total_style),
    ])
    
    # Nuevos anchos de columna distribuidos (Total 540 puntos utilizables en A5)
    # Al sacar frecuencias, le dimos más aire a Ruta, Alt, Dist y Combustible
    tabla_tramos = Table(pdf_rows, colWidths=[40, 115, 45, 34, 34, 34, 38, 36, 45, 44, 75])
    tabla_tramos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(tabla_tramos)
    story.append(Spacer(1, 6))
    
    # BLOQUE INFERIOR DE FRECUENCIAS DE RADIO (Ordenado y compacto)
    frec_items = [f"<b>{k}:</b> {v} MHz" for k, v in frecuencias_utilizadas.items()]
    frec_texto = " | ".join(frec_items)
    
    frec_data = [[Paragraph(f"📞 <b>FRECUENCIAS DE LA RUTA:</b> {frec_texto}", frec_style)]]
    tabla_frec = Table(frec_data, colWidths=[540])
    tabla_frec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(tabla_frec)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# 5. CONFIGURACIÓN DE STREAMLIT
st.set_page_config(page_title="Planilla de Navegación A5", page_icon="📋", layout="wide")

st.title("📋 Planilla de Navegación Operativa (Kneeboard A5)")
st.write("Planilla de vuelo compactada para formato pernera con previsualización de ruta en mapa.")
st.write("Desarrollada por Gabriel Basterra y Gemini")
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

# --- MAPA INTERACTIVO DE CONTROL EN EL SIDEBAR ---
# --- MAPA INTERACTIVO DE CONTROL EN EL SIDEBAR (CON LÍNEAS DE RUTA) ---
# --- MAPA INTERACTIVO DE CONTROL EN EL SIDEBAR (CON LÍNEAS DE RUTA) ---
# --- MAPA INTERACTIVO DE CONTROL EN EL SIDEBAR (LEAFLET.JS AUTOMÁTICO) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🗺️ Mapa de Ruta Seleccionada")

import streamlit.components.v1 as components

coordenadas_ruta = []
map_markers_js = ""
line_coords_js = []

# Procesamos los puntos de la ruta activa
for idx, p_id in enumerate(st.session_state.ruta):
    if p_id in AERODROMOS:
        lat = AERODROMOS[p_id]["lat"]
        lon = AERODROMOS[p_id]["lon"]
        nombre = f"{p_id} - {AERODROMOS[p_id]['nombre']}"
        coordenadas_ruta.append([lat, lon])
        
        # Color diferenciado: Verde el origen de la pierna inicial, Rojo el resto
        color_pin = "#10B981" if idx == 0 else "#EF4444"
        
        # Inyectamos código JavaScript para cada marcador
        map_markers_js += f"""
        L.circleMarker([{lat}, {lon}], {{
            radius: 6,
            fillColor: '{color_pin}',
            color: '#FFFFFF',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.9
        }}).addTo(map).bindPopup('<b>{nombre}</b>');
        """
        line_coords_js.append(f"[{lat}, {lon}]")

if coordenadas_ruta:
    # Determinamos el centro del mapa en base al primer punto
    lat_c, lon_c = coordenadas_ruta[0][0], coordenadas_ruta[0][1]
    lines_array_js = f"[{', '.join(line_coords_js)}]" if len(line_coords_js) > 1 else "[]"
    
    # Construimos el mapa HTML/JS embebido usando Leaflet con un mapa base claro (OpenStreetMap)
    html_map_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            html, body, #map {{ height: 100%; margin: 0; padding: 0; background-color: #F8FAFC; }}
            .leaflet-container {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            // Inicializar mapa centrado en el origen de la ruta
            var map = L.map('map', {{
                center: [{lat_c}, {lon_c}],
                zoom: 8,
                zoomControl: false,
                attributionControl: false
            }});
            
            // Cargar mapa base claro ideal para navegación visual VFR
            L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
                maxZoom: 18
            }}).addTo(map);
            
            // Agregar los marcadores de los aeródromos
            {map_markers_js}
            
            // Dibujar la línea de ruta si hay más de un punto seleccionado
            var lineCoords = {lines_array_js};
            if (lineCoords.length > 1) {{
                var polyline = L.polyline(lineCoords, {{
                    color: '#1D4ED8',
                    weight: 3,
                    opacity: 0.85,
                    dashArray: '5, 5' // Línea de trazos estilo ruta aeronáutica
                }}).addTo(map);
                
                // Ajustar el zoom automáticamente para que quepa toda la ruta en pantalla
                map.fitBounds(polyline.getBounds(), {{ padding: [20, 20] }});
            }}
        </script>
    </body>
    </html>
    """
    
    # Renderizar el componente HTML de manera nativa en el sidebar (Altura fija de 250px)
    components.html(html_map_code, height=250)
    
    # Eje de ruta en texto abajo del mapa para control
    trayecto_texto = " ➔ ".join(st.session_state.ruta)
    st.sidebar.caption(f"**Eje de Ruta:** {trayecto_texto}")

st.sidebar.markdown("---")

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
                "Tramo": f"P{i+1}",
                "Ruta": f"{origen_sel} ➔ {destino_sel}",
                "Frecuencias": f"O:{p_orig['frec']} / D:{p_dest['frec']}",
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
        
        # LLAMADA A LA NUEVA FUNCIÓN EN FORMATO A5
        pdf_data = generar_pdf_a5_apaisado(
            tabla_navegacion, total_distancia, total_tiempo, total_combustible, 
            avión_sel, var_mag, dir_viento, vel_viento
        )
        
        st.download_button(
            label="📥 Descargar Planilla de Navegación en PDF (Formato Pernera A5)",
            data=pdf_data,
            file_name="Planilla_VFR_Kneeboard_A5.pdf",
            mime="application/pdf"
        )