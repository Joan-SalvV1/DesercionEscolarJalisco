import pandas as pd

# Cargar el archivo XLS (tu clasificación final)
df = pd.read_csv("clasificacion_municipios(1).csv")

# Convertir el DataFrame a JSON: lista de diccionarios
json_data = df.to_json(orient="records", force_ascii=False, indent=4)

# Guardar en un archivo JSON
with open("clasificacion_municipios.json", "w", encoding="utf-8") as f:
    f.write(json_data)

print("Archivo JSON generado: clasificacion_municipios.json")