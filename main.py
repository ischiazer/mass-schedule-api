from flask import Flask, jsonify
from bs4 import BeautifulSoup
import nest_asyncio
import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime

app = Flask(__name__)
nest_asyncio.apply()

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
                'Date': row['DATE'][5:],  # Remove prefix (e.g. "dim. ")
                'Jour': mapping_days.get(row['DATE'][:3], row['DATE'][:3]),
                'Heure': row['HEURE'],
                'Où': mapping_churches.get(row['LIEU DE CULTE'], row['LIEU DE CULTE']),
                'Célébration': row['LITURGIE']
            }
            clean_schedule.append(clean_row)
        except Exception:
            continue

    return jsonify(clean_schedule)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
