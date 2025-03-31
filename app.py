import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import unicodedata

# Función para normalizar nombres de municipios
def normalize_text(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("utf-8")
    return text.strip().lower()

# Cargar datos de deserción
with open("clasificacion_municipios.json", "r", encoding="utf-8") as f:
    desercion_data = json.load(f)
    
df_desercion = pd.DataFrame(desercion_data)
df_desercion["NOMBRE MUNICIPIO"] = df_desercion["NOMBRE MUNICIPIO"].apply(normalize_text)

# Cargar y filtrar GeoJSON
with open("Jalisco.json", "r", encoding="utf-8") as f:
    geo_json = json.load(f)

geo_json["features"] = [
    feat for feat in geo_json["features"]
    if feat["properties"]["NAME_1"] == "Jalisco"  # Filtra solo Jalisco
    and "coordinates" in feat["geometry"]         # Asegura geometrías válidas
]

# Vincular datos de deserción con GeoJSON
for feature in geo_json['features']:
    municipio_geo = normalize_text(feature['properties']['NAME_2'])
    datos = df_desercion[df_desercion["NOMBRE MUNICIPIO"] == municipio_geo]
    
    if not datos.empty:
        feature['properties'].update({
            'DESERCION': round(datos['DESERCION INTRACURRICULAR'].values[0], 2),
            'RIESGO': datos['RIESGO'].values[0],
            'EFICIENCIA': round(datos['EFICIENCIA TERMINAL'].values[0], 2)
        })
    else:
        feature['properties'].update({
            'DESERCION': 'N/D',
            'RIESGO': 'Sin datos',
            'EFICIENCIA': 'N/D'
        })

# Sidebar con controles
with st.sidebar:
    st.header("🔍 Filtros y Búsqueda")
    
    # Buscador de municipios
    municipios = [f.title() for f in df_desercion["NOMBRE MUNICIPIO"].unique()]
    selected_municipio = st.selectbox("Buscar municipio:", sorted(municipios))
    
    # Filtro de riesgo
    riesgos = ["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"]
    riesgo_filter = st.multiselect("Filtrar por riesgo:", riesgos, default=riesgos)

# Filtrar GeoJSON según selección
geo_json_filtrado = {
    "type": "FeatureCollection",
    "features": [
        f for f in geo_json["features"]
        if f['properties']['RIESGO'] in riesgo_filter
    ]
}

# Paleta de colores para riesgos
color_map = {
    "Bajo Riesgo": "#2ecc71",
    "Riesgo Moderado": "#f1c40f",
    "Alto Riesgo": "#e74c3c",
    "Sin datos": "#95a5a6"
}

# Estilo de los polígonos
def style_function(feature):
    return {
        'fillColor': color_map.get(feature['properties']['RIESGO'], '#95a5a6'),
        'color': '#000000',
        'weight': 0.5,
        'fillOpacity': 0.6
    }

# Crear mapa
m = folium.Map(
    location=[20.6597, -102],
    zoom_start=7,
    tiles="CartoDB positron"
)

# Añadir capa GeoJSON
folium.GeoJson(
    geo_json,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(
        fields=['NAME_2', 'DESERCION', 'RIESGO', 'EFICIENCIA'],
        aliases=['Municipio:', 'Deserción (%):', 'Riesgo:', 'Eficiencia (%):'],
        style=(
            "background-color: white; border: 1px solid black;"
            "border-radius: 3px; padding: 5px; font-size: 12px;"
        )
    )
).add_to(m)

# Interfaz de Streamlit
st.title("Deserción Escolar en Jalisco")
col1, col2 = st.columns([3, 1])

with col1:
    st_folium(m, width=800, height=600)

with col2:
    st.subheader("Leyenda:")
    st.markdown("""
    <div style='background-color:#2ecc71; padding:10px; color:white; margin:5px; border-radius:5px;'>Bajo Riesgo</div>
    <div style='background-color:#f1c40f; padding:10px; margin:5px; border-radius:5px;'>Riesgo Moderado</div>
    <div style='background-color:#e74c3c; padding:10px; color:white; margin:5px; border-radius:5px;'>Alto Riesgo</div>
    <div style='background-color:#95a5a6; padding:10px; margin:5px; border-radius:5px;'>Sin datos</div>
    """, unsafe_allow_html=True)

# Mostrar tabla de datos
st.subheader("Datos Detallados")
st.dataframe(df_desercion[["NOMBRE MUNICIPIO", "DESERCION INTRACURRICULAR", "RIESGO"]].sort_values("NOMBRE MUNICIPIO"))