import requests
from bs4 import BeautifulSoup
from googletrans import Translator
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
import dateparser
from datetime import datetime

# CONFIGURACIÓN 🔧
SPREADSHEET_NAME = "Convocatorias Clima"
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"  # ← cambia por el nombre de tu JSON de credenciales
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# CONECTAR A SHEETS ✅
def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    client = gspread.authorize(creds)
    return client

# SCRAPER INTELIGENTE 🤖
def scrape_fuente(nombre, url, tipo, idioma):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Buscar fecha de cierre
        fecha = None
        for line in lines:
            parsed_date = dateparser.parse(line, settings={"PREFER_DATES_FROM": "future"})
            if parsed_date and parsed_date > datetime.now():
                fecha = parsed_date.strftime("%Y-%m-%d")
                break
        if not fecha:
            print(f"📭 No se encontró fecha de cierre futura para: {nombre}")
            return []

        # Buscar título
        titulo = soup.find("h1")
        if titulo:
            titulo = titulo.get_text(strip=True)
        else:
            titulo = lines[0][:120]  # fallback simple

        # Buscar descripción larga
        descripcion = ""
        for line in lines:
            if len(line) > 150 and "cookie" not in line.lower():
                descripcion = line
                break
        if not descripcion:
            print(f"⚠️ No hay descripción útil en: {nombre}")
            return []

        # Traducir
        translator = Translator()
        descripcion_pt = translator.translate(
            descripcion,
            src='es' if idioma.lower().startswith('es') else 'en',
            dest='pt'
        ).text

        return [[
            titulo,
            nombre,
            fecha,
            url,
            idioma,
            descripcion,
            descripcion_pt
        ]]

    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

# ACTUALIZAR CONVOCATORIAS 🔁
def actualizar_convocatorias():
    gc = conectar_sheets()
    hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")

    fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(4)  # Usar URL como ID

    nuevas = []

    for fuente in fuentes:
        nombre = fuente["Nombre"]
        url = fuente["URL"]
        tipo = fuente["Tipo"]
        idioma = fuente["Idioma"]

        nuevas_conv = scrape_fuente(nombre, url, tipo, idioma)

        for conv in nuevas_conv:
            if conv[3] not in existentes:
                nuevas.append(conv)
            else:
                print(f"🔁 Convocatoria duplicada omitida: {conv[0]}")

    if nuevas:
        hoja_convocatorias.append_rows(nuevas)
        print(f"✅ Agregadas {len(nuevas)} nuevas convocatorias.")
    else:
        print("📭 No hay convocatorias nuevas para agregar.")

# FLASK PARA RENDER 🌐
app = Flask(__name__)

@app.route('/')
def home():
    actualizar_convocatorias()
    return "<h3>🤖 Bot ejecutado correctamente desde Render</h3>"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
