import asyncio
import logging
from .bike_functions import update_bike_db, get_bike_db_stats
from .bike_functions import DB_NAME_LOCAL, DB_NAME_BB
from .utilities import throw_static_file, log_msg
from flask import Blueprint
import os
##################################################################
# REGISTER BLUEPRINT
bp_bike = Blueprint("bike_bp", __name__)

##################################################################
# QUERY - FETCH CURRENT TEMPERATURE
@bp_bike.route('/fetch_current_bike')
def query_current_bike():
    log_msg(f"query_current_bike  pid= {os.getpid()}")
    try:
        log_msg("query_current_bike start")
        result = 'none'
        log_msg("query_current_bike end")
        return result.to_csv()
    except Exception as e:
        logging.error(f"query_current_bike failed: {e}")
        return f"Error fetching bike: {e}", 500


##################################################################
# QUERY - FORCE UPDATE BIKE DATABASE
@bp_bike.route('/update_bike_db')
def query_update_bike_db():
    log_msg(f'/query_update_bike_db  pid= {os.getpid()}')
    try:
        update_bike_db()
        log_msg("update done")
        log_msg("Getting file...")
        log_msg(f"File name: local=<{DB_NAME_LOCAL}> BB=<{DB_NAME_BB}>")
        x = 'bike updated'
        log_msg("...done")
        return x
    except Exception as e:
        logging.error(f"Force update failed: {str(e)}")
        return f"Error Force update: {str(e)}", 500

##################################################################
# QUERY - BIKE DATABASE STATS
@bp_bike.route('/bike_db_stats')
def query_bike_dt_stats():
    log_msg("querying DB stats")
    dbstats = get_bike_db_stats()
    log_msg("...done dbstats")
    return dbstats