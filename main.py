import time
import requests
from flask import Flask
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateparser import parse
from googletrans import Translator
from gspread.exceptions import APIError

app = Flask(__name__)

CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"  # ← Asegúrate de que ese sea el nombre correcto de tu archivo JSON
SPREADSHEET_NAME = "Convocatorias Clima"

def conectar_sheets():
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    client = gspread.authorize(creds)
    return client

def traducir(texto, destino="pt"):
    try:
        traductor = Translator()
        resultado = traductor.translate(texto, dest=destino)
        return resultado.text
    except Exception as e:
        print(f"⚠️ Error al traducir: {e}")
        return texto

def extraer_fecha(texto):
    fecha = parse(texto, languages=['es', 'en', 'pt'])
    if fecha:
        return fecha.strftime('%Y-%m-%d')
    return ''

def scrape_fuente(nombre, url, tipo, idioma):
    print(f"🌐 Accediendo a: {url}")
    convocatorias = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        respuesta = requests.get(url, headers=headers, timeout=20)
        respuesta.raise_for_status()

        soup = BeautifulSoup(respuesta.text, "html.parser")
        bloques = soup.find_all(["article", "div", "section", "li", "tr", "td", "p"])

        for bloque in bloques:
            texto = bloque.get_text(separator=" ", strip=True)
            if any(palabra in texto.lower() for palabra in ["call", "convocatoria", "submit", "submission", "deadline", "apply", "aplica", "fecha límite", "fecha de cierre"]):
                fecha = extraer_fecha(texto)
                if fecha:
                    hoy = datetime.today().strftime('%Y-%m-%d')
                    if fecha >= hoy:
                        descripcion = texto.strip()
                        descripcion_pt = traducir(descripcion) if idioma.lower() != "portugués" else descripcion
                        convocatorias.append([
                            nombre,  # 🧠 Tópico
                            nombre,  # Entidad
                            fecha,
                            url,
                            idioma,
                            descripcion,
                            descripcion_pt
                        ])
        time.sleep(2)  # 😴 Evita sobrecargar
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")

    return convocatorias

def actualizar_convocatorias():
    try:
        gc = conectar_sheets()
        hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
        hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")

        print("📥 Obteniendo fuentes...")
        fuentes = hoja_fuentes.get_all_records()
        time.sleep(2)

        print("📥 Obteniendo registros ya existentes...")
        existentes = hoja_convocatorias.col_values(1)
        time.sleep(2)

        nuevas = []

        for fuente in fuentes:
            nombre = fuente["Nombre"]
            url = fuente["URL"]
            tipo = fuente["Tipo"]
            idioma = fuente["Idioma"]

            print(f"🔍 Procesando: {nombre}")
            try:
                resultados = scrape_fuente(nombre, url, tipo, idioma)
                for fila in resultados:
                    if fila[0] not in existentes:
                        nuevas.append(fila)
                        print(f"➕ Nueva convocatoria: {fila[0]}")
                    else:
                        print(f"🔁 Ya existe: {fila[0]}")
            except Exception as e:
                print(f"❌ Falló la fuente {nombre}: {e}")
            time.sleep(3)

        if nuevas:
            hoja_convocatorias.append_rows(nuevas)
            print(f"✅ {len(nuevas)} nuevas convocatorias agregadas.")
        else:
            print("📭 No hay convocatorias nuevas.")
    except APIError as e:
        print("🚨 Límite de peticiones alcanzado. Espera unos minutos.")
        print(e)

@app.route("/")
def home():
    actualizar_convocatorias()
    return "🤖 Bot de convocatorias ejecutado correctamente."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
