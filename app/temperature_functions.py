import logging
from playwright.async_api import async_playwright
import pandas as pd, numpy as np
from datetime import date, datetime
from .utilities import download_file_from_b2, push_b2_file
import asyncio


##################################################################
# GLOBAL VARIABLES
BASE_FOLDER = 'app_files/meloir_files/'
TEMPERATURE_CSV = BASE_FOLDER+'temperatures.csv'


##################################################################
# SUB-FUNCTION - RETURN LIST OF CITIES FOR WHICH TEMPERATURE IS NEEDED

def get_city_mapping():
    mapping_city_url = {'Den Haag': "https://www.seatemperature.org/europe/netherlands/scheveningen.htm",
                        "Egmond":"https://www.seatemperature.org/europe/netherlands/egmond-aan-zee.htm",
                        "Vlieland":"https://www.seatemperature.org/europe/netherlands/oost-vlieland.htm",
                        "Knokke":"https://www.seatemperature.org/europe/belgium/knokke-heist.htm",
                        "Penzance":"https://www.seatemperature.org/europe/united-kingdom/penzance.htm",
                        "Falmouth":"https://www.seatemperature.org/europe/united-kingdom/falmouth.htm",
                        "Brighton": "https://www.seatemperature.org/europe/united-kingdom/brighton.htm",
                        "Helgoland":"https://www.seatemperature.org/europe/germany/helgoland.htm",
                        "Saint Malo": "https://www.seatemperature.org/europe/france/saint-malo.htm",
                        "Cancale":"https://www.seatemperature.org/europe/france/cancale.htm",
                        "Saint Lunaire":"https://www.seatemperature.org/europe/france/saint-lunaire.htm",
                        "Cabourg":"https://www.seatemperature.org/europe/france/cabourg.htm",
                        "Honfleur":"https://www.seatemperature.org/europe/france/honfleur.htm",
                        "Benodet":"https://www.seatemperature.org/europe/france/benodet.htm",
                        "Quiberon": "https://www.seatemperature.org/europe/france/quiberon.htm",
                        "Saint Jean de Luz":"https://www.seatemperature.org/europe/france/saint-jean-de-luz.htm",
                        "Lavandou":"https://www.seatemperature.org/europe/france/le-lavandou.htm",
                        "Antibes":"https://www.seatemperature.org/europe/france/antibes.htm",
                        "Carqueiranne": "https://www.seatemperature.org/europe/france/carqueiranne.htm",
                        "Biarritz":"https://www.seatemperature.org/europe/france/biarritz.htm",
                        "Ile Rousse":"https://www.seatemperature.org/europe/france/lile-rousse.htm",
                        "Toulon": "https://www.seatemperature.org/europe/france/toulon.htm",
                        "Sorrento":"https://www.seatemperature.org/europe/italy/sorrento.htm",
                        "Rapallo":"https://www.seatemperature.org/europe/italy/rapallo.htm",
                        "Ischia":"https://www.seatemperature.org/europe/italy/ischia.htm",
                        "Catania":"https://www.seatemperature.org/europe/italy/catania.htm",
                        "Heraklion":"https://www.seatemperature.org/europe/greece/irkleion.htm",
                        "Rhodes":"https://www.seatemperature.org/europe/greece/rodos.htm",
                        "Corfu":"https://www.seatemperature.org/europe/greece/corfu.htm",
                        "Cascais":"https://www.seatemperature.org/europe/portugal/cascais.htm",
                        "Albufeira":"https://www.seatemperature.org/europe/portugal/albufeira.htm",
                        }
    return mapping_city_url

##################################################################
# SUB-FUNCTION - GET FROM WEB HTML FILE WITH TEMPERATURE FOR ONE CITY
async def temperature_fetch_full_text(city):
    logging.info("[City] " + str(city) + ' start')
    url = get_city_mapping()[city]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_selector("body")  # Wait for the main body to load
        logging.info("[City] " + str(city) + ' end')
        return await page.inner_text("body")

##################################################################
# SUB-FUNCTION - GET FROM WEB CURRENT TEMPERATURE
async def temperature_current():
    logging.info("[Current temp] Start]")
    dt_str = datetime.today().strftime('%Y-%m-%d')
    temps = pd.DataFrame(index=[k for k in get_city_mapping()], columns=[dt_str])
    for city in temps.index:
        try:
            html = await temperature_fetch_full_text(city)
            html = html[html.index('(Today)'):]
            html = html[:html.index('°C')]
            html = html[html.index('\n')+1:]
            t = float(html)
        except Exception as e:
            logging.warning(f"Failed to fetch temperature for {city}: {e}")
            t = np.nan
        temps.loc[city, dt_str] = t
    logging.info("[Current temp] End]")
    return temps

##################################################################
# FUNCTION - UPDATE SEA TEMPERATURE FILE
def update_temperatures():
    # Load existing history of temperatures
    logging.info("Downloading temperature file...")
    download_file_from_b2('temperature',TEMPERATURE_CSV, TEMPERATURE_CSV)
    logging.info("Done")
    temps_existing = pd.read_csv(TEMPERATURE_CSV,index_col=0)
    logging.info("Converted to dataframe")

    # Get current temperatures
    logging.info("Getting current...")
    temps_new = asyncio.run(temperature_current())
    logging.info("...done")

    # Add current temperatures to existing
    logging.info("Joining...")
    if temps_new.columns[0] in temps_existing.columns:
        logging.info('Date %s already present' % str(temps_new.columns[0]))
        temps_updated = temps_existing.copy()
        logging.info('copied')
    else:
        logging.info('Starting join...')
        temps_updated = temps_new.join(temps_existing, how='outer')
        logging.info('...done joining')
    logging.info("...Done")

    # Save and upload
    logging.info("Saving CSV...")
    temps_updated.to_csv(TEMPERATURE_CSV)
    logging.info("...Done")
    logging.info("Pushing BB file...")
    push_b2_file('temperature',TEMPERATURE_CSV,TEMPERATURE_CSV)
    logging.info("...Done")

##################################################################
# FUNCTION: CALL THE SEA TEMPERATURE UPDATE
def force_fetch_temperature():
    logging.info("force_fetch_temperature")
    update_temperatures()

##################################################################
# REGULAR CALL TO THE SEA TEMPERATURE
async def periodic_query_temperature():
    while True:
        try:
            update_temperatures()
        except Exception as e:
            logging.warning(f"Periodic fetch of temperature failed: {e}")
        await asyncio.sleep(60 * 60 * 12)   

##################################################################
# FUNCTION CALLED BY THE THREADING LOOP
def background_loop_temperature():
    logging.info("/start_background_loop_temperature 1")
    loop = asyncio.new_event_loop()
    logging.info("/start_background_loop_temperature 2")
    asyncio.set_event_loop(loop)
    logging.info("/start_background_loop_temperature 3")
    loop.run_until_complete(periodic_query_temperature())
    logging.info("/start_background_loop_temperature 4")
