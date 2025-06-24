import os
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from flask import jsonify
from datetime import date, datetime, timedelta
import asyncio
import time
import feedparser
from openai import OpenAI
import json
from .utilities import get_time_stamp_HTML, french_date, fix_encoding, push_b2_file, format_datetime, log_msg, get_now_french
from email.utils import parsedate_to_datetime
import os

##################################################################
# GLOBAL VARIABLES

if os.path.abspath('.').endswith(('/app/', '/app')):
    BASE_FOLDER = '../app_files/meloir_files/'
else:
    BASE_FOLDER = 'app_files/meloir_files/'
HTML_FILE_PATH_LOCAL = os.path.abspath(BASE_FOLDER+"latest.html")
UPLOAD_FOLDER_LOCAL = os.path.abspath(BASE_FOLDER+"uploaded_files")
WORD_FOLDER_LOCAL = os.path.abspath(BASE_FOLDER+"uploaded_word")
HTML_FOLDER_LOCAL = os.path.abspath(BASE_FOLDER+"created_HTML")
UPLOAD_LOG_FILE_LOCAL = os.path.abspath(BASE_FOLDER+"upload_log.txt")
PATH_BULLETIN_LOCAL = os.path.abspath(BASE_FOLDER+'bulletin_paroissial.html')
READINGS_PATH_LAST_LOCAL = os.path.abspath(BASE_FOLDER+'readings_current.html')
READINGS_PATH_STORE_LOCAL = os.path.abspath(BASE_FOLDER+'readings_%s.html')
PERPLEXITY_TABLE_LAST_LOCAL = os.path.abspath(BASE_FOLDER+"evenements.html")
PERPLEXITY_TIMESTAMP_LOCAL = os.path.abspath(BASE_FOLDER+"evenements_MAJ.txt")
PERPLEXITY_TABLE_STORE_LOCAL = os.path.abspath(BASE_FOLDER+"evenements_%s.html")
NEWS_TABLE_LOCAL = os.path.abspath(BASE_FOLDER+"nouvelles_vatican.html")
NEWS_TIMESTAMP_LOCAL = os.path.abspath(BASE_FOLDER+"nouvelles_MAJ.txt")
SITE_HEARTBEAT_LOCAL = os.path.abspath(BASE_FOLDER+"site_heartbeat.txt")


os.makedirs(UPLOAD_FOLDER_LOCAL, exist_ok=True)
os.makedirs(WORD_FOLDER_LOCAL, exist_ok=True)
os.makedirs(HTML_FOLDER_LOCAL, exist_ok=True)
os.makedirs(BASE_FOLDER+"static", exist_ok=True)

# Create the base folder if it does not exist
if not os.path.exists(UPLOAD_LOG_FILE_LOCAL):
    with open(UPLOAD_LOG_FILE_LOCAL, "w", encoding="utf-8") as log:
        log.write("[INIT] Created log file\n")

# Show the paths
log_msg(f'Local file HTML_FILE_PATH_LOCAL = {HTML_FILE_PATH_LOCAL}')
log_msg(f'Local file UPLOAD_FOLDER_LOCAL = {UPLOAD_FOLDER_LOCAL}')
log_msg(f'local file WORD_FOLDER_LOCAL = {WORD_FOLDER_LOCAL}')
log_msg(f'local file HTML_FOLDER_LOCAL = {HTML_FOLDER_LOCAL}')
log_msg(f'local file UPLOAD_LOG_FILE_LOCAL = {UPLOAD_LOG_FILE_LOCAL}')
log_msg(f'local file PATH_BULLETIN_LOCAL = {PATH_BULLETIN_LOCAL}')
log_msg(f'local file READINGS_PATH_LAST_LOCAL = {READINGS_PATH_LAST_LOCAL}')
log_msg(f'local file READINGS_PATH_STORE_LOCAL = {READINGS_PATH_STORE_LOCAL}')
log_msg(f'local file PERPLEXITY_TABLE_LAST_LOCAL   = {PERPLEXITY_TABLE_LAST_LOCAL}')
log_msg(f'local file PERPLEXITY_TIMESTAMP_LOCAL = {PERPLEXITY_TIMESTAMP_LOCAL}')
log_msg(f'local file PERPLEXITY_TABLE_STORE_LOCAL = {PERPLEXITY_TABLE_STORE_LOCAL}')
log_msg(f'local file NEWS_TABLE_LOCAL = {NEWS_TABLE_LOCAL}')
log_msg(f'local file NEWS_TIMESTAMP_LOCAL = {NEWS_TIMESTAMP_LOCAL}')


##################################################################
# FUNCTION TO FETCH MASS SCHEDULE AND PROCESS
async def fetch_and_clean_schedule():
    url = "https://messes.info/horaires/paroisse%20notre%20dame%20du%20Bois%20Renou?display=TABLE"

    log_msg(f"Function Fetching mass schedule pid= {os.getpid()}")
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

    log_msg('Mass schedule done')
    return jsonify(clean_schedule)



##################################################################
# UTILITY FUNCTION - REFORMAT HTML TABLE
def reformat_html_table(html_code):
    # Define your CSS styles
    style = """
    <style>
      table {
        border-collapse: collapse;
        width: 100%;
      }
      th, td {
        border: none;
        border-bottom: 1px solid grey;
        padding: 8px;
        text-align: left;
      }
      th {
        color: #3579BE;
      }
    </style>
    """

    # Parse the HTML and add the style
    soup = BeautifulSoup(html_code, "html.parser")
    full_html = f"{style}{str(soup)}"
    return full_html


##################################################################
# SUBFUNCTION FOR READINGS: DATE OP NEXT SUNDAY
def get_next_sunday():
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    next_sunday = today + timedelta(days=days_until_sunday)
    return next_sunday.strftime('%Y-%m-%d')

##################################################################
# SUBFUNCTION FOR READINGS: GIVE CURRENT URL TO READ
def get_current_readings_URL():
    base_url = "https://levangileauquotidien.org/FR/gospel/"
    return base_url + get_next_sunday()


##################################################################
# SUB-FUNCTION TO FETCH READINGS VIA CHROMIUM
async def readings_extract_all_sections(url):
    log_msg("/fetch_readings async started")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            log_msg("/fetch_readings async opening URL")
            await page.goto(url)
            log_msg("/fetch_readings async opened URL")
            await page.wait_for_selector("h2")
            log_msg("/fetch_readings async selector")

            # Get all h2s (titles of sections like Première lecture, Cantique, etc.)
            titles = await page.query_selector_all("h2")
            result = []

            for title_el in titles:
                log_msg("/fetch_readings async title " + str(title_el))
                title_text = await title_el.inner_text()

                # Get the next sibling: h3 for reference
                parent = await title_el.evaluate_handle("node => node.parentElement")
                h3 = await parent.query_selector("h3")
                reference = await h3.inner_text() if h3 else ""

                # Now get the div.reading-text that follows the title
                # We'll look for the next sibling with that class
                reading_text_el = await parent.evaluate_handle('node => node.parentElement.querySelector(".reading-text")')
                text = await reading_text_el.inner_text() if reading_text_el else ""

                result.append({
                    "title": title_text,
                    "reference": reference,
                    "text": text
                })

            # Get the commentary separately
            comment_el = await page.query_selector("div.comment-text")
            commentary = await comment_el.inner_text() if comment_el else "(Pas de commentaire trouvé)"
            result.append({
                "title": "Commentaire",
                "reference": "",
                "text": commentary
            })

            await browser.close()
            return result
    except:
        return None

##################################################################
# MAIN FUNCTION TO FETCH READINGS
def fetch_readings():
    global z
    log_msg(f"Function fetch_readings pid= {os.getpid()}")
    url = get_current_readings_URL()
    log_msg(f"fetch_readings URL defined")
    try:
        readings = asyncio.get_event_loop().run_until_complete(readings_extract_all_sections(url))
        log_msg("/fetch_readings URL requested")
        if readings is None:
            full_text = ''
            log_msg("/fetch_readings content empty")
        else:
            log_msg("/fetch_readings content obtained")
            z = readings
            full_text = '<P>' + french_date(get_next_sunday()) + '</P?<BR>'
            log_msg("/fetch_readings starting sections")
            list_sections = ['1e lecture', 'Psaume', '2e lecture','Evangile']

            for i, r in enumerate(readings[:4]):
                log_msg("/fetch_readings processing section #%d" % i)
                full_text += '<div class="sqs-block-content">'
                full_text += f"<H3 class='sqs-block-title' style='color: rgb(55, 125, 197); margin-top: 2em; margin-bottom: 0.3em;'>{fix_encoding(list_sections[i])}</H3>\n"
                full_text += f"<I>{fix_encoding(r['title'])}</I><BR>\n"
                full_text += '<p>' + fix_encoding(r['text'])+'<BR></P>\n'
                full_text += '</DIV>'
        full_text += get_time_stamp_HTML()

    except Exception as e:
        log_msg("/fetch_readings error %s" % str(e))
        full_text = ''
    with open(READINGS_PATH_LAST_LOCAL, "w", encoding="utf-8") as f:
        f.write(full_text)
    log_msg(f"/fetch_readings local file written ({len(full_text)} length)")
    push_b2_file('meloir',READINGS_PATH_LAST_LOCAL, 'lectures.html')
    log_msg(f"/fetch_readings local file size {os.path.getsize(READINGS_PATH_LAST_LOCAL)} bytes")
    log_msg("/fetch_readings local file written uploaded to BB")

    with open(READINGS_PATH_STORE_LOCAL % get_next_sunday(), "w", encoding="utf-8") as f:
        f.write(full_text)
    push_b2_file('meloir',READINGS_PATH_STORE_LOCAL % get_next_sunday(), 'historique_lectures_%s.html' % get_next_sunday())
    log_msg('function fetch_readings done')
    return full_text



##################################################################
# FUNCTION CALLING PERPLEXITY TO FIND NEARBY EVENTS
def get_perplexity_events():
    log_msg(f'Function get_perplexity_events pid= {os.getpid()}')
    # Initialise the Perplexity connection
    api_key = os.getenv("PERPLEXITY_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

    # 1 -- Base query
    log_msg("Perplexity query step 1")
    query = "Pouvez-vous me donner la liste des événements religieux catholiques tels que pélerinages, processions, ou retraites organisés autour de Saint Malo ou du Mont Saint Michel, Saint Méloir des Ondes, l'abbaye de Beaufort (Plerguer) dans le mois à venir. Je souhaiterais au moins trois événements"
    response = client.chat.completions.create(
        model="llama-3.1-sonar-large-128k-online",  # Or another available Perplexity model
        messages=[
            {"role": "user", "content": query}
        ]
    )
    history = [
        {"role": "user", "content": query},
        {"role": "assistant", "content": response.choices[0].message.content}
    ]

    # 2 -- Add locations we like
    log_msg("Perplexity query step 2")
    query_additions = ("Si il y a des événements religieux catholiques pertinents dans le mois à venir dans les abbayes suivantes, pouvez-vous les ajouter à ce que vous venez de me donner? \n"
        "- Monastère de Beaufort (https://www.monastere-beaufort.com/accueil.php)\n"
        "- Abbaye de Saint Jacut (https://www.abbaye-st-jacut.com/)\n"
        "- Abbaye du Mont Saint Michel\n")
    history.append({"role": "user", "content": query_additions})
    response2 = client.chat.completions.create(
        model="llama-3.1-sonar-large-128k-online",
        messages=history
    )
    history.append({"role": "assistant", "content": response2.choices[0].message.content})

    # 3 -- Filter the results
    log_msg("Perplexity query step 3")
    results = response.choices[0].message.content+'\n\n'+response2.choices[0].message.content
    post_process_instruction = (
        "Voici les événements catholiques que vous avez trouvé:\n\n"
        f"{results}\n\n"
        "Veuillez filtrer cette liste pour n'inclure que les événements poru lesquels vous connaissez le lieu; pour lesquels le lieu est à moins de 100km de Saint Malo; et pour lesquels les dates sont disponibles "
    )
    history.append({"role": "user", "content": post_process_instruction})
    post_process_response = client.chat.completions.create(
        model="llama-3.1-sonar-large-128k-online",  # or your chosen model
        messages=history
    )
    history.append({"role": "assistant", "content": post_process_response.choices[0].message.content})

    # 4 -- Formatting
    log_msg("Perplexity query step 4")
    results_filtered = post_process_response.choices[0]
    formatting_instruction = (
        "Voici ce que vous avez trouvé:"
        f"{results}\n\n"
        "Donnez-moi s'il vous plaît une table HTML en français avec une ligne pour chaque événement, et des colonnes pour (a) Date; (b) Lieu; (c) Description; (d) lien URL (il doit uniquement apparaître le mot 'Cliquez ici'). N'incluez pas les citations / références. La table HTML ne doit pas montrer de lignes verticales, et les lignes horizontales doivent être grises. La ligne de titres doit utiliser la couleur RGB 3579BE pour les caractères (sur fond transparent)"
    )
    history.append({"role": "user", "content": formatting_instruction})
    formatted_response = client.chat.completions.create(
        model="llama-3.1-sonar-large-128k-online",  # or your chosen model
        messages=history
    )
    html_content = formatted_response.choices[0].message.content

    # 5 - Only keep the HTML content
    log_msg("Perplexity query step 5")
    html_content = html_content[html_content.upper().find('<TABLE'):html_content.upper().find('</TABLE')+8]

    # 5B - Reformat the HTML table
    log_msg("Perplexity query step 5b")
    html_content = reformat_html_table(html_content)

    # 6 - Check that the HTML code is correct
    log_msg("Perplexity query step 6")
    log_msg(f"Writing Perplexity HTML to local file {PERPLEXITY_TABLE_LAST_LOCAL}")
    with open(PERPLEXITY_TABLE_LAST_LOCAL, "wt") as f:
        f.write(html_content)
    log_msg("Perplexity query step 6b")
    dt = datetime.now().strftime("%Y-%m-%d")
    log_msg("Perplexity query step 6c")
    with open(PERPLEXITY_TABLE_STORE_LOCAL % dt, "wt") as f:
        f.write(html_content)
    log_msg("Perplexity query step 6d")
    log_msg("Perplexity query step 6e")
    log_msg("Perplexity query step 6f")
    with open(PERPLEXITY_TIMESTAMP_LOCAL, 'w') as f:
        f.write(get_now_french())
    log_msg("Perplexity query step 6g")
    push_b2_file('meloir',PERPLEXITY_TABLE_LAST_LOCAL,"evenements.html")
    log_msg("Perplexity query step 6h")
    push_b2_file('meloir',PERPLEXITY_TABLE_STORE_LOCAL % dt,"historique_evenements_%s.html" % dt)
    log_msg("Perplexity query step 6i")
    push_b2_file('meloir',PERPLEXITY_TIMESTAMP_LOCAL,"evenements_MAJ.txt")
    log_msg("Perplexity query step 6j")
    log_msg(f"Perplexity query done. HTML length {len(str(html_content))} characters, type {str(type(html_content))}")
    return html_content

    #except Exception as e:
    #    log_msg(f"Perplexity HTML incorrect {str(e)}")


##################################################################
# FUNCTION - FETCH VATICAN NEWS
def get_news():
    log_msg(f'Function get_news pid= {os.getpid()}')
    # URL of Vatican RSS
    rss_url = "https://www.vaticannews.va/fr.rss.xml"
    log_msg("Fetching Vatican news from " + rss_url)
    feed = feedparser.parse(rss_url)
    log_msg("Done with fetching Vatican news")

    # Start HTML table with inline CSS styling
    html = '''
    <table style="border-collapse: collapse; width: 100%;">
        <tr style="border-bottom: 1px solid lightgrey;">
            <th style="color: #3579BE; text-align: left; padding: 8px;">Date</th>
            <th style="color: #3579BE; text-align: left; padding: 8px;">Titre</th>
            <th style="color: #3579BE; text-align: left; padding: 8px;">Lien</th>
        </tr>
    '''

    # Add each news item
    log_msg("Going through each news entry...")
    for entry in feed.entries[:10]:
        log_msg(f"Processing news entry: {entry.title}")
        # Date of publication
        raw_date = entry.published
        pub_date = parsedate_to_datetime(raw_date)
        news_dt = format_datetime(pub_date, "EEE d MMMM y", locale='fr_FR')

        # Title of news
        news_title = entry.title

        # Link to article
        news_link = entry.link

        # Append to HTML table
        html += f'''
        <tr style="border-bottom: 1px solid lightgrey;">
            <td style="padding: 8px;">{news_dt}</td>
            <td style="padding: 8px;">{news_title}</td>
            <td style="padding: 8px;"><a href="{news_link}" target="_blank">Cliquez ici</a></td>
        </tr>
        '''

    # End of table
    log_msg("Finished processing news entries")
    html += '</table>'
    log_msg("Writing news to local file...")
    with open(NEWS_TABLE_LOCAL, "w") as f:
        f.write(html)
    log_msg("... done writing news to local file")
    with open(NEWS_TIMESTAMP_LOCAL, 'w') as f:
        f.write(get_now_french())
    log_msg("Pushing news file to B2...")
    push_b2_file('meloir',NEWS_TABLE_LOCAL,"nouvelles_vatican.html")
    log_msg("Pushing news timestamp to B2...")
    push_b2_file('meloir',NEWS_TIMESTAMP_LOCAL,"nouvelles_vatican_MAJ.txt")
    log_msg("Done with get_news()")

##################################################################
# CALL MASS SCHEDULE FUNCTION AND STORE
def call_mass_schedule_and_store():
    log_msg(f'Function call_mass_schedule_and_store pid= {os.getpid()}')
    data = asyncio.get_event_loop().run_until_complete(fetch_and_clean_schedule())

    # Save cleaned JSON
    with open(BASE_FOLDER+"static/schedule.json", "w", encoding="utf-8") as f:
        json.dump(data.get_json(), f, ensure_ascii=False, indent=2)

    # Upload JSON to BlackBlaze
    push_b2_file('meloir',BASE_FOLDER+"static/schedule.json","horaires_messes.json")

    # Save last updated timestamp in French format
    formatted = get_now_french()
    log_msg(f'Last updated timestamp: {formatted}')
    with open(BASE_FOLDER+"static/last_updated.txt", "w", encoding="utf-8") as f:
        f.write(formatted)
    push_b2_file('meloir',BASE_FOLDER+"static/last_updated.txt","horaires_messes_MAJ.txt")

    # Save heartbeat timestamp (ISO format)
    with open(BASE_FOLDER+"static/heartbeat.txt", "w") as hb:
        hb.write(now.isoformat())
    push_b2_file('meloir',BASE_FOLDER+"static/heartbeat.txt","heartbeat.txt")

    return f'Schedule updated static/schedule.json locally to <{BASE_FOLDER+"static/last_updated.txt"} and BB horaires_messes_MAJ.txt'

##################################################################
# WEB SITE HEARTBEAT
def heartbeat():
    log_msg(f'Function heartbeat pid= {os.getpid()}')
    msg_heartbeat = get_now_french()
    with open(SITE_HEARTBEAT_LOCAL, "wt") as hb:
        hb.write(msg_heartbeat)
    push_b2_file('meloir',SITE_HEARTBEAT_LOCAL,"site_heartbeat.txt")
    log_msg(f'Heartbeat updated to {msg_heartbeat}')
    return f'Heartbeat updated to {msg_heartbeat}'

##################################################################
# REGULAR CALL TO THE VATICAN NEWS QUERY
def periodic_query_vatican_news():
    time.sleep(27 * 60)
    while True:
        get_news()
        time.sleep(90 * 60)

##################################################################
# REGULAR CALL TO PERPLEXITY
def periodic_query_perplexity():
    time.sleep(2 * 60 * 60)
    while True:
        get_perplexity_events()
        time.sleep(24 * 60 * 60)

##################################################################
# REGULAR CALL TO THE READINGS QUERY
def periodic_query_readings():
    time.sleep(.25 * 60 * 60) 
    while True:
        fetch_readings()
        time.sleep(1 * 60 * 60)  # Sleep 1 hours

##################################################################
# REGULAR CALL TO THE MASS SCHEDULE
def periodic_query_mass_schedule():
    time.sleep(.7 * 60 * 60) 
    while True:
        call_mass_schedule_and_store()
        time.sleep(.5 * 60 * 60)  # Sleep 30 min

