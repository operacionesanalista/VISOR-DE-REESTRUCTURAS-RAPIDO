import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import hashlib
import colorsys

# 1. Configuración de página
st.set_page_config(layout="wide", page_title="GEOPUNTOS")

# --- FUNCIONES DE APOYO ---
@st.cache_data
def cargar_datos(archivo):
    """Carga y cachea los datos para no reprocesar el Excel/CSV en cada recarga."""
    if archivo.name.endswith('.csv'):
        df = pd.read_csv(archivo, encoding='utf-8-sig')
    else:
        df = pd.read_excel(archivo)
    df.columns = [c.strip() for c in df.columns]
    
    if 'TIENDA ELIMINADA' not in df.columns:
        df['TIENDA ELIMINADA'] = 'NO'
    if 'FRECUENCIA' not in df.columns:
        df['FRECUENCIA'] = 0.0
    return df

def generar_color_contraste(texto):
    """Genera colores HSL forzando alta saturación y bajo brillo para máximo contraste."""
    if pd.isna(texto) or texto == "None" or str(texto).upper() == "ELIMINADA": return "#404040"
    
    hash_val = int(hashlib.md5(str(texto).encode()).hexdigest(), 16)
    hue = (hash_val % 360) / 360.0
    # Saturación al 85% y Luminosidad al 45% aseguran colores vivos y legibles
    r, g, b = colorsys.hls_to_rgb(hue, 0.45, 0.85)
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))


st.title('Visualización de Rutas por Estados')

# 2. Carga de Archivo
uploaded_file = st.sidebar.file_uploader("Carga tu archivo con columnas ESTADO, RUTA, lat, lon", type=["csv", "xlsx"])

if uploaded_file:
    df = cargar_datos(uploaded_file)
    
    # Asegurar que las columnas existan o asignar valores por defecto
    col_estado = 'ESTADO' if 'ESTADO' in df.columns else None
    col_ruta = 'NUEVA RUTA' if 'NUEVA RUTA' in df.columns else df.columns[0]
    
    # --- 4. FILTROS EN SIDEBAR ---
    st.sidebar.header("Filtros de Visualización")
    
    # Filtro por Estado
    if col_estado:
        estados = sorted(df[col_estado].unique().astype(str))
        estado_sel = st.sidebar.multiselect("Seleccionar Estado(s):", estados, default=estados[0] if estados else None)
        df_filtrado = df[df[col_estado].isin(estado_sel)]
    else:
        st.sidebar.warning("Columna 'ESTADO' no encontrada.")
        df_filtrado = df

    # Filtro por Ruta
    rutas_en_estado = sorted(df_filtrado[col_ruta].unique().astype(str))
    ruta_enfoque = st.sidebar.selectbox("Enfoque de Ruta:", ["TODAS"] + rutas_en_estado)

    if ruta_enfoque != "TODAS":
        df_filtrado = df_filtrado[df_filtrado[col_ruta] == ruta_enfoque]

    # Pre-calcular totales de frecuencia por ruta para el Tooltip
    totales_frecuencia = df_filtrado[df_filtrado['TIENDA ELIMINADA'].astype(str).str.upper() != 'SI'].groupby(col_ruta)['FRECUENCIA'].sum().to_dict()

    # --- 5. LÓGICA DEL MAPA ---
    col1, col2 = st.columns([1, 4])

    with col2:
        if not df_filtrado.empty:
            lat_m, lon_m = df_filtrado['lat'].mean(), df_filtrado['lon'].mean()
        else:
            lat_m, lon_m = 20.66, -103.39 

        m = folium.Map(location=[lat_m, lon_m], zoom_start=11, tiles="CartoDB positron")

        for idx, row in df_filtrado.iterrows():
            if pd.isna(row['lat']) or pd.isna(row['lon']): continue
            
            es_eliminada = str(row['TIENDA ELIMINADA']).upper() == 'SI'
            color_p = generar_color_contraste(row[col_ruta])
            
            # Recuperar el total de la ruta (si es eliminada, puede ser 0 o ignorarse)
            total_frec_ruta = totales_frecuencia.get(row[col_ruta], 0)
            
            # TOOLTIP MEJORADO CON TOTAL DE RUTA
            status_txt = "<b style='color:red;'>[ELIMINADA]</b>" if es_eliminada else f"Ruta: <b>{row[col_ruta]}</b>"
            
            html_tooltip = f"""
                <div style="font-family: sans-serif; font-size: 12px; min-width: 160px;">
                    {status_txt}<br>
                    <hr style="margin: 4px 0;">
                    <b>ID:</b> {row.get('ID TIENDA', 'N/A')}<br>
                    <b>Estado:</b> {row.get('ESTADO', 'N/A')}<br>
                    <b>Frec. Indiv:</b> {row.get('FRECUENCIA', 0)}<br>
                    <div style="background-color: #f0f0f0; padding: 4px; margin-top: 5px; border-radius: 3px; border-left: 3px solid {color_p if not es_eliminada else '#ff0000'};">
                        <b>Carga Total Ruta: {total_frec_ruta:.1f}</b>
                    </div>
                </div>
            """

            if es_eliminada:
                folium.Marker(
                    location=[row['lat'], row['lon']],
                    icon=folium.DivIcon(
                        html=f"""<div style="font-family: Arial; color: red; font-size: 14pt; font-weight: bold; text-align: center; text-shadow: 1px 1px 2px white;">X</div>"""
                    ),
                    tooltip=folium.Tooltip(html_tooltip, sticky=True)
                ).add_to(m)
            else:
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=7,
                    color=color_p,
                    fill=True,
                    fill_opacity=0.8, # Subí ligeramente la opacidad para que resalte más
                    weight=1.5, # Borde un poco más grueso
                    tooltip=folium.Tooltip(html_tooltip, sticky=True)
                ).add_to(m)

        # EL SECRETO PARA LA FLUIDEZ: returned_objects=[]
        st_folium(m, width="100%", height=700, key="visor_mapa", returned_objects=[])

    # --- 6. RESUMEN ESTADÍSTICO ---
    with col1:
        st.subheader("Métricas")
        st.metric("TIENDAS EN PANTALLA", len(df_filtrado))
        st.metric("CONTEO DE RUTAS", df_filtrado[col_ruta].nunique())
        
        st.write("**Carga por Ruta:**")
        # Mostrar el resumen basado en el diccionario ya calculado para eficiencia
        resumen_df = pd.DataFrame(list(totales_frecuencia.items()), columns=['RUTA', 'CARGA TOTAL']).sort_values(by='CARGA TOTAL', ascending=False)
        st.dataframe(resumen_df, hide_index=True, width='stretch')

else:
    st.info("Carga el archivo para generar la visualización.")