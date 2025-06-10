from flask import Flask
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import time
from dateparser.search import search_dates
from datetime import datetime
from deep_translator import GoogleTranslator

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
        print(f"⚠️ Error de traducción: {idioma_origen} --> {idioma_destino}\n{e}")
        return texto

def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🔍 Procesando: {nombre}")
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    text_content = soup.get_text(separator=" ").strip()

    convocatorias = []
    posibles_fechas = search_dates(text_content, languages=['en', 'es', 'fr', 'pt'])

    if not posibles_fechas:
        print(f"📭 No se encontraron fechas con links en {nombre}")
        return []

    for texto, fecha in posibles_fechas:
        if not fecha:
            continue

        now = datetime.now().astimezone()
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=now.tzinfo)

        if fecha <= now:
            continue

        descripcion = texto.strip()

        if len(descripcion.split()) < 4:
            index = text_content.find(descripcion)
            if index != -1:
                start = max(0, index - 75)
                end = min(len(text_content), index + 75)
                descripcion = text_content[start:end].strip()

        descripcion_pt = traducir_texto(descripcion, idioma_origen=idioma, idioma_destino="pt")

        convocatorias.append([
            descripcion[:100],  # Título
            nombre,             # Fuente
            fecha.strftime("%Y-%m-%d"),  # Fecha
            url,                # Enlace
            idioma,             # Idioma
            descripcion,        # Descripción
            descripcion_pt      # Descripción (PT)
        ])
        print(f"✅ Convocatoria encontrada: {fecha.strftime('%Y-%m-%d')}")
        break  # Solo la primera válida

    time.sleep(1)
    return convocatorias

def actualizar_convocatorias():
    print("📡 Conectando con Google Sheets...")
    gc = conectar_sheets()
    hoja = gc.open(SPREADSHEET_NAME)
    hoja_fuentes = hoja.worksheet("Fuentes")
    hoja_convocatorias = hoja.worksheet("Convocatorias Clima")

    fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(1)

    nuevas = []

    for fuente in fuentes:
        nombre = fuente.get("Nombre") or fuente.get("Fonte")
        url = fuente.get("URL") or fuente.get("Enlace")
        tipo = fuente.get("Tipo") or fuente.get("Tipo")  # Future-proofing
        idioma = fuente.get("Idioma") or fuente.get("Língua")

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

# === ENDPOINTS ===

@app.route('/')
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

@app.route('/health')
def health():
    return "✅ Online", 200

# === EJECUCIÓN LOCAL ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
