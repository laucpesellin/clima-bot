from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from deep_translator import GoogleTranslator
import requests
from bs4 import BeautifulSoup

# Ruta al archivo de credenciales JSON
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"

# Nombre del Google Sheet
SPREADSHEET_NAME = "Convocatorias Clima"

def conectar_sheets():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SPREADSHEET_NAME).sheet1
    return sheet

def traducir_descripcion(texto):
    try:
        return GoogleTranslator(source='auto', target='pt').translate(texto)
    except:
        return "⚠️ No se pudo traducir"

def agregar_convocatorias():
    sheet = conectar_sheets()
    convocatorias = [
        {
            "titulo": "Nature & Climate AI Challenge",
            "organizacion": "iCS",
            "fechaCierre": "30/06/2025",
            "enlace": "https://www2.fundsforngos.org/awards/ics-announces-nature-climate-ai-challenge-in-brazil/",
            "idioma": "Inglés",
            "descripcion": "Apoya tecnologías digitales aplicadas a desafíos climáticos y ambientales en Brasil."
        },
        {
            "titulo": "FONTAGRO 2025",
            "organizacion": "FONTAGRO",
            "fechaCierre": "31/12/2025",
            "enlace": "https://bio-emprender.iica.int/iica-opportunities/convocatoria-2025-fontagro/",
            "idioma": "Español",
            "descripcion": "Proyectos agro resilientes y sostenibles frente al cambio climático en América Latina."
        }
    ]

    for c in convocatorias:
        descripcion_pt = traducir_descripcion(c["descripcion"])
        sheet.append_row([
            c["titulo"],
            c["organizacion"],
            c["fechaCierre"],
            c["enlace"],
            c["idioma"],
            c["descripcion"],
            descripcion_pt
        ])

def agregar_publicaciones():
    sheet = conectar_sheets()

    revistas = [
        {
            "url": "https://www.mdpi.com/journal/agronomy",
            "nombre": "MDPI Agronomy"
        },
        {
            "url": "https://revistas.inia.cl/index.php/chileangj",
            "nombre": "Chilean Journal of Agricultural Research"
        }
    ]

    for revista in revistas:
        try:
            response = requests.get(revista["url"], timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            titulos = soup.find_all("h3")[:1]

            for titulo in titulos:
                sheet.append_row([
                    f"Artículo científico: {titulo.text.strip()}",
                    revista["nombre"],
                    "Sin fecha",
                    revista["url"],
                    "Inglés",
                    "Artículo reciente en agronegocios y clima",
                    traducir_descripcion("Artículo reciente en agronegocios y clima")
                ])
        except Exception as e:
            print(f"❌ Error con {revista['nombre']}: {e}")

# === Función Principal ===
def main():
    agregar_convocatorias()
    agregar_publicaciones()
    print("✅ BOT ejecutado correctamente 🎉")

main()

# === Flask App para Render ===
app = Flask(__name__)

@app.route('/')
def home():
    main()
    return "✅ Bot ejecutado correctamente desde la web 🌐"

app.run(host='0.0.0.0', port=8080)
