import streamlit as st
import json

st.set_page_config(page_title="Gestor de Waypoints", page_icon="📍", layout="wide")

st.title("📍 Base de Datos de Waypoints y Aeródromos")
st.write("Agregá nuevos puntos visuales o editá los existentes. Al guardarlos, se mantendrán de forma permanente en tu equipo.")
st.markdown("---")

DB_FILE = "waypoints_db.json"

if "aerodromos" not in st.session_state:
    st.warning("Por favor, abre primero la página principal para cargar la base de datos.")
else:
    # 1. SECCIÓN PARA AGREGAR NUEVOS PUNTOS
    st.subheader("➕ Agregar Nuevo Waypoint")
    
    c1, c2, c3, c4, c5 = st.columns([1, 2, 1.5, 1.5, 1])
    nuevo_id = c1.text_input("Identificador (Ej: VOR_SADM)", placeholder="OACI o Nombre").strip().upper()
    nuevo_nombre = c2.text_input("Nombre Completo / Referencia", placeholder="Ej: VOR Morón / Antena Azul")
    nueva_lat = c3.number_input("Latitud (Decimal)", value=-34.0000, format="%.4f")
    nueva_lon = c4.number_input("Longitud (Decimal)", value=-58.0000, format="%.4f")
    nueva_frec = c5.text_input("Frecuencia VHF", value="123.5")
    
    if st.button("💾 Guardar Waypoint"):
        if not nuevo_id or not nuevo_nombre:
            st.error("El Identificador y el Nombre son campos obligatorios.")
        elif nuevo_id in st.session_state.aerodromos:
            st.error(f"El identificador '{nuevo_id}' ya existe en la base de datos.")
        else:
            # Modificar el estado en memoria
            st.session_state.aerodromos[nuevo_id] = {
                "nombre": nuevo_nombre,
                "lat": nueva_lat,
                "lon": nueva_lon,
                "frec": nueva_frec
            }
            # ESCRIBIR CAMBIOS EN DISCO
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.aerodromos, f, indent=4, ensure_ascii=False)
                
            st.success(f"¡Waypoint {nuevo_id} guardado y guardado en disco con éxito!")
            st.rerun()

    st.markdown("---")
    
    # 2. SECCIÓN DE VISUALIZACIÓN Y ELIMINACIÓN
    st.subheader("📋 Waypoints Almacenados Actuales")
    
    tabla_visual = []
    for k, v in st.session_state.aerodromos.items():
        tabla_visual.append({
            "Identificador": k,
            "Nombre / Referencia": v["nombre"],
            "Latitud": v["lat"],
            "Longitud": v["lon"],
            "Frecuencia": v["frec"]
        })
    
    st.table(tabla_visual)
    
    st.subheader("🗑️ Eliminar un Waypoint")
    punto_a_borrar = st.selectbox("Selecciona el punto que deseas remover", list(st.session_state.aerodromos.keys()))
    
    if st.button("🔴 Eliminar Punto Seleccionado"):
        if len(st.session_state.aerodromos) <= 2:
            st.error("No puedes dejar la base de datos con menos de dos puntos.")
        else:
            # Eliminar de la memoria
            del st.session_state.aerodromos[punto_a_borrar]
            
            # ACTUALIZAR ARCHIVO EN DISCO
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.aerodromos, f, indent=4, ensure_ascii=False)
                
            st.success(f"Punto {punto_a_borrar} eliminado correctamente del disco.")
            st.rerun()