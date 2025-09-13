from openai import OpenAI
import os, requests, time, tempfile, pytz, nest_asyncio
import asyncio
import openai
from datetime import datetime
from babel.dates import format_datetime
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from flask import Flask, request
from .utilities import push_b2_file,log_msg

##################################################################
# BASIC SET-UP
PERPLEXITY_MODEL = "sonar-pro" 
assistant_id = os.getenv('OPENAI_ASSISTANT')
openAI_key = os.getenv('OPENAI_KEY')
pp_key = os.getenv('PERPLEXITY_KEY')
HTML_CONFESSION_LOCAL = os.path.abspath('berger_confession_schedule.html')
HTML_CONFESSION_BB = 'berger_confession_schedule.html'
list_churches = {'Saint Charles de Monceau': {'direct': "https://www.saintcharlesdemonceau.com/horaires-acces/", 'messesinfo': "https://messes.info/lieu/75/paris-17/saint-charles-de-monceau"},
               'Saint François de Sales': {'direct':"https://saintfrancoisdesales.fr/reconciliation/", 'messesinfo': "https://messes.info/lieu/75/paris-17/saint-francois-de-sales-ancienne-eglise"},
               'Saint Augustin': {'direct': 'https://www.saintaugustin.net/horaires-des-messes', 'messesinfo': 'https://messes.info/lieu/75/paris-08/saint-augustin'},
               'Saint Eugène': {'direct': "https://saint-eugene.net/informations-pratiques/horaires-messes-et-offices/", 'messesinfo': "https://messes.info/lieu/75/paris-09/saint-eugene"},
               "Saint Sulpice": {'direct':"https://www.paroissesaintsulpice.paris/", 'messesinfo':"https://messes.info/lieu/75/paris-06/saint-sulpice"}
               }
list_churches_descr = {'Saint Charles de Monceau':{'short':'S. Charles','address':'22b rue Legendre','maplink':'https://maps.app.goo.gl/VKzr3wSUadnX5A5HA'},
                       'Saint François de Sales': {'short':'S. F. de Sales','address': '70 rue Jouffroy / 15 rue Ampère', 'maplink':'https://maps.app.goo.gl/ME2PSxXLUTqkbtuA9'},
                       'Saint Eugène':{'short':'S. Eugène','address':'4 rue du Conservatoire (9e)', 'maplink':'https://maps.app.goo.gl/7iSixX5FkjoRquNA7'},
                       'Saint Augustin':{'short':'S. Augustin','address':'Pl. Saint Augustin (8e)', 'maplink':'https://maps.app.goo.gl/wNtY5sgTV4r2Q2Vk6'},
                       'Saint Sulpice':{'short':'S. Sulpice','address':'2 rue Palatine (6e)', 'maplink':'https://maps.app.goo.gl/iBa1GhN9XqU9Rnna6'}
                       }
nest_asyncio.apply()



######################################################################
# EXTRACTION OF CONFESSION TIMES FROM MESSESINFO
async def get_messesinfo_confessions(church_name, URL):
    # Fetch the data
    log_msg(f'Querying confessions from MessesInfo for {church_name}')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, timeout=60000)
        await page.wait_for_load_state('networkidle')  # Wait until JS content is likely done loading
        content = await page.content()
        await browser.close()

    # Process the content
    soup = BeautifulSoup(content, "html.parser")
    
    # Find the header or tag that contains "Horaires de confession"
    log_msg(f'\tInterpreting confessions MessesInfo data for {church_name}')
    confession_paragraph = soup.find("p", class_="infos-pratique-confession")
    if confession_paragraph:
        spans = confession_paragraph.find_all("span")
        if len(spans) >= 2:
            label = spans[0].get_text(strip=True)
            times = spans[1].get_text(strip=True)
            if label.find('Horaires de confessi')>=0:
                return times
            else:
                return ''
        else:
            return ''
    else:
        return ''

######################################################################
# DIRECT ACCESS TO CHURCH WEB SITE WITH PERPLEXITY INTERPRETATION
def get_direct_church_confession_perplexity(church_name, openAI_client, url):
    # Query the church's Web site
    log_msg(f'Querying confessions church Web site for {church_name}')
    log_msg(f'\tDownloading confessions HTML from {url}')
    response = requests.get(url)
    response.raise_for_status()  
    full_source = response.text
    
    # Write the HTML into a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        tmp.write(full_source.encode("utf-8"))
        html_file_name = tmp.name

    
    # Upload file
    log_msg('\tUploading confessions file to OpenAI')
    uploaded_file = openAI_client.files.create(
        file=open(html_file_name, "rb"),
        purpose="assistants"
    )
    thread = openAI_client.beta.threads.create()
    
    # Add message with file attached via attachment
    log_msg('\tSending confessions message to OpenAI')
    openAI_client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=[
            {
                "type": "text",
                "text": "Voici un fichier HTML extrait d’un site de paroisse. Pouvez-vous en extraire les horaires de confessions ?"
            }
        ],
        attachments=[
            {
                "file_id": uploaded_file.id,
                "tools": [{"type": "file_search"}]
            }
        ]
    )
    
    # Run assistant and wait for completion
    log_msg('\tRunning OpenAI query on confessions')
    log_msg('Confessions thread.id ' + str(thread.id))
    run = openAI_client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )
    log_msg('\tWaiting for confessions from OpenAI')
    while True:
        run_status = openAI_client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status in ["completed", "failed"]:
            break
        time.sleep(1)
    
    # Get the assistant reply
    log_msg('\tGetting confessions OpenAI answer')
    openai_result = '(aucun résultat confessions)'
    messages = openAI_client.beta.threads.messages.list(thread_id=thread.id)
    for msg in reversed(messages.data):
        if msg.role == "assistant":
            openai_result = msg.content[0].text.value
            log_msg('\tdone with confessions OpenAI')
            break

    # Store answer
    return openai_result


######################################################################
# ITERATE THROUGH EACH CHURCH
def generate_confession_schedule():
    # Set up OpenAI and Perplexity clients
    log_msg('generate_confession_schedule: setting up OpenAI and Perplexity')
    openAI_client = openai.OpenAI(api_key=openAI_key)  
    pp_client = OpenAI(api_key=pp_key, base_url="https://api.perplexity.ai")
    
    
    # Iterate through churches
    list_answers = ''
    log_msg('generate_confession_schedule: 1')
    for i, c in enumerate(list_churches):
        # Header
        list_answers += f'{i}) INFORMATIONS SUR {c}\n\n'
    
        # With MessesInfo
        list_answers += 'a) Depuis la source du site MessesInfo\n'
        h = asyncio.get_event_loop().run_until_complete(get_messesinfo_confessions(c,list_churches[c]['messesinfo']))
        list_answers += str(h) + '\n\n'
        
        # Direct access
        list_answers += 'b) Depuis le site Web de la paroisse\n'
        h = get_direct_church_confession_perplexity(c,openAI_client, list_churches[c]['direct'])
        list_answers += str(h) + '\n\n\n\n'
    
    # Tidy up church names
    log_msg('generate_confession_schedule: 2')
    for c in list_churches_descr:
        list_answers = list_answers.replace(c,list_churches_descr[c]['short'])
    
    ######################################################################
    # GET HOLIDAY SCHEDULE
    log_msg('generate_confession_schedule: 3')
    text_ask = "Indiquez s'il vous plaît pour chacun des dix jours à venir si ils sont des vacances scolaires à Paris. La réponse est en français" 
    response = pp_client.chat.completions.create(
        model=PERPLEXITY_MODEL,  
        messages=[
            {"role": "user", "content": text_ask}
        ]
    )
    descr_holidays = response.choices[0].message.content
    log_msg('generate_confession_schedule: 4')
    
    ######################################################################
    # GET PERPLEXITY TO PROCESS THE WHOLE
    descr_list = ", ".join([list_churches_descr[c]['short'] for c in list_churches])
    text_ask = f"""Quels sont les horaires de confessions pour chacun des septs jours à venir dans les églises parisiennes de {descr_list}? 
                    Veuillez baser votre analyse exclusivement sur les informations données ci-dessous, qui proviennent de deux sources
                    Prenez en compte les mentions d'horaires d'été ou de vacances indiqués
                    
                    Les résultats doivent être présentés comme une table HTML:
                    - Les données que vous jugez incertaines en italiques
                    - Lorsque les informations sont manquantes ou aucun confession n'a lieu', marquez '-'
                    - Les églises en colonnes
                    - Lorsque votre source couvre plusieurs jours de la semaine (e.g. 'dumardi au jeudi 10h-11h') veuillez remplir les jours correspondants avec ces horaires (sans la mention des jours)
                    - Si la confession a lieu pendant une messe, indiquez ❉ suivi de l'horaire de la messe correspondante (mais ne mentionnez pas la messe dominicale dans le texte)
                    - Les dates en lignes. Le format des dates doit être du type 'Jeu 15 juillet'
                    - Des lignes horizontales gris clair séparent chaque ligne de la table
                    - Pas de lignes verticales, pas de variations de couleur de fond
                    - les caractères des titres de colonne fonte de couleur #dd6666 (sans changer le background blanc ou transparent). 
                    - Toutes les colonnes doivent être centrées horizontalement, sauf la colonne avec les dates qui doit être alignée à gauche
                    - Un espace modéré (équivalent à HUIT caractères) doit être inclus entre chaque colonne
                    - Le background de la table doit être blanc. Aucune variation de couleur de fonds d'une ligne à l'autre (pas de bandes)
                    
                    --------------------
                    Informations sur les vacances scolaires:
                        {descr_holidays}
                    
                    --------------------
                    Informations sur les confessions à utiliser listées ci-dessous:
                        {list_answers}
                """
    log_msg('generate_confession_schedule: 5')
    response = pp_client.chat.completions.create(
        model=PERPLEXITY_MODEL,
        messages=[
            {"role": "user", "content": text_ask}
        ]
    )
    h = response.choices[0].message.content
    log_msg('generate_confession_schedule: 6')
    with open('full.html', 'wt') as f:
        f.write(h)
    log_msg('generate_confession_schedule: 7')
    
    # Only keep the table
    h = h[h.upper().find('<TABLE'):h.upper().find('</TABLE')+8]
    
    # Add timestamp
    h += f'<BR>❉ Pendant la messe<BR><span style="font-size: 10px;">Mise à jour: {get_now_french()}</SPAN><BR>\n'
    

    # Add church addresses
    h = '<TABLE style="border-collapse:collapse;">\n'
    h += '<TR><th style="color:#dd6666; text-align:left; padding-right:64px;">Eglise</th>\n'
    h += '<th style="color:#dd6666; text-align:left; padding-right:64px;">Adresse</th>\n'
    h += '<th style="color:#dd6666; text-align:left; padding-right:64px;">Plan</th>\n'
    h += '</TR>\n'
    for c in list_churches_descr:
        h += '<TR>\n'
        h += '<TD style="text-align:left;">' + list_churches_descr[c]['short'] + '</td>\n'
        h += '<TD style="text-align:left;padding-right: 16px;">' + list_churches_descr[c]['address'] + '</td>\n'
        h += '<TD style="text-align:left;"><a href="' + list_churches_descr[c]['maplink'] + '" target="_blank">Carte</A></td>\n'
        h += '</TR>\n'
    h += '</TABLE>\n\n'
    log_msg('generate_confession_schedule: 8')

    # Save result in local file
    with open(HTML_CONFESSION_LOCAL, 'wt') as f:
        f.write(h)
    log_msg(f'Confessions table saved in {HTML_CONFESSION_LOCAL}')
    
    # Push the file to BB
    push_b2_file('bergerconfessions', HTML_CONFESSION_LOCAL, HTML_CONFESSION_BB)
    log_msg(f'Confessions table pushed to BB in {HTML_CONFESSION_BB}')




##################################################################
# REGULAR CALL TO THE generate_confession_schedule
def periodic_query_confessions():
    log_msg('Entering background function periodic_query_confessions ')
    log_msg('periodic_query_confessions sleep')
    time.sleep(19)
    log_msg('periodic_query_confessions sleep end')
    while True:
        log_msg('periodic_query_confessions loop step ')
        try:
            generate_confession_schedule()
        except Exception as e:
            log_msg('Error in periodic_query_confessions update: ' + str(e))
        else:
            log_msg('periodic_query_confessions update done')
        time.sleep(12 * 60 * 60)
