import pandas as pd
from flask import Flask, request
from .utilities import push_b2_file,log_msg, download_file_from_b2_if_absent, get_now_french_noformat, get_now_french, get_now_french_seconds
import os
import requests
import time
from sqlalchemy import create_engine, types
from babel.dates import format_datetime

##################################################################
# GLOBAL VARIABLES
URL_GBFS = "https://data.lime.bike/api/partners/v2/gbfs/paris/gbfs.json"
URL_types = 'https://data.lime.bike/api/partners/v2/gbfs/paris/vehicle_types.json'
list_fields_cat = ['bike_id','propulsion_type','form_factor','date_time']
SQL_URL = os.getenv('RENDER_DB_URL')
_sql_engine = None

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
# UPDATE THE BIKE DATABASE
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
    print(get_now_french_seconds() + ' Starting SQL append query')
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


##################################################################
# REGULAR CALL TO THE UPDATE_BIKE_DB_FUNCTION
def periodic_query_bike():
    log_msg('Entering background function periodic_query_bike ')
    log_msg('Bike sleep start')
    time.sleep(19 * 60)
    log_msg('Bike sleep end')
    while True:
        log_msg('Periodic bike update through update_bike_db ')
        try:
            update_bike_db()
        except Exception as e:
            log_msg('Error in periodic bike update: ' + str(e))
        else:
            log_msg('Periodic bike update done')
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
