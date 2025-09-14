import nest_asyncio, os, pytz, asyncio,time
import pandas as pd
from bs4 import BeautifulSoup
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from playwright.async_api import async_playwright
from babel.dates import format_datetime
from datetime import datetime, timedelta
from .utilities import push_b2_file,log_msg, get_now_french

##################################################################
# BASIC SET-UP
HTML_PARIS_MASS_LOCAL = os.path.abspath('berger_mass_schedule.html')
HTML_PARIS_MASS_BB = 'berger_mass_schedule.html'
list_churches = {'Saint Charles de Monceau': {'direct': "https://www.saintcharlesdemonceau.com/horaires-acces/", 'messesinfo': "https://messes.info/lieu/75/paris-17/saint-charles-de-monceau", 'messesinfo_messe': 'https://messes.info/horaires/eglise%20saint%20charles%20monceau%20diocese:pa%20dim%20toutecelebration?display=TABLE'},
               'Saint François de Sales': {'direct':"https://saintfrancoisdesales.fr/reconciliation/", 'messesinfo': "https://messes.info/lieu/75/paris-17/saint-francois-de-sales-ancienne-eglise",'messesinfo_messe':'https://messes.info/horaires/75017%20saint%20francois%20de%20sales%20toutecelebration?display=TABLE'},
               'Saint Augustin': {'direct': 'https://www.saintaugustin.net/horaires-des-messes', 'messesinfo': 'https://messes.info/lieu/75/paris-08/saint-augustin','messesinfo_messe':'https://messes.info/horaires/saint-augustin%20paris%2075008%20toutecelebration?display=TABLE'},
               'Saint Eugène': {'direct': "https://saint-eugene.net/informations-pratiques/horaires-messes-et-offices/", 'messesinfo': "https://messes.info/lieu/75/paris-09/saint-eugene",'messesinfo_messe': 'https://messes.info/horaires/Saint-Eug%C3%A8ne%20-%20Sainte-C%C3%A9cile%20toutecelebration?display=TABLE'},
               "Saint Sulpice": {'direct':"https://www.paroissesaintsulpice.paris/", 'messesinfo':"https://messes.info/lieu/75/paris-06/saint-sulpice",'messesinfo_messe':'https://messes.info/horaires/saint-sulpice%2075006%20paris%20%20toutecelebration?display=TABLE'}
               }
list_churches_descr = {'Saint Charles de Monceau':{'short':'S. Charles','address':'22b rue Legendre','maplink':'https://maps.app.goo.gl/VKzr3wSUadnX5A5HA'},
                       'Saint François de Sales': {'short':'S. F. de Sales','address': '70 rue Jouffroy / 15 rue Ampère', 'maplink':'https://maps.app.goo.gl/ME2PSxXLUTqkbtuA9'},
                       'Saint Eugène':{'short':'S. Eugène','address':'4 rue du Conservatoire (9e)', 'maplink':'https://maps.app.goo.gl/7iSixX5FkjoRquNA7'},
                       'Saint Augustin':{'short':'S. Augustin','address':'Pl. Saint Augustin (8e)', 'maplink':'https://maps.app.goo.gl/wNtY5sgTV4r2Q2Vk6'},
                       'Saint Sulpice':{'short':'S. Sulpice','address':'2 rue Palatine (6e)', 'maplink':'https://maps.app.goo.gl/iBa1GhN9XqU9Rnna6'}
                       }
nest_asyncio.apply()




##################################################################
# GET PARIS MASS SCHEDULE FOR ONE CHURCH BASED ON MESSES.INFO
async def paris_mass_one_church(church,url):
    log_msg(f'\tQuerying Paris mass schedule for {church} - start')
    # Query messes.info
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("tr td:nth-child(7)", timeout=15000)
        content = await page.content()
        await browser.close()

    # Set up BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")

    # Extract mass schedule and return as dict
    mass_schedule = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 7:
            mass_schedule.append({
                "Eglise": church,
                "EgliseLong": cells[2].get_text(strip=True),
                "Date": cells[4].get_text(strip=True),
                "Heure": cells[5].get_text(strip=True),
                "Liturgie": cells[6].get_text(strip=True),
            })
    log_msg(f'\tQuerying Paris mass schedule for {church} - done')
    return mass_schedule


##################################################################
# CONERT FRENCH-STYLED STRING DATES TO PANDAS DATES
def convert_date_to_pd(x, dt_field):
    list_months_short = {'jan':1, 'fév':2, 'mar':3,'avr':4,'mai':5,'aoû':8, 'sep':9, 'oct':10, 'nov':11,'déc':12}
    y = x[[dt_field]].copy()
    y['DateClean'] = ''
    for i in y.index:
        dt = y.loc[i, 'Date'].split()
        if dt[2][:3] in list_months_short:
            m = list_months_short[dt[2][:3]]
        else:
            if dt[2][:4] == 'juin':
                m = 6
            elif dt[2][:4] == 'juil':
                m = 7
            else:
                m = 0
        m = str(m).rjust(2,'0')
        d = dt[1].rjust(2,'0')
        yr = dt[3]
        y.loc[i, 'DateClean'] = yr + '-' + m + '-' + d
    return pd.to_datetime(y.DateClean)

##################################################################
# GET HTML SUMMARISING PARIS MASS SCHEDULES
def make_html_paris_mass_schedule():
    # Iterate through churches, making a dict for each
    log_msg('make_html_paris_mass_schedule start')
    log_msg('\tmake_html_paris_mass_schedule Starting loop')
    loop = asyncio.get_event_loop()
    list_mass = []
    for church in list_churches:
        log_msg(f'\tmake_html_paris_mass_schedule querying {church}')
        h = loop.run_until_complete(paris_mass_one_church(church,list_churches[church]['messesinfo_messe']))
        list_mass += h
    
    # Store into pandas and clean up
    log_msg('\tmake_html_paris_mass_schedule Cleaning results')
    x = pd.DataFrame(list_mass)
    x['DateClean'] = convert_date_to_pd(x, 'Date')
    x.Liturgie = [s if s.find('\n')<0 else s[:s.find('\n')] for s in x.Liturgie]
    x.Heure = [''+x.loc[i,'Heure'] if x.loc[i,'Liturgie'].lower().find('domini')>=0 else x.loc[i,'Heure'] for i in x.index]
    is_sunday_mass = [i for i in x.index if x.loc[i,'Liturgie'].lower().find('domini')>=0 ]
    x.loc[is_sunday_mass, 'DateClean'] = pd.to_datetime(x.loc[is_sunday_mass, 'DateClean']) + pd.Timedelta(hours=6)
    x.sort_values(by='DateClean',ascending=True)
    x.Eglise = [list_churches_descr[s]['short'] for s in x.Eglise]

    # Only keep the dates within seven days
    dt_now = datetime.now(pytz.timezone('Europe/Paris'))
    dt_cutoff = dt_now.replace(tzinfo=None) + timedelta(days=7, hours=18)
    x = x[x.DateClean <= dt_cutoff]

    # Re-arrange as a pivot table
    log_msg('\tmake_html_paris_mass_schedule Pivoting')
    y = x.pivot_table(index='DateClean',columns='Eglise',values='Heure',
                  aggfunc=lambda values: '\n'.join(values))
    
    # Create HTML
    log_msg('\tmake_html_paris_mass_schedule Creating HTML')
    html = """
    <style>
    .table_mass_times_berger {
        border-collapse: collapse;
        max-width: 700px;
        width: auto;
        table-layout: fixed;
    }
    
    .table_mass_times_berger tr {
        border-bottom: 1px solid lightgrey;
    }
    
    .table_mass_times_berger td,
    .table_mass_times_berger th {
        padding: 6px;
        text-align: center;
        vertical-align: middle;
        word-wrap: break-word;
    }
    
    </style>
    """
    html += '<TABLE class="table_mass_times_berger">\n'
    html += '<caption style="caption-side: top; text-align: center; font-weight: bold; color: #CE6D6A; font-size: 16px; padding-bottom: 8px;">' + 'Horaires des messes' + '</caption>\n'
    html += '\t<THEAD><TR>\n\t\t<TH></TH>'
    for c in y.columns:
        html += f'<TH style="font-weight: bold; color:#CE6D6A">{c}</TH>'
    html += '</TR></THEAD>\n'
    html += '<TBODY>\n'
    for d in y.index:
        html += '\t<TR>'
        if d.hour == 6:
            cell_style = ' style="font-weight:bold; background-color: #EEEEEE;"'
        else:
            cell_style = ''
        html += f'<TD {cell_style}>{format_datetime(d, "EEE d MMMM", locale="fr_FR")}</TD>'
        for c in y.columns:
            s = y.loc[d,c]
            if pd.isnull(s):
                s = ''
            else:
                s = s.replace('\n','<BR>')
            html += f'<TD {cell_style}>{s}</TD>'
        html += '</TR>\n'
    html += '</TBODY>\n'
    html += '</TABLE>'
    html += '<BR><BR><TABLE class="table_mass_times_berger";font-size: 0.75em;>\n\t<TR>\n\t\t<TH></TH><TH style="font-weight: bold; color:#CE6D6A">Nom</TH><TH style="font-weight: bold; color:#CE6D6A" >Adresse</TH/><TH style="font-weight: bold; color:#CE6D6A">Map</TH></TR>\n'
    for c in list_churches_descr:
        maplink = list_churches_descr[c]['maplink']
        html += f'\t<TD>{list_churches_descr[c]["short"]}</TD><TD>{c}</TD><TD>{list_churches_descr[c]["address"]}</TD><TD><A HREF="{maplink}">Map</TD></TR>\n'
    html += '</TABLE>\n\n'

    # Add timestamp
    log_msg('\tmake_html_paris_mass_schedule Adding timestamp')
    html += f'<BR><span style="font-size: 10px;">Mise à jour: {get_now_french()}</SPAN><BR>'

    # Save HTML to local file
    log_msg('\tmake_html_paris_mass_schedule Saving HTML')
    with open(HTML_PARIS_MASS_LOCAL,'wt') as f:
        f.write(html)
    log_msg('\tmake_html_paris_mass_schedule Done')
    
    # Push the file to BB
    log_msg('make_html_paris_mass_schedule pushing to BB')
    push_b2_file('bergermesses', HTML_PARIS_MASS_LOCAL, HTML_PARIS_MASS_BB)
    log_msg(f'make_html_paris_mass_schedule table pushed to BB in {HTML_PARIS_MASS_BB}')


    



##################################################################
# REGULAR CALL TO THE make_html_paris_mass_schedule()
def periodic_query_berger_mass():
    log_msg('Entering background function periodic_query_berger_mass ')
    log_msg('periodic_query_berger_mass sleep')
    time.sleep(3)
    log_msg('periodic_query_berger_mass sleep end')
    while True:
        log_msg('periodic_query_berger_mass loop step ')
        try:
            make_html_paris_mass_schedule()
        except Exception as e:
            log_msg('Error in periodic_query_berger_mass update: ' + str(e))
        else:
            log_msg('periodic_query_berger_mass update done')
        time.sleep(12 * 60 * 60)
