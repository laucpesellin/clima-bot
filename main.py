import requests
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Autenticación Google Sheets ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_PATH = 'eli-rv-0a9f3f56cefa.json'  # Ajusta con el nombre real del .json
SPREADSHEET_NAME = 'Convocatorias Clima'

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
    cliente = gspread.authorize(creds)
    return cliente

def scrape_fuente(nombre, url, tipo, idioma):
    try:
        print(f"🌐 Revisando fuente: {nombre} ({url})")
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Aquí ajusta los selectores según el sitio real
        convocatorias = soup.find_all('article') or soup.find_all('div')
        
        if not convocatorias:
            print(f"🚫 No se encontraron convocatorias en {nombre}")
            return []

        resultados = []
        for c in convocatorias:
            titulo = c.text.strip()[:80]
            fecha = datetime.today().strftime('%Y-%m-%d')  # 👈 Ajusta si encuentras fecha real
            resultados.append([titulo, url, tipo, idioma, fecha])
        
        print(f"✅ Encontradas {len(resultados)} convocatorias en {nombre}")
        return resultados

    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")
        return []

def actualizar_convocatorias():
    gc = conectar_sheets()
    hoja_fuentes = gc.open(SPREADSHEET_NAME).worksheet("Fuentes")
    hoja_convocatorias = gc.open(SPREADSHEET_NAME).worksheet("Convocatorias Clima")
    
    Fuentes = hoja_fuentes.get_all_records()
    existentes = hoja_convocatorias.col_values(1)

    nuevas = []

    for fuente in Fuentes:
        nombre = fuente["Nombre"]
        url = fuente["URL"]
        tipo = fuente["Tipo"]
        idioma = fuente["Idioma"]

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

# Llama la función
actualizar_convocatorias()
