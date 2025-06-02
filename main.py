from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import dateparser
import time

app = Flask(__name__)

# Configuración de Google Sheets
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"  # 👈 Cambia esto por el nombre de tu archivo JSON
SPREADSHEET_NAME = "Convocatorias Clima"

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    client = gspread.authorize(creds)
    return client

def traducir_texto(texto, idioma_origen="auto", idioma_destino="pt"):
    try:
        return GoogleTranslator(source=idioma_origen, target=idioma_destino).translate(texto)
    except Exception as e:
        print(f"⚠️ No se pudo traducir: {texto} | Error: {e}")
        return texto

def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🔍 Procesando: {nombre}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    convocatorias = []

    text_content = soup.get_text(separator=" ").strip()
    posibles_fechas = list(set(dateparser.search.search_dates(text_content, languages=['en', 'es', 'fr', 'pt'])))
    
    if posibles_fechas:
        for texto, fecha in posibles_fechas:
            if fecha and fecha > dateparser.parse("now"):
                descripcion = texto.strip()
                descripcion_pt = traducir_texto(descripcion, idioma_origen=idioma, idioma_destino="pt")
                convocatorias.append([
                    descripcion[:100],  # Tópico
                    nombre,             # Entidad
                    fecha.strftime("%Y-%m-%d"),  # Fecha
                    url,                # Link
                    idioma,             # Idioma
                    descripcion,        # Descripción
                    descripcion_pt      # Descripción en PT
                ])
                break  # Solo una válida por fuente
    else:
        print(f"📭 No se encontraron fechas válidas en {nombre}")
    
    time.sleep(2)  # Evita límite de rate
    return convocatorias

def actualizar_convocatorias():
    gc = conectar_sheets()
    hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")

    fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(1)

    nuevas = []
    for fuente in fuentes:
        nombre = fuente.get("Nombre")
        url = fuente.get("URL")
        tipo = fuente.get("Tipo")
        idioma = fuente.get("Idioma")

        if not all([nombre, url, tipo, idioma]):
            print(f"⚠️ Fuente incompleta: {fuente}")
            continue

        nuevas_conv = scrape_fuente(nombre, url, tipo, idioma)
        for conv in nuevas_conv:
            if conv[0] not in existentes:
                nuevas.append(conv)
            else:
                print(f"🔁 Convocatoria duplicada omitida: {conv[0]}")

    if nuevas:
        hoja_convocatorias.append_rows(nuevas)
        print(f"📝 Agregadas {len(nuevas)} nuevas convocatorias.")
    else:
        print("✅ No hay convocatorias nuevas.")

@app.route("/")
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
