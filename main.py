import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from deep_translator import GoogleTranslator

# --- Configuración ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_PATH = 'eli-rv-0a9f3f56cefa.json'  # <-- Reemplaza esto con el nombre real del archivo .json
SPREADSHEET_NAME = 'Convocatorias Clima'

# --- Conectar a Google Sheets ---
def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    cliente = gspread.authorize(creds)
    return cliente

# --- Validar URL ---
def es_url_valida(url):
    return url.startswith("http://") or url.startswith("https://")

# --- Scraping simplificado ---
def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🌐 Revisando fuente: {nombre} ({url})")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(url, headers=headers, timeout=20)
        html = response.text.lower()

        # Bloquear páginas no válidas
        bloqueos = [
            "cloudflare", "access denied", "enable javascript", "just a moment",
            "ray id", "403 forbidden", "cookies to continue", "digitar", "entrar", "biblioteca"
        ]
        if any(p in html for p in bloqueos):
            print(f"🚫 Página protegida o vacía: {url}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        # Filtrar si el texto útil no contiene términos esperados
        if not any(keyword in text.lower() for keyword in ["convocatoria", "call for", "papers", "envío", "deadline", "fecha límite", "submissions"]):
            print(f"⚠️ No contiene términos útiles, descartada: {url}")
            return []

        titulo = soup.title.text.strip() if soup.title else f"Convocatoria de {nombre}"
        descripcion = text[:1000]
        descripcion_pt = GoogleTranslator(source='auto', target='pt').translate(descripcion)
        hoy = datetime.today().strftime('%Y-%m-%d')

        return [[
            titulo,
            nombre,
            hoy,
            url,
            idioma,
            descripcion,
            descripcion_pt
        ]]

    except Exception as e:
        print(f"❌ Error procesando {nombre}: {e}")
        return []
        
# --- Actualizar hoja ---
def actualizar_convocatorias():
    gc = conectar_sheets()
    hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")

    fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(1)  # Tópico

    nuevas = []

    for fuente in fuentes:
        if not all(k in fuente for k in ["Nombre", "URL", "Tipo", "Idioma"]):
            print(f"⚠️ Encabezado faltante en fuente: {fuente}")
            continue

        nombre = fuente.get("Nombre", "").strip()
        url = fuente.get("URL", "").strip()
        tipo = fuente.get("Tipo", "").strip()
        idioma = fuente.get("Idioma", "").strip()

        if not es_url_valida(url):
            print(f"⚠️ URL inválida: {url}")
            continue

        nuevas_conv = scrape_fuente(nombre, url, tipo, idioma)

        for conv in nuevas_conv:
            if conv[0] not in existentes:
                nuevas.append(conv)
            else:
                print(f"🔁 Duplicado omitido: {conv[0]}")

    if nuevas:
        hoja_convocatorias.append_rows(nuevas)
        print(f"✅ {len(nuevas)} nuevas convocatorias agregadas.")
    else:
        print("📭 No hay nuevas convocatorias para agregar.")

# --- Ejecutar ---
if __name__ == '__main__':
    actualizar_convocatorias()
