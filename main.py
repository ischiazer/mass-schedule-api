from flask import Flask, jsonify
from bs4 import BeautifulSoup
import nest_asyncio
import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime
from flask_cors import CORS  # ✅ CORS import

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://www.boisrenou.fr"]}})  # ✅ Allow Squarespace domain

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
    url = "https://messes.info/horaires/paroisse%20notre%20dame%20du%20Bo
