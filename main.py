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
from gspread.exceptions import APIError

app = Flask(__name__)

SPREADSHEET_NAME = "Convocatorias Clima"
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    return gspread.authorize(creds)

def traducir_texto(texto, idioma_origen="auto", idioma_destino="pt"):
    try:
        return GoogleTranslator(source=idioma_origen, target=idioma_destino).translate(texto)
    except Exception as e:
        print(f"⚠️ Error de traducción: {e}")
        return texto

def to_naive(dt):
    if dt and dt.tzinfo:
        return dt.replace(tzinfo=None)
    return dt

def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🔍 Procesando: {nombre}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links_con_fechas = []

    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        if not text:
            continue
        fechas = search_dates(text, languages=['en', 'es', 'fr', 'pt'])
        if fechas:
            for _, fecha in fechas:
                fecha_naive = to_naive(fecha)
                if fecha_naive and fecha_naive > datetime.now():
                    href = link["href"]
                    full_link = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                    links_con_fechas.append({
                        "fecha": fecha_naive,
                        "descripcion": text,
                        "link_directo": full_link
                    })

    convocatorias = []
    if links_con_fechas:
        for item in links_con_fechas:
            descripcion = item["descripcion"]
            descripcion_pt = traducir_texto(descripcion, idioma_origen=idioma, idioma_destino="pt")
            convocatorias.append([
                descripcion[:100],
                nombre,
                item["fecha"].strftime("%Y-%m-%d"),
                item["link_directo"],
                idioma,
                descripcion,
                descripcion_pt
            ])
            break
    else:
        print(f"📭 No se encontraron fechas con links en {nombre}")

    time.sleep(2)
    return convocatorias

def actualizar_convocatorias():
    retries = 3
    for intento in range(retries):
        try:
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
            return
        except APIError as e:
            if "429" in str(e):
                print(f"⚠️ API limit reached. Esperando antes de reintentar... ({intento+1}/{retries})")
                time.sleep(60)  # Esperar 1 minuto antes de reintentar
            else:
                raise e
    print("❌ No se pudo completar la operación tras varios intentos.")

@app.route("/")
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

@app.route("/health")
def health():
    return "✅ OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
