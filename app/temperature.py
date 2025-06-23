import asyncio
import logging
from .temperature_functions import temperature_current, update_temperatures
from .temperature_functions import TEMPERATURE_CSV_BB, TEMPERATURE_CSV_LOCAL
from .utilities import throw_static_file, log_msg
from flask import Blueprint

##################################################################
# REGISTER BLUEPRINT
bp_temperature = Blueprint("temperature_bp", __name__)

##################################################################
# QUERY - FETCH CURRENT TEMPERATURE
@bp_temperature.route('/fetch_current_temperature')
def query_current_temperature():
    log_msg("fetch_current_temperature")
    try:
        log_msg("fetch_current_temperature start")
        result = asyncio.run(temperature_current())
        log_msg("fetch_current_temperature end")
        return result.to_csv()
    except Exception as e:
        logging.error(f"Current temperature failed: {e}")
        return f"Error fetching temperature: {e}", 500

##################################################################
# QUERY - FETCH TEMPERATURE HISTORY
@bp_temperature.route('/fetch_temperature_history')
def query_historical_temperature():
    log_msg("fetch_temperature_history")
    log_msg(f"File name: BB=<{TEMPERATURE_CSV_BB}> local=<{TEMPERATURE_CSV_LOCAL}>")
    try:
        return throw_static_file('temperature', TEMPERATURE_CSV_LOCAL, TEMPERATURE_CSV_BB, "Fetched historical temperatures")
    except Exception as e:
        logging.error(f"History fetch failed: {str(e)}")
        return f"Error fetching history: {e}", 500

##################################################################
# QUERY - FORCE UPDATE TEMPERATURE
@bp_temperature.route('/update_temperature')
def query_update_temperature():
    log_msg("force update_temperature")
    try:
        update_temperatures()
        log_msg("update done")
        log_msg("Getting file...")
        log_msg(f"File name: local=<{TEMPERATURE_CSV_LOCAL}> BB=<{TEMPERATURE_CSV_BB}>")
        x = throw_static_file('temperature', TEMPERATURE_CSV_LOCAL, TEMPERATURE_CSV_BB, "Fetched historical temperatures")
        log_msg("...done")
        return x
    except Exception as e:
        logging.error(f"Force update failed: {str(e)}")
        return f"Error Force update: {str(e)}", 500
