from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from deep_translator import GoogleTranslator
import requests
from bs4 import BeautifulSoup
import datetime
import dateparser

CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"  # <-- AJUSTA si tu JSON tiene otro nombre
SPREADSHEET_NAME = "Convocatorias Clima"

def conectar_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
    client = gspread.authorize(creds)
    return client

def traducir(texto):
    try:
        return GoogleTranslator(source='auto', target='pt').translate(texto)
    except:
        return "⚠️ No traducido"

def ya_existe(sheet, titulo, enlace):
    registros = sheet.get_all_values()
    for fila in registros:
        if titulo in fila or enlace in fila:
            return True
    return False

def extraer_convocatorias(client):
    hoja_fuentes = client.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = client.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")
    fuentes = hoja_fuentes.get_all_records()

    for fuente in fuentes:
        url = fuente["URL"]
        nombre = fuente["Nombre"]
        idioma = fuente.get("Idioma", "Inglés")

        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            elementos = soup.find_all(["h2", "h3", "h4", "a", "strong", "p", "span"])

            for el in elementos:
                texto = el.get_text().strip()
                fecha_detectada = dateparser.parse(texto, settings={'PREFER_DATES_FROM': 'future'})

                if fecha_detectada and fecha_detectada > datetime.datetime.now():
                    titulo = texto
                    enlace = el.get("href") if el.name == "a" and el.get("href") else url

                    if not ya_existe(hoja_convocatorias, titulo, enlace):
                        fecha_str = fecha_detectada.strftime("%d/%m/%Y")
                        descripcion = f"{titulo} - Detectado desde {nombre}"
                        hoja_convocatorias.append_row([
                            titulo, nombre, fecha_str, enlace, idioma, descripcion, traducir(descripcion)
                        ])
        except Exception as e:
            print(f"❌ Error con {nombre}: {e}")

def main():
    client = conectar_sheets()
    extraer_convocatorias(client)
    print("✅ BOT ejecutado con detección de fechas")

app = Flask(__name__)

@app.route('/')
def home():
    main()
    return "✅ Bot ejecutado con filtros de fechas reales 📅🧠"

app.run(host='0.0.0.0', port=8080)
