from flask import Flask, jsonify, request, send_file, Response
from bs4 import BeautifulSoup
import nest_asyncio
import asyncio
from playwright.async_api import async_playwright
import json
import os
import base64
from datetime import datetime
from flask_cors import CORS  # ✅ CORS import

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
HTML_FILE_PATH = "latest.html"
UPLOAD_FOLDER = "uploaded_files"
UPLOAD_LOG_FILE = "upload_log.txt"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CORS(app, resources={r"/*": {"origins": "*"}})

# Create the log file if it doesn't exist
if not os.path.exists(UPLOAD_LOG_FILE):
    with open(UPLOAD_LOG_FILE, "w", encoding="utf-8") as log:
        log.write("[INIT] Created log file\n")

nest_asyncio.apply()

def log_upload(status, filename, detail=""):
    timestamp = datetime.utcnow().isoformat()
    log_line = f"[{timestamp}] {status.upper()}: {filename} {detail}".strip() + "\n"
    with open(UPLOAD_LOG_FILE, "a", encoding="utf-8") as log:
        log.write(log_line)


@app.route('/')
def home():
    return "Mass Schedule API is running!"

@app.route('/schedule')
def get_schedule():
    return asyncio.get_event_loop().run_until_complete(fetch_and_clean_schedule())

@app.route('/refresh')
def refresh_schedule():
    data = asyncio.get_event_loop().run_until_complete(fetch_and_clean_schedule())

    os.makedirs("static", exist_ok=True)

    # Save cleaned JSON
    with open("static/schedule.json", "w", encoding="utf-8") as f:
        json.dump(data.get_json(), f, ensure_ascii=False, indent=2)

    # Save last updated timestamp in French format
    now = datetime.now()
    formatted = now.strftime("%A %d %B %Y à %H:%M")
    with open("static/last_updated.txt", "w", encoding="utf-8") as f:
        f.write(formatted)

    # Save heartbeat timestamp (ISO format)
    with open("static/heartbeat.txt", "w") as hb:
        hb.write(now.isoformat())

    return "Schedule updated and saved to static/schedule.json"

async def fetch_and_clean_schedule():
    url = "https://messes.info/horaires/paroisse%20notre%20dame%20du%20Bois%20Renou?display=TABLE"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("tr td:nth-child(7)", timeout=15000)
        content = await page.content()
        await browser.close()

    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")

    mass_schedule = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 7:
            mass_schedule.append({
                "CP": cells[0].get_text(strip=True),
                "COMMUNE": cells[1].get_text(strip=True),
                "LIEU DE CULTE": cells[2].get_text(strip=True),
                "PAROISSE": cells[3].get_text(strip=True),
                "DATE": cells[4].get_text(strip=True),
                "HEURE": cells[5].get_text(strip=True),
                "LITURGIE": cells[6].get_text(strip=True),
            })

    # Clean and format
    mapping_churches = {
        'Église Notre Dame de la Visitation': 'Hirel',
        "Église Notre-Dame de l'Assomption": 'La Gouesnière',
        'Église Saint-Benoit': 'Saint Benoît',
        'Église Saint-Louis': 'Vildé La Marine',
        'Église Saint-Méen-et-Sainte-Croix': 'La Fresnais',
        'Église Saint-Méloir': 'Saint Méloir'
    }

    mapping_days = {
        'lun': 'Lundi', 'mar': 'Mardi', 'mer': 'Mercredi',
        'jeu': 'Jeudi', 'ven': 'Vendredi', 'sam': 'Samedi', 'dim': 'Dimanche'
    }

    clean_schedule = []
    for row in mass_schedule:
        try:
            clean_row = {
                'Date': row['DATE'][5:],  # Remove "dim. ", etc.
                'Jour': mapping_days.get(row['DATE'][:3], row['DATE'][:3]),
                'Heure': row['HEURE'],
                'Où': mapping_churches.get(row['LIEU DE CULTE'], row['LIEU DE CULTE']),
                'Célébration': row['LITURGIE']
            }
            clean_schedule.append(clean_row)
        except Exception:
            continue

    return jsonify(clean_schedule)

@app.route("/upload_html", methods=["POST"])
def upload_html():
    html_content = request.get_data(as_text=True)
    with open(HTML_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    return "HTML saved", 200

@app.route("/latest")
def latest():
    if os.path.exists(HTML_FILE_PATH):
        return send_file(HTML_FILE_PATH, mimetype="text/html")
    else:
        return "No HTML uploaded yet.", 404

@app.route("/upload_attachment", methods=["POST"])
def upload_attachment():
    uploaded_file = request.files.get("file")
    filename = request.form.get("filename")

    if not uploaded_file or not filename:
        log_upload("FAIL", filename or "unknown", "Missing file or filename in multipart/form-data")
        return "Missing file or filename", 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        uploaded_file.save(filepath)

        log_upload("SUCCESS", filename)
        return f"✅ File '{filename}' saved", 200

    except Exception as e:
        log_upload("FAIL", filename, str(e))
        return f"❌ Error saving file: {str(e)}", 500


@app.route("/upload_log")
def show_log():
    if not os.path.exists(UPLOAD_LOG_FILE):
        return "No log available yet.", 404

    with open(UPLOAD_LOG_FILE, "r", encoding="utf-8") as f:
        log_content = f.read()

    return Response(f"<pre>{log_content}</pre>", mimetype="text/html")

@app.errorhandler(413)
def request_entity_too_large(error):
    return "❌ File too large. Limit is 10MB.", 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
