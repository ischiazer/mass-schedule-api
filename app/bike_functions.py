import pandas as pd
from flask import Flask, request
from .utilities import push_b2_file,log_msg, download_file_from_b2_if_absent, get_now_french_noformat, get_now_french, get_now_french_seconds
import os
import requests
import time
from sqlalchemy import create_engine, types
from babel.dates import format_datetime
import datetime

##################################################################
# GLOBAL VARIABLES
URL_GBFS = "https://data.lime.bike/api/partners/v2/gbfs/paris/gbfs.json"
URL_types = 'https://data.lime.bike/api/partners/v2/gbfs/paris/vehicle_types.json'
list_fields_cat = ['bike_id','propulsion_type','form_factor','date_time']
URL_DOTT = 'https://gbfs.api.ridedott.com/public/v2/brussels/free_bike_status.json'
SQL_URL = os.getenv('RENDER_DB_URL')
_sql_engine = None
URL_sources_all_bikes = [
    ['dott','paris', 'https://gbfs.api.ridedott.com/public/v2/paris/free_bike_status.json'],
    ['dott','brussels', 'https://gbfs.api.ridedott.com/public/v2/brussels/free_bike_status.json'],
    ['dott','milan', 'https://gbfs.api.ridedott.com/public/v2/milan/free_bike_status.json'],
    ['dott','rome', 'https://gbfs.api.ridedott.com/public/v2/rome/free_bike_status.json'],
    ['dott','munich', 'https://gbfs.api.ridedott.com/public/v2/munich/free_bike_status.json'],
    ['dott','frankfurt','https://gbfs.api.ridedott.com/public/v2/frankfurt/free_bike_status.json'],
    ['dott','hamburg', 'https://gbfs.api.ridedott.com/public/v2/hamburg/free_bike_status.json'],
    ['dott','berlin','https://gbfs.api.ridedott.com/public/v2/berlin/free_bike_status.json'],
    ['dott','copenhagen','https://gbfs.api.ridedott.com/public/v2/copenhagen/free_bike_status.json'],
    ['dott','warsaw', 'https://gbfs.api.ridedott.com/public/v2/warsaw/free_bike_status.json'],
    ['dott','lyon', 'https://gbfs.api.ridedott.com/public/v2/lyon/free_bike_status.json'],
    ['dott','budapest', 'https://gbfs.api.ridedott.com/public/v2/budapest/free_bike_status.json'],
    ['dott','leipzig', 'https://gbfs.api.ridedott.com/public/v2/leipzig/free_bike_status.json'],
    ['dott','cologne','https://gbfs.api.ridedott.com/public/v2/cologne/free_bike_status.json'],
    ['bird','milan','https://mds.bird.co/gbfs/v2/public/milan/free_bike_status.json'],
    ['bird','rome','https://mds.bird.co/gbfs/v2/public/rome/free_bike_status.json'],
    ['bird','barcelona','https://mds.bird.co/gbfs/v2/public/barcelona/free_bike_status.json'],
    ['bird','madrid','https://mds.bird.co/gbfs/v2/public/madrid/free_bike_status.json'],
    ['bird','zurich','https://mds.bird.co/gbfs/v2/public/zurich/free_bike_status.json'],
    ['bird','lisbon','https://mds.bird.co/gbfs/v2/public/lisbon/free_bike_status.json'],
    ['donkey','barcelona','https://stables.donkey.bike/api/public/gbfs/2/donkey_barcelona/en/free_bike_status.json'],
    ['donkey','copenhagen', 'https://stables.donkey.bike/api/public/gbfs/2/donkey_copenhagen/en/free_bike_status.json'],
    ['donkey','geneva','https://stables.donkey.bike/api/public/gbfs/2/donkey_ge/de/free_bike_status.json']
]

##################################################################
# RETURN SQL ENGINE (AND START ONE IF THERE IS NONE)
def get_sql_engine():
    global _sql_engine
    if _sql_engine is None:
        log_msg('Bike DB engine set up starting')
        _sql_engine = create_engine(
            SQL_URL,
            pool_size=5,
            max_overflow=2,
            pool_timeout=30,
            pool_recycle=1800,
            future=True
        )
        log_msg('Bike DB engine set up done')
    else:
        log_msg('Bike DB engine already in place')
    return _sql_engine

##################################################################
# START THE SQL ENGINE
_temp = get_sql_engine()


##################################################################
# FILES
if os.path.abspath('.').endswith(('/app/', '/app')):
    BASE_FOLDER = '../app_files/bike_files/'
else:
    BASE_FOLDER = 'app_files/bike_files/'
os.makedirs(BASE_FOLDER, exist_ok=True)
log_msg('Bike python file dir  = ' + os.path.abspath('.'))
log_msg('Folder created for bike')


############################################################################
# ONE-OFF DOWNLOAD LIME BIKE DATA
def download_bikes(url_locations, url_types):
    print(get_now_french() + ' Bike download start')
    disc = requests.get(url_locations).json()
    feeds = {f["name"]: f["url"] for f in disc["data"]["en"]["feeds"]}
    
    # Get mapping of vehicles types
    source_types = requests.get(url_types).json()
    table_types = pd.DataFrame(source_types['data']['vehicle_types']).set_index("vehicle_type_id")
    table_types = table_types[['form_factor','propulsion_type']]

    # Prefer vehicle_status if present; else use free_bike_status
    vehicle_status_url = feeds.get("vehicle_status") or feeds.get("free_bike_status")

    # Make timestamp
    now_paris = get_now_french_noformat()

    # Get data    
    data = requests.get(vehicle_status_url).json()
    
    # Normalize: some feeds put vehicles under "vehicles", older ones under "bikes"
    vehicles = (data.get("data", {}).get("vehicles")
                or data.get("data", {}).get("bikes")
                or [])
    vehicles = pd.DataFrame(vehicles)
    vehicles = vehicles[[c for c in vehicles.columns if (not (c in ['vehicle_type','form_factor','propulsion_type']))]]
    vehicles = vehicles.join(table_types, how='left', on='vehicle_type_id')
    print(get_now_french() + ' Bike # entries '+str(vehicles.shape[0]))
    
    # Store the extraction time
    vehicles['date_time'] = now_paris
    
    # Convert into categories
    for f in list_fields_cat:
        vehicles[f] =vehicles[f].astype('category')
        
    # Return result
    print(get_now_french() + ' Bike download end')
    return vehicles.copy()

############################################################################
# ONE-OFF DOWNLOAD DOTT BIKE DATA
def download_dott_bikes():
    log_msg('Downloading Dott bike data (1)')
    t = pd.Timestamp.now(tz='Europe/Paris')
    log_msg('Downloading Dott bike data (2)')
    data = requests.get(URL_DOTT).json()
    log_msg('Downloading Dott bike data (3)')
    x = pd.DataFrame.from_dict(data['data']['bikes'])
    x['scrape_time'] = t
    t_str = t.strftime('%Y-%m-%d %H:%M')
    x['time_str'] = t_str
    log_msg('Downloading Dott bike data (4 - done time=' + t_str + ')')
    return x
############################################################################
# ONE-OFF DOWNLOAD DOTT BIKE DATA
def download_all_bikes():
    log_msg('Downloading all cities bike data (1)')
    list_data = []
    for source in URL_sources_all_bikes:
        provider = source[0]
        city = source[1]
        url = source[2]
        log_msg('\n==> Bikes ==> ' + provider + ' / ' + city)
        log_msg('\tDownloading bike data (1)')
        t = pd.Timestamp.now(tz='Europe/Paris')
        log_msg('\tDownloading all cities bike data (2)')
        data = requests.get(url).json()
        log_msg('\tDownloading all cities bike data (3)')
        x = pd.DataFrame.from_dict(data['data']['bikes'])
        x['scrape_time'] = t
        t_str = t.strftime('%Y-%m-%d %H:%M')
        x['time_str'] = t_str
        x['city'] = city
        x['provider'] = provider
        log_msg('Downloading all cities bike data (4 - done time=' + t_str + ')')
        list_data.append(x)
    x = pd.concat(list_data)
    return x

############################################################################
# UPDATE THE LIME BIKE DATABASE
def update_bike_db():
    # Get the new bike data
    print(get_now_french_seconds() + ' Downloading bike data...')
    x = download_bikes(URL_GBFS, URL_types)
    print(get_now_french_seconds() + ' appending data to SQL database')
    if pd.api.types.is_datetime64_any_dtype(x["date_time"]):
        if x["date_time"].dt.tz is None:
            x["date_time"] = x["date_time"].dt.tz_localize("UTC")
        else:
            x["date_time"] = x["date_time"].dt.tz_convert("UTC")

    # dtype mapping for SQL
    pg_types = {
        "date_time":            types.DateTime(timezone=True),
        "bike_id":              types.Text(),
        "lat":                  types.Float(precision=53),
        "lon":                  types.Float(precision=53),
        "is_reserved":          types.Boolean(),
        "is_disabled":          types.Boolean(),
        "current_range_meters": types.Integer(),
        "vehicle_type_id":      types.Text(),
        "last_reported":        types.BigInteger(),
        "form_factor":          types.Text(),
        "propulsion_type":      types.Text(),
    }

    # Append newly downloaded data to SQL DB
    print(get_now_french_seconds() + ' Starting SQL append query ')
    x.to_sql(
        "bikeactivity",
        get_sql_engine(),
        if_exists="append",
        index=False,
        dtype=pg_types,
        method="multi", 
        chunksize=1000
    )
    print(get_now_french_seconds() + ' Completed SQL append query')


############################################################################
# UPDATE THE DOTT BIKE DATABASE
def update_dott_db():
    # Get the new dott data
    x = download_dott_bikes()

    # dtype mapping for SQL
    pg_types = {
        'bike_id':              types.Text(),
        'current_range_meters': types.Float(),
        "is_disabled":          types.Boolean(),
        "is_reserved":          types.Boolean(),
        "last_reported":        types.Float(),
        "lat":                  types.Float(),
        "lon":                  types.Float(),
        "current_fuel_percent": types.Float(),
        'pricing_plan_id':      types.Text(),
        "vehicle_type_id":      types.Text(),
        "scrape_time":           types.TIMESTAMP(timezone=True),
        "time_str":              types.Text(),
    }

    # Append newly downloaded data to SQL DB
    log_msg('Appending Dott data to SQL database - start')
    n_rows = int(pd.read_sql('SELECT COUNT(*) FROM dottbrussels', get_sql_engine()).iloc[0,0])
    log_msg('Dott rows before = ' + str(n_rows))
    scrape_time = x['time_str'].iloc[0]
    log_msg('Dott scrape_time = ' + scrape_time)
    log_msg('Dott data shape = ' + str(x.shape))
    try:
        n_added = x[[k for k in pg_types.keys()]].to_sql(
            "dottbrussels",
            get_sql_engine(),
            if_exists="append",
            schema="public",
            index=False,
            dtype=pg_types,
            method="multi", 
            chunksize=1000
        )
    except Exception as e:
        log_msg('Error in appending Dott data to SQL database: ' + str(e))
    else:
        log_msg('Appending Dott data to SQL database - successful - added ' + str(n_added) + ' rows'    )
    n_rows = int(pd.read_sql('SELECT COUNT(*) FROM dottbrussels', get_sql_engine()).iloc[0,0])
    log_msg('Dott rows after = ' + str(n_rows))
    log_msg('Appending Dott data to SQL database - end')



############################################################################
# UPDATE THE ALL-CITIES BIKE DATABASE
def update_all_bikes_db():
    # Get the new all-cities bike data
    x = download_all_bikes()

    # dtype mapping for SQL
    pg_types = {
        'bike_id':              types.Text(),
        "lat":                  types.Float(),
        "lon":                  types.Float(),
        "is_reserved":          types.Boolean(),
        "is_disabled":          types.Boolean(),
        'current_range_meters': types.Float(),
        "last_reported":        types.Float(),
        "scrape_time":          types.TIMESTAMP(timezone=True),
        "time_str":             types.Text(),
        'city':                 types.Text(),
        'provider':             types.Text(),
        "current_fuel_percent": types.Float(),
        'pricing_plan_id':      types.Text(),
        'station_id':           types.Text(),
        "vehicle_type_id":      types.Text(),
    }

    # Append newly downloaded data to SQL DB
    log_msg('Appending all cities bike data to SQL database - start')
    n_rows = int(pd.read_sql('SELECT COUNT(*) FROM all_bikes', get_sql_engine()).iloc[0,0])
    log_msg('All-cities rows before = ' + str(n_rows))
    scrape_time = x['time_str'].iloc[0]
    log_msg('All-cities scrape_time = ' + scrape_time)
    log_msg('All-cities data shape = ' + str(x.shape))
    try:
        n_added = x[[k for k in pg_types.keys()]].to_sql(
            "all_bikes",
            get_sql_engine(),
            if_exists="append",
            schema="public",
            index=False,
            dtype=pg_types,
            method="multi", 
            chunksize=1000
        )
    except Exception as e:
        log_msg('Error in appending all-cities bike data to SQL database: ' + str(e))
    else:
        log_msg('Appending all-cities bike data to SQL database - successful - added ' + str(n_added) + ' rows'    )
    n_rows = int(pd.read_sql('SELECT COUNT(*) FROM all_bikes', get_sql_engine()).iloc[0,0])
    log_msg('All-cities rows after = ' + str(n_rows))
    log_msg('Appending all-cities bike data to SQL database - end')


##################################################################
# REGULAR CALL TO THE LIME UPDATE_BIKE_DB_FUNCTION
def periodic_query_bike():
    log_msg('Entering background function periodic_query_bike ')
    log_msg('Bike sleep start')
    time.sleep(7 * 60)
    log_msg('Bike sleep end')
    while True:
        log_msg('Periodic bike update through update_bike_db ')
        try:
            update_bike_db()
        except Exception as e:
            log_msg('Error in periodic bike update: ' + str(e))
        else:
            log_msg('Periodic bike update done')
        time.sleep(30 * 60)

##################################################################
# REGULAR CALL TO THE DOTT UPDATE_DOTT_DB_FUNCTION
def periodic_query_dott():
    log_msg('Entering background function periodic_query_dott ')
    log_msg('Dott sleep start')
    time.sleep(60*4)
    log_msg('Dott sleep end')
    while True:
        log_msg('Periodic dott update through periodic_query_dott ')
        try:
            update_dott_db()
        except Exception as e:
            log_msg('Error in periodic Dott update: ' + str(e))
        else:
            log_msg('Periodic Dott update done')
        time.sleep(10 * 60)
##################################################################
# REGULAR CALL TO THE ALL-CITIES periodic_query_all_bikes
def periodic_query_all_bikes():
    log_msg('Entering background function periodic_query_dott ')
    log_msg('All-cities sleep start')
    time.sleep(9*60)
    log_msg('All-cities sleep end')
    while True:
        log_msg('Periodic all-cities update through periodic_query_all_bikes ')
        try:
            update_all_bikes_db()
        except Exception as e:
            log_msg('Error in periodic all-cities update: ' + str(e))
        else:
            log_msg('Periodic all-cities update done')
        time.sleep(10 * 60)


############################################################################
# GET BIKE DATABASE STATS
def get_bike_db_stats():
    print(get_now_french() + ' Creating bike stats...')

    # Run query
    print(get_now_french_seconds() + ' Querying SQL data stats')
    query = "SELECT date_time, COUNT(*) AS n_rows FROM bikeactivity GROUP BY date_time ORDER BY date_time;"
    x = pd.read_sql(query, get_sql_engine()).set_index('date_time')
    print(get_now_french_seconds() + ' Qdone qerying SQL data stats')
    
    # Create summary Pandas
    x.index = [format_datetime(d.tz_convert("Europe/Paris"),'dd-MM-y HH:mm',locale='fr_FR') for d in x.index]
    
    # Create HTML
    s = '<TABLE><tr><TH>Time</TH><TH></TH><TH>Count</TH>\n'
    for d in x.index:
        s += '<TR><TD>' + d + '</TD><TD> - - </TD><TD>' + str(x.loc[d, 'n_rows']) + '</TD>\n'
    s += '</TABLE>\n'
    
    # Return HTML
    return s
log_msg('Bike code read')
