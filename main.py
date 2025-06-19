from flask import Flask
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import time
import dateparser
from dateparser.search import search_dates
from datetime import datetime
from deep_translator import GoogleTranslator
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

app = Flask(__name__)

# === INSTALAR DEPENDENCIAS NECESARIAS ===
# pip install sumy

# === CONFIGURACIÓN ===
SPREADSHEET_NAME = "Convocatorias Clima"
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
PALABRAS_CLAVE = [
    'call for papers', 'submit your proposal', 'funding opportunity',
    'grant application', 'deadline', 'submission', 'research',
    'sustainability', 'climate change', 'environment', 'agribusiness'
]

# === FUNCIONES ===

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    return gspread.authorize(creds)

def traducir_texto(texto):
    try:
        return GoogleTranslator(source="auto", target="pt").translate(texto)
    except Exception as e:
        print(f"⚠️ Error de traducción: {e}")
        return texto

def resumir_texto(texto, lineas=2):
    try:
        parser = PlaintextParser.from_string(texto, Tokenizer("english"))
        summarizer = LsaSummarizer()
        resumen = summarizer(parser.document, lineas)
        return " ".join(str(s) for s in resumen)
    except Exception:
        return texto[:300]

def scrape_fuente(nombre, url, tipo):
    print(f"🔍 Procesando: {nombre}")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    text_content = soup.get_text(" ").strip()

    convocatorias = []
    now = datetime.now().astimezone()
    candidatos = []

    # Buscar bloques con fecha y palabra clave
    for tag in soup.find_all(['p', 'li', 'div', 'article']):
        txt = tag.get_text(" ").strip()
        if any(kw in txt.lower() for kw in PALABRAS_CLAVE):
            fechas = search_dates(txt, languages=['en', 'es', 'fr', 'pt']) or []
            for t, f in fechas:
                if f.tzinfo is None:
                    f = f.replace(tzinfo=now.tzinfo)
                if f > now:
                    candidatos.append((f, txt, tag))
    if not candidatos:
        print(f"📭 No se encontraron bloques válidos en {nombre}")
        return []

    # Tomar la convocatoria más próxima
    fecha, bloque, tag = sorted(candidatos, key=lambda x: x[0])[0]
    resumen = resumir_texto(bloque, lineas=2)

    # Buscar enlace directo
    enlace = ""
    for a in tag.find_all('a', href=True):
        href = a['href']
        if any(kw in href.lower() for kw in ['call', 'grant', 'submit', 'fund']):
            enlace = requests.compat.urljoin(url, href)
            break

    descripcion_pt = traducir_texto(resumen)
    convocatorias.append([
        resumen[:100],
        nombre,
        fecha.strftime("%Y-%m-%d"),
        enlace or url,
        resumen,
        descripcion_pt
    ])
    print(f"✅ Convocatoria encontrada: {fecha.strftime('%Y-%m-%d')}")

    time.sleep(2)
    return convocatorias

def actualizar_convocatorias():
    print("📡 Conectando con Google Sheets...")
    gc = conectar_sheets()
    hoja = gc.open(SPREADSHEET_NAME)
    fuentes = hoja.worksheet("Fuentes").get_all_records()
    hoja_conv = hoja.worksheet("Convocatorias Clima")
    existentes = hoja_conv.col_values(1)
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
                print(f"🔁 Omitiendo duplicada: {conv[0]}")

    if nuevas:
        hoja_conv.append_rows(nuevas)
        print(f"📝 Agregadas {len(nuevas)} nuevas convocatorias.")
    else:
        print("📭 No hay nuevas convocatorias para agregar.")
    time.sleep(2)

@app.route('/')
def home():
    actualizar_convocatorias()
    return "✅ Bot ejecutado correctamente."

@app.route('/health')
def health():
    return "🟢 OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
