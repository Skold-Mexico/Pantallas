import json

# Carga tu secrets.json
with open("secrets.json", "r") as f:
    data = json.load(f)

# Convierte los saltos de línea de la clave privada
if "private_key" in data:
    data["private_key"] = data["private_key"].replace("\\n", "\n")  # en caso de que ya tenga \n
    data["private_key"] = data["private_key"].replace("\n", "\\n")  # para Streamlit

# Genera el diccionario para usar en st.secrets
secrets_dict = {"google": data}

# Opcional: imprime para copiar en Streamlit
import pprint
pprint.pprint(secrets_dict)
