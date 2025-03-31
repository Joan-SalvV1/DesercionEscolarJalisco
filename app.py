import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import unicodedata
import numpy as np

def normalize_text(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("utf-8")
    return text.strip().lower()

def calcular_centroide(coordinates):
    try:
        if isinstance(coordinates[0][0], list):
            coordinates = coordinates[0]
        arr = np.array(coordinates)
        return [np.mean(arr[:,1]), np.mean(arr[:,0])]
    except:
        return [20.6597, -103.3496]

# Cargar datos
with open("clasificacion_municipios.json", "r", encoding="utf-8") as f:
    desercion_data = json.load(f)
    
df_desercion = pd.DataFrame(desercion_data)
df_desercion["NOMBRE MUNICIPIO"] = df_desercion["NOMBRE MUNICIPIO"].apply(normalize_text)

with open("Jalisco.json", "r", encoding="utf-8") as f:
    geo_json = json.load(f)

geo_json["features"] = [feat for feat in geo_json["features"] if feat["properties"]["NAME_1"] == "Jalisco" and "coordinates" in feat["geometry"]]

# Procesar GeoJSON
for feature in geo_json['features']:
    municipio_geo = normalize_text(feature['properties']['NAME_2'])
    datos = df_desercion[df_desercion["NOMBRE MUNICIPIO"] == municipio_geo]
    
    props = {
        'DESERCION': round(datos['DESERCION INTRACURRICULAR'].values[0], 2) if not datos.empty else 'N/D',
        'RIESGO': datos['RIESGO'].values[0] if not datos.empty else 'Sin datos',
        'EFICIENCIA': round(datos['EFICIENCIA TERMINAL'].values[0], 2) if not datos.empty else 'N/D',
        'centroide': calcular_centroide(feature['geometry']['coordinates'])
    }
    feature['properties'].update(props)

# Sidebar
with st.sidebar:
    st.header("🔍 Filtros y Búsqueda")

    ver_todos = st.checkbox("Mostrar todos los municipios", value=True)
    if not ver_todos:
        municipios = [f.title() for f in df_desercion["NOMBRE MUNICIPIO"].unique()]
        selected_municipio = st.selectbox("Buscar municipio:", sorted(municipios))
    else:
        selected_municipio = None 
        
    riesgos = ["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"]
    riesgo_filter = st.multiselect("Filtrar por riesgo:", riesgos, default=riesgos)

if not riesgo_filter:
    riesgo_filter = riesgos

# Filtrar y configurar mapa
geo_json_filtrado = {
    "type": "FeatureCollection",
    "features": [f for f in geo_json["features"] if f['properties']['RIESGO'] in riesgo_filter]
}

if not geo_json_filtrado["features"]:
    geo_json_filtrado = geo_json

map_center = [20.6597, -103.3496]
zoom = 7
if selected_municipio:
    selected_normalized = normalize_text(selected_municipio)
    for feature in geo_json["features"]:
        if normalize_text(feature['properties']['NAME_2']) == selected_normalized:
            map_center = feature['properties']['centroide']
            zoom = 10
            break

m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB positron")

# Paleta de colores
color_map = {
    "Bajo Riesgo": "#2ecc71",
    "Riesgo Moderado": "#f1c40f",
    "Alto Riesgo": "#e74c3c",
    "Sin datos": "#95a5a6"
}

def style_function(feature, selected_municipio_value):
    municipio_nombre = normalize_text(feature['properties']['NAME_2'])
    if selected_municipio_value and municipio_nombre != normalize_text(selected_municipio_value):
        # Municipio no seleccionado: gris
        return {
            'fillColor': '#d3d3d3',
            'color': '#000000',
            'weight': 0.5,
            'fillOpacity': 0.3
        }
    else:
        # Municipio seleccionado o sin filtro: usar el color según riesgo
        return {
            'fillColor': color_map.get(feature['properties']['RIESGO'], '#95a5a6'),
            'color': '#000000',
            'weight': 0.5,
            'fillOpacity': 0.6
        }

# Al añadir la capa GeoJSON, usamos un lambda para capturar el valor de selected_municipio:
folium.GeoJson(
    geo_json_filtrado,
    style_function=lambda feature: style_function(feature, selected_municipio),
    tooltip=folium.GeoJsonTooltip(
        fields=['NAME_2', 'DESERCION', 'RIESGO', 'EFICIENCIA'],
        aliases=['Municipio:', 'Deserción (%):', 'Riesgo:', 'Eficiencia (%):'],
        style="background-color: white; border: 1px solid black; border-radius: 3px; padding: 5px;"
    )
).add_to(m)


# Interfaz principal
st.title("Deserción Escolar en Jalisco")
col1, col2 = st.columns([3, 1])

with col1:
    st_folium(m, width=800, height=600)

with col2:
    st.subheader("Leyenda:")
    for riesgo, color in color_map.items():
        st.markdown(f"<div style='background-color:{color}; padding:10px; margin:5px; border-radius:5px;'>{riesgo}</div>", unsafe_allow_html=True)

# Gráfico y tabla
st.subheader("Distribución de Riesgos")
riesgo_counts = df_desercion[df_desercion["RIESGO"].isin(riesgo_filter)].groupby("RIESGO").size()
st.bar_chart(riesgo_counts, color="#3498db")

df_filtrado = df_desercion[df_desercion["RIESGO"].isin(riesgo_filter)]
if selected_municipio:
    df_filtrado = df_filtrado[df_filtrado["NOMBRE MUNICIPIO"] == normalize_text(selected_municipio)]


st.subheader("Datos Detallados")
st.dataframe(df_filtrado.sort_values("NOMBRE MUNICIPIO"))