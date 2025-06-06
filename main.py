from flask import Flask
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import time
import dateparser
from dateparser.search import search_dates
from deep_translator import GoogleTranslator
from datetime import datetime

app = Flask(__name__)

# === CONFIGURACIÓN ===
SPREADSHEET_NAME = "Convocatorias Clima"
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# === FUNCIONES ===

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    client = gspread.authorize(creds)
    return client

def traducir_texto(texto, idioma_origen="auto", idioma_destino="pt"):
    try:
        return GoogleTranslator(source=idioma_origen, target=idioma_destino).translate(texto)
    except Exception as e:
        print(f"⚠️ Error de traducción: {e}")
        return texto

def es_fecha_util(texto):
    texto = texto.lower()
    claves = ["cierre", "deadline", "fecha límite", "apply by", "plazo", "fecha de cierre"]
    return any(clave in texto for clave in claves)

def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🔍 Procesando: {nombre}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error al acceder a {nombre}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    text_content = soup.get_text(separator=" ").strip()

    convocatorias = []
    fechas_detectadas = search_dates(text_content, languages=['en', 'es', 'fr', 'pt'])

    if fechas_detectadas:
        for fragmento, fecha in fechas_detectadas:
            if fecha and fecha > datetime.now() and es_fecha_util(fragmento):
                descripcion = fragmento.strip()
                descripcion_pt = traducir_texto(descripcion, idioma_origen=idioma, idioma_destino="pt")

                convocatorias.append([
                    descripcion[:100],
                    nombre,
                    fecha.strftime("%Y-%m-%d"),
                    url,
                    idioma,
                    descripcion,
                    descripcion_pt
                ])
                break  # solo la primera válida
    else:
        print(f"📭 No se encontraron fechas en contexto útil en {nombre}")

    time.sleep(2)
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
        print("📭 No hay convocatorias nuevas para agregar.")

@app.route('/')
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

@app.route('/')
def home():
    try:
        actualizar_convocatorias()
        return "✅ Bot ejecutado correctamente."
    except Exception as e:
        print(f"💥 Error inesperado en '/' => {e}")
        return "❌ Error interno en el bot.", 200  # Devuelve 200 para evitar 500 en uptime

@app.route('/')
def home():
    try:
        actualizar_convocatorias()
        return "✅ Bot ejecutado correctamente."
    except Exception as e:
        print(f"💥 Error inesperado en '/' => {e}")
        return "❌ Error interno en el bot.", 200  # evita 500 y mantiene el servicio "vivo"

@app.route('/health')
def health():
    return "🟢 OK", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
