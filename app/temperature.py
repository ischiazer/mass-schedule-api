import asyncio
import logging
from .temperature_functions import temperature_current, update_temperatures
from .temperature_functions import TEMPERATURE_CSV
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
        return "Error fetching temperature", 500

##################################################################
# QUERY - FETCH TEMPERATURE HISTORY
@bp_temperature.route('/fetch_temperature_history')
def query_historical_temperature():
    log_msg("fetch_temperature_history")
    try:
        return throw_static_file('temperature', TEMPERATURE_CSV, TEMPERATURE_CSV, "Fetched historical temperatures")
    except Exception as e:
        logging.error(f"History fetch failed: {str(e)}")
        return "Error fetching history", 500

##################################################################
# QUERY - FORCE UPDATE TEMPERATURE
@bp_temperature.route('/update_temperature')
def query_update_temperature():
    log_msg("force update_temperature")
    try:
        update_temperatures()
        log_msg("update done")
        log_msg("Getting file...")
        x = throw_static_file('temperature', TEMPERATURE_CSV, TEMPERATURE_CSV, "Fetched historical temperatures")
        log_msg("...done")
        return x
    except Exception as e:
        logging.error(f"Force update failed: {str(e)}")
        return "Error Force update", 500
