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
import pytz

app = Flask(__name__)

# === CONFIGURACIÓN ===
SPREADSHEET_NAME = "Convocatorias Clima"
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# === FUNCIONES ===

def conectar_sheets():
    print("📡 Conectando con Google Sheets...")
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

    if not text_content or len(text_content) < 200:
        print(f"⚠️ Contenido muy corto o vacío para {nombre}")
        return []

    fechas = search_dates(text_content, languages=['en', 'es', 'fr', 'pt'])

    if not fechas:
        print(f"📭 No se encontraron fechas con links en {nombre}")
        return []

    convocatorias = []
    ahora = datetime.now(pytz.utc)

    for texto, fecha in fechas:
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=pytz.utc)
        if fecha > ahora:
            descripcion = texto.strip()
            descripcion_pt = traducir_texto(descripcion, idioma_origen=idioma, idioma_destino="pt")
            convocatorias.append([
                descripcion[:100],  # Tema corto
                nombre,
                fecha.strftime("%Y-%m-%d"),
                url,
                idioma,
                descripcion,
                descripcion_pt
            ])
            print(f"✅ Convocatoria encontrada: {descripcion[:80]}...")
            break

    if not convocatorias:
        print(f"📭 Fechas encontradas, pero ninguna futura en {nombre}")
    time.sleep(2)
    return convocatorias

def actualizar_convocatorias():
    gc = conectar_sheets()
    hoja = gc.open(SPREADSHEET_NAME)
    hoja_fuentes = hoja.worksheet("Fuentes")
    hoja_convocatorias = hoja.worksheet("Convocatorias Clima")

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
    print("🌐 Acceso a raíz recibido. Ejecutando bot...")
    try:
        actualizar_convocatorias()
        return "✅ Bot ejecutado correctamente."
    except Exception as e:
        print(f"💥 Error al actualizar convocatorias: {e}")
        return f"❌ Error: {e}"

@app.route('/health')
def health():
    return "✅ OK"

# === INICIO ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
