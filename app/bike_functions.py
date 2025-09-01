import pandas as pd
from flask import Flask, request
from .utilities import push_b2_file,log_msg, download_file_from_b2_if_absent, get_now_french_noformat, get_now_french
import os
import requests
import pickle
import time

##################################################################
# GLOBAL VARIABLES
URL_GBFS = "https://data.lime.bike/api/partners/v2/gbfs/paris/gbfs.json"
URL_types = 'https://data.lime.bike/api/partners/v2/gbfs/paris/vehicle_types.json'
list_fields_cat = ['bike_id','propulsion_type','form_factor','DateTime']


##################################################################
# FILES
if os.path.abspath('.').endswith(('/app/', '/app')):
    BASE_FOLDER = '../app_files/bike_files/'
else:
    BASE_FOLDER = 'app_files/bike_files/'
DB_NAME_LOCAL = os.path.abspath(BASE_FOLDER+'bike.pickle')
DB_NAME_BB = 'bike.pickle'
os.makedirs(BASE_FOLDER, exist_ok=True)
log_msg('Bike python file dir  = ' + os.path.abspath('.'))
log_msg('Bike local DB file = ' + DB_NAME_LOCAL)
log_msg('Folder created for bike')
download_file_from_b2_if_absent('bikedata', DB_NAME_BB, DB_NAME_LOCAL)


##################################################################
# UPLOAD DATABASE TO BLACKBLAZE
def update_b2_DB():
    log_msg('Pushing bike DB to B2...')
    push_b2_file('bikedata',DB_NAME_LOCAL, DB_NAME_BB)
    log_msg('...Done')
    

############################################################################
# ONE-OFF DOWNLOAD LIME BIKE DATA
def download_bikes(url_locations, url_types):
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
    
    # Store the extraction time
    vehicles['DateTime'] = now_paris
    
    # Convert into categories
    for f in list_fields_cat:
        vehicles[f] =vehicles[f].astype('category')
        
    # Return result
    return vehicles.copy()

############################################################################
# UPDATE THE BIKE DATABASE
def update_bike_db():
    print(get_now_french() + ' Downloading bike data...')
    x = download_bikes(URL_GBFS, URL_types)
    with open(DB_NAME_LOCAL, 'rb') as f:
        db = pickle.load(f)
    db = pd.concat([db, x], ignore_index=True)
    with open(DB_NAME_LOCAL, 'wb') as f:
        pickle.dump(db, f)
    print(get_now_french() + ' ... bike data done & saved')
    push_b2_file('bikedata',DB_NAME_LOCAL, DB_NAME_BB)
    print(get_now_french() + ' pushed to BlackBlaze')

##################################################################
# REGULAR CALL TO THE UPDATE_BIKE_DB_FUNCTION
def periodic_query_bike():
    log_msg('Entering background function periodic_query_bike ')
    time.sleep(3 * 60)
    log_msg('Sleep time elapsed for periodic_query_bike')
    while True:
        log_msg('Periodic bike update through update_bike_db ')
        update_bike_db()
        time.sleep(90 * 60)
