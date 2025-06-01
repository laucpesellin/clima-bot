from urllib.parse import urlparse
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import requests
from deep_translator import GoogleTranslator
from datetime import datetime

# === CONFIG ===
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"  # 👈 Reemplaza con el nombre exacto del JSON
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = "Convocatorias Clima"
SHEET_CONVOCATORIAS = "Convocatorias Clima"
SHEET_FUENTES = "fuentes"

# === APP ===
app = Flask(__name__)

# === FUNCIONES ===
def es_url_valida(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME)

def ya_existe(sheet, titulo):
    titulos_existentes = sheet.col_values(1)
    return titulo.strip() in titulos_existentes

def extraer_datos(url):
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        titulo = soup.title.text.strip() if soup.title else "Sin título"
        contenido = soup.get_text()
        return titulo, contenido
    except Exception as e:
        print(f"❌ Error accediendo a {url}: {e}")
        return None, None

def traducir_texto(texto):
    try:
        return GoogleTranslator(source="auto", target="pt").translate(texto)
    except Exception as e:
        print(f"⚠️ Error al traducir: {e}")
        return texto

def agregar_convocatorias():
    print("🚀 Iniciando actualización de convocatorias...")
    sheet = conectar_sheets()
    hoja_conv = sheet.worksheet(SHEET_CONVOCATORIAS)
    hoja_fuentes = sheet.worksheet(SHEET_FUENTES)

    fuentes = hoja_fuentes.col_values(1)[1:]  # omitir encabezado

    for idx, fuente_url in enumerate(fuentes, start=2):
        fuente_url = fuente_url.strip()
        if not es_url_valida(fuente_url):
            print(f"❌ URL inválida en fila {idx}: {fuente_url}")
            continue

        titulo, contenido = extraer_datos(fuente_url)
        if not titulo or not contenido:
            print(f"❌ No se pudo extraer contenido de {fuente_url}")
            continue

        if ya_existe(hoja_conv, titulo):
            print(f"⏭️ Ya existe: {titulo}")
            continue

        traduccion = traducir_texto(contenido[:1000])
        hoja_conv.append_row([titulo, fuente_url, datetime.today().strftime('%Y-%m-%d'), traduccion])
        print(f"✅ Agregado: {titulo}")

# === RUTA PARA FLASK (UPTIME + EJECUCIÓN) ===
@app.route('/')
def home():
    try:
        agregar_convocatorias()
        return "✅ Bot ejecutado correctamente 🎉"
    except Exception as e:
        return f"❌ Error en ejecución: {e}"

# === EJECUTAR APP ===
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
