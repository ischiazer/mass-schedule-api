import os
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from flask import jsonify
from datetime import date, datetime, timedelta
import logging
import asyncio
import time
import feedparser
from openai import OpenAI
from .utilities import get_time_stamp_HTML, french_date, fix_encoding, push_b2_file, format_datetime
from email.utils import parsedate_to_datetime


##################################################################
# INITIALISATION
HTML_FILE_PATH = "latest.html"
UPLOAD_FOLDER = "uploaded_files"
WORD_FOLDER = "uploaded_word"
HTML_FOLDER = "created_HTML"
UPLOAD_LOG_FILE = "upload_log.txt"
PATH_BULLETIN = 'bulletin_paroissial.html'
READINGS_PATH_LAST = 'readings_current.html'
READINGS_PATH_STORE = 'readings_%s.html'
PERPLEXITY_TABLE_LAST = "evenements.html"
PERPLEXITY_TIMESTAMP = "evenements_MAJ.txt"
PERPLEXITY_TABLE_STORE = "evenements_%s.html"
NEWS_TABLE = "nouvelles_vatican.html"
NEWS_TIMESTAMP = "nouvelles_MAJ.txt"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WORD_FOLDER, exist_ok=True)
os.makedirs(HTML_FOLDER, exist_ok=True)
if not os.path.exists(UPLOAD_LOG_FILE):
    with open(UPLOAD_LOG_FILE, "w", encoding="utf-8") as log:
        log.write("[INIT] Created log file\n")



##################################################################
# FUNCTION TO FETCH MASS SCHEDULE AND PROCESS
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
    logging.info("/fetch_readings async started")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            logging.info("/fetch_readings async opening URL")
            await page.goto(url)
            logging.info("/fetch_readings async opened URL")
            await page.wait_for_selector("h2")
            logging.info("/fetch_readings async selector")

            # Get all h2s (titles of sections like Première lecture, Cantique, etc.)
            titles = await page.query_selector_all("h2")
            result = []

            for title_el in titles:
                logging.info("/fetch_readings async title " + str(title_el))
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
    url = get_current_readings_URL()
    logging.info("/fetch_readings URL defined")
    try:
        readings = asyncio.get_event_loop().run_until_complete(readings_extract_all_sections(url))
        logging.info("/fetch_readings URL requested")
        if readings is None:
            full_text = ''
            logging.info("/fetch_readings content empty")
        else:
            logging.info("/fetch_readings content obtained")
            z = readings
            full_text = '<P>' + french_date(get_next_sunday()) + '</P?<BR>'
            logging.info("/fetch_readings starting sections")
            list_sections = ['1e lecture', 'Psaume', '2e lecture','Evangile']

            for i, r in enumerate(readings[:4]):
                logging.info("/fetch_readings processing section #%d" % i)
                full_text += '<div class="sqs-block-content">'
                full_text += f"<H3 class='sqs-block-title' style='color: rgb(55, 125, 197); margin-top: 2em; margin-bottom: 0.3em;'>{fix_encoding(list_sections[i])}</H3>\n"
                full_text += f"<I>{fix_encoding(r['title'])}</I><BR>\n"
                full_text += '<p>' + fix_encoding(r['text'])+'<BR></P>\n'
                full_text += '</DIV>'
        full_text += get_time_stamp_HTML()

    except Exception as e:
        logging.info("/fetch_readings error %s" % str(e))
        full_text = ''
    with open(READINGS_PATH_LAST, "w", encoding="utf-8") as f:
        f.write(full_text)
    logging.info(f"/fetch_readings local file written ({len(full_text)} length)")
    push_b2_file('meloir',READINGS_PATH_LAST, 'lectures.html')
    logging.info(f"/fetch_readings local file size {os.path.getsize(READINGS_PATH_LAST)} bytes")
    logging.info("/fetch_readings local file written uploaded to BB")

    with open(READINGS_PATH_STORE % get_next_sunday(), "w", encoding="utf-8") as f:
        f.write(full_text)
    push_b2_file('meloir',READINGS_PATH_STORE % get_next_sunday(), 'historique_lectures_%s.html' % get_next_sunday())
    return full_text


##################################################################
# REGULAR CALL TO THE READINGS QUERY
def periodic_query_readings():
    while True:
        fetch_readings()
        time.sleep(1 * 60 * 60)  # Sleep 1 hours

##################################################################
# FUNCTION CALLING PERPLEXITY TO FIND NEARBY EVENTS
def get_perplexity_events():
    # Initialise the Perplexity connection
    api_key = os.getenv("PERPLEXITY_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

    # 1 -- Base query
    logging.info("Perplexity query step 1")
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
    logging.info("Perplexity query step 2")
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
    logging.info("Perplexity query step 3")
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
    logging.info("Perplexity query step 4")
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
    logging.info("Perplexity query step 5")
    html_content = html_content[html_content.upper().find('<TABLE'):html_content.upper().find('</TABLE')+8]

    # 5B - Reformat the HTML table
    logging.info("Perplexity query step 5b")
    html_content = reformat_html_table(html_content)

    # 6 - Check that the HTML code is correct
    logging.info("Perplexity query step 6")
    #try:
    #    soup = BeautifulSoup(html_content, "html5lib")
    #    print("HTML parsed successfully — no fatal errors.")
    with open(PERPLEXITY_TABLE_LAST, "w") as f:
        f.write(html_content)
    logging.info("Perplexity query step 6b")
    dt = datetime.now().strftime("%Y-%m-%d")
    logging.info("Perplexity query step 6c")
    with open(PERPLEXITY_TABLE_STORE % dt, "w") as f:
        f.write(html_content)
    logging.info("Perplexity query step 6d")
    logging.info("Perplexity query step 6e")
    time_now = datetime.now()
    logging.info("Perplexity query step 6f")
    with open(PERPLEXITY_TIMESTAMP, 'w') as f:
        f.write(time_now.strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("Perplexity query step 6g")
    push_b2_file('meloir',PERPLEXITY_TABLE_LAST,"evenements.html")
    logging.info("Perplexity query step 6h")
    push_b2_file('meloir',PERPLEXITY_TABLE_STORE % dt,"historique_evenements_%s.html" % dt)
    logging.info("Perplexity query step 6i")
    push_b2_file('meloir',PERPLEXITY_TIMESTAMP,"evenements_MAJ.txt")
    logging.info("Perplexity query step 6j")
    logging.info("Perplexity query done")
    return html_content

    #except Exception as e:
    #    logging.info(f"Perplexity HTML incorrect {str(e)}")


##################################################################
# FUNCTION - FETCH VATICAN NEWS
def get_news():
    # URL of Vatican RSS
    rss_url = "https://www.vaticannews.va/fr.rss.xml"
    feed = feedparser.parse(rss_url)

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
    for entry in feed.entries[:10]:
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
    html += '</table>'
    with open(NEWS_TABLE, "w") as f:
        f.write(html)
    time_now = datetime.now()
    with open(NEWS_TIMESTAMP, 'w') as f:
        f.write(time_now.strftime("%Y-%m-%d %H:%M:%S"))
    push_b2_file('meloir',NEWS_TABLE,"nouvelles_vatican.html")
    push_b2_file('meloir',NEWS_TIMESTAMP,"nouvelles_vatican_MAJ.txt")



##################################################################
# REGULAR CALL TO THE VATICAN NEWS QUERY
def periodic_query_vatican_news():
    while True:
        get_news()
        time.sleep(90 * 60)

##################################################################
# REGULAR CALL TO PERPLEXITY
def periodic_query_perplexity():
    while True:
        get_perplexity_events()
        time.sleep(24 * 60 * 60)
