import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import dateparser
import time
from flask import Flask

app = Flask(__name__)

# 🌍 Configuración de acceso a Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"  # Asegúrate de tener esto bien cargado en Render
SPREADSHEET_NAME = "Convocatorias Clima"

# 🎯 Conectar a Google Sheets
def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    gc = gspread.authorize(creds)
    return gc

# 🧠 Extraer datos de una fuente según tipo
def scrape_fuente(nombre, url, tipo, idioma):
    convocatorias = []
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")

        # ⏳ Extraer títulos tentativos de convocatorias
        titulos = soup.find_all(['h2', 'h3', 'h4'])
        for t in titulos:
            titulo = t.get_text(strip=True)

            # 🔍 Buscar fecha asociada al texto
            text = t.find_next().get_text(" ", strip=True)
            fecha = dateparser.parse(text, languages=['en', 'es', 'pt'])

            if not fecha:
                continue

            # 📅 Validar que la fecha sea futura
            if fecha < datetime.now():
                continue

            # 💬 Descripción
            descripcion = text if len(text) < 500 else text[:500]

            # 🇧🇷 Traducir si no es portugués
            descripcion_pt = descripcion
            if idioma.lower() != "portugués":
                try:
                    descripcion_pt = GoogleTranslator(source='auto', target='pt').translate(descripcion)
                except:
                    print(f"⚠️ No se pudo traducir: {descripcion}")

            # 🧾 Construir fila
            fila = [
                titulo.strip(),
                nombre,
                fecha.strftime("%Y-%m-%d"),
                url,
                idioma,
                descripcion,
                descripcion_pt
            ]
            convocatorias.append(fila)

            # 💤 Esperar para evitar abuso
            time.sleep(1)

    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")

    return convocatorias

# 📊 Actualizar hoja con nuevas convocatorias
def actualizar_convocatorias():
    gc = conectar_sheets()
    hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")

    fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(1)

    nuevas = []

    for fuente in fuentes:
        nombre = fuente["Nombre"]
        url = fuente["URL"]
        tipo = fuente["Tipo"]
        idioma = fuente["Idioma"]

        print(f"🔍 Revisando {nombre}...")
        convocatorias = scrape_fuente(nombre, url, tipo, idioma)

        for conv in convocatorias:
            if conv[0] not in existentes:
                nuevas.append(conv)
            else:
                print(f"🔁 Ya existía: {conv[0]}")

    if nuevas:
        hoja_convocatorias.append_rows(nuevas)
        print(f"✅ Se agregaron {len(nuevas)} convocatorias nuevas.")
    else:
        print("📭 No se encontraron convocatorias nuevas.")

# 🚀 Endpoint principal de Flask para Render
@app.route('/')
def home():
    actualizar_convocatorias()
    return "🤖 Bot ejecutado correctamente."

# 🏁 Ejecutar la app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
