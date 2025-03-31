import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import pandas as pd
import unicodedata
import numpy as np
import plotly.express as px

# Coordenadas centrales para Jalisco
CENTERED_COORDINATES = [20.6597, -102]

#====================================== CLASE PARA PROCESAMIENTO DE DATOS =================================

class DataProcessor:
    def __init__(self, clasificacion_path, geojson_path):
        self.clasificacion_path = clasificacion_path
        self.geojson_path = geojson_path
        self.df_desercion = None
        self.geo_json = None

    @staticmethod
    def normalize_text(text):
        text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("utf-8")
        return text.strip().lower()

    @staticmethod
    def calcular_centroide(coordinates):
        try:
            # Función recursiva para aplanar la lista de coordenadas
            def flatten(coords):
                if isinstance(coords[0], (float, int)):
                    return [coords]
                else:
                    out = []
                    for c in coords:
                        out.extend(flatten(c))
                    return out

            flat = flatten(coordinates)
            arr = np.array(flat)
            # Cada par es [lon, lat] en GeoJSON; retornamos [lat, lon]
            return [np.mean(arr[:, 1]), np.mean(arr[:, 0])]
        except:
            return CENTERED_COORDINATES

    def load_data(self):
        # Cargar clasificación y normalizar nombres
        with open(self.clasificacion_path, "r", encoding="utf-8") as f:
            desercion_data = json.load(f)
        self.df_desercion = pd.DataFrame(desercion_data)
        self.df_desercion["NOMBRE MUNICIPIO"] = self.df_desercion["NOMBRE MUNICIPIO"].apply(self.normalize_text)

        # Cargar GeoJSON y filtrar solo municipios de Jalisco
        with open(self.geojson_path, "r", encoding="utf-8") as f:
            self.geo_json = json.load(f)
        self.geo_json["features"] = [
            feat for feat in self.geo_json["features"] 
            if feat["properties"].get("NAME_1") == "Jalisco" and "coordinates" in feat["geometry"]
        ]
    
    def procesar_geojson(self):
        # Fusionar datos de deserción con el GeoJSON
        for feature in self.geo_json['features']:
            municipio_geo = self.normalize_text(feature['properties'].get('NAME_2', ''))
            datos = self.df_desercion[self.df_desercion["NOMBRE MUNICIPIO"] == municipio_geo]
            props = {
                'DESERCION': round(datos['DESERCION INTRACURRICULAR'].values[0], 2) if not datos.empty else 'N/D',
                'RIESGO': datos['RIESGO'].values[0] if not datos.empty else 'Sin datos',
                'EFICIENCIA': round(datos['EFICIENCIA TERMINAL'].values[0], 2) if not datos.empty else 'N/D',
                'centroide': self.calcular_centroide(feature['geometry']['coordinates'])
            }
            feature['properties'].update(props)
    
    def get_dataframe(self):
        return self.df_desercion

    def get_geojson(self):
        return self.geo_json

#=================================== CLASE PARA LA APLICACIÓN =================================================================
class MapaApp:
    def __init__(self, data_processor: DataProcessor):
        self.dp = data_processor
        self.df_desercion = self.dp.get_dataframe()
        self.geo_json = self.dp.get_geojson()
        self.color_map = {
            "Bajo Riesgo": "#2ecc71",
            "Riesgo Moderado": "#f1c40f",
            "Alto Riesgo": "#e74c3c",
            "Sin datos": "#95a5a6"
        }
        self.selected_municipio = None
        self.riesgo_filter = None
        self.geo_json_filtrado = None
        self.map_center = CENTERED_COORDINATES
        self.zoom = 7

    def sidebar_filters(self):
        with st.sidebar:
            st.header("🔍 Filtros y Búsqueda")
            
            # Opción para cambiar entre modo individual y comparación
            modo = st.radio("Modo:", options=["Individual", "Comparación"], index=0)
            
            # Filtro de riesgo
            riesgos = ["Bajo Riesgo", "Riesgo Moderado", "Alto Riesgo"]
            self.riesgo_filter = st.multiselect("Filtrar por riesgo:", riesgos, default=riesgos)
            if not self.riesgo_filter:
                self.riesgo_filter = riesgos
            
            if modo == "Individual":
                ver_todos = st.checkbox("Mostrar todos los municipios", value=True)
                if not ver_todos:
                    municipios = [m.title() for m in self.df_desercion["NOMBRE MUNICIPIO"].unique()]
                    self.selected_municipio = st.selectbox("Buscar municipio:", sorted(municipios))
                else:
                    self.selected_municipio = None
            else:
                # En modo comparación se permite seleccionar múltiples municipios
                municipios = [m.title() for m in self.df_desercion["NOMBRE MUNICIPIO"].unique()]
                self.selected_municipio = st.multiselect("Comparar municipios:", sorted(municipios))
            
            return modo

    def filtrar_geojson(self):
        # Si en modo comparación se han seleccionado municipios (lista) y la lista no está vacía:
        if isinstance(self.selected_municipio, list) and self.selected_municipio:
            municipios_norm = [DataProcessor.normalize_text(m) for m in self.selected_municipio]
            features = [
                f for f in self.geo_json["features"]
                if DataProcessor.normalize_text(f['properties']['NAME_2']) in municipios_norm
            ]
        # Si se seleccionó un único municipio (modo individual):
        elif self.selected_municipio and isinstance(self.selected_municipio, str):
            selected_normalized = DataProcessor.normalize_text(self.selected_municipio)
            features = [
                f for f in self.geo_json["features"]
                if DataProcessor.normalize_text(f['properties']['NAME_2']) == selected_normalized
            ]
        # Si no se seleccionó ningún municipio, filtra por riesgo:
        else:
            features = [
                f for f in self.geo_json["features"]
                if f['properties']['RIESGO'] in self.riesgo_filter
            ]
        
        self.geo_json_filtrado = {"type": "FeatureCollection", "features": features}
        
        if not self.geo_json_filtrado["features"]:
            self.geo_json_filtrado = self.geo_json

    def ajustar_centro_mapa(self):
        # Ajusta el centro del mapa en modo individual
        self.map_center = CENTERED_COORDINATES
        self.zoom = 7
        if self.selected_municipio and isinstance(self.selected_municipio, str):
            selected_normalized = DataProcessor.normalize_text(self.selected_municipio)
            for feature in self.geo_json["features"]:
                if DataProcessor.normalize_text(feature['properties']['NAME_2']) == selected_normalized:
                    self.map_center = feature['properties']['centroide']
                    self.zoom = 10
                    break

    def style_function(self, feature):
        # Para modo individual, descolorear municipios que no sean seleccionados
        if self.selected_municipio and isinstance(self.selected_municipio, str):
            municipio_nombre = DataProcessor.normalize_text(feature['properties']['NAME_2'])
            if municipio_nombre != DataProcessor.normalize_text(self.selected_municipio):
                return {
                    'fillColor': '#d3d3d3',
                    'color': '#000000',
                    'weight': 0.5,
                    'fillOpacity': 0.3
                }
        # Modo comparación o sin filtro: usar color según riesgo
        return {
            'fillColor': self.color_map.get(feature['properties']['RIESGO'], '#95a5a6'),
            'color': '#000000',
            'weight': 0.5,
            'fillOpacity': 0.6
        }
    
    def generar_mapa(self):
        # Ajusta el centro si está en modo individual
        self.ajustar_centro_mapa()
        m = folium.Map(location=self.map_center, zoom_start=self.zoom, tiles="CartoDB positron")
        folium.GeoJson(
            self.geo_json_filtrado,
            style_function=lambda feature: self.style_function(feature),
            tooltip=folium.GeoJsonTooltip(
                fields=['NAME_2', 'DESERCION', 'RIESGO', 'EFICIENCIA'],
                aliases=['Municipio:', 'Deserción (%):', 'Riesgo:', 'Eficiencia (%):'],
                style="background-color: white; border: 1px solid black; border-radius: 3px; padding: 5px;"
            )
        ).add_to(m)
        return m

    def mostrar_comparacion(self):
        st.subheader("Comparación entre Municipios")
        # En modo comparación, self.selected_municipio es una lista
        if not self.selected_municipio or len(self.selected_municipio) < 2:
            st.info("Seleccione al menos dos municipios para comparar.")
            return

        # Normalizamos y filtramos el dataframe para que solo contenga los municipios seleccionados
        municipios_norm = [DataProcessor.normalize_text(m) for m in self.selected_municipio]
        df_comp = self.df_desercion[self.df_desercion["NOMBRE MUNICIPIO"].isin(municipios_norm)]
        
        if df_comp.empty:
            st.warning("No se encontraron datos para los municipios seleccionados.")
            return

        st.dataframe(df_comp.sort_values("NOMBRE MUNICIPIO"))

        # Gráfico comparativo para Deserción (solo la métrica de deserción)
        fig_desercion = px.bar(
            df_comp,
            x="NOMBRE MUNICIPIO",
            y="DESERCION INTRACURRICULAR",
            labels={"DESERCION INTRACURRICULAR": "Deserción (%)", "NOMBRE MUNICIPIO": "Municipio"},
            title="Comparación de Deserción Escolar"
        )
        # Gráfico comparativo para Eficiencia Terminal
        fig_eficiencia = px.bar(
            df_comp,
            x="NOMBRE MUNICIPIO",
            y="EFICIENCIA TERMINAL",
            labels={"EFICIENCIA TERMINAL": "Eficiencia Terminal (%)", "NOMBRE MUNICIPIO": "Municipio"},
            title="Comparación de Eficiencia Terminal"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_desercion, use_container_width=True)
        with col2:
            st.plotly_chart(fig_eficiencia, use_container_width=True)

    def run(self):
        modo = self.sidebar_filters()
        self.filtrar_geojson()
        
        st.title("Deserción Escolar en Jalisco")
        url="https://datos.jalisco.gob.mx/dataset/indicadores-cct"
        st.write("Datos obtenidos desde [datos.jalisco.gob.mx](%s) con fecha de 2017, evaluados mediante tecnicas de machine learning" % url)
        col1, col2 = st.columns([3, 1])
        
        with col1:
            mapa = self.generar_mapa()
            st_folium(mapa, width=800, height=600)
        
        with col2:
            st.subheader("Leyenda:")
            for riesgo, color in self.color_map.items():
                st.markdown(f"<div style='background-color:{color}; padding:10px; margin:5px; border-radius:5px;'>{riesgo}</div>", unsafe_allow_html=True)
        
        st.subheader("Distribución de Riesgos")
        riesgo_counts = self.df_desercion[self.df_desercion["RIESGO"].isin(self.riesgo_filter)].groupby("RIESGO").size()
        st.bar_chart(riesgo_counts, color="#3498db")
        
        # Modo individual: mostrar datos detallados de un único municipio
        if modo == "Individual":
            df_filtrado = self.df_desercion[self.df_desercion["RIESGO"].isin(self.riesgo_filter)]
            if self.selected_municipio and isinstance(self.selected_municipio, str):
                df_filtrado = df_filtrado[df_filtrado["NOMBRE MUNICIPIO"] == DataProcessor.normalize_text(self.selected_municipio)]
            st.subheader("Datos Detallados")
            st.write("El dataset tenia datos incompletos en muchos casos, asi que no siempre la suma de todos los porcentajes llegan al 100%")
            st.dataframe(df_filtrado.sort_values("NOMBRE MUNICIPIO"))
        else:
            # Modo comparación: mostrar sección comparativa
            self.mostrar_comparacion()


def main():
    st.set_page_config(page_title="Deserción Escolar en Jalisco", layout="wide")
    
    # Instanciar y cargar datos
    dp = DataProcessor("clasificacion_municipios.json", "Jalisco.json")
    dp.load_data()
    dp.procesar_geojson()
    
    # Instanciar la aplicación y ejecutarla
    app = MapaApp(dp)
    app.run()

if __name__ == "__main__":
    main()
