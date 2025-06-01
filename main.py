from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from deep_translator import GoogleTranslator
import requests
from bs4 import BeautifulSoup
import datetime
import dateparser

# === Configuración Google Sheets ===
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_PATH = "eli-rv-0a9f3f56cefa.json"
SHEET_NAME = "Convocatorias Clima"


# === Conexión a Google Sheets ===
def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).worksheet("Convocatorias Clima")
    return sheet

# === Revisión para evitar duplicados ===
def ya_existe_en_sheets(titulo):
    sheet = conectar_sheets()
    titulos = sheet.col_values(1)
    return titulo in titulos

# === Función principal para scraping ===
def agregar_convocatorias():
    sheet = conectar_sheets()
    fuentes_sheet = gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    ).open(SHEET_NAME).worksheet("Fuentes")
    
    fuentes = fuentes_sheet.col_values(1)
    
    for fuente in fuentes:
        try:
            response = requests.get(fuente, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            # Título (flexible)
            titulo_element = soup.find("h1") or soup.find("title")
            if titulo_element:
                titulo = titulo_element.text.strip()
            else:
                titulo = "Título no disponible"

            # Fecha de cierre tentativa (flexible)
            texto_completo = soup.get_text()
            fecha_cierre = ""
            for palabra in texto_completo.split():
                if "/" in palabra or "-" in palabra:
                    try:
                        fecha = datetime.strptime(palabra.strip(), "%d/%m/%Y")
                        if fecha > datetime.now():
                            fecha_cierre = fecha.strftime("%d/%m/%Y")
                            break
                    except:
                        pass

            if not ya_existe_en_sheets(titulo):
                sheet.append_row([titulo, fuente, fecha_cierre])
                print(f"✅ Añadido: {titulo}")
            else:
                print(f"⛔ Ya existe: {titulo}")

        except Exception as e:
            print(f"❌ Error con {fuente}: {e}")

# === Traducción al portugués (columna adicional) ===
def traducir_columnas():
    sheet = conectar_sheets()
    valores = sheet.get_all_values()

    if len(valores[0]) < 4:
        sheet.update_cell(1, 4, "Título en portugués")

    for i in range(2, len(valores) + 1):
        if len(valores[i - 1]) >= 1:
            titulo = valores[i - 1][0]
            try:
                traduccion = GoogleTranslator(source='auto', target='pt').translate(titulo)
                sheet.update_cell(i, 4, traduccion)
                print(f"🌍 Traducido: {titulo}")
            except:
                print(f"⚠️ No se pudo traducir fila {i}")

# === Flask app ===
app = Flask(__name__)

@app.route("/")
def home():
    agregar_convocatorias()
    traducir_columnas()
    return "✅ Bot ejecutado correctamente desde la web 🎉"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
