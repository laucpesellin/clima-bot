from flask import Flask
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import time
import dateparser
from dateparser.search import search_dates
from deep_translator import GoogleTranslator
from datetime import datetime, timezone

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

def traducir_texto(texto):
    try:
        return GoogleTranslator(source="auto", target="pt").translate(texto)
    except Exception as e:
        print(f"⚠️ Error de traducción: {e}")
        return texto

def scrape_fuente(nombre, url, tipo):
    print(f"🔍 Procesando: {nombre}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    text_content = soup.get_text(separator=" ").strip()

    if len(text_content) < 100:
        print(f"⚠️ Contenido muy corto o vacío para {nombre}")
        return []

    convocatorias = []
    fechas_detectadas = search_dates(text_content, languages=['en', 'es', 'fr', 'pt'])

    print(">>> Fechas detectadas:", fechas_detectadas)

    if fechas_detectadas:
        for texto, fecha in fechas_detectadas:
            print("📅 Revisando:", fecha, "| Fragmento:", texto)
            if fecha:
                now = datetime.now(timezone.utc) if fecha.tzinfo else datetime.now()
                if fecha > now:
                    descripcion = texto.strip()
                    index = text_content.find(descripcion)

                    if index != -1:
                        punto_inicio = text_content.rfind('.', 0, index)
                        punto_final = text_content.find('.', index)

                        if punto_inicio == -1:
                            punto_inicio = max(0, index - 100)

                        if punto_final == -1:
                            punto_final = min(len(text_content), index + 200)

                        descripcion = text_content[punto_inicio + 1: punto_final + 1].strip()

                    descripcion_pt = traducir_texto(descripcion)

                    convocatorias.append([
                        descripcion[:100],
                        nombre,
                        fecha.strftime("%Y-%m-%d"),
                        url,
                        descripcion,
                        descripcion_pt
                    ])
                    print(f"✅ Convocatoria encontrada: {fecha.strftime('%Y-%m-%d')}")
                    break
    else:
        print(f"📭 No se encontraron fechas con links en {nombre}")

    time.sleep(2)
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
        nombre = fuente.get("Nombre")
        url = fuente.get("URL")
        tipo = fuente.get("Tipo") or "Otro"

        if not nombre or not url:
            continue

        nuevas_conv = scrape_fuente(nombre, url, tipo)

        for conv in nuevas_conv:
            if conv[0] not in existentes:
                nuevas.append(conv)
            else:
                print(f"🔁 Convocatoria duplicada omitida: {conv[0]}")

    if nuevas:
        print("➡️ A escribir en hoja:", nuevas)
        hoja_convocatorias.append_rows(nuevas)
        print(f"📝 Agregadas {len(nuevas)} nuevas convocatorias.")
    else:
        print("📭 No hay convocatorias nuevas para agregar.")

    time.sleep(2)

@app.route('/')
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

@app.route('/health')
def health():
    return "🟢 OK"

# === INICIO ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
