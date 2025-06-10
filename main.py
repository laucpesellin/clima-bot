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

def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🔍 Procesando: {nombre}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    text_content = soup.get_text(separator=" ").strip()

    if not text_content or len(text_content) < 50:
        print(f"⚠️ Contenido muy corto o vacío para {nombre}")
        return []

    posibles_fechas = search_dates(text_content, languages=['en', 'es', 'fr', 'pt'])

    convocatorias = []
    if posibles_fechas:
        for texto, fecha in posibles_fechas:
            if fecha and fecha > datetime.now().astimezone(fecha.tzinfo):  # Comparar fechas con misma zona horaria
                descripcion = texto.strip()
                descripcion_pt = traducir_texto(descripcion, idioma_origen=idioma, idioma_destino="pt")
                convocatorias.append({
                    "Título": descripcion[:100],
                    "Fuente": nombre,
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Enlace": url,
                    "Idioma": idioma,
                    "Descripción": descripcion,
                    "Descripción PT": descripcion_pt
                })
                print(f"✅ Convocatoria encontrada: {fecha.strftime('%Y-%m-%d')}")
                break
    else:
        print(f"📭 No se encontraron fechas con links en {nombre}")

    time.sleep(2)
    return convocatorias

def actualizar_convocatorias():
    print("📡 Conectando con Google Sheets...")
    gc = conectar_sheets()
    hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")

    # Leer encabezados reales
    headers = hoja_convocatorias.row_values(1)
    header_indices = {header: idx for idx, header in enumerate(headers)}

    fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(header_indices.get("Título", 1) + 1)

    nuevas = []

    for fuente in fuentes:
        nombre = fuente.get("Nombre")
        url = fuente.get("URL")
        tipo = fuente.get("Tipo")
        idioma = fuente.get("Idioma")

        nuevas_conv = scrape_fuente(nombre, url, tipo, idioma)

        for conv in nuevas_conv:
            if conv["Título"] not in existentes:
                nuevas.append([
                    conv.get("Título", ""),
                    conv.get("Fuente", ""),
                    conv.get("Fecha", ""),
                    conv.get("Enlace", ""),
                    conv.get("Idioma", ""),
                    conv.get("Descripción", ""),
                    conv.get("Descripción PT", "")
                ])
            else:
                print(f"🔁 Convocatoria duplicada omitida: {conv['Título']}")

    if nuevas:
        hoja_convocatorias.append_rows(nuevas)
        print(f"📝 Agregadas {len(nuevas)} nuevas convocatorias.")
    else:
        print("📭 No hay convocatorias nuevas para agregar.")

@app.route('/')
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

@app.route('/health')
def health():
    return "✅ OK"

# === INICIO ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
