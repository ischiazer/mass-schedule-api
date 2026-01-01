
import os, time, json
import requests, re
from typing import Tuple, Dict, Any, Optional, List
from openai import OpenAI
import pandas as pd
import re, html
from datetime import date, timedelta, datetime
import unicodedata
import urllib.parse
import unicodedata
from . import lib_tmdb
from html import escape
from urllib.parse import quote
from pathlib import Path
from .utilities import get_now_french, push_b2_file, download_file_from_b2, log_msg

##################################################################
# INITIALISATION

#root_path = '/Users/etiennecomon/Downloads/cinema/'
TIME_RE = re.compile(r"\b\d{1,2}[:h]\d{2}\s*(?:[ap]m)?\b", re.I)
PICKLE_PARIS_FILMS_BB = 'berger_films.pickle'
PICKLE_PARIS_SHOW_TIMES_BB = 'berger_show_times.pickle'
PICKLE_PARIS_FAILED_FILMS_BB = 'berger_films_failed.pickle'
HTML_PARIS_FILMS_BB = 'berger_films.html'
PERPLEXITY_MODEL = "sonar-pro" #"llama-3.1-sonar-large-128k-online"
TIME_RE = re.compile(r"\b\d{1,2}[:h]\d{2}\s*(?:[ap]m)?\b", re.I)

# list of cinemas (all Paris)
list_cinemas = ["Grand Action", "Reflet Médicis", "Espace Saint Michel", "Epée de Bois", "Champo", "Filmothèque du Quartier Latin","Cinéma Christine","Ecoles Cinéma Club","Cinéma du Panthéon","Studio Galande", "Studio des Ursulines", "Cinéma Arlequin", "Cinéma Lincoln","Cinéma Balzac","Cinéma des Cinéastes", "Sept Parnassiens", "Action Christine"]
cinema_location = 'Paris, France'
root_path = '/Users/etiennecomon/Downloads/cinema/'

# List of spurious film names
list_film_entries_ignore = ['Christine 21','Christine Cinéma','Cinéma des cin','Cinéma du Panth','Cinéma Espace Saint','Cinéma Studio','Espace Saint-Michel','Espace Saint Michel','GRAND ACTION','Le Balzac','Les horaires du cin','Studio Galande','À L&#x27;AFFICHE','Écoles Cinéma','Cinéma La Filmot','Reflet Medicis','Reflet Médicis','Cinéma le Lincoln','Filmothèque du Quar','Cinéma Epée de Bois','Programme TV','Espace Marcel','horaires des films','La Filmothèque du Quarti', "Cinéma L'Épée", "Filmothèque du Quartier Latin", "Action Christine","Films les plus popula","Grand Action", "Reflet Médicis", "Espace Saint Michel", "Epée de Bois", "Champo", "Filmothèque du Quartier Latin","Cinéma Christine","Ecoles Cinéma Club","Cinéma du Panthéon","Studio Galande", "Studio des Ursulines", "Cinéma Arlequin", "Cinéma Lincoln","Cinéma Balzac","Cinéma des Cinéastes", "Sept Parnassiens", "Action Christine"]
list_film_entries_ignore = [f.lower() for f in list_film_entries_ignore]

# Perplexity setup
PERPLEXITY_MAX_FILMS = 300
PERPLEXITY_MAX_TRY = 3
PERPLEXITY_TIMEOUT_MIN = 4
pp_api_key = os.getenv("PERPLEXITY_KEY")
perplexity_client = OpenAI(api_key=pp_api_key, base_url="https://api.perplexity.ai")


# %%
##################################################################
# FUNCTIONS TO SAVE & LOAD FILM DATABASE AND SHOW TIMES DATABASE

# Get from BlackBlaze the set of film references
def load_film_references():
    download_file_from_b2('bergershops', PICKLE_PARIS_FILMS_BB, PICKLE_PARIS_FILMS_BB)
    with open(PICKLE_PARIS_FILMS_BB, 'rb') as f:
        x_film_references = pd.read_pickle(f)
    download_file_from_b2('bergershops', PICKLE_PARIS_FAILED_FILMS_BB, PICKLE_PARIS_FAILED_FILMS_BB)
    with open(PICKLE_PARIS_FAILED_FILMS_BB, 'rb') as f:
        x_failed = pd.read_pickle(f)
    return x_film_references, x_failed

# Push to BlackBlaze the  set of film references
def save_film_references(x_film_references):
    # Remove references that appear spurious
    list_removed = []
    for film_title in x_film_references.index:
        if not isinstance(film_title, str):
            list_removed.append(film_title)
        else:
            if any(f_ignore in film_title.lower() for f_ignore in list_film_entries_ignore):
                list_removed.append(film_title)
    if len(list_removed) > 0:
        log_msg('Removing film references: ' + (' | '.join(list_removed)))
    x_film_references = x_film_references[~x_film_references.index.isin(list_removed)]

    # Convert HTML text into standard text
    x_film_references = x_film_references.map(lambda v: html.unescape(v) if isinstance(v, str) else v)

    # Save
    log_msg('Saving combined film references to BlackBlaze')
    x_film_references.to_pickle(PICKLE_PARIS_FILMS_BB)
    push_b2_file('bergershops', PICKLE_PARIS_FILMS_BB, PICKLE_PARIS_FILMS_BB)
    log_msg('Done saving film references to BlackBlaze')


# Get from BlackBlaze the show times
def load_show_times():
    download_file_from_b2('bergershops', PICKLE_PARIS_SHOW_TIMES_BB, PICKLE_PARIS_SHOW_TIMES_BB)
    with open(PICKLE_PARIS_SHOW_TIMES_BB, 'rb') as f:
        x_show_times = pd.read_pickle(f)
    return x_show_times

# Push to BlackBlaze the  set of show times
def save_show_times(x_show_times):
    # Convert HTML text into standard text
    x_show_times = x_show_times.map(lambda v: html.unescape(v) if isinstance(v, str) else v)

    # Remove references that appear spurious
    list_removed = []
    for i in x_show_times.index:
        film_title = x_show_times.loc[i, 'Title']
        if not isinstance(film_title, str):
            list_removed.append(film_title)
        else:
            if any(f_ignore in film_title.lower() for f_ignore in list_film_entries_ignore):
                list_removed.append(film_title)
    if len(list_removed) > 0:
        log_msg('Removing film lists: ' + (' | '.join(list_removed)))
    x_show_times = x_show_times[~x_show_times['Title'].isin(list_removed)]

    # Remove unclear show times
    if 'Schedule unknown' in x_show_times.columns:
        x_show_times.drop(columns=['Schedule unknown'], inplace=True)

    # Save
    log_msg('Saving show times to BlackBlaze')
    x_show_times.to_pickle(PICKLE_PARIS_SHOW_TIMES_BB)
    push_b2_file('bergershops', PICKLE_PARIS_SHOW_TIMES_BB, PICKLE_PARIS_SHOW_TIMES_BB)
    log_msg('Done saving show times to BlackBlaze')


##################################################################
# FUNCTIONS SCRAPING FILM TIMES FROM GOOGLE VIA SERP API

# One cinema - get show listings from Google via Serp API
def get_showtimes_serpapi_one_cinema(cinema: str, location: Optional[str] = None, timeout: int = 30) -> Tuple[Dict[str, Any], Dict[str, list]]:
    api_key = os.getenv('SERP_API')
    q = f"showtimes {cinema} {location or ''}".strip()
    params = {'engine': 'google', 'q': q, 'hl': 'en', 'api_key': api_key}
    if location:
        params['location'] = location
    r = requests.get('https://serpapi.com/search.json', params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    matches: dict[str, list] = {}
    def traverse(obj, path='root'):
        if isinstance(obj, str):
            found = TIME_RE.findall(obj)
            if found:
                matches[path] = found
        elif isinstance(obj, dict):
            for k, v in obj.items():
                traverse(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                traverse(v, f"{path}[{i}]")
    traverse(data, 'root')
    return data, matches

# All cinemas - get show listings from Google via Serp API
def get_showtimes_serpapi_all_cinemas(list_cinemas):
    all_data, all_matches = {}, {}
    for c in list_cinemas:
        try:
            log_msg('\tQuerying SerpAPI for ' + str(c))
            d, m = get_showtimes_serpapi_one_cinema(c, cinema_location)
            all_data[c] = d
            all_matches[c] = m
            time.sleep(1)
        except Exception as e:
            log_msg('Failed for ' + str(c) + ' | m' + str(e))
    return all_data, all_matches


# %%
##################################################################
# FUNCTIONS CLEANING AND ORGANISING FILM TIME SCRAPE DATA

all_show_dates: List[str] = []
showtimes_by_film_cinema_date: Dict[str, Dict[str, Dict[str, List[str]]]] = {}

# Helper to sanitize filenames
def _sanitize_fname(s: str) -> str:
    if not s:
        return 'untitled'
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s)
    return s[:120]


def _sort_date_keys(values: Optional[set[str]] = None) -> List[str]:
    values = values or set()
    def sort_key(val: str):
        if val == 'unknown':
            return (1, val)
        try:
            return (0, datetime.fromisoformat(val))
        except Exception:
            return (0, val)
    return sorted(values, key=sort_key)


def _schedule_column_label(day_key: str) -> str:
    if not day_key or day_key == 'unknown':
        return 'Schedule unknown'
    try:
        dt = datetime.fromisoformat(day_key)
        return f"Schedule {dt.strftime('%a %d-%b')}"
    except Exception:
        return f"Schedule {day_key}"


# Convert text label to ISO date where possible
def to_iso_date_from_label(label: str):
    if not label or not isinstance(label, str):
        return None
    s_raw = label.strip()
    month_map = {
        'janvier':'January','février':'February','fevrier':'February','mars':'March','avril':'April','mai':'May','juin':'June',
        'juillet':'July','août':'August','aout':'August','septembre':'September','octobre':'October','novembre':'November','décembre':'December','decembre':'December',
        'janv':'Jan','fév':'Feb','fev':'Feb','avr':'Apr','juil':'Jul','août':'Aug','aout':'Aug','sept':'Sep','oct':'Oct','nov':'Nov','déc':'Dec','dec':'Dec'
    }
    s_norm = s_raw
    for fr, en in month_map.items():
        s_norm = re.sub(fr, en, s_norm, flags=re.I)
    s = s_norm.lower()
    today = date.today()
    if 'today' in s or 'aujourd' in s:
        return today.isoformat()
    if 'tomorrow' in s or 'demain' in s:
        return (today + timedelta(days=1)).isoformat()
    m = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', s)
    if m:
        return m.group(1)
    m2 = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', s)
    if m2:
        for fmt in ('%d/%m/%Y','%d-%m-%Y','%d/%m/%y','%d-%m-%y'):
            try:
                dt = datetime.strptime(m2.group(1), fmt).date()
                return dt.isoformat()
            except Exception:
                pass
    month_formats = ['%d %B %Y', '%d %b %Y', '%B %d %Y', '%b %d %Y', '%d %B', '%d %b', '%B %d', '%b %d']
    for fmt in month_formats:
        try:
            dt = datetime.strptime(s_raw, fmt).date()
            if dt.year == 1900:
                dt = dt.replace(year=today.year)
                if dt < today:
                    dt = dt.replace(year=today.year + 1)
            return dt.isoformat()
        except Exception:
            pass
    weekdays = {'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5,'sunday':6,
                'lundi':0,'mardi':1,'mercredi':2,'jeudi':3,'vendredi':4,'samedi':5,'dimanche':6}
    for name, wd in weekdays.items():
        if name in s:
            days_ahead = (wd - today.weekday() + 7) % 7
            target = today if days_ahead == 0 else today + timedelta(days=days_ahead)
            return target.isoformat()
    return None

# Collect time strings from nested SerpAPI structures
def collect_times(node):
    times = []
    if isinstance(node, str):
        times.extend(TIME_RE.findall(node))
    elif isinstance(node, dict):
        for v in node.values():
            times.extend(collect_times(v))
    elif isinstance(node, list):
        for v in node:
            times.extend(collect_times(v))
    return list(dict.fromkeys([t.strip() for t in times if t]))

# Walk SerpAPI response to extract film entries while preserving day context
def extract_from_cinema(data, cinema_name):
    films = []
    def walk(node, context_day=None):
        if isinstance(node, list):
            if all(isinstance(el, dict) for el in node) and any(('day' in el or 'date' in el or 'movies' in el) for el in node):
                for el in node:
                    raw_day = ''
                    if isinstance(el, dict):
                        raw_day = (el.get('date') or el.get('day') or el.get('title') or '')
                    iso_day = to_iso_date_from_label(raw_day) or (raw_day if raw_day else 'unknown')
                    movies_list = el.get('movies') if isinstance(el, dict) else None
                    if movies_list and isinstance(movies_list, list):
                        for m in movies_list:
                            title = m.get('name') or m.get('title') or m.get('movie')
                            times = collect_times(m)
                            if title and times:
                                films.append({'title': title, 'cinema': cinema_name, 'day': iso_day, 'times': times, 'meta': m})
                        continue
                    walk(el, context_day=iso_day)
                return
            for el in node:
                walk(el, context_day=context_day)
        elif isinstance(node, dict):
            if 'movies' in node and isinstance(node.get('movies'), list):
                raw_day = (node.get('date') or node.get('day') or node.get('title') or '')
                iso_day = to_iso_date_from_label(raw_day) or (raw_day if raw_day else context_day or 'unknown')
                for m in node.get('movies', []):
                    title = m.get('name') or m.get('title') or m.get('movie')
                    times = collect_times(m)
                    if title and times:
                        films.append({'title': title, 'cinema': cinema_name, 'day': iso_day, 'times': times, 'meta': m})
                return
            if any(k.lower() in ('title','name','movie') for k in node.keys()):
                title = node.get('title') or node.get('name') or node.get('movie')
                times = collect_times(node)
                if title and times:
                    films.append({'title': title, 'cinema': cinema_name, 'day': context_day or 'unknown', 'times': times, 'meta': node})
                return
            for v in node.values():
                walk(v, context_day=context_day)
    walk(data)
    return films



# Aggregate films across cinemas — NO director/year/country extraction here
def aggregate_films_across_cinemas(data_all, matches_all):
    global all_show_dates, showtimes_by_film_cinema_date
    agg: Dict[str, Dict[str, Any]] = {}
    dates_seen: set[str] = set()
    film_cinema_map: Dict[str, Dict[str, Dict[str, set[str]]]] = {}
    for cinema, d in data_all.items():
        try:
            films = extract_from_cinema(d, cinema)
        except Exception as e:
            print('Extraction error for', cinema, e)
            films = []
        for f in films:
            title_norm = (f.get('title') or '').strip()
            if not title_norm:
                continue
            # drop pure time-like titles
            try:
                if TIME_RE.fullmatch(title_norm):
                    continue
            except Exception:
                pass
            key = title_norm.lower()
            entry = agg.setdefault(key, {'title': title_norm, 'cinemas': set(), 'schedule': {}, 'meta_sample': None, 'google_link': ''})
            entry['cinemas'].add(f['cinema'])
            day_iso = f['day']
            if day_iso == 'unknown':
                meta = f.get('meta') or {}
                for v in meta.values() if isinstance(meta, dict) else []:
                    if isinstance(v, str):
                        iso = to_iso_date_from_label(v)
                        if iso:
                            day_iso = iso
                            break
            resolved = to_iso_date_from_label(day_iso) if isinstance(day_iso, str) else None
            if not resolved:
                resolved = 'unknown'
            dates_seen.add(resolved)
            sched = entry['schedule'].setdefault(resolved, set())
            film_bucket = film_cinema_map.setdefault(title_norm, {})
            cinema_bucket = film_bucket.setdefault(f['cinema'], {})
            day_bucket = cinema_bucket.setdefault(resolved, set())
            for t in f['times']:
                clean_time = t.strip()
                if not clean_time:
                    continue
                sched.add(clean_time)
                day_bucket.add(clean_time)
            try:
                if not entry.get('meta_sample') and f.get('meta') is not None:
                    entry['meta_sample'] = f.get('meta')
            except Exception:
                pass
            # store a Google search link for the title (for later OpenAI use)
            if not entry.get('google_link'):
                q = urllib.parse.quote_plus(title_norm)
                entry['google_link'] = f"https://www.google.com/search?hl=fr&gl=FR&q={q}"

    def _serialize_showtimes(raw_map: Dict[str, Dict[str, Dict[str, set[str]]]]) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        serialized: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        for film, cinemas in raw_map.items():
            serialized[film] = {}
            for cinema_name, dates in cinemas.items():
                serialized[film][cinema_name] = {date: sorted(times) for date, times in dates.items()}
        return serialized

    all_show_dates = _sort_date_keys(dates_seen)
    showtimes_by_film_cinema_date = _serialize_showtimes(film_cinema_map)
    return agg


# Build table with film times
def make_table_film_times(agg, list_films_ignore, dates_to_include: Optional[List[str]] = None):
    rows = []
    list_removed = []
    date_filter: Optional[set[str]] = None
    if dates_to_include:
        parsed_dates = set()
        for raw_date in dates_to_include:
            normalized = to_iso_date_from_label(raw_date) or (raw_date.strip() if isinstance(raw_date, str) else None)
            if normalized:
                parsed_dates.add(normalized)
        if parsed_dates:
            date_filter = parsed_dates

    def _compute_schedule_dates() -> List[str]:
        if all_show_dates:
            subset = [d for d in all_show_dates if not date_filter or d in date_filter]
        else:
            subset = []
        if not subset:
            collected: set[str] = set()
            for v in agg.values():
                collected.update(v['schedule'].keys())
            if date_filter:
                collected = collected.intersection(date_filter)
            subset = _sort_date_keys(collected)
        if not subset and date_filter:
            subset = _sort_date_keys(date_filter)
        if not subset:
            return ['unknown']
        return subset

    schedule_dates = _compute_schedule_dates()
    schedule_columns = [(day_key, _schedule_column_label(day_key)) for day_key in schedule_dates]

    for k, v in sorted(agg.items(), key=lambda x: x[1]['title'].lower()):
        title_text = v['title']
        if any(f_ignore in title_text.lower() for f_ignore in list_films_ignore):
            list_removed.append(title_text[:15])
            continue
        cinemas = ', '.join(sorted(v['cinemas']))
        google_url = v.get('google_link', '')
        row_entry = {'Title': title_text, 'Film link': google_url, 'Cinemas': cinemas}
        has_visible_schedule = False
        for day_key, column_label in schedule_columns:
            times_for_day = v['schedule'].get(day_key, set())
            if times_for_day:
                has_visible_schedule = True
            row_entry[column_label] = '\n'.join(sorted(times_for_day)) if times_for_day else ''
        if date_filter and not has_visible_schedule:
            continue
        rows.append(row_entry)

    column_order = ['Title', 'Film link', 'Cinemas'] + [label for _, label in schedule_columns]
    table_films = pd.DataFrame(rows, columns=column_order)
    table_films = table_films.fillna('')
    if len(list_removed) > 0:
        log_msg('Spurious film titles skipped: ' + ' | '.join(list_removed))

    return table_films

##################################################################
# CONSOLIDATED CALL TO THE FUNCTIONS FETCHING SHOW TIMES
def consolidated_fetch_show_times():
    log_msg('Fetching film times of individual cinemas')
    all_data, all_matches = get_showtimes_serpapi_all_cinemas(list_cinemas)
    log_msg('Aggregating film times across cinemas')
    x_all_films = aggregate_films_across_cinemas(all_data, all_matches)
    log_msg('Making films table')
    table_films = make_table_film_times(x_all_films, list_film_entries_ignore)
    log_msg('Done films table')
    save_show_times(table_films)



######################################################################
# GET DIRECTOR, FILM YEAR, COUNTRY, GENRE, SYNOPSIS FROM PERPLEXITY


# Query film descriptions from Perplexity
def query_films_from_perplexity(pp_client, film_name, film_link, msg_tracker, failed_storage):
    log_msg('\tPerplexity query [' + msg_tracker + '] for ' + film_name)
    prompt = ("I will provide a film with a google link. Please return a completed dictionary where you will add the following elements: [a] 'Director', [b] 'Year', [c] 'Country',[d] 'Genre',[e] 'Synopsis' based on the film name and google link provided. " +
            "Return the completed dictionary for this film. " +
            "If a value is not present, return an empty string for that field. " +
            "Make the response a pure json string, without any comment, prefix nor suffix. Now the dictionary:\n\n" + json.dumps({'Film':film_name, 'link':film_link}))
    resp = pp_client.chat.completions.create(
        model=PERPLEXITY_MODEL,
        messages=[
            {"role":"user","content":prompt}
        ],
        max_tokens=128000,
        temperature=0.0,
        timeout=60*PERPLEXITY_TIMEOUT_MIN
    )
    if not resp.choices:
        raise RuntimeError("No response from Perplexity API")
    if resp.choices[0].finish_reason != 'stop':
        raise RuntimeError("Incomplete response from Perplexity API")
    s = resp.choices[0].message.content
    if s.count('{') != s.count('}'):
        raise RuntimeError("Mismatched { and }")
    if "```" in s:
        s = s[s.find("```")+3 : s.rfind('```')]
    s = s.replace('json\n','')

    # Parse JSON content and store into pandas
    resp_converted = json.loads(s)

    # Convert to Pandas
    resp_df = pd.DataFrame([resp_converted])
    return resp_df


# Query film descriptions from Perplexity
def loop_films_from_perplexity():
    # Set up the list of films to query from Perplexity
    x_existing_perplexity, x_failed = load_film_references()
    table_films = load_show_times()
    prompt_films = {}
    count_new_film = 0
    for ix in table_films.index[:PERPLEXITY_MAX_FILMS]:
        if (not table_films.loc[ix, 'Title'] in x_existing_perplexity.index):
            prompt_films[count_new_film] = {'Title': table_films.loc[ix,'Title'], 'Film link': table_films.loc[ix,'Film link']}
            count_new_film += 1
    log_msg('\tNumber of prompts ' + str(len(prompt_films)))

    # Loop through batches of films
    list_new_perplexity = []
    list_fails = []
    for i_film in range(0, len(prompt_films)):
        # Define the batch of films to query
        str_tracker = str(i_film+1) + '/' + str(len(prompt_films))

        # Run the Perplexity query until successful
        n_tries = 0
        completed = False
        while not completed and n_tries < PERPLEXITY_MAX_TRY:
            film_name = prompt_films[i_film]['Title']
            film_link = prompt_films[i_film]['Film link']
            try:
                response = query_films_from_perplexity(perplexity_client, film_name,film_link, str_tracker, x_failed)
                if response[(~pd.isnull(response['Director'])&(response['Director']!=''))].shape[0] == 1:
                    completed = True
                else:
                    n_tries += 1
                    log_msg(f"\tIncomplete data in film {film_name}, try {n_tries}")
                    time.sleep(2)
                    response = None
            except Exception as e:
                n_tries += 1
                log_msg(f"\tError querying film {film_name}, try {n_tries}: {e}")
                time.sleep(2)
                response = None
        if not response is None:    
            list_new_perplexity.append(response)
        else:
            list_fails.append(film_name)
            if film_name in x_failed.index:
                x_failed.loc[film_name,'n_fail'] = x_failed.loc[film_name,'n_fail'] + 1
            else:
                x_failed.loc[film_name,'n_fail'] = 1

    # Concatenate new film entries
    if len(list_new_perplexity) > 0:
        x_new_perplexity = pd.concat(list_new_perplexity)
        x_new_perplexity.set_index('Film',inplace=True)
        x_new_perplexity = x_new_perplexity[~pd.isnull(x_new_perplexity['Director'])]
        x_new_perplexity = x_new_perplexity[x_new_perplexity['Director'] != '']
        if 'Link' in x_new_perplexity.columns:
            x_new_perplexity.drop(columns=['Link'],inplace=True)

        # Combine old and new film entries from Perplexity
        log_msg('\tCombining existing and new film Perplexity entries')
        log_msg('\t\ttExisting = %d' % x_existing_perplexity.shape[0])
        log_msg('\t\t\tNew = %d' % x_new_perplexity.shape[0])
        if x_new_perplexity.shape[0] > 0:
            x_perplexity = pd.concat([x_existing_perplexity, x_new_perplexity])
            x_perplexity = x_perplexity[~x_perplexity.index.duplicated(keep='first')]
        else:
            x_perplexity = x_existing_perplexity.copy()
    else:
        x_perplexity = x_existing_perplexity.copy()
    log_msg('\t\tCombined = %d' % x_perplexity.shape[0])

    # Save result
    save_film_references(x_perplexity)

    # Show failed films
    if len(list_fails) > 0:
        log_msg('Failed films:' + '\n'.join(['\t'+s for s in list_fails]))


######################################################################
# GET TRAILER LINK AND WIKI PAGE FOR EACH FILM

def run_wiki_and_trailer_fetch():
    x_perplexity, x_failed = load_film_references()
    x_perplexity['trailer_url'] = None
    x_perplexity['wikipedia_title'] = None
    perplexity_client = OpenAI(api_key=pp_api_key, base_url="https://api.perplexity.ai")
    log_msg('Fetching Wiki & trailer')
    for film_name in x_perplexity.index:
        if isinstance(film_name, str):
            if pd.isnull(x_perplexity.loc[film_name, 'Trailer link']) or pd.isnull(x_perplexity.loc[film_name, 'Wikipedia']):
                log_msg('\t' + film_name)
                film_director = x_perplexity.loc[film_name, 'Director'] 
                prompt = "Please provide [a] a YouTube link to the movie trailer if available; and [b] a link to a jpeg or png picture of the movie poster for the film if available on Wikipedia. The film is '" + film_name + "' by " + film_director + ". Please provide your answer as a json dictionary of two elements, with no commentary or addition. If either [a] or [b] cannot be returned, please return an empty string for the missing item"
                prompt = f"""You are a web-connected assistant.
                            Task:
                            For the film "{film_name}" directed by {film_director}:

                            1. Find an official or widely used movie trailer on YouTube.
                            - Return the full YouTube URL as "trailer_url".

                            2. The exact English Wikipedia article title of the movie (case sensitive, exactly as used in the page URL, without adding https:// links). 

                            Output format (IMPORTANT):
                            - Return ONLY a single JSON object (no commentary, no extra text).
                            - The JSON must have exactly these keys:
                            - "trailer_url": string or null
                            - "wikipedia_title": string or null

                            If you truly cannot find a valid   URL, set the field to null, but do not omit the key.

                            Example of the required structure (for illustration only):

                            {{
                            'trailer_url': 'https://www.youtube.com/...',
                            'wikipedia_title": "Amores_Perros'
                            }}
                            """

                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You find official movie trailer and poster URLs. "
                            "Return ONLY valid JSON dictionary with the following keys: "
                            "trailer_url, poster_url. Do not include explanations."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
                n_tries = 0
                completed = False
                while not completed and n_tries < PERPLEXITY_MAX_TRY:
                    try:
                        resp = perplexity_client.chat.completions.create(
                            model=PERPLEXITY_MODEL,
                            messages=messages,
                            max_tokens=128000,
                            temperature=0.4,
                            timeout=60*PERPLEXITY_TIMEOUT_MIN
                        )
                        try:
                            resp = resp.choices[0].message.content
                            resp = resp.replace("```","")
                            try:
                                resp_converted = json.loads(resp)
                                x_perplexity.loc[film_name, 'Trailer link'] = resp_converted.get('trailer_url','')
                                x_perplexity.loc[film_name, 'Wikipedia'] = resp_converted.get('wikipedia_title','')
                                completed = True
                            except Exception as e:
                                log_msg('\tCould not convert Wiki results for ' + film_name + ' | '  + str(e))
                                n_tries += 1
                        except Exception as e:
                            log_msg('\tNo Wiki output for ' + film_name + '[' + str(e) + ']')
                            n_tries += 1
                    except Exception as e:
                        log_msg('\tPerplexity Wiki failed for ' + film_name + '[' + str(e) + ']')
                        n_tries += 1

    # Save result
    save_film_references(x_perplexity)


############################################################
# ADD WIKIPEDIA LINK

def wikipedia_page_url(title: str) -> str:
    normalized = title.replace(" ", "_")
    return "https://en.wikipedia.org/wiki/" + quote(normalized)

def run_wikipedia_link_addition():
    x_perplexity, x_failed = load_film_references()
    if not 'Wikipedia page' in x_perplexity.columns:
        x_perplexity['Wikipedia page'] = None
    log_msg('Adding Wikipedia page links')
    for f in x_perplexity.index:
        if pd.isnull(x_perplexity.loc[f,'Wikipedia page']):
            if not pd.isnull(x_perplexity.loc[f,'Wikipedia']):
                x_perplexity.loc[f,'Wikipedia page'] = wikipedia_page_url(x_perplexity.loc[f,'Wikipedia'])
    log_msg('Done Wikipedia page links')
    save_film_references(x_perplexity)


############################################################
# ADD FILM POSTERS FROM WIKIPEDIA PAGES

def add_posters_from_wiki():
    x_perplexity, x_failed = load_film_references()
    HEADERS = { "User-Agent": "FilmPosterFetcher/1.0 (your_email@example.com)" }

    def _query_wikipedia(params: dict) -> dict:
        api = "https://en.wikipedia.org/w/api.php"
        r = requests.get(api, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()

    def _get_page_dict_for_title(page_title: str) -> dict | None:
        data = _query_wikipedia({
            "action": "query",
            "format": "json",
            "titles": page_title,
            "redirects": 1,
        })
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None
        return next(iter(pages.values()))

    def get_wikipedia_poster_url(page_title: str, thumb_width: int = 300) -> str | None:
        """
        Try to get a poster-like image URL for a given English Wikipedia page.
        1) First try pageimages thumbnail.
        2) Then fall back to images + imageinfo and pick a 'poster' file.
        Returns a direct jpg/png URL or None.
        """

        # --- 1) Try pageimages thumbnail ---
        data = _query_wikipedia({
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": thumb_width,
            "titles": page_title,
            "redirects": 1,
        })

        pages = data.get("query", {}).get("pages", {})
        if pages:
            page = next(iter(pages.values()))
            thumb = page.get("thumbnail")
            if thumb and "source" in thumb:
                return thumb["source"]

        # Optional: if that failed, try with " (film)" suffix
        alt_title = f"{page_title} (film)"
        if alt_title != page_title:
            data_alt = _query_wikipedia({
                "action": "query",
                "format": "json",
                "prop": "pageimages",
                "piprop": "thumbnail",
                "pithumbsize": thumb_width,
                "titles": alt_title,
                "redirects": 1,
            })
            pages_alt = data_alt.get("query", {}).get("pages", {})
            if pages_alt:
                page_alt = next(iter(pages_alt.values()))
                thumb_alt = page_alt.get("thumbnail")
                if thumb_alt and "source" in thumb_alt:
                    return thumb_alt["source"]

        # --- 2) Fallback: list images on the page and pick a poster-like one ---
        page = _get_page_dict_for_title(page_title)
        if page is None or "pageid" not in page:
            return None

        pageid = page["pageid"]
        images_data = _query_wikipedia({
            "action": "query",
            "format": "json",
            "prop": "images",
            "pageids": pageid,
            "imlimit": "max",
        })

        img_page = images_data.get("query", {}).get("pages", {}).get(str(pageid), {})
        images = img_page.get("images", [])
        if not images:
            return None

        def is_image_file(title: str) -> bool:
            t = title.lower()
            return t.endswith(".jpg") or t.endswith(".jpeg") or t.endswith(".png")

        # Prefer filenames that look like posters
        poster_candidates = [
            img["title"] for img in images
            if is_image_file(img.get("title", ""))
            and any(
                token in img["title"].lower()
                for token in ("poster", "film_poster", "movie_poster")
            )
        ]

        # If none look like posters, fall back to any jpg/png
        if not poster_candidates:
            poster_candidates = [
                img["title"] for img in images
                if is_image_file(img.get("title", ""))
            ]

        if not poster_candidates:
            return None

        image_title = poster_candidates[0]

        # --- 3) Get direct URL from imageinfo ---
        imageinfo_data = _query_wikipedia({
            "action": "query",
            "format": "json",
            "titles": image_title,
            "prop": "imageinfo",
            "iiprop": "url",
        })

        img_pages = imageinfo_data.get("query", {}).get("pages", {})
        if not img_pages:
            return None

        img_page = next(iter(img_pages.values()))
        imageinfo = img_page.get("imageinfo")
        if not imageinfo:
            return None

        return imageinfo[0].get("url")


    # Loop through films
    log_msg('Adding film posters from Wikipedia pages')
    if 'Poster' not in x_perplexity.columns:
        x_perplexity['Poster'] = None
    for f in x_perplexity.index:
        if not x_perplexity.loc[f, 'Wikipedia'] is None:
            if pd.isnull(x_perplexity.loc[f,'Poster']):
                picture_url = get_wikipedia_poster_url(x_perplexity.loc[f,'Wikipedia'])
                x_perplexity.loc[f,'Poster'] = picture_url
    log_msg('Done film posters from Wikipedia pages')

    save_film_references(x_perplexity)


############################################################
# GET TMDB MOVIE ID

def add_TMDB_IDs():
    log_msg('Getting TMDB IDs')
    x_perplexity, x_failed = load_film_references()
    if 'TMDB_ID' not in x_perplexity.columns:
        x_perplexity['TMDB_ID'] = None

    # Loop through all films
    for f in x_perplexity.index:
        if pd.isnull(x_perplexity.loc[f,'TMDB_ID']):
            if isinstance(f, str):
                log_msg('\tFetching TMBD ID for '+f)
                movie_id = lib_tmdb.tmdb_get_movie_id(
                            title=html.unescape(f),
                            director=html.unescape(x_perplexity.loc[f,'Director'])
                        )
                x_perplexity.loc[f,'TMDB_ID'] = movie_id

    # Save result
    save_film_references(x_perplexity)
    log_msg('Done getting TMDB IDs')

############################################################
# GET TMDB DETAILS

def add_TMBD_details():
    log_msg('Adding TMDB details to films')
    x_perplexity, x_failed = load_film_references()
    for f in ['TMDB_Cast','TMDB_Country','TMDB_Genre','TMDB_Poster','TMDB_Popularity','TMDB_Release_Date','TMDB_Runtime','TMDB_Synopsis','TMDB_Poster','TMDB_Trailer']:
        if f not in x_perplexity.columns:
            x_perplexity[f] = None

    # Loop through all films
    log_msg('Extracting film details from TMDB')
    for f in x_perplexity.index:
        if (pd.isnull(x_perplexity.loc[f,'TMDB_Cast']) or (x_perplexity.loc[f,'TMDB_Cast']=='')):
            if isinstance(f, str):
                log_msg('\tFetching TMBD details for '+f)
                # Download TMDB details
                movie_id = x_perplexity.loc[f,'TMDB_ID']
                try:
                    details = lib_tmdb.tmdb_get_movie_details(movie_id)
                    credits = lib_tmdb.tmdb_get_movie_credits(movie_id)
                    images = lib_tmdb.tmdb_get_movie_images(movie_id)
                    film_trailer = lib_tmdb.tmdb_get_trailer_url(movie_id)

                    # Extract values
                    if isinstance(details['origin_country'], list):
                        film_country = ' | '.join(details['origin_country'])
                    else:
                        film_country = details['origin_country']
                    film_synopsis = details['overview']
                    film_popularity = details['popularity']
                    film_release_date = details['release_date']
                    film_runtime = details['runtime']
                    film_genre = ' | '.join([ k['name'] for k in details['genres']])
                    film_poster = lib_tmdb.pick_best_poster(images)
                    film_poster = lib_tmdb.tmdb_poster_url_from_poster_dict(film_poster, size="w342")
                    film_cast = ''
                    for actor in credits['cast'][:5]:
                        if film_cast != '':
                            film_cast += '\n'
                        film_cast += actor['name'] + ' (' + actor['character'] + ')'
                except Exception as e:
                    log_msg('\t\tFailed to get TMDB details for ' + f + ' | ' + str(e))
                    film_country = ''
                    film_synopsis = ''
                    film_popularity = ''
                    film_release_date = ''
                    film_runtime = ''
                    film_genre = ''
                    film_poster = ''
                    film_cast = ''
                    film_trailer = ''

                # Store
                x_perplexity.loc[f,'TMDB_Cast'] = film_cast
                x_perplexity.loc[f,'TMDB_Country'] = film_country
                x_perplexity.loc[f,'TMDB_Genre'] = film_genre
                x_perplexity.loc[f,'TMDB_Poster'] = film_poster
                x_perplexity.loc[f,'TMDB_Popularity'] = film_popularity
                x_perplexity.loc[f,'TMDB_Release_Date'] = film_release_date
                x_perplexity.loc[f,'TMDB_Runtime'] = film_runtime
                x_perplexity.loc[f,'TMDB_Synopsis'] = film_synopsis
                x_perplexity.loc[f,'TMDB_Trailer'] = film_trailer

    # Save result
    save_film_references(x_perplexity)
    log_msg('Done adding TMDB details')

############################################################
# PRODUCE HTML TABLE FOR VIEWING

# Resolve template relative to this file so it works both locally
# and on Render, regardless of the current working directory.
TEMPLATE_PATH = (Path(__file__).resolve().parent.parent
                                 / 'app_files' / 'berger_files' / 'film_table_template.html')

def make_HTML():
  BASE_HEADERS = [
      "","Film","Genre","Cinemas"
  ]
  BASE_COLUMN_CLASSES = [
      'col-poster','col-title','col-genre','col-cinemas'
  ]
  DEFAULT_SYNOPSIS = 'Synopsis unavailable.'
  DEFAULT_CAST = 'Cast unavailable.'
  DEFAULT_RUNTIME = 'Runtime unavailable.'

  def _is_schedule_column(name):
      name_str = str(name).strip().lower()
      return name_str.startswith('schedule') or 'schedule' in name_str

  def prepare_table_dataframe(filled_df):
      table_df = filled_df.reset_index()
      if 'Title' not in table_df.columns:
          table_df = table_df.rename(columns={'index': 'Title'})
      return table_df.fillna('')

  def _as_text(value):
      value = '' if value is None else value
      return str(value).strip()

  def _format_multiline(value):
      return escape(_as_text(value)).replace('\n', '<br>')

  def _extract_year(value):
      text = _as_text(value)
      if not text:
          return ''
      match = re.search(r'(\d{4})', text)
      if match:
          return match.group(1)
      if len(text) >= 4:
          return text[-4:]
      return text

  def _poster_cell_markup(url, title):
      safe_title = escape(title) if title else 'Poster'
      if url:
          safe_url = escape(url, quote=True)
          return f"<div class='poster-thumb'><img src='{safe_url}' alt='Poster for {safe_title}'></div>"
      return "<div class='poster-thumb poster-thumb--placeholder'></div>"

  def _modal_poster_markup(url, title):
      safe_title = escape(title) if title else 'Poster'
      if url:
          safe_url = escape(url, quote=True)
          return f"<img class='modal-poster-img' src='{safe_url}' alt='Poster for {safe_title}'>"
      return "<div class='modal-poster-placeholder'>Poster</div>"

  def _build_column_group(classes):
      parts = ['<colgroup>']
      parts.extend(f"<col class='{cls}'>" for cls in classes)
      parts.append('</colgroup>')
      return ''.join(parts)

  def _build_table_head(headers):
      head_parts = ['<thead><tr>']
      head_parts.extend(f'<th>{head}</th>' for head in headers)
      head_parts.append('</tr></thead>')
      return ''.join(head_parts)

  def _schedule_display_label(column_label: str) -> str:
      return column_label.replace('Schedule ', '', 1).strip() or column_label

  def _normalize_schedule_cell(value):
      # Treat blank-like markers as empty and strip HTML/non-breaking spaces
      if pd.isna(value):
          return []
      if value is None or (isinstance(value, float) and pd.isna(value)):
          return []
      if isinstance(value, (list, tuple)):
          return [str(x).strip() for x in value if str(x).strip()]
      text_value = str(value)
      # Normalize NBSP and decode HTML entities
      text_value = html.unescape(text_value.replace('\xa0', ' ').replace('\u00a0', ' ')).strip()
      if not text_value:
          return []
      lowered = text_value.lower()
      if lowered in {'nan','none','null','[]','{}','na','n/a','-','—','no show','no shows','no showtimes','n\u00b0 show','n\u00b0 shows','<na>','<na>'}:
          return []
      # Strip trivial bracketed empties and tags
      compact = lowered.replace(' ', '')
      if compact in {'[]','[ ]','[\n]','<br>','<br/>'}:
          return []
      text_value = re.sub(r'<[^>]+>', ' ', text_value)
      lines = [line.strip() for line in text_value.splitlines()]
      return [line for line in lines if line]

  def _row_has_any_schedule(row, schedule_cols):
      if not schedule_cols:
          return False
      for col in schedule_cols:
          if _normalize_schedule_cell(row.get(col)):
              return True
      return False

  def _compose_schedule_html(schedule_map, selected_keys):
      selected_keys = selected_keys or []
      parts = []
      for key in selected_keys:
          times = schedule_map.get(key) or []
          if not times:
              continue
          label = escape(_schedule_display_label(key))
          times_html = ', '.join(escape(t) for t in times)
          parts.append(
              f"<div class='schedule-day-line'><span class='schedule-day-label'>{label}</span>: "
              f"<span class='schedule-day-times'>{times_html}</span></div>"
          )
      if not parts:
          return ""
      return ''.join(parts)

  def _build_rows_and_modals(table_df, column_classes, schedule_columns, initial_selection):
      body_parts = ['<tbody>']
      modals = []
      schedule_payload = {}
      kept = 0
      dropped_no_show = 0
      for idx, row in table_df.iterrows():
          if not _row_has_any_schedule(row, schedule_columns):
              dropped_no_show += 1
              continue
          row_key = f"film-{idx}"
          title = _as_text(row.get('Title')) or 'Untitled'
          link = _as_text(row.get('Film link'))
          poster_url = _as_text(row.get('TMDB_Poster'))
          if not link:
              title_cell = f"<strong>{escape(title)}</strong>"
          else:
              title_cell = (
                  f"<a href='{escape(link, quote=True)}' target='_blank' rel='noopener noreferrer'><strong>{escape(title)}</strong></a>"
              )
          synopsis_html = _format_multiline(row.get('TMDB_Synopsis') or DEFAULT_SYNOPSIS)
          cast_html = _format_multiline(row.get('TMDB_Cast') or DEFAULT_CAST)
          runtime_text = _as_text(row.get('TMDB_Runtime'))
          runtime_display = runtime_text + ' min' if runtime_text.isdigit() else (runtime_text or DEFAULT_RUNTIME)
          runtime_html = escape(runtime_display)
          modal_id = f"synopsis-{idx}"
          eye_cell = (
              f"<button class='film-eye-btn' type='button' "
              f"onclick=\"var el=document.getElementById('{modal_id}'); if(el){{el.style.display='block';}}\" "
              "aria-label='Synopsis'>&#128269;</button>"
          )
          youtube_link = _as_text(row.get('TMDB_Trailer'))
          if youtube_link:
              youtube_safe = escape(youtube_link, quote=True)
              yt_button = (
                  f"<button class='film-youtube-btn' type='button' "
                  f"onclick=\"window.open('{youtube_safe}','_blank','noopener');\" "
                  "aria-label='Play trailer'>&#9654;</button>"
              )
          else:
              yt_button = "<button class='film-youtube-btn disabled' type='button' disabled aria-label='No trailer'>&#9654;</button>"
          director_text = _as_text(row.get('Director'))
          director_html = f'<i>{escape(director_text)}</i>' if director_text else ''
          year_text = _as_text(row.get('Year')) or _extract_year(row.get('TMDB_Release_Date'))
          country_text = _as_text(row.get('TMDB_Country'))
          year_country_html = ''
          if year_text and country_text:
              year_country_html = f'{escape(year_text)} ({escape(country_text)})'
          elif year_text:
              year_country_html = escape(year_text)
          elif country_text:
              year_country_html = f'({escape(country_text)})'
          title_parts = [title_cell]
          if director_html:
              title_parts.append('<br>' + director_html)
          if year_country_html:
              title_parts.append('<br>' + year_country_html)
          icons_html = ' '.join([eye_cell, yt_button])
          title_parts.append('<br>' + icons_html)
          combined_title_cell = ''.join(title_parts)
          row_schedule_map = {col: _normalize_schedule_cell(row.get(col)) for col in schedule_columns}
          if not any(row_schedule_map.values()):
              dropped_no_show += 1
              continue
          schedule_payload[row_key] = row_schedule_map
          schedule_html = _compose_schedule_html(row_schedule_map, initial_selection)
          schedule_cell = f"<div class='schedule-cell-content' data-schedule-target='{row_key}'>{schedule_html}</div>"
          row_cells = [
              _poster_cell_markup(poster_url, title),
              combined_title_cell,
              escape(_as_text(row.get('TMDB_Genre'))),
              _format_multiline(row.get('Cinemas')),
              schedule_cell
          ]
          body_parts.append(f"<tr data-film-key='{row_key}'>")
          for cell, cls in zip(row_cells, column_classes):
              class_attr = f" class='{cls}'" if cls else ''
              body_parts.append(f"<td{class_attr}>{cell}</td>")
          body_parts.append('</tr>')
          modal_poster = _modal_poster_markup(poster_url, title)
          modal_html = f"""
  <div id=\"{modal_id}\" class=\"synopsis-modal\" onclick=\"if(event.target===this){{this.style.display='none';}}\">
    <div class=\"synopsis-modal-content\">
      <span class=\"close-synopsis\" onclick=\"this.closest('.synopsis-modal').style.display='none';\">&times;</span>
      <div class=\"modal-body\">
        <div class=\"modal-poster\">{modal_poster}</div>
        <div class=\"modal-details\">
          <h3>{escape(title)}</h3>
          <div class=\"modal-section\">
            <h4>Synopsis</h4>
            <p>{synopsis_html}</p>
          </div>
          <div class=\"modal-section\">
            <h4>Cast</h4>
            <p>{cast_html}</p>
          </div>
          <div class=\"modal-section\">
            <h4>Runtime</h4>
            <p>{runtime_html}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
  """
          modals.append(modal_html)
          kept += 1
      log_msg(f"make_HTML: rows kept={kept}, dropped_no_show={dropped_no_show}")
      body_parts.append('</tbody>')
      return ''.join(body_parts), ''.join(modals), schedule_payload

  def _build_template_components(table_df, schedule_columns, initial_selection):
      headers = BASE_HEADERS + ['Schedule']
      column_classes = BASE_COLUMN_CLASSES + ['col-schedule']
      body_html, modal_html, schedule_payload = _build_rows_and_modals(
          table_df,
          column_classes,
          schedule_columns,
          initial_selection
      )
      return {
          'COLGROUP': _build_column_group(column_classes),
          'TABLE_HEAD': _build_table_head(headers),
          'TABLE_BODY': body_html,
          'MODALS': modal_html
      }, schedule_payload

  def build_schedule_filter(schedule_columns):
      if not schedule_columns:
          return ''
      buttons = []
      for idx, column in enumerate(schedule_columns):
          label = escape(_schedule_display_label(column))
          selected_class = ' is-selected' if idx == 0 else ''
          aria_pressed = 'true' if idx == 0 else 'false'
          buttons.append(
              f"<button class='schedule-filter-btn{selected_class}' type='button' "
              f"data-schedule-key='{escape(column)}' aria-pressed='{aria_pressed}'>"
              f"{label}</button>"
          )
      return (
          "<div class='schedule-filter'>"
          "<span class='schedule-filter-label'>Dates:</span>"
          f"<div class='schedule-filter-buttons'>{''.join(buttons)}</div>"
          "</div>"
      )

  def build_schedule_payload_script(schedule_columns, schedule_payload, initial_selection):
      if not schedule_columns:
          return ''
      meta = {
          'columns': [{'key': col, 'label': _schedule_display_label(col)} for col in schedule_columns],
          'rows': schedule_payload,
          'initialSelected': initial_selection
      }
      payload_json = json.dumps(meta)
      escaped_payload = payload_json.replace('</', '<' + '/')
      script_lines = [
          "<script id=\"schedule-data\" type=\"application/json\">",
          escaped_payload,
          "</script>",
          "<script>",
          "(function() {",
          "  var dataEl = document.getElementById('schedule-data');",
          "  if (!dataEl) return;",
          "  var scheduleData = JSON.parse(dataEl.textContent || '{}');",
          "  var buttons = Array.from(document.querySelectorAll('.schedule-filter-btn'));",
          "  var fallbackSelection = (scheduleData.columns && scheduleData.columns.length) ? [scheduleData.columns[0].key] : [];",
          "  var selectedKeys = new Set((scheduleData.initialSelected && scheduleData.initialSelected.length) ? scheduleData.initialSelected : fallbackSelection);",
          "  var multiSelect = true;",
          "",
          "  function escapeHtml(str) {",
          "    return String(str).replace(/[&<>\\\"']/g, function(ch) {",
          "      switch (ch) {",
          "        case '&': return '&amp;';",
          "        case '<': return '&lt;';",
          "        case '>': return '&gt;';",
          "        case '\\\"': return '&quot;';",
          "        case '\\'': return '&#39;';",
          "        default: return ch;",
          "      }",
          "    });",
          "  }",
          "",
          "  function buildScheduleHtml(scheduleMap, orderedKeys) {",
          "    var fragments = [];",
          "    orderedKeys.forEach(function(key) {",
          "      var times = scheduleMap[key];",
          "      if (!times || !times.length) { return; }",
          "      var labelEntry = (scheduleData.columns || []).find(function(col) { return col.key === key; });",
          "      var displayLabel = labelEntry ? labelEntry.label : key.replace(/^Schedule\\s+/, '');",
          "      var timesHtml = times.map(function(time) { return escapeHtml(time); }).join(', ');",
          "      fragments.push(",
          "        '<div class=schedule-day-line><span class=schedule-day-label>' + escapeHtml(displayLabel) + '</span>: ' +",
          "        '<span class=schedule-day-times>' + timesHtml + '</span></div>'",
          "      );",
          "    });",
          "    return { html: fragments.join(''), hasShows: fragments.length > 0 };",
          "  }",
          "",
          "  function renderSchedules() {",
          "    var orderedKeys = (scheduleData.columns || []).map(function(col) { return col.key; }).filter(function(key) { return selectedKeys.has(key); });",
          "    var targets = document.querySelectorAll('[data-schedule-target]');",
          "    targets.forEach(function(target) {",
          "      var rowKey = target.getAttribute('data-schedule-target');",
          "      var scheduleMap = scheduleData.rows[rowKey] || {};",
          "      var result = buildScheduleHtml(scheduleMap, orderedKeys);",
          "      var rowEl = target.closest('tr');",
          "      if (rowEl) {",
          "        rowEl.style.display = result.hasShows ? '' : 'none';",
          "      }",
          "      target.innerHTML = result.hasShows ? result.html : '';",
          "    });",
          "  }",
          "",
          "  function updateButtonStates() {",
          "    buttons.forEach(function(btn) {",
          "      var key = btn.getAttribute('data-schedule-key');",
          "      var isSelected = selectedKeys.has(key);",
          "      btn.classList.toggle('is-selected', isSelected);",
          "      btn.setAttribute('aria-pressed', isSelected ? 'true' : 'false');",
          "    });",
          "  }",
          "",
          "  buttons.forEach(function(btn) {",
          "    btn.addEventListener('click', function() {",
          "      var key = btn.getAttribute('data-schedule-key');",
          "      if (!key) { return; }",
          "      if (!multiSelect) {",
          "        selectedKeys.clear();",
          "        selectedKeys.add(key);",
          "      } else {",
          "        if (selectedKeys.has(key)) {",
          "          selectedKeys.delete(key);",
          "        } else {",
          "          selectedKeys.add(key);",
          "        }",
          "        if (!selectedKeys.size && fallbackSelection.length) {",
          "          selectedKeys.add(fallbackSelection[0]);",
          "        }",
          "      }",
          "      updateButtonStates();",
          "      renderSchedules();",
          "    });",
          "  });",
          "",
          "  updateButtonStates();",
          "  renderSchedules();",
          "})();",
          "</script>"
      ]
      return '\n'.join(script_lines)

  def build_schedule_styles(schedule_columns):
      if not schedule_columns:
          return ''
      return """
<style>
  .schedule-filter { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
  .schedule-filter-label { font-weight: 600; color: #C0716D; }
  .schedule-filter-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
  .schedule-filter-btn { padding: 6px 12px; border-radius: 999px; border: 1px solid #C0716D; background: #ffffff; color: #C0716D; cursor: pointer; font-size: 0.85rem; transition: all 0.15s ease; }
  .film-table-container .schedule-filter-btn.is-selected,
  .film-table-container .schedule-filter-btn[aria-pressed=\"true\"] { background: #BE6B66 !important; background-color: #BE6B66 !important; color: #ffffff !important; border-color: #BE6B66 !important; }
  .schedule-filter-btn:focus { outline: 2px solid #C0716D; outline-offset: 2px; }
  .schedule-day-line { margin-bottom: 6px; }
  .schedule-day-line:last-child { margin-bottom: 0; }
  .schedule-day-label { font-weight: 600; color: #C0716D; margin-right: 4px; }
  .schedule-day-times { color: #000000; }
  .schedule-empty { color: #999999; font-style: italic; }
</style>
      """

  def load_template(path=TEMPLATE_PATH):
      with open(path, 'rt') as f:
          return f.read()

  def render_template(template_str, components):
      rendered = template_str
      for placeholder, value in components.items():
          key = f"__{placeholder}__"
          if key not in rendered:
              raise ValueError(f"Missing placeholder {key} in template")
          rendered = rendered.replace(key, value)
      return rendered

  def save_and_push(html_content, local_filename=HTML_PARIS_FILMS_BB, bucket='bergershops'):
      with open(local_filename, 'wt') as f:
          f.write(html_content)
      log_msg('Done saving films HTML table locally')
      push_b2_file(bucket, local_filename, local_filename)
      log_msg('Done saving films HTML table into BlackBlaze')

  # Main
  table_films = load_show_times()
  x_perplexity, x_failed = load_film_references()
  table_filled = table_films.join(x_perplexity, on='Title', how='left')
  table_df = prepare_table_dataframe(table_filled)
  schedule_columns = [col for col in table_df.columns if _is_schedule_column(col)]
  initial_selection = schedule_columns[:1]
  template_components, schedule_payload = _build_template_components(table_df, schedule_columns, initial_selection)
  template_html = load_template()
  table_HTML = render_template(template_html, template_components)
  filter_html = build_schedule_filter(schedule_columns)
  if filter_html:
      table_HTML = table_HTML.replace('<div class=\"film-table-container\">', f'<div class=\"film-table-container\">{filter_html}', 1)
      table_HTML += build_schedule_styles(schedule_columns)
      table_HTML += build_schedule_payload_script(schedule_columns, schedule_payload, initial_selection)
  # Add timestamp
  table_HTML += f'<BR><span style="font-size: 10px;">Mise à jour: {get_now_french()}</SPAN><BR>'

  save_and_push(table_HTML)



##################################################################
# EXECUTE
def run_cinema_update():
    consolidated_fetch_show_times()
    loop_films_from_perplexity()

    if False:
        run_wiki_and_trailer_fetch()
        run_wikipedia_link_addition()
        add_posters_from_wiki()
    add_TMDB_IDs()
    add_TMBD_details()
    make_HTML()
    log_msg('*** Films done')

##################################################################
# GET THE CINEMA HTML
def get_cinema_html_stored():
    log_msg('Fetching cinema HTML stored file')
    download_file_from_b2('bergershops', HTML_PARIS_FILMS_BB, HTML_PARIS_FILMS_BB)
    with open(HTML_PARIS_FILMS_BB, 'rt') as f:
        html_content = f.read()
    log_msg('Done fetching cinema HTML stored file')
    return html_content
