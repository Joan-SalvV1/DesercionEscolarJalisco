import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import unicodedata
import numpy as np

class DataProcessor:
    def __init__(self, geojson_path, desercion_path):
        self.geojson_path = geojson_path
        self.desercion_path = desercion_path
        self.centered_coordinates = [20.6597, -102]
        self.geo_json = self.load_geojson()
        self.df_desercion = self.load_desercion()
        self.process_geojson()
    
    def load_geojson(self):
        with open(self.geojson_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def load_desercion(self):
        with open(self.desercion_path, "r", encoding="utf-8") as f:
            desercion_data = json.load(f)
        df = pd.DataFrame(desercion_data)
        df["NOMBRE MUNICIPIO"] = df["NOMBRE MUNICIPIO"].apply(self.normalize_text)
        return df
    
    def normalize_text(self, text):
        text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("utf-8")
        return text.strip().lower()
    
    def calcular_centroide(self, coordinates):
        try:
            if isinstance(coordinates[0][0], list):
                coordinates = coordinates[0]
            arr = np.array(coordinates)
            return [np.mean(arr[:, 1]), np.mean(arr[:, 0])]
        except:
            return self.centered_coordinates
    
    def process_geojson(self):
        self.geo_json["features"] = [
            feat for feat in self.geo_json["features"] if feat["properties"]["NAME_1"] == "Jalisco" and "coordinates" in feat["geometry"]
        ]
        for feature in self.geo_json['features']:
            municipio_geo = self.normalize_text(feature['properties']['NAME_2'])
            datos = self.df_desercion[self.df_desercion["NOMBRE MUNICIPIO"] == municipio_geo]
            props = {
                'DESERCION': round(datos['DESERCION INTRACURRICULAR'].values[0], 2) if not datos.empty else 'N/D',
                'RIESGO': datos['RIESGO'].values[0] if not datos.empty else 'Sin datos',
                'EFICIENCIA': round(datos['EFICIENCIA TERMINAL'].values[0], 2) if not datos.empty else 'N/D',
                'centroide': self.calcular_centroide(feature['geometry']['coordinates'])
            }
            feature['properties'].update(props)


class Mapa:
    def __init__(self, data_processor, selected_municipio=None, riesgo_filter=None):
        self.data_processor = data_processor
        self.selected_municipio = selected_municipio
        self.riesgo_filter = riesgo_filter or ["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"]
        self.color_map = {
            "Bajo Riesgo": "#2ecc71",
            "Riesgo Moderado": "#f1c40f",
            "Alto Riesgo": "#e74c3c",
            "Sin datos": "#95a5a6"
        }
    
    def filter_geojson(self):
        return {
            "type": "FeatureCollection",
            "features": [
                f for f in self.data_processor.geo_json["features"] if f['properties']['RIESGO'] in self.riesgo_filter
            ]
        }
    
    def style_function(self, feature):
        municipio_nombre = self.data_processor.normalize_text(feature['properties']['NAME_2'])#NAME_2 es como el geojson nombra a los municipios
        if self.selected_municipio and municipio_nombre != self.data_processor.normalize_text(self.selected_municipio):
            return {'fillColor': '#d3d3d3', 'color': '#000000', 'weight': 0.5, 'fillOpacity': 0.3}
        return {'fillColor': self.color_map.get(feature['properties']['RIESGO'], '#95a5a6'), 'color': '#000000', 'weight': 0.5, 'fillOpacity': 0.6}
    
    def render(self):
        geo_json_filtrado = self.filter_geojson()
        m = folium.Map(location=self.data_processor.centered_coordinates, zoom_start=7, tiles="CartoDB positron")
        folium.GeoJson(
            geo_json_filtrado,
            style_function=lambda feature: self.style_function(feature),
            tooltip=folium.GeoJsonTooltip(
                fields=['NAME_2', 'DESERCION', 'RIESGO', 'EFICIENCIA'],
                aliases=['Municipio:', 'Deserción (%):', 'Riesgo:', 'Eficiencia (%):'],
                style="background-color: white; border: 1px solid black; border-radius: 3px; padding: 5px;"
            )
        ).add_to(m)
        return m


# Inicializar procesamiento de datos
data_processor = DataProcessor("Jalisco.json", "clasificacion_municipios.json")

# Sidebar y filtros
with st.sidebar:
    st.header("🔍 Filtros y Búsqueda")
    ver_todos = st.checkbox("Mostrar todos los municipios", value=True)
    selected_municipio = None if ver_todos else st.selectbox("Buscar municipio:", sorted([f.title() for f in data_processor.df_desercion["NOMBRE MUNICIPIO"].unique()]))
    riesgo_filter = st.multiselect("Filtrar por riesgo:", ["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"], default=["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"])
    if not riesgo_filter:
        riesgo_filter = ["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"]

# Renderizar mapa
mapa = Mapa(data_processor, selected_municipio, riesgo_filter)
st.title("Deserción Escolar en Jalisco")
col1, col2 = st.columns([3, 1])
with col1:
    st_folium(mapa.render(), width=800, height=600)
with col2:
    st.subheader("Leyenda:")
    for riesgo, color in mapa.color_map.items():
        st.markdown(f"<div style='background-color:{color}; padding:10px; margin:5px; border-radius:5px;'>{riesgo}</div>", unsafe_allow_html=True)

# Mostrar datos y gráficos
st.subheader("Distribución de Riesgos")
st.bar_chart(data_processor.df_desercion[data_processor.df_desercion["RIESGO"].isin(riesgo_filter)].groupby("RIESGO").size(), color="#3498db")
st.subheader("Datos Detallados")
st.dataframe(data_processor.df_desercion[data_processor.df_desercion["RIESGO"].isin(riesgo_filter)].sort_values("NOMBRE MUNICIPIO"))
