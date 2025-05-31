from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

app = Flask(__name__)

def agregar_convocatorias():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "eli-rv-7b7ef7f4f819.json", scope
    )
    client = gspread.authorize(creds)
    sheet = client.open("Convocatorias Clima").sheet1

    url = "https://www.fundsforngos.org/category/environment-2/climate-change/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    articulos = soup.find_all("h2", class_="entry-title")

    for art in articulos[:5]:
        titulo = art.text.strip()
        enlace = art.find("a")["href"]
        titulo_pt = GoogleTranslator(source="auto", target="pt").translate(titulo)
        sheet.append_row([
            titulo, "Funds For NGOs", "N/A", enlace, "Inglés", titulo_pt
        ])

@app.route("/")
def home():
    agregar_convocatorias()
    return "✅ BOT ejecutado y actualizado correctamente 🌎"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
